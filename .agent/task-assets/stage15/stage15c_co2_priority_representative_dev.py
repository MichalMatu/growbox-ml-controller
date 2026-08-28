#!/usr/bin/env python3
"""Stage 15C read-only representative DEV benchmark for deterministic CO2 priority."""

from __future__ import annotations

import json
import math
import time
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass

from tools.ml.climate_benchmark import _status_for_step, _tracking_terms
from tools.ml.climate_input import MeasurementStatus
from tools.ml.climate_policy import (
    ClimateRulePolicy,
    apply_climate_safety,
    arbitrate_climate_action,
    hard_limit_violations,
)
from tools.ml.climate_scenarios import REQUIRED_SCENARIO_FAMILIES, structured_training_episodes
from tools.ml.climate_simulator import CLIMATE_OUTPUT_NAMES, ClimateAction, ClimateSimulator

SEED = 316227
SCENARIOS_PER_FAMILY = 2
STEPS_PER_SCENARIO = 60
SENSOR_TIMEOUT_MS = 30_000
ACTIVE = 0.05
VARIANTS = ("rule", "co2_priority")


@dataclass(frozen=True)
class Metrics:
    steps: int
    tracking_cost: float
    switching_per_step: float
    actuator_effort_per_step: float
    co2_enabled_usable_steps: int
    co2_mae_ppm: float
    overlap_fraction: float
    overlap_fraction_on_co2_enabled_usable: float
    vent_loss_proxy_per_co2_enabled_usable_step: float
    arbitration_intervention_fraction: float
    safety_intervention_fraction: float
    hard_limit_violation_fraction: float


def _usable(status, name: str, value: float) -> bool:
    return status.get(name, MeasurementStatus()).usable(value, SENSOR_TIMEOUT_MS)


def _couple(action: ClimateAction, variant: str) -> ClimateAction:
    values = action.clipped().as_dict()
    if variant == "co2_priority" and values["co2_doser"] > ACTIVE and values["exhaust_fan"] > ACTIVE:
        values["exhaust_fan"] = 0.0
    elif variant != "rule":
        raise ValueError(variant)
    return ClimateAction.from_mapping(values).clipped()


def _run(variant: str, episodes):
    policy = ClimateRulePolicy()
    totals = defaultdict(float)
    family_totals = {family: defaultdict(float) for family in REQUIRED_SCENARIO_FAMILIES}
    arbitration_reasons: Counter[str] = Counter()
    safety_reasons: Counter[str] = Counter()

    for episode in episodes:
        simulator = ClimateSimulator(episode.scenario)
        previous_applied = ClimateAction()
        fam = family_totals[episode.family]
        for step in range(STEPS_PER_SCENARIO):
            profile = episode.profile_for_step(step, STEPS_PER_SCENARIO)
            simulator.set_light_level(profile.light_level)
            state = simulator.observe(add_sensor_noise=False)
            status = _status_for_step(episode, step, STEPS_PER_SCENARIO)
            tracking_cost, *_ = _tracking_terms(state, profile, status, SENSOR_TIMEOUT_MS)
            hard = int(bool(hard_limit_violations(state)))
            totals["tracking"] += float(tracking_cost)
            totals["hard"] += hard
            fam["tracking"] += float(tracking_cost)
            fam["hard"] += hard

            raw = policy.choose(
                simulator.scenario,
                state,
                profile,
                status=status,
                sensor_timeout_ms=SENSOR_TIMEOUT_MS,
            )
            raw = _couple(raw, variant)
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
                fam["arbitration"] += 1
                arbitration_reasons.update(arbitration.interventions)
            if safety.interventions:
                totals["safety"] += 1
                fam["safety"] += 1
                safety_reasons.update(safety.interventions)

            current = applied.as_tuple()
            previous = previous_applied.as_tuple()
            switching = sum(abs(a - b) for a, b in zip(current, previous, strict=True)) / len(CLIMATE_OUTPUT_NAMES)
            effort = sum(current) / len(CLIMATE_OUTPUT_NAMES)
            totals["switching"] += switching
            totals["effort"] += effort
            fam["switching"] += switching
            fam["effort"] += effort

            overlap = applied.co2_doser > ACTIVE and applied.exhaust_fan > ACTIVE
            strength = applied.co2_doser * applied.exhaust_fan
            totals["overlap"] += int(overlap)
            fam["overlap"] += int(overlap)

            co2_enabled_usable = profile.targets.co2_enabled and _usable(status, "co2_ppm", state.co2_ppm)
            if co2_enabled_usable:
                co2_error = abs(state.co2_ppm - profile.targets.co2_ppm)
                totals["co2_enabled_usable"] += 1
                totals["co2_abs_error"] += co2_error
                totals["overlap_co2_enabled"] += int(overlap)
                totals["vent_loss"] += strength
                fam["co2_enabled_usable"] += 1
                fam["co2_abs_error"] += co2_error
                fam["overlap_co2_enabled"] += int(overlap)
                fam["vent_loss"] += strength

            simulator.step(applied, add_sensor_noise=False, light_level=profile.light_level)
            previous_applied = applied
            totals["steps"] += 1
            fam["steps"] += 1

    steps = int(totals["steps"])
    co2_steps = int(totals["co2_enabled_usable"])
    metrics = Metrics(
        steps=steps,
        tracking_cost=totals["tracking"] / steps,
        switching_per_step=totals["switching"] / steps,
        actuator_effort_per_step=totals["effort"] / steps,
        co2_enabled_usable_steps=co2_steps,
        co2_mae_ppm=totals["co2_abs_error"] / co2_steps if co2_steps else 0.0,
        overlap_fraction=totals["overlap"] / steps,
        overlap_fraction_on_co2_enabled_usable=totals["overlap_co2_enabled"] / co2_steps if co2_steps else 0.0,
        vent_loss_proxy_per_co2_enabled_usable_step=totals["vent_loss"] / co2_steps if co2_steps else 0.0,
        arbitration_intervention_fraction=totals["arbitration"] / steps,
        safety_intervention_fraction=totals["safety"] / steps,
        hard_limit_violation_fraction=totals["hard"] / steps,
    )

    families = {}
    for family, fam in family_totals.items():
        fsteps = int(fam["steps"])
        fco2 = int(fam["co2_enabled_usable"])
        families[family] = {
            "steps": fsteps,
            "tracking_cost": fam["tracking"] / fsteps,
            "switching_per_step": fam["switching"] / fsteps,
            "co2_mae_ppm": fam["co2_abs_error"] / fco2 if fco2 else 0.0,
            "overlap_fraction": fam["overlap"] / fsteps,
            "overlap_fraction_on_co2_enabled_usable": fam["overlap_co2_enabled"] / fco2 if fco2 else 0.0,
            "vent_loss_proxy_per_co2_enabled_usable_step": fam["vent_loss"] / fco2 if fco2 else 0.0,
            "arbitration_intervention_fraction": fam["arbitration"] / fsteps,
            "safety_intervention_fraction": fam["safety"] / fsteps,
            "hard_limit_violation_fraction": fam["hard"] / fsteps,
        }
    return metrics, families, dict(arbitration_reasons), dict(safety_reasons)


