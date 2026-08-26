from __future__ import annotations

from dataclasses import replace

import pytest

from tools.ml.climate_input import ClimateTargets, MeasurementStatus
from tools.ml.climate_simulator import (
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
from tools.ml.climate_teacher import (
    ClimateRolloutTeacher,
    ClimateTeacherConfig,
)


def all_capabilities() -> ClimateActuatorCapabilities:
    return ClimateActuatorCapabilities(
        heater=HeaterCapabilities(True, 240.0, 0.95),
        cooler=CoolerCapabilities(True, 260.0),
        exhaust_fan=ExhaustFanCapabilities(True, 120.0, 0.0),
        humidifier=HumidifierCapabilities(True, 180.0, 0.7),
        dehumidifier=DehumidifierCapabilities(True, 150.0, 0.7),
        co2_doser=Co2DoserCapabilities(True, 3.0),
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


def make_sim(
    state: ClimateState,
    *,
    caps: ClimateActuatorCapabilities | None = None,
    lag: ClimateResponseLag | None = None,
) -> ClimateSimulator:
    env = ClimateEnvironmentParameters(
        growbox_volume_m3=0.8,
        thermal_mass_j_per_k=30_000.0,
        heat_loss_w_per_k=0.0,
        air_leak_rate_ach=0.0,
        outside_co2_ppm=420.0,
        crop_dry_weight=0.0,
        lights_max_heat_w=0.0,
        radiation_lights_off=0.0,
        radiation_lights_full=0.0,
    )
    return ClimateSimulator(
        ClimateScenario(
            scenario_id="teacher-test",
            seed=42,
            initial_state=state,
            environment=env,
            actuators=caps or all_capabilities(),
            response_lag=lag or zero_lag(),
            timestep_s=10.0,
        )
    )


def fast_teacher() -> ClimateRolloutTeacher:
    return ClimateRolloutTeacher(
        config=ClimateTeacherConfig(horizon_s=120.0, rollout_dt_s=10.0, coordinate_passes=2)
    )


def test_cold_case_requests_heating_without_cooling() -> None:
    sim = make_sim(
        ClimateState(
            air_temperature_c=15.0,
            relative_humidity_pct=60.0,
            outside_temperature_c=15.0,
            outside_humidity_pct=60.0,
        )
    )
    result = fast_teacher().choose(sim, ClimateTargets(air_temperature_c=25.0))
    assert result.action.heater > 0.0
    assert result.action.cooler == 0.0


def test_hot_case_requests_cooling_without_heating() -> None:
    sim = make_sim(
        ClimateState(
            air_temperature_c=35.0,
            relative_humidity_pct=60.0,
            outside_temperature_c=35.0,
            outside_humidity_pct=60.0,
        )
    )
    result = fast_teacher().choose(sim, ClimateTargets(air_temperature_c=24.0))
    assert result.action.cooler > 0.0
    assert result.action.heater == 0.0


def test_rh_mode_uses_only_the_needed_humidity_actuator() -> None:
    dry = make_sim(
        ClimateState(
            air_temperature_c=24.0,
            relative_humidity_pct=30.0,
            outside_temperature_c=24.0,
            outside_humidity_pct=30.0,
        )
    )
    wet = make_sim(
        ClimateState(
            air_temperature_c=24.0,
            relative_humidity_pct=88.0,
            outside_temperature_c=24.0,
            outside_humidity_pct=88.0,
        )
    )
    targets = ClimateTargets(air_temperature_c=24.0, relative_humidity_pct=60.0)
    dry_action = fast_teacher().choose(dry, targets, humidity_control_mode="RH").action
    wet_action = fast_teacher().choose(wet, targets, humidity_control_mode="RH").action
    assert dry_action.humidifier > 0.0
    assert dry_action.dehumidifier == 0.0
    assert wet_action.dehumidifier > 0.0
    assert wet_action.humidifier == 0.0


def test_vpd_mode_uses_vpd_not_rh_target() -> None:
    high_vpd = make_sim(
        ClimateState(
            air_temperature_c=30.0,
            relative_humidity_pct=35.0,
            outside_temperature_c=30.0,
            outside_humidity_pct=35.0,
        )
    )
    low_vpd = make_sim(
        ClimateState(
            air_temperature_c=22.0,
            relative_humidity_pct=92.0,
            outside_temperature_c=22.0,
            outside_humidity_pct=92.0,
        )
    )
    targets = ClimateTargets(
        air_temperature_c=30.0,
        relative_humidity_pct=20.0,
        air_vpd_kpa=1.2,
    )
    dry_action = fast_teacher().choose(high_vpd, targets, humidity_control_mode="VPD").action
    humid_targets = replace(targets, air_temperature_c=22.0, relative_humidity_pct=20.0)
    wet_action = fast_teacher().choose(
        low_vpd, humid_targets, humidity_control_mode="VPD"
    ).action
    assert dry_action.humidifier > 0.0
    assert dry_action.dehumidifier == 0.0
    assert wet_action.dehumidifier > 0.0
    assert wet_action.humidifier == 0.0


def test_co2_dosing_requires_enabled_control_and_usable_sensor() -> None:
    state = ClimateState(
        air_temperature_c=24.0,
        relative_humidity_pct=60.0,
        co2_ppm=450.0,
        outside_temperature_c=24.0,
        outside_humidity_pct=60.0,
    )
    targets = ClimateTargets(air_temperature_c=24.0, co2_enabled=True, co2_ppm=1_100.0)
    enabled = fast_teacher().choose(make_sim(state), targets).action
    assert enabled.co2_doser > 0.0

    disabled = fast_teacher().choose(
        make_sim(state), replace(targets, co2_enabled=False)
    ).action
    assert disabled.co2_doser == 0.0

    invalid = fast_teacher().choose(
        make_sim(state),
        targets,
        status={"co2_ppm": MeasurementStatus(valid=False, age_ms=0)},
    ).action
    assert invalid.co2_doser == 0.0


def test_required_sensor_failure_returns_zero_safe_label() -> None:
    sim = make_sim(ClimateState())
    result = fast_teacher().choose(
        sim,
        ClimateTargets(),
        status={"air_temperature_c": MeasurementStatus(valid=False, age_ms=0)},
    )
    assert result.safe_fallback
    assert result.action.as_tuple() == (0.0,) * 6
    assert result.evaluations == 0


def test_exhaust_uses_outside_air_only_when_outside_measurements_are_usable() -> None:
    caps = replace(all_capabilities(), cooler=CoolerCapabilities(False, 0.0))
    state = ClimateState(
        air_temperature_c=33.0,
        relative_humidity_pct=60.0,
        outside_temperature_c=12.0,
        outside_humidity_pct=60.0,
    )
    targets = ClimateTargets(air_temperature_c=24.0, relative_humidity_pct=60.0)
    available = fast_teacher().choose(make_sim(state, caps=caps), targets).action
    assert available.exhaust_fan > 0.0

    unavailable = fast_teacher().choose(
        make_sim(state, caps=caps),
        targets,
        status={"outside_temperature_c": MeasurementStatus(valid=False, age_ms=0)},
    ).action
    assert unavailable.exhaust_fan == 0.0


def test_teacher_never_returns_opposing_actuator_pairs() -> None:
    sim = make_sim(
        ClimateState(
            air_temperature_c=29.0,
            relative_humidity_pct=78.0,
            co2_ppm=500.0,
            outside_temperature_c=20.0,
            outside_humidity_pct=45.0,
        )
    )
    action = fast_teacher().choose(
        sim,
        ClimateTargets(
            air_temperature_c=24.0,
            relative_humidity_pct=60.0,
            co2_enabled=True,
            co2_ppm=1_000.0,
        ),
    ).action
    assert not (action.heater > 0.0 and action.cooler > 0.0)
    assert not (action.humidifier > 0.0 and action.dehumidifier > 0.0)


def test_horizon_must_cover_three_times_longest_actuator_lag() -> None:
    lag = replace(zero_lag(), heater_s=120.0)
    sim = make_sim(ClimateState(), lag=lag)
    teacher = ClimateRolloutTeacher(config=ClimateTeacherConfig(horizon_s=300.0))
    with pytest.raises(ValueError, match="3x longest actuator lag"):
        teacher.choose(sim, ClimateTargets())


def test_teacher_is_deterministic_for_identical_state() -> None:
    sim = make_sim(
        ClimateState(
            air_temperature_c=28.0,
            relative_humidity_pct=70.0,
            co2_ppm=600.0,
            outside_temperature_c=18.0,
            outside_humidity_pct=50.0,
        )
    )
    targets = ClimateTargets(
        air_temperature_c=24.0,
        relative_humidity_pct=60.0,
        co2_enabled=True,
        co2_ppm=900.0,
    )
    teacher = fast_teacher()
    left = teacher.choose(sim, targets)
    right = teacher.choose(sim.clone(), targets)
    assert left == right
