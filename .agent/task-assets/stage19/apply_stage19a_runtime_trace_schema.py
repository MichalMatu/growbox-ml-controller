from __future__ import annotations

from pathlib import Path
from textwrap import dedent

ROOT = Path.cwd()

SCHEMA = dedent(r'''
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://growbox.local/schemas/climate-runtime-trace.v1.json",
  "title": "Climate Runtime Trace Record",
  "description": "One climate-v6 control step. Contains only runtime-observable/configured data; simulator-hidden physical truth is intentionally excluded.",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "schema_id",
    "schema_version",
    "contract",
    "monotonic_ms",
    "sensor_timeout_ms",
    "timestep_s",
    "policy",
    "model",
    "measurements",
    "targets",
    "humidity_control_mode",
    "light_level",
    "capabilities",
    "previous_action",
    "trends",
    "features",
    "rule",
    "ml",
    "applied",
    "effective_before",
    "effective_after"
  ],
  "$defs": {
    "action": {
      "type": "object",
      "additionalProperties": false,
      "required": ["heater", "cooler", "exhaust_fan", "humidifier", "dehumidifier", "co2_doser"],
      "properties": {
        "heater": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "cooler": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "exhaust_fan": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "humidifier": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "dehumidifier": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "co2_doser": {"type": "number", "minimum": 0.0, "maximum": 1.0}
      }
    },
    "measurement": {
      "type": "object",
      "additionalProperties": false,
      "required": ["value", "valid", "age_ms"],
      "properties": {
        "value": {"type": "number"},
        "valid": {"type": "boolean"},
        "age_ms": {"type": "integer", "minimum": 0}
      }
    },
    "trend": {
      "type": "object",
      "additionalProperties": false,
      "required": ["rate_per_min", "available"],
      "properties": {
        "rate_per_min": {"type": "number"},
        "available": {"type": "boolean"}
      }
    },
    "evaluation": {
      "type": "object",
      "additionalProperties": false,
      "required": ["raw", "arbitrated", "safe", "arbitration_interventions", "safety_interventions"],
      "properties": {
        "raw": {"$ref": "#/$defs/action"},
        "arbitrated": {"$ref": "#/$defs/action"},
        "safe": {"$ref": "#/$defs/action"},
        "arbitration_interventions": {"type": "array", "items": {"type": "string"}, "uniqueItems": true},
        "safety_interventions": {"type": "array", "items": {"type": "string"}, "uniqueItems": true}
      }
    },
    "optionalEvaluation": {
      "type": "object",
      "additionalProperties": false,
      "required": ["evaluated", "raw", "arbitrated", "safe", "arbitration_interventions", "safety_interventions"],
      "properties": {
        "evaluated": {"type": "boolean"},
        "raw": {"oneOf": [{"$ref": "#/$defs/action"}, {"type": "null"}]},
        "arbitrated": {"oneOf": [{"$ref": "#/$defs/action"}, {"type": "null"}]},
        "safe": {"oneOf": [{"$ref": "#/$defs/action"}, {"type": "null"}]},
        "arbitration_interventions": {"type": "array", "items": {"type": "string"}, "uniqueItems": true},
        "safety_interventions": {"type": "array", "items": {"type": "string"}, "uniqueItems": true}
      }
    }
  },
  "properties": {
    "schema_id": {"const": "climate-runtime-trace"},
    "schema_version": {"const": 1},
    "contract": {
      "type": "object",
      "additionalProperties": false,
      "required": ["id", "schema_version", "hash"],
      "properties": {
        "id": {"const": "climate-mvp-v1"},
        "schema_version": {"const": 6},
        "hash": {"type": "string", "pattern": "^[0-9a-f]{64}$"}
      }
    },
    "monotonic_ms": {"type": "integer", "minimum": 0},
    "sensor_timeout_ms": {"type": "integer", "minimum": 0},
    "timestep_s": {"type": "number", "exclusiveMinimum": 0.0},
    "policy": {
      "type": "object",
      "additionalProperties": false,
      "required": ["mode", "status", "authoritative_policy"],
      "properties": {
        "mode": {"enum": ["rule", "ml_shadow", "ml_active"]},
        "status": {"enum": ["ok", "ml_provider_missing", "ml_inference_failed", "ml_active_not_allowed"]},
        "authoritative_policy": {"enum": ["rule", "ml"]}
      }
    },
    "model": {
      "oneOf": [
        {"type": "null"},
        {
          "type": "object",
          "additionalProperties": false,
          "required": ["id", "contract_hash"],
          "properties": {
            "id": {"type": "string", "minLength": 1},
            "contract_hash": {"type": "string", "pattern": "^[0-9a-f]{64}$"}
          }
        }
      ]
    },
    "measurements": {
      "type": "object",
      "additionalProperties": false,
      "required": ["air_temperature_c", "relative_humidity_pct", "co2_ppm", "outside_temperature_c", "outside_humidity_pct"],
      "properties": {
        "air_temperature_c": {"$ref": "#/$defs/measurement"},
        "relative_humidity_pct": {"$ref": "#/$defs/measurement"},
        "co2_ppm": {"$ref": "#/$defs/measurement"},
        "outside_temperature_c": {"$ref": "#/$defs/measurement"},
        "outside_humidity_pct": {"$ref": "#/$defs/measurement"}
      }
    },
    "targets": {
      "type": "object",
      "additionalProperties": false,
      "required": ["air_temperature_c", "relative_humidity_pct", "air_vpd_kpa", "co2_enabled", "co2_ppm"],
      "properties": {
        "air_temperature_c": {"type": "number"},
        "relative_humidity_pct": {"type": "number"},
        "air_vpd_kpa": {"type": "number"},
        "co2_enabled": {"type": "boolean"},
        "co2_ppm": {"type": "number"}
      }
    },
    "humidity_control_mode": {"enum": ["RH", "VPD"]},
    "light_level": {"type": "number", "minimum": 0.0, "maximum": 1.0},
    "capabilities": {
      "type": "object",
      "additionalProperties": false,
      "required": ["heater", "cooler", "exhaust_fan", "humidifier", "dehumidifier", "co2_doser"],
      "properties": {
        "heater": {"type": "boolean"},
        "cooler": {"type": "boolean"},
        "exhaust_fan": {"type": "boolean"},
        "humidifier": {"type": "boolean"},
        "dehumidifier": {"type": "boolean"},
        "co2_doser": {"type": "boolean"}
      }
    },
    "previous_action": {"$ref": "#/$defs/action"},
    "trends": {
      "type": "object",
      "additionalProperties": false,
      "required": ["temperature", "humidity", "co2"],
      "properties": {
        "temperature": {"$ref": "#/$defs/trend"},
        "humidity": {"$ref": "#/$defs/trend"},
        "co2": {"$ref": "#/$defs/trend"}
      }
    },
    "features": {
      "type": "array",
      "minItems": 44,
      "maxItems": 44,
      "items": {"type": "number", "minimum": 0.0, "maximum": 1.0}
    },
    "rule": {"$ref": "#/$defs/evaluation"},
    "ml": {"$ref": "#/$defs/optionalEvaluation"},
    "applied": {"$ref": "#/$defs/action"},
    "effective_before": {"$ref": "#/$defs/action"},
    "effective_after": {"$ref": "#/$defs/action"}
  }
}
''').lstrip()

