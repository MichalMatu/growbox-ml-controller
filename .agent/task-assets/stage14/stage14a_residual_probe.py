#!/usr/bin/env python3
"""Stage 14A development probe for sequence-oracle residual learning."""

from __future__ import annotations

import json
import math
import time
from collections import defaultdict

import numpy as np

from tools.ml.climate_dataset import ClimateDatasetConfig, _family_aware_splits, _runtime_status
from tools.ml.climate_input import (
    ClimateEffectiveActionEstimator,
    ClimateInputConfig,
    ClimateTrendEstimator,
    encode_climate_input,
)
from tools.ml.climate_policy import ClimateRulePolicy
from tools.ml.climate_scenarios import REQUIRED_SCENARIO_FAMILIES, structured_training_episodes
from tools.ml.climate_sequence_teacher import ClimateSequenceRolloutTeacher
from tools.ml.climate_simulator import CLIMATE_OUTPUT_NAMES, ClimateAction, ClimateSimulator
from tools.ml.climate_training import configure_tensorflow_determinism

SEED = 141421
SCENARIOS_PER_FAMILY = 4
STEPS_PER_SCENARIO = 3
EPOCHS = 24
BATCH_SIZE = 32


def _build_model(seed: int, *, residual: bool):
    tf = configure_tensorflow_determinism(seed)
    keras = tf.keras
    activation = "tanh" if residual else "sigmoid"
    name = "stage14a_residual" if residual else "stage14a_direct"
    model = keras.Sequential(
        [
            keras.layers.Input(shape=(44,), name="climate_v6_features"),
            keras.layers.Dense(
                32,
                activation="relu",
                kernel_initializer=keras.initializers.GlorotUniform(seed=seed + 1),
                bias_initializer="zeros",
            ),
            keras.layers.Dense(
                32,
                activation="relu",
                kernel_initializer=keras.initializers.GlorotUniform(seed=seed + 2),
                bias_initializer="zeros",
            ),
            keras.layers.Dense(
                6,
                activation=activation,
                kernel_initializer=keras.initializers.GlorotUniform(seed=seed + 3),
                bias_initializer="zeros",
            ),
        ],
        name=name,
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


def _mae_by_output(expected: np.ndarray, predicted: np.ndarray) -> dict[str, float]:
    return {
        name: float(np.mean(np.abs(predicted[:, index] - expected[:, index])))
        for index, name in enumerate(CLIMATE_OUTPUT_NAMES)
    }


def main() -> None:
    started = time.monotonic()
    config = ClimateDatasetConfig(
        scenarios_per_family=SCENARIOS_PER_FAMILY,
        steps_per_scenario=STEPS_PER_SCENARIO,
        seed=SEED,
        random_invalid_probability=0.01,
        random_stale_probability=0.01,
    )
    episodes = structured_training_episodes(
        scenarios_per_family=SCENARIOS_PER_FAMILY,
        seed=SEED,
    )
    split_by_id = _family_aware_splits(episodes, seed=SEED + 31)
    teacher = ClimateSequenceRolloutTeacher()
    rule_policy = ClimateRulePolicy()

    features: list[np.ndarray] = []
    oracle_actions: list[np.ndarray] = []
    rule_actions: list[np.ndarray] = []
    splits: list[str] = []
    families: list[str] = []
    safe_fallbacks: list[bool] = []
    evaluations: list[int] = []

    for episode_index, episode in enumerate(episodes):
        simulator = ClimateSimulator(episode.scenario)
        trends = ClimateTrendEstimator()
        effective = ClimateEffectiveActionEstimator()
        status_rng = np.random.default_rng(episode.scenario.seed ^ 0x6A09E667 ^ episode_index)
        for step_index in range(STEPS_PER_SCENARIO):
            profile = episode.profile_for_step(step_index, STEPS_PER_SCENARIO)
            simulator.set_light_level(profile.light_level)
            observation = simulator.observe(add_sensor_noise=False)
            status = _runtime_status(
                episode,
                step_index=step_index,
                total_steps=STEPS_PER_SCENARIO,
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
                raise AssertionError("Stage 14A requires finite 44-feature rows")
            rule = rule_policy.choose(
                simulator.scenario,
                observation,
                profile,
                status=status,
                sensor_timeout_ms=input_config.sensor_timeout_ms,
            )
            oracle = teacher.choose(
                simulator,
                profile.targets,
                humidity_control_mode=profile.humidity_control_mode,
                status=status,
                sensor_timeout_ms=input_config.sensor_timeout_ms,
            )
            features.append(row.astype(np.float32, copy=False))
            rule_actions.append(np.asarray(rule.as_tuple(), dtype=np.float32))
            oracle_actions.append(np.asarray(oracle.action.as_tuple(), dtype=np.float32))
            splits.append(split_by_id[episode.scenario.scenario_id])
            families.append(episode.family)
            safe_fallbacks.append(bool(oracle.safe_fallback))
            evaluations.append(int(oracle.evaluations))
            simulator.step(
                oracle.action,
                add_sensor_noise=False,
                light_level=profile.light_level,
            )
            effective.update(simulator.scenario, oracle.action)

    x = np.asarray(features, dtype=np.float32)
    oracle_y = np.asarray(oracle_actions, dtype=np.float32)
    rule_y = np.asarray(rule_actions, dtype=np.float32)
    split_arr = np.asarray(splits)
    family_arr = np.asarray(families)
    residual_y = oracle_y - rule_y
    if x.shape[1:] != (44,) or oracle_y.shape[1:] != (6,):
        raise AssertionError("unexpected Stage 14A tensor shapes")
    if float(np.min(residual_y)) < -1.000001 or float(np.max(residual_y)) > 1.000001:
        raise AssertionError("oracle-rule residual escaped [-1, 1]")
    reconstructed = np.clip(rule_y + residual_y, 0.0, 1.0)
    if not np.allclose(reconstructed, oracle_y, atol=1.0e-7, rtol=0.0):
        raise AssertionError("exact residual reconstruction failed")

    train = split_arr == "train"
    validation = split_arr == "validation"
    test = split_arr == "test"
    for mask, name in ((train, "train"), (validation, "validation"), (test, "test")):
        if not np.any(mask):
            raise AssertionError(f"Stage 14A {name} split is empty")
    for family in REQUIRED_SCENARIO_FAMILIES:
        if not np.any(validation & (family_arr == family)):
            raise AssertionError(f"validation split lacks family {family}")

    direct = _build_model(SEED + 101, residual=False)
    residual = _build_model(SEED + 202, residual=True)
    _fit(direct, x[train], oracle_y[train], SEED + 303)
    _fit(residual, x[train], residual_y[train], SEED + 404)

    direct_prediction = np.asarray(direct(x[validation], training=False), dtype=np.float32)
    delta_prediction = np.asarray(residual(x[validation], training=False), dtype=np.float32)
    residual_prediction = np.clip(rule_y[validation] + delta_prediction, 0.0, 1.0)
    rule_prediction = rule_y[validation]
    expected = oracle_y[validation]

    abs_residual = np.abs(residual_y)
    per_output_residual = {}
    for index, name in enumerate(CLIMATE_OUTPUT_NAMES):
        values = abs_residual[:, index]
        per_output_residual[name] = {
            "mean_abs": float(np.mean(values)),
            "p95_abs": float(np.quantile(values, 0.95)),
            "within_0_05_fraction": float(np.mean(values <= 0.05)),
        }

    family_validation_counts = {
        family: int(np.sum(validation & (family_arr == family)))
        for family in REQUIRED_SCENARIO_FAMILIES
    }
    result = {
        "experiment": "stage14a_sequence_oracle_bounded_residual_probe",
        "seed": SEED,
        "scenarios_per_family": SCENARIOS_PER_FAMILY,
        "steps_per_scenario": STEPS_PER_SCENARIO,
        "rows": int(len(x)),
        "split_rows": {
            "train": int(np.sum(train)),
            "validation": int(np.sum(validation)),
            "test_reserved_uninspected": int(np.sum(test)),
        },
        "validation_family_counts": family_validation_counts,
        "sequence_evaluations_per_row": float(np.mean(evaluations)),
        "safe_fallback_fraction": float(np.mean(safe_fallbacks)),
        "residual_range": [float(np.min(residual_y)), float(np.max(residual_y))],
        "residual_abs_mean": float(np.mean(abs_residual)),
        "residual_abs_p95": float(np.quantile(abs_residual, 0.95)),
        "residual_within_0_05_fraction": float(np.mean(abs_residual <= 0.05)),
        "residual_by_output": per_output_residual,
        "validation_action_mae": {
            "rule": float(np.mean(np.abs(rule_prediction - expected))),
            "direct_mlp": float(np.mean(np.abs(direct_prediction - expected))),
            "bounded_residual_mlp": float(np.mean(np.abs(residual_prediction - expected))),
        },
        "validation_action_mae_by_output": {
            "rule": _mae_by_output(expected, rule_prediction),
            "direct_mlp": _mae_by_output(expected, direct_prediction),
            "bounded_residual_mlp": _mae_by_output(expected, residual_prediction),
        },
        "test_metrics_evaluated": False,
        "wall_seconds": float(time.monotonic() - started),
    }
    if not all(math.isfinite(float(value)) for value in result["validation_action_mae"].values()):
        raise AssertionError("non-finite validation metric")
    print("STAGE14A_JSON=" + json.dumps(result, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
