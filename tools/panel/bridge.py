"""Thread-safe serial bridge for the demo firmware NDJSON protocol."""

from __future__ import annotations

from collections import deque
import json
import threading
import time
from typing import Any

import serial
from serial.tools import list_ports


class SerialBridgeError(RuntimeError):
    """Raised when the panel cannot talk to the demo firmware."""


class SerialBridge:
    def __init__(self, *, history_limit: int = 50) -> None:
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._reader: threading.Thread | None = None
        self._serial: serial.Serial | None = None
        self._history_limit = history_limit
        self._state: dict[str, Any] = {
            "connected": False,
            "port": None,
            "baud": 115200,
            "last_error": None,
            "last_startup": None,
            "last_decision": None,
            "last_status": None,
            "last_ack": None,
            "last_firmware_error": None,
            "history": [],
        }

    def list_ports(self) -> list[dict[str, str]]:
        ports: list[dict[str, str]] = []
        for entry in list_ports.comports():
            ports.append(
                {
                    "device": entry.device,
                    "description": entry.description or "",
                    "hwid": entry.hwid or "",
                }
            )
        return ports

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            state = dict(self._state)
            history = state.get("history")
            if isinstance(history, deque):
                state["history"] = list(history)
            return state

    def connect(self, port: str, *, baud: int = 115200) -> None:
        port = port.strip()
        if not port:
            raise SerialBridgeError("port must not be empty")
        self.disconnect()
        try:
            device = serial.Serial(port=port, baudrate=baud, timeout=0.1)
        except serial.SerialException as exc:
            raise SerialBridgeError(str(exc)) from exc

        with self._lock:
            self._serial = device
            self._state["connected"] = True
            self._state["port"] = port
            self._state["baud"] = baud
            self._state["last_error"] = None

        self._stop.clear()
        self._reader = threading.Thread(target=self._reader_loop, name="panel-serial", daemon=True)
        self._reader.start()

    def disconnect(self) -> None:
        self._stop.set()
        reader = self._reader
        if reader is not None and reader.is_alive():
            reader.join(timeout=1.0)
        self._reader = None

        with self._lock:
            if self._serial is not None:
                try:
                    self._serial.close()
                except serial.SerialException:
                    pass
            self._serial = None
            self._state["connected"] = False
            self._state["port"] = None

    def send_command(self, command: dict[str, Any]) -> None:
        if "command" not in command:
            raise SerialBridgeError("payload must include command")
        encoded = json.dumps(command, separators=(",", ":")).encode("utf-8") + b"\n"
        with self._lock:
            if self._serial is None:
                raise SerialBridgeError("serial port is not connected")
            try:
                self._serial.write(encoded)
                self._serial.flush()
            except serial.SerialException as exc:
                self._state["last_error"] = str(exc)
                raise SerialBridgeError(str(exc)) from exc
            self._append_history("tx", command)

    def load_scenario(self, scenario: dict[str, Any], *, seed: int | None = None) -> None:
        payload = dict(scenario)
        if seed is not None:
            payload["seed"] = seed
        if "seed" not in payload:
            raise SerialBridgeError("scenario requires seed")
        payload["command"] = "load_scenario"
        self.send_command(payload)

    def _append_history(self, direction: str, payload: Any) -> None:
        entry = {"direction": direction, "payload": payload, "timestamp": time.time()}
        history = self._state["history"]
        if not isinstance(history, deque):
            history = deque(history, maxlen=self._history_limit)
            self._state["history"] = history
        history.appendleft(entry)

    def _reader_loop(self) -> None:
        while not self._stop.is_set():
            with self._lock:
                device = self._serial
            if device is None:
                break
            try:
                raw = device.readline()
            except serial.SerialException as exc:
                with self._lock:
                    self._state["last_error"] = str(exc)
                    self._state["connected"] = False
                break
            if not raw:
                continue
            text = raw.decode("utf-8", errors="replace").strip()
            if not text:
                continue
            try:
                message = json.loads(text)
            except json.JSONDecodeError:
                with self._lock:
                    self._append_history("rx_invalid", text)
                continue
            if not isinstance(message, dict):
                continue
            self._handle_message(message)

    def _handle_message(self, message: dict[str, Any]) -> None:
        with self._lock:
            self._append_history("rx", message)
            message_type = message.get("type")
            if message_type == "startup":
                self._state["last_startup"] = message
            elif message_type == "decision":
                self._state["last_decision"] = message
            elif message_type == "status":
                self._state["last_status"] = message
            elif message_type == "ack":
                self._state["last_ack"] = message
            elif message_type == "error":
                self._state["last_firmware_error"] = message