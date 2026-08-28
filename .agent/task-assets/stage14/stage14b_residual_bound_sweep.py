#!/usr/bin/env python3
"""Stage 14B validation-only sweep for bounded residual climate control."""

from __future__ import annotations

import json
import math
import time

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
from tools.ml.climate_simulator import CLIMATE_OUTPUT_NAMES, ClimateSimulator
from tools.ml.climate_training import configure_tensorflow_determinism

SEED = 141421
SCENARIOS_PER_FAMILY = 4
STEPS_PER_SCENARIO = 3
EPOCHS = 32
BATCH_SIZE = 32
BOUNDS = (0.10, 0.20, 0.35, 0.50, 1.00)


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
        name="stage14b_bounded_residual",
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
                raise AssertionError("Stage 14B requires finite 44-feature rows")
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

    train = split_arr == "train"
    validation = split_arr == "validation"
    test = split_arr == "test"
    for mask, name in ((train, "train"), (validation, "validation"), (test, "test")):
        if not np.any(mask):
            raise AssertionError(f"Stage 14B {name} split is empty")
    for family in REQUIRED_SCENARIO_FAMILIES:
        if not np.any(validation & (family_arr == family)):
            raise AssertionError(f"validation split lacks family {family}")

    expected = oracle_y[validation]
    rule_prediction = rule_y[validation]
    rule_mae = float(np.mean(np.abs(rule_prediction - expected)))
    sweep: dict[str, dict[str, object]] = {}

    for bound_index, bound in enumerate(BOUNDS):
        target = np.clip(residual_y[train] / np.float32(bound), -1.0, 1.0)
        model = _build_residual_model(SEED + 500 + bound_index * 17)
        _fit(model, x[train], target, SEED + 700 + bound_index * 19)
        normalized_delta = np.asarray(model(x[validation], training=False), dtype=np.float32)
        delta = np.float32(bound) * normalized_delta
        prediction = np.clip(rule_prediction + delta, 0.0, 1.0)

        projected_delta = np.clip(residual_y[validation], -bound, bound)
        projected = np.clip(rule_prediction + projected_delta, 0.0, 1.0)
        mae = float(np.mean(np.abs(prediction - expected)))
        floor_mae = float(np.mean(np.abs(projected - expected)))
        sweep[f"{bound:.2f}"] = {
            "validation_action_mae": mae,
            "validation_action_mae_by_output": _mae_by_output(expected, prediction),
            "oracle_projection_floor_mae": floor_mae,
            "improvement_vs_rule_fraction": (rule_mae - mae) / rule_mae if rule_mae else 0.0,
            "headroom_to_projection_floor": mae - floor_mae,
        }

    winner_bound = min(BOUNDS, key=lambda value: float(sweep[f"{value:.2f}"]["validation_action_mae"]))
    winner = sweep[f"{winner_bound:.2f}"]
    result = {
        "experiment": "stage14b_sequence_oracle_residual_bound_sweep",
        "seed": SEED,
        "scenarios_per_family": SCENARIOS_PER_FAMILY,
        "steps_per_scenario": STEPS_PER_SCENARIO,
        "rows": int(len(x)),
        "split_rows": {
            "train": int(np.sum(train)),
            "validation": int(np.sum(validation)),
            "test_reserved_uninspected": int(np.sum(test)),
        },
        "validation_family_counts": {
            family: int(np.sum(validation & (family_arr == family)))
            for family in REQUIRED_SCENARIO_FAMILIES
        },
        "sequence_evaluations_per_row": float(np.mean(evaluations)),
        "rule_validation_action_mae": rule_mae,
        "bounds": sweep,
        "winner_bound": float(winner_bound),
        "winner_validation_action_mae": float(winner["validation_action_mae"]),
        "winner_beats_rule": bool(float(winner["validation_action_mae"]) < rule_mae),
        "test_metrics_evaluated": False,
        "wall_seconds": float(time.monotonic() - started),
    }
    numeric = [
        result["rule_validation_action_mae"],
        result["winner_validation_action_mae"],
        result["wall_seconds"],
    ]
    if not all(math.isfinite(float(value)) for value in numeric):
        raise AssertionError("Stage 14B produced non-finite summary metrics")
    print("STAGE14B_JSON=" + json.dumps(result, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
