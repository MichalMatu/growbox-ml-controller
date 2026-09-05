from __future__ import annotations

from dataclasses import replace

import numpy as np

from tools.ml.climate_input import ClimateEffectiveActionEstimator, MeasurementStatus
from tools.ml.climate_policy import (
    ClimateRulePolicy,
    apply_climate_safety,
    arbitrate_climate_action,
)
from tools.ml.climate_runtime import (
    ClimatePolicyMode,
    ClimateRuntimeConfig,
    ClimateRuntimeController,
    ClimateRuntimeStatus,
)
from tools.ml.climate_scenarios import build_training_episode
from tools.ml.climate_simulator import ClimateAction


class _FakeModel:
    def __init__(self, values: tuple[float, ...]) -> None:
        self.values = np.asarray(values, dtype=np.float32)

    def predict(self, features: np.ndarray) -> np.ndarray:
        assert features.shape == (44,)
        return self.values.copy()


class _FailingModel:
    def predict(self, features: np.ndarray) -> np.ndarray:
        assert features.shape == (44,)
        raise RuntimeError("synthetic inference failure")


def _episode(family: str = "cold_heating"):
    return build_training_episode(family, 0, 18_018)


def test_rule_is_default_authority_and_needs_no_model() -> None:
    episode = _episode()
    state = episode.scenario.initial_state
    profile = episode.first_profile
    runtime = ClimateRuntimeController()

    decision = runtime.step(episode.scenario, state, profile, monotonic_ms=0)

    expected_raw = ClimateRulePolicy().choose(episode.scenario, state, profile)
    expected_arb = arbitrate_climate_action(expected_raw, episode.scenario)
    expected_safe = apply_climate_safety(expected_arb.action, episode.scenario, state, profile)
    assert decision.status is ClimateRuntimeStatus.OK
    assert decision.mode is ClimatePolicyMode.RULE
    assert decision.authoritative_policy == "rule"
    assert decision.applied == expected_safe.action
    assert decision.ml_raw is None
    assert decision.ml_features is None


def test_ml_shadow_without_model_falls_back_to_rule_with_status() -> None:
    episode = _episode()
    runtime = ClimateRuntimeController(
        config=ClimateRuntimeConfig(mode=ClimatePolicyMode.ML_SHADOW)
    )
    decision = runtime.step(
        episode.scenario,
        episode.scenario.initial_state,
        episode.first_profile,
        monotonic_ms=0,
    )
    assert decision.status is ClimateRuntimeStatus.ML_PROVIDER_MISSING
    assert decision.authoritative_policy == "rule"
    assert decision.applied == decision.rule_safe
    assert decision.ml_raw is None


def test_ml_shadow_cannot_change_applied_command_or_effective_state() -> None:
    episode = _episode()
    state = episode.scenario.initial_state
    profile = episode.first_profile
    runtime = ClimateRuntimeController(
        model=_FakeModel((1.0, 1.0, 1.0, 1.0, 1.0, 1.0)),
        config=ClimateRuntimeConfig(mode=ClimatePolicyMode.ML_SHADOW),
    )

    decision = runtime.step(
        episode.scenario,
        state,
        profile,
        previous_command=ClimateAction(),
        monotonic_ms=0,
    )

    assert decision.status is ClimateRuntimeStatus.OK
    assert decision.authoritative_policy == "rule"
    assert decision.applied == decision.rule_safe
    assert decision.ml_raw is not None
    assert decision.ml_safe is not None
    assert decision.ml_features is not None
    assert len(decision.ml_features) == 44
    expected_estimator = ClimateEffectiveActionEstimator()
    expected_effective = expected_estimator.update(episode.scenario, decision.rule_safe)
    assert decision.effective_after == expected_effective


def test_ml_active_without_opt_in_falls_back_to_rule_with_status() -> None:
    episode = _episode()
    runtime = ClimateRuntimeController(
        model=_FakeModel((0.0, 0.0, 0.0, 0.0, 0.0, 0.0)),
        config=ClimateRuntimeConfig(mode=ClimatePolicyMode.ML_ACTIVE),
    )
    decision = runtime.step(
        episode.scenario,
        episode.scenario.initial_state,
        episode.first_profile,
        monotonic_ms=0,
    )
    assert decision.status is ClimateRuntimeStatus.ML_ACTIVE_NOT_ALLOWED
    assert decision.authoritative_policy == "rule"
    assert decision.applied == decision.rule_safe
    assert decision.ml_raw is None


