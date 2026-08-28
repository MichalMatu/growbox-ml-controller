#!/usr/bin/env python3
"""Stage 14E read-only projection and temporal smoothing audit for residual control."""

from __future__ import annotations

import importlib.util
import json
import math
import time
from collections import Counter
from dataclasses import asdict
from pathlib import Path

import numpy as np

from tools.ml.climate_benchmark import _status_for_step, _tracking_terms
from tools.ml.climate_input import ClimateEffectiveActionEstimator, ClimateInputConfig, ClimateTrendEstimator, encode_climate_input
from tools.ml.climate_policy import ClimateRulePolicy, apply_climate_safety, arbitrate_climate_action, hard_limit_violations
from tools.ml.climate_scenarios import structured_training_episodes
from tools.ml.climate_simulator import CLIMATE_OUTPUT_NAMES, ClimateAction, ClimateSimulator

BASE_PATH = Path('/tmp/stage14d-residual-intervention-audit.py')
spec = importlib.util.spec_from_file_location('stage14d_base', BASE_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError('cannot load Stage 14D base')
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)

DEADZONE = 0.20
ALPHAS = (1.0, 0.75, 0.50, 0.25)
SLEW_LIMITS = (1.0, 0.25, 0.15, 0.10)


def _usable_required(state, status) -> bool:
    return (
        status['air_temperature_c'].usable(state.air_temperature_c, base.SENSOR_TIMEOUT_MS)
        and status['relative_humidity_pct'].usable(state.relative_humidity_pct, base.SENSOR_TIMEOUT_MS)
    )


def _project(values: np.ndarray, rule: np.ndarray, simulator: ClimateSimulator, profile, state, status) -> np.ndarray:
    out = np.clip(np.asarray(values, dtype=np.float32), 0.0, 1.0)
    name_to_i = {name: i for i, name in enumerate(CLIMATE_OUTPUT_NAMES)}
    caps = simulator.scenario.actuators
    available = {
        'heater': caps.heater.available,
        'cooler': caps.cooler.available,
        'exhaust_fan': caps.exhaust_fan.available,
        'humidifier': caps.humidifier.available,
        'dehumidifier': caps.dehumidifier.available,
        'co2_doser': caps.co2_doser.available,
    }
    for name, ok in available.items():
        if not ok:
            out[name_to_i[name]] = 0.0

    if not _usable_required(state, status):
        return np.asarray(rule, dtype=np.float32)

    co2_ok = status['co2_ppm'].usable(state.co2_ppm, base.SENSOR_TIMEOUT_MS)
    if not profile.targets.co2_enabled or not co2_ok:
        out[name_to_i['co2_doser']] = 0.0

    for left, right in (('heater', 'cooler'), ('humidifier', 'dehumidifier')):
        li, ri = name_to_i[left], name_to_i[right]
        if rule[li] > 0.0:
            out[ri] = 0.0
        elif rule[ri] > 0.0:
            out[li] = 0.0
        elif out[li] > 0.0 and out[ri] > 0.0:
            if out[li] >= out[ri]:
                out[ri] = 0.0
            else:
                out[li] = 0.0
    return out


