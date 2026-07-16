"""Guardrails: active training contract stays aligned with the growbox simulator."""

from __future__ import annotations

import pytest

from tools.ml.alignment import (
    assert_encoded_vector,
    assert_outputs_match_contract,
    load_active_contract,
    summarize_training_fields,
)
from tools.ml.controller_input import controller_input_record
from tools.ml.generate_dataset import random_scenario
from tools.ml.scenario_payload import default_scenario
from tools.ml.simulator import OUTPUT_NAMES, ControlAction, SequentialEnvironmentSimulator


def test_active_contract_is_v4_pots_with_expected_io():
    contract = load_active_contract()
    summary = summarize_training_fields(contract)
    assert summary["schema_version"] == 4
    assert summary["schema_hash"] == "457ddca8b0e5"
    assert summary["feature_count"] == 128
    assert summary["output_count"] == 15
    assert summary["outputs"] == list(OUTPUT_NAMES)
    assert summary["feature_groups"]["sensors"] == 7
    assert summary["feature_groups"]["pots.*.irrigation"] == 20
    assert summary["feature_groups"]["pots.*.heat_mat"] == 12


def test_simulator_outputs_match_active_contract():
    contract = load_active_contract()
    assert_outputs_match_contract(contract, OUTPUT_NAMES)


def test_simulator_outputs_mismatch_raises():
    contract = load_active_contract()
    with pytest.raises(ValueError, match="outputs do not match"):
        assert_outputs_match_contract(contract, OUTPUT_NAMES[:-1])


def test_controller_input_covers_all_feature_paths():
    contract = load_active_contract()
    scenario = random_scenario(0, 42)
    simulator = SequentialEnvironmentSimulator(scenario)
    state = simulator.observe(add_sensor_noise=False)
    record = controller_input_record(
        scenario,
        state,
        validity={
            "air_temperature_c": True,
            "air_humidity_pct": True,
            "co2_ppm": True,
            "nutrient_solution_temperature_c": True,
            "outside_temperature_c": True,
            "outside_humidity_pct": True,
            "outside_co2_ppm": True,
        },
        pot_validity={
            index: {"soil_moisture_pct": True, "soil_temperature_c": True} for index in range(4)
        },
        previous=ControlAction(),
    )
    encoded = contract.encode(record)
    assert_encoded_vector(contract, encoded)


def test_default_scenario_encodes_on_active_contract():
    contract = load_active_contract()
    scenario = default_scenario(seed=7, preset="nominal")
    encoded = contract.encode(scenario)
    assert_encoded_vector(contract, encoded)


def test_scenario_payload_does_not_import_panel():
    import tools.ml.scenario_payload as payload

    # Serial/ML path must stay free of tools.panel.
    assert "tools.panel" not in payload.__name__
    source = payload.__file__ or ""
    assert "tools/ml/" in source.replace("\\", "/")
