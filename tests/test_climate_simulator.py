from __future__ import annotations

import math
from dataclasses import replace

from tools.ml.climate_simulator import (
    CLIMATE_OUTPUT_NAMES,
    ClimateAction,
    ClimateActuatorCapabilities,
    ClimateEnvironmentParameters,
    ClimateResponseLag,
    ClimateScenario,
    ClimateSimulator,
    ClimateState,
    Co2DoserCapabilities,
    CoolerCapabilities,
    DehumidifierCapabilities,
    ExhaustFanCapabilities,
    HeaterCapabilities,
    HumidifierCapabilities,
)


def zero_lag() -> ClimateResponseLag:
    return ClimateResponseLag(
        heater_s=0.0,
        cooler_s=0.0,
        exhaust_fan_s=0.0,
        humidifier_s=0.0,
        dehumidifier_s=0.0,
        co2_doser_s=0.0,
    )


def isolated_environment(**changes: float) -> ClimateEnvironmentParameters:
    base = ClimateEnvironmentParameters(
        growbox_volume_m3=0.8,
        thermal_mass_j_per_k=35_000.0,
        heat_loss_w_per_k=0.0,
        air_leak_rate_ach=0.0,
        outside_co2_ppm=420.0,
        crop_dry_weight=0.0,
        lights_max_heat_w=120.0,
        radiation_lights_off=0.0,
        radiation_lights_full=80.0,
    )
    return replace(base, **changes)


def all_capabilities() -> ClimateActuatorCapabilities:
    return ClimateActuatorCapabilities(
        heater=HeaterCapabilities(available=True, max_power_w=180.0, efficiency=0.92),
        cooler=CoolerCapabilities(available=True, max_cooling_w=200.0),
        exhaust_fan=ExhaustFanCapabilities(
            available=True,
            max_airflow_m3_h=90.0,
            minimum_command=0.0,
        ),
        humidifier=HumidifierCapabilities(
            available=True,
            max_output_g_h=110.0,
            delivery_efficiency=0.55,
        ),
        dehumidifier=DehumidifierCapabilities(
            available=True,
            max_removal_g_h=80.0,
            delivery_efficiency=0.55,
        ),
        co2_doser=Co2DoserCapabilities(available=True, max_injection_ppm_s=2.0),
    )


def scenario(
    *,
    state: ClimateState | None = None,
    environment: ClimateEnvironmentParameters | None = None,
    actuators: ClimateActuatorCapabilities | None = None,
    lag: ClimateResponseLag | None = None,
) -> ClimateScenario:
    return ClimateScenario(
        scenario_id="test",
        seed=123,
        initial_state=state or ClimateState(),
        environment=environment or isolated_environment(),
        actuators=actuators or all_capabilities(),
        response_lag=lag or zero_lag(),
        timestep_s=5.0,
    )


def run_for(
    sim: ClimateSimulator,
    action: ClimateAction,
    seconds: float,
    *,
    dt: float = 5.0,
    light_level: float | None = None,
) -> ClimateState:
    steps = int(round(seconds / dt))
    assert math.isclose(steps * dt, seconds)
    result = sim.observe()
    for _ in range(steps):
        result = sim.step(action, timestep_s=dt, light_level=light_level)
    return result


def test_contract_surface_is_climate_only() -> None:
    assert CLIMATE_OUTPUT_NAMES == (
        "heater",
        "cooler",
        "exhaust_fan",
        "humidifier",
        "dehumidifier",
        "co2_doser",
    )
    action = ClimateAction()
    assert not hasattr(action, "light")
    assert not hasattr(action, "circulation_fan")
    assert not any("pot" in name or "irrigation" in name for name in action.__dataclass_fields__)


def test_heater_and_cooler_move_temperature_in_opposite_directions() -> None:
    base = scenario(state=ClimateState(air_temperature_c=22.0, outside_temperature_c=22.0))
    neutral = run_for(ClimateSimulator(base), ClimateAction(), 180.0)
    heated = run_for(ClimateSimulator(base), ClimateAction(heater=1.0), 180.0)
    cooled = run_for(ClimateSimulator(base), ClimateAction(cooler=1.0), 180.0)
    assert heated.air_temperature_c > neutral.air_temperature_c + 0.5
    assert cooled.air_temperature_c < neutral.air_temperature_c - 0.5


def test_humidifier_and_dehumidifier_move_rh_in_opposite_directions() -> None:
    base = scenario(
        state=ClimateState(
            air_temperature_c=24.0,
            relative_humidity_pct=55.0,
            outside_temperature_c=24.0,
            outside_humidity_pct=55.0,
        )
    )
    neutral = run_for(ClimateSimulator(base), ClimateAction(), 180.0)
    humidified = run_for(ClimateSimulator(base), ClimateAction(humidifier=1.0), 180.0)
    dried = run_for(ClimateSimulator(base), ClimateAction(dehumidifier=1.0), 180.0)
    assert humidified.relative_humidity_pct > neutral.relative_humidity_pct + 1.0
    assert dried.relative_humidity_pct < neutral.relative_humidity_pct - 1.0


