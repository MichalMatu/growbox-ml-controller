from __future__ import annotations

import numpy as np

from tools.ml.generate_dataset import (
    DatasetConfig,
    generate_dataset,
    random_scenario,
    split_scenarios,
)
from tools.ml.teacher import RolloutTeacher


def test_scenario_split_has_no_sequence_leakage():
    identifiers = [f"scenario-{index}" for index in range(20)]
    mapping = split_scenarios(identifiers, seed=55)
    split_sets = {
        split: {name for name, assigned in mapping.items() if assigned == split}
        for split in ("train", "validation", "test")
    }
    assert all(split_sets.values())
    assert split_sets["train"].isdisjoint(split_sets["validation"])
    assert split_sets["train"].isdisjoint(split_sets["test"])
    assert split_sets["validation"].isdisjoint(split_sets["test"])
    assert mapping == split_scenarios(identifiers, seed=55)


def test_generated_rows_keep_each_scenario_in_one_split():
    dataset = generate_dataset(
        DatasetConfig(scenario_count=6, steps_per_scenario=4, seed=91),
        teacher=RolloutTeacher(horizon_steps=1),
    )
    assert dataset.features.shape == (24, 43)
    assert dataset.labels.shape == (24, 4)
    assert np.all((0.0 <= dataset.features) & (dataset.features <= 1.0))
    assert np.all((0.0 <= dataset.labels) & (dataset.labels <= 1.0))
    for scenario_id in set(dataset.scenario_ids):
        rows = dataset.scenario_ids == scenario_id
        assert len(set(dataset.splits[rows].tolist())) == 1
        assert len(set(dataset.scenario_seeds[rows].tolist())) == 1


def test_absent_devices_have_zero_capacity():
    no_heater = random_scenario(1, 100)
    no_fan = random_scenario(2, 101)
    no_humidifier = random_scenario(3, 102)
    no_pump = random_scenario(4, 103)
    assert not no_heater.actuators.heater.available
    assert no_heater.actuators.heater.max_power_w == 0.0
    assert not no_fan.actuators.fan.available
    assert no_fan.actuators.fan.max_airflow_m3_h == 0.0
    assert not no_humidifier.actuators.humidifier.available
    assert no_humidifier.actuators.humidifier.max_output_g_h == 0.0
    assert not no_pump.actuators.irrigation_pump.available
    assert no_pump.actuators.irrigation_pump.flow_ml_s == 0.0
    assert no_pump.actuators.irrigation_pump.maximum_pulse_s == 0.0
