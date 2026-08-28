from pathlib import Path

ROOT = Path.cwd()

runtime = r'''"""Climate-v6 runtime policy selection with shadow-mode diagnostics.

This module is the Python reference runtime for policy authority. Rule control is
production authority by default. ML shadow mode evaluates the persisted model
through the same arbitration and safety gates without allowing ML to influence
the applied command. ML active mode exists only as an explicit, unqualified
research opt-in and is disabled by default. Missing, blocked, or failed ML always
falls back to the Rule path and is reported through ``ClimateRuntimeStatus``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol

import numpy as np

from .climate_input import (
    DEFAULT_SENSOR_TIMEOUT_MS,
    ClimateEffectiveActionEstimator,
    ClimateInputConfig,
    ClimateTrendEstimator,
    ClimateTrends,
    MeasurementStatus,
    encode_climate_input,
)
from .climate_policy import (
    ClimateRulePolicy,
    apply_climate_safety,
    apply_ml_request_deadzone,
    arbitrate_climate_action,
)
from .climate_scenarios import ClimateProfile
from .climate_simulator import CLIMATE_OUTPUT_NAMES, ClimateAction, ClimateScenario, ClimateState


class ClimatePolicyMode(str, Enum):
    RULE = "rule"
    ML_SHADOW = "ml_shadow"
    ML_ACTIVE = "ml_active"


class ClimateRuntimeStatus(str, Enum):
    OK = "ok"
    ML_PROVIDER_MISSING = "ml_provider_missing"
    ML_INFERENCE_FAILED = "ml_inference_failed"
    ML_ACTIVE_NOT_ALLOWED = "ml_active_not_allowed"


class ClimateInferenceModel(Protocol):
    def predict(self, features: np.ndarray) -> np.ndarray: ...


@dataclass(frozen=True)
class ClimateRuntimeConfig:
    mode: ClimatePolicyMode = ClimatePolicyMode.RULE
    sensor_timeout_ms: int = DEFAULT_SENSOR_TIMEOUT_MS
    allow_unqualified_ml_active: bool = False


@dataclass(frozen=True)
class ClimateRuntimeDecision:
    status: ClimateRuntimeStatus
    mode: ClimatePolicyMode
    authoritative_policy: str
    rule_raw: ClimateAction
    rule_arbitrated: ClimateAction
    rule_safe: ClimateAction
    rule_arbitration_interventions: tuple[str, ...]
    rule_safety_interventions: tuple[str, ...]
    ml_raw: ClimateAction | None
    ml_arbitrated: ClimateAction | None
    ml_safe: ClimateAction | None
    ml_arbitration_interventions: tuple[str, ...]
    ml_safety_interventions: tuple[str, ...]
    ml_features: tuple[float, ...] | None
    trends: ClimateTrends
    effective_before: ClimateAction
    applied: ClimateAction
    effective_after: ClimateAction


class ClimateRuntimeController:
    """Reference climate-v6 runtime with explicit policy authority and Rule fallback."""

    def __init__(
        self,
        model: ClimateInferenceModel | None = None,
        config: ClimateRuntimeConfig | None = None,
    ) -> None:
        self.config = config or ClimateRuntimeConfig()
        self.model = model
        if self.config.sensor_timeout_ms < 0:
            raise ValueError("sensor_timeout_ms must be non-negative")
        self.rule_policy = ClimateRulePolicy()
        self.trend_estimator = ClimateTrendEstimator()
        self.effective_estimator = ClimateEffectiveActionEstimator()

    def reset(self) -> None:
        self.trend_estimator.reset()
        self.effective_estimator.reset()

    def _evaluate_ml(
        self,
        scenario: ClimateScenario,
        state: ClimateState,
        profile: ClimateProfile,
        previous_command: ClimateAction,
        trends: ClimateTrends,
        status: dict[str, MeasurementStatus],
    ) -> tuple[
        ClimateAction,
        ClimateAction,
        ClimateAction,
        tuple[str, ...],
        tuple[str, ...],
        tuple[float, ...],
    ]:
        if self.model is None:
            raise RuntimeError("ML evaluation requested without a model")
        features = encode_climate_input(
            scenario,
            state,
            previous=previous_command,
            estimated_effective=self.effective_estimator.state,
            trends=trends,
            status=status,
            config=ClimateInputConfig(
                targets=profile.targets,
                humidity_control_mode=profile.humidity_control_mode,
                sensor_timeout_ms=self.config.sensor_timeout_ms,
            ),
        )
        prediction = np.asarray(self.model.predict(features), dtype=np.float32)
        if prediction.shape != (len(CLIMATE_OUTPUT_NAMES),):
            raise ValueError("climate model prediction must have shape (6,)")
        if not np.isfinite(prediction).all():
            raise ValueError("climate model prediction contains NaN/Inf")
        raw = apply_ml_request_deadzone(
            ClimateAction.from_mapping(
                dict(zip(CLIMATE_OUTPUT_NAMES, (float(value) for value in prediction), strict=True))
            )
        )
        arbitrated = arbitrate_climate_action(raw, scenario)
        safe = apply_climate_safety(
            arbitrated.action,
            scenario,
            state,
            profile,
            status=status,
            sensor_timeout_ms=self.config.sensor_timeout_ms,
        )
        return (
            raw,
            arbitrated.action,
            safe.action,
            arbitrated.interventions,
            safe.interventions,
            tuple(float(value) for value in features),
        )

    def step(
        self,
        scenario: ClimateScenario,
        state: ClimateState,
        profile: ClimateProfile,
        *,
        previous_command: ClimateAction | None = None,
        monotonic_ms: int,
        status: dict[str, MeasurementStatus] | None = None,
        timestep_s: float | None = None,
    ) -> ClimateRuntimeDecision:
        statuses = dict(status or {})
        previous = previous_command or ClimateAction()
        trends = self.trend_estimator.update(
            state,
            monotonic_ms,
            status=statuses,
            sensor_timeout_ms=self.config.sensor_timeout_ms,
        )

        rule_raw = self.rule_policy.choose(
            scenario,
            state,
            profile,
            status=statuses,
            sensor_timeout_ms=self.config.sensor_timeout_ms,
        )
        rule_arbitrated = arbitrate_climate_action(rule_raw, scenario)
        rule_safe = apply_climate_safety(
            rule_arbitrated.action,
            scenario,
            state,
            profile,
            status=statuses,
            sensor_timeout_ms=self.config.sensor_timeout_ms,
        )

        runtime_status = ClimateRuntimeStatus.OK
        ml_raw: ClimateAction | None = None
        ml_arbitrated: ClimateAction | None = None
        ml_safe: ClimateAction | None = None
        ml_arb_interventions: tuple[str, ...] = ()
        ml_safety_interventions: tuple[str, ...] = ()
        ml_features: tuple[float, ...] | None = None

        if (
            self.config.mode is ClimatePolicyMode.ML_ACTIVE
            and not self.config.allow_unqualified_ml_active
        ):
            runtime_status = ClimateRuntimeStatus.ML_ACTIVE_NOT_ALLOWED
        elif self.config.mode is not ClimatePolicyMode.RULE:
            if self.model is None:
                runtime_status = ClimateRuntimeStatus.ML_PROVIDER_MISSING
            else:
                try:
                    (
                        ml_raw,
                        ml_arbitrated,
                        ml_safe,
                        ml_arb_interventions,
                        ml_safety_interventions,
                        ml_features,
                    ) = self._evaluate_ml(scenario, state, profile, previous, trends, statuses)
                except Exception:
                    runtime_status = ClimateRuntimeStatus.ML_INFERENCE_FAILED
                    ml_raw = None
                    ml_arbitrated = None
                    ml_safe = None
                    ml_arb_interventions = ()
                    ml_safety_interventions = ()
                    ml_features = None

        authoritative_policy = "rule"
        applied = rule_safe.action
        if self.config.mode is ClimatePolicyMode.ML_ACTIVE and runtime_status is ClimateRuntimeStatus.OK:
            if ml_safe is None:
                runtime_status = ClimateRuntimeStatus.ML_INFERENCE_FAILED
            else:
                authoritative_policy = "ml"
                applied = ml_safe

        effective_before = self.effective_estimator.state
        effective_after = self.effective_estimator.update(
            scenario,
            applied,
            timestep_s=timestep_s,
        )
        return ClimateRuntimeDecision(
            status=runtime_status,
            mode=self.config.mode,
            authoritative_policy=authoritative_policy,
            rule_raw=rule_raw,
            rule_arbitrated=rule_arbitrated.action,
            rule_safe=rule_safe.action,
            rule_arbitration_interventions=rule_arbitrated.interventions,
            rule_safety_interventions=rule_safe.interventions,
            ml_raw=ml_raw,
            ml_arbitrated=ml_arbitrated,
            ml_safe=ml_safe,
            ml_arbitration_interventions=ml_arb_interventions,
            ml_safety_interventions=ml_safety_interventions,
            ml_features=ml_features,
            trends=trends,
            effective_before=effective_before,
            applied=applied,
            effective_after=effective_after,
        )


__all__ = [
    "ClimateInferenceModel",
    "ClimatePolicyMode",
    "ClimateRuntimeConfig",
    "ClimateRuntimeController",
    "ClimateRuntimeDecision",
    "ClimateRuntimeStatus",
]
'''

tests = r'''from __future__ import annotations

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
    runtime = ClimateRuntimeController(config=ClimateRuntimeConfig(mode=ClimatePolicyMode.ML_SHADOW))
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
'''

(ROOT / "tools/ml/climate_runtime.py").write_text(runtime, encoding="utf-8")
(ROOT / "tests/test_climate_runtime.py").write_text(tests, encoding="utf-8")
