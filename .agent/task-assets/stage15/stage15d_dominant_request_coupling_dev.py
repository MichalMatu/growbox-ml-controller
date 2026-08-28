#!/usr/bin/env python3
"""Stage 15D read-only representative DEV audit for dominant CO2/exhaust coupling."""

from __future__ import annotations

import importlib.util
import json
import math
import sys
import time
from dataclasses import asdict
from pathlib import Path

from tools.ml.climate_scenarios import REQUIRED_SCENARIO_FAMILIES, structured_training_episodes
from tools.ml.climate_simulator import ClimateAction

BASE_PATH = Path('/tmp/stage15c-co2-priority-representative-dev.py')
spec = importlib.util.spec_from_file_location('stage15c_base', BASE_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError('cannot load Stage 15C base')
base = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = base
spec.loader.exec_module(base)

VARIANT = 'dominant_priority'


def _dominant_couple(action: ClimateAction, variant: str) -> ClimateAction:
    values = action.clipped().as_dict()
    if variant == 'rule':
        return action.clipped()
    if variant != VARIANT:
        raise ValueError(variant)
    if values['co2_doser'] > base.ACTIVE and values['exhaust_fan'] > base.ACTIVE:
        if values['co2_doser'] >= values['exhaust_fan']:
            values['exhaust_fan'] = 0.0
        else:
            values['co2_doser'] = 0.0
    return ClimateAction.from_mapping(values).clipped()


def main() -> None:
    started = time.monotonic()
    # Repair the Stage 15C helper locally and replace it with the frozen dominant-request rule.
    base._couple = _dominant_couple
    episodes = structured_training_episodes(
        scenarios_per_family=base.SCENARIOS_PER_FAMILY,
        seed=base.SEED,
    )
    expected = len(REQUIRED_SCENARIO_FAMILIES) * base.SCENARIOS_PER_FAMILY
    if len(episodes) != expected:
        raise AssertionError(f'unexpected Stage 15D episode count: {len(episodes)} != {expected}')

    rule_metrics, rule_families, rule_arb, rule_safety = base._run('rule', episodes)
    candidate_metrics, candidate_families, candidate_arb, candidate_safety = base._run(
        VARIANT, episodes
    )
    rule = asdict(rule_metrics)
    candidate = asdict(candidate_metrics)
    comparison = {
        'tracking_improvement_vs_rule_fraction': (
            (rule['tracking_cost'] - candidate['tracking_cost']) / rule['tracking_cost']
        ),
        'switching_ratio_vs_rule': (
            candidate['switching_per_step'] / rule['switching_per_step']
        ),
        'co2_mae_improvement_vs_rule_fraction': (
            (rule['co2_mae_ppm'] - candidate['co2_mae_ppm']) / rule['co2_mae_ppm']
            if rule['co2_mae_ppm'] else 0.0
        ),
        'overlap_delta_fraction': candidate['overlap_fraction'] - rule['overlap_fraction'],
        'vent_loss_proxy_delta': (
            candidate['vent_loss_proxy_per_co2_enabled_usable_step']
            - rule['vent_loss_proxy_per_co2_enabled_usable_step']
        ),
    }
    qualifies = (
        candidate['overlap_fraction'] == 0.0
        and candidate['hard_limit_violation_fraction'] <= rule['hard_limit_violation_fraction']
        and candidate['safety_intervention_fraction'] <= rule['safety_intervention_fraction']
        and candidate['arbitration_intervention_fraction'] <= rule['arbitration_intervention_fraction']
        and candidate['tracking_cost'] <= rule['tracking_cost'] * 1.001
        and candidate['switching_per_step'] <= rule['switching_per_step'] * 1.02
        and candidate['co2_mae_ppm'] <= rule['co2_mae_ppm'] * 1.01
    )

    per_family = {}
    for family in REQUIRED_SCENARIO_FAMILIES:
        r = rule_families[family]
        c = candidate_families[family]
        per_family[family] = {
            'tracking_delta': c['tracking_cost'] - r['tracking_cost'],
            'switching_delta': c['switching_per_step'] - r['switching_per_step'],
            'co2_mae_delta_ppm': c['co2_mae_ppm'] - r['co2_mae_ppm'],
            'rule_overlap_fraction': r['overlap_fraction'],
            'candidate_overlap_fraction': c['overlap_fraction'],
        }

    output = {
        'experiment': 'stage15d_dominant_request_coupling_dev',
        'seed': base.SEED,
        'scenarios_per_family': base.SCENARIOS_PER_FAMILY,
        'steps_per_scenario': base.STEPS_PER_SCENARIO,
        'variant': VARIANT,
        'rule_metrics': rule,
        'candidate_metrics': candidate,
        'comparison': comparison,
        'candidate_qualifies': bool(qualifies),
        'per_family': per_family,
        'rule_arbitration_reasons': rule_arb,
        'rule_safety_reasons': rule_safety,
        'candidate_arbitration_reasons': candidate_arb,
        'candidate_safety_reasons': candidate_safety,
        'reserved_stage14ab_test_split_evaluated': False,
        'wall_seconds': float(time.monotonic() - started),
    }
    if not math.isfinite(output['wall_seconds']):
        raise AssertionError('Stage 15D produced non-finite wall time')
    print('STAGE15D_JSON=' + json.dumps(output, sort_keys=True), flush=True)


if __name__ == '__main__':
    main()
