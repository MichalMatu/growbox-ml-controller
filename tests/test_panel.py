"""Tests for the growbox control panel helpers."""

from collections import deque
import json
import threading
from http.server import ThreadingHTTPServer
import urllib.request

from tools.panel.bridge import SerialBridge
from tools.panel.form_schema import build_panel_schema, default_scenario
from tools.panel.server import PanelHandler


def test_default_scenario_has_nominal_actuators():
    scenario = default_scenario(seed=101)
    assert scenario["seed"] == 101
    assert scenario["actuators"]["heater"]["available"] is True
    assert scenario["actuators"]["heater"]["control_type"] == "binary"
    assert scenario["actuators"]["fan"]["control_type"] == "pwm"
    assert scenario["actuators"]["humidifier"]["control_type"] == "binary"
    assert scenario["actuators"]["irrigation"]["control_type"] == "binary"
    assert scenario["sensors"]["air_temperature_c"] == 22.0
    assert scenario["sensors"]["outside_co2_ppm"] == 420.0
    assert scenario["validity"]["outside_co2_ppm"] is True
    assert scenario["safety"]["maximum_air_temperature_c"] == 35.0
    assert scenario["safety"]["binary_threshold"] == 0.5


def test_panel_schema_matches_contract_feature_count():
    schema = build_panel_schema()
    assert schema["feature_count"] == 43
    assert schema["outputs"] == ["heater", "fan", "humidifier", "irrigation"]
    assert len(schema["sections"]) >= 6
    safety = next(section for section in schema["sections"] if section["id"] == "safety")
    assert len(safety["fields"]) == 8


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
    bridge._apply_status_message({"type": "status", "mode": "closed_loop", "paused": True, "step": 1})
    assert bridge._state["last_status"]["paused"] is False


def test_bridge_connect_clears_stale_device_state():
    bridge = SerialBridge()
    bridge._state["last_status"] = {"mode": "closed_loop", "paused": True, "step": 9}
    bridge._state["last_decision"] = {"type": "decision", "step": 9}
    bridge._last_transport_tx_at = 99.0
    bridge._reset_session_state()
    assert bridge._state["last_status"] is None
    assert bridge._state["last_decision"] is None
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
        {"type": "status", "mode": "closed_loop", "paused": True, "step": 1, "seed": 101}
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
            "heap": {"psram_enabled": True, "free_internal": 120000, "free_psram": 7000000},
            "task": {"main_stack_free_bytes": 4096},
        }
    )
    assert bridge._state["last_diagnostics"]["heap"]["psram_enabled"] is True
    snapshot = bridge.diagnostics_snapshot()
    assert snapshot["device"]["heap"]["free_psram"] == 7000000


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
            "/js/state.js": (b"let panelSchema", "javascript"),
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