MODULE = dedent(r'''
"""Versioned climate-v6 runtime trace record.

A trace record captures only information available to the controller at one
control step. Simulator-hidden physical truth is intentionally excluded so the
same schema can be produced by host simulation, HIL, and eventual hardware.
This module defines the record and validation contract only; persistent NDJSON
recording belongs to the next stage.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import jsonschema

from .climate_input import (
    CLIMATE_V6_CONTRACT_PATH,
    DEFAULT_SENSOR_TIMEOUT_MS,
    ClimateInputConfig,
    MeasurementStatus,
    encode_climate_input,
)
from .climate_runtime import ClimateRuntimeDecision
from .climate_scenarios import ClimateProfile
from .climate_simulator import ClimateAction, ClimateScenario, ClimateState
from .contract import load_contract

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TRACE_SCHEMA_PATH = PROJECT_ROOT / "schemas" / "climate-runtime-trace.v1.json"
TRACE_SCHEMA_ID = "climate-runtime-trace"
TRACE_SCHEMA_VERSION = 1
_SENSOR_NAMES = (
    "air_temperature_c",
    "relative_humidity_pct",
    "co2_ppm",
    "outside_temperature_c",
    "outside_humidity_pct",
)


def _action(action: ClimateAction | None) -> dict[str, float] | None:
    if action is None:
        return None
    return {name: float(value) for name, value in action.as_dict().items()}


def _measurement(value: float, status: MeasurementStatus) -> dict[str, object]:
    return {"value": float(value), "valid": bool(status.valid), "age_ms": int(status.age_ms)}


def _interventions(values: Sequence[str]) -> list[str]:
    return list(dict.fromkeys(str(value) for value in values))


def _assert_finite(value: object, path: str = "record") -> None:
    if isinstance(value, bool) or value is None or isinstance(value, (str, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"non-finite trace value at {path}")
        return
    if isinstance(value, Mapping):
        for key, child in value.items():
            _assert_finite(child, f"{path}.{key}")
        return
    if isinstance(value, Sequence):
        for index, child in enumerate(value):
            _assert_finite(child, f"{path}[{index}]")
        return
    raise TypeError(f"unsupported trace value at {path}: {type(value).__name__}")


def load_climate_runtime_trace_schema() -> dict[str, Any]:
    with TRACE_SCHEMA_PATH.open("r", encoding="utf-8") as stream:
        document = json.load(stream)
    if not isinstance(document, dict):
        raise ValueError("trace schema root must be an object")
    jsonschema.Draft202012Validator.check_schema(document)
    return document


def validate_climate_runtime_trace_record(record: Mapping[str, Any]) -> None:
    _assert_finite(record)
    jsonschema.Draft202012Validator(load_climate_runtime_trace_schema()).validate(record)


def canonical_climate_runtime_trace_json(record: Mapping[str, Any]) -> str:
    validate_climate_runtime_trace_record(record)
    return json.dumps(
        record,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def build_climate_runtime_trace_record(
    scenario: ClimateScenario,
    state: ClimateState,
    profile: ClimateProfile,
    decision: ClimateRuntimeDecision,
    *,
    previous_command: ClimateAction | None = None,
    monotonic_ms: int,
    status: Mapping[str, MeasurementStatus] | None = None,
    sensor_timeout_ms: int = DEFAULT_SENSOR_TIMEOUT_MS,
    timestep_s: float | None = None,
    model_id: str | None = None,
    model_contract_hash: str | None = None,
) -> dict[str, Any]:
    """Build one hardware-replayable trace record from a completed runtime step."""

    if monotonic_ms < 0:
        raise ValueError("monotonic_ms must be non-negative")
    if sensor_timeout_ms < 0:
        raise ValueError("sensor_timeout_ms must be non-negative")
    dt = float(scenario.timestep_s if timestep_s is None else timestep_s)
    if not math.isfinite(dt) or dt <= 0.0:
        raise ValueError("timestep_s must be finite and positive")
    if (model_id is None) != (model_contract_hash is None):
        raise ValueError("model_id and model_contract_hash must be provided together")

    statuses = {name: (status or {}).get(name, MeasurementStatus()) for name in _SENSOR_NAMES}
    previous = previous_command or ClimateAction()
    contract = load_contract(CLIMATE_V6_CONTRACT_PATH)
    features = encode_climate_input(
        scenario,
        state,
        previous=previous,
        estimated_effective=decision.effective_before,
        trends=decision.trends,
        status=statuses,
        config=ClimateInputConfig(
            targets=profile.targets,
            humidity_control_mode=profile.humidity_control_mode,
            sensor_timeout_ms=sensor_timeout_ms,
        ),
    )

    values = {
        "air_temperature_c": state.air_temperature_c,
        "relative_humidity_pct": state.relative_humidity_pct,
        "co2_ppm": state.co2_ppm,
        "outside_temperature_c": state.outside_temperature_c,
        "outside_humidity_pct": state.outside_humidity_pct,
    }
    caps = scenario.actuators
    model = None
    if model_id is not None and model_contract_hash is not None:
        model = {"id": str(model_id), "contract_hash": str(model_contract_hash)}

    record: dict[str, Any] = {
        "schema_id": TRACE_SCHEMA_ID,
        "schema_version": TRACE_SCHEMA_VERSION,
        "contract": {
            "id": str(contract.document.get("contract_id", "")),
            "schema_version": int(contract.schema_version),
            "hash": contract.hash_hex,
        },
        "monotonic_ms": int(monotonic_ms),
        "sensor_timeout_ms": int(sensor_timeout_ms),
        "timestep_s": dt,
        "policy": {
            "mode": decision.mode.value,
            "status": decision.status.value,
            "authoritative_policy": decision.authoritative_policy,
        },
        "model": model,
        "measurements": {
            name: _measurement(values[name], statuses[name]) for name in _SENSOR_NAMES
        },
        "targets": {
            "air_temperature_c": float(profile.targets.air_temperature_c),
            "relative_humidity_pct": float(profile.targets.relative_humidity_pct),
            "air_vpd_kpa": float(profile.targets.air_vpd_kpa),
            "co2_enabled": bool(profile.targets.co2_enabled),
            "co2_ppm": float(profile.targets.co2_ppm),
        },
        "humidity_control_mode": profile.humidity_control_mode,
        "light_level": float(profile.light_level),
        "capabilities": {
            "heater": bool(caps.heater.available),
            "cooler": bool(caps.cooler.available),
            "exhaust_fan": bool(caps.exhaust_fan.available),
            "humidifier": bool(caps.humidifier.available),
            "dehumidifier": bool(caps.dehumidifier.available),
            "co2_doser": bool(caps.co2_doser.available),
        },
        "previous_action": _action(previous),
        "trends": {
            "temperature": {
                "rate_per_min": float(decision.trends.temperature.rate_per_min),
                "available": bool(decision.trends.temperature.available),
            },
            "humidity": {
                "rate_per_min": float(decision.trends.humidity.rate_per_min),
                "available": bool(decision.trends.humidity.available),
            },
            "co2": {
                "rate_per_min": float(decision.trends.co2.rate_per_min),
                "available": bool(decision.trends.co2.available),
            },
        },
        "features": [float(value) for value in features],
        "rule": {
            "raw": _action(decision.rule_raw),
            "arbitrated": _action(decision.rule_arbitrated),
            "safe": _action(decision.rule_safe),
            "arbitration_interventions": _interventions(
                decision.rule_arbitration_interventions
            ),
            "safety_interventions": _interventions(decision.rule_safety_interventions),
        },
        "ml": {
            "evaluated": decision.ml_safe is not None,
            "raw": _action(decision.ml_raw),
            "arbitrated": _action(decision.ml_arbitrated),
            "safe": _action(decision.ml_safe),
            "arbitration_interventions": _interventions(decision.ml_arbitration_interventions),
            "safety_interventions": _interventions(decision.ml_safety_interventions),
        },
        "applied": _action(decision.applied),
        "effective_before": _action(decision.effective_before),
        "effective_after": _action(decision.effective_after),
    }
    validate_climate_runtime_trace_record(record)
    return record


__all__ = [
    "TRACE_SCHEMA_ID",
    "TRACE_SCHEMA_PATH",
    "TRACE_SCHEMA_VERSION",
    "build_climate_runtime_trace_record",
    "canonical_climate_runtime_trace_json",
    "load_climate_runtime_trace_schema",
    "validate_climate_runtime_trace_record",
]
''').lstrip()

TESTS = dedent(r'''
from __future__ import annotations

import copy
import json

import jsonschema
import numpy as np
import pytest

from tools.ml.climate_input import CLIMATE_V6_CONTRACT_PATH, MeasurementStatus
from tools.ml.climate_runtime import ClimatePolicyMode, ClimateRuntimeConfig, ClimateRuntimeController
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
    status = (
        {"air_temperature_c": MeasurementStatus(valid=False, age_ms=0)}
        if sensor_fault
        else {}
    )
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
    assert "required_sensor_unusable" in record["rule"]["safety_interventions"] or record[
        "rule"
    ]["safe"] == ClimateAction().as_dict()


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
''').lstrip()

FILES = {
    ROOT / "schemas" / "climate-runtime-trace.v1.json": SCHEMA,
    ROOT / "tools" / "ml" / "climate_trace.py": MODULE,
    ROOT / "tests" / "test_climate_trace.py": TESTS,
}

for path, content in FILES.items():
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
