"""Tests for the growbox control panel helpers."""

import json
import threading
import urllib.error
import urllib.request
from collections import deque
from http.server import ThreadingHTTPServer
from typing import Any

import pytest

from tools.panel import server as panel_server
from tools.panel.bridge import SerialBridge, SerialBridgeError
from tools.panel.form_schema import build_panel_schema, default_scenario
from tools.panel.server import PanelHandler


class FakeBridge:
    """In-memory bridge for HTTP handler tests (no serial hardware)."""

    def __init__(self) -> None:
        self.commands: list[dict[str, Any]] = []
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

    def list_ports(self) -> list[dict[str, Any]]:
        return [
            {
                "device": "/dev/cu.usbmodemFAKE",
                "description": "USB JTAG/serial",
                "hwid": "ESP32",
                "kind": "likely_esp",
                "recommended": True,
            }
        ]

    def snapshot(self) -> dict[str, Any]:
        return dict(self._state)

    def diagnostics_snapshot(self) -> dict[str, Any]:
        return {
            "connected": self._state["connected"],
            "port": self._state["port"],
            "host": {"python": "test", "platform": "test"},
            "device": self._state.get("last_diagnostics"),
            "startup": self._state.get("last_startup"),
        }

    def connect(self, port: str, *, baud: int = 115200, verify: bool = True) -> None:
        port = port.strip()
        if not port:
            raise SerialBridgeError("port must not be empty")
        self.disconnect()
        self._state["connected"] = True
        self._state["port"] = port
        self._state["baud"] = baud
        self._state["last_error"] = None
        if verify:
            self._state["last_status"] = {
                "type": "status",
                "schema_hash": "e12b0cc20edf",
                "mode": "replay",
                "paused": True,
                "step": 0,
            }
            self._state["last_startup"] = {
                "type": "startup",
                "framework": "esp-idf",
                "schema_hash": "e12b0cc20edf",
            }

    def disconnect(self) -> None:
        self._state["connected"] = False
        self._state["port"] = None

    def send_command(self, command: dict[str, Any]) -> None:
        if "command" not in command:
            raise SerialBridgeError("payload must include command")
        if not self._state["connected"]:
            raise SerialBridgeError("serial port is not connected")
        self.commands.append(dict(command))
        SerialBridge._patch_status_from_command(self._state, command)

    def load_scenario(self, scenario: dict[str, Any], *, seed: int | None = None) -> None:
        payload = dict(scenario)
        if seed is not None:
            payload["seed"] = seed
        if "seed" not in payload:
            raise SerialBridgeError("scenario requires seed")
        payload["command"] = "load_scenario"
        self.send_command(payload)


def _http_json(
    method: str, base: str, path: str, body: dict[str, Any] | None = None
) -> tuple[int, dict[str, Any]]:
    data = json.dumps(body or {}).encode("utf-8")
    req = urllib.request.Request(
        f"{base}{path}",
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        payload = exc.read().decode("utf-8")
        return exc.code, json.loads(payload) if payload else {"error": exc.reason}


@pytest.fixture
def panel_http_server(monkeypatch):
    fake = FakeBridge()
    monkeypatch.setattr(panel_server, "BRIDGE", fake)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), PanelHandler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{httpd.server_address[1]}"
    try:
        yield fake, base
    finally:
        httpd.shutdown()
        thread.join(timeout=2.0)


def test_default_scenario_has_nominal_actuators():
    scenario = default_scenario(seed=101)
    assert scenario["seed"] == 101
    assert scenario["actuators"]["heater"]["available"] is True
    assert scenario["actuators"]["fan"]["available"] is True
    assert scenario["zones"][0]["available"] is True
    assert scenario["zones"][0]["irrigation"]["control_type"] == "binary"
    assert scenario["zones"][0]["irrigation"]["available"] is True
    assert scenario["pseudo"]["lights_active"] is False
    assert scenario["sensors"]["air_temperature_c"] == 22.0
    assert scenario["sensors"]["outside_co2_ppm"] == 420.0
    assert scenario["validity"]["outside_co2_ppm"] is True
    assert scenario["safety"]["maximum_air_temperature_c"] == 35.0
    assert scenario["safety"]["binary_threshold"] == 0.5


