#!/usr/bin/env python3
"""Stage 15A read-only CO2/exhaust coupling audit for Rule vs Sequence Teacher."""

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
from tools.ml.climate_scenarios import structured_training_episodes
from tools.ml.climate_sequence_teacher import ClimateSequenceRolloutTeacher
from tools.ml.climate_simulator import CLIMATE_OUTPUT_NAMES, ClimateAction, ClimateSimulator

SEED = 244949
SCENARIOS_PER_FAMILY = 1
STEPS_PER_SCENARIO = 24
SENSOR_TIMEOUT_MS = 30_000
ACTIVE = 0.05
FAMILIES = (
    "co2_enrichment",
    "co2_unavailable",
    "outside_helpful",
    "outside_harmful",
    "hot_cooling",
    "day_light_load",
)


@dataclass(frozen=True)
class Metrics:
    steps: int
    tracking_cost: float
    switching_per_step: float
    actuator_effort_per_step: float
    co2_enabled_usable_steps: int
    co2_mae_ppm: float
    co2_dose_active_fraction: float
    exhaust_active_fraction: float
    overlap_fraction: float
    overlap_fraction_on_co2_enabled_usable: float
    overlap_strength_per_step: float
    vent_loss_proxy_per_co2_enabled_usable_step: float
    mean_co2_doser: float
    mean_exhaust_fan: float
    arbitration_intervention_fraction: float
    safety_intervention_fraction: float
    hard_limit_violation_fraction: float
    teacher_evaluations_per_step: float
    teacher_safe_fallback_fraction: float


def _usable(status, name: str, value: float) -> bool:
    return status.get(name, MeasurementStatus()).usable(value, SENSOR_TIMEOUT_MS)


def _run(policy_name: str, episodes):
    rule = ClimateRulePolicy()
    teacher = ClimateSequenceRolloutTeacher()
    totals = defaultdict(float)
    arbitration_reasons: Counter[str] = Counter()
    safety_reasons: Counter[str] = Counter()
    family_totals: dict[str, defaultdict[str, float]] = {
        family: defaultdict(float) for family in FAMILIES
    }

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
            totals["tracking"] += float(tracking_cost)
            fam["tracking"] += float(tracking_cost)
            hard = int(bool(hard_limit_violations(state)))
            totals["hard"] += hard
            fam["hard"] += hard

            if policy_name == "rule":
                raw = rule.choose(
                    simulator.scenario,
                    state,
                    profile,
                    status=status,
                    sensor_timeout_ms=SENSOR_TIMEOUT_MS,
                )
                evaluations = 0
                safe_fallback = False
            elif policy_name == "sequence":
                result = teacher.choose(
                    simulator,
                    profile.targets,
                    humidity_control_mode=profile.humidity_control_mode,
                    status=status,
                    sensor_timeout_ms=SENSOR_TIMEOUT_MS,
                )
                raw = result.action
                evaluations = int(result.evaluations)
                safe_fallback = bool(result.safe_fallback)
            else:
                raise ValueError(policy_name)

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

            values = applied.as_tuple()
            totals["switching"] += sum(
                abs(a - b)
                for a, b in zip(values, previous_applied.as_tuple(), strict=True)
            ) / len(CLIMATE_OUTPUT_NAMES)
            totals["effort"] += sum(values) / len(CLIMATE_OUTPUT_NAMES)
            fam["switching"] += sum(
                abs(a - b)
                for a, b in zip(values, previous_applied.as_tuple(), strict=True)
            ) / len(CLIMATE_OUTPUT_NAMES)
            fam["effort"] += sum(values) / len(CLIMATE_OUTPUT_NAMES)

            dose_active = applied.co2_doser > ACTIVE
            exhaust_active = applied.exhaust_fan > ACTIVE
            overlap = dose_active and exhaust_active
            overlap_strength = applied.co2_doser * applied.exhaust_fan
            totals["dose_active"] += int(dose_active)
            totals["exhaust_active"] += int(exhaust_active)
            totals["overlap"] += int(overlap)
            totals["overlap_strength"] += overlap_strength
            totals["co2_doser"] += applied.co2_doser
            totals["exhaust_fan"] += applied.exhaust_fan
            fam["dose_active"] += int(dose_active)
            fam["exhaust_active"] += int(exhaust_active)
            fam["overlap"] += int(overlap)
            fam["overlap_strength"] += overlap_strength
            fam["co2_doser"] += applied.co2_doser
            fam["exhaust_fan"] += applied.exhaust_fan

            co2_enabled_usable = (
                profile.targets.co2_enabled
                and _usable(status, "co2_ppm", state.co2_ppm)
            )
            if co2_enabled_usable:
                co2_error = abs(state.co2_ppm - profile.targets.co2_ppm)
                totals["co2_enabled_usable"] += 1
                totals["co2_abs_error"] += co2_error
                totals["overlap_co2_enabled"] += int(overlap)
                totals["vent_loss_proxy_co2_enabled"] += overlap_strength
                fam["co2_enabled_usable"] += 1
                fam["co2_abs_error"] += co2_error
                fam["overlap_co2_enabled"] += int(overlap)
                fam["vent_loss_proxy_co2_enabled"] += overlap_strength

            totals["teacher_evaluations"] += evaluations
            totals["teacher_safe_fallback"] += int(safe_fallback)
            fam["teacher_evaluations"] += evaluations
            fam["teacher_safe_fallback"] += int(safe_fallback)

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
        co2_mae_ppm=(totals["co2_abs_error"] / co2_steps if co2_steps else 0.0),
        co2_dose_active_fraction=totals["dose_active"] / steps,
        exhaust_active_fraction=totals["exhaust_active"] / steps,
        overlap_fraction=totals["overlap"] / steps,
        overlap_fraction_on_co2_enabled_usable=(
            totals["overlap_co2_enabled"] / co2_steps if co2_steps else 0.0
        ),
        overlap_strength_per_step=totals["overlap_strength"] / steps,
        vent_loss_proxy_per_co2_enabled_usable_step=(
            totals["vent_loss_proxy_co2_enabled"] / co2_steps if co2_steps else 0.0
        ),
        mean_co2_doser=totals["co2_doser"] / steps,
        mean_exhaust_fan=totals["exhaust_fan"] / steps,
        arbitration_intervention_fraction=totals["arbitration"] / steps,
        safety_intervention_fraction=totals["safety"] / steps,
        hard_limit_violation_fraction=totals["hard"] / steps,
        teacher_evaluations_per_step=totals["teacher_evaluations"] / steps,
        teacher_safe_fallback_fraction=totals["teacher_safe_fallback"] / steps,
    )

    by_family = {}
    for family, fam in family_totals.items():
        fsteps = int(fam["steps"])
        fco2 = int(fam["co2_enabled_usable"])
        by_family[family] = {
            "steps": fsteps,
            "tracking_cost": fam["tracking"] / fsteps,
            "switching_per_step": fam["switching"] / fsteps,
            "co2_enabled_usable_steps": fco2,
            "co2_mae_ppm": fam["co2_abs_error"] / fco2 if fco2 else 0.0,
            "co2_dose_active_fraction": fam["dose_active"] / fsteps,
            "exhaust_active_fraction": fam["exhaust_active"] / fsteps,
            "overlap_fraction": fam["overlap"] / fsteps,
            "overlap_fraction_on_co2_enabled_usable": (
                fam["overlap_co2_enabled"] / fco2 if fco2 else 0.0
            ),
            "overlap_strength_per_step": fam["overlap_strength"] / fsteps,
            "vent_loss_proxy_per_co2_enabled_usable_step": (
                fam["vent_loss_proxy_co2_enabled"] / fco2 if fco2 else 0.0
            ),
            "mean_co2_doser": fam["co2_doser"] / fsteps,
            "mean_exhaust_fan": fam["exhaust_fan"] / fsteps,
            "arbitration_intervention_fraction": fam["arbitration"] / fsteps,
            "safety_intervention_fraction": fam["safety"] / fsteps,
            "hard_limit_violation_fraction": fam["hard"] / fsteps,
            "teacher_evaluations_per_step": fam["teacher_evaluations"] / fsteps,
            "teacher_safe_fallback_fraction": fam["teacher_safe_fallback"] / fsteps,
        }

    return metrics, by_family, dict(arbitration_reasons), dict(safety_reasons)


