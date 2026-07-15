from __future__ import annotations

import re

import numpy as np

from tools.ml.contract import V2_CONTRACT_PATH, load_contract
from tools.ml.generate_dataset_v2 import controller_input_record_v2, random_scenario_v2
from tools.ml.simulator_v2 import ControlAction, SequentialEnvironmentSimulatorV2


def test_v2_contract_loads_with_ten_outputs():
    contract = load_contract(V2_CONTRACT_PATH)
    assert contract.schema_version == 2
    assert len(contract.outputs) == 10
    assert len(contract.features) == 103
    assert contract.outputs[0] == "heater"
    assert contract.outputs[-1] == "irrigation_zone_4"


def test_v2_contract_hash_matches_generated_cpp():
    contract = load_contract(V2_CONTRACT_PATH)
    header = (
        contract.path.parent.parent / "lib/environment_control/src/EnvironmentSchemaV2.h"
    ).read_text(encoding="utf-8")
    cpp_hash = re.search(r'kSchemaHash\[\] = "([0-9a-f]+)"', header)
    assert cpp_hash is not None
    assert contract.short_hash == cpp_hash.group(1)
    assert "kFeatureCount = 103U" in header
    assert "kOutputCount = 10U" in header


def test_v2_zone_sensor_validity_masking():
    contract = load_contract(V2_CONTRACT_PATH)
    controller_input = {
        "zones": [
            {
                "available": True,
                "sensors": {"soil_moisture_pct": 80.0},
                "validity": {"soil_moisture_pct": False},
            }
        ]
    }
    encoded = contract.encode(controller_input)
    moisture_index = contract.feature_names.index("soil_moisture_zone_1_pct")
    default_norm = contract.features[moisture_index].normalize(50.0)
    assert encoded[moisture_index] == default_norm


def test_v2_full_controller_input_record_encodes():
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
    contract = load_contract(V2_CONTRACT_PATH)
    encoded = contract.encode(record)
    assert encoded.shape == (103,)
    assert np.all((0.0 <= encoded) & (encoded <= 1.0))
