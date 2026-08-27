from __future__ import annotations

import argparse
import json
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import replace
from typing import Mapping

from tools.ml.climate_benchmark import _tracking_terms
from tools.ml.climate_input import DEFAULT_SENSOR_TIMEOUT_MS, ClimateTargets, HumidityControlMode, MeasurementStatus
from tools.ml.climate_policy import ClimateRulePolicy, apply_climate_safety, arbitrate_climate_action, hard_limit_violations
from tools.ml.climate_scenarios import structured_training_episodes
from tools.ml.climate_sequence_teacher import (
    ClimateSequenceRolloutTeacher,
    ClimateSequenceTeacherConfig,
    ClimateSequenceTeacherResult,
)
from tools.ml.climate_simulator import CLIMATE_OUTPUT_NAMES, ClimateAction, ClimateSimulator

TOLERANCES = (0.0, 0.001, 0.0025, 0.005)
GROUPS = ("temperature", "humidity", "exhaust", "co2")


def _plan_delta_u(plan: tuple[ClimateAction, ...], previous: ClimateAction) -> float:
    total = 0.0
    before = previous.clipped()
    for action in plan:
        command = action.clipped()
        total += sum(abs(now - old) for now, old in zip(command.as_tuple(), before.as_tuple(), strict=True))
        before = command
    return total / len(CLIMATE_OUTPUT_NAMES)


class SmoothedSequenceTeacher:
    """Post-process the best tracking plan inside a fixed relative tracking band."""

    def __init__(self, tolerance_fraction: float) -> None:
        if tolerance_fraction < 0.0:
            raise ValueError("tolerance_fraction must be non-negative")
        self.tolerance_fraction = float(tolerance_fraction)
        self.base = ClimateSequenceRolloutTeacher(
            config=ClimateSequenceTeacherConfig(primary_tolerance=0.0)
        )

    def choose(
        self,
        simulator: ClimateSimulator,
        targets: ClimateTargets,
        *,
        humidity_control_mode: HumidityControlMode = "RH",
        status: Mapping[str, MeasurementStatus] | None = None,
        sensor_timeout_ms: int = DEFAULT_SENSOR_TIMEOUT_MS,
    ) -> ClimateSequenceTeacherResult:
        result = self.base.choose(
            simulator,
            targets,
            humidity_control_mode=humidity_control_mode,
            status=status,
            sensor_timeout_ms=sensor_timeout_ms,
        )
        if result.safe_fallback or self.tolerance_fraction <= 0.0:
            return result

        statuses = status or {}
        timeout = int(sensor_timeout_ms)
        state = simulator.state
        outside_usable = self.base._status_usable(
            "outside_temperature_c", state.outside_temperature_c, statuses, timeout
        ) and self.base._status_usable(
            "outside_humidity_pct", state.outside_humidity_pct, statuses, timeout
        )
        co2_usable = self.base._status_usable("co2_ppm", state.co2_ppm, statuses, timeout)
        allow_co2 = targets.co2_enabled and co2_usable

        tracking_anchor = result.tracking_cost
        tracking_limit = tracking_anchor * (1.0 + self.tolerance_fraction)
        selected_plan = result.plan
        selected_tracking = result.tracking_cost
        selected_secondary = result.secondary_cost
        selected_delta_u = _plan_delta_u(selected_plan, simulator.previous_command)
        evaluations = result.evaluations

        for block_index in range(len(selected_plan)):
            for group in GROUPS:
                current_action = selected_plan[block_index]
                for candidate_action in self.base._group_options(
                    simulator,
                    current_action,
                    group=group,
                    outside_usable=outside_usable,
                    allow_co2=allow_co2,
                ):
                    if candidate_action == current_action:
                        continue
                    candidate_plan_list = list(selected_plan)
                    candidate_plan_list[block_index] = candidate_action
                    candidate_plan = tuple(candidate_plan_list)
                    tracking, secondary = self.base.evaluate_plan(
                        simulator,
                        candidate_plan,
                        targets,
                        humidity_control_mode=humidity_control_mode,
                        co2_usable=co2_usable,
                    )
                    evaluations += 1
                    if tracking > tracking_limit + 1.0e-12:
                        continue
                    delta_u = _plan_delta_u(candidate_plan, simulator.previous_command)
                    if delta_u < selected_delta_u - 1.0e-12 or (
                        abs(delta_u - selected_delta_u) <= 1.0e-12
                        and secondary < selected_secondary - 1.0e-12
                    ):
                        selected_plan = candidate_plan
                        selected_tracking = tracking
                        selected_secondary = secondary
                        selected_delta_u = delta_u

        return replace(
            result,
            action=selected_plan[0],
            plan=selected_plan,
            tracking_cost=float(selected_tracking),
            secondary_cost=float(selected_secondary),
            evaluations=evaluations,
        )


