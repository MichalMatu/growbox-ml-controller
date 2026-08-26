from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from tools.ml.climate_dataset import (
    ClimateDatasetBundle,
    ClimateDatasetConfig,
    assert_climate_dataset_ready,
    audit_climate_dataset,
    generate_climate_dataset,
)
from tools.ml.climate_scenarios import (
    REQUIRED_SCENARIO_FAMILIES,
    build_training_episode,
    structured_training_episodes,
)
from tools.ml.climate_simulator import CLIMATE_OUTPUT_NAMES
from tools.ml.climate_teacher import ClimateRolloutTeacher, ClimateTeacherConfig
from tools.ml.dataset import Dataset


def fast_teacher() -> ClimateRolloutTeacher:
    return ClimateRolloutTeacher(
        config=ClimateTeacherConfig(
            horizon_s=240.0,
            rollout_dt_s=20.0,
            coordinate_passes=1,
        )
    )


def test_structured_generator_covers_every_required_family() -> None:
    episodes = structured_training_episodes(scenarios_per_family=1, seed=123)
    assert tuple(episode.family for episode in episodes) == REQUIRED_SCENARIO_FAMILIES
    assert len({episode.scenario.scenario_id for episode in episodes}) == len(episodes)


def test_physical_randomization_is_correlated_with_volume() -> None:
    episodes = structured_training_episodes(scenarios_per_family=3, seed=777)
    for episode in episodes:
        scenario = episode.scenario
        volume = scenario.environment.growbox_volume_m3
        assert 28_000.0 <= scenario.environment.thermal_mass_j_per_k / volume <= 75_000.0
        if scenario.actuators.heater.available:
            assert 160.0 <= scenario.actuators.heater.max_power_w / volume <= 340.0
        if scenario.actuators.exhaust_fan.available:
            assert 75.0 <= scenario.actuators.exhaust_fan.max_airflow_m3_h / volume <= 155.0
        assert (
            max(
                scenario.response_lag.heater_s,
                scenario.response_lag.cooler_s,
                scenario.response_lag.exhaust_fan_s,
                scenario.response_lag.humidifier_s,
                scenario.response_lag.dehumidifier_s,
                scenario.response_lag.co2_doser_s,
            )
            <= 75.0
        )


def test_transition_families_switch_profile_at_midpoint() -> None:
    day_to_night = build_training_episode("day_to_night", 0, 1001)
    night_to_day = build_training_episode("night_to_day", 0, 1002)
    assert day_to_night.profile_for_step(0, 4).name == "day"
    assert day_to_night.profile_for_step(2, 4).name == "night"
    assert night_to_day.profile_for_step(0, 4).name == "night"
    assert night_to_day.profile_for_step(2, 4).name == "day"


def test_sensor_fault_family_faults_only_second_half() -> None:
    episode = build_training_episode("sensor_fault", 0, 1003)
    assert episode.fault_sensor == "air_temperature_c"
    assert episode.forced_status_for_step(0, 4) == {}
    fault = episode.forced_status_for_step(2, 4)["air_temperature_c"]
    assert fault.valid is False


def test_actuator_missing_family_rotates_all_six_outputs() -> None:
    missing: list[str] = []
    for index, expected in enumerate(CLIMATE_OUTPUT_NAMES):
        episode = build_training_episode("actuator_missing", index, 2000 + index)
        caps = episode.scenario.actuators
        availability = {
            "heater": caps.heater.available,
            "cooler": caps.cooler.available,
            "exhaust_fan": caps.exhaust_fan.available,
            "humidifier": caps.humidifier.available,
            "dehumidifier": caps.dehumidifier.available,
            "co2_doser": caps.co2_doser.available,
        }
        absent = [name for name, available in availability.items() if not available]
        assert absent == [expected]
        missing.extend(absent)
    assert tuple(missing) == CLIMATE_OUTPUT_NAMES


