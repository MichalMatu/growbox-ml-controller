"""Thread-safe serial bridge for the demo firmware NDJSON protocol."""

from __future__ import annotations

import json
import threading
import time
from collections import deque
from typing import Any

import serial
from serial.tools import list_ports


class SerialBridgeError(RuntimeError):
    """Raised when the panel cannot talk to the demo firmware."""


_SCENARIO_SNAPSHOT_KEYS = (
    "sensors",
    "validity",
    "zones",
    "pseudo",
    "environment",
    "actuators",
    "targets",
    "safety",
    "previous",
)

_HANDSHAKE_TIMEOUT_S = 2.5
_PORT_UNLIKELY_MARKERS = (
    "bluetooth",
    "incoming-port",
    "airpods",
    "headphone",
    "headset",
    "audio",
    "bose",
    "sony wh",
    "beats",
    "keyboard",
    "mouse",
    "debug-console",
    "wlan-debug",
)
_PORT_LIKELY_MARKERS = (
    "esp",
    "espressif",
    "usb jtag",
    "jtag/serial",
    "cp210",
    "ch340",
    "silicon labs",
    "uart",
)


class SerialBridge:
    def __init__(self, *, history_limit: int = 50) -> None:
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._reader: threading.Thread | None = None
        self._serial: serial.Serial | None = None
        self._history_limit = history_limit
        self._pending_mode_value: str | None = None
        self._last_status_tx_at = 0.0
        self._last_transport_tx_at = 0.0
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
            "last_diagnostics": None,
            "history": [],
        }

    @staticmethod
    def port_is_listable(kind: str) -> bool:
        return kind != "unlikely"

    @staticmethod
    def classify_port(device: str, description: str = "", hwid: str = "") -> str:
        text = f"{device} {description} {hwid}".lower()
        if any(marker in text for marker in _PORT_UNLIKELY_MARKERS):
            return "unlikely"
        if "usbmodem" in device.lower() or any(marker in text for marker in _PORT_LIKELY_MARKERS):
            return "likely_esp"
        if "usbserial" in device.lower():
            return "unknown"
        return "unlikely"

    @staticmethod
    def is_growbox_handshake(state: dict[str, Any]) -> bool:
        startup = state.get("last_startup")
        if isinstance(startup, dict) and startup.get("type") == "startup":
            if startup.get("framework") == "esp-idf" and startup.get("schema_hash"):
                return True
        status = state.get("last_status")
        if isinstance(status, dict) and status.get("type") == "status":
            if status.get("schema_hash") and status.get("mode") in {"replay", "closed_loop"}:
                return True
        return False

    def list_ports(self) -> list[dict[str, Any]]:
        ports: list[dict[str, Any]] = []
        for entry in list_ports.comports():
            device = entry.device
            description = entry.description or ""
            hwid = entry.hwid or ""
            kind = self.classify_port(device, description, hwid)
            if not self.port_is_listable(kind):
                continue
            ports.append(
                {
                    "device": device,
                    "description": description,
                    "hwid": hwid,
                    "kind": kind,
                    "recommended": kind == "likely_esp",
                }
            )
        ports.sort(
            key=lambda item: (
                0 if item["recommended"] else 1,
                0 if "usbmodem" in item["device"] else 1,
                item["device"],
            )
        )
        return ports

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            state = dict(self._state)
            history = state.get("history")
            if isinstance(history, deque):
                state["history"] = list(history)
            return state

    def diagnostics_snapshot(self) -> dict[str, Any]:
        import platform
        import sys

        with self._lock:
            return {
                "connected": self._state["connected"],
                "port": self._state["port"],
                "host": {
                    "python": sys.version.split()[0],
                    "platform": platform.system(),
                },
                "device": self._state.get("last_diagnostics"),
                "startup": self._state.get("last_startup"),
            }

    def request_diagnostics(self, *, timeout_s: float = 1.5) -> dict[str, Any] | None:
        self.send_command({"command": "diagnostics"})
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            with self._lock:
                diagnostics = self._state.get("last_diagnostics")
            if isinstance(diagnostics, dict):
                return diagnostics
            time.sleep(0.05)
        with self._lock:
            diagnostics = self._state.get("last_diagnostics")
        return diagnostics if isinstance(diagnostics, dict) else None

    def _reset_session_state(self) -> None:
        self._state["last_status"] = None
        self._state["last_decision"] = None
        self._state["last_ack"] = None
        self._state["last_startup"] = None
        self._state["last_firmware_error"] = None
        self._state["last_diagnostics"] = None
        self._last_transport_tx_at = 0.0
        self._last_status_tx_at = 0.0
        self._pending_mode_value = None

    def _wait_for_growbox_handshake(self, timeout_s: float = _HANDSHAKE_TIMEOUT_S) -> bool:
        try:
            self.send_command({"command": "status"})
        except SerialBridgeError:
            return False
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            with self._lock:
                if self.is_growbox_handshake(self._state):
                    return True
            time.sleep(0.05)
        with self._lock:
            return self.is_growbox_handshake(self._state)

    def connect(self, port: str, *, baud: int = 115200, verify: bool = True) -> None:
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
            self._reset_session_state()
            self._state["connected"] = True
            self._state["port"] = port
            self._state["baud"] = baud
            self._state["last_error"] = None

        try:
            device.reset_input_buffer()
        except serial.SerialException:
            pass

        self._stop.clear()
        self._reader = threading.Thread(target=self._reader_loop, name="panel-serial", daemon=True)
        self._reader.start()

        if verify and not self._wait_for_growbox_handshake():
            self.disconnect()
            raise SerialBridgeError(
                "Wybrany port nie odpowiada jak growbox ML (ESP32-S3). "
                "Wybierz port USB z „usbmodem” / Espressif, nie Bluetooth ani inne urządzenia."
            )

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

    @staticmethod
    def _patch_status_from_command(state: dict[str, Any], command: dict[str, Any]) -> None:
        """Keep last_status transport fields in sync when firmware only returns ack."""
        cmd = command.get("command")
        if cmd not in {"mode", "pause", "resume", "reset", "load_scenario"}:
            return
        status = state.get("last_status")
        if not isinstance(status, dict):
            status = {}
            state["last_status"] = status
        if cmd == "pause":
            status["paused"] = True
        elif cmd == "resume":
            status["paused"] = False
        elif cmd in {"reset", "load_scenario"}:
            status["step"] = 0
            status["paused"] = True
            if cmd == "load_scenario":
                scenario = {
                    key: command[key]
                    for key in _SCENARIO_SNAPSHOT_KEYS
                    if key in command and isinstance(command[key], dict)
                }
                if scenario:
                    status["scenario"] = scenario
                if "seed" in command:
                    status["seed"] = command["seed"]
        elif cmd == "mode":
            value = command.get("value")
            if value in {"replay", "closed_loop"}:
                status["mode"] = value
            if value == "replay":
                status["paused"] = True

    def _apply_status_message(self, message: dict[str, Any]) -> None:
        current = self._state.get("last_status")
        if isinstance(current, dict):
            merged = dict(message)
            if "scenario" not in merged and isinstance(current.get("scenario"), dict):
                merged["scenario"] = current["scenario"]
            if "seed" not in merged and "seed" in current:
                merged["seed"] = current["seed"]
            message = merged
        if self._last_transport_tx_at > self._last_status_tx_at:
            current = self._state.get("last_status")
            if isinstance(current, dict):
                merged = dict(message)
                if "mode" in current:
                    merged["mode"] = current["mode"]
                if "paused" in current:
                    merged["paused"] = current["paused"]
                self._state["last_status"] = merged
                return
        self._state["last_status"] = message

    def _apply_scenario_message(self, message: dict[str, Any]) -> None:
        status = self._state.get("last_status")
        if not isinstance(status, dict):
            status = {}
            self._state["last_status"] = status
        if "seed" in message:
            status["seed"] = message["seed"]
        scenario = message.get("scenario")
        if isinstance(scenario, dict):
            status["scenario"] = scenario

    def _apply_ack_message(self, message: dict[str, Any]) -> None:
        cmd = message.get("command")
        if cmd == "mode" and self._pending_mode_value in {"replay", "closed_loop"}:
            self._patch_status_from_command(
                self._state,
                {"command": "mode", "value": self._pending_mode_value},
            )
            self._pending_mode_value = None
        elif cmd == "pause":
            self._patch_status_from_command(self._state, {"command": "pause"})
        elif cmd == "resume":
            self._patch_status_from_command(self._state, {"command": "resume"})
        elif cmd == "reset":
            self._state["last_decision"] = None
            self._patch_status_from_command(self._state, {"command": "reset"})
        elif cmd == "load_scenario":
            self._state["last_decision"] = None
            self._patch_status_from_command(self._state, {"command": "load_scenario"})

    def send_command(self, command: dict[str, Any]) -> None:
        if "command" not in command:
            raise SerialBridgeError("payload must include command")
        encoded = json.dumps(command, separators=(",", ":")).encode("utf-8") + b"\n"
        with self._lock:
            if self._serial is None:
                raise SerialBridgeError("serial port is not connected")
            cmd = command.get("command")
            now = time.monotonic()
            if cmd == "status":
                self._last_status_tx_at = now
            elif cmd in {"mode", "pause", "resume", "reset", "load_scenario"}:
                if cmd in {"mode", "pause", "resume"}:
                    self._last_transport_tx_at = now
                if cmd == "mode":
                    value = command.get("value")
                    self._pending_mode_value = value if value in {"replay", "closed_loop"} else None
                if cmd in {"reset", "load_scenario"}:
                    self._state["last_decision"] = None
            self._patch_status_from_command(self._state, command)
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
                self._apply_status_message(message)
            elif message_type == "scenario":
                self._apply_scenario_message(message)
            elif message_type == "diagnostics":
                self._state["last_diagnostics"] = message
            elif message_type == "ack":
                self._state["last_ack"] = message
                self._apply_ack_message(message)
            elif message_type == "error":
                self._state["last_firmware_error"] = message
