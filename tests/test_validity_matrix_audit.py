"""Host tests for validity mask audit helpers and rule evaluation."""

from __future__ import annotations

from tools.ml.board_engine_audit import OUTPUT_NAMES
from tools.ml.validity_matrix_audit import (
    MASK_COUNT,
    VALIDITY_SLOTS,
    apply_mask,
    base_audit_scenario,
    evaluate_validity_rules,
    mask_label,
    scenario_for_mask,
)


def _decision(
    safe: dict[str, float] | None = None,
    *,
    raw: dict[str, float] | None = None,
) -> dict:
    safe_out = {name: 0.0 for name in OUTPUT_NAMES}
    if safe:
        safe_out.update(safe)
    raw_out = dict(safe_out)
    if raw:
        raw_out.update(raw)
    return {
        "type": "decision",
        "schema_version": 4,
        "schema_hash": "457ddca8b0e5",
        "safe_output": safe_out,
        "raw_output": raw_out,
        "diagnostics": {"inference_status": "ok"},
    }


def test_mask_count_and_slots():
    assert MASK_COUNT == 32768
    assert len(VALIDITY_SLOTS) == 15


def test_mask_label_examples():
    assert mask_label(0) == "none"
    assert "air_temperature" in mask_label(1)
    assert mask_label(32767) != "none"


def test_apply_mask_toggles_global_and_pot():
    scenario = base_audit_scenario()
    apply_mask(scenario, 0)
    assert scenario["validity"]["air_temperature_c"] is False
    assert scenario["pots"][0]["validity"]["soil_moisture_pct"] is False

    apply_mask(scenario, (1 << 0) | (1 << 7))
    assert scenario["validity"]["air_temperature_c"] is True
    assert scenario["pots"][0]["validity"]["soil_moisture_pct"] is True
    assert scenario["pots"][0]["irrigation"]["available"] is True


def test_scenario_for_mask_unique_seed():
    a = scenario_for_mask(42)
    b = scenario_for_mask(43)
    assert a["seed"] == 9042
    assert b["seed"] == 9043


def test_invalid_air_temp_zeros_heater():
    scenario = scenario_for_mask(0)
    scenario["validity"]["air_temperature_c"] = False
    findings = evaluate_validity_rules("case", scenario, _decision({"heater": 0.8}))
    codes = {f.code for f in findings}
    assert "invalid_temp_heater_on" in codes
    assert any(f.severity == "error" for f in findings)


def test_invalid_rh_zeros_humidity_actuators():
    scenario = scenario_for_mask(0)
    findings = evaluate_validity_rules(
        "case",
        scenario,
        _decision({"humidifier": 0.6, "dehumidifier": 0.4}),
    )
    codes = {f.code for f in findings}
    assert "invalid_rh_humidifier_on" in codes
    assert "invalid_rh_dehumidifier_on" in codes


def test_all_valid_cold_triggers_ml_warn():
    scenario = scenario_for_mask((1 << 15) - 1)
    findings = evaluate_validity_rules("case", scenario, _decision())
    codes = {f.code for f in findings}
    assert "cold_no_heat" in codes
    assert "dry_no_humidify" in codes
    assert "dry_soil_no_irrigation" in codes


def test_all_valid_with_engaged_outputs_no_ml_warns():
    scenario = scenario_for_mask((1 << 15) - 1)
    findings = evaluate_validity_rules(
        "case",
        scenario,
        _decision(
            {
                "heater": 0.9,
                "humidifier": 0.9,
                "co2_doser": 0.9,
                "irrigation_pot_1": 0.9,
            }
        ),
    )
    warn_codes = {f.code for f in findings if f.severity == "warn"}
    assert "cold_no_heat" not in warn_codes
    assert "dry_no_humidify" not in warn_codes
    assert "dry_soil_no_irrigation" not in warn_codes
