#!/usr/bin/env python3
"""Stage 14C fresh-seed closed-loop development benchmark for bounded residual control."""

from __future__ import annotations

import json
import math
import time
from dataclasses import asdict, dataclass

import numpy as np

from tools.ml.climate_benchmark import _status_for_step, _tracking_terms
from tools.ml.climate_dataset import ClimateDatasetConfig, _family_aware_splits, _runtime_status
from tools.ml.climate_input import (
    ClimateEffectiveActionEstimator,
    ClimateInputConfig,
    ClimateTrendEstimator,
    encode_climate_input,
)
from tools.ml.climate_policy import (
    ClimateRulePolicy,
    apply_climate_safety,
    arbitrate_climate_action,
    hard_limit_violations,
)
from tools.ml.climate_scenarios import REQUIRED_SCENARIO_FAMILIES, structured_training_episodes
from tools.ml.climate_sequence_teacher import ClimateSequenceRolloutTeacher
from tools.ml.climate_simulator import CLIMATE_OUTPUT_NAMES, ClimateAction, ClimateSimulator
from tools.ml.climate_training import configure_tensorflow_determinism

TRAIN_SEED = 141421
BENCHMARK_SEED = 223607
TRAIN_SCENARIOS_PER_FAMILY = 4
TRAIN_STEPS_PER_SCENARIO = 3
BENCHMARK_SCENARIOS_PER_FAMILY = 1
BENCHMARK_STEPS_PER_SCENARIO = 12
EPOCHS = 32
BATCH_SIZE = 32
BOUND = 1.0
SENSOR_TIMEOUT_MS = 30_000
POLICIES = ("rule", "sequence", "residual")


@dataclass(frozen=True)
class Metrics:
    steps: int
    tracking_cost: float
    switching_per_step: float
    actuator_effort_per_step: float
    safety_intervention_fraction: float
    arbitration_intervention_fraction: float
    hard_limit_violation_fraction: float


def _build_residual_model(seed: int):
    tf = configure_tensorflow_determinism(seed)
    keras = tf.keras
    model = keras.Sequential(
        [
            keras.layers.Input(shape=(44,), name="climate_v6_features"),
            keras.layers.Dense(
                32,
                activation="relu",
                kernel_initializer=keras.initializers.GlorotUniform(seed=seed + 1),
                bias_initializer="zeros",
                name="hidden_1",
            ),
            keras.layers.Dense(
                32,
                activation="relu",
                kernel_initializer=keras.initializers.GlorotUniform(seed=seed + 2),
                bias_initializer="zeros",
                name="hidden_2",
            ),
            keras.layers.Dense(
                6,
                activation="tanh",
                kernel_initializer="zeros",
                bias_initializer="zeros",
                name="bounded_residual",
            ),
        ],
        name="stage14c_bounded_residual",
    )
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=0.001),
        loss=tf.keras.losses.Huber(delta=0.15),
    )
    return model


def _fit(model, x: np.ndarray, y: np.ndarray, seed: int) -> None:
    rng = np.random.default_rng(seed)
    batch = min(BATCH_SIZE, len(x))
    for _ in range(EPOCHS):
        order = rng.permutation(len(x))
        for start in range(0, len(order), batch):
            idx = order[start : start + batch]
            model.train_on_batch(x[idx], y[idx])


