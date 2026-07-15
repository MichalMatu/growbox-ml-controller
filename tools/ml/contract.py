"""Load and apply the shared environment-controller data contract."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONTRACT_PATH = PROJECT_ROOT / "schemas" / "environment-controller-v1.json"


def canonical_json_bytes(document: Mapping[str, Any]) -> bytes:
    return json.dumps(
        document,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def schema_digest(document: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json_bytes(document)).hexdigest()


@dataclass(frozen=True)
class FeatureSpec:
    name: str
    path: str
    minimum: float
    maximum: float
    default: float
    encoding: Mapping[str, float] | None = None

    def normalize(self, value: Any) -> float:
        if isinstance(value, bool):
            numeric = 1.0 if value else 0.0
        elif isinstance(value, str):
            encodings = self.encoding or {}
            if value not in encodings:
                raise ValueError(f"unsupported categorical value {value!r} for {self.name}")
            numeric = encodings[value]
        else:
            try:
                numeric = float(value)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"invalid numeric value {value!r} for {self.name}") from exc
        if not math.isfinite(numeric):
            raise ValueError(f"non-finite value for {self.name}")
        numeric = min(self.maximum, max(self.minimum, numeric))
        width = self.maximum - self.minimum
        if width <= 0.0:
            raise ValueError(f"invalid normalization range for {self.name}")
        return (numeric - self.minimum) / width


@dataclass(frozen=True)
class Contract:
    document: Mapping[str, Any]
    path: Path
    schema_version: int
    hash_hex: str
    features: tuple[FeatureSpec, ...]
    outputs: tuple[str, ...]

    @property
    def short_hash(self) -> str:
        return self.hash_hex[:12]

    @property
    def feature_names(self) -> tuple[str, ...]:
        return tuple(feature.name for feature in self.features)

    def encode(self, controller_input: Mapping[str, Any]) -> np.ndarray:
        encoded: list[float] = []
        feature_by_path = {feature.path: feature for feature in self.features}
        for feature in self.features:
            value = _resolve_path_or_default(controller_input, feature.path, feature.default)
            # Validate every supplied value before applying a sensor mask. This
            # mirrors the firmware fail-safe contract: NaN/Inf is never an
            # encoding for "missing"; use a false mask plus a finite value or
            # omit the value so its schema default is used.
            normalized = feature.normalize(value)
            if feature.path.startswith("sensors."):
                sensor_name = feature.path.split(".", 1)[1]
                validity_path = f"validity.{sensor_name}"
                validity_feature = feature_by_path.get(validity_path)
                if validity_feature is None:
                    raise ValueError(f"contract has no validity feature for {feature.path!r}")
                valid = _resolve_path_or_default(
                    controller_input, validity_path, validity_feature.default
                )
                if not bool(valid):
                    normalized = feature.normalize(feature.default)
            encoded.append(normalized)
        return np.asarray(encoded, dtype=np.float32)

    def output_vector(self, values: Mapping[str, Any] | Sequence[float]) -> np.ndarray:
        if isinstance(values, Mapping):
            vector = [float(values[name]) for name in self.outputs]
        else:
            vector = [float(value) for value in values]
        if len(vector) != len(self.outputs):
            raise ValueError("output count does not match contract")
        if not all(math.isfinite(value) for value in vector):
            raise ValueError("model outputs must be finite")
        return np.clip(np.asarray(vector, dtype=np.float32), 0.0, 1.0)


def _number(entry: Mapping[str, Any], *keys: str, fallback: float | None = None) -> float:
    for key in keys:
        if key in entry:
            return float(entry[key])
    normalization = entry.get("normalization")
    if isinstance(normalization, Mapping):
        for key in keys:
            if key in normalization:
                return float(normalization[key])
    if fallback is None:
        raise ValueError(f"missing one of {keys} in feature {entry!r}")
    return float(fallback)


def _parse_feature(entry: Any) -> FeatureSpec:
    if not isinstance(entry, Mapping):
        raise ValueError("model.features entries must be objects")
    name = str(entry.get("name", ""))
    if not name:
        raise ValueError("model feature has no name")
    path = entry.get("path")
    if not isinstance(path, str) or not path or len(path.split(".")) < 2:
        raise ValueError(f"model feature {name!r} has no valid path")
    if "source" in entry:
        raise ValueError(f"model feature {name!r} uses obsolete source metadata")
    minimum = _number(entry, "minimum", "min")
    maximum = _number(entry, "maximum", "max")
    default = _number(entry, "default", fallback=minimum)
    raw_encoding = entry.get("encoding")
    encoding = None
    if isinstance(raw_encoding, Mapping):
        encoding = {str(key): float(value) for key, value in raw_encoding.items()}
    return FeatureSpec(name, path, minimum, maximum, default, encoding)


def _parse_outputs(entries: Any) -> tuple[str, ...]:
    if not isinstance(entries, list):
        raise ValueError("model.outputs must be an array")
    outputs: list[str] = []
    for entry in entries:
        name = entry.get("name") if isinstance(entry, Mapping) else entry
        if not isinstance(name, str) or not name:
            raise ValueError("invalid model output entry")
        outputs.append(name)
    if len(outputs) != len(set(outputs)):
        raise ValueError("model output names must be unique")
    return tuple(outputs)


def load_contract(path: str | Path = DEFAULT_CONTRACT_PATH) -> Contract:
    contract_path = Path(path).resolve()
    with contract_path.open("r", encoding="utf-8") as stream:
        document = json.load(stream)
    if not isinstance(document, Mapping):
        raise ValueError("contract root must be an object")
    model = document.get("model")
    if not isinstance(model, Mapping):
        raise ValueError("contract is missing model metadata")
    raw_features = model.get("features")
    if not isinstance(raw_features, list):
        raise ValueError("model.features must be an array")
    features = tuple(_parse_feature(entry) for entry in raw_features)
    if not features or len(features) != len({feature.name for feature in features}):
        raise ValueError("model feature names must be non-empty and unique")
    if len(features) != len({feature.path for feature in features}):
        raise ValueError("model feature paths must be unique")
    outputs = _parse_outputs(model.get("outputs"))
    version = document.get("schema_version", document.get("version"))
    if not isinstance(version, int):
        raise ValueError("schema_version must be an integer")
    return Contract(
        document=document,
        path=contract_path,
        schema_version=version,
        hash_hex=schema_digest(document),
        features=features,
        outputs=outputs,
    )


def _resolve_path(document: Mapping[str, Any], path: str) -> Any:
    current: Any = document
    for part in path.split("."):
        if not isinstance(current, Mapping) or part not in current:
            raise KeyError(f"contract feature path {path!r} is absent from controller input")
        current = current[part]
    return current


def _resolve_path_or_default(document: Mapping[str, Any], path: str, default: Any) -> Any:
    try:
        return _resolve_path(document, path)
    except KeyError:
        return default
