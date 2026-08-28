from __future__ import annotations

from tools.ml.generate_climate_runtime_parity import DEFAULT_OUTPUT, _case_specs, render_header


def test_committed_runtime_parity_header_matches_python_reference() -> None:
    assert DEFAULT_OUTPUT.read_text(encoding="utf-8") == render_header()


def test_runtime_parity_fixture_covers_required_policy_and_safety_cases() -> None:
    names = {case.name for case in _case_specs()}
    assert {
        "rule_nominal",
        "ml_shadow_opposition",
        "ml_active_allowed",
        "ml_active_blocked",
        "ml_provider_missing",
        "ml_inference_failed",
        "required_sensor_invalid",
        "high_temperature",
        "high_humidity",
        "high_co2",
        "unavailable_cooler",
        "vpd_shadow",
    } <= names
