"""Panel scenario sync badge and bridge state tracking tests."""

from __future__ import annotations

import copy
import json
from typing import Any

import pytest

from tools.panel.bridge import SerialBridge
from tools.panel.form_schema import build_panel_schema, default_scenario

PANEL_STATIC = (
    __import__("pathlib").Path(__file__).resolve().parents[1] / "tools" / "panel" / "static"
)
SCENARIO_JS = PANEL_STATIC / "js" / "scenario.js"
CONSTANTS_JS = PANEL_STATIC / "js" / "constants.js"
MAIN_JS = PANEL_STATIC / "js" / "main.js"
DEVICE_JS = PANEL_STATIC / "js" / "device.js"
BRIDGE_PY = (
    __import__("pathlib").Path(__file__).resolve().parents[1] / "tools" / "panel" / "bridge.py"
)

SCENARIO_BADGE_KEYS = (
    "sensors",
    "validity",
    "pots",
    "pseudo",
    "environment",
    "actuators",
    "targets",
    "safety",
)


def _extract_js_function(source: str, name: str) -> str | None:
    marker = f"function {name}"
    start = source.find(marker)
    if start < 0:
        return None
    brace = source.find("{", start)
    if brace < 0:
        return None
    depth = 0
    for index in range(brace, len(source)):
        char = source[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source[start : index + 1]
    return None


def badge_payload_python(doc: dict[str, Any]) -> dict[str, Any]:
    """Mirror scenarioBadgePayload() — must stay aligned with scenario.js."""
    payload: dict[str, Any] = {"seed": doc.get("seed", 101)}
    for key in SCENARIO_BADGE_KEYS:
        if key in doc:
            payload[key] = copy.deepcopy(doc[key])
    pots = payload.get("pots")
    if isinstance(pots, list):
        payload["pots"] = [
            {k: v for k, v in pot.items() if k != "previous"} if isinstance(pot, dict) else pot
            for pot in pots
        ]
    return payload


def stable_stringify(value: Any) -> str:
    if isinstance(value, list):
        return "[" + ",".join(stable_stringify(item) for item in value) + "]"
    if isinstance(value, dict):
        keys = sorted(value.keys())
        return (
            "{"
            + ",".join(f"{json.dumps(key)}:{stable_stringify(value[key])}" for key in keys)
            + "}"
        )
    return json.dumps(value)


def badge_fingerprint_python(doc: dict[str, Any]) -> str:
    return stable_stringify(badge_payload_python(doc))


def test_badge_keys_exclude_runtime_previous():
    constants = CONSTANTS_JS.read_text(encoding="utf-8")
    assert "SCENARIO_BADGE_KEYS" in constants
    assert '"previous"' not in constants.split("SCENARIO_BADGE_KEYS", 1)[1].split("];", 1)[0]
    assert '"previous"' in constants.split("SCENARIO_SYNC_KEYS", 1)[1].split("];", 1)[0]


def test_scenario_js_uses_badge_fingerprint_for_sync_badge():
    scenario_js = SCENARIO_JS.read_text(encoding="utf-8")
    badge_fn = _extract_js_function(scenario_js, "updateScenarioSyncBadge")
    baseline_fn = _extract_js_function(scenario_js, "setDeviceScenarioBaseline")
    assert badge_fn
    assert baseline_fn
    assert "scenarioBadgeFingerprint" in badge_fn
    assert "scenarioBadgeFingerprint" in baseline_fn
    assert "scenarioSyncFingerprint(readScenarioFromForm" not in badge_fn
    assert "function scenarioBadgePayload" in scenario_js
    assert "SCENARIO_BADGE_KEYS" in scenario_js
    assert "const { previous, ...rest } = pot" in scenario_js


def test_main_init_uses_cached_device_scenario_on_refresh():
    main_js = MAIN_JS.read_text(encoding="utf-8")
    init_start = main_js.index("async function init")
    init_block = main_js[init_start : main_js.index("function bindToolbar", init_start)]
    assert "hasDeviceScenario(lastState)" in init_block
    assert "tryApplyScenarioFromDevice(lastState, { force: true })" in init_block
    assert "let formRendered = false" in init_block
    assert "if (!formRendered) renderForm()" in init_block
    assert init_block.count("renderForm()") == 1


def test_device_scenario_request_short_circuits_when_snapshot_present():
    device_js = DEVICE_JS.read_text(encoding="utf-8")
    status_fn = _extract_js_function(device_js, "requestDeviceStatus")
    scenario_fn = _extract_js_function(device_js, "requestDeviceScenario")
    assert status_fn
    assert scenario_fn
    assert "hasDeviceStatus(lastState)" in status_fn
    assert "hasDeviceScenario(lastState)" in scenario_fn


def test_badge_fingerprint_ignores_previous_mutations():
    scenario = default_scenario(seed=101)
    baseline = badge_fingerprint_python(scenario)
    mutated = copy.deepcopy(scenario)
    mutated["previous"]["fan"] = 0.88
    mutated["pots"][0]["previous"]["irrigation"] = 0.42
    assert badge_fingerprint_python(mutated) == baseline


def test_badge_fingerprint_detects_target_edits():
    scenario = default_scenario(seed=101)
    baseline = badge_fingerprint_python(scenario)
    edited = copy.deepcopy(scenario)
    edited["targets"]["air_temperature_c"] = 27.5
    assert badge_fingerprint_python(edited) != baseline


def test_bridge_updates_status_step_from_decision():
    bridge = SerialBridge()
    bridge._state["last_status"] = {"mode": "closed_loop", "paused": False, "step": 0}
    bridge._handle_message(
        {
            "type": "decision",
            "step": 7,
            "simulated_time_s": 70,
            "safe_output": {"fan": 0.2},
        }
    )
    status = bridge._state["last_status"]
    assert status["step"] == 7
    assert status["simulated_time_s"] == 70
    assert bridge._state["last_decision"]["step"] == 7


def test_panel_schema_hash_matches_v3_contract():
    schema = build_panel_schema()
    assert schema["schema_version"] == 4
    assert schema["schema_hash"] == "5768273a73ac"
    assert len(schema["outputs"]) == 15


@pytest.mark.parametrize("preset_id", ["nominal", "disabled_actuators", "saturated_soil"])
def test_default_scenario_badge_payload_roundtrip(preset_id: str):
    scenario = default_scenario(seed=202, preset=preset_id)
    payload = badge_payload_python(scenario)
    assert "previous" not in payload
    for pot in payload["pots"]:
        assert "previous" not in pot
    assert payload["seed"] == 202
    assert "actuators" in payload
