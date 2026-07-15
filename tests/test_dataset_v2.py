from __future__ import annotations

import numpy as np

from tools.ml.contract import V2_CONTRACT_PATH, load_contract
from tools.ml.generate_dataset import DatasetConfig, split_scenarios
from tools.ml.generate_dataset_v2 import (
    controller_input_record_v2,
    generate_dataset_v2,
    random_scenario_v2,
)
from tools.ml.simulator_v2 import SequentialEnvironmentSimulatorV2
from tools.ml.teacher_v2 import RolloutTeacherV2


def test_v2_controller_input_record_matches_contract_paths():
    scenario = random_scenario_v2(0, 4242)
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
    )
    contract = load_contract(V2_CONTRACT_PATH)
    encoded = contract.encode(record)
    assert encoded.shape == (len(contract.features),)
    assert np.all((0.0 <= encoded) & (encoded <= 1.0))


def test_generated_v2_rows_keep_each_scenario_in_one_split():
    contract = load_contract(V2_CONTRACT_PATH)
    dataset = generate_dataset_v2(
        DatasetConfig(scenario_count=6, steps_per_scenario=3, seed=91),
        teacher=RolloutTeacherV2(horizon_steps=1),
    )
    assert dataset.features.shape == (18, len(contract.features))
    assert dataset.labels.shape == (18, len(contract.outputs))
    assert np.all((0.0 <= dataset.features) & (dataset.features <= 1.0))
    assert np.all((0.0 <= dataset.labels) & (dataset.labels <= 1.0))
    for scenario_id in set(dataset.scenario_ids):
        rows = dataset.scenario_ids == scenario_id
        assert len(set(dataset.splits[rows].tolist())) == 1
        assert len(set(dataset.scenario_seeds[rows].tolist())) == 1


def test_v2_split_has_no_sequence_leakage():
    identifiers = [f"v2-scenario-{index}" for index in range(20)]
    mapping = split_scenarios(identifiers, seed=55)
    split_sets = {
        split: {name for name, assigned in mapping.items() if assigned == split}
        for split in ("train", "validation", "test")
    }
    assert all(split_sets.values())
    assert split_sets["train"].isdisjoint(split_sets["validation"])
    assert split_sets["train"].isdisjoint(split_sets["test"])
    assert split_sets["validation"].isdisjoint(split_sets["test"])
