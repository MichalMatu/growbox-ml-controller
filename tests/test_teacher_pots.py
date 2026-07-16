from __future__ import annotations

from dataclasses import replace

import pytest

from tools.ml.generate_dataset import random_scenario
from tools.ml.simulator import (
    ControlAction,
    HeaterCapabilities,
    HeatMatCapabilities,
    NutrientHeaterCapabilities,
    PotConfig,
    PumpCapabilities,
    SequentialEnvironmentSimulator,
    default_scenario_v2,
)
from tools.ml.teacher import (
    CostConfig,
    RolloutTeacher,
    build_candidates,
    heat_mat_levels_for_zone,
    irrigation_levels_for_zone,
    nutrient_heater_levels,
)


@pytest.fixture
def scenario_v2():
    return default_scenario_v2(seed=17)


def test_build_candidates_scales_with_active_zones(scenario_v2):
    one_zone = SequentialEnvironmentSimulator(scenario_v2)
    assert len(build_candidates(one_zone)) == 320

    two_zone_scenario = replace(
        scenario_v2,
        pots=(
            PotConfig(available=True, soil_moisture_valid=True, irrigation=PumpCapabilities(True)),
            PotConfig(available=True, soil_moisture_valid=True, irrigation=PumpCapabilities(True)),
            PotConfig(),
            PotConfig(),
        ),
    )
    two_zone = SequentialEnvironmentSimulator(two_zone_scenario)
    assert len(build_candidates(two_zone)) == 640

    zero_zone = SequentialEnvironmentSimulator(
        replace(scenario_v2, pots=(PotConfig(), PotConfig(), PotConfig(), PotConfig()))
    )
    assert len(build_candidates(zero_zone)) == 160


def test_zero_cost_tie_selects_first_candidate(scenario_v2):
    zero = CostConfig(
        temperature_error=0.0,
        humidity_error=0.0,
        co2_error=0.0,
        soil_moisture_error=0.0,
        energy=0.0,
        water=0.0,
        switching=0.0,
        constraint_violation=0.0,
        unreachable_target=0.0,
        terminal_multiplier=0.0,
    )
    result = RolloutTeacher(cost=zero, horizon_steps=1).choose(
        SequentialEnvironmentSimulator(scenario_v2)
    )
    assert result.candidate_index == 0
    assert result.action == ControlAction()


def test_teacher_is_deterministic_and_does_not_advance_source(scenario_v2):
    simulator = SequentialEnvironmentSimulator(scenario_v2)
    before_temp = simulator.state.air_temperature_c
    teacher = RolloutTeacher(horizon_steps=2)
    first = teacher.choose(simulator)
    second = teacher.choose(simulator)
    assert first == second
    assert simulator.state.air_temperature_c == before_temp
    assert simulator.elapsed_s == 0.0


def test_teacher_never_selects_unavailable_outputs(scenario_v2):
    unavailable = replace(
        scenario_v2.actuators,
        heater=HeaterCapabilities(False, 0.0, 0.0),
        fan=replace(scenario_v2.actuators.fan, available=False, max_airflow_m3_h=0.0),
        humidifier=replace(scenario_v2.actuators.humidifier, available=False, max_output_g_h=0.0),
        dehumidifier=replace(scenario_v2.actuators.dehumidifier, available=False),
        cooler=replace(scenario_v2.actuators.cooler, available=False),
        co2_doser=replace(scenario_v2.actuators.co2_doser, available=False),
    )
    pots = tuple(
        replace(pot, irrigation=replace(pot.irrigation, available=False))
        for pot in scenario_v2.pots
    )
    simulator = SequentialEnvironmentSimulator(
        replace(scenario_v2, actuators=unavailable, pots=pots)
    )
    result = RolloutTeacher(horizon_steps=2).choose(simulator)
    assert result.action == ControlAction()


def test_irrigation_blocked_when_soil_at_target(scenario_v2):
    simulator = SequentialEnvironmentSimulator(scenario_v2)
    pot = simulator.scenario.pots[0]
    simulator.state.pots[0].soil_moisture_pct = pot.target_soil_moisture_pct
    assert irrigation_levels_for_zone(simulator, 0) == (0.0,)


def test_irrigation_interval_violation_has_explicit_cost(scenario_v2):
    simulator = SequentialEnvironmentSimulator(scenario_v2)
    simulator.step(ControlAction(irrigation_pot_1=1.0), add_sensor_noise=False)
    teacher = RolloutTeacher(horizon_steps=1)
    irrigation = teacher.evaluate(simulator, ControlAction(irrigation_pot_1=1.0))
    idle = teacher.evaluate(simulator, ControlAction())
    assert irrigation > idle


def test_heating_levels_only_when_below_target(scenario_v2):
    simulator = SequentialEnvironmentSimulator(scenario_v2)
    assert nutrient_heater_levels(simulator) == (0.0,)
    assert heat_mat_levels_for_zone(simulator, 0) == (0.0,)

    cold_nutrient = replace(
        scenario_v2,
        validity=replace(scenario_v2.validity, nutrient_solution_temperature_c=True),
        actuators=replace(
            scenario_v2.actuators,
            nutrient_heater=NutrientHeaterCapabilities(available=True, max_power_w=120.0),
        ),
    )
    cold_sim = SequentialEnvironmentSimulator(cold_nutrient)
    cold_sim.state.nutrient_solution_temperature_c = 16.0
    assert nutrient_heater_levels(cold_sim) == (0.0, 1.0)

    heated_zone = replace(
        scenario_v2.pots[0],
        soil_temperature_valid=True,
        heat_mat=HeatMatCapabilities(available=True, max_power_w=30.0),
        target_soil_temperature_c=24.0,
    )
    soil_sim = SequentialEnvironmentSimulator(
        replace(scenario_v2, pots=(heated_zone,) + scenario_v2.pots[1:])
    )
    soil_sim.state.pots[0].soil_temperature_c = 18.0
    assert heat_mat_levels_for_zone(soil_sim, 0) == (0.0, 1.0)


def test_teacher_can_select_nutrient_heater_when_solution_is_cold(scenario_v2):
    cold = replace(
        scenario_v2,
        validity=replace(scenario_v2.validity, nutrient_solution_temperature_c=True),
        actuators=replace(
            scenario_v2.actuators,
            humidifier=replace(scenario_v2.actuators.humidifier, available=False),
            nutrient_heater=NutrientHeaterCapabilities(available=True, max_power_w=150.0),
        ),
    )
    simulator = SequentialEnvironmentSimulator(cold)
    simulator.state.nutrient_solution_temperature_c = 16.0
    pot = simulator.scenario.pots[0]
    simulator.state.pots[0].soil_moisture_pct = pot.target_soil_moisture_pct
    nutrient_focus = CostConfig(
        temperature_error=0.0,
        humidity_error=0.0,
        co2_error=0.0,
        soil_moisture_error=0.0,
        nutrient_temperature_error=12.0,
        soil_temperature_error=0.0,
        energy=0.0,
        water=0.0,
        switching=0.0,
        constraint_violation=100.0,
        unreachable_target=0.0,
        terminal_multiplier=2.0,
    )
    result = RolloutTeacher(cost=nutrient_focus, horizon_steps=2).choose(simulator)
    assert result.action.nutrient_heater == 1.0
    assert result.action.irrigation_pot_1 == 0.0


def test_random_scenario_supports_zero_to_four_active_zones():
    counts = {len(random_scenario(index, 9000 + index).active_pot_indices()) for index in range(40)}
    assert counts == {0, 1, 2, 3, 4}
