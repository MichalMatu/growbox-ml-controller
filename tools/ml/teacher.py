"""Deterministic rollout teacher for simulator v2 (15 ML outputs incl. heating)."""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass

from .simulator import (
    MAX_POTS,
    OUTPUT_NAMES,
    ControlAction,
    ControlTargets,
    SequentialEnvironmentSimulator,
)

HEATER_LEVELS = (0.0, 1.0)
FAN_LEVELS = (0.0, 0.25, 0.5, 0.75, 1.0)
BINARY_LEVELS = (0.0, 1.0)
IRRIGATION_LEVELS = (0.0, 1.0)


@dataclass(frozen=True)
class CostConfig:
    # Prefer tracking climate setpoints over energy when errors are large; weak
    # sigmoid outputs otherwise fall below safety binary_threshold (0.5).
    temperature_error: float = 8.0
    humidity_error: float = 3.4
    co2_error: float = 1.1
    soil_moisture_error: float = 3.2
    nutrient_temperature_error: float = 3.6
    soil_temperature_error: float = 3.0
    energy: float = 0.08
    water: float = 0.16
    switching: float = 0.08
    # Soft penalty when opposing climate actuators fight each other (labels only).
    opposing_actuators: float = 12.0
    constraint_violation: float = 100.0
    unreachable_target: float = 0.35
    terminal_multiplier: float = 1.8


@dataclass(frozen=True)
class TeacherResult:
    action: ControlAction
    cost: float
    candidate_index: int


def nutrient_heater_levels(simulator: SequentialEnvironmentSimulator) -> tuple[float, ...]:
    caps = simulator.scenario.actuators.nutrient_heater
    if not caps.available or not simulator.scenario.validity.nutrient_solution_temperature_c:
        return (0.0,)
    target = simulator.scenario.targets.target_nutrient_solution_temperature_c
    current = simulator.state.nutrient_solution_temperature_c
    if current < target - 0.5:
        return BINARY_LEVELS
    return (0.0,)


def heat_mat_levels_for_zone(
    simulator: SequentialEnvironmentSimulator,
    pot_index: int,
) -> tuple[float, ...]:
    pot = simulator.scenario.pots[pot_index]
    if not pot.available or not pot.heat_mat.available or not pot.soil_temperature_valid:
        return (0.0,)
    current = simulator.state.pots[pot_index].soil_temperature_c
    if current < pot.target_soil_temperature_c - 0.5:
        return BINARY_LEVELS
    return (0.0,)


def irrigation_levels_for_zone(
    simulator: SequentialEnvironmentSimulator,
    pot_index: int,
) -> tuple[float, ...]:
    pot = simulator.scenario.pots[pot_index]
    if not pot.available or not pot.irrigation.available or not pot.soil_moisture_valid:
        return (0.0,)
    state = simulator.state.pots[pot_index]
    if state.soil_moisture_pct >= pot.target_soil_moisture_pct - 0.5:
        return (0.0,)
    if not simulator.irrigation_ready(pot_index):
        return (0.0,)
    return IRRIGATION_LEVELS


def build_candidates(simulator: SequentialEnvironmentSimulator) -> tuple[ControlAction, ...]:
    """Build a finite candidate set; irrigation combos depend on active pots."""

    active = simulator.scenario.active_pot_indices()
    irrigation_products: tuple[tuple[float, ...], ...]
    if active:
        level_sets = [irrigation_levels_for_zone(simulator, index) for index in active]
        irrigation_products = tuple(itertools.product(*level_sets))
    else:
        irrigation_products = ((),)

    nutrient_levels = nutrient_heater_levels(simulator)
    heat_mat_products = tuple(
        itertools.product(
            *(heat_mat_levels_for_zone(simulator, pot_index) for pot_index in range(MAX_POTS))
        )
    )

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
            for nutrient_heater in nutrient_levels:
                for heat_mat_combo in heat_mat_products:
                    values = {
                        "heater": heater,
                        "fan": fan,
                        "humidifier": humidifier,
                        "dehumidifier": dehumidifier,
                        "cooler": cooler,
                        "co2_doser": co2_doser,
                        "nutrient_heater": nutrient_heater,
                    }
                    for output_index, pot_index in enumerate(range(MAX_POTS)):
                        name = OUTPUT_NAMES[6 + output_index]
                        if pot_index in active:
                            combo_index = active.index(pot_index)
                            values[name] = irrigation_combo[combo_index]
                        else:
                            values[name] = 0.0
                    for pot_index, heat_name in enumerate(OUTPUT_NAMES[11:]):
                        values[heat_name] = heat_mat_combo[pot_index]
                    candidates.append(ControlAction.from_mapping(values))
    return tuple(candidates)