def main() -> None:
    started = time.monotonic()
    all_episodes = structured_training_episodes(
        scenarios_per_family=SCENARIOS_PER_FAMILY,
        seed=SEED,
    )
    episodes = tuple(ep for ep in all_episodes if ep.family in FAMILIES)
    if len(episodes) != len(FAMILIES) * SCENARIOS_PER_FAMILY:
        raise AssertionError(f"unexpected Stage 15A episode count: {len(episodes)}")

    rule, rule_families, rule_arb, rule_safety = _run("rule", episodes)
    sequence, sequence_families, sequence_arb, sequence_safety = _run("sequence", episodes)

    result = {
        "experiment": "stage15a_co2_exhaust_coupling_audit",
        "seed": SEED,
        "scenarios_per_family": SCENARIOS_PER_FAMILY,
        "steps_per_scenario": STEPS_PER_SCENARIO,
        "families": list(FAMILIES),
        "rule_metrics": asdict(rule),
        "sequence_metrics": asdict(sequence),
        "rule_families": rule_families,
        "sequence_families": sequence_families,
        "rule_arbitration_reasons": rule_arb,
        "rule_safety_reasons": rule_safety,
        "sequence_arbitration_reasons": sequence_arb,
        "sequence_safety_reasons": sequence_safety,
        "sequence_tracking_improvement_vs_rule_fraction": (
            (rule.tracking_cost - sequence.tracking_cost) / rule.tracking_cost
            if rule.tracking_cost else 0.0
        ),
        "sequence_switching_ratio_vs_rule": (
            sequence.switching_per_step / rule.switching_per_step
            if rule.switching_per_step else 0.0
        ),
        "sequence_overlap_delta_fraction": sequence.overlap_fraction - rule.overlap_fraction,
        "sequence_vent_loss_proxy_delta": (
            sequence.vent_loss_proxy_per_co2_enabled_usable_step
            - rule.vent_loss_proxy_per_co2_enabled_usable_step
        ),
        "reserved_stage14ab_test_split_evaluated": False,
        "wall_seconds": float(time.monotonic() - started),
    }
    if not math.isfinite(result["wall_seconds"]):
        raise AssertionError("Stage 15A produced non-finite wall time")
    print("STAGE15A_JSON=" + json.dumps(result, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