def _policy_name(tolerance: float) -> str:
    if tolerance == 0.0:
        return "sequence_t0"
    return "sequence_t" + str(tolerance).replace(".", "p")


def _run_episode(policy: str, tolerance: float | None, episode, steps: int, sensor_timeout_ms: int) -> dict[str, object]:
    started = time.perf_counter()
    simulator = ClimateSimulator(episode.scenario)
    rule = ClimateRulePolicy()
    sequence_teacher = SmoothedSequenceTeacher(tolerance or 0.0) if tolerance is not None else None
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
    safety_steps = 0
    hard_steps = 0
    evaluations = 0

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
        else:
            assert sequence_teacher is not None
            choice = sequence_teacher.choose(
                simulator,
                profile.targets,
                humidity_control_mode=profile.humidity_control_mode,
                status=status,
                sensor_timeout_ms=sensor_timeout_ms,
            )
            raw = choice.action
            evaluations += choice.evaluations

        arbitration = arbitrate_climate_action(raw, simulator.scenario)
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
            abs(a - b) for a, b in zip(applied.as_tuple(), previous_applied.as_tuple(), strict=True)
        ) / len(CLIMATE_OUTPUT_NAMES)
        effort_sum += sum(applied.as_tuple()) / len(CLIMATE_OUTPUT_NAMES)
        co2_seconds += applied.co2_doser * simulator.scenario.timestep_s
        simulator.step(applied, add_sensor_noise=False, light_level=profile.light_level)
        previous_applied = applied

    return {
        "policy": policy,
        "family": episode.family,
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
        "safety_intervention_fraction": safety_steps / steps,
        "hard_limit_violation_fraction": hard_steps / steps,
        "evaluations_per_step": evaluations / steps if policy != "rule" else 0.0,
        "wall_seconds": time.perf_counter() - started,
    }


def _aggregate(policy: str, results: list[dict[str, object]]) -> dict[str, float | int]:
    selected = [item for item in results if item["policy"] == policy]
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
        "safety_intervention_fraction": weighted("safety_intervention_fraction"),
        "hard_limit_violation_fraction": weighted("hard_limit_violation_fraction"),
        "evaluations_per_step": weighted("evaluations_per_step"),
        "wall_seconds_sum": sum(float(item["wall_seconds"]) for item in selected),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=314159)
    parser.add_argument("--scenarios-per-family", type=int, default=1)
    parser.add_argument("--steps", type=int, default=10)
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--sensor-timeout-ms", type=int, default=30_000)
    args = parser.parse_args()

    episodes = structured_training_episodes(scenarios_per_family=args.scenarios_per_family, seed=args.seed)
    variants = [("rule", None)] + [(_policy_name(tolerance), tolerance) for tolerance in TOLERANCES]
    work = [(policy, tolerance, episode) for episode in episodes for policy, tolerance in variants]
    results: list[dict[str, object]] = []
    started = time.perf_counter()

    with ProcessPoolExecutor(max_workers=min(args.workers, len(work))) as executor:
        futures = {
            executor.submit(_run_episode, policy, tolerance, episode, args.steps, args.sensor_timeout_ms): (policy, episode.family)
            for policy, tolerance, episode in work
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

    policies = [name for name, _ in variants]
    aggregate = {policy: _aggregate(policy, results) for policy in policies}
    rule = aggregate["rule"]
    rule_tracking = float(rule["tracking_cost"])
    rule_switching = float(rule["switching_per_step"])
    tracking_gate = rule_tracking * 0.98
    switching_gate = rule_switching * 1.75 + 0.02

    for policy in policies[1:]:
        metrics = aggregate[policy]
        tracking = float(metrics["tracking_cost"])
        switching = float(metrics["switching_per_step"])
        metrics["tracking_improvement_vs_rule_pct"] = 100.0 * (rule_tracking - tracking) / rule_tracking
        metrics["tracking_gate_pass"] = int(tracking <= tracking_gate)
        metrics["switching_gate_pass"] = int(switching <= switching_gate)
        metrics["combined_gate_pass"] = int(tracking <= tracking_gate and switching <= switching_gate)

    families = {
        family: {
            policy: {
                "tracking_cost": next(float(item["tracking_cost"]) for item in results if item["family"] == family and item["policy"] == policy),
                "switching_per_step": next(float(item["switching_per_step"]) for item in results if item["family"] == family and item["policy"] == policy),
            }
            for policy in policies
        }
        for family in sorted({str(item["family"]) for item in results})
    }

    report = {
        "experiment": "stage12c_relative_tracking_tolerance_sweep",
        "config": vars(args),
        "tolerances": TOLERANCES,
        "tracking_gate": tracking_gate,
        "switching_gate": switching_gate,
        "aggregate": aggregate,
        "families": families,
        "wall_seconds": time.perf_counter() - started,
    }
    print("STAGE12C_JSON=" + json.dumps(report, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