def _train_residual_model():
    config = ClimateDatasetConfig(
        scenarios_per_family=TRAIN_SCENARIOS_PER_FAMILY,
        steps_per_scenario=TRAIN_STEPS_PER_SCENARIO,
        seed=TRAIN_SEED,
        random_invalid_probability=0.01,
        random_stale_probability=0.01,
    )
    episodes = structured_training_episodes(
        scenarios_per_family=TRAIN_SCENARIOS_PER_FAMILY,
        seed=TRAIN_SEED,
    )
    split_by_id = _family_aware_splits(episodes, seed=TRAIN_SEED + 31)
    teacher = ClimateSequenceRolloutTeacher()
    rule_policy = ClimateRulePolicy()
    features: list[np.ndarray] = []
    residuals: list[np.ndarray] = []
    evaluations: list[int] = []
    family_counts = {family: 0 for family in REQUIRED_SCENARIO_FAMILIES}

    for episode_index, episode in enumerate(episodes):
        if split_by_id[episode.scenario.scenario_id] != "train":
            continue
        simulator = ClimateSimulator(episode.scenario)
        trends = ClimateTrendEstimator()
        effective = ClimateEffectiveActionEstimator()
        status_rng = np.random.default_rng(episode.scenario.seed ^ 0x6A09E667 ^ episode_index)
        for step_index in range(TRAIN_STEPS_PER_SCENARIO):
            profile = episode.profile_for_step(step_index, TRAIN_STEPS_PER_SCENARIO)
            simulator.set_light_level(profile.light_level)
            observation = simulator.observe(add_sensor_noise=False)
            status = _runtime_status(
                episode,
                step_index=step_index,
                total_steps=TRAIN_STEPS_PER_SCENARIO,
                rng=status_rng,
                config=config,
            )
            trend_values = trends.update(
                observation,
                int(round(simulator.elapsed_s * 1000.0)),
                status=status,
            )
            input_config = ClimateInputConfig(
                targets=profile.targets,
                humidity_control_mode=profile.humidity_control_mode,
                sensor_timeout_ms=SENSOR_TIMEOUT_MS,
            )
            row = encode_climate_input(
                simulator.scenario,
                observation,
                previous=simulator.previous_command,
                estimated_effective=effective.state,
                trends=trend_values,
                status=status,
                config=input_config,
            )
            if row.shape != (44,) or not np.isfinite(row).all():
                raise AssertionError("Stage 14C requires finite 44-feature training rows")
            rule = rule_policy.choose(
                simulator.scenario,
                observation,
                profile,
                status=status,
                sensor_timeout_ms=SENSOR_TIMEOUT_MS,
            )
            oracle = teacher.choose(
                simulator,
                profile.targets,
                humidity_control_mode=profile.humidity_control_mode,
                status=status,
                sensor_timeout_ms=SENSOR_TIMEOUT_MS,
            )
            features.append(row.astype(np.float32, copy=False))
            residuals.append(
                np.asarray(oracle.action.as_tuple(), dtype=np.float32)
                - np.asarray(rule.as_tuple(), dtype=np.float32)
            )
            evaluations.append(int(oracle.evaluations))
            family_counts[episode.family] += 1
            simulator.step(
                oracle.action,
                add_sensor_noise=False,
                light_level=profile.light_level,
            )
            effective.update(simulator.scenario, oracle.action)

    x = np.asarray(features, dtype=np.float32)
    residual_y = np.asarray(residuals, dtype=np.float32)
    if x.shape != (90, 44) or residual_y.shape != (90, 6):
        raise AssertionError(f"unexpected Stage 14C train tensors: {x.shape}, {residual_y.shape}")
    if any(count != 6 for count in family_counts.values()):
        raise AssertionError(f"unexpected Stage 14C train family counts: {family_counts}")
    target = np.clip(residual_y / np.float32(BOUND), -1.0, 1.0)
    model = _build_residual_model(TRAIN_SEED + 500 + 4 * 17)
    _fit(model, x, target, TRAIN_SEED + 700 + 4 * 19)
    return model, float(np.mean(evaluations)), family_counts


