"""On-policy DAgger data collection for climate-v6.

DAgger rows are collected from states visited by the current ML policy after
request dead-zone, arbitration and SafetySupervisor. The rollout teacher labels
those same states. New rows are train-only; the frozen Stage 9B validation/test
rows are never replaced or re-split.
"""

from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass

import numpy as np

from .climate_input import (
    ClimateInputConfig,
    ClimateTrendEstimator,
    MeasurementStatus,
    encode_climate_input,
)
from .climate_model_artifact import ClimatePortableModel
from .climate_policy import apply_climate_safety, apply_ml_request_deadzone, arbitrate_climate_action
from .climate_scenarios import ClimateTrainingEpisode, structured_training_episodes
from .climate_simulator import CLIMATE_OUTPUT_NAMES, ClimateAction, ClimateSimulator
from .climate_teacher import ClimateRolloutTeacher
from .contract import Contract
from .dataset import Dataset


@dataclass(frozen=True)
class DaggerCollectionConfig:
    seed: int
    scenarios_per_family: int = 12
    steps_per_scenario: int = 100
    workers: int = 6
    random_invalid_probability: float = 0.01
    random_stale_probability: float = 0.01

    def __post_init__(self) -> None:
        if self.scenarios_per_family <= 0 or self.steps_per_scenario <= 0 or self.workers <= 0:
            raise ValueError("DAgger scenarios, steps and workers must be positive")
        if not 0.0 <= self.random_invalid_probability < 1.0:
            raise ValueError("random_invalid_probability must be in [0, 1)")
        if not 0.0 <= self.random_stale_probability < 1.0:
            raise ValueError("random_stale_probability must be in [0, 1)")
        if self.random_invalid_probability + self.random_stale_probability >= 0.5:
            raise ValueError("combined DAgger random sensor fault probability is too high")


@dataclass(frozen=True)
class DaggerRows:
    dataset: Dataset
    families: np.ndarray
    humidity_modes: np.ndarray
    safe_fallbacks: np.ndarray

    def __post_init__(self) -> None:
        rows = len(self.dataset.features)
        if any(len(values) != rows for values in (self.families, self.humidity_modes, self.safe_fallbacks)):
            raise ValueError("DAgger metadata has inconsistent row counts")
        if rows and not np.all(self.dataset.splits == "train"):
            raise ValueError("DAgger rows must be train-only")


@dataclass(frozen=True)
class _EpisodeWork:
    episode: ClimateTrainingEpisode
    episode_index: int
    config: DaggerCollectionConfig
    model: ClimatePortableModel
    contract: Contract


def _status_for_step(
    episode: ClimateTrainingEpisode,
    *,
    episode_index: int,
    step_index: int,
    total_steps: int,
    seed: int,
    invalid_probability: float,
    stale_probability: float,
) -> dict[str, MeasurementStatus]:
    rng = np.random.default_rng(
        int(episode.scenario.seed) ^ int(seed) ^ 0x9E3779B9 ^ (episode_index * 65537) ^ step_index
    )
    statuses = {
        name: MeasurementStatus(valid=True, age_ms=0)
        for name in (
            "air_temperature_c",
            "relative_humidity_pct",
            "co2_ppm",
            "outside_temperature_c",
            "outside_humidity_pct",
        )
    }
    for name in tuple(statuses):
        draw = float(rng.random())
        if draw < invalid_probability:
            statuses[name] = MeasurementStatus(valid=False, age_ms=0)
        elif draw < invalid_probability + stale_probability:
            statuses[name] = MeasurementStatus(valid=True, age_ms=60_000)
    statuses.update(episode.forced_status_for_step(step_index, total_steps))
    return statuses


def _collect_episode(work: _EpisodeWork) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    episode = work.episode
    config = work.config
    simulator = ClimateSimulator(episode.scenario)
    trend_estimator = ClimateTrendEstimator()
    teacher = ClimateRolloutTeacher()

    features: list[np.ndarray] = []
    labels: list[np.ndarray] = []
    scenario_ids: list[str] = []
    scenario_seeds: list[int] = []
    families: list[str] = []
    humidity_modes: list[str] = []
    safe_fallbacks: list[bool] = []

    for step_index in range(config.steps_per_scenario):
        profile = episode.profile_for_step(step_index, config.steps_per_scenario)
        simulator.set_light_level(profile.light_level)
        observation = simulator.observe(add_sensor_noise=False)
        status = _status_for_step(
            episode,
            episode_index=work.episode_index,
            step_index=step_index,
            total_steps=config.steps_per_scenario,
            seed=config.seed,
            invalid_probability=config.random_invalid_probability,
            stale_probability=config.random_stale_probability,
        )
        monotonic_ms = int(round(simulator.elapsed_s * 1000.0))
        trends = trend_estimator.update(observation, monotonic_ms, status=status)
        input_config = ClimateInputConfig(
            targets=profile.targets,
            humidity_control_mode=profile.humidity_control_mode,
        )
        row = encode_climate_input(
            simulator.scenario,
            observation,
            previous=simulator.previous_command,
            trends=trends,
            status=status,
            config=input_config,
            contract=work.contract,
        )
        teacher_result = teacher.choose(
            simulator,
            profile.targets,
            humidity_control_mode=profile.humidity_control_mode,
            status=status,
            sensor_timeout_ms=input_config.sensor_timeout_ms,
        )

        prediction = work.model.predict(row)
        raw_action = ClimateAction.from_mapping(
            dict(zip(CLIMATE_OUTPUT_NAMES, (float(value) for value in prediction), strict=True))
        )
        requested = apply_ml_request_deadzone(raw_action)
        arbitration = arbitrate_climate_action(requested, simulator.scenario)
        safety = apply_climate_safety(
            arbitration.action,
            simulator.scenario,
            observation,
            profile,
            status=status,
            sensor_timeout_ms=input_config.sensor_timeout_ms,
        )

        features.append(row)
        labels.append(work.contract.output_vector(teacher_result.action.as_dict()))
        scenario_ids.append(simulator.scenario.scenario_id)
        scenario_seeds.append(simulator.scenario.seed)
        families.append(episode.family)
        humidity_modes.append(profile.humidity_control_mode)
        safe_fallbacks.append(teacher_result.safe_fallback)

        simulator.step(safety.action, add_sensor_noise=False, light_level=profile.light_level)

    rows = len(features)
    return (
        np.asarray(features, dtype=np.float32),
        np.asarray(labels, dtype=np.float32),
        np.asarray(scenario_ids),
        np.asarray(scenario_seeds, dtype=np.int64),
        np.full(rows, "train"),
        np.asarray(families),
        np.asarray(humidity_modes),
        np.asarray(safe_fallbacks, dtype=np.bool_),
    )


