from __future__ import annotations

import copy
import json

import jsonschema
import numpy as np
import pytest

from tools.ml.climate_input import CLIMATE_V6_CONTRACT_PATH, MeasurementStatus
from tools.ml.climate_runtime import (
    ClimatePolicyMode,
    ClimateRuntimeConfig,
    ClimateRuntimeController,
)
from tools.ml.climate_scenarios import build_training_episode
from tools.ml.climate_simulator import ClimateAction
from tools.ml.climate_trace import (
    TRACE_SCHEMA_ID,
    TRACE_SCHEMA_VERSION,
    build_climate_runtime_trace_record,
    canonical_climate_runtime_trace_json,
    load_climate_runtime_trace_schema,
    validate_climate_runtime_trace_record,
)
from tools.ml.contract import load_contract


class _FixedModel:
    def predict(self, features: np.ndarray) -> np.ndarray:
        assert features.shape == (44,)
        return np.asarray((0.2, 0.8, 0.7, 0.6, 0.4, 0.9), dtype=np.float32)


def _record(*, shadow: bool = False, sensor_fault: bool = False):
    episode = build_training_episode("cold_heating", 0, 19_019)
    status = {"air_temperature_c": MeasurementStatus(valid=False, age_ms=0)} if sensor_fault else {}
    config = ClimateRuntimeConfig(
        mode=ClimatePolicyMode.ML_SHADOW if shadow else ClimatePolicyMode.RULE
    )
    runtime = ClimateRuntimeController(model=_FixedModel() if shadow else None, config=config)
    previous = ClimateAction(heater=0.1, exhaust_fan=0.2)
    decision = runtime.step(
        episode.scenario,
        episode.scenario.initial_state,
        episode.first_profile,
        previous_command=previous,
        monotonic_ms=120_000,
        status=status,
    )
    contract_hash = load_contract(CLIMATE_V6_CONTRACT_PATH).hash_hex
    return build_climate_runtime_trace_record(
        episode.scenario,
        episode.scenario.initial_state,
        episode.first_profile,
        decision,
        previous_command=previous,
        monotonic_ms=120_000,
        status=status,
        model_id="stage13-compat" if shadow else None,
        model_contract_hash=contract_hash if shadow else None,
    )


def test_trace_schema_is_valid_draft_2020_12() -> None:
    schema = load_climate_runtime_trace_schema()
    jsonschema.Draft202012Validator.check_schema(schema)
    assert schema["properties"]["features"]["minItems"] == 44
    assert schema["properties"]["features"]["maxItems"] == 44


def test_rule_trace_captures_runtime_observable_contract() -> None:
    record = _record()
    validate_climate_runtime_trace_record(record)
    contract = load_contract(CLIMATE_V6_CONTRACT_PATH)
    assert record["schema_id"] == TRACE_SCHEMA_ID
    assert record["schema_version"] == TRACE_SCHEMA_VERSION
    assert record["contract"] == {
        "id": "climate-mvp-v1",
        "schema_version": 6,
        "hash": contract.hash_hex,
    }
    assert record["policy"] == {
        "mode": "rule",
        "status": "ok",
        "authoritative_policy": "rule",
    }
    assert record["model"] is None
    assert len(record["features"]) == 44
    assert record["previous_action"]["heater"] == pytest.approx(0.1)
    assert "environment" not in record
    assert "response_lag" not in record


def test_shadow_trace_is_observational_and_identifies_model() -> None:
    record = _record(shadow=True)
    assert record["policy"]["mode"] == "ml_shadow"
    assert record["policy"]["authoritative_policy"] == "rule"
    assert record["ml"]["evaluated"] is True
    assert record["ml"]["safe"] is not None
    assert record["applied"] == record["rule"]["safe"]
    assert record["model"]["id"] == "stage13-compat"
    assert len(record["model"]["contract_hash"]) == 64


def test_required_sensor_fault_remains_explicit_and_safe() -> None:
    record = _record(shadow=True, sensor_fault=True)
    assert record["measurements"]["air_temperature_c"]["valid"] is False
    assert record["applied"] == ClimateAction().as_dict()
    assert (
        "required_sensor_unusable" in record["rule"]["safety_interventions"]
        or record["rule"]["safe"] == ClimateAction().as_dict()
    )


def test_canonical_trace_json_round_trips_without_nan_extensions() -> None:
    record = _record(shadow=True)
    encoded = canonical_climate_runtime_trace_json(record)
    assert "NaN" not in encoded and "Infinity" not in encoded
    assert json.loads(encoded) == record


def test_validator_rejects_non_finite_and_unknown_fields() -> None:
    record = _record()
    broken = copy.deepcopy(record)
    broken["features"][0] = float("nan")
    with pytest.raises(ValueError, match="non-finite"):
        validate_climate_runtime_trace_record(broken)

    broken = copy.deepcopy(record)
    broken["hidden_simulator_truth"] = {"thermal_mass": 123.0}
    with pytest.raises(jsonschema.ValidationError):
        validate_climate_runtime_trace_record(broken)


def test_model_identity_is_all_or_nothing() -> None:
    episode = build_training_episode("cold_heating", 0, 19_020)
    runtime = ClimateRuntimeController()
    decision = runtime.step(
        episode.scenario,
        episode.scenario.initial_state,
        episode.first_profile,
        monotonic_ms=0,
    )
    with pytest.raises(ValueError, match="provided together"):
        build_climate_runtime_trace_record(
            episode.scenario,
            episode.scenario.initial_state,
            episode.first_profile,
            decision,
            monotonic_ms=0,
            model_id="incomplete",
        )