def test_small_dataset_has_v6_shapes_metadata_and_no_conflicting_labels() -> None:
    bundle = generate_climate_dataset(
        ClimateDatasetConfig(
            scenarios_per_family=1,
            steps_per_scenario=2,
            seed=321,
            random_invalid_probability=0.0,
            random_stale_probability=0.0,
        ),
        teacher=fast_teacher(),
    )
    dataset = bundle.dataset
    expected_rows = len(REQUIRED_SCENARIO_FAMILIES) * 2
    assert dataset.features.shape == (expected_rows, 38)
    assert dataset.labels.shape == (expected_rows, 6)
    assert dataset.output_names == CLIMATE_OUTPUT_NAMES
    assert set(bundle.families) == set(REQUIRED_SCENARIO_FAMILIES)
    assert set(dataset.splits) == {"train", "validation", "test"}
    assert np.isfinite(dataset.features).all()
    assert np.isfinite(dataset.labels).all()
    heater = CLIMATE_OUTPUT_NAMES.index("heater")
    cooler = CLIMATE_OUTPUT_NAMES.index("cooler")
    humidifier = CLIMATE_OUTPUT_NAMES.index("humidifier")
    dehumidifier = CLIMATE_OUTPUT_NAMES.index("dehumidifier")
    active = dataset.labels > 0.05
    assert not np.any(active[:, heater] & active[:, cooler])
    assert not np.any(active[:, humidifier] & active[:, dehumidifier])


def test_dataset_generation_is_deterministic_for_same_seed() -> None:
    config = ClimateDatasetConfig(
        scenarios_per_family=1,
        steps_per_scenario=1,
        seed=654,
        random_invalid_probability=0.0,
        random_stale_probability=0.0,
    )
    left = generate_climate_dataset(config, teacher=fast_teacher())
    right = generate_climate_dataset(config, teacher=fast_teacher())
    assert np.array_equal(left.dataset.features, right.dataset.features)
    assert np.array_equal(left.dataset.labels, right.dataset.labels)
    assert np.array_equal(left.dataset.splits, right.dataset.splits)
    assert np.array_equal(left.families, right.families)


def test_family_aware_split_covers_each_family_when_three_samples_exist() -> None:
    bundle = generate_climate_dataset(
        ClimateDatasetConfig(
            scenarios_per_family=3,
            steps_per_scenario=1,
            seed=987,
            random_invalid_probability=0.0,
            random_stale_probability=0.0,
        ),
        teacher=fast_teacher(),
    )
    pairs = set(zip(bundle.families, bundle.dataset.splits, strict=True))
    for family in REQUIRED_SCENARIO_FAMILIES:
        assert (family, "train") in pairs
        assert (family, "validation") in pairs
        assert (family, "test") in pairs


def test_audit_reports_structure_and_never_hides_conflicts() -> None:
    bundle = generate_climate_dataset(
        ClimateDatasetConfig(
            scenarios_per_family=1,
            steps_per_scenario=2,
            seed=4321,
            random_invalid_probability=0.0,
            random_stale_probability=0.0,
        ),
        teacher=fast_teacher(),
    )
    report = audit_climate_dataset(bundle, minimum_active_fraction=0.0)
    assert report.row_count == len(REQUIRED_SCENARIO_FAMILIES) * 2
    assert report.feature_count == 38
    assert report.output_count == 6
    assert report.conflicting_temperature_rows == 0
    assert report.conflicting_humidity_rows == 0
    assert set(report.family_counts) == set(REQUIRED_SCENARIO_FAMILIES)


def test_audit_rejects_all_zero_labels_before_training() -> None:
    source = generate_climate_dataset(
        ClimateDatasetConfig(
            scenarios_per_family=1,
            steps_per_scenario=1,
            seed=2468,
            random_invalid_probability=0.0,
            random_stale_probability=0.0,
        ),
        teacher=fast_teacher(),
    )
    dataset = source.dataset
    zero_dataset = Dataset(
        features=dataset.features,
        labels=np.zeros_like(dataset.labels),
        scenario_ids=dataset.scenario_ids,
        scenario_seeds=dataset.scenario_seeds,
        splits=dataset.splits,
        feature_names=dataset.feature_names,
        output_names=dataset.output_names,
    )
    bundle = ClimateDatasetBundle(
        dataset=zero_dataset,
        families=source.families,
        profiles=source.profiles,
        safe_fallbacks=source.safe_fallbacks,
    )
    report = audit_climate_dataset(bundle)
    assert not report.ready_for_training
    assert any("active fraction" in error for error in report.errors)
    with pytest.raises(ValueError, match="not ready for training"):
        assert_climate_dataset_ready(report)


def test_full_style_family_coverage_gate_requires_bundle() -> None:
    source = generate_climate_dataset(
        ClimateDatasetConfig(
            scenarios_per_family=1,
            steps_per_scenario=1,
            seed=1357,
            random_invalid_probability=0.0,
            random_stale_probability=0.0,
        ),
        teacher=fast_teacher(),
    )
    report = audit_climate_dataset(source, minimum_active_fraction=0.0)
    with pytest.raises(ValueError, match="bundle is required"):
        assert_climate_dataset_ready(
            replace(report, errors=()),
            require_family_coverage_in_each_split=True,
        )
