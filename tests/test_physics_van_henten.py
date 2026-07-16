"""Tier A chamber physics — Van Henten backbone."""

from __future__ import annotations

from dataclasses import replace

from tools.ml.physics.van_henten import (
    VanHentenParams,
    humidity_state_from_rh,
    rh_from_humidity_state,
    step_chamber_van_henten,
)
from tools.ml.simulator import (
    ControlAction,
    LightsConfig,
    SequentialEnvironmentSimulator,
    default_scenario_v2,
)


def test_rh_roundtrip_near_nominal():
    params = VanHentenParams()
    for temperature in (15.0, 22.0, 28.0):
        for rh in (40.0, 60.0, 80.0):
            state = humidity_state_from_rh(rh, temperature, params)
            recovered = rh_from_humidity_state(state, temperature, params)
            assert abs(recovered - rh) < 1e-6


def test_heater_raises_temperature_vs_idle():
    common = dict(
        air_temperature_c=20.0,
        air_humidity_pct=55.0,
        co2_ppm=800.0,
        outside_temperature_c=10.0,
        outside_humidity_pct=50.0,
        outside_co2_ppm=420.0,
        u_co2=0.0,
        u_vent=0.5,
        radiation=20.0,
        dt_s=10.0,
    )
    heated, _, _, _ = step_chamber_van_henten(**common, u_heat=120.0)
    idle, _, _, _ = step_chamber_van_henten(**common, u_heat=0.0)
    assert heated > idle


def test_fan_pulls_temperature_toward_outside_when_cold_out():
    warm_in = 28.0
    cold_out = 8.0
    common = dict(
        air_temperature_c=warm_in,
        air_humidity_pct=50.0,
        co2_ppm=900.0,
        outside_temperature_c=cold_out,
        outside_humidity_pct=40.0,
        outside_co2_ppm=420.0,
        u_co2=0.0,
        u_heat=0.0,
        radiation=10.0,
        dt_s=30.0,
    )
    with_fan, _, _, _ = step_chamber_van_henten(**common, u_vent=7.0)
    sealed, _, _, _ = step_chamber_van_henten(**common, u_vent=0.0)
    # Higher vent should cool faster toward cold outside.
    assert with_fan < sealed


def test_simulator_van_henten_default_is_deterministic():
    scenario = default_scenario_v2(seed=3)
    assert scenario.chamber_model == "van_henten"
    a = SequentialEnvironmentSimulator(scenario, seed=3)
    b = SequentialEnvironmentSimulator(scenario, seed=3)
    commands = [ControlAction(heater=0.8, fan=0.2), ControlAction(fan=0.5)] * 5
    trail_a = [a.step(c, add_sensor_noise=False).air_temperature_c for c in commands]
    trail_b = [b.step(c, add_sensor_noise=False).air_temperature_c for c in commands]
    assert trail_a == trail_b


def test_simulator_lights_still_heat_with_van_henten():
    scenario = default_scenario_v2(seed=1)
    scenario = replace(
        scenario,
        actuators=replace(
            scenario.actuators,
            lights=LightsConfig(integrated=True, max_heat_w=300.0),
            heater=replace(scenario.actuators.heater, available=False, max_power_w=0.0),
        ),
        initial_state=replace(scenario.initial_state, lights_active=True, air_temperature_c=18.0),
    )
    on = SequentialEnvironmentSimulator(scenario)
    off = SequentialEnvironmentSimulator(
        replace(scenario, initial_state=replace(scenario.initial_state, lights_active=False))
    )
    for _ in range(12):
        on.step(ControlAction(), add_sensor_noise=False)
        off.step(ControlAction(), add_sensor_noise=False)
    assert on.state.air_temperature_c > off.state.air_temperature_c
