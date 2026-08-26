from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np

from tools.ml.climate_benchmark import ClimateBenchmarkConfig, run_closed_loop_benchmark
from tools.ml.climate_input import ClimateTargets, MeasurementStatus
from tools.ml.climate_model_artifact import load_portable_model
from tools.ml.climate_policy import (
    ML_REQUEST_DEADZONE,
    ClimateRulePolicy,
    apply_climate_safety,
    apply_ml_request_deadzone,
    arbitrate_climate_action,
)
from tools.ml.climate_scenarios import (
    REQUIRED_SCENARIO_FAMILIES,
    ClimateProfile,
    build_training_episode,
)
from tools.ml.climate_simulator import ClimateAction, ClimateState

ROOT = Path(__file__).resolve().parents[1]
WEIGHTS = ROOT / "reports" / "ml" / "climate_v6_model_seed1847.npz"
METADATA = ROOT / "reports" / "ml" / "climate_v6_model_seed1847.json"


def _profile(*, temperature: float = 24.0, humidity: float = 60.0) -> ClimateProfile:
    return ClimateProfile(
        name="test",
        targets=ClimateTargets(
            air_temperature_c=temperature,
            relative_humidity_pct=humidity,
            air_vpd_kpa=1.2,
            co2_enabled=False,
            co2_ppm=800.0,
        ),
        humidity_control_mode="RH",
        light_level=0.0,
    )


def test_rule_policy_heats_cold_air_without_conflicting_cooling() -> None:
    episode = build_training_episode("cold_heating", 0, 1234)
    state = replace(episode.scenario.initial_state, air_temperature_c=16.0)
    action = ClimateRulePolicy().choose(episode.scenario, state, _profile(temperature=25.0))
    assert action.heater > 0.0
    assert action.cooler == 0.0


def test_rule_policy_uses_exhaust_when_outside_air_is_helpful() -> None:
    episode = build_training_episode("outside_helpful", 0, 2222)
    state = replace(
        episode.scenario.initial_state,
        air_temperature_c=31.0,
        outside_temperature_c=16.0,
        relative_humidity_pct=62.0,
        outside_humidity_pct=58.0,
    )
    action = ClimateRulePolicy().choose(episode.scenario, state, _profile(temperature=24.0))
    assert action.exhaust_fan > 0.0


def test_arbitration_removes_opposing_actuators() -> None:
    episode = build_training_episode("cold_heating", 0, 3333)
    result = arbitrate_climate_action(
        ClimateAction(heater=0.4, cooler=0.8, humidifier=0.7, dehumidifier=0.2),
        episode.scenario,
    )
    assert result.action.heater == 0.0
    assert result.action.cooler == 0.8
    assert result.action.humidifier == 0.7
    assert result.action.dehumidifier == 0.0
    assert len(result.interventions) == 2


def test_ml_request_deadzone_turns_sigmoid_tails_off() -> None:
    assert ML_REQUEST_DEADZONE == 0.05
    action = apply_ml_request_deadzone(
        ClimateAction(
            heater=0.001,
            cooler=0.05,
            exhaust_fan=0.05001,
            humidifier=0.02,
            dehumidifier=0.0,
            co2_doser=0.049,
        )
    )
    assert action.heater == 0.0
    assert action.cooler == 0.0
    assert action.exhaust_fan == 0.05001
    assert action.humidifier == 0.0
    assert action.dehumidifier == 0.0
    assert action.co2_doser == 0.0

    episode = build_training_episode("cold_heating", 0, 3334)
    arbitration = arbitrate_climate_action(action, episode.scenario)
    assert not arbitration.interventions


def test_ml_request_deadzone_rejects_invalid_threshold() -> None:
    try:
        apply_ml_request_deadzone(ClimateAction(), threshold=1.0)
    except ValueError as exc:
        assert "dead-zone" in str(exc)
    else:
        raise AssertionError("invalid ML dead-zone must be rejected")


def test_safety_zeros_commands_when_required_sensor_is_stale() -> None:
    episode = build_training_episode("sensor_fault", 0, 4444)
    state = ClimateState(
        air_temperature_c=28.0,
        relative_humidity_pct=70.0,
        co2_ppm=600.0,
        outside_temperature_c=18.0,
        outside_humidity_pct=50.0,
        light_level=0.8,
    )
    result = apply_climate_safety(
        ClimateAction(heater=0.5, exhaust_fan=0.5, humidifier=0.5),
        episode.scenario,
        state,
        _profile(),
        status={"air_temperature_c": MeasurementStatus(valid=True, age_ms=60_000)},
    )
    np.testing.assert_array_equal(result.action.as_tuple(), ClimateAction().as_tuple())
    assert "required_sensor_unusable" in result.interventions


def test_quick_closed_loop_benchmark_is_finite_and_covers_all_policies() -> None:
    model = load_portable_model(WEIGHTS, METADATA)
    report = run_closed_loop_benchmark(model, config=ClimateBenchmarkConfig.quick(seed=55_001))
    assert set(report.aggregate) == {"rule", "teacher", "ml"}
    family_count = len(REQUIRED_SCENARIO_FAMILIES)
    assert len(report.families) == family_count
    assert len(report.episodes) == family_count * 3
    for metrics in report.aggregate.values():
        assert metrics.steps == family_count * 6
        assert np.isfinite(metrics.tracking_cost)
        assert np.isfinite(metrics.temperature_mae_c)
        assert 0.0 <= metrics.outside_deadband_fraction <= 1.0
        assert 0.0 <= metrics.safety_intervention_fraction <= 1.0
        assert 0.0 <= metrics.hard_limit_violation_fraction <= 1.0
