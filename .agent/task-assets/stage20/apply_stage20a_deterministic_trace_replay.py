from __future__ import annotations

from pathlib import Path
from textwrap import dedent

ROOT = Path.cwd()

MODULE = dedent(r'''
"""Deterministic replay for climate-v6 runtime trace records.

Replay intentionally stops at the policy boundary. It reconstructs only data
that was observable/configured at runtime, re-encodes the 44 features, and
re-runs Rule/optional ML policy, arbitration, and safety. It does not replay
simulator physics or recompute ``effective_after`` because response-lag and
other physical calibration terms are intentionally absent from trace v1.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import numpy as np

from .climate_input import (
    ClimateInputConfig,
    ClimateTargets,
    ClimateTrends,
    MeasurementStatus,
    TrendValue,
    encode_climate_input,
)
from .climate_policy import (
    ClimateRulePolicy,
    apply_climate_safety,
    apply_ml_request_deadzone,
    arbitrate_climate_action,
)
from .climate_scenarios import ClimateProfile
from .climate_simulator import (
    CLIMATE_OUTPUT_NAMES,
    ClimateAction,
    ClimateActuatorCapabilities,
    ClimateScenario,
    ClimateState,
    Co2DoserCapabilities,
    CoolerCapabilities,
    DehumidifierCapabilities,
    ExhaustFanCapabilities,
    HeaterCapabilities,
    HumidifierCapabilities,
)
from .climate_trace import validate_climate_runtime_trace_record
from .climate_trace_io import iter_climate_trace_ndjson_records


class ClimateReplayModel(Protocol):
    def predict(self, features: np.ndarray) -> np.ndarray: ...


@dataclass(frozen=True)
class ClimateReplayDivergence:
    step_index: int
    field: str
    expected: object
    actual: object


@dataclass(frozen=True)
class ClimateCounterfactualDecision:
    raw: ClimateAction
    arbitrated: ClimateAction
    safe: ClimateAction
    arbitration_interventions: tuple[str, ...]
    safety_interventions: tuple[str, ...]
    features: tuple[float, ...]


def _action(value: Mapping[str, Any]) -> ClimateAction:
    return ClimateAction.from_mapping({name: float(value[name]) for name in CLIMATE_OUTPUT_NAMES})


def _scenario(record: Mapping[str, Any]) -> ClimateScenario:
    caps = record["capabilities"]
    return ClimateScenario(
        scenario_id="trace-replay",
        actuators=ClimateActuatorCapabilities(
            heater=HeaterCapabilities(available=bool(caps["heater"])),
            cooler=CoolerCapabilities(available=bool(caps["cooler"])),
            exhaust_fan=ExhaustFanCapabilities(available=bool(caps["exhaust_fan"])),
            humidifier=HumidifierCapabilities(available=bool(caps["humidifier"])),
            dehumidifier=DehumidifierCapabilities(available=bool(caps["dehumidifier"])),
            co2_doser=Co2DoserCapabilities(available=bool(caps["co2_doser"])),
        ),
        timestep_s=float(record["timestep_s"]),
    )


def _state(record: Mapping[str, Any]) -> ClimateState:
    measurements = record["measurements"]
    return ClimateState(
        air_temperature_c=float(measurements["air_temperature_c"]["value"]),
        relative_humidity_pct=float(measurements["relative_humidity_pct"]["value"]),
        co2_ppm=float(measurements["co2_ppm"]["value"]),
        outside_temperature_c=float(measurements["outside_temperature_c"]["value"]),
        outside_humidity_pct=float(measurements["outside_humidity_pct"]["value"]),
        light_level=float(record["light_level"]),
    )


def _statuses(record: Mapping[str, Any]) -> dict[str, MeasurementStatus]:
    return {
        name: MeasurementStatus(valid=bool(value["valid"]), age_ms=int(value["age_ms"]))
        for name, value in record["measurements"].items()
    }


def _profile(record: Mapping[str, Any]) -> ClimateProfile:
    targets = record["targets"]
    return ClimateProfile(
        name="trace-replay",
        targets=ClimateTargets(
            air_temperature_c=float(targets["air_temperature_c"]),
            relative_humidity_pct=float(targets["relative_humidity_pct"]),
            air_vpd_kpa=float(targets["air_vpd_kpa"]),
            co2_enabled=bool(targets["co2_enabled"]),
            co2_ppm=float(targets["co2_ppm"]),
        ),
        humidity_control_mode=str(record["humidity_control_mode"]),
        light_level=float(record["light_level"]),
    )


def _trends(record: Mapping[str, Any]) -> ClimateTrends:
    trends = record["trends"]

    def value(name: str) -> TrendValue:
        item = trends[name]
        return TrendValue(
            rate_per_min=float(item["rate_per_min"]),
            available=bool(item["available"]),
        )

    return ClimateTrends(
        temperature=value("temperature"),
        humidity=value("humidity"),
        co2=value("co2"),
    )


def _evaluation(
    raw: ClimateAction,
    arbitrated: ClimateAction,
    safe: ClimateAction,
    arbitration_interventions: tuple[str, ...],
    safety_interventions: tuple[str, ...],
) -> dict[str, object]:
    return {
        "raw": raw.as_dict(),
        "arbitrated": arbitrated.as_dict(),
        "safe": safe.as_dict(),
        "arbitration_interventions": list(arbitration_interventions),
        "safety_interventions": list(safety_interventions),
    }


def _first_difference(
    expected: object,
    actual: object,
    *,
    path: str,
    tolerance: float,
) -> tuple[str, object, object] | None:
    if isinstance(expected, bool) or isinstance(actual, bool):
        if expected != actual:
            return path, expected, actual
        return None
    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        expected_float = float(expected)
        actual_float = float(actual)
        if not math.isclose(expected_float, actual_float, rel_tol=tolerance, abs_tol=tolerance):
            return path, expected, actual
        return None
    if isinstance(expected, Mapping) and isinstance(actual, Mapping):
        expected_keys = list(expected.keys())
        actual_keys = list(actual.keys())
        if expected_keys != actual_keys:
            return f"{path}.__keys__", expected_keys, actual_keys
        for key in expected_keys:
            difference = _first_difference(
                expected[key], actual[key], path=f"{path}.{key}", tolerance=tolerance
            )
            if difference is not None:
                return difference
        return None
    if isinstance(expected, (list, tuple)) and isinstance(actual, (list, tuple)):
        if len(expected) != len(actual):
            return f"{path}.__len__", len(expected), len(actual)
        for index, (expected_item, actual_item) in enumerate(zip(expected, actual, strict=True)):
            difference = _first_difference(
                expected_item,
                actual_item,
                path=f"{path}[{index}]",
                tolerance=tolerance,
            )
            if difference is not None:
                return difference
        return None
    if expected != actual:
        return path, expected, actual
    return None


def _replay_inputs(record: Mapping[str, Any]) -> tuple[
    ClimateScenario,
    ClimateState,
    ClimateProfile,
    dict[str, MeasurementStatus],
    ClimateTrends,
    ClimateAction,
    ClimateAction,
    tuple[float, ...],
]:
    scenario = _scenario(record)
    state = _state(record)
    profile = _profile(record)
    statuses = _statuses(record)
    trends = _trends(record)
    previous = _action(record["previous_action"])
    effective_before = _action(record["effective_before"])
    features_array = encode_climate_input(
        scenario,
        state,
        previous=previous,
        estimated_effective=effective_before,
        trends=trends,
        status=statuses,
        config=ClimateInputConfig(
            targets=profile.targets,
            humidity_control_mode=profile.humidity_control_mode,
            sensor_timeout_ms=int(record["sensor_timeout_ms"]),
        ),
    )
    features = tuple(float(value) for value in features_array)
    return scenario, state, profile, statuses, trends, previous, effective_before, features


def _evaluate_ml(
    model: ClimateReplayModel,
    features: tuple[float, ...],
    scenario: ClimateScenario,
    state: ClimateState,
    profile: ClimateProfile,
    statuses: Mapping[str, MeasurementStatus],
    sensor_timeout_ms: int,
) -> ClimateCounterfactualDecision:
    prediction = np.asarray(model.predict(np.asarray(features, dtype=np.float32)), dtype=np.float32)
    if prediction.shape != (len(CLIMATE_OUTPUT_NAMES),):
        raise ValueError("climate replay model prediction must have shape (6,)")
    if not np.isfinite(prediction).all():
        raise ValueError("climate replay model prediction contains NaN/Inf")
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
        status=statuses,
        sensor_timeout_ms=sensor_timeout_ms,
    )
    return ClimateCounterfactualDecision(
        raw=raw,
        arbitrated=arbitrated.action,
        safe=safe.action,
        arbitration_interventions=arbitrated.interventions,
        safety_interventions=safe.interventions,
        features=features,
    )


def replay_climate_trace_record(
    record: Mapping[str, Any],
    *,
    model: ClimateReplayModel | None = None,
    step_index: int = 1,
    tolerance: float = 1.0e-6,
) -> ClimateReplayDivergence | None:
    """Return the first deterministic policy divergence for one trace record.

    Rule/feature/applied replay works without a model for Rule and shadow traces.
    If a model is supplied, recorded ML evaluation is also checked. ML-active
    traces require a model because ML was authoritative for the recorded action.
    """

    if tolerance < 0.0 or not math.isfinite(tolerance):
        raise ValueError("tolerance must be finite and non-negative")
    validate_climate_runtime_trace_record(record)
    (
        scenario,
        state,
        profile,
        statuses,
        _recorded_trends,
        _previous,
        _effective_before,
        features,
    ) = _replay_inputs(record)

    difference = _first_difference(
        record["features"], list(features), path="features", tolerance=tolerance
    )
    if difference is not None:
        field, expected, actual = difference
        return ClimateReplayDivergence(step_index, field, expected, actual)

    rule_raw = ClimateRulePolicy().choose(
        scenario,
        state,
        profile,
        status=statuses,
        sensor_timeout_ms=int(record["sensor_timeout_ms"]),
    )
    rule_arbitrated = arbitrate_climate_action(rule_raw, scenario)
    rule_safe = apply_climate_safety(
        rule_arbitrated.action,
        scenario,
        state,
        profile,
        status=statuses,
        sensor_timeout_ms=int(record["sensor_timeout_ms"]),
    )
    actual_rule = _evaluation(
        rule_raw,
        rule_arbitrated.action,
        rule_safe.action,
        rule_arbitrated.interventions,
        rule_safe.interventions,
    )
    difference = _first_difference(
        record["rule"], actual_rule, path="rule", tolerance=tolerance
    )
    if difference is not None:
        field, expected, actual = difference
        return ClimateReplayDivergence(step_index, field, expected, actual)

    authoritative_policy = str(record["policy"]["authoritative_policy"])
    if authoritative_policy == "rule":
        difference = _first_difference(
            record["applied"], rule_safe.action.as_dict(), path="applied", tolerance=tolerance
        )
        if difference is not None:
            field, expected, actual = difference
            return ClimateReplayDivergence(step_index, field, expected, actual)

    if model is None:
        if authoritative_policy == "ml":
            return ClimateReplayDivergence(
                step_index,
                "model",
                record.get("model"),
                None,
            )
        return None

    candidate = _evaluate_ml(
        model,
        features,
        scenario,
        state,
        profile,
        statuses,
        int(record["sensor_timeout_ms"]),
    )
    if bool(record["ml"]["evaluated"]):
        actual_ml = {
            "evaluated": True,
            **_evaluation(
                candidate.raw,
                candidate.arbitrated,
                candidate.safe,
                candidate.arbitration_interventions,
                candidate.safety_interventions,
            ),
        }
        difference = _first_difference(
            record["ml"], actual_ml, path="ml", tolerance=tolerance
        )
        if difference is not None:
            field, expected, actual = difference
            return ClimateReplayDivergence(step_index, field, expected, actual)

    if authoritative_policy == "ml":
        difference = _first_difference(
            record["applied"], candidate.safe.as_dict(), path="applied", tolerance=tolerance
        )
        if difference is not None:
            field, expected, actual = difference
            return ClimateReplayDivergence(step_index, field, expected, actual)
    return None


def first_climate_trace_replay_divergence(
    records: Iterable[Mapping[str, Any]],
    *,
    model: ClimateReplayModel | None = None,
    tolerance: float = 1.0e-6,
) -> ClimateReplayDivergence | None:
    for step_index, record in enumerate(records, start=1):
        divergence = replay_climate_trace_record(
            record,
            model=model,
            step_index=step_index,
            tolerance=tolerance,
        )
        if divergence is not None:
            return divergence
    return None


def first_climate_trace_ndjson_replay_divergence(
    path: str | Path,
    *,
    model: ClimateReplayModel | None = None,
    tolerance: float = 1.0e-6,
) -> ClimateReplayDivergence | None:
    return first_climate_trace_replay_divergence(
        iter_climate_trace_ndjson_records(path),
        model=model,
        tolerance=tolerance,
    )


def counterfactual_climate_trace_ml(
    record: Mapping[str, Any],
    model: ClimateReplayModel,
    *,
    tolerance: float = 1.0e-6,
) -> ClimateCounterfactualDecision:
    """Evaluate a new ML candidate without changing the recorded trajectory."""

    validate_climate_runtime_trace_record(record)
    scenario, state, profile, statuses, _trends_value, _previous, _effective, features = (
        _replay_inputs(record)
    )
    difference = _first_difference(
        record["features"], list(features), path="features", tolerance=tolerance
    )
    if difference is not None:
        field, expected, actual = difference
        raise ValueError(f"trace feature divergence at {field}: expected={expected!r} actual={actual!r}")
    return _evaluate_ml(
        model,
        features,
        scenario,
        state,
        profile,
        statuses,
        int(record["sensor_timeout_ms"]),
    )


__all__ = [
    "ClimateCounterfactualDecision",
    "ClimateReplayDivergence",
    "ClimateReplayModel",
    "counterfactual_climate_trace_ml",
    "first_climate_trace_ndjson_replay_divergence",
    "first_climate_trace_replay_divergence",
    "replay_climate_trace_record",
]
''').lstrip()

