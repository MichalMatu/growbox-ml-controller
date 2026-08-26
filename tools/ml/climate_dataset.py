"""Climate-v6 dataset generation and pre-training audit gate.

No model training should consume this dataset until ``audit_climate_dataset``
reports ``ready_for_training=True``. The generator uses structured scenario
families, the exact v6 Python encoder and the climate rollout teacher.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass

import numpy as np

from .climate_input import (
    CLIMATE_V6_CONTRACT_PATH,
    ClimateInputConfig,
    ClimateTrendEstimator,
    MeasurementStatus,
    encode_climate_input,
)
from .climate_scenarios import (
    REQUIRED_SCENARIO_FAMILIES,
    ClimateTrainingEpisode,
    structured_training_episodes,
)
from .climate_simulator import CLIMATE_OUTPUT_NAMES, ClimateSimulator
from .climate_teacher import ClimateRolloutTeacher
from .contract import Contract, load_contract
from .dataset import Dataset, split_scenarios


@dataclass(frozen=True)
class ClimateDatasetConfig:
    scenarios_per_family: int
    steps_per_scenario: int
    seed: int = 1847
    random_invalid_probability: float = 0.01
    random_stale_probability: float = 0.01

    def __post_init__(self) -> None:
        if self.scenarios_per_family <= 0:
            raise ValueError("scenarios_per_family must be positive")
        if self.steps_per_scenario <= 0:
            raise ValueError("steps_per_scenario must be positive")
        if not 0.0 <= self.random_invalid_probability < 1.0:
            raise ValueError("random_invalid_probability must be in [0, 1)")
        if not 0.0 <= self.random_stale_probability < 1.0:
            raise ValueError("random_stale_probability must be in [0, 1)")
        if self.random_invalid_probability + self.random_stale_probability >= 0.5:
            raise ValueError("combined random sensor fault probability is too high")

    @classmethod
    def quick(cls, seed: int = 1847) -> ClimateDatasetConfig:
        return cls(scenarios_per_family=1, steps_per_scenario=4, seed=seed)

    @classmethod
    def full(cls, seed: int = 1847) -> ClimateDatasetConfig:
        return cls(scenarios_per_family=6, steps_per_scenario=80, seed=seed)


@dataclass(frozen=True)
class ClimateDatasetBundle:
    dataset: Dataset
    families: np.ndarray
    profiles: np.ndarray
    humidity_modes: np.ndarray
    safe_fallbacks: np.ndarray

    def __post_init__(self) -> None:
        rows = self.dataset.features.shape[0]
        if any(
            len(values) != rows
            for values in (self.families, self.profiles, self.humidity_modes, self.safe_fallbacks)
        ):
            raise ValueError("climate dataset metadata has inconsistent row counts")


@dataclass(frozen=True)
class ClimateDatasetAudit:
    ready_for_training: bool
    row_count: int
    feature_count: int
    output_count: int
    family_counts: dict[str, int]
    split_counts: dict[str, int]
    humidity_mode_counts: dict[str, int]
    active_fraction: dict[str, float]
    mean_level: dict[str, float]
    safe_fallback_fraction: float
    all_zero_fraction: float
    conflicting_temperature_rows: int
    conflicting_humidity_rows: int
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    def summary_lines(self) -> tuple[str, ...]:
        label_summary = ", ".join(
            f"{name}={self.active_fraction[name]:.3f}" for name in CLIMATE_OUTPUT_NAMES
        )
        lines = [
            f"ready_for_training={self.ready_for_training}",
            f"rows={self.row_count} features={self.feature_count} outputs={self.output_count}",
            "humidity_modes: "
            + ", ".join(
                f"{name}={self.humidity_mode_counts.get(name, 0)}" for name in ("RH", "VPD")
            ),
            f"active_fraction: {label_summary}",
            f"safe_fallback_fraction={self.safe_fallback_fraction:.3f}",
            f"all_zero_fraction={self.all_zero_fraction:.3f}",
        ]
        if self.errors:
            lines.append("errors: " + " | ".join(self.errors))
        if self.warnings:
            lines.append("warnings: " + " | ".join(self.warnings))
        return tuple(lines)


def _family_aware_splits(
    episodes: tuple[ClimateTrainingEpisode, ...], *, seed: int
) -> dict[str, str]:
    grouped: dict[str, list[ClimateTrainingEpisode]] = defaultdict(list)
    for episode in episodes:
        grouped[episode.family].append(episode)

    # Tiny/quick datasets cannot represent every family in all three splits.
    # Fall back to the existing leakage-free global splitter in that case.
    if any(len(items) < 3 for items in grouped.values()):
        return split_scenarios((episode.scenario.scenario_id for episode in episodes), seed=seed)

    mapping: dict[str, str] = {}
    for family_index, family in enumerate(REQUIRED_SCENARIO_FAMILIES):
        items = sorted(grouped[family], key=lambda item: item.scenario.scenario_id)
        order = np.random.default_rng(seed + 7919 * (family_index + 1)).permutation(len(items))
        shuffled = [items[int(index)] for index in order]
        count = len(shuffled)
        validation_count = max(1, int(round(count * 0.15)))
        test_count = max(1, int(round(count * 0.15)))
        if validation_count + test_count >= count:
            validation_count = 1
            test_count = 1
        train_count = count - validation_count - test_count
        for index, episode in enumerate(shuffled):
            if index < train_count:
                split = "train"
            elif index < train_count + validation_count:
                split = "validation"
            else:
                split = "test"
            mapping[episode.scenario.scenario_id] = split
    return mapping


def _runtime_status(
    episode: ClimateTrainingEpisode,
    *,
    step_index: int,
    total_steps: int,
    rng: np.random.Generator,
    config: ClimateDatasetConfig,
) -> dict[str, MeasurementStatus]:
    status = {
        name: MeasurementStatus(valid=True, age_ms=0)
        for name in (
            "air_temperature_c",
            "relative_humidity_pct",
            "co2_ppm",
            "outside_temperature_c",
            "outside_humidity_pct",
        )
    }
    for name in tuple(status):
        draw = float(rng.random())
        if draw < config.random_invalid_probability:
            status[name] = MeasurementStatus(valid=False, age_ms=0)
        elif draw < config.random_invalid_probability + config.random_stale_probability:
            status[name] = MeasurementStatus(valid=True, age_ms=60_000)
    status.update(episode.forced_status_for_step(step_index, total_steps))
    return status


def generate_climate_dataset(
    config: ClimateDatasetConfig,
    *,
    contract: Contract | None = None,
    teacher: ClimateRolloutTeacher | None = None,
) -> ClimateDatasetBundle:
    contract = contract or load_contract(CLIMATE_V6_CONTRACT_PATH)
    if contract.schema_version != 6:
        raise ValueError("climate dataset requires schema v6")
    if contract.feature_names != tuple(
        feature["name"] for feature in contract.document["model"]["features"]
    ):
        raise ValueError("climate feature order is inconsistent")
    if contract.outputs != CLIMATE_OUTPUT_NAMES:
        raise ValueError("climate simulator outputs do not match v6 contract")

    teacher = teacher or ClimateRolloutTeacher()
    episodes = structured_training_episodes(
        scenarios_per_family=config.scenarios_per_family,
        seed=config.seed,
    )
    split_by_id = _family_aware_splits(episodes, seed=config.seed + 31)

    feature_rows: list[np.ndarray] = []
    label_rows: list[np.ndarray] = []
    scenario_ids: list[str] = []
    scenario_seeds: list[int] = []
    splits: list[str] = []
    families: list[str] = []
    profiles: list[str] = []
    humidity_modes: list[str] = []
    safe_fallbacks: list[bool] = []

    for episode_index, episode in enumerate(episodes):
        simulator = ClimateSimulator(episode.scenario)
        trend_estimator = ClimateTrendEstimator()
        status_rng = np.random.default_rng(episode.scenario.seed ^ 0x6A09E667 ^ episode_index)

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
            trends = trend_estimator.update(
                observation,
                monotonic_ms,
                status=status,
            )
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
            scenario_ids.append(simulator.scenario.scenario_id)
            scenario_seeds.append(simulator.scenario.seed)
            splits.append(split_by_id[simulator.scenario.scenario_id])
            families.append(episode.family)
            profiles.append(profile.name)
            humidity_modes.append(profile.humidity_control_mode)
            safe_fallbacks.append(teacher_result.safe_fallback)
            simulator.step(
                teacher_result.action,
                add_sensor_noise=False,
                light_level=profile.light_level,
            )

    dataset = Dataset(
        features=np.asarray(feature_rows, dtype=np.float32),
        labels=np.asarray(label_rows, dtype=np.float32),
        scenario_ids=np.asarray(scenario_ids),
        scenario_seeds=np.asarray(scenario_seeds, dtype=np.int64),
        splits=np.asarray(splits),
        feature_names=contract.feature_names,
        output_names=contract.outputs,
    )
    return ClimateDatasetBundle(
        dataset=dataset,
        families=np.asarray(families),
        profiles=np.asarray(profiles),
        humidity_modes=np.asarray(humidity_modes),
        safe_fallbacks=np.asarray(safe_fallbacks, dtype=np.bool_),
    )


def audit_climate_dataset(
    bundle: ClimateDatasetBundle,
    *,
    minimum_active_fraction: float = 0.02,
    maximum_active_fraction: float = 0.98,
    activity_threshold: float = 0.05,
) -> ClimateDatasetAudit:
    dataset = bundle.dataset
    features = dataset.features
    labels = dataset.labels
    errors: list[str] = []
    warnings: list[str] = []

    rows = int(features.shape[0]) if features.ndim == 2 else 0
    feature_count = int(features.shape[1]) if features.ndim == 2 else 0
    output_count = int(labels.shape[1]) if labels.ndim == 2 else 0
    if feature_count != 38:
        errors.append(f"expected 38 features, got {feature_count}")
    if output_count != 6:
        errors.append(f"expected 6 outputs, got {output_count}")
    if dataset.output_names != CLIMATE_OUTPUT_NAMES:
        errors.append("dataset output order does not match climate v6")
    if not np.isfinite(features).all():
        errors.append("features contain NaN/Inf")
    if not np.isfinite(labels).all():
        errors.append("labels contain NaN/Inf")
    if labels.size and (float(np.min(labels)) < 0.0 or float(np.max(labels)) > 1.0):
        errors.append("labels are outside [0, 1]")

    family_counts = dict(Counter(str(value) for value in bundle.families))
    missing_families = [
        family for family in REQUIRED_SCENARIO_FAMILIES if family not in family_counts
    ]
    if missing_families:
        errors.append("missing scenario families: " + ", ".join(missing_families))

    split_counts = dict(Counter(str(value) for value in dataset.splits))
    for split in ("train", "validation", "test"):
        if split_counts.get(split, 0) == 0:
            errors.append(f"split {split!r} has no rows")

    humidity_mode_counts = dict(Counter(str(value) for value in bundle.humidity_modes))
    for mode in ("RH", "VPD"):
        if humidity_mode_counts.get(mode, 0) == 0:
            errors.append(f"humidity mode {mode!r} has no rows")

    active_fraction: dict[str, float] = {}
    mean_level: dict[str, float] = {}
    if rows > 0 and output_count == 6:
        active = labels > float(activity_threshold)
        for output_index, name in enumerate(CLIMATE_OUTPUT_NAMES):
            fraction = float(np.mean(active[:, output_index]))
            active_fraction[name] = fraction
            mean_level[name] = float(np.mean(labels[:, output_index]))
            if fraction < minimum_active_fraction:
                errors.append(
                    f"{name} active fraction {fraction:.3f} < {minimum_active_fraction:.3f}"
                )
            if fraction > maximum_active_fraction:
                errors.append(
                    f"{name} active fraction {fraction:.3f} > {maximum_active_fraction:.3f}"
                )
    else:
        active = np.zeros((rows, max(6, output_count)), dtype=bool)
        active_fraction = {name: 0.0 for name in CLIMATE_OUTPUT_NAMES}
        mean_level = {name: 0.0 for name in CLIMATE_OUTPUT_NAMES}

    conflicting_temperature_rows = 0
    conflicting_humidity_rows = 0
    all_zero_fraction = 0.0
    if rows > 0 and output_count == 6:
        heater = CLIMATE_OUTPUT_NAMES.index("heater")
        cooler = CLIMATE_OUTPUT_NAMES.index("cooler")
        humidifier = CLIMATE_OUTPUT_NAMES.index("humidifier")
        dehumidifier = CLIMATE_OUTPUT_NAMES.index("dehumidifier")
        conflicting_temperature_rows = int(np.sum(active[:, heater] & active[:, cooler]))
        conflicting_humidity_rows = int(np.sum(active[:, humidifier] & active[:, dehumidifier]))
        all_zero_fraction = float(np.mean(np.all(labels <= activity_threshold, axis=1)))
        if conflicting_temperature_rows:
            errors.append(f"{conflicting_temperature_rows} rows command heater and cooler together")
        if conflicting_humidity_rows:
            errors.append(
                f"{conflicting_humidity_rows} rows command humidifier and dehumidifier together"
            )
        if all_zero_fraction > 0.85:
            warnings.append(f"all-zero label fraction is high: {all_zero_fraction:.3f}")

    safe_fallback_fraction = (
        float(np.mean(bundle.safe_fallbacks)) if len(bundle.safe_fallbacks) else 0.0
    )
    if safe_fallback_fraction > 0.25:
        warnings.append(f"safe fallback fraction is high: {safe_fallback_fraction:.3f}")

    return ClimateDatasetAudit(
        ready_for_training=not errors,
        row_count=rows,
        feature_count=feature_count,
        output_count=output_count,
        family_counts=family_counts,
        split_counts=split_counts,
        humidity_mode_counts=humidity_mode_counts,
        active_fraction=active_fraction,
        mean_level=mean_level,
        safe_fallback_fraction=safe_fallback_fraction,
        all_zero_fraction=all_zero_fraction,
        conflicting_temperature_rows=conflicting_temperature_rows,
        conflicting_humidity_rows=conflicting_humidity_rows,
        errors=tuple(errors),
        warnings=tuple(warnings),
    )


def assert_climate_dataset_ready(
    report: ClimateDatasetAudit,
    *,
    require_family_coverage_in_each_split: bool = False,
    require_humidity_mode_coverage_in_each_split: bool = False,
    bundle: ClimateDatasetBundle | None = None,
) -> None:
    errors = list(report.errors)
    if require_family_coverage_in_each_split:
        if bundle is None:
            raise ValueError("bundle is required for split/family coverage check")
        pairs = {
            (str(family), str(split))
            for family, split in zip(bundle.families, bundle.dataset.splits, strict=True)
        }
        for family in REQUIRED_SCENARIO_FAMILIES:
            for split in ("train", "validation", "test"):
                if (family, split) not in pairs:
                    errors.append(f"family {family!r} is absent from {split!r} split")
    if require_humidity_mode_coverage_in_each_split:
        if bundle is None:
            raise ValueError("bundle is required for split/humidity-mode coverage check")
        mode_pairs = {
            (str(mode), str(split))
            for mode, split in zip(bundle.humidity_modes, bundle.dataset.splits, strict=True)
        }
        for mode in ("RH", "VPD"):
            for split in ("train", "validation", "test"):
                if (mode, split) not in mode_pairs:
                    errors.append(f"humidity mode {mode!r} is absent from {split!r} split")
    if errors:
        raise ValueError("climate dataset is not ready for training: " + " | ".join(errors))


__all__ = [
    "ClimateDatasetAudit",
    "ClimateDatasetBundle",
    "ClimateDatasetConfig",
    "assert_climate_dataset_ready",
    "audit_climate_dataset",
    "generate_climate_dataset",
]