def _raw_action(
    policy: str,
    *,
    simulator: ClimateSimulator,
    episode,
    step: int,
    model,
    trends: ClimateTrendEstimator,
    effective: ClimateEffectiveActionEstimator,
    sequence_teacher: ClimateSequenceRolloutTeacher,
) -> tuple[ClimateAction, dict]:
    profile = episode.profile_for_step(step, BENCHMARK_STEPS_PER_SCENARIO)
    simulator.set_light_level(profile.light_level)
    state = simulator.observe(add_sensor_noise=False)
    status = _status_for_step(episode, step, BENCHMARK_STEPS_PER_SCENARIO)
    rule = ClimateRulePolicy().choose(
        simulator.scenario,
        state,
        profile,
        status=status,
        sensor_timeout_ms=SENSOR_TIMEOUT_MS,
    )
    if policy == "rule":
        return rule, status
    if policy == "sequence":
        oracle = sequence_teacher.choose(
            simulator,
            profile.targets,
            humidity_control_mode=profile.humidity_control_mode,
            status=status,
            sensor_timeout_ms=SENSOR_TIMEOUT_MS,
        )
        return oracle.action, status
    if policy != "residual":
        raise ValueError(policy)

    trend_values = trends.update(
        state,
        int(round(simulator.elapsed_s * 1000.0)),
        status=status,
        sensor_timeout_ms=SENSOR_TIMEOUT_MS,
    )
    row = encode_climate_input(
        simulator.scenario,
        state,
        previous=simulator.previous_command,
        estimated_effective=effective.state,
        trends=trend_values,
        status=status,
        config=ClimateInputConfig(
            targets=profile.targets,
            humidity_control_mode=profile.humidity_control_mode,
            sensor_timeout_ms=SENSOR_TIMEOUT_MS,
        ),
    )
    normalized_delta = np.asarray(model(row.reshape(1, -1), training=False), dtype=np.float32)[0]
    rule_values = np.asarray(rule.as_tuple(), dtype=np.float32)
    combined = np.clip(rule_values + np.float32(BOUND) * normalized_delta, 0.0, 1.0)
    return ClimateAction.from_mapping(dict(zip(CLIMATE_OUTPUT_NAMES, combined, strict=True))), status


def _run_policy(policy: str, episodes, model) -> tuple[Metrics, dict[str, float]]:
    totals = {
        "steps": 0,
        "tracking": 0.0,
        "switching": 0.0,
        "effort": 0.0,
        "safety": 0,
        "arbitration": 0,
        "hard": 0,
    }
    family_tracking: dict[str, list[float]] = {family: [] for family in REQUIRED_SCENARIO_FAMILIES}
    sequence_teacher = ClimateSequenceRolloutTeacher()

    for episode in episodes:
        simulator = ClimateSimulator(episode.scenario)
        trends = ClimateTrendEstimator()
        effective = ClimateEffectiveActionEstimator()
        previous_applied = ClimateAction()
        episode_tracking = 0.0
        for step in range(BENCHMARK_STEPS_PER_SCENARIO):
            profile = episode.profile_for_step(step, BENCHMARK_STEPS_PER_SCENARIO)
            simulator.set_light_level(profile.light_level)
            state = simulator.observe(add_sensor_noise=False)
            status = _status_for_step(episode, step, BENCHMARK_STEPS_PER_SCENARIO)
            tracking_cost, *_ = _tracking_terms(state, profile, status, SENSOR_TIMEOUT_MS)
            episode_tracking += float(tracking_cost)
            totals["tracking"] += float(tracking_cost)
            totals["hard"] += int(bool(hard_limit_violations(state)))

            raw, status = _raw_action(
                policy,
                simulator=simulator,
                episode=episode,
                step=step,
                model=model,
                trends=trends,
                effective=effective,
                sequence_teacher=sequence_teacher,
            )
            arbitration = arbitrate_climate_action(raw, simulator.scenario)
            safety = apply_climate_safety(
                arbitration.action,
                simulator.scenario,
                state,
                profile,
                status=status,
                sensor_timeout_ms=SENSOR_TIMEOUT_MS,
            )
            applied = safety.action
            totals["arbitration"] += int(bool(arbitration.interventions))
            totals["safety"] += int(bool(safety.interventions))
            totals["switching"] += sum(
                abs(a - b)
                for a, b in zip(applied.as_tuple(), previous_applied.as_tuple(), strict=True)
            ) / len(CLIMATE_OUTPUT_NAMES)
            totals["effort"] += sum(applied.as_tuple()) / len(CLIMATE_OUTPUT_NAMES)
            simulator.step(applied, add_sensor_noise=False, light_level=profile.light_level)
            effective.update(simulator.scenario, applied)
            previous_applied = applied
            totals["steps"] += 1
        family_tracking[episode.family].append(episode_tracking / BENCHMARK_STEPS_PER_SCENARIO)

    steps = int(totals["steps"])
    metrics = Metrics(
        steps=steps,
        tracking_cost=float(totals["tracking"]) / steps,
        switching_per_step=float(totals["switching"]) / steps,
        actuator_effort_per_step=float(totals["effort"]) / steps,
        safety_intervention_fraction=float(totals["safety"]) / steps,
        arbitration_intervention_fraction=float(totals["arbitration"]) / steps,
        hard_limit_violation_fraction=float(totals["hard"]) / steps,
    )
    family_mean = {
        family: float(np.mean(values)) if values else float("nan")
        for family, values in family_tracking.items()
    }
    return metrics, family_mean