TEST = dedent(r'''
from __future__ import annotations

import copy

import numpy as np

from tools.ml.climate_input import CLIMATE_V6_CONTRACT_PATH
from tools.ml.climate_replay import (
    counterfactual_climate_trace_ml,
    first_climate_trace_ndjson_replay_divergence,
    first_climate_trace_replay_divergence,
    replay_climate_trace_record,
)
from tools.ml.climate_runtime import (
    ClimatePolicyMode,
    ClimateRuntimeConfig,
    ClimateRuntimeController,
)
from tools.ml.climate_scenarios import build_training_episode
from tools.ml.climate_simulator import ClimateAction
from tools.ml.climate_trace import build_climate_runtime_trace_record
from tools.ml.climate_trace_io import append_climate_trace_ndjson_record
from tools.ml.contract import load_contract


class _FixedModel:
    def __init__(self, values=(0.2, 0.8, 0.7, 0.6, 0.4, 0.9)) -> None:
        self.values = values

    def predict(self, features: np.ndarray) -> np.ndarray:
        assert features.shape == (44,)
        return np.asarray(self.values, dtype=np.float32)


def _record(*, mode: ClimatePolicyMode = ClimatePolicyMode.RULE):
    episode = build_training_episode("cold_heating", 0, 20_001)
    model = _FixedModel() if mode is not ClimatePolicyMode.RULE else None
    runtime = ClimateRuntimeController(
        model=model,
        config=ClimateRuntimeConfig(
            mode=mode,
            allow_unqualified_ml_active=mode is ClimatePolicyMode.ML_ACTIVE,
        ),
    )
    previous = ClimateAction(heater=0.1, exhaust_fan=0.2)
    decision = runtime.step(
        episode.scenario,
        episode.scenario.initial_state,
        episode.first_profile,
        previous_command=previous,
        monotonic_ms=120_000,
    )
    contract_hash = load_contract(CLIMATE_V6_CONTRACT_PATH).hash_hex
    return build_climate_runtime_trace_record(
        episode.scenario,
        episode.scenario.initial_state,
        episode.first_profile,
        decision,
        previous_command=previous,
        monotonic_ms=120_000,
        model_id="fixed-replay-model" if model is not None else None,
        model_contract_hash=contract_hash if model is not None else None,
    )


def test_rule_trace_replays_without_divergence() -> None:
    assert replay_climate_trace_record(_record()) is None


def test_shadow_trace_replays_rule_authority_without_loading_model() -> None:
    record = _record(mode=ClimatePolicyMode.ML_SHADOW)
    assert record["ml"]["evaluated"] is True
    assert replay_climate_trace_record(record) is None


def test_shadow_trace_can_verify_recorded_ml_when_model_is_available() -> None:
    record = _record(mode=ClimatePolicyMode.ML_SHADOW)
    assert replay_climate_trace_record(record, model=_FixedModel()) is None


def test_ml_active_requires_model_and_replays_when_supplied() -> None:
    record = _record(mode=ClimatePolicyMode.ML_ACTIVE)
    missing = replay_climate_trace_record(record)
    assert missing is not None
    assert missing.field == "model"
    assert replay_climate_trace_record(record, model=_FixedModel()) is None


def test_first_divergence_reports_step_field_expected_and_actual() -> None:
    first = _record()
    second = copy.deepcopy(first)
    second["features"][0] = min(1.0, second["features"][0] + 0.25)
    divergence = first_climate_trace_replay_divergence([first, second])
    assert divergence is not None
    assert divergence.step_index == 2
    assert divergence.field == "features[0]"
    assert divergence.expected == second["features"][0]
    assert divergence.actual != divergence.expected


def test_replay_detects_rule_gate_divergence() -> None:
    record = _record()
    record["rule"]["safe"]["heater"] = min(1.0, record["rule"]["safe"]["heater"] + 0.2)
    divergence = replay_climate_trace_record(record)
    assert divergence is not None
    assert divergence.field == "rule.safe.heater"


def test_ndjson_replay_streams_and_reports_first_bad_step(tmp_path) -> None:
    path = tmp_path / "trace.ndjson"
    first = _record()
    second = copy.deepcopy(first)
    second["applied"]["heater"] = min(1.0, second["applied"]["heater"] + 0.2)
    append_climate_trace_ndjson_record(path, first)
    append_climate_trace_ndjson_record(path, second)
    divergence = first_climate_trace_ndjson_replay_divergence(path)
    assert divergence is not None
    assert divergence.step_index == 2
    assert divergence.field == "applied.heater"


def test_counterfactual_ml_does_not_mutate_recorded_trajectory() -> None:
    record = _record()
    before = copy.deepcopy(record)
    candidate = counterfactual_climate_trace_ml(
        record,
        _FixedModel(values=(0.9, 0.8, 0.7, 0.6, 0.5, 0.4)),
    )
    assert len(candidate.features) == 44
    assert candidate.safe.as_dict() != ClimateAction().as_dict()
    assert record == before
    assert record["applied"] == before["applied"]
    assert record["effective_after"] == before["effective_after"]
''').lstrip()

(ROOT / "tools/ml/climate_replay.py").write_text(MODULE, encoding="utf-8")
(ROOT / "tests/test_climate_replay.py").write_text(TEST, encoding="utf-8")