def test_panel_schema_matches_contract_feature_count():
    schema = build_panel_schema()
    assert schema["feature_count"] == 103
    assert schema["outputs"] == [
        "heater",
        "fan",
        "humidifier",
        "dehumidifier",
        "cooler",
        "co2_doser",
        "irrigation_zone_1",
        "irrigation_zone_2",
        "irrigation_zone_3",
        "irrigation_zone_4",
    ]
    assert len(schema["sections"]) >= 8
    actuators = next(section for section in schema["sections"] if section["id"] == "actuators")
    assert actuators["title"] == "Aktuary"
    zones = next(section for section in schema["sections"] if section["id"] == "zones")
    assert zones["title"] == "Strefy uprawy"
    safety = next(section for section in schema["sections"] if section["id"] == "safety")
    assert len(safety["fields"]) == 15


def test_bridge_snapshot_serializes_history_deque():
    bridge = SerialBridge()
    bridge._state["history"] = deque([{"direction": "rx", "payload": {"type": "ack"}}], maxlen=5)
    snapshot = bridge.snapshot()
    assert isinstance(snapshot["history"], list)
    assert snapshot["history"][0]["payload"]["type"] == "ack"


def test_bridge_patches_last_status_on_transport_commands():
    bridge = SerialBridge()
    bridge._state["last_status"] = {"mode": "closed_loop", "paused": False, "step": 3}
    SerialBridge._patch_status_from_command(
        bridge._state,
        {"command": "mode", "value": "replay"},
    )
    assert bridge._state["last_status"]["mode"] == "replay"
    assert bridge._state["last_status"]["paused"] is True
    SerialBridge._patch_status_from_command(bridge._state, {"command": "resume"})
    assert bridge._state["last_status"]["paused"] is False


def test_bridge_ignores_stale_status_after_transport_command():
    bridge = SerialBridge()
    bridge._state["last_status"] = {"mode": "closed_loop", "paused": False, "step": 1}
    bridge._last_status_tx_at = 10.0
    bridge._last_transport_tx_at = 11.0
    bridge._apply_status_message(
        {"type": "status", "mode": "closed_loop", "paused": True, "step": 1}
    )
    assert bridge._state["last_status"]["paused"] is False


def test_bridge_connect_clears_stale_device_state():
    bridge = SerialBridge()
    bridge._state["last_status"] = {"mode": "closed_loop", "paused": True, "step": 9}
    bridge._state["last_decision"] = {"type": "decision", "step": 9}
    bridge._state["last_firmware_error"] = {"type": "error", "code": "stale"}
    bridge._last_transport_tx_at = 99.0
    bridge._reset_session_state()
    assert bridge._state["last_status"] is None
    assert bridge._state["last_decision"] is None
    assert bridge._state["last_firmware_error"] is None
    assert bridge._last_transport_tx_at == 0.0


def test_bridge_reset_clears_decision_and_step():
    bridge = SerialBridge()
    bridge._state["last_decision"] = {"type": "decision", "step": 12}
    bridge._state["last_status"] = {"mode": "closed_loop", "paused": False, "step": 12}
    SerialBridge._patch_status_from_command(bridge._state, {"command": "reset"})
    assert bridge._state["last_status"]["step"] == 0
    assert bridge._state["last_status"]["paused"] is True
    bridge._apply_ack_message({"type": "ack", "command": "reset"})
    assert bridge._state["last_decision"] is None


def test_bridge_patches_scenario_on_load_scenario():
    bridge = SerialBridge()
    bridge._state["last_status"] = {"mode": "closed_loop", "paused": False, "step": 3}
    SerialBridge._patch_status_from_command(
        bridge._state,
        {
            "command": "load_scenario",
            "seed": 202,
            "sensors": {"air_temperature_c": 21.0, "outside_co2_ppm": 500.0},
            "validity": {"outside_co2_ppm": False},
            "targets": {"co2_ppm": 800.0},
        },
    )
    status = bridge._state["last_status"]
    assert status["step"] == 0
    assert status["paused"] is True
    assert status["seed"] == 202
    assert status["scenario"]["sensors"]["outside_co2_ppm"] == 500.0
    assert status["scenario"]["validity"]["outside_co2_ppm"] is False
    assert status["scenario"]["targets"]["co2_ppm"] == 800.0


