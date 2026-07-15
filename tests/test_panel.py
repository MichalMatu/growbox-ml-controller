"""Tests for the growbox control panel helpers."""

from collections import deque

from tools.panel.bridge import SerialBridge
from tools.panel.form_schema import build_panel_schema, default_scenario


def test_default_scenario_has_nominal_actuators():
    scenario = default_scenario(seed=101)
    assert scenario["seed"] == 101
    assert scenario["actuators"]["heater"]["available"] is True
    assert scenario["sensors"]["air_temperature_c"] == 22.0


def test_panel_schema_matches_contract_feature_count():
    schema = build_panel_schema()
    assert schema["feature_count"] == 40
    assert schema["outputs"] == ["heater", "fan", "humidifier", "irrigation"]
    assert len(schema["sections"]) >= 6


def test_bridge_snapshot_serializes_history_deque():
    bridge = SerialBridge()
    bridge._state["history"] = deque([{"direction": "rx", "payload": {"type": "ack"}}], maxlen=5)
    snapshot = bridge.snapshot()
    assert isinstance(snapshot["history"], list)
    assert snapshot["history"][0]["payload"]["type"] == "ack"