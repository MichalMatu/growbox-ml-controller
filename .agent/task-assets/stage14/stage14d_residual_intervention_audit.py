#!/usr/bin/env python3
"""Stage 14D read-only intervention/deadzone audit for residual climate control."""

from __future__ import annotations

import json
import math
import time
from collections import Counter
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
DEADZONES = (0.0, 0.02, 0.05, 0.10, 0.15, 0.20)


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
        name="stage14d_bounded_residual",
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
            row = encode_climate_input(
                simulator.scenario,
                observation,
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
            simulator.step(oracle.action, add_sensor_noise=False, light_level=profile.light_level)
            effective.update(simulator.scenario, oracle.action)

    x = np.asarray(features, dtype=np.float32)
    y = np.asarray(residuals, dtype=np.float32)
    if x.shape != (90, 44) or y.shape != (90, 6):
        raise AssertionError(f"unexpected Stage 14D train tensors: {x.shape}, {y.shape}")
    model = _build_residual_model(TRAIN_SEED + 500 + 4 * 17)
    _fit(model, x, np.clip(y / np.float32(BOUND), -1.0, 1.0), TRAIN_SEED + 700 + 4 * 19)
    return model, float(np.mean(evaluations))


def _raw_residual_action(
    *,
    simulator: ClimateSimulator,
    episode,
    step: int,
    model,
    trends: ClimateTrendEstimator,
    effective: ClimateEffectiveActionEstimator,
    deadzone: float,
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
    delta = np.asarray(model(row.reshape(1, -1), training=False), dtype=np.float32)[0]
    if deadzone > 0.0:
        delta = np.where(np.abs(delta) <= np.float32(deadzone), np.float32(0.0), delta)
    combined = np.clip(
        np.asarray(rule.as_tuple(), dtype=np.float32) + np.float32(BOUND) * delta,
        0.0,
        1.0,
    )
    return ClimateAction.from_mapping(dict(zip(CLIMATE_OUTPUT_NAMES, combined, strict=True))), status


def _run_rule(episodes) -> Metrics:
    totals = {"steps": 0, "tracking": 0.0, "switching": 0.0, "effort": 0.0, "hard": 0}
    for episode in episodes:
        simulator = ClimateSimulator(episode.scenario)
        previous = ClimateAction()
        for step in range(BENCHMARK_STEPS_PER_SCENARIO):
            profile = episode.profile_for_step(step, BENCHMARK_STEPS_PER_SCENARIO)
            simulator.set_light_level(profile.light_level)
            state = simulator.observe(add_sensor_noise=False)
            status = _status_for_step(episode, step, BENCHMARK_STEPS_PER_SCENARIO)
            tracking_cost, *_ = _tracking_terms(state, profile, status, SENSOR_TIMEOUT_MS)
            totals["tracking"] += float(tracking_cost)
            totals["hard"] += int(bool(hard_limit_violations(state)))
            action = ClimateRulePolicy().choose(
                simulator.scenario,
                state,
                profile,
                status=status,
                sensor_timeout_ms=SENSOR_TIMEOUT_MS,
            )
            totals["switching"] += sum(
                abs(a - b) for a, b in zip(action.as_tuple(), previous.as_tuple(), strict=True)
            ) / len(CLIMATE_OUTPUT_NAMES)
            totals["effort"] += sum(action.as_tuple()) / len(CLIMATE_OUTPUT_NAMES)
            simulator.step(action, add_sensor_noise=False, light_level=profile.light_level)
            previous = action
            totals["steps"] += 1
    steps = int(totals["steps"])
    return Metrics(
        steps=steps,
        tracking_cost=float(totals["tracking"]) / steps,
        switching_per_step=float(totals["switching"]) / steps,
        actuator_effort_per_step=float(totals["effort"]) / steps,
        safety_intervention_fraction=0.0,
        arbitration_intervention_fraction=0.0,
        hard_limit_violation_fraction=float(totals["hard"]) / steps,
    )


def _run_residual(episodes, model, deadzone: float):
    totals = {
        "steps": 0,
        "tracking": 0.0,
        "switching": 0.0,
        "effort": 0.0,
        "safety": 0,
        "arbitration": 0,
        "hard": 0,
    }
    arbitration_reasons: Counter[str] = Counter()
    safety_reasons: Counter[str] = Counter()

    for episode in episodes:
        simulator = ClimateSimulator(episode.scenario)
        trends = ClimateTrendEstimator()
        effective = ClimateEffectiveActionEstimator()
        previous = ClimateAction()
        for step in range(BENCHMARK_STEPS_PER_SCENARIO):
            profile = episode.profile_for_step(step, BENCHMARK_STEPS_PER_SCENARIO)
            simulator.set_light_level(profile.light_level)
            state = simulator.observe(add_sensor_noise=False)
            status = _status_for_step(episode, step, BENCHMARK_STEPS_PER_SCENARIO)
            tracking_cost, *_ = _tracking_terms(state, profile, status, SENSOR_TIMEOUT_MS)
            totals["tracking"] += float(tracking_cost)
            totals["hard"] += int(bool(hard_limit_violations(state)))
            raw, status = _raw_residual_action(
                simulator=simulator,
                episode=episode,
                step=step,
                model=model,
                trends=trends,
                effective=effective,
                deadzone=deadzone,
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
            if arbitration.interventions:
                totals["arbitration"] += 1
                arbitration_reasons.update(arbitration.interventions)
            if safety.interventions:
                totals["safety"] += 1
                safety_reasons.update(safety.interventions)
            totals["switching"] += sum(
                abs(a - b) for a, b in zip(applied.as_tuple(), previous.as_tuple(), strict=True)
            ) / len(CLIMATE_OUTPUT_NAMES)
            totals["effort"] += sum(applied.as_tuple()) / len(CLIMATE_OUTPUT_NAMES)
            simulator.step(applied, add_sensor_noise=False, light_level=profile.light_level)
            effective.update(simulator.scenario, applied)
            previous = applied
            totals["steps"] += 1

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
    return metrics, dict(arbitration_reasons), dict(safety_reasons)


def main() -> None:
    started = time.monotonic()
    model, evaluations_per_row = _train_residual_model()
    episodes = structured_training_episodes(
        scenarios_per_family=BENCHMARK_SCENARIOS_PER_FAMILY,
        seed=BENCHMARK_SEED,
    )
    rule = _run_rule(episodes)
    variants: dict[str, dict] = {}
    for deadzone in DEADZONES:
        metrics, arbitration_reasons, safety_reasons = _run_residual(episodes, model, deadzone)
        variants[f"{deadzone:.2f}"] = {
            "metrics": asdict(metrics),
            "arbitration_reasons": arbitration_reasons,
            "safety_reasons": safety_reasons,
            "tracking_improvement_vs_rule_fraction": (
                (rule.tracking_cost - metrics.tracking_cost) / rule.tracking_cost
                if rule.tracking_cost
                else 0.0
            ),
        }

    safest_key = min(
        variants,
        key=lambda key: (
            float(variants[key]["metrics"]["safety_intervention_fraction"]),
            float(variants[key]["metrics"]["arbitration_intervention_fraction"]),
            float(variants[key]["metrics"]["tracking_cost"]),
        ),
    )
    best_tracking_key = min(
        variants,
        key=lambda key: float(variants[key]["metrics"]["tracking_cost"]),
    )
    result = {
        "experiment": "stage14d_residual_intervention_deadzone_audit",
        "train_seed": TRAIN_SEED,
        "benchmark_seed": BENCHMARK_SEED,
        "training_sequence_evaluations_per_row": evaluations_per_row,
        "rule_metrics": asdict(rule),
        "deadzones": variants,
        "safest_deadzone": float(safest_key),
        "best_tracking_deadzone": float(best_tracking_key),
        "reserved_stage14ab_test_split_evaluated": False,
        "wall_seconds": float(time.monotonic() - started),
    }
    if not math.isfinite(result["wall_seconds"]):
        raise AssertionError("Stage 14D produced non-finite wall time")
    print("STAGE14D_JSON=" + json.dumps(result, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
