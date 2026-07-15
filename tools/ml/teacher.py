"""Deterministic finite-candidate rollout teacher."""

from __future__ import annotations

import itertools
import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from .simulator import ControlAction, ControlTargets, SequentialEnvironmentSimulator


@dataclass(frozen=True)
class CostConfig:
    temperature_error: float = 5.0
    humidity_error: float = 2.2
    co2_error: float = 0.8
    soil_moisture_error: float = 2.8
    energy: float = 0.12
    water: float = 0.18
    switching: float = 0.10
    constraint_violation: float = 100.0
    unreachable_target: float = 0.35
    terminal_multiplier: float = 1.5


HEATER_LEVELS = (0.0, 1.0)
FAN_LEVELS = (0.0, 0.25, 0.5, 0.75, 1.0)
HUMIDIFIER_LEVELS = (0.0, 1.0)
IRRIGATION_LEVELS = (0.0, 1.0)


def fixed_candidates() -> tuple[ControlAction, ...]:
    """Return candidates in the tie-breaking order used by the teacher.

    The Cartesian product starts at the all-off command. ``min`` is used with
    this tuple without a secondary key, so equal costs always resolve to the
    earliest candidate.
    """

    return tuple(
        ControlAction(heater, fan, humidifier, irrigation)
        for heater, fan, humidifier, irrigation in itertools.product(
            HEATER_LEVELS, FAN_LEVELS, HUMIDIFIER_LEVELS, IRRIGATION_LEVELS
        )
    )


FIXED_CANDIDATES = fixed_candidates()


@dataclass(frozen=True)
class TeacherResult:
    action: ControlAction
    cost: float
    candidate_index: int


class RolloutTeacher:
    def __init__(
        self,
        *,
        cost: CostConfig | None = None,
        horizon_steps: int = 3,
        candidates: Sequence[ControlAction] = FIXED_CANDIDATES,
    ) -> None:
        if horizon_steps <= 0:
            raise ValueError("horizon_steps must be positive")
        if not candidates:
            raise ValueError("at least one candidate is required")
        self.cost_config = cost or CostConfig()
        self.horizon_steps = int(horizon_steps)
        self.candidates = tuple(candidates)

    def choose(
        self,
        simulator: SequentialEnvironmentSimulator,
        targets: ControlTargets | None = None,
    ) -> TeacherResult:
        targets = targets or simulator.scenario.targets
        best_index = 0
        best_cost = math.inf
        for index, candidate in enumerate(self.candidates):
            candidate_cost = self.evaluate(simulator, candidate, targets)
            # Strict comparison deliberately preserves candidate order on ties.
            if candidate_cost < best_cost:
                best_index = index
                best_cost = candidate_cost
        return TeacherResult(self.candidates[best_index], best_cost, best_index)

    def evaluate(
        self,
        simulator: SequentialEnvironmentSimulator,
        candidate: ControlAction,
        targets: ControlTargets | None = None,
    ) -> float:
        targets = targets or simulator.scenario.targets
        rollout = simulator.clone()
        weights = self.cost_config
        total = self._command_cost(rollout, candidate, targets)

        for horizon_index in range(self.horizon_steps):
            state = rollout.step(candidate, add_sensor_noise=False)
            terminal_scale = (
                weights.terminal_multiplier if horizon_index == self.horizon_steps - 1 else 1.0
            )
            temperature = (state.air_temperature_c - targets.target_air_temperature_c) / 10.0
            humidity = (state.air_humidity_pct - targets.target_air_humidity_pct) / 35.0
            co2 = (state.co2_ppm - targets.target_co2_ppm) / 1200.0
            soil = (state.soil_moisture_pct - targets.target_soil_moisture_pct) / 50.0
            total += terminal_scale * (
                weights.temperature_error * temperature * temperature
                + weights.humidity_error * humidity * humidity
                + weights.co2_error * co2 * co2
                + weights.soil_moisture_error * soil * soil
            )

        return float(total)

    def _command_cost(
        self,
        simulator: SequentialEnvironmentSimulator,
        candidate: ControlAction,
        targets: ControlTargets,
    ) -> float:
        weights = self.cost_config
        caps = simulator.scenario.actuators
        crop = simulator.scenario.cultivation

        energy_proxy = (
            candidate.heater * caps.heater.max_power_w / 1000.0
            + candidate.fan * candidate.fan * caps.fan.max_airflow_m3_h / 500.0
            + candidate.humidifier * caps.humidifier.max_output_g_h / 500.0
        )
        water_fraction = (
            candidate.irrigation
            * caps.irrigation_pump.flow_ml_s
            * caps.irrigation_pump.maximum_pulse_s
            / max(1.0, crop.substrate_water_capacity_ml)
        )
        switches = sum(
            abs(now - before)
            for now, before in zip(candidate.as_array(), simulator.previous_command.as_array())
        )

        violation = 0.0
        availability = (
            caps.heater.available,
            caps.fan.available,
            caps.humidifier.available,
            caps.irrigation_pump.available,
        )
        for value, available in zip(candidate.as_array(), availability):
            if value > 0.0 and not available:
                violation += 1.0 + value
        if 0.0 < candidate.fan < caps.fan.minimum_command:
            violation += caps.fan.minimum_command - candidate.fan
        if candidate.irrigation > 0.0 and not simulator.irrigation_ready:
            violation += 1.0
        pulse_s = candidate.irrigation * caps.irrigation_pump.maximum_pulse_s
        if pulse_s > caps.irrigation_pump.maximum_pulse_s + 1.0e-9:
            violation += pulse_s - caps.irrigation_pump.maximum_pulse_s

        state = simulator.state
        unreachable = 0.0
        if not caps.heater.available and state.air_temperature_c < targets.target_air_temperature_c:
            unreachable += (targets.target_air_temperature_c - state.air_temperature_c) / 10.0
        if (
            not caps.humidifier.available
            and state.air_humidity_pct < targets.target_air_humidity_pct
        ):
            unreachable += (targets.target_air_humidity_pct - state.air_humidity_pct) / 35.0
        if (
            not caps.irrigation_pump.available
            and state.soil_moisture_pct < targets.target_soil_moisture_pct
        ):
            unreachable += (targets.target_soil_moisture_pct - state.soil_moisture_pct) / 50.0
        if not caps.fan.available:
            unreachable += abs(state.co2_ppm - targets.target_co2_ppm) / 1200.0

        return float(
            weights.energy * energy_proxy
            + weights.water * water_fraction
            + weights.switching * switches
            + weights.constraint_violation * violation
            + weights.unreachable_target * unreachable
        )


def label_sequence(
    simulator: SequentialEnvironmentSimulator,
    teacher: RolloutTeacher,
    steps: int,
) -> Iterable[tuple[object, TeacherResult]]:
    """Yield noisy observations and labels while advancing a scenario."""

    for _ in range(steps):
        observation = simulator.observe(add_sensor_noise=True)
        result = teacher.choose(simulator)
        yield observation, result
        simulator.step(result.action, add_sensor_noise=False)