def main() -> None:
    started = time.monotonic()
    episodes = structured_training_episodes(scenarios_per_family=SCENARIOS_PER_FAMILY, seed=SEED)
    expected = len(REQUIRED_SCENARIO_FAMILIES) * SCENARIOS_PER_FAMILY
    if len(episodes) != expected:
        raise AssertionError(f"unexpected Stage 15C episode count: {len(episodes)} != {expected}")

    results = {}
    for variant in VARIANTS:
        metrics, families, arbitration_reasons, safety_reasons = _run(variant, episodes)
        results[variant] = {
            "metrics": asdict(metrics),
            "families": families,
            "arbitration_reasons": arbitration_reasons,
            "safety_reasons": safety_reasons,
        }

    rule = results["rule"]["metrics"]
    candidate = results["co2_priority"]["metrics"]
    comparison = {
        "tracking_improvement_vs_rule_fraction": (rule["tracking_cost"] - candidate["tracking_cost"]) / rule["tracking_cost"],
        "switching_ratio_vs_rule": candidate["switching_per_step"] / rule["switching_per_step"],
        "co2_mae_improvement_vs_rule_fraction": (rule["co2_mae_ppm"] - candidate["co2_mae_ppm"]) / rule["co2_mae_ppm"] if rule["co2_mae_ppm"] else 0.0,
        "overlap_delta_fraction": candidate["overlap_fraction"] - rule["overlap_fraction"],
        "vent_loss_proxy_delta": candidate["vent_loss_proxy_per_co2_enabled_usable_step"] - rule["vent_loss_proxy_per_co2_enabled_usable_step"],
    }
    qualifies = (
        candidate["overlap_fraction"] == 0.0
        and candidate["hard_limit_violation_fraction"] <= rule["hard_limit_violation_fraction"]
        and candidate["safety_intervention_fraction"] <= rule["safety_intervention_fraction"]
        and candidate["arbitration_intervention_fraction"] <= rule["arbitration_intervention_fraction"]
        and candidate["tracking_cost"] <= rule["tracking_cost"] * 1.001
        and candidate["switching_per_step"] <= rule["switching_per_step"] * 1.02
        and candidate["co2_mae_ppm"] <= rule["co2_mae_ppm"] * 1.01
    )

    output = {
        "experiment": "stage15c_co2_priority_representative_dev",
        "seed": SEED,
        "scenarios_per_family": SCENARIOS_PER_FAMILY,
        "steps_per_scenario": STEPS_PER_SCENARIO,
        "families": list(REQUIRED_SCENARIO_FAMILIES),
        "variants": results,
        "comparison": comparison,
        "candidate_qualifies": bool(qualifies),
        "reserved_stage14ab_test_split_evaluated": False,
        "wall_seconds": float(time.monotonic() - started),
    }
    if not math.isfinite(output["wall_seconds"]):
        raise AssertionError("Stage 15C produced non-finite wall time")
    print("STAGE15C_JSON=" + json.dumps(output, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