def test_bridge_applies_scenario_message():
    bridge = SerialBridge()
    bridge._state["last_status"] = {"mode": "closed_loop", "paused": True, "step": 2}
    bridge._apply_scenario_message(
        {
            "type": "scenario",
            "seed": 101,
            "scenario": {
                "actuators": {"irrigation": {"available": False}},
                "targets": {"co2_ppm": 800.0},
            },
        }
    )
    status = bridge._state["last_status"]
    assert status["seed"] == 101
    assert status["mode"] == "closed_loop"
    assert status["scenario"]["actuators"]["irrigation"]["available"] is False


def test_bridge_light_status_preserves_scenario_snapshot():
    bridge = SerialBridge()
    bridge._state["last_status"] = {
        "mode": "closed_loop",
        "paused": False,
        "step": 1,
        "seed": 101,
        "scenario": {"actuators": {"irrigation": {"available": False}}},
    }
    bridge._apply_status_message(
        {
            "type": "status",
            "mode": "closed_loop",
            "paused": True,
            "step": 1,
            "seed": 101,
        }
    )
    status = bridge._state["last_status"]
    assert status["paused"] is True
    assert status["scenario"]["actuators"]["irrigation"]["available"] is False


def test_bridge_confirms_transport_on_ack():
    bridge = SerialBridge()
    bridge._state["last_status"] = {"mode": "closed_loop", "paused": True, "step": 0}
    bridge._pending_mode_value = "replay"
    bridge._apply_ack_message({"type": "ack", "command": "mode"})
    assert bridge._state["last_status"]["mode"] == "replay"
    assert bridge._state["last_status"]["paused"] is True
    bridge._apply_ack_message({"type": "ack", "command": "resume"})
    assert bridge._state["last_status"]["paused"] is False


def test_bridge_stores_diagnostics_message():
    bridge = SerialBridge()
    bridge._handle_message(
        {
            "type": "diagnostics",
            "heap": {
                "psram_enabled": True,
                "free_internal": 120000,
                "free_psram": 7000000,
            },
            "task": {"main_stack_free_bytes": 4096},
        }
    )
    assert bridge._state["last_diagnostics"]["heap"]["psram_enabled"] is True
    snapshot = bridge.diagnostics_snapshot()
    assert snapshot["device"]["heap"]["free_psram"] == 7000000


def test_classify_port_marks_esp_usbmodem_likely():
    kind = SerialBridge.classify_port("/dev/cu.usbmodem1101", "USB JTAG/serial debug unit")
    assert kind == "likely_esp"


def test_classify_port_marks_bluetooth_unlikely():
    kind = SerialBridge.classify_port("/dev/cu.BoseQC", "Bose QC Headphones Bluetooth")
    assert kind == "unlikely"


def test_list_ports_excludes_unlikely_devices(monkeypatch):
    class FakeComPort:
        def __init__(self, device: str, description: str = "", hwid: str = "") -> None:
            self.device = device
            self.description = description
            self.hwid = hwid

    monkeypatch.setattr(
        "tools.panel.bridge.list_ports.comports",
        lambda: [
            FakeComPort("/dev/cu.usbmodem1101", "USB JTAG/serial debug unit"),
            FakeComPort("/dev/cu.BoseQCUltraHeadphones"),
            FakeComPort("/dev/cu.Bluetooth-Incoming-Port"),
            FakeComPort("/dev/cu.debug-console"),
        ],
    )
    ports = SerialBridge().list_ports()
    assert [port["device"] for port in ports] == ["/dev/cu.usbmodem1101"]


def test_is_growbox_handshake_accepts_status_and_startup():
    assert SerialBridge.is_growbox_handshake(
        {
            "last_status": {
                "type": "status",
                "schema_hash": "e12b0cc20edf",
                "mode": "replay",
            }
        }
    )
    assert SerialBridge.is_growbox_handshake(
        {
            "last_startup": {
                "type": "startup",
                "framework": "esp-idf",
                "schema_hash": "e12b0cc20edf",
            }
        }
    )
    assert not SerialBridge.is_growbox_handshake(
        {"last_status": {"type": "status", "mode": "replay"}}
    )


