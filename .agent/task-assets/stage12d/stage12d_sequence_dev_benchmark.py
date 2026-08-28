from __future__ import annotations

import argparse
import json
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

from tools.ml.climate_benchmark import _raw_opposition, _tracking_terms
from tools.ml.climate_policy import (
    ClimateRulePolicy,
    apply_climate_safety,
    arbitrate_climate_action,
    hard_limit_violations,
)
from tools.ml.climate_scenarios import structured_training_episodes
from tools.ml.climate_sequence_teacher import ClimateSequenceRolloutTeacher
from tools.ml.climate_simulator import CLIMATE_OUTPUT_NAMES, ClimateAction, ClimateSimulator

POLICIES = ("rule", "sequence_teacher")


def run_episode(policy: str, episode, steps: int, sensor_timeout_ms: int) -> dict[str, object]:
    started = time.perf_counter()
    simulator = ClimateSimulator(episode.scenario)
    rule = ClimateRulePolicy()
    sequence = ClimateSequenceRolloutTeacher()
    previous_applied = ClimateAction()

    tracking_sum = 0.0
    outside_steps = 0
    temp_sum = 0.0
    rh_sum = 0.0
    rh_steps = 0
    vpd_sum = 0.0
    vpd_steps = 0
    co2_sum = 0.0
    co2_steps = 0
    switching_sum = 0.0
    effort_sum = 0.0
    co2_seconds = 0.0
    arbitration_steps = 0
    safety_steps = 0
    hard_steps = 0
    raw_opposition_steps = 0
    sequence_evaluations = 0

    for step in range(steps):
        profile = episode.profile_for_step(step, steps)
        simulator.set_light_level(profile.light_level)
        state = simulator.observe(add_sensor_noise=False)
        status = episode.forced_status_for_step(step, steps)
        tracking, outside, temp_error, rh_error, vpd_error, co2_error = _tracking_terms(
            state, profile, status, sensor_timeout_ms
        )
        tracking_sum += tracking
        outside_steps += int(outside)
        temp_sum += temp_error
        if rh_error is not None:
            rh_sum += rh_error
            rh_steps += 1
        if vpd_error is not None:
            vpd_sum += vpd_error
            vpd_steps += 1
        if co2_error is not None:
            co2_sum += co2_error
            co2_steps += 1
        hard_steps += int(bool(hard_limit_violations(state)))

        if policy == "rule":
            raw = rule.choose(
                simulator.scenario,
                state,
                profile,
                status=status,
                sensor_timeout_ms=sensor_timeout_ms,
            )
        elif policy == "sequence_teacher":
            choice = sequence.choose(
                simulator,
                profile.targets,
                humidity_control_mode=profile.humidity_control_mode,
                status=status,
                sensor_timeout_ms=sensor_timeout_ms,
            )
            raw = choice.action
            sequence_evaluations += choice.evaluations
        else:
            raise ValueError(f"unsupported policy: {policy}")

        raw_opposition_steps += int(_raw_opposition(raw))
        arbitration = arbitrate_climate_action(raw, simulator.scenario)
        arbitration_steps += int(bool(arbitration.interventions))
        safety = apply_climate_safety(
            arbitration.action,
            simulator.scenario,
            state,
            profile,
            status=status,
            sensor_timeout_ms=sensor_timeout_ms,
        )
        safety_steps += int(bool(safety.interventions))
        applied = safety.action
        switching_sum += sum(
            abs(a - b)
            for a, b in zip(applied.as_tuple(), previous_applied.as_tuple(), strict=True)
        ) / len(CLIMATE_OUTPUT_NAMES)
        effort_sum += sum(applied.as_tuple()) / len(CLIMATE_OUTPUT_NAMES)
        co2_seconds += applied.co2_doser * simulator.scenario.timestep_s
        simulator.step(applied, add_sensor_noise=False, light_level=profile.light_level)
        previous_applied = applied

    return {
        "policy": policy,
        "family": episode.family,
        "scenario_id": episode.scenario.scenario_id,
        "steps": steps,
        "tracking_cost": tracking_sum / steps,
        "outside_deadband_fraction": outside_steps / steps,
        "temperature_mae_c": temp_sum / steps,
        "rh_mae_pct": rh_sum / rh_steps if rh_steps else 0.0,
        "rh_steps": rh_steps,
        "vpd_mae_kpa": vpd_sum / vpd_steps if vpd_steps else 0.0,
        "vpd_steps": vpd_steps,
        "co2_mae_ppm": co2_sum / co2_steps if co2_steps else 0.0,
        "co2_steps": co2_steps,
        "switching_per_step": switching_sum / steps,
        "actuator_effort_per_step": effort_sum / steps,
        "co2_dose_command_seconds": co2_seconds,
        "arbitration_intervention_fraction": arbitration_steps / steps,
        "safety_intervention_fraction": safety_steps / steps,
        "hard_limit_violation_fraction": hard_steps / steps,
        "raw_opposition_fraction": raw_opposition_steps / steps,
        "sequence_evaluations_per_step": sequence_evaluations / steps if policy == "sequence_teacher" else 0.0,
        "wall_seconds": time.perf_counter() - started,
    }


