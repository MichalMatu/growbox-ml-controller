"""Guards for contract-shaped scenario payloads used by panel and serial."""

from __future__ import annotations

import json
import math

import pytest

from tools.ml.scenario_payload import SCENARIO_PRESETS, default_scenario


def _walk(obj, path=""):
    if isinstance(obj, dict):
        for key, value in obj.items():
            yield from _walk(value, f"{path}.{key}" if path else key)
    elif isinstance(obj, list):
        for index, value in enumerate(obj):
            yield from _walk(value, f"{path}[{index}]")
    else:
        yield path, obj


@pytest.mark.parametrize("preset_id", sorted(SCENARIO_PRESETS))
def test_preset_validity_fields_are_bools(preset_id: str):
    scenario = default_scenario(seed=42, preset=preset_id)
    for path, value in _walk(scenario):
        if "validity" in path:
            assert isinstance(value, bool), f"{preset_id}:{path}={value!r}"
        if path.endswith(".available") or path.endswith("lights_active"):
            assert isinstance(value, bool), f"{preset_id}:{path}={value!r}"
        if isinstance(value, float):
            assert math.isfinite(value), f"{preset_id}:{path} non-finite"


@pytest.mark.parametrize("preset_id", sorted(SCENARIO_PRESETS))
def test_preset_has_complete_pots_and_serializes(preset_id: str):
    scenario = default_scenario(seed=7, preset=preset_id)
    assert len(scenario["pots"]) == 4
    for pot in scenario["pots"]:
        assert "targets" in pot and "soil_temperature_c" in pot["targets"]
        assert "control_type" in pot["irrigation"]
        assert "control_type" in pot["heat_mat"]
    payload = {"command": "load_scenario", **scenario}
    raw = json.dumps(payload, separators=(",", ":"))
    assert len(raw) < 8192
