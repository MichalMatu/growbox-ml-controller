"""Deterministic rollout teacher for simulator v2 (10 ML outputs)."""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass

from .simulator_v2 import (
    MAX_ZONES,
    OUTPUT_NAMES,
    ControlAction,
    ControlTargets,
    SequentialEnvironmentSimulatorV2,
)

HEATER_LEVELS = (0.0, 1.0)
FAN_LEVELS = (0.0, 0.25, 0.5, 0.75, 1.0)
BINARY_LEVELS = (0.0, 1.0)
IRRIGATION_LEVELS = (0.0, 1.0)


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


@dataclass(frozen=True)
class TeacherResult:
    action: ControlAction
    cost: float
    candidate_index: int


def irrigation_levels_for_zone(
    simulator: SequentialEnvironmentSimulatorV2,
    zone_index: int,
) -> tuple[float, ...]:
    zone = simulator.scenario.zones[zone_index]
    if not zone.available or not zone.irrigation.available or not zone.soil_moisture_valid:
        return (0.0,)
    state = simulator.state.zones[zone_index]
    if state.soil_moisture_pct >= zone.target_soil_moisture_pct - 0.5:
        return (0.0,)
    if not simulator.irrigation_ready(zone_index):
        return (0.0,)
    return IRRIGATION_LEVELS


def build_candidates(simulator: SequentialEnvironmentSimulatorV2) -> tuple[ControlAction, ...]:
    """Build a finite candidate set; irrigation combos depend on active zones."""

    active = simulator.scenario.active_zone_indices()
    irrigation_products: tuple[tuple[float, ...], ...]
    if active:
        level_sets = [irrigation_levels_for_zone(simulator, index) for index in active]
        irrigation_products = tuple(itertools.product(*level_sets))
    else:
        irrigation_products = ((),)

    candidates: list[ControlAction] = []
    for heater, fan, humidifier, dehumidifier, cooler, co2_doser in itertools.product(
        HEATER_LEVELS,
        FAN_LEVELS,
        BINARY_LEVELS,
        BINARY_LEVELS,
        BINARY_LEVELS,
        BINARY_LEVELS,
    ):
        for irrigation_combo in irrigation_products:
            values = {
                "heater": heater,
                "fan": fan,
                "humidifier": humidifier,
                "dehumidifier": dehumidifier,
                "cooler": cooler,
                "co2_doser": co2_doser,
            }
            for output_index, zone_index in enumerate(range(MAX_ZONES)):
                name = OUTPUT_NAMES[6 + output_index]
                if zone_index in active:
                    combo_index = active.index(zone_index)
                    values[name] = irrigation_combo[combo_index]
                else:
                    values[name] = 0.0
            candidates.append(ControlAction.from_mapping(values))
    return tuple(candidates)