def aggregate(selected: list[dict[str, object]]) -> dict[str, object]:
    total_steps = sum(int(item["steps"]) for item in selected)
    rh_steps = sum(int(item["rh_steps"]) for item in selected)
    vpd_steps = sum(int(item["vpd_steps"]) for item in selected)
    co2_steps = sum(int(item["co2_steps"]) for item in selected)

    def weighted(name: str) -> float:
        return sum(float(item[name]) * int(item["steps"]) for item in selected) / total_steps

    return {
        "episodes": len(selected),
        "steps": total_steps,
        "tracking_cost": weighted("tracking_cost"),
        "outside_deadband_fraction": weighted("outside_deadband_fraction"),
        "temperature_mae_c": weighted("temperature_mae_c"),
        "rh_mae_pct": sum(float(item["rh_mae_pct"]) * int(item["rh_steps"]) for item in selected) / rh_steps if rh_steps else 0.0,
        "vpd_mae_kpa": sum(float(item["vpd_mae_kpa"]) * int(item["vpd_steps"]) for item in selected) / vpd_steps if vpd_steps else 0.0,
        "co2_mae_ppm": sum(float(item["co2_mae_ppm"]) * int(item["co2_steps"]) for item in selected) / co2_steps if co2_steps else 0.0,
        "switching_per_step": weighted("switching_per_step"),
        "actuator_effort_per_step": weighted("actuator_effort_per_step"),
        "co2_dose_command_seconds_per_episode": sum(float(item["co2_dose_command_seconds"]) for item in selected) / len(selected),
        "arbitration_intervention_fraction": weighted("arbitration_intervention_fraction"),
        "safety_intervention_fraction": weighted("safety_intervention_fraction"),
        "hard_limit_violation_fraction": weighted("hard_limit_violation_fraction"),
        "raw_opposition_fraction": weighted("raw_opposition_fraction"),
        "sequence_evaluations_per_step": weighted("sequence_evaluations_per_step"),
        "wall_seconds_sum": sum(float(item["wall_seconds"]) for item in selected),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--scenarios-per-family", type=int, default=2)
    parser.add_argument("--steps", type=int, default=60)
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--sensor-timeout-ms", type=int, default=30_000)
    args = parser.parse_args()

    episodes = structured_training_episodes(
        scenarios_per_family=args.scenarios_per_family,
        seed=args.seed,
    )
    work = [(policy, episode) for episode in episodes for policy in POLICIES]
    results: list[dict[str, object]] = []
    started = time.perf_counter()

    with ProcessPoolExecutor(max_workers=min(args.workers, len(work))) as executor:
        futures = {
            executor.submit(run_episode, policy, episode, args.steps, args.sensor_timeout_ms): (policy, episode.family)
            for policy, episode in work
        }
        for future in as_completed(futures):
            policy, family = futures[future]
            result = future.result()
            results.append(result)
            print(
                f"done policy={policy} family={family} tracking={result['tracking_cost']:.6f} "
                f"switching={result['switching_per_step']:.6f} wall={result['wall_seconds']:.2f}s",
                flush=True,
            )

    results.sort(key=lambda item: (str(item["family"]), str(item["scenario_id"]), str(item["policy"])))
    aggregate_all = {
        policy: aggregate([item for item in results if item["policy"] == policy])
        for policy in POLICIES
    }
    families = {
        family: {
            policy: aggregate(
                [item for item in results if item["family"] == family and item["policy"] == policy]
            )
            for policy in POLICIES
        }
        for family in sorted({str(item["family"]) for item in results})
    }

    rule = aggregate_all["rule"]
    sequence = aggregate_all["sequence_teacher"]
    tracking_gate = float(rule["tracking_cost"]) * 0.98
    outside_gate = float(rule["outside_deadband_fraction"]) + 0.03
    switching_gate = float(rule["switching_per_step"]) * 1.75 + 0.02
    safety_gate = float(rule["safety_intervention_fraction"]) + 0.02
    reasons: list[str] = []
    if float(sequence["hard_limit_violation_fraction"]) > 0.0:
        reasons.append("sequence teacher produced hard-limit violations")
    if float(sequence["tracking_cost"]) > tracking_gate:
        reasons.append("sequence teacher did not improve tracking by at least 2% versus rule")
    if float(sequence["outside_deadband_fraction"]) > outside_gate:
        reasons.append("sequence teacher spends materially more time outside target deadbands")
    if float(sequence["switching_per_step"]) > switching_gate:
        reasons.append("sequence teacher switching is materially higher than rule baseline")
    if float(sequence["safety_intervention_fraction"]) > safety_gate:
        reasons.append("sequence teacher needs materially more safety intervention than rule baseline")

    sequence["tracking_improvement_vs_rule_pct"] = 100.0 * (
        float(rule["tracking_cost"]) - float(sequence["tracking_cost"])
    ) / float(rule["tracking_cost"])
    report = {
        "experiment": "stage12d_sequence_teacher_development_benchmark",
        "config": vars(args),
        "gates": {
            "tracking_rule_x_0_98": tracking_gate,
            "outside_rule_plus_0_03": outside_gate,
            "switching_rule_x_1_75_plus_0_02": switching_gate,
            "safety_rule_plus_0_02": safety_gate,
            "hard_limit_max": 0.0,
        },
        "verdict": {"accepted": not reasons, "reasons": reasons},
        "aggregate": aggregate_all,
        "families": families,
        "episodes": results,
        "wall_seconds": time.perf_counter() - started,
    }
    print("STAGE12D_JSON=" + json.dumps(report, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
