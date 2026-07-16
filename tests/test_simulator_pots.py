from __future__ import annotations

from dataclasses import replace

import pytest

from tools.ml.simulator import (
    ControlAction,
    LightsConfig,
    PotConfig,
    PotState,
    PumpCapabilities,
    SequentialEnvironmentSimulator,
    default_scenario_v2,
)


@pytest.fixture
def scenario_v2():
    return default_scenario_v2(seed=11)


def test_simulator_is_deterministic(scenario_v2):
    commands = [
        ControlAction(heater=1.0),
        ControlAction(fan=0.5),
        ControlAction(irrigation_pot_1=1.0),
    ] * 4
    first = SequentialEnvironmentSimulator(scenario_v2, seed=3)
    second = SequentialEnvironmentSimulator(scenario_v2, seed=3)
    trail_a = [
        first.step(command, add_sensor_noise=False).air_temperature_c for command in commands
    ]
    trail_b = [
        second.step(command, add_sensor_noise=False).air_temperature_c for command in commands
    ]
    assert trail_a == trail_b


def test_inactive_zones_do_not_receive_irrigation(scenario_v2):
    simulator = SequentialEnvironmentSimulator(scenario_v2)
    before = simulator.state.pots[2].soil_moisture_pct
    simulator.step(ControlAction(irrigation_pot_3=1.0), add_sensor_noise=False)
    assert simulator.state.pots[2].soil_moisture_pct == before


def test_active_zone_irrigation_increases_soil_and_humidity(scenario_v2):
    simulator = SequentialEnvironmentSimulator(scenario_v2)
    soil_before = simulator.state.pots[0].soil_moisture_pct
    humidity_before = simulator.state.air_humidity_pct
    simulator.step(ControlAction(irrigation_pot_1=1.0), add_sensor_noise=False)
    assert simulator.state.pots[0].soil_moisture_pct > soil_before
    assert simulator.state.air_humidity_pct >= humidity_before


def test_lights_active_adds_heat(scenario_v2):
    scenario = replace(
        scenario_v2,
        actuators=replace(
            scenario_v2.actuators,
            lights=LightsConfig(integrated=True, max_heat_w=250.0),
        ),
        initial_state=replace(
            scenario_v2.initial_state, lights_active=True, air_temperature_c=20.0
        ),
    )
    heated = SequentialEnvironmentSimulator(scenario)
    idle = SequentialEnvironmentSimulator(
        replace(scenario, initial_state=replace(scenario.initial_state, lights_active=False))
    )
    for _ in range(8):
        heated.step(ControlAction(), add_sensor_noise=False)
        idle.step(ControlAction(), add_sensor_noise=False)
    assert heated.state.air_temperature_c > idle.state.air_temperature_c


def test_mix_and_match_two_zones():
    zone_a = PotConfig(
        available=True, soil_moisture_valid=True, irrigation=PumpCapabilities(available=True)
    )
    zone_b = PotConfig(
        available=True, soil_moisture_valid=True, irrigation=PumpCapabilities(available=True)
    )
    scenario = replace(
        default_scenario_v2(seed=5),
        pots=(zone_a, zone_b, PotConfig(), PotConfig()),
        initial_state=replace(
            default_scenario_v2().initial_state,
            pots=[
                PotState(soil_moisture_pct=35.0),
                PotState(soil_moisture_pct=60.0),
                PotState(),
                PotState(),
            ],
        ),
    )
    simulator = SequentialEnvironmentSimulator(scenario)
    simulator.step(ControlAction(irrigation_pot_1=1.0), add_sensor_noise=False)
    assert simulator.state.pots[0].soil_moisture_pct > 35.0
    # Pot 2 active but not irrigated — only background drying, no irrigation jump.
    assert simulator.state.pots[1].soil_moisture_pct < 60.0
    assert simulator.state.pots[1].soil_moisture_pct > 59.0
