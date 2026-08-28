#!/usr/bin/env python3
"""Stage 15B read-only deterministic CO2/exhaust coupling ablation."""

from __future__ import annotations

import importlib.util
import json
import math
import sys
import time
from collections import Counter, defaultdict
from dataclasses import asdict
from pathlib import Path

from tools.ml.climate_benchmark import _status_for_step, _tracking_terms
from tools.ml.climate_policy import ClimateRulePolicy, apply_climate_safety, arbitrate_climate_action, hard_limit_violations
from tools.ml.climate_scenarios import structured_training_episodes
from tools.ml.climate_simulator import CLIMATE_OUTPUT_NAMES, ClimateAction, ClimateSimulator

BASE_PATH = Path('/tmp/stage15a-co2-exhaust-coupling-audit.py')
spec = importlib.util.spec_from_file_location('stage15a_base', BASE_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError('cannot load Stage 15A base')
base = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = base
spec.loader.exec_module(base)

VARIANTS = ('rule', 'exhaust_priority', 'co2_priority', 'sticky_priority')


def _couple(action: ClimateAction, variant: str, previous: ClimateAction) -> ClimateAction:
    values = action.clipped().as_dict()
    if values['co2_doser'] <= base.ACTIVE or values['exhaust_fan'] <= base.ACTIVE:
        return action.clipped()
    if variant == 'exhaust_priority':
        values['co2_doser'] = 0.0
    elif variant == 'co2_priority':
        values['exhaust_fan'] = 0.0
    elif variant == 'sticky_priority':
        if previous.co2_doser > base.ACTIVE and previous.exhaust_fan <= base.ACTIVE:
            values['exhaust_fan'] = 0.0
        elif previous.exhaust_fan > base.ACTIVE and previous.co2_doser <= base.ACTIVE:
            values['co2_doser'] = 0.0
        elif values['co2_doser'] >= values['exhaust_fan']:
            values['exhaust_fan'] = 0.0
        else:
            values['co2_doser'] = 0.0
    elif variant != 'rule':
        raise ValueError(variant)
    return ClimateAction.from_mapping(values).clipped()


def _run_variant(variant: str, episodes):
    rule = ClimateRulePolicy()
    totals = defaultdict(float)
    family_totals = {family: defaultdict(float) for family in base.FAMILIES}
    arbitration_reasons: Counter[str] = Counter()
    safety_reasons: Counter[str] = Counter()

    for episode in episodes:
        simulator = ClimateSimulator(episode.scenario)
        previous_applied = ClimateAction()
        fam = family_totals[episode.family]
        for step in range(base.STEPS_PER_SCENARIO):
            profile = episode.profile_for_step(step, base.STEPS_PER_SCENARIO)
            simulator.set_light_level(profile.light_level)
            state = simulator.observe(add_sensor_noise=False)
            status = _status_for_step(episode, step, base.STEPS_PER_SCENARIO)
            tracking_cost, *_ = _tracking_terms(state, profile, status, base.SENSOR_TIMEOUT_MS)
            totals['tracking'] += float(tracking_cost)
            fam['tracking'] += float(tracking_cost)
            hard = int(bool(hard_limit_violations(state)))
            totals['hard'] += hard
            fam['hard'] += hard

            raw = rule.choose(
                simulator.scenario,
                state,
                profile,
                status=status,
                sensor_timeout_ms=base.SENSOR_TIMEOUT_MS,
            )
            raw = _couple(raw, variant, previous_applied)
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
                fam['arbitration'] += 1
                arbitration_reasons.update(arbitration.interventions)
            if safety.interventions:
                totals['safety'] += 1
                fam['safety'] += 1
                safety_reasons.update(safety.interventions)

            current = applied.as_tuple()
            previous = previous_applied.as_tuple()
            switching = sum(abs(a - b) for a, b in zip(current, previous, strict=True)) / len(CLIMATE_OUTPUT_NAMES)
            totals['switching'] += switching
            fam['switching'] += switching
            totals['effort'] += sum(current) / len(CLIMATE_OUTPUT_NAMES)
            fam['effort'] += sum(current) / len(CLIMATE_OUTPUT_NAMES)

            dose_active = applied.co2_doser > base.ACTIVE
            exhaust_active = applied.exhaust_fan > base.ACTIVE
            overlap = dose_active and exhaust_active
            strength = applied.co2_doser * applied.exhaust_fan
            for target in (totals, fam):
                target['dose_active'] += int(dose_active)
                target['exhaust_active'] += int(exhaust_active)
                target['overlap'] += int(overlap)
                target['overlap_strength'] += strength
                target['co2_doser'] += applied.co2_doser
                target['exhaust_fan'] += applied.exhaust_fan

            co2_enabled_usable = profile.targets.co2_enabled and base._usable(status, 'co2_ppm', state.co2_ppm)
            if co2_enabled_usable:
                co2_error = abs(state.co2_ppm - profile.targets.co2_ppm)
                for target in (totals, fam):
                    target['co2_enabled_usable'] += 1
                    target['co2_abs_error'] += co2_error
                    target['overlap_co2_enabled'] += int(overlap)
                    target['vent_loss_proxy_co2_enabled'] += strength

            simulator.step(applied, add_sensor_noise=False, light_level=profile.light_level)
            previous_applied = applied
            totals['steps'] += 1
            fam['steps'] += 1

    steps = int(totals['steps'])
    co2_steps = int(totals['co2_enabled_usable'])
    metrics = base.Metrics(
        steps=steps,
        tracking_cost=totals['tracking'] / steps,
        switching_per_step=totals['switching'] / steps,
        actuator_effort_per_step=totals['effort'] / steps,
        co2_enabled_usable_steps=co2_steps,
        co2_mae_ppm=totals['co2_abs_error'] / co2_steps if co2_steps else 0.0,
        co2_dose_active_fraction=totals['dose_active'] / steps,
        exhaust_active_fraction=totals['exhaust_active'] / steps,
        overlap_fraction=totals['overlap'] / steps,
        overlap_fraction_on_co2_enabled_usable=totals['overlap_co2_enabled'] / co2_steps if co2_steps else 0.0,
        overlap_strength_per_step=totals['overlap_strength'] / steps,
        vent_loss_proxy_per_co2_enabled_usable_step=totals['vent_loss_proxy_co2_enabled'] / co2_steps if co2_steps else 0.0,
        mean_co2_doser=totals['co2_doser'] / steps,
        mean_exhaust_fan=totals['exhaust_fan'] / steps,
        arbitration_intervention_fraction=totals['arbitration'] / steps,
        safety_intervention_fraction=totals['safety'] / steps,
        hard_limit_violation_fraction=totals['hard'] / steps,
        teacher_evaluations_per_step=0.0,
        teacher_safe_fallback_fraction=0.0,
    )

    by_family = {}
    for family, fam in family_totals.items():
        fsteps = int(fam['steps'])
        fco2 = int(fam['co2_enabled_usable'])
        by_family[family] = {
            'tracking_cost': fam['tracking'] / fsteps,
            'switching_per_step': fam['switching'] / fsteps,
            'co2_mae_ppm': fam['co2_abs_error'] / fco2 if fco2 else 0.0,
            'overlap_fraction': fam['overlap'] / fsteps,
            'overlap_fraction_on_co2_enabled_usable': fam['overlap_co2_enabled'] / fco2 if fco2 else 0.0,
            'vent_loss_proxy_per_co2_enabled_usable_step': fam['vent_loss_proxy_co2_enabled'] / fco2 if fco2 else 0.0,
            'hard_limit_violation_fraction': fam['hard'] / fsteps,
            'safety_intervention_fraction': fam['safety'] / fsteps,
            'arbitration_intervention_fraction': fam['arbitration'] / fsteps,
        }
    return metrics, by_family, dict(arbitration_reasons), dict(safety_reasons)


def main() -> None:
    started = time.monotonic()
    episodes = tuple(
        ep for ep in structured_training_episodes(scenarios_per_family=base.SCENARIOS_PER_FAMILY, seed=base.SEED)
        if ep.family in base.FAMILIES
    )
    if len(episodes) != len(base.FAMILIES) * base.SCENARIOS_PER_FAMILY:
        raise AssertionError(f'unexpected Stage 15B episode count: {len(episodes)}')

    results = {}
    for variant in VARIANTS:
        metrics, families, arbitration_reasons, safety_reasons = _run_variant(variant, episodes)
        results[variant] = {
            'metrics': asdict(metrics),
            'families': families,
            'arbitration_reasons': arbitration_reasons,
            'safety_reasons': safety_reasons,
        }

    rule = results['rule']['metrics']
    comparisons = {}
    for variant in VARIANTS[1:]:
        metrics = results[variant]['metrics']
        comparisons[variant] = {
            'tracking_improvement_vs_rule_fraction': (rule['tracking_cost'] - metrics['tracking_cost']) / rule['tracking_cost'],
            'switching_ratio_vs_rule': metrics['switching_per_step'] / rule['switching_per_step'],
            'co2_mae_improvement_vs_rule_fraction': (rule['co2_mae_ppm'] - metrics['co2_mae_ppm']) / rule['co2_mae_ppm'],
            'overlap_delta_fraction': metrics['overlap_fraction'] - rule['overlap_fraction'],
            'vent_loss_proxy_delta': metrics['vent_loss_proxy_per_co2_enabled_usable_step'] - rule['vent_loss_proxy_per_co2_enabled_usable_step'],
        }

    eligible = [
        variant for variant in VARIANTS[1:]
        if results[variant]['metrics']['hard_limit_violation_fraction'] == 0.0
        and results[variant]['metrics']['safety_intervention_fraction'] == 0.0
        and results[variant]['metrics']['arbitration_intervention_fraction'] == 0.0
        and results[variant]['metrics']['overlap_fraction'] == 0.0
    ]
    winner = min(
        eligible,
        key=lambda variant: (
            results[variant]['metrics']['tracking_cost'],
            results[variant]['metrics']['switching_per_step'],
        ),
    ) if eligible else None

    output = {
        'experiment': 'stage15b_deterministic_coupling_ablation',
        'seed': base.SEED,
        'scenarios_per_family': base.SCENARIOS_PER_FAMILY,
        'steps_per_scenario': base.STEPS_PER_SCENARIO,
        'families': list(base.FAMILIES),
        'variants': results,
        'comparisons': comparisons,
        'eligible_zero_intervention_zero_overlap_variants': eligible,
        'winner': winner,
        'reserved_stage14ab_test_split_evaluated': False,
        'wall_seconds': float(time.monotonic() - started),
    }
    if not math.isfinite(output['wall_seconds']):
        raise AssertionError('Stage 15B produced non-finite wall time')
    print('STAGE15B_JSON=' + json.dumps(output, sort_keys=True), flush=True)


if __name__ == '__main__':
    main()
