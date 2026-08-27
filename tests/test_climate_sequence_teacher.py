from __future__ import annotations

from dataclasses import replace

import pytest

from tools.ml.climate_input import ClimateTargets, MeasurementStatus
from tools.ml.climate_sequence_teacher import (
    DEFAULT_MOVE_BLOCK_STEPS,
    ClimateSequenceRolloutTeacher,
    ClimateSequenceTeacherConfig,
)
from tools.ml.climate_simulator import (
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
            scenario_id="sequence-teacher-test",
            seed=42,
            initial_state=state,
            environment=env,
            actuators=caps or all_capabilities(),
            response_lag=lag or zero_lag(),
            timestep_s=10.0,
        )
    )


def fast_config() -> ClimateSequenceTeacherConfig:
    return ClimateSequenceTeacherConfig(
        horizon_s=60.0,
        rollout_dt_s=10.0,
        move_block_steps=(1, 1, 1, 3),
        coordinate_passes=1,
    )


def test_default_move_blocks_cover_300_second_horizon() -> None:
    config = ClimateSequenceTeacherConfig()
    assert DEFAULT_MOVE_BLOCK_STEPS == (1, 1, 1, 1, 2, 2, 3, 4, 5, 10)
    assert sum(config.move_block_steps) * config.rollout_dt_s == config.horizon_s


def test_full_sequence_config_uses_one_action_per_rollout_step() -> None:
    config = ClimateSequenceTeacherConfig.full_sequence()
    assert len(config.move_block_steps) == 30
    assert config.move_block_steps == (1,) * 30


def test_config_rejects_move_blocks_that_do_not_cover_horizon() -> None:
    with pytest.raises(ValueError, match="cover the complete horizon"):
        ClimateSequenceTeacherConfig(
            horizon_s=60.0,
            rollout_dt_s=10.0,
            move_block_steps=(1, 1, 1),
        )


def test_cold_case_returns_receding_horizon_first_action_and_valid_plan() -> None:
    sim = make_sim(
        ClimateState(
            air_temperature_c=15.0,
            relative_humidity_pct=60.0,
            outside_temperature_c=15.0,
            outside_humidity_pct=60.0,
        )
    )
    result = ClimateSequenceRolloutTeacher(config=fast_config()).choose(
        sim, ClimateTargets(air_temperature_c=25.0)
    )

    assert result.action == result.plan[0]
    assert len(result.plan) == len(result.move_block_steps) == 4
    assert sum(result.move_block_steps) == 6
    assert result.action.heater > 0.0
    assert result.action.cooler == 0.0
    assert result.evaluations > 2
    assert result.tracking_cost >= 0.0
    assert result.secondary_cost >= 0.0
    for action in result.plan:
        assert not (action.heater > 0.0 and action.cooler > 0.0)
        assert not (action.humidifier > 0.0 and action.dehumidifier > 0.0)


def test_required_sensor_failure_returns_zero_safe_plan() -> None:
    sim = make_sim(ClimateState())
    result = ClimateSequenceRolloutTeacher(config=fast_config()).choose(
        sim,
        ClimateTargets(),
        status={"air_temperature_c": MeasurementStatus(valid=False, age_ms=0)},
    )

    assert result.safe_fallback
    assert result.action.as_tuple() == (0.0,) * 6
    assert all(action.as_tuple() == (0.0,) * 6 for action in result.plan)
    assert result.evaluations == 0


def test_co2_plan_respects_disabled_control() -> None:
    state = ClimateState(
        air_temperature_c=24.0,
        relative_humidity_pct=60.0,
        co2_ppm=450.0,
        outside_temperature_c=24.0,
        outside_humidity_pct=60.0,
    )
    enabled_targets = ClimateTargets(
        air_temperature_c=24.0,
        relative_humidity_pct=60.0,
        co2_enabled=True,
        co2_ppm=1_100.0,
    )
    disabled_targets = replace(enabled_targets, co2_enabled=False)

    enabled = ClimateSequenceRolloutTeacher(config=fast_config()).choose(
        make_sim(state), enabled_targets
    )
    disabled = ClimateSequenceRolloutTeacher(config=fast_config()).choose(
        make_sim(state), disabled_targets
    )

    assert any(action.co2_doser > 0.0 for action in enabled.plan)
    assert all(action.co2_doser == 0.0 for action in disabled.plan)


def test_evaluate_plan_rejects_wrong_number_of_blocks() -> None:
    teacher = ClimateSequenceRolloutTeacher(config=fast_config())
    with pytest.raises(ValueError, match="plan has 1 blocks; expected 4"):
        teacher.evaluate_plan(
            make_sim(ClimateState()),
            (ClimateAction(),),
            ClimateTargets(),
        )
