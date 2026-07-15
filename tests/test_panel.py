"""Tests for the growbox control panel helpers."""

from collections import deque
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
    assert scenario["sensors"]["air_temperature_c"] == 22.0


def test_panel_schema_matches_contract_feature_count():
    schema = build_panel_schema()
    assert schema["feature_count"] == 43
    assert schema["outputs"] == ["heater", "fan", "humidifier", "irrigation"]
    assert len(schema["sections"]) >= 6


def test_bridge_snapshot_serializes_history_deque():
    bridge = SerialBridge()
    bridge._state["history"] = deque([{"direction": "rx", "payload": {"type": "ack"}}], maxlen=5)
    snapshot = bridge.snapshot()
    assert isinstance(snapshot["history"], list)
    assert snapshot["history"][0]["payload"]["type"] == "ack"


def test_panel_serves_favicon_assets():
    server = ThreadingHTTPServer(("127.0.0.1", 0), PanelHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{server.server_address[1]}"
        for path in ("/favicon.ico", "/favicon.svg"):
            with urllib.request.urlopen(f"{base}{path}") as response:
                body = response.read()
                assert response.status == 200
                assert b"<svg" in body
    finally:
        server.shutdown()
        thread.join(timeout=2.0)