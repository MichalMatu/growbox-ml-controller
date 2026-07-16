"""Tier B pot substrate physics."""

from __future__ import annotations

from dataclasses import replace

from tools.ml.physics.pots_substrate import (
    PotPhysicsConfig,
    PotPhysicsState,
    evaporation_ml_s,
    step_pot,
    water_ml_to_humidity_pp,
)
from tools.ml.simulator import (
    ControlAction,
    HeatMatCapabilities,
    PotConfig,
    PotCultivation,
    PotState,
    PumpCapabilities,
    SequentialEnvironmentSimulator,
    default_scenario_v2,
)


def _wet_config(**kwargs) -> PotPhysicsConfig:
    base = dict(
        available=True,
        soil_moisture_valid=True,
        soil_temperature_valid=True,
        pot_volume_l=12.0,
        substrate_water_capacity_ml=3000.0,
        transpiration_factor=1.2,
        irrigation_available=True,
        irrigation_flow_ml_s=20.0,
        irrigation_maximum_pulse_s=5.0,
        heat_mat_available=True,
        heat_mat_max_power_w=40.0,
    )
    base.update(kwargs)
    return PotPhysicsConfig(**base)


def test_wetter_soil_evaporates_faster():
    cfg = _wet_config()
    wet = PotPhysicsState(soil_moisture_pct=70.0, soil_temperature_c=22.0)
    dry = PotPhysicsState(soil_moisture_pct=25.0, soil_temperature_c=22.0)
    e_wet = evaporation_ml_s(wet, cfg, air_temperature_c=24.0, air_humidity_pct=45.0)
    e_dry = evaporation_ml_s(dry, cfg, air_temperature_c=24.0, air_humidity_pct=45.0)
    assert e_wet > e_dry * 1.3


def test_irrigation_increases_moisture_and_releases_some_free_water():
    cfg = _wet_config()
    pot = PotPhysicsState(soil_moisture_pct=40.0, soil_temperature_c=20.0)
    result = step_pot(
        pot,
        cfg,
        air_temperature_c=22.0,
        air_humidity_pct=50.0,
        heat_mat_command_0_1=0.0,
        dt_s=10.0,
        irrigation_command_0_1=1.0,
        nutrient_solution_temperature_c=18.0,
        irrigation_ready=True,
    )
    assert result.soil_moisture_pct > 40.0
    assert result.applied_irrigation_ml > 0.0
    assert result.irrigation_free_water_ml > 0.0
    assert result.water_to_air_ml >= result.irrigation_free_water_ml


def test_heat_mat_raises_soil_temperature_module():
    cfg = _wet_config()
    pot = PotPhysicsState(soil_moisture_pct=50.0, soil_temperature_c=18.0)
    cold = step_pot(
        pot,
        cfg,
        air_temperature_c=18.0,
        air_humidity_pct=50.0,
        heat_mat_command_0_1=0.0,
        dt_s=60.0,
    )
    hot = step_pot(
        pot,
        cfg,
        air_temperature_c=18.0,
        air_humidity_pct=50.0,
        heat_mat_command_0_1=1.0,
        dt_s=60.0,
    )
    assert hot.soil_temperature_c > cold.soil_temperature_c


def test_water_ml_to_humidity_scales_with_volume():
    small = water_ml_to_humidity_pp(10.0, growbox_volume_m3=0.5)
    large = water_ml_to_humidity_pp(10.0, growbox_volume_m3=2.0)
    assert small > large


def test_simulator_wet_pot_adds_more_humidity_than_dry():
    wet_pot = PotConfig(
        available=True,
        soil_moisture_valid=True,
        soil_temperature_valid=True,
        irrigation=PumpCapabilities(available=False),
        cultivation=PotCultivation(
            pot_volume_l=12.0,
            substrate_water_capacity_ml=3000.0,
            transpiration_factor=1.5,
        ),
    )
    base = default_scenario_v2(seed=21)
    wet_scene = replace(
        base,
        pots=(wet_pot, base.pots[1], base.pots[2], base.pots[3]),
        initial_state=replace(
            base.initial_state,
            air_humidity_pct=40.0,
            pots=[PotState(soil_moisture_pct=75.0, soil_temperature_c=24.0)] + [PotState()] * 3,
        ),
    )
    dry_scene = replace(
        wet_scene,
        initial_state=replace(
            wet_scene.initial_state,
            pots=[PotState(soil_moisture_pct=20.0, soil_temperature_c=24.0)] + [PotState()] * 3,
        ),
    )
    wet_sim = SequentialEnvironmentSimulator(wet_scene)
    dry_sim = SequentialEnvironmentSimulator(dry_scene)
    for _ in range(20):
        wet_sim.step(ControlAction(), timestep_s=30.0, add_sensor_noise=False)
        dry_sim.step(ControlAction(), timestep_s=30.0, add_sensor_noise=False)
    assert wet_sim.state.air_humidity_pct > dry_sim.state.air_humidity_pct
    assert wet_sim.state.pots[0].soil_moisture_pct < 75.0


def test_inactive_pot_stays_dry_under_irrigation_command():
    scenario = default_scenario_v2(seed=2)
    sim = SequentialEnvironmentSimulator(scenario)
    before = sim.state.pots[2].soil_moisture_pct
    sim.step(ControlAction(irrigation_pot_3=1.0), add_sensor_noise=False)
    assert sim.state.pots[2].soil_moisture_pct == before


def test_heat_mat_still_works_in_simulator():
    base = default_scenario_v2(seed=11)
    pot = PotConfig(
        available=True,
        soil_moisture_valid=True,
        soil_temperature_valid=True,
        heat_mat=HeatMatCapabilities(available=True, max_power_w=40.0),
    )
    scenario = replace(
        base,
        pots=(pot, base.pots[1], base.pots[2], base.pots[3]),
        initial_state=replace(
            base.initial_state,
            pots=[PotState(soil_temperature_c=19.0), PotState(), PotState(), PotState()],
        ),
    )
    sim = SequentialEnvironmentSimulator(scenario)
    before = sim.state.pots[0].soil_temperature_c
    for _ in range(40):
        sim.step(ControlAction(heat_mat_pot_1=1.0), timestep_s=60.0)
    assert sim.state.pots[0].soil_temperature_c > before + 0.3
