"""Contract v3 — nutrient heater + heat mats."""

from __future__ import annotations

import json
import re

import numpy as np

from tools.ml.contract import V3_CONTRACT_PATH, load_contract
from tools.ml.generate_dataset_v2 import controller_input_record_v2, random_scenario_v2
from tools.ml.simulator_v2 import ControlAction, SequentialEnvironmentSimulatorV2


def test_v3_contract_hash_matches_generated_cpp():
    contract = load_contract(V3_CONTRACT_PATH)
    header = (
        contract.path.parent.parent / "lib/environment_control/src/EnvironmentSchemaV3.h"
    ).read_text(encoding="utf-8")
    cpp_hash = re.search(r'kSchemaHash\[\] = "([0-9a-f]+)"', header)
    assert cpp_hash is not None
    assert contract.short_hash == cpp_hash.group(1)
    assert "kFeatureCount = 128U" in header
    assert "kOutputCount = 15U" in header


def test_v3_contract_loads_with_fifteen_outputs():
    contract = load_contract(V3_CONTRACT_PATH)
    assert contract.schema_version == 3
    assert len(contract.outputs) == 15
    assert len(contract.features) == 128
    assert contract.outputs[-5:] == (
        "nutrient_heater",
        "heat_mat_zone_1",
        "heat_mat_zone_2",
        "heat_mat_zone_3",
        "heat_mat_zone_4",
    )


def test_v3_inactive_zone_soil_temperature_target_uses_schema_default():
    contract = load_contract(V3_CONTRACT_PATH)
    controller_input = {
        "zones": [
            {"available": True, "targets": {"soil_temperature_c": 24.0}},
            {"available": False, "targets": {"soil_temperature_c": 31.0}},
        ]
    }
    encoded = contract.encode(controller_input)
    active_index = contract.feature_names.index("zone_1_target_soil_temperature_c")
    inactive_index = contract.feature_names.index("zone_2_target_soil_temperature_c")
    assert encoded[active_index] == contract.features[active_index].normalize(24.0)
    assert encoded[inactive_index] == contract.features[inactive_index].normalize(20.0)


def test_v3_nutrient_heater_features_encode():
    contract = load_contract(V3_CONTRACT_PATH)
    controller_input = {
        "actuators": {
            "nutrient_heater": {
                "available": True,
                "max_power_w": 120.0,
                "efficiency": 0.9,
            }
        },
        "previous": {"nutrient_heater": 0.5},
        "targets": {"nutrient_solution_temperature_c": 22.0},
    }
    encoded = contract.encode(controller_input)
    assert np.all((0.0 <= encoded) & (encoded <= 1.0))


def test_v3_example_scenarios_encode():
    contract = load_contract(V3_CONTRACT_PATH)
    scenario_dir = contract.path.parent.parent / "examples" / "scenarios"
    for scenario_path in sorted(scenario_dir.glob("v3-*.jsonl")):
        records = [
            json.loads(line)
            for line in scenario_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        scenario = next(record for record in records if record.get("command") == "load_scenario")
        encoded = contract.encode(scenario)
        assert encoded.shape == (128,)
        assert np.all((0.0 <= encoded) & (encoded <= 1.0))


def test_v3_full_controller_input_record_encodes():
    scenario = random_scenario_v2(3, 5150)
    simulator = SequentialEnvironmentSimulatorV2(scenario)
    state = simulator.observe(add_sensor_noise=False)
    record = controller_input_record_v2(
        scenario,
        state,
        validity={
            "air_temperature_c": True,
            "air_humidity_pct": True,
            "co2_ppm": scenario.validity.co2_ppm,
            "nutrient_solution_temperature_c": scenario.validity.nutrient_solution_temperature_c,
            "outside_temperature_c": True,
            "outside_humidity_pct": True,
            "outside_co2_ppm": scenario.validity.outside_co2_ppm,
        },
        zone_validity={
            index: {
                "soil_moisture_pct": zone.available and zone.soil_moisture_valid,
                "soil_temperature_c": zone.available and zone.soil_temperature_valid,
            }
            for index, zone in enumerate(scenario.zones)
        },
        previous=ControlAction(),
    )
    contract = load_contract(V3_CONTRACT_PATH)
    encoded = contract.encode(record)
    assert encoded.shape == (128,)
    assert np.all((0.0 <= encoded) & (encoded <= 1.0))