def test_exhaust_moves_all_air_variables_toward_outside_boundary() -> None:
    initial = ClimateState(
        air_temperature_c=30.0,
        relative_humidity_pct=80.0,
        co2_ppm=1_200.0,
        outside_temperature_c=12.0,
        outside_humidity_pct=30.0,
    )
    base = scenario(state=initial)
    neutral = run_for(ClimateSimulator(base), ClimateAction(), 300.0)
    exhausted = run_for(ClimateSimulator(base), ClimateAction(exhaust_fan=1.0), 300.0)
    assert abs(exhausted.air_temperature_c - initial.outside_temperature_c) < abs(
        neutral.air_temperature_c - initial.outside_temperature_c
    )
    assert abs(exhausted.relative_humidity_pct - initial.outside_humidity_pct) < abs(
        neutral.relative_humidity_pct - initial.outside_humidity_pct
    )
    assert abs(exhausted.co2_ppm - base.environment.outside_co2_ppm) < abs(
        neutral.co2_ppm - base.environment.outside_co2_ppm
    )


def test_co2_dosing_is_a_rate_and_is_timestep_invariant() -> None:
    initial = ClimateState(
        air_temperature_c=24.0,
        relative_humidity_pct=55.0,
        co2_ppm=600.0,
        outside_temperature_c=24.0,
        outside_humidity_pct=55.0,
    )
    base = scenario(state=initial)
    fine = run_for(ClimateSimulator(base), ClimateAction(co2_doser=0.5), 120.0, dt=1.0)
    coarse = run_for(ClimateSimulator(base), ClimateAction(co2_doser=0.5), 120.0, dt=10.0)
    expected = initial.co2_ppm + 0.5 * base.actuators.co2_doser.max_injection_ppm_s * 120.0
    assert math.isclose(fine.co2_ppm, expected, abs_tol=1e-6)
    assert math.isclose(coarse.co2_ppm, expected, abs_tol=1e-6)
    assert math.isclose(fine.co2_ppm, coarse.co2_ppm, abs_tol=1e-6)


def test_light_level_is_context_and_adds_heat_once() -> None:
    initial = ClimateState(air_temperature_c=22.0, outside_temperature_c=22.0)
    base = scenario(state=initial)
    dark = run_for(ClimateSimulator(base), ClimateAction(), 300.0, light_level=0.0)
    lit = run_for(ClimateSimulator(base), ClimateAction(), 300.0, light_level=1.0)
    assert lit.air_temperature_c > dark.air_temperature_c + 0.5
    assert math.isclose(lit.light_level, 1.0)


def test_general_trajectory_is_materially_stable_across_supported_timesteps() -> None:
    initial = ClimateState(
        air_temperature_c=27.0,
        relative_humidity_pct=68.0,
        co2_ppm=900.0,
        outside_temperature_c=18.0,
        outside_humidity_pct=45.0,
        light_level=0.4,
    )
    env = isolated_environment(
        heat_loss_w_per_k=7.0,
        air_leak_rate_ach=0.25,
        crop_dry_weight=0.0025,
    )
    base = scenario(
        state=initial,
        environment=env,
        lag=ClimateResponseLag(),
    )
    action = ClimateAction(heater=0.25, exhaust_fan=0.35, humidifier=0.2, co2_doser=0.1)
    fine = run_for(ClimateSimulator(base), action, 300.0, dt=2.0, light_level=0.4)
    coarse = run_for(ClimateSimulator(base), action, 300.0, dt=10.0, light_level=0.4)
    assert abs(fine.air_temperature_c - coarse.air_temperature_c) < 0.2
    assert abs(fine.relative_humidity_pct - coarse.relative_humidity_pct) < 1.0
    assert abs(fine.co2_ppm - coarse.co2_ppm) < 15.0


def test_supported_stress_run_stays_finite_and_bounded() -> None:
    initial = ClimateState(
        air_temperature_c=34.0,
        relative_humidity_pct=88.0,
        co2_ppm=1_800.0,
        outside_temperature_c=-5.0,
        outside_humidity_pct=95.0,
        light_level=1.0,
    )
    env = isolated_environment(
        heat_loss_w_per_k=20.0,
        air_leak_rate_ach=1.5,
        crop_dry_weight=0.005,
        lights_max_heat_w=300.0,
    )
    sim = ClimateSimulator(scenario(state=initial, environment=env))
    result = run_for(
        sim,
        ClimateAction(exhaust_fan=0.8, dehumidifier=0.6, cooler=0.4, co2_doser=0.2),
        600.0,
        dt=5.0,
        light_level=1.0,
    )
    assert math.isfinite(result.air_temperature_c)
    assert math.isfinite(result.relative_humidity_pct)
    assert math.isfinite(result.co2_ppm)
    assert -30.0 <= result.air_temperature_c <= 70.0
    assert 0.0 <= result.relative_humidity_pct <= 100.0
    assert 250.0 <= result.co2_ppm <= 5_000.0


def test_clone_replays_identically_without_sensor_noise() -> None:
    sim = ClimateSimulator(scenario())
    run_for(sim, ClimateAction(heater=0.3, exhaust_fan=0.2), 60.0)
    clone = sim.clone()
    action = ClimateAction(humidifier=0.25, co2_doser=0.1)
    left = run_for(sim, action, 120.0)
    right = run_for(clone, action, 120.0)
    assert left == right
