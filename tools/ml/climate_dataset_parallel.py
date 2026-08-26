"""Deterministic parallel generation for the climate-v6 dataset.

The reference generator remains untouched.  This companion splits work only at
the episode boundary.  Each episode keeps exactly the same seed derivation,
status RNG, trend history, simulator history and row order as the sequential
implementation.  ``ProcessPoolExecutor.map`` preserves episode ordering when
results are reassembled.
"""

from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass

import numpy as np

from .climate_dataset import (
    ClimateDatasetBundle,
    ClimateDatasetConfig,
    _family_aware_splits,
    _runtime_status,
    generate_climate_dataset,
)
from .climate_input import (
    CLIMATE_V6_CONTRACT_PATH,
    ClimateInputConfig,
    ClimateTrendEstimator,
    encode_climate_input,
)
from .climate_scenarios import ClimateTrainingEpisode, structured_training_episodes
from .climate_simulator import CLIMATE_OUTPUT_NAMES, ClimateSimulator
from .climate_teacher import ClimateRolloutTeacher
from .contract import load_contract
from .dataset import Dataset


@dataclass(frozen=True)
class _EpisodeWork:
    episode_index: int
    episode: ClimateTrainingEpisode
    split: str
    config: ClimateDatasetConfig


@dataclass(frozen=True)
class _EpisodeRows:
    features: np.ndarray
    labels: np.ndarray
    scenario_ids: np.ndarray
    scenario_seeds: np.ndarray
    splits: np.ndarray
    families: np.ndarray
    profiles: np.ndarray
    safe_fallbacks: np.ndarray


def _generate_episode_rows(work: _EpisodeWork) -> _EpisodeRows:
    contract = load_contract(CLIMATE_V6_CONTRACT_PATH)
    if contract.schema_version != 6 or contract.outputs != CLIMATE_OUTPUT_NAMES:
        raise ValueError("parallel climate dataset requires the climate-v6 contract")

    episode = work.episode
    config = work.config
    simulator = ClimateSimulator(episode.scenario)
    teacher = ClimateRolloutTeacher()
    trend_estimator = ClimateTrendEstimator()
    status_rng = np.random.default_rng(episode.scenario.seed ^ 0x6A09E667 ^ work.episode_index)

    feature_rows: list[np.ndarray] = []
    label_rows: list[np.ndarray] = []
    profiles: list[str] = []
    safe_fallbacks: list[bool] = []

    for step_index in range(config.steps_per_scenario):
        profile = episode.profile_for_step(step_index, config.steps_per_scenario)
        simulator.set_light_level(profile.light_level)
        observation = simulator.observe(add_sensor_noise=False)
        status = _runtime_status(
            episode,
            step_index=step_index,
            total_steps=config.steps_per_scenario,
            rng=status_rng,
            config=config,
        )
        monotonic_ms = int(round(simulator.elapsed_s * 1000.0))
        trends = trend_estimator.update(observation, monotonic_ms, status=status)
        input_config = ClimateInputConfig(
            targets=profile.targets,
            humidity_control_mode=profile.humidity_control_mode,
        )
        feature_rows.append(
            encode_climate_input(
                simulator.scenario,
                observation,
                previous=simulator.previous_command,
                trends=trends,
                status=status,
                config=input_config,
                contract=contract,
            )
        )
        teacher_result = teacher.choose(
            simulator,
            profile.targets,
            humidity_control_mode=profile.humidity_control_mode,
            status=status,
            sensor_timeout_ms=input_config.sensor_timeout_ms,
        )
        label_rows.append(contract.output_vector(teacher_result.action.as_dict()))
        profiles.append(profile.name)
        safe_fallbacks.append(teacher_result.safe_fallback)
        simulator.step(
            teacher_result.action,
            add_sensor_noise=False,
            light_level=profile.light_level,
        )

    rows = config.steps_per_scenario
    return _EpisodeRows(
        features=np.asarray(feature_rows, dtype=np.float32),
        labels=np.asarray(label_rows, dtype=np.float32),
        scenario_ids=np.full(rows, episode.scenario.scenario_id),
        scenario_seeds=np.full(rows, episode.scenario.seed, dtype=np.int64),
        splits=np.full(rows, work.split),
        families=np.full(rows, episode.family),
        profiles=np.asarray(profiles),
        safe_fallbacks=np.asarray(safe_fallbacks, dtype=np.bool_),
    )


def _concat(chunks: tuple[_EpisodeRows, ...], attribute: str) -> np.ndarray:
    return np.concatenate([getattr(chunk, attribute) for chunk in chunks], axis=0)


def generate_climate_dataset_parallel(
    config: ClimateDatasetConfig,
    *,
    workers: int = 4,
) -> ClimateDatasetBundle:
    """Generate the exact reference dataset with episodes evaluated in parallel."""
    if workers <= 0:
        raise ValueError("workers must be positive")
    if workers == 1:
        return generate_climate_dataset(config)

    contract = load_contract(CLIMATE_V6_CONTRACT_PATH)
    if contract.schema_version != 6:
        raise ValueError("climate dataset requires schema v6")
    if contract.outputs != CLIMATE_OUTPUT_NAMES:
        raise ValueError("climate simulator outputs do not match v6 contract")

    episodes = structured_training_episodes(
        scenarios_per_family=config.scenarios_per_family,
        seed=config.seed,
    )
    split_by_id = _family_aware_splits(episodes, seed=config.seed + 31)
    work = tuple(
        _EpisodeWork(
            episode_index=index,
            episode=episode,
            split=split_by_id[episode.scenario.scenario_id],
            config=config,
        )
        for index, episode in enumerate(episodes)
    )

    process_count = min(int(workers), len(work))
    with ProcessPoolExecutor(max_workers=process_count) as executor:
        chunks = tuple(executor.map(_generate_episode_rows, work, chunksize=1))

    dataset = Dataset(
        features=_concat(chunks, "features"),
        labels=_concat(chunks, "labels"),
        scenario_ids=_concat(chunks, "scenario_ids"),
        scenario_seeds=_concat(chunks, "scenario_seeds"),
        splits=_concat(chunks, "splits"),
        feature_names=contract.feature_names,
        output_names=contract.outputs,
    )
    return ClimateDatasetBundle(
        dataset=dataset,
        families=_concat(chunks, "families"),
        profiles=_concat(chunks, "profiles"),
        safe_fallbacks=_concat(chunks, "safe_fallbacks"),
    )


__all__ = ["generate_climate_dataset_parallel"]