def test_http_connect_and_disconnect(panel_http_server):
    fake, base = panel_http_server
    status, payload = _http_json("POST", base, "/api/connect", {"port": "/dev/cu.usbmodemFAKE"})
    assert status == 200
    assert payload["connected"] is True
    assert payload["port"] == "/dev/cu.usbmodemFAKE"
    assert payload["last_status"]["type"] == "status"

    status, payload = _http_json("POST", base, "/api/disconnect", {})
    assert status == 200
    assert payload["connected"] is False


def test_http_connect_rejects_empty_port(panel_http_server):
    _fake, base = panel_http_server
    status, payload = _http_json("POST", base, "/api/connect", {"port": "  "})
    assert status == 400
    assert "port" in payload["error"]


def test_http_command_requires_connection(panel_http_server):
    _fake, base = panel_http_server
    status, payload = _http_json("POST", base, "/api/command", {"command": "status"})
    assert status == 400
    assert "not connected" in payload["error"]


def test_http_command_forwards_payload(panel_http_server):
    fake, base = panel_http_server
    _http_json("POST", base, "/api/connect", {"port": "/dev/fake"})
    status, payload = _http_json("POST", base, "/api/command", {"command": "pause"})
    assert status == 200
    assert payload == {"ok": True}
    assert fake.commands[-1] == {"command": "pause"}


def test_http_load_scenario_flattens_payload(panel_http_server):
    fake, base = panel_http_server
    _http_json("POST", base, "/api/connect", {"port": "/dev/fake"})
    scenario = default_scenario(seed=303)
    body = {key: scenario[key] for key in scenario if key != "seed"}
    status, payload = _http_json(
        "POST",
        base,
        "/api/load_scenario",
        {"seed": 303, "scenario": body},
    )
    assert status == 200
    assert payload == {"ok": True}
    sent = fake.commands[-1]
    assert sent["command"] == "load_scenario"
    assert sent["seed"] == 303
    assert sent["sensors"]["air_temperature_c"] == scenario["sensors"]["air_temperature_c"]
    assert sent["zones"][0]["irrigation"]["control_type"] == "binary"


def test_http_step_sends_step_command(panel_http_server):
    fake, base = panel_http_server
    _http_json("POST", base, "/api/connect", {"port": "/dev/fake"})
    status, payload = _http_json("POST", base, "/api/step", {})
    assert status == 200
    assert payload == {"ok": True}
    assert fake.commands[-1] == {"command": "step"}


def test_http_step_forwards_overrides(panel_http_server):
    fake, base = panel_http_server
    _http_json("POST", base, "/api/connect", {"port": "/dev/fake"})
    sensors = {"air_temperature_c": 19.5}
    validity = {"air_temperature_c": True}
    _http_json("POST", base, "/api/step", {"sensors": sensors, "validity": validity})
    assert fake.commands[-1] == {
        "command": "step",
        "sensors": sensors,
        "validity": validity,
    }


def test_panel_serves_static_assets():
    server = ThreadingHTTPServer(("127.0.0.1", 0), PanelHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{server.server_address[1]}"
        cases = {
            "/favicon.ico": (b"<svg", "image"),
            "/favicon.svg": (b"<svg", "image"),
            "/panel.css": (b":root", "text/css"),
            "/js/state.js": (b"var panelSchema", "javascript"),
            "/js/main.js": (b"async function init", "javascript"),
        }
        for path, (needle, kind) in cases.items():
            with urllib.request.urlopen(f"{base}{path}") as response:
                body = response.read()
                assert response.status == 200
                assert needle in body
                if kind == "text/css":
                    assert "text/css" in response.headers["Content-Type"]
                elif kind == "javascript":
                    assert "javascript" in response.headers["Content-Type"]
    finally:
        with urllib.request.urlopen(f"{base}/api/diagnostics") as response:
            payload = json.loads(response.read().decode("utf-8"))
            assert response.status == 200
            assert "host" in payload
            assert payload["connected"] is False
        server.shutdown()
        thread.join(timeout=2.0)
