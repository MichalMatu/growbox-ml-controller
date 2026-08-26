from pathlib import Path

policy = Path("tools/ml/climate_policy.py")
s = policy.read_text()
s = s.replace(
    "def _clip(value: float) -> float:\n    return min(1.0, max(0.0, float(value)))\n\n\n",
    "def _clip(value: float) -> float:\n    return min(1.0, max(0.0, float(value)))\n\n\nML_REQUEST_DEADZONE = 0.05\n\n\ndef apply_ml_request_deadzone(\n    action: ClimateAction, threshold: float = ML_REQUEST_DEADZONE\n) -> ClimateAction:\n    threshold = float(threshold)\n    if not 0.0 <= threshold < 1.0:\n        raise ValueError(\"ML request dead-zone must be in [0, 1)\")\n    values = {\n        name: 0.0 if float(value) <= threshold else float(value)\n        for name, value in action.clipped().as_dict().items()\n    }\n    return ClimateAction.from_mapping(values).clipped()\n\n\n",
)
s = s.replace(
    '    "ClimateSafetyLimits",\n    "apply_climate_safety",\n',
    '    "ClimateSafetyLimits",\n    "ML_REQUEST_DEADZONE",\n    "apply_climate_safety",\n    "apply_ml_request_deadzone",\n',
)
policy.write_text(s)

benchmark = Path("tools/ml/climate_benchmark.py")
s = benchmark.read_text()
s = s.replace(
    "    ClimateRulePolicy,\n    apply_climate_safety,\n",
    "    ClimateRulePolicy,\n    apply_climate_safety,\n    apply_ml_request_deadzone,\n",
)
s = s.replace(
    "    action = ClimateAction.from_mapping(\n        dict(zip(CLIMATE_OUTPUT_NAMES, (float(value) for value in prediction), strict=True))\n    )\n    return action, status\n",
    "    action = ClimateAction.from_mapping(\n        dict(zip(CLIMATE_OUTPUT_NAMES, (float(value) for value in prediction), strict=True))\n    )\n    return apply_ml_request_deadzone(action), status\n",
)
benchmark.write_text(s)

 tests = Path("tests/test_climate_benchmark.py")
s = tests.read_text()
s = s.replace(
    "    ClimateRulePolicy,\n    apply_climate_safety,\n",
    "    ML_REQUEST_DEADZONE,\n    ClimateRulePolicy,\n    apply_climate_safety,\n    apply_ml_request_deadzone,\n",
)
insert = '''\n\ndef test_ml_request_deadzone_turns_sigmoid_tails_off() -> None:\n    assert ML_REQUEST_DEADZONE == 0.05\n    action = apply_ml_request_deadzone(\n        ClimateAction(\n            heater=0.001,\n            cooler=0.05,\n            exhaust_fan=0.05001,\n            humidifier=0.02,\n            dehumidifier=0.0,\n            co2_doser=0.049,\n        )\n    )\n    assert action.heater == 0.0\n    assert action.cooler == 0.0\n    assert action.exhaust_fan == 0.05001\n    assert action.humidifier == 0.0\n    assert action.dehumidifier == 0.0\n    assert action.co2_doser == 0.0\n\n    episode = build_training_episode(\"cold_heating\", 0, 3334)\n    arbitration = arbitrate_climate_action(action, episode.scenario)\n    assert not arbitration.interventions\n\n\ndef test_ml_request_deadzone_rejects_invalid_threshold() -> None:\n    try:\n        apply_ml_request_deadzone(ClimateAction(), threshold=1.0)\n    except ValueError as exc:\n        assert \"dead-zone\" in str(exc)\n    else:\n        raise AssertionError(\"invalid ML dead-zone must be rejected\")\n'''
marker = "\ndef test_safety_zeros_commands_when_required_sensor_is_stale() -> None:\n"
s = s.replace(marker, insert + marker)
tests.write_text(s)

print("STAGE9E_DEADZONE_PATCH_APPLIED")
