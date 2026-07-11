from __future__ import annotations

from dataclasses import replace

import pytest

from tools.ml.simulator import (
    ControlAction,
    EnvironmentState,
    SequentialEnvironmentSimulator,
)


def _run(simulator: SequentialEnvironmentSimulator, commands: list[ControlAction]):
    return [simulator.step(command).as_dict() for command in commands]


def test_simulator_is_deterministic_for_seed(scenario):
    commands = [
        ControlAction(heater=1.0),
        ControlAction(fan=0.5, humidifier=1.0),
        ControlAction(irrigation=1.0),
    ] * 6
    first = _run(SequentialEnvironmentSimulator(scenario, seed=77), commands)
    second = _run(SequentialEnvironmentSimulator(scenario, seed=77), commands)
    assert first == second


def test_sensor_noise_changes_with_seed_but_latent_dynamics_do_not(scenario):
    first = SequentialEnvironmentSimulator(scenario, seed=1)
    second = SequentialEnvironmentSimulator(scenario, seed=2)
    observed_first = first.step(ControlAction(heater=0.7))
    observed_second = second.step(ControlAction(heater=0.7))
    assert observed_first.as_dict() != observed_second.as_dict()
    assert first.state.as_dict() == second.state.as_dict()


def test_response_lag_is_explicit(scenario):
    simulator = SequentialEnvironmentSimulator(scenario)
    simulator.step(ControlAction(heater=1.0), add_sensor_noise=False)
    assert 0.0 < simulator.effective_action.heater < 1.0


def test_heating_humidification_ventilation_and_irrigation_have_effects(scenario):
    initial = replace(
        scenario.initial_state,
        air_temperature_c=18.0,
        outside_temperature_c=5.0,
        air_humidity_pct=30.0,
        outside_humidity_pct=20.0,
        co2_ppm=1800.0,
        soil_moisture_pct=25.0,
    )
    actuators = replace(
        scenario.actuators,
        heater=replace(
            scenario.actuators.heater, available=True, max_power_w=300.0
        ),
        fan=replace(
            scenario.actuators.fan, available=True, max_airflow_m3_h=120.0
        ),
        humidifier=replace(
            scenario.actuators.humidifier, available=True, max_output_g_h=150.0
        ),
        irrigation_pump=replace(
            scenario.actuators.irrigation_pump,
            available=True,
            flow_ml_s=20.0,
            maximum_pulse_s=5.0,
        ),
    )
    scenario = replace(scenario, initial_state=initial, actuators=actuators)
    idle = SequentialEnvironmentSimulator(scenario)
    heated = SequentialEnvironmentSimulator(scenario)
    humidified = SequentialEnvironmentSimulator(scenario)
    ventilated = SequentialEnvironmentSimulator(scenario)
    irrigated = SequentialEnvironmentSimulator(scenario)
    for _ in range(12):
        idle.step(ControlAction(), add_sensor_noise=False)
        heated.step(ControlAction(heater=1.0), add_sensor_noise=False)
        humidified.step(ControlAction(humidifier=1.0), add_sensor_noise=False)
        ventilated.step(ControlAction(fan=1.0), add_sensor_noise=False)
        irrigated.step(ControlAction(), add_sensor_noise=False)
    irrigated.step(ControlAction(irrigation=1.0), add_sensor_noise=False)

    assert heated.state.air_temperature_c > idle.state.air_temperature_c
    assert humidified.state.air_humidity_pct > idle.state.air_humidity_pct
    assert abs(ventilated.state.co2_ppm - 420.0) < abs(idle.state.co2_ppm - 420.0)
    assert irrigated.state.soil_moisture_pct > idle.state.soil_moisture_pct


def test_soil_dries_slowly_without_pump(scenario):
    simulator = SequentialEnvironmentSimulator(scenario)
    before = simulator.state.soil_moisture_pct
    for _ in range(30):
        simulator.step(ControlAction(), add_sensor_noise=False)
    assert simulator.state.soil_moisture_pct < before


def test_unavailable_actuator_is_masked(scenario):
    missing_heater = replace(
        scenario.actuators.heater, available=False, max_power_w=0.0
    )
    scenario = replace(
        scenario,
        actuators=replace(scenario.actuators, heater=missing_heater),
    )
    simulator = SequentialEnvironmentSimulator(scenario)
    simulator.step(ControlAction(heater=1.0), add_sensor_noise=False)
    assert simulator.previous_command.heater == 0.0
    assert simulator.effective_action.heater == 0.0


@pytest.mark.parametrize("bad_timestep", [0.0, -1.0, float("nan"), float("inf")])
def test_invalid_timestep_is_rejected(scenario, bad_timestep):
    with pytest.raises(ValueError):
        SequentialEnvironmentSimulator(scenario).step(
            ControlAction(), bad_timestep, add_sensor_noise=False
        )
