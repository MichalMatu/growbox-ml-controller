"""Deterministic sequence-rollout oracle for the climate-only MVP v6 simulator.

This module is intentionally experimental. Unlike ``ClimateRolloutTeacher``, which
holds one candidate action for the complete rollout horizon, this oracle optimizes
a move-blocked sequence and returns only the first action. Calling ``choose`` again
at the next control step therefore implements receding-horizon sequence control.

The primary objective is the benchmark-aligned climate tracking cost. After the
best tracking plan is found, a narrow relative tracking band may be used to prefer
a smoother receding-horizon first action, with whole-plan delta-u and the existing
secondary cost used only as later tie-breakers.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from .climate_input import (
    DEFAULT_SENSOR_TIMEOUT_MS,
    ClimateTargets,
    HumidityControlMode,
    MeasurementStatus,
)
from .climate_simulator import ClimateAction, ClimateSimulator
from .climate_teacher import ClimateRolloutTeacher, ClimateTeacherConfig, ClimateTeacherCost

DEFAULT_MOVE_BLOCK_STEPS: tuple[int, ...] = (1, 1, 1, 1, 2, 2, 3, 4, 5, 10)


@dataclass(frozen=True)
class ClimateSequenceTeacherConfig:
    horizon_s: float = 300.0
    rollout_dt_s: float = 10.0
    move_block_steps: tuple[int, ...] = DEFAULT_MOVE_BLOCK_STEPS
    coordinate_passes: int = 1
    primary_tolerance: float = 1.0e-12
    smoothing_tolerance_fraction: float = 0.001

    def __post_init__(self) -> None:
        if not math.isfinite(self.horizon_s) or self.horizon_s <= 0.0:
            raise ValueError("horizon_s must be finite and positive")
        if not math.isfinite(self.rollout_dt_s) or self.rollout_dt_s <= 0.0:
            raise ValueError("rollout_dt_s must be finite and positive")
        if self.coordinate_passes <= 0:
            raise ValueError("coordinate_passes must be positive")
        if not math.isfinite(self.primary_tolerance) or self.primary_tolerance < 0.0:
            raise ValueError("primary_tolerance must be finite and non-negative")
        if (
            not math.isfinite(self.smoothing_tolerance_fraction)
            or self.smoothing_tolerance_fraction < 0.0
        ):
            raise ValueError("smoothing_tolerance_fraction must be finite and non-negative")
        if not self.move_block_steps or any(step <= 0 for step in self.move_block_steps):
            raise ValueError("move_block_steps must contain positive integers")

        horizon_steps = self.horizon_s / self.rollout_dt_s
        rounded_steps = int(round(horizon_steps))
        if not math.isclose(horizon_steps, rounded_steps, rel_tol=0.0, abs_tol=1.0e-9):
            raise ValueError("horizon_s must be an integer multiple of rollout_dt_s")
        if sum(self.move_block_steps) != rounded_steps:
            raise ValueError(
                "move_block_steps must cover the complete horizon: "
                f"got {sum(self.move_block_steps)} steps, expected {rounded_steps}"
            )

    @classmethod
    def full_sequence(
        cls, *, horizon_s: float = 300.0, rollout_dt_s: float = 10.0
    ) -> ClimateSequenceTeacherConfig:
        horizon_steps = horizon_s / rollout_dt_s
        rounded_steps = int(round(horizon_steps))
        if not math.isclose(horizon_steps, rounded_steps, rel_tol=0.0, abs_tol=1.0e-9):
            raise ValueError("horizon_s must be an integer multiple of rollout_dt_s")
        return cls(
            horizon_s=horizon_s,
            rollout_dt_s=rollout_dt_s,
            move_block_steps=(1,) * rounded_steps,
        )


@dataclass(frozen=True)
class ClimateSequenceTeacherResult:
    action: ClimateAction
    plan: tuple[ClimateAction, ...]
    move_block_steps: tuple[int, ...]
    tracking_cost: float
    secondary_cost: float
    evaluations: int
    safe_fallback: bool = False


class ClimateSequenceRolloutTeacher:
    """Move-blocked sequence optimizer over the existing black-box simulator."""

    def __init__(
        self,
        *,
        cost: ClimateTeacherCost | None = None,
        config: ClimateSequenceTeacherConfig | None = None,
    ) -> None:
        self.cost = cost or ClimateTeacherCost()
        self.config = config or ClimateSequenceTeacherConfig()
        self._constant_teacher = ClimateRolloutTeacher(
            cost=self.cost,
            config=ClimateTeacherConfig(
                horizon_s=self.config.horizon_s,
                rollout_dt_s=self.config.rollout_dt_s,
                coordinate_passes=2,
            ),
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
        statuses = status or {}
        state = simulator.state
        timeout = int(sensor_timeout_ms)
        if timeout < 0:
            raise ValueError("sensor_timeout_ms must be non-negative")
        self._constant_teacher._validate_horizon(simulator)

        temperature_usable = self._status_usable(
            "air_temperature_c", state.air_temperature_c, statuses, timeout
        )
        humidity_usable = self._status_usable(
            "relative_humidity_pct", state.relative_humidity_pct, statuses, timeout
        )
        if not temperature_usable or not humidity_usable:
            zero = ClimateAction()
            plan = (zero,) * len(self.config.move_block_steps)
            return ClimateSequenceTeacherResult(
                action=zero,
                plan=plan,
                move_block_steps=self.config.move_block_steps,
                tracking_cost=0.0,
                secondary_cost=0.0,
                evaluations=0,
                safe_fallback=True,
            )

        co2_usable = self._status_usable("co2_ppm", state.co2_ppm, statuses, timeout)
        outside_usable = self._status_usable(
            "outside_temperature_c", state.outside_temperature_c, statuses, timeout
        ) and self._status_usable(
            "outside_humidity_pct", state.outside_humidity_pct, statuses, timeout
        )
        allow_co2 = targets.co2_enabled and co2_usable

        previous = self._constant_teacher._sanitize_previous(
            simulator,
            allow_exhaust=outside_usable,
            allow_co2=allow_co2,
        )
        constant = self._constant_teacher.choose(
            simulator,
            targets,
            humidity_control_mode=humidity_control_mode,
            status=statuses,
            sensor_timeout_ms=timeout,
        ).action

        seeds = (
            (previous,) * len(self.config.move_block_steps),
            (constant,) * len(self.config.move_block_steps),
        )
        evaluations = 0
        best_plan = seeds[0]
        best_primary, best_secondary = self.evaluate_plan(
            simulator,
            best_plan,
            targets,
            humidity_control_mode=humidity_control_mode,
            co2_usable=co2_usable,
        )
        evaluations += 1
        for seed in seeds[1:]:
            primary, secondary = self.evaluate_plan(
                simulator,
                seed,
                targets,
                humidity_control_mode=humidity_control_mode,
                co2_usable=co2_usable,
            )
            evaluations += 1
            if self._better(primary, secondary, best_primary, best_secondary):
                best_plan = seed
                best_primary = primary
                best_secondary = secondary

        for _ in range(self.config.coordinate_passes):
            for block_index in range(len(best_plan)):
                for group in ("temperature", "humidity", "exhaust", "co2"):
                    current_action = best_plan[block_index]
                    for candidate_action in self._group_options(
                        simulator,
                        current_action,
                        group=group,
                        outside_usable=outside_usable,
                        allow_co2=allow_co2,
                    ):
                        if candidate_action == current_action:
                            continue
                        candidate_plan = list(best_plan)
                        candidate_plan[block_index] = candidate_action
                        candidate_tuple = tuple(candidate_plan)
                        primary, secondary = self.evaluate_plan(
                            simulator,
                            candidate_tuple,
                            targets,
                            humidity_control_mode=humidity_control_mode,
                            co2_usable=co2_usable,
                        )
                        evaluations += 1
                        if self._better(primary, secondary, best_primary, best_secondary):
                            best_plan = candidate_tuple
                            best_primary = primary
                            best_secondary = secondary

        if self.config.smoothing_tolerance_fraction > 0.0:
            (
                best_plan,
                best_primary,
                best_secondary,
                smoothing_evaluations,
            ) = self._smooth_plan_within_tracking_band(
                simulator,
                best_plan,
                best_primary,
                best_secondary,
                targets,
                humidity_control_mode=humidity_control_mode,
                co2_usable=co2_usable,
                outside_usable=outside_usable,
                allow_co2=allow_co2,
            )
            evaluations += smoothing_evaluations

        return ClimateSequenceTeacherResult(
            action=best_plan[0],
            plan=best_plan,
            move_block_steps=self.config.move_block_steps,
            tracking_cost=float(best_primary),
            secondary_cost=float(best_secondary),
            evaluations=evaluations,
        )

    def evaluate_plan(
        self,
        simulator: ClimateSimulator,
        plan: Sequence[ClimateAction],
        targets: ClimateTargets,
        *,
        humidity_control_mode: HumidityControlMode = "RH",
        co2_usable: bool = True,
    ) -> tuple[float, float]:
        if len(plan) != len(self.config.move_block_steps):
            raise ValueError(
                f"plan has {len(plan)} blocks; expected {len(self.config.move_block_steps)}"
            )

        rollout = simulator.clone()
        horizon = float(self.config.horizon_s)
        dt = float(self.config.rollout_dt_s)
        tracking = 0.0
        secondary = 0.0
        previous = simulator.previous_command.clipped()
        caps = simulator.scenario.actuators

        for action, block_steps in zip(plan, self.config.move_block_steps, strict=True):
            command = action.clipped()
            block_seconds = block_steps * dt
            energy_proxy = (
                command.heater * max(0.0, caps.heater.max_power_w) / 500.0
                + command.cooler * max(0.0, caps.cooler.max_cooling_w) / 500.0
                + command.exhaust_fan * command.exhaust_fan
                + command.humidifier * max(0.0, caps.humidifier.max_output_g_h) / 500.0
                + command.dehumidifier * max(0.0, caps.dehumidifier.max_removal_g_h) / 500.0
            )
            secondary += (block_seconds / horizon) * (
                self.cost.energy * energy_proxy + self.cost.co2_use * command.co2_doser
            )
            secondary += self.cost.switching * sum(
                abs(now - before)
                for now, before in zip(command.as_tuple(), previous.as_tuple(), strict=True)
            )
            previous = command

            for _ in range(block_steps):
                state = rollout.step(command, timestep_s=dt, add_sensor_noise=False)
                tracking += (dt / horizon) * self._constant_teacher._state_cost(
                    state.air_temperature_c,
                    state.relative_humidity_pct,
                    state.co2_ppm,
                    targets,
                    humidity_control_mode=humidity_control_mode,
                    co2_usable=co2_usable,
                )

        return float(tracking), float(secondary)

    def _better(
        self,
        primary: float,
        secondary: float,
        best_primary: float,
        best_secondary: float,
    ) -> bool:
        tolerance = self.config.primary_tolerance
        if primary < best_primary - tolerance:
            return True
        return abs(primary - best_primary) <= tolerance and secondary < best_secondary - 1.0e-12

    @staticmethod
    def _action_delta(action: ClimateAction, previous: ClimateAction) -> float:
        current_values = action.clipped().as_tuple()
        previous_values = previous.clipped().as_tuple()
        return sum(
            abs(now - before) for now, before in zip(current_values, previous_values, strict=True)
        ) / len(current_values)

    @classmethod
    def _plan_delta_u(cls, plan: Sequence[ClimateAction], previous: ClimateAction) -> float:
        total = 0.0
        before = previous.clipped()
        for action in plan:
            command = action.clipped()
            total += cls._action_delta(command, before)
            before = command
        return total

    def _smooth_plan_within_tracking_band(
        self,
        simulator: ClimateSimulator,
        plan: tuple[ClimateAction, ...],
        tracking_anchor: float,
        secondary_cost: float,
        targets: ClimateTargets,
        *,
        humidity_control_mode: HumidityControlMode,
        co2_usable: bool,
        outside_usable: bool,
        allow_co2: bool,
    ) -> tuple[tuple[ClimateAction, ...], float, float, int]:
        tracking_limit = tracking_anchor * (1.0 + self.config.smoothing_tolerance_fraction)
        selected_plan = plan
        selected_tracking = tracking_anchor
        selected_secondary = secondary_cost
        previous = simulator.previous_command.clipped()
        selected_first_delta = self._action_delta(selected_plan[0], previous)
        selected_plan_delta = self._plan_delta_u(selected_plan, previous)
        evaluations = 0

        for block_index in range(len(selected_plan)):
            for group in ("temperature", "humidity", "exhaust", "co2"):
                current_action = selected_plan[block_index]
                for candidate_action in self._group_options(
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
                    tracking, secondary = self.evaluate_plan(
                        simulator,
                        candidate_plan,
                        targets,
                        humidity_control_mode=humidity_control_mode,
                        co2_usable=co2_usable,
                    )
                    evaluations += 1
                    if tracking > tracking_limit + 1.0e-12:
                        continue

                    first_delta = self._action_delta(candidate_plan[0], previous)
                    plan_delta = self._plan_delta_u(candidate_plan, previous)
                    if (
                        first_delta < selected_first_delta - 1.0e-12
                        or (
                            abs(first_delta - selected_first_delta) <= 1.0e-12
                            and plan_delta < selected_plan_delta - 1.0e-12
                        )
                        or (
                            abs(first_delta - selected_first_delta) <= 1.0e-12
                            and abs(plan_delta - selected_plan_delta) <= 1.0e-12
                            and secondary < selected_secondary - 1.0e-12
                        )
                    ):
                        selected_plan = candidate_plan
                        selected_tracking = tracking
                        selected_secondary = secondary
                        selected_first_delta = first_delta
                        selected_plan_delta = plan_delta

        return (
            selected_plan,
            float(selected_tracking),
            float(selected_secondary),
            evaluations,
        )

    def _group_options(
        self,
        simulator: ClimateSimulator,
        current: ClimateAction,
        *,
        group: str,
        outside_usable: bool,
        allow_co2: bool,
    ) -> tuple[ClimateAction, ...]:
        if group == "temperature":
            return self._constant_teacher._temperature_options(simulator, current)
        if group == "humidity":
            return self._constant_teacher._humidity_options(simulator, current)
        if group == "exhaust":
            return self._constant_teacher._exhaust_options(simulator, current, outside_usable)
        if group == "co2":
            return self._constant_teacher._co2_options(simulator, current, allow_co2)
        raise ValueError(f"unsupported action group: {group!r}")

    @staticmethod
    def _status_usable(
        name: str,
        value: float,
        statuses: Mapping[str, MeasurementStatus],
        timeout_ms: int,
    ) -> bool:
        return statuses.get(name, MeasurementStatus()).usable(value, timeout_ms)


__all__ = [
    "ClimateSequenceRolloutTeacher",
    "ClimateSequenceTeacherConfig",
    "ClimateSequenceTeacherResult",
    "DEFAULT_MOVE_BLOCK_STEPS",
]
