"""Open-loop calibration estimators and apply-to-scenario."""

from __future__ import annotations

import math

from tools.ml.calibration import (
    apply_estimates_to_scenario,
    calibration_protocol,
    estimate_co2_dose_ppm,
    estimate_effective_ach_from_fan,
    estimate_humidifier_g_h,
    estimate_substrate_capacity_ml,
    estimate_thermal_mass_from_heater,
    protocol_as_markdown,
)
from tools.ml.physics.psychrometrics import air_moisture_capacity_g, sat_absolute_humidity_g_m3
from tools.ml.simulator import default_scenario_v2


def test_protocol_nonempty():
    steps = calibration_protocol()
    assert len(steps) >= 5
    assert "heater" in protocol_as_markdown().lower()


def test_thermal_mass_positive_from_heater_series():
    series = {
        "t_s": [0.0, 60.0, 120.0, 300.0],
        "air_temperature_c": [20.0, 20.5, 21.0, 22.5],
    }
    est = estimate_thermal_mass_from_heater(series, heater_power_w=180.0, heater_efficiency=0.92)
    assert math.isfinite(est.value)
    assert est.value > 1000.0


def test_ach_from_cooling_series():
    series = {
        "t_s": [0.0, 120.0, 300.0],
        "air_temperature_c": [28.0, 24.0, 20.0],
        "outside_temperature_c": [14.0, 14.0, 14.0],
    }
    est = estimate_effective_ach_from_fan(series, growbox_volume_m3=0.8)
    assert math.isfinite(est.value)
    assert est.value > 0.1


def test_ach_requires_outside_temperature():
    est = estimate_effective_ach_from_fan(
        {"t_s": [0.0, 300.0], "air_temperature_c": [28.0, 20.0]},
        growbox_volume_m3=0.8,
    )
    assert not math.isfinite(est.value)


def test_humidifier_and_co2_and_soil():
    humid = estimate_humidifier_g_h(
        {
            "t_s": [0.0, 180.0],
            "air_humidity_pct": [40.0, 55.0],
            "air_temperature_c": [24.0, 24.0],
        },
        growbox_volume_m3=0.8,
    )
    assert math.isfinite(humid.value) and humid.value > 1.0

    co2 = estimate_co2_dose_ppm(co2_before_ppm=600.0, co2_after_ppm=820.0, pulses=2)
    assert abs(co2.value - 110.0) < 1.0

    cap = estimate_substrate_capacity_ml(
        soil_before_pct=35.0, soil_after_pct=50.0, applied_ml=100.0
    )
    # retained 98 ml → Δ15% → capacity ≈ 98*100/15
    assert abs(cap.value - (98.0 * 100.0 / 15.0)) < 1.0


def test_apply_estimates_updates_scenario():
    scenario = default_scenario_v2()
    estimates = [
        estimate_thermal_mass_from_heater(
            {"t_s": [0.0, 300.0], "air_temperature_c": [20.0, 23.0]},
            heater_power_w=180.0,
        ),
        estimate_co2_dose_ppm(co2_before_ppm=500.0, co2_after_ppm=650.0, pulses=1),
        estimate_substrate_capacity_ml(soil_before_pct=40.0, soil_after_pct=55.0, applied_ml=80.0),
    ]
    calibrated = apply_estimates_to_scenario(scenario, estimates)
    assert calibrated.environment.thermal_mass_j_per_k != scenario.environment.thermal_mass_j_per_k
    assert calibrated.actuators.co2_doser.dose_ppm_per_full_pulse == estimates[1].value
    assert calibrated.pots[0].cultivation.substrate_water_capacity_ml == estimates[2].value


def test_psychrometrics_capacity_rises_with_temperature():
    cold = air_moisture_capacity_g(1.0, 10.0)
    warm = air_moisture_capacity_g(1.0, 30.0)
    assert warm > cold
    # ~room temp: order 10–30 g/m³
    assert 10.0 < sat_absolute_humidity_g_m3(25.0) < 30.0


def test_estimators_reject_nonsensical_series():
    cool_down = estimate_thermal_mass_from_heater(
        {"t_s": [0.0, 300.0], "air_temperature_c": [22.0, 20.0]},
        heater_power_w=180.0,
    )
    assert not math.isfinite(cool_down.value)

    no_rh = estimate_humidifier_g_h(
        {"t_s": [0.0, 180.0], "air_humidity_pct": [50.0, 48.0], "air_temperature_c": [24.0, 24.0]},
        growbox_volume_m3=0.8,
    )
    assert not math.isfinite(no_rh.value)

    no_co2 = estimate_co2_dose_ppm(co2_before_ppm=800.0, co2_after_ppm=790.0, pulses=1)
    assert not math.isfinite(no_co2.value)

    away = estimate_effective_ach_from_fan(
        {
            "t_s": [0.0, 300.0],
            "air_temperature_c": [20.0, 24.0],
            "outside_temperature_c": [14.0, 14.0],
        },
        growbox_volume_m3=0.8,
    )
    assert not math.isfinite(away.value)


def test_calibrated_thermal_mass_slows_van_henten_heating():
    from dataclasses import replace

    from tools.ml.simulator import ControlAction, SequentialEnvironmentSimulator

    base = default_scenario_v2(seed=11)
    light = replace(base, environment=replace(base.environment, thermal_mass_j_per_k=20_000.0))
    heavy = replace(base, environment=replace(base.environment, thermal_mass_j_per_k=80_000.0))
    sim_light = SequentialEnvironmentSimulator(light, seed=11)
    sim_heavy = SequentialEnvironmentSimulator(heavy, seed=11)
    for _ in range(30):
        sim_light.step(ControlAction(heater=1.0), add_sensor_noise=False)
        sim_heavy.step(ControlAction(heater=1.0), add_sensor_noise=False)
    assert sim_light.state.air_temperature_c > sim_heavy.state.air_temperature_c + 0.3