def main() -> None:
    started = time.monotonic()
    model, training_evaluations_per_row, train_family_counts = _train_residual_model()
    episodes = structured_training_episodes(
        scenarios_per_family=BENCHMARK_SCENARIOS_PER_FAMILY,
        seed=BENCHMARK_SEED,
    )
    if len(episodes) != len(REQUIRED_SCENARIO_FAMILIES):
        raise AssertionError("Stage 14C benchmark must contain one episode per family")

    metrics: dict[str, dict] = {}
    family_tracking: dict[str, dict[str, float]] = {}
    for policy in POLICIES:
        policy_metrics, policy_family = _run_policy(policy, episodes, model)
        metrics[policy] = asdict(policy_metrics)
        family_tracking[policy] = policy_family

    rule_tracking = float(metrics["rule"]["tracking_cost"])
    residual_tracking = float(metrics["residual"]["tracking_cost"])
    sequence_tracking = float(metrics["sequence"]["tracking_cost"])
    improvement = (rule_tracking - residual_tracking) / rule_tracking if rule_tracking else 0.0
    result = {
        "experiment": "stage14c_residual_closed_loop_dev",
        "train_seed": TRAIN_SEED,
        "benchmark_seed": BENCHMARK_SEED,
        "residual_bound": BOUND,
        "train_rows": 90,
        "train_family_counts": train_family_counts,
        "training_sequence_evaluations_per_row": training_evaluations_per_row,
        "benchmark_scenarios_per_family": BENCHMARK_SCENARIOS_PER_FAMILY,
        "benchmark_steps_per_scenario": BENCHMARK_STEPS_PER_SCENARIO,
        "metrics": metrics,
        "family_tracking_cost": family_tracking,
        "residual_tracking_improvement_vs_rule_fraction": improvement,
        "residual_beats_rule_tracking": residual_tracking < rule_tracking,
        "sequence_beats_rule_tracking": sequence_tracking < rule_tracking,
        "residual_safety_clear": (
            float(metrics["residual"]["safety_intervention_fraction"]) == 0.0
            and float(metrics["residual"]["hard_limit_violation_fraction"]) == 0.0
        ),
        "reserved_stage14ab_test_split_evaluated": False,
        "wall_seconds": float(time.monotonic() - started),
    }
    finite_values = [
        rule_tracking,
        residual_tracking,
        sequence_tracking,
        improvement,
        result["wall_seconds"],
    ]
    if not all(math.isfinite(float(value)) for value in finite_values):
        raise AssertionError("Stage 14C produced non-finite summary metrics")
    print("STAGE14C_JSON=" + json.dumps(result, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
