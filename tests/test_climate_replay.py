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
    current = record["rule"]["safe"]["heater"]
    record["rule"]["safe"]["heater"] = 0.0 if current > 0.0 else 1.0
    divergence = replay_climate_trace_record(record)
    assert divergence is not None
    assert divergence.field == "rule.safe.heater"


def test_ndjson_replay_streams_and_reports_first_bad_step(tmp_path) -> None:
    path = tmp_path / "trace.ndjson"
    first = _record()
    second = copy.deepcopy(first)
    current = second["applied"]["heater"]
    second["applied"]["heater"] = 0.0 if current > 0.0 else 1.0
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