def collect_dagger_rows(
    model: ClimatePortableModel,
    *,
    config: DaggerCollectionConfig,
    contract: Contract,
) -> DaggerRows:
    if model.metadata.schema_version != 6:
        raise ValueError("DAgger requires a climate-v6 model")
    if model.metadata.feature_names != contract.feature_names:
        raise ValueError("DAgger model feature order does not match contract")
    if model.metadata.output_names != contract.outputs or contract.outputs != CLIMATE_OUTPUT_NAMES:
        raise ValueError("DAgger model output order does not match contract")

    episodes = structured_training_episodes(
        scenarios_per_family=config.scenarios_per_family,
        seed=config.seed,
    )
    work = tuple(
        _EpisodeWork(
            episode=episode,
            episode_index=index,
            config=config,
            model=model,
            contract=contract,
        )
        for index, episode in enumerate(episodes)
    )
    if config.workers <= 1:
        parts = tuple(_collect_episode(item) for item in work)
    else:
        with ProcessPoolExecutor(max_workers=min(config.workers, len(work))) as executor:
            parts = tuple(executor.map(_collect_episode, work, chunksize=1))

    features = np.concatenate([item[0] for item in parts], axis=0)
    labels = np.concatenate([item[1] for item in parts], axis=0)
    scenario_ids = np.concatenate([item[2] for item in parts], axis=0)
    scenario_seeds = np.concatenate([item[3] for item in parts], axis=0)
    splits = np.concatenate([item[4] for item in parts], axis=0)
    families = np.concatenate([item[5] for item in parts], axis=0)
    modes = np.concatenate([item[6] for item in parts], axis=0)
    fallbacks = np.concatenate([item[7] for item in parts], axis=0)
    expected_rows = len(episodes) * config.steps_per_scenario
    if features.shape != (expected_rows, 38) or labels.shape != (expected_rows, 6):
        raise AssertionError("DAgger collection produced unexpected tensor shapes")
    if not np.isfinite(features).all() or not np.isfinite(labels).all():
        raise ValueError("DAgger collection produced NaN/Inf")

    dataset = Dataset(
        features=features,
        labels=labels,
        scenario_ids=scenario_ids,
        scenario_seeds=scenario_seeds,
        splits=splits,
        feature_names=contract.feature_names,
        output_names=contract.outputs,
    )
    return DaggerRows(dataset=dataset, families=families, humidity_modes=modes, safe_fallbacks=fallbacks)


def append_train_only(base: Dataset, dagger: Dataset) -> Dataset:
    if base.feature_names != dagger.feature_names or base.output_names != dagger.output_names:
        raise ValueError("cannot append DAgger rows with different contract ordering")
    if len(dagger.features) and not np.all(dagger.splits == "train"):
        raise ValueError("only train-only DAgger rows may be appended")
    overlap = set(str(value) for value in np.unique(base.scenario_ids)) & set(
        str(value) for value in np.unique(dagger.scenario_ids)
    )
    if overlap:
        raise ValueError("DAgger scenarios overlap existing dataset: " + ", ".join(sorted(overlap)[:5]))
    return Dataset(
        features=np.concatenate((base.features, dagger.features), axis=0),
        labels=np.concatenate((base.labels, dagger.labels), axis=0),
        scenario_ids=np.concatenate((base.scenario_ids, dagger.scenario_ids), axis=0),
        scenario_seeds=np.concatenate((base.scenario_seeds, dagger.scenario_seeds), axis=0),
        splits=np.concatenate((base.splits, dagger.splits), axis=0),
        feature_names=base.feature_names,
        output_names=base.output_names,
    )


def frozen_split_fingerprint(dataset: Dataset, split: str) -> str:
    import hashlib

    mask = dataset.splits == split
    digest = hashlib.sha256()
    for array in (dataset.features[mask], dataset.labels[mask], dataset.scenario_seeds[mask]):
        values = np.ascontiguousarray(array)
        digest.update(str(values.shape).encode("utf-8"))
        digest.update(str(values.dtype).encode("utf-8"))
        digest.update(values.tobytes())
    for scenario_id in dataset.scenario_ids[mask]:
        encoded = str(scenario_id).encode("utf-8")
        digest.update(len(encoded).to_bytes(4, "little"))
        digest.update(encoded)
    return digest.hexdigest()


__all__ = [
    "DaggerCollectionConfig",
    "DaggerRows",
    "append_train_only",
    "collect_dagger_rows",
    "frozen_split_fingerprint",
]