def test_explicit_research_ml_active_still_uses_arbitration_and_safety() -> None:
    episode = _episode("co2_enrichment")
    state = episode.scenario.initial_state
    profile = episode.first_profile
    runtime = ClimateRuntimeController(
        model=_FakeModel((1.0, 1.0, 1.0, 1.0, 1.0, 1.0)),
        config=ClimateRuntimeConfig(
            mode=ClimatePolicyMode.ML_ACTIVE,
            allow_unqualified_ml_active=True,
        ),
    )

    decision = runtime.step(episode.scenario, state, profile, monotonic_ms=0)

    assert decision.status is ClimateRuntimeStatus.OK
    assert decision.authoritative_policy == "ml"
    assert decision.ml_safe is not None
    assert decision.applied == decision.ml_safe
    assert decision.ml_arbitrated is not None
    assert decision.ml_arbitrated.cooler == 0.0
    assert decision.ml_arbitrated.dehumidifier == 0.0


def test_ml_inference_failure_falls_back_to_rule() -> None:
    episode = _episode()
    runtime = ClimateRuntimeController(
        model=_FailingModel(),
        config=ClimateRuntimeConfig(mode=ClimatePolicyMode.ML_SHADOW),
    )
    decision = runtime.step(
        episode.scenario,
        episode.scenario.initial_state,
        episode.first_profile,
        monotonic_ms=0,
    )
    assert decision.status is ClimateRuntimeStatus.ML_INFERENCE_FAILED
    assert decision.authoritative_policy == "rule"
    assert decision.applied == decision.rule_safe
    assert decision.ml_raw is None
    assert decision.ml_features is None


def test_nonfinite_ml_output_falls_back_to_rule() -> None:
    episode = _episode()
    runtime = ClimateRuntimeController(
        model=_FakeModel((float("nan"), 0.0, 0.0, 0.0, 0.0, 0.0)),
        config=ClimateRuntimeConfig(mode=ClimatePolicyMode.ML_SHADOW),
    )
    decision = runtime.step(
        episode.scenario,
        episode.scenario.initial_state,
        episode.first_profile,
        monotonic_ms=0,
    )
    assert decision.status is ClimateRuntimeStatus.ML_INFERENCE_FAILED
    assert decision.applied == decision.rule_safe


def test_required_sensor_fault_keeps_shadow_observational_only() -> None:
    episode = _episode()
    state = episode.scenario.initial_state
    profile = episode.first_profile
    runtime = ClimateRuntimeController(
        model=_FakeModel((1.0, 1.0, 1.0, 1.0, 1.0, 1.0)),
        config=ClimateRuntimeConfig(mode=ClimatePolicyMode.ML_SHADOW),
    )

    decision = runtime.step(
        episode.scenario,
        state,
        profile,
        monotonic_ms=60_000,
        status={"air_temperature_c": MeasurementStatus(valid=False)},
    )

    assert decision.status is ClimateRuntimeStatus.OK
    assert decision.applied == ClimateAction()
    assert decision.rule_safe == ClimateAction()
    assert decision.ml_safe == ClimateAction()
    assert "required_sensor_unusable" in decision.ml_safety_interventions


def test_humidity_ventilation_uses_absolute_humidity_when_intake_rh_is_higher() -> None:
    episode = _episode()
    state = replace(
        episode.scenario.initial_state,
        air_temperature_c=27.0,
        relative_humidity_pct=70.0,
        outside_temperature_c=15.0,
        outside_humidity_pct=80.0,
    )
    profile = replace(
        episode.first_profile,
        targets=replace(
            episode.first_profile.targets,
            air_temperature_c=27.0,
            relative_humidity_pct=60.0,
        ),
    )

    request = ClimateRulePolicy().choose(episode.scenario, state, profile)

    assert request.exhaust_fan > 0.0


def test_humidity_ventilation_rejects_lower_rh_when_intake_absolute_humidity_is_higher() -> None:
    episode = _episode()
    state = replace(
        episode.scenario.initial_state,
        air_temperature_c=27.0,
        relative_humidity_pct=70.0,
        outside_temperature_c=35.0,
        outside_humidity_pct=55.0,
    )
    profile = replace(
        episode.first_profile,
        targets=replace(
            episode.first_profile.targets,
            air_temperature_c=27.0,
            relative_humidity_pct=60.0,
        ),
    )

    request = ClimateRulePolicy().choose(episode.scenario, state, profile)

    assert request.exhaust_fan == 0.0


def test_temperature_ventilation_does_not_require_fresh_intake_humidity() -> None:
    episode = _episode()
    state = replace(
        episode.scenario.initial_state,
        air_temperature_c=28.0,
        relative_humidity_pct=60.0,
        outside_temperature_c=20.0,
        outside_humidity_pct=95.0,
    )
    profile = replace(
        episode.first_profile,
        targets=replace(
            episode.first_profile.targets,
            air_temperature_c=24.0,
            relative_humidity_pct=60.0,
        ),
    )

    request = ClimateRulePolicy().choose(
        episode.scenario,
        state,
        profile,
        status={"outside_humidity_pct": MeasurementStatus(valid=False)},
    )

    assert request.exhaust_fan > 0.1
