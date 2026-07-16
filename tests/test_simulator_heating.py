"""Simulator v3 heating dynamics smoke tests."""

from __future__ import annotations

from dataclasses import replace

from tools.ml.simulator import (
    ControlAction,
    EnvironmentState,
    GlobalActuators,
    HeatMatCapabilities,
    NutrientHeaterCapabilities,
    PotConfig,
    PotState,
    SequentialEnvironmentSimulator,
    default_scenario_v2,
)


def test_nutrient_heater_raises_solution_temperature():
    scenario = replace(
        default_scenario_v2(seed=7),
        initial_state=EnvironmentState(
            nutrient_solution_temperature_c=18.0,
            outside_temperature_c=10.0,
        ),
        actuators=GlobalActuators(
            nutrient_heater=NutrientHeaterCapabilities(
                available=True, max_power_w=200.0, efficiency=1.0
            )
        ),
    )
    simulator = SequentialEnvironmentSimulator(scenario)
    before = simulator.state.nutrient_solution_temperature_c
    for _ in range(30):
        simulator.step(ControlAction(nutrient_heater=1.0), timestep_s=60.0)
    after = simulator.state.nutrient_solution_temperature_c
    assert after > before + 0.5


def test_heat_mat_raises_soil_temperature():
    base = default_scenario_v2(seed=11)
    zone_one = PotConfig(
        available=True,
        soil_moisture_valid=True,
        soil_temperature_valid=True,
        heat_mat=HeatMatCapabilities(available=True, max_power_w=40.0),
    )
    scenario = replace(
        base,
        pots=(zone_one, base.pots[1], base.pots[2], base.pots[3]),
        initial_state=EnvironmentState(
            pots=[PotState(soil_temperature_c=19.0), PotState(), PotState(), PotState()]
        ),
    )
    simulator = SequentialEnvironmentSimulator(scenario)
    before = simulator.state.pots[0].soil_temperature_c
    for _ in range(40):
        simulator.step(ControlAction(heat_mat_pot_1=1.0), timestep_s=60.0)
    after = simulator.state.pots[0].soil_temperature_c
    assert after > before + 0.3
