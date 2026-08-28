#!/usr/bin/env python3
"""Stage 14G read-only data-scaling probe for projected residual climate control."""

from __future__ import annotations

import importlib.util
import json
import math
import sys
import time
from dataclasses import asdict
from pathlib import Path

import numpy as np

from tools.ml.climate_dataset import ClimateDatasetConfig, _family_aware_splits, _runtime_status
from tools.ml.climate_input import ClimateEffectiveActionEstimator, ClimateInputConfig, ClimateTrendEstimator, encode_climate_input
from tools.ml.climate_policy import ClimateRulePolicy
from tools.ml.climate_scenarios import REQUIRED_SCENARIO_FAMILIES, structured_training_episodes
from tools.ml.climate_sequence_teacher import ClimateSequenceRolloutTeacher
from tools.ml.climate_simulator import ClimateSimulator

BASE_PATH = Path('/tmp/stage14f-per-output-residual-ablation.py')
spec = importlib.util.spec_from_file_location('stage14f_base', BASE_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError('cannot load Stage 14F base')
base = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = base
spec.loader.exec_module(base)

TRAIN_SEED = 141421
TRAIN_SCENARIOS_PER_FAMILY = 8
TRAIN_STEPS_PER_SCENARIO = 3
EXPECTED_TRAIN_ROWS = 180
DEADZONE = 0.20
VARIANTS = {
    'all': base.MASKS['all'],
    'cooler_exhaust': base.MASKS['cooler_exhaust'],
    'thermal_exhaust': base.MASKS['thermal_exhaust'],
    'dehumidifier': base.MASKS['dehumidifier'],
}


def _train_scaled_model():
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
    features = []
    residuals = []
    evaluations = []
    family_counts = {family: 0 for family in REQUIRED_SCENARIO_FAMILIES}

    for episode_index, episode in enumerate(episodes):
        if split_by_id[episode.scenario.scenario_id] != 'train':
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
                sensor_timeout_ms=base.base.SENSOR_TIMEOUT_MS,
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
                raise AssertionError('Stage 14G requires finite 44-feature rows')
            rule = rule_policy.choose(
                simulator.scenario,
                observation,
                profile,
                status=status,
                sensor_timeout_ms=base.base.SENSOR_TIMEOUT_MS,
            )
            oracle = teacher.choose(
                simulator,
                profile.targets,
                humidity_control_mode=profile.humidity_control_mode,
                status=status,
                sensor_timeout_ms=base.base.SENSOR_TIMEOUT_MS,
            )
            features.append(row.astype(np.float32, copy=False))
            residuals.append(
                np.asarray(oracle.action.as_tuple(), dtype=np.float32)
                - np.asarray(rule.as_tuple(), dtype=np.float32)
            )
            evaluations.append(int(oracle.evaluations))
            family_counts[episode.family] += 1
            simulator.step(oracle.action, add_sensor_noise=False, light_level=profile.light_level)
            effective.update(simulator.scenario, oracle.action)

    x = np.asarray(features, dtype=np.float32)
    y = np.asarray(residuals, dtype=np.float32)
    if x.shape != (EXPECTED_TRAIN_ROWS, 44) or y.shape != (EXPECTED_TRAIN_ROWS, 6):
        raise AssertionError(f'unexpected Stage 14G train tensors: {x.shape}, {y.shape}')
    if any(count != 12 for count in family_counts.values()):
        raise AssertionError(f'unexpected Stage 14G train family counts: {family_counts}')

    model = base.base._build_residual_model(TRAIN_SEED + 500 + 4 * 17)
    target = np.clip(y / np.float32(base.base.BOUND), -1.0, 1.0)
    base.base._fit(model, x, target, TRAIN_SEED + 700 + 4 * 19)
    return model, float(np.mean(evaluations)), family_counts


def main() -> None:
    started = time.monotonic()
    model, evaluations_per_row, family_counts = _train_scaled_model()
    episodes = structured_training_episodes(
        scenarios_per_family=base.base.BENCHMARK_SCENARIOS_PER_FAMILY,
        seed=base.base.BENCHMARK_SEED,
    )
    rule = base.base._run_rule(episodes)

    variants = {}
    for key, enabled_names in VARIANTS.items():
        metrics, arbitration_reasons, safety_reasons = base._run_variant(episodes, model, enabled_names)
        variants[key] = {
            'enabled_outputs': list(enabled_names),
            'metrics': asdict(metrics),
            'arbitration_reasons': arbitration_reasons,
            'safety_reasons': safety_reasons,
            'tracking_improvement_vs_rule_fraction': (
                (rule.tracking_cost - metrics.tracking_cost) / rule.tracking_cost
                if rule.tracking_cost else 0.0
            ),
            'switching_ratio_vs_rule': (
                metrics.switching_per_step / rule.switching_per_step
                if rule.switching_per_step else 0.0
            ),
        }

    eligible = [
        key for key, value in variants.items()
        if float(value['metrics']['hard_limit_violation_fraction']) == 0.0
        and float(value['metrics']['safety_intervention_fraction']) == 0.0
        and float(value['metrics']['arbitration_intervention_fraction']) == 0.0
        and float(value['metrics']['tracking_cost']) < rule.tracking_cost
    ]
    winner = min(
        eligible,
        key=lambda key: (
            float(variants[key]['metrics']['switching_per_step']),
            float(variants[key]['metrics']['tracking_cost']),
        ),
    ) if eligible else None

    result = {
        'experiment': 'stage14g_residual_data_scaling_probe',
        'train_seed': TRAIN_SEED,
        'benchmark_seed': base.base.BENCHMARK_SEED,
        'train_scenarios_per_family': TRAIN_SCENARIOS_PER_FAMILY,
        'train_steps_per_scenario': TRAIN_STEPS_PER_SCENARIO,
        'train_rows': EXPECTED_TRAIN_ROWS,
        'train_family_counts': family_counts,
        'deadzone': DEADZONE,
        'training_sequence_evaluations_per_row': evaluations_per_row,
        'rule_metrics': asdict(rule),
        'variants': variants,
        'eligible_zero_intervention_variants': eligible,
        'winner': winner,
        'reserved_stage14ab_test_split_evaluated': False,
        'wall_seconds': float(time.monotonic() - started),
    }
    if winner is not None:
        result['winner_metrics'] = variants[winner]
    if not math.isfinite(result['wall_seconds']):
        raise AssertionError('Stage 14G produced non-finite wall time')
    print('STAGE14G_JSON=' + json.dumps(result, sort_keys=True), flush=True)


if __name__ == '__main__':
    main()
