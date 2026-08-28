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
    if isinstance(value, bool) or value is None or isinstance(value, str | int):
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
            "arbitration_interventions": _interventions(decision.rule_arbitration_interventions),
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
