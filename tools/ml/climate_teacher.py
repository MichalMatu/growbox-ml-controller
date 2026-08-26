"""Deterministic rollout teacher for the climate-only MVP v6 simulator.

The teacher optimizes four coupled actuator groups with deterministic coordinate
search instead of the historical full Cartesian product. Opposing actuators are
not generated at all. The default 300 s horizon is long enough to observe the
configured MVP actuator lags and is validated against each scenario.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace

from .climate_input import (
    DEFAULT_SENSOR_TIMEOUT_MS,
    ClimateTargets,
    HumidityControlMode,
    MeasurementStatus,
    air_vpd_kpa,
)
from .climate_simulator import ClimateAction, ClimateSimulator


@dataclass(frozen=True)
class ClimateTeacherCost:
    temperature_error: float = 6.0
    humidity_error: float = 3.0
    vpd_error: float = 4.0
    co2_error: float = 1.5
    energy: float = 0.08
    co2_use: float = 0.08
    switching: float = 0.06
    terminal_multiplier: float = 2.0
    temperature_deadband_c: float = 0.3
    humidity_deadband_pct: float = 2.0
    vpd_deadband_kpa: float = 0.08
    co2_deadband_ppm: float = 50.0


@dataclass(frozen=True)
class ClimateTeacherConfig:
    horizon_s: float = 300.0
    rollout_dt_s: float = 10.0
    coordinate_passes: int = 2

    def __post_init__(self) -> None:
        if not math.isfinite(self.horizon_s) or self.horizon_s <= 0.0:
            raise ValueError("horizon_s must be finite and positive")
        if not math.isfinite(self.rollout_dt_s) or self.rollout_dt_s <= 0.0:
            raise ValueError("rollout_dt_s must be finite and positive")
        if self.coordinate_passes <= 0:
            raise ValueError("coordinate_passes must be positive")


@dataclass(frozen=True)
class ClimateTeacherResult:
    action: ClimateAction
    cost: float
    evaluations: int
    safe_fallback: bool = False


def _deadband_error(actual: float, target: float, deadband: float, scale: float) -> float:
    delta = float(actual) - float(target)
    excess = max(0.0, abs(delta) - max(0.0, float(deadband)))
    if excess == 0.0:
        return 0.0
    return math.copysign(excess / max(1.0e-9, float(scale)), delta)


def _status_usable(
    name: str,
    value: float,
    statuses: Mapping[str, MeasurementStatus],
    timeout_ms: int,
) -> bool:
    return statuses.get(name, MeasurementStatus()).usable(value, timeout_ms)


def _unique_levels(levels: Sequence[float], extra: float) -> tuple[float, ...]:
    values = [min(1.0, max(0.0, float(value))) for value in levels]
    values.append(min(1.0, max(0.0, float(extra))))
    return tuple(dict.fromkeys(values))


class ClimateRolloutTeacher:
    def __init__(
        self,
        *,
        cost: ClimateTeacherCost | None = None,
        config: ClimateTeacherConfig | None = None,
    ) -> None:
        self.cost = cost or ClimateTeacherCost()
        self.config = config or ClimateTeacherConfig()

    def choose(
        self,
        simulator: ClimateSimulator,
        targets: ClimateTargets,
        *,
        humidity_control_mode: HumidityControlMode = "RH",
        status: Mapping[str, MeasurementStatus] | None = None,
        sensor_timeout_ms: int = DEFAULT_SENSOR_TIMEOUT_MS,
    ) -> ClimateTeacherResult:
        statuses = status or {}
        state = simulator.state
        timeout = int(sensor_timeout_ms)
        if timeout < 0:
            raise ValueError("sensor_timeout_ms must be non-negative")
        self._validate_horizon(simulator)

        temperature_usable = _status_usable(
            "air_temperature_c", state.air_temperature_c, statuses, timeout
        )
        humidity_usable = _status_usable(
            "relative_humidity_pct", state.relative_humidity_pct, statuses, timeout
        )
        if not temperature_usable or not humidity_usable:
            return ClimateTeacherResult(ClimateAction(), 0.0, 0, safe_fallback=True)

        co2_usable = _status_usable("co2_ppm", state.co2_ppm, statuses, timeout)
        outside_usable = _status_usable(
            "outside_temperature_c", state.outside_temperature_c, statuses, timeout
        ) and _status_usable("outside_humidity_pct", state.outside_humidity_pct, statuses, timeout)

        current = self._sanitize_previous(
            simulator,
            allow_exhaust=outside_usable,
            allow_co2=targets.co2_enabled and co2_usable,
        )
        evaluations = 0
        best_cost = self.evaluate(
            simulator,
            current,
            targets,
            humidity_control_mode=humidity_control_mode,
            co2_usable=co2_usable,
        )
        evaluations += 1

        groups = (
            lambda action: self._temperature_options(simulator, action),
            lambda action: self._humidity_options(simulator, action),
            lambda action: self._exhaust_options(simulator, action, outside_usable),
            lambda action: self._co2_options(simulator, action, targets.co2_enabled and co2_usable),
        )

        for _ in range(self.config.coordinate_passes):
            for options_for in groups:
                options = options_for(current)
                group_best = current
                group_cost = best_cost
                for candidate in options:
                    cost = self.evaluate(
                        simulator,
                        candidate,
                        targets,
                        humidity_control_mode=humidity_control_mode,
                        co2_usable=co2_usable,
                    )
                    evaluations += 1
                    if cost < group_cost - 1.0e-12:
                        group_best = candidate
                        group_cost = cost
                current = group_best
                best_cost = group_cost

        return ClimateTeacherResult(current, float(best_cost), evaluations)

    def evaluate(
        self,
        simulator: ClimateSimulator,
        candidate: ClimateAction,
        targets: ClimateTargets,
        *,
        humidity_control_mode: HumidityControlMode = "RH",
        co2_usable: bool = True,
    ) -> float:
        rollout = simulator.clone()
        horizon = float(self.config.horizon_s)
        dt = min(float(self.config.rollout_dt_s), horizon)
        full_steps = int(horizon // dt)
        remainder = horizon - full_steps * dt
        steps = [dt] * full_steps
        if remainder > 1.0e-9:
            steps.append(remainder)
        if not steps:
            steps = [horizon]

        total = self._command_cost(simulator, candidate)
        final_state_cost = 0.0
        for step_dt in steps:
            state = rollout.step(candidate, timestep_s=step_dt, add_sensor_noise=False)
            final_state_cost = self._state_cost(
                state.air_temperature_c,
                state.relative_humidity_pct,
                state.co2_ppm,
                targets,
                humidity_control_mode=humidity_control_mode,
                co2_usable=co2_usable,
            )
            total += final_state_cost * (step_dt / horizon)
        total += max(0.0, self.cost.terminal_multiplier - 1.0) * final_state_cost
        return float(total)

    def _state_cost(
        self,
        temperature_c: float,
        humidity_pct: float,
        co2_ppm: float,
        targets: ClimateTargets,
        *,
        humidity_control_mode: HumidityControlMode,
        co2_usable: bool,
    ) -> float:
        temperature_error = _deadband_error(
            temperature_c,
            targets.air_temperature_c,
            self.cost.temperature_deadband_c,
            5.0,
        )
        if humidity_control_mode == "VPD":
            humidity_error = _deadband_error(
                air_vpd_kpa(temperature_c, humidity_pct),
                targets.air_vpd_kpa,
                self.cost.vpd_deadband_kpa,
                0.7,
            )
            humidity_cost = self.cost.vpd_error * humidity_error * humidity_error
        elif humidity_control_mode == "RH":
            humidity_error = _deadband_error(
                humidity_pct,
                targets.relative_humidity_pct,
                self.cost.humidity_deadband_pct,
                20.0,
            )
            humidity_cost = self.cost.humidity_error * humidity_error * humidity_error
        else:
            raise ValueError(f"unsupported humidity control mode: {humidity_control_mode!r}")

        co2_cost = 0.0
        if targets.co2_enabled and co2_usable:
            co2_error = _deadband_error(
                co2_ppm,
                targets.co2_ppm,
                self.cost.co2_deadband_ppm,
                700.0,
            )
            co2_cost = self.cost.co2_error * co2_error * co2_error
        return (
            self.cost.temperature_error * temperature_error * temperature_error
            + humidity_cost
            + co2_cost
        )

    def _command_cost(self, simulator: ClimateSimulator, candidate: ClimateAction) -> float:
        caps = simulator.scenario.actuators
        energy_proxy = (
            candidate.heater * max(0.0, caps.heater.max_power_w) / 500.0
            + candidate.cooler * max(0.0, caps.cooler.max_cooling_w) / 500.0
            + candidate.exhaust_fan * candidate.exhaust_fan
            + candidate.humidifier * max(0.0, caps.humidifier.max_output_g_h) / 500.0
            + candidate.dehumidifier * max(0.0, caps.dehumidifier.max_removal_g_h) / 500.0
        )
        switches = sum(
            abs(now - before)
            for now, before in zip(
                candidate.as_tuple(), simulator.previous_command.as_tuple(), strict=True
            )
        )
        return float(
            self.cost.energy * energy_proxy
            + self.cost.co2_use * candidate.co2_doser
            + self.cost.switching * switches
        )

    def _validate_horizon(self, simulator: ClimateSimulator) -> None:
        lag = simulator.scenario.response_lag
        longest = max(
            0.0,
            lag.heater_s,
            lag.cooler_s,
            lag.exhaust_fan_s,
            lag.humidifier_s,
            lag.dehumidifier_s,
            lag.co2_doser_s,
        )
        required = 3.0 * longest
        if self.config.horizon_s + 1.0e-9 < required:
            raise ValueError(
                f"teacher horizon {self.config.horizon_s:g}s is shorter than 3x longest "
                f"actuator lag ({required:g}s required)"
            )

    @staticmethod
    def _sanitize_previous(
        simulator: ClimateSimulator,
        *,
        allow_exhaust: bool,
        allow_co2: bool,
    ) -> ClimateAction:
        previous = simulator.previous_command.clipped()
        caps = simulator.scenario.actuators
        heater = previous.heater if caps.heater.available else 0.0
        cooler = previous.cooler if caps.cooler.available else 0.0
        if heater > 0.0 and cooler > 0.0:
            if heater >= cooler:
                cooler = 0.0
            else:
                heater = 0.0
        humidifier = previous.humidifier if caps.humidifier.available else 0.0
        dehumidifier = previous.dehumidifier if caps.dehumidifier.available else 0.0
        if humidifier > 0.0 and dehumidifier > 0.0:
            if humidifier >= dehumidifier:
                dehumidifier = 0.0
            else:
                humidifier = 0.0
        return ClimateAction(
            heater=heater,
            cooler=cooler,
            exhaust_fan=(
                previous.exhaust_fan if caps.exhaust_fan.available and allow_exhaust else 0.0
            ),
            humidifier=humidifier,
            dehumidifier=dehumidifier,
            co2_doser=(previous.co2_doser if caps.co2_doser.available and allow_co2 else 0.0),
        )

    @staticmethod
    def _temperature_options(
        simulator: ClimateSimulator, current: ClimateAction
    ) -> tuple[ClimateAction, ...]:
        caps = simulator.scenario.actuators
        pairs: list[tuple[float, float]] = [(0.0, 0.0), (current.heater, current.cooler)]
        if caps.heater.available:
            pairs.extend((level, 0.0) for level in (0.35, 0.7, 1.0))
        if caps.cooler.available:
            pairs.extend((0.0, level) for level in (0.35, 0.7, 1.0))
        unique = tuple(dict.fromkeys(pairs))
        return tuple(replace(current, heater=heater, cooler=cooler) for heater, cooler in unique)

    @staticmethod
    def _humidity_options(
        simulator: ClimateSimulator, current: ClimateAction
    ) -> tuple[ClimateAction, ...]:
        caps = simulator.scenario.actuators
        pairs: list[tuple[float, float]] = [
            (0.0, 0.0),
            (current.humidifier, current.dehumidifier),
        ]
        if caps.humidifier.available:
            pairs.extend((level, 0.0) for level in (0.35, 0.7, 1.0))
        if caps.dehumidifier.available:
            pairs.extend((0.0, level) for level in (0.35, 0.7, 1.0))
        unique = tuple(dict.fromkeys(pairs))
        return tuple(
            replace(current, humidifier=humidifier, dehumidifier=dehumidifier)
            for humidifier, dehumidifier in unique
        )

    @staticmethod
    def _exhaust_options(
        simulator: ClimateSimulator, current: ClimateAction, allowed: bool
    ) -> tuple[ClimateAction, ...]:
        if not simulator.scenario.actuators.exhaust_fan.available or not allowed:
            return (replace(current, exhaust_fan=0.0),)
        levels = _unique_levels((0.0, 0.25, 0.5, 0.75, 1.0), current.exhaust_fan)
        return tuple(replace(current, exhaust_fan=level) for level in levels)

    @staticmethod
    def _co2_options(
        simulator: ClimateSimulator, current: ClimateAction, allowed: bool
    ) -> tuple[ClimateAction, ...]:
        if not simulator.scenario.actuators.co2_doser.available or not allowed:
            return (replace(current, co2_doser=0.0),)
        levels = _unique_levels((0.0, 0.5, 1.0), current.co2_doser)
        return tuple(replace(current, co2_doser=level) for level in levels)


__all__ = [
    "ClimateRolloutTeacher",
    "ClimateTeacherConfig",
    "ClimateTeacherCost",
    "ClimateTeacherResult",
]