class RolloutTeacherV2:
    def __init__(
        self,
        *,
        cost: CostConfig | None = None,
        horizon_steps: int = 3,
    ) -> None:
        if horizon_steps <= 0:
            raise ValueError("horizon_steps must be positive")
        self.cost_config = cost or CostConfig()
        self.horizon_steps = int(horizon_steps)

    def choose(
        self,
        simulator: SequentialEnvironmentSimulatorV2,
        targets: ControlTargets | None = None,
    ) -> TeacherResult:
        targets = targets or simulator.scenario.targets
        candidates = build_candidates(simulator)
        best_index = 0
        best_cost = math.inf
        for index, candidate in enumerate(candidates):
            candidate_cost = self.evaluate(simulator, candidate, targets)
            if candidate_cost < best_cost:
                best_index = index
                best_cost = candidate_cost
        return TeacherResult(candidates[best_index], best_cost, best_index)

    def evaluate(
        self,
        simulator: SequentialEnvironmentSimulatorV2,
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
            soil_terms = 0.0
            for zone_index, zone in enumerate(rollout.scenario.zones):
                if not zone.available or not zone.soil_moisture_valid:
                    continue
                soil = (
                    state.zones[zone_index].soil_moisture_pct - zone.target_soil_moisture_pct
                ) / 50.0
                soil_terms += soil * soil
            total += terminal_scale * (
                weights.temperature_error * temperature * temperature
                + weights.humidity_error * humidity * humidity
                + weights.co2_error * co2 * co2
                + weights.soil_moisture_error * soil_terms
            )
        return float(total)

    def _command_cost(
        self,
        simulator: SequentialEnvironmentSimulatorV2,
        candidate: ControlAction,
        targets: ControlTargets,
    ) -> float:
        weights = self.cost_config
        caps = simulator.scenario.actuators
        state = simulator.state

        energy_proxy = (
            candidate.heater * caps.heater.max_power_w / 1000.0
            + candidate.fan * candidate.fan * caps.fan.max_airflow_m3_h / 500.0
            + candidate.humidifier * caps.humidifier.max_output_g_h / 500.0
            + candidate.dehumidifier * caps.dehumidifier.max_removal_g_h / 500.0
            + candidate.cooler * caps.cooler.max_cooling_w / 1000.0
        )

        water_fraction = 0.0
        for zone_index, zone in enumerate(simulator.scenario.zones):
            if not zone.available or not zone.irrigation.available:
                continue
            output_name = f"irrigation_zone_{zone_index + 1}"
            irrigation = getattr(candidate, output_name)
            water_fraction += (
                irrigation
                * zone.irrigation.flow_ml_s
                * zone.irrigation.maximum_pulse_s
                / max(1.0, zone.cultivation.substrate_water_capacity_ml)
            )

        switches = sum(
            abs(now - before)
            for now, before in zip(candidate.as_tuple(), simulator.previous_command.as_tuple())
        )

        violation = 0.0
        if candidate.heater > 0.0 and not caps.heater.available:
            violation += 1.0 + candidate.heater
        if candidate.fan > 0.0 and not caps.fan.available:
            violation += 1.0 + candidate.fan
        if candidate.humidifier > 0.0 and not caps.humidifier.available:
            violation += 1.0 + candidate.humidifier
        if candidate.dehumidifier > 0.0 and not caps.dehumidifier.available:
            violation += 1.0 + candidate.dehumidifier
        if candidate.cooler > 0.0 and not caps.cooler.available:
            violation += 1.0 + candidate.cooler
        if candidate.co2_doser > 0.0 and not caps.co2_doser.available:
            violation += 1.0 + candidate.co2_doser

        for zone_index, zone in enumerate(simulator.scenario.zones):
            if not zone.available or not zone.irrigation.available:
                continue
            output_name = f"irrigation_zone_{zone_index + 1}"
            irrigation = getattr(candidate, output_name)
            if irrigation > 0.0 and not simulator.irrigation_ready(zone_index):
                violation += 1.0
            if irrigation > 0.0 and zone.soil_moisture_valid:
                if state.zones[zone_index].soil_moisture_pct >= zone.target_soil_moisture_pct:
                    violation += 1.0 + irrigation

        unreachable = 0.0
        if not caps.heater.available and state.air_temperature_c < targets.target_air_temperature_c:
            unreachable += (targets.target_air_temperature_c - state.air_temperature_c) / 10.0
        if (
            not caps.humidifier.available
            and state.air_humidity_pct < targets.target_air_humidity_pct
        ):
            unreachable += (targets.target_air_humidity_pct - state.air_humidity_pct) / 35.0
        if not caps.fan.available:
            unreachable += abs(state.co2_ppm - targets.target_co2_ppm) / 1200.0
        for zone_index, zone in enumerate(simulator.scenario.zones):
            if not zone.available or not zone.irrigation.available or not zone.soil_moisture_valid:
                continue
            if state.zones[zone_index].soil_moisture_pct < zone.target_soil_moisture_pct:
                unreachable += (
                    zone.target_soil_moisture_pct - state.zones[zone_index].soil_moisture_pct
                ) / 50.0

        return float(
            weights.energy * energy_proxy
            + weights.water * water_fraction
            + weights.switching * switches
            + weights.constraint_violation * violation
            + weights.unreachable_target * unreachable
        )