def _run_variant(episodes, model, *, alpha: float, slew_limit: float):
    totals = {'steps': 0, 'tracking': 0.0, 'switching': 0.0, 'effort': 0.0, 'safety': 0, 'arbitration': 0, 'hard': 0}
    arbitration_reasons: Counter[str] = Counter()
    safety_reasons: Counter[str] = Counter()

    for episode in episodes:
        simulator = ClimateSimulator(episode.scenario)
        trends = ClimateTrendEstimator()
        effective = ClimateEffectiveActionEstimator()
        previous_applied = ClimateAction()
        previous_correction = np.zeros(6, dtype=np.float32)

        for step in range(base.BENCHMARK_STEPS_PER_SCENARIO):
            profile = episode.profile_for_step(step, base.BENCHMARK_STEPS_PER_SCENARIO)
            simulator.set_light_level(profile.light_level)
            state = simulator.observe(add_sensor_noise=False)
            status = _status_for_step(episode, step, base.BENCHMARK_STEPS_PER_SCENARIO)
            tracking_cost, *_ = _tracking_terms(state, profile, status, base.SENSOR_TIMEOUT_MS)
            totals['tracking'] += float(tracking_cost)
            totals['hard'] += int(bool(hard_limit_violations(state)))

            rule_action = ClimateRulePolicy().choose(
                simulator.scenario, state, profile, status=status, sensor_timeout_ms=base.SENSOR_TIMEOUT_MS
            )
            rule = np.asarray(rule_action.as_tuple(), dtype=np.float32)
            trend_values = trends.update(
                state,
                int(round(simulator.elapsed_s * 1000.0)),
                status=status,
                sensor_timeout_ms=base.SENSOR_TIMEOUT_MS,
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
                    sensor_timeout_ms=base.SENSOR_TIMEOUT_MS,
                ),
            )
            delta = np.asarray(model(row.reshape(1, -1), training=False), dtype=np.float32)[0]
            delta = np.where(np.abs(delta) <= np.float32(DEADZONE), np.float32(0.0), delta)
            target_correction = np.clip(rule + delta, 0.0, 1.0) - rule

            if not _usable_required(state, status):
                correction = np.zeros(6, dtype=np.float32)
                previous_correction = correction.copy()
            else:
                filtered = np.float32(alpha) * target_correction + np.float32(1.0 - alpha) * previous_correction
                change = np.clip(filtered - previous_correction, -np.float32(slew_limit), np.float32(slew_limit))
                correction = previous_correction + change
                previous_correction = correction.copy()

            combined = _project(rule + correction, rule, simulator, profile, state, status)
            raw = ClimateAction.from_mapping(dict(zip(CLIMATE_OUTPUT_NAMES, combined, strict=True)))
            arbitration = arbitrate_climate_action(raw, simulator.scenario)
            safety = apply_climate_safety(
                arbitration.action,
                simulator.scenario,
                state,
                profile,
                status=status,
                sensor_timeout_ms=base.SENSOR_TIMEOUT_MS,
            )
            applied = safety.action
            if arbitration.interventions:
                totals['arbitration'] += 1
                arbitration_reasons.update(arbitration.interventions)
            if safety.interventions:
                totals['safety'] += 1
                safety_reasons.update(safety.interventions)
            totals['switching'] += sum(
                abs(a - b) for a, b in zip(applied.as_tuple(), previous_applied.as_tuple(), strict=True)
            ) / len(CLIMATE_OUTPUT_NAMES)
            totals['effort'] += sum(applied.as_tuple()) / len(CLIMATE_OUTPUT_NAMES)
            simulator.step(applied, add_sensor_noise=False, light_level=profile.light_level)
            effective.update(simulator.scenario, applied)
            previous_applied = applied
            totals['steps'] += 1

    steps = int(totals['steps'])
    metrics = base.Metrics(
        steps=steps,
        tracking_cost=float(totals['tracking']) / steps,
        switching_per_step=float(totals['switching']) / steps,
        actuator_effort_per_step=float(totals['effort']) / steps,
        safety_intervention_fraction=float(totals['safety']) / steps,
        arbitration_intervention_fraction=float(totals['arbitration']) / steps,
        hard_limit_violation_fraction=float(totals['hard']) / steps,
    )
    return metrics, dict(arbitration_reasons), dict(safety_reasons)


def main() -> None:
    started = time.monotonic()
    model, evaluations_per_row = base._train_residual_model()
    episodes = structured_training_episodes(
        scenarios_per_family=base.BENCHMARK_SCENARIOS_PER_FAMILY,
        seed=base.BENCHMARK_SEED,
    )
    rule = base._run_rule(episodes)
    baseline_metrics, baseline_arb, baseline_safety = base._run_residual(episodes, model, DEADZONE)

    variants = {}
    for alpha in ALPHAS:
        for slew in SLEW_LIMITS:
            metrics, arb, safety = _run_variant(episodes, model, alpha=alpha, slew_limit=slew)
            key = f'a{alpha:.2f}_s{slew:.2f}'
            variants[key] = {
                'alpha': alpha,
                'slew_limit': slew,
                'metrics': asdict(metrics),
                'arbitration_reasons': arb,
                'safety_reasons': safety,
                'tracking_improvement_vs_rule_fraction': (
                    (rule.tracking_cost - metrics.tracking_cost) / rule.tracking_cost if rule.tracking_cost else 0.0
                ),
                'switching_ratio_vs_rule': metrics.switching_per_step / rule.switching_per_step if rule.switching_per_step else 0.0,
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
        'experiment': 'stage14e_projected_residual_temporal_smoothing_audit',
        'train_seed': base.TRAIN_SEED,
        'benchmark_seed': base.BENCHMARK_SEED,
        'deadzone': DEADZONE,
        'training_sequence_evaluations_per_row': evaluations_per_row,
        'rule_metrics': asdict(rule),
        'stage14d_deadzone_020_baseline': {
            'metrics': asdict(baseline_metrics),
            'arbitration_reasons': baseline_arb,
            'safety_reasons': baseline_safety,
        },
        'variants': variants,
        'eligible_zero_intervention_variants': eligible,
        'winner': winner,
        'reserved_stage14ab_test_split_evaluated': False,
        'wall_seconds': float(time.monotonic() - started),
    }
    if winner is not None:
        result['winner_metrics'] = variants[winner]
    if not math.isfinite(result['wall_seconds']):
        raise AssertionError('Stage 14E produced non-finite wall time')
    print('STAGE14E_JSON=' + json.dumps(result, sort_keys=True), flush=True)


if __name__ == '__main__':
    main()