class RolloutTeacher:
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
        simulator: SequentialEnvironmentSimulator,
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
            soil_terms = 0.0
            soil_temperature_terms = 0.0
            for pot_index, pot in enumerate(rollout.scenario.pots):
                if not pot.available or not pot.soil_moisture_valid:
                    continue
                soil = (
                    state.pots[pot_index].soil_moisture_pct - pot.target_soil_moisture_pct
                ) / 50.0
                soil_terms += soil * soil
                if pot.soil_temperature_valid:
                    soil_temperature = (
                        state.pots[pot_index].soil_temperature_c - pot.target_soil_temperature_c
                    ) / 12.0
                    soil_temperature_terms += soil_temperature * soil_temperature
            nutrient_temperature = 0.0
            if rollout.scenario.validity.nutrient_solution_temperature_c:
                nutrient_temperature = (
                    state.nutrient_solution_temperature_c
                    - targets.target_nutrient_solution_temperature_c
                ) / 12.0
            total += terminal_scale * (
                weights.temperature_error * temperature * temperature
                + weights.humidity_error * humidity * humidity
                + weights.co2_error * co2 * co2
                + weights.soil_moisture_error * soil_terms
                + weights.nutrient_temperature_error * nutrient_temperature * nutrient_temperature
                + weights.soil_temperature_error * soil_temperature_terms
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
        state = simulator.state

        energy_proxy = (
            candidate.heater * caps.heater.max_power_w / 1000.0
            + candidate.fan * candidate.fan * caps.fan.max_airflow_m3_h / 500.0
            + candidate.humidifier * caps.humidifier.max_output_g_h / 500.0
            + candidate.dehumidifier * caps.dehumidifier.max_removal_g_h / 500.0
            + candidate.cooler * caps.cooler.max_cooling_w / 1000.0
            + candidate.nutrient_heater
            * caps.nutrient_heater.max_power_w
            * caps.nutrient_heater.efficiency
            / 1000.0
        )
        for pot_index, pot in enumerate(simulator.scenario.pots):
            if not pot.available or not pot.heat_mat.available:
                continue
            heat_name = f"heat_mat_pot_{pot_index + 1}"
            energy_proxy += getattr(candidate, heat_name) * pot.heat_mat.max_power_w / 1000.0

        water_fraction = 0.0
        for pot_index, pot in enumerate(simulator.scenario.pots):
            if not pot.available or not pot.irrigation.available:
                continue
            output_name = f"irrigation_pot_{pot_index + 1}"
            irrigation = getattr(candidate, output_name)
            water_fraction += (
                irrigation
                * pot.irrigation.flow_ml_s
                * pot.irrigation.maximum_pulse_s
                / max(1.0, pot.cultivation.substrate_water_capacity_ml)
            )

        switches = sum(
            abs(now - before)
            for now, before in zip(candidate.as_tuple(), simulator.previous_command.as_tuple())
        )

        # Opposing pairs waste energy and fight setpoints (soft, not safety).
        opposing = 0.0
        if candidate.heater > 0.0 and candidate.cooler > 0.0:
            opposing += candidate.heater * candidate.cooler
        if candidate.humidifier > 0.0 and candidate.dehumidifier > 0.0:
            opposing += candidate.humidifier * candidate.dehumidifier

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
        if candidate.nutrient_heater > 0.0 and not caps.nutrient_heater.available:
            violation += 1.0 + candidate.nutrient_heater

        for pot_index, pot in enumerate(simulator.scenario.pots):
            heat_name = f"heat_mat_pot_{pot_index + 1}"
            heat_mat = getattr(candidate, heat_name)
            if heat_mat <= 0.0:
                continue
            if not pot.available or not pot.heat_mat.available:
                violation += 1.0 + heat_mat

        for pot_index, pot in enumerate(simulator.scenario.pots):
            if not pot.available or not pot.irrigation.available:
                continue
            output_name = f"irrigation_pot_{pot_index + 1}"
            irrigation = getattr(candidate, output_name)
            if irrigation > 0.0 and not simulator.irrigation_ready(pot_index):
                violation += 1.0
            if irrigation > 0.0 and pot.soil_moisture_valid:
                if state.pots[pot_index].soil_moisture_pct >= pot.target_soil_moisture_pct:
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
        for pot_index, pot in enumerate(simulator.scenario.pots):
            if not pot.available or not pot.irrigation.available or not pot.soil_moisture_valid:
                continue
            if state.pots[pot_index].soil_moisture_pct < pot.target_soil_moisture_pct:
                unreachable += (
                    pot.target_soil_moisture_pct - state.pots[pot_index].soil_moisture_pct
                ) / 50.0
        if (
            not caps.nutrient_heater.available
            and simulator.scenario.validity.nutrient_solution_temperature_c
            and state.nutrient_solution_temperature_c
            < targets.target_nutrient_solution_temperature_c
        ):
            unreachable += (
                targets.target_nutrient_solution_temperature_c
                - state.nutrient_solution_temperature_c
            ) / 12.0
        for pot_index, pot in enumerate(simulator.scenario.pots):
            if not pot.available or not pot.heat_mat.available or not pot.soil_temperature_valid:
                continue
            if state.pots[pot_index].soil_temperature_c < pot.target_soil_temperature_c:
                unreachable += (
                    pot.target_soil_temperature_c - state.pots[pot_index].soil_temperature_c
                ) / 12.0

        return float(
            weights.energy * energy_proxy
            + weights.water * water_fraction
            + weights.switching * switches
            + weights.opposing_actuators * opposing
            + weights.constraint_violation * violation
            + weights.unreachable_target * unreachable
        )
