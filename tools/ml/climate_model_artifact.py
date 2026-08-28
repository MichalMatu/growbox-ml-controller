"""Portable climate-v6 MLP artifact and NumPy inference.

The artifact stores exact float32 weights for a two-hidden-layer 44 -> H1 -> H2 -> 6
Keras model plus contract identity. NumPy inference is deliberately independent
of TensorFlow so closed-loop benchmarks and later embedded export exercise the
persisted model rather than an in-memory training object.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

_WEIGHT_KEYS = ("w1", "b1", "w2", "b2", "w3", "b3")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class ClimateModelMetadata:
    schema_version: int
    contract_hash: str
    feature_names: tuple[str, ...]
    output_names: tuple[str, ...]
    training_seed: int
    candidate_name: str
    source_commit: str

    def validate(self) -> None:
        if self.schema_version != 6:
            raise ValueError("portable climate model requires schema v6")
        if len(self.contract_hash) != 64 or any(
            ch not in "0123456789abcdef" for ch in self.contract_hash
        ):
            raise ValueError("contract_hash must be a lowercase SHA-256 hex digest")
        if len(self.feature_names) != 44 or len(set(self.feature_names)) != 44:
            raise ValueError("portable climate model requires 44 unique feature names")
        if len(self.output_names) != 6 or len(set(self.output_names)) != 6:
            raise ValueError("portable climate model requires 6 unique output names")
        if not self.candidate_name:
            raise ValueError("candidate_name is required")
        if not self.source_commit:
            raise ValueError("source_commit is required")


def _validate_weight_arrays(weights: tuple[np.ndarray, ...]) -> None:
    if len(weights) != len(_WEIGHT_KEYS):
        raise ValueError("portable climate model must contain six weight arrays")

    arrays = tuple(np.asarray(value) for value in weights)
    w1, b1, w2, b2, w3, b3 = arrays

    if w1.ndim != 2 or w1.shape[0] != 44 or w1.shape[1] <= 0:
        raise ValueError(f"weight 0 has shape {w1.shape}, expected (44, H1)")
    hidden_1 = int(w1.shape[1])
    if b1.shape != (hidden_1,):
        raise ValueError(f"weight 1 has shape {b1.shape}, expected ({hidden_1},)")

    if w2.ndim != 2 or w2.shape[0] != hidden_1 or w2.shape[1] <= 0:
        raise ValueError(f"weight 2 has shape {w2.shape}, expected ({hidden_1}, H2)")
    hidden_2 = int(w2.shape[1])
    if b2.shape != (hidden_2,):
        raise ValueError(f"weight 3 has shape {b2.shape}, expected ({hidden_2},)")

    if w3.shape != (hidden_2, 6):
        raise ValueError(f"weight 4 has shape {w3.shape}, expected ({hidden_2}, 6)")
    if b3.shape != (6,):
        raise ValueError(f"weight 5 has shape {b3.shape}, expected (6,)")

    for index, value in enumerate(arrays):
        if value.dtype != np.float32:
            raise ValueError(f"weight {index} must be float32")
        if not np.isfinite(value).all():
            raise ValueError(f"weight {index} contains NaN/Inf")


@dataclass(frozen=True)
class ClimatePortableModel:
    metadata: ClimateModelMetadata
    weights: tuple[np.ndarray, ...]

    def __post_init__(self) -> None:
        self.metadata.validate()
        _validate_weight_arrays(self.weights)

    @property
    def parameter_count(self) -> int:
        return int(sum(array.size for array in self.weights))

    @property
    def hidden_units(self) -> tuple[int, int]:
        return int(self.weights[0].shape[1]), int(self.weights[2].shape[1])

    def predict(self, features: np.ndarray) -> np.ndarray:
        values = np.asarray(features, dtype=np.float32)
        single = values.ndim == 1
        if single:
            values = values.reshape(1, -1)
        if values.ndim != 2 or values.shape[1] != 44:
            raise ValueError("portable climate model expects shape (44,) or (N, 44)")
        if not np.isfinite(values).all():
            raise ValueError("model input contains NaN/Inf")
        w1, b1, w2, b2, w3, b3 = self.weights
        hidden1 = np.maximum(values @ w1 + b1, np.float32(0.0))
        hidden2 = np.maximum(hidden1 @ w2 + b2, np.float32(0.0))
        logits = hidden2 @ w3 + b3
        logits = np.clip(logits, np.float32(-60.0), np.float32(60.0))
        output = np.float32(1.0) / (np.float32(1.0) + np.exp(-logits))
        output = np.asarray(output, dtype=np.float32)
        if not np.isfinite(output).all():
            raise ValueError("portable model produced NaN/Inf")
        return output[0] if single else output


def from_keras_model(model: Any, metadata: ClimateModelMetadata) -> ClimatePortableModel:
    metadata.validate()
    raw_weights = model.get_weights()
    if len(raw_weights) != len(_WEIGHT_KEYS):
        raise ValueError("unexpected Keras weight array count for climate-v6 MLP")
    weights = tuple(np.asarray(value, dtype=np.float32) for value in raw_weights)
    return ClimatePortableModel(metadata=metadata, weights=weights)


def save_portable_model(
    model: ClimatePortableModel,
    weights_path: str | Path,
    metadata_path: str | Path,
) -> None:
    weights_destination = Path(weights_path)
    metadata_destination = Path(metadata_path)
    weights_destination.parent.mkdir(parents=True, exist_ok=True)
    metadata_destination.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        weights_destination,
        **{key: value for key, value in zip(_WEIGHT_KEYS, model.weights, strict=True)},
    )
    weights_sha256 = _sha256_file(weights_destination)
    payload = {
        "schema_version": model.metadata.schema_version,
        "contract_hash": model.metadata.contract_hash,
        "feature_names": list(model.metadata.feature_names),
        "output_names": list(model.metadata.output_names),
        "training_seed": model.metadata.training_seed,
        "candidate_name": model.metadata.candidate_name,
        "source_commit": model.metadata.source_commit,
        "parameter_count": model.parameter_count,
        "weights_file": weights_destination.name,
        "weights_format": "npz-float32-v1",
        "weights_sha256": weights_sha256,
    }
    metadata_destination.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def load_portable_model(
    weights_path: str | Path,
    metadata_path: str | Path,
) -> ClimatePortableModel:
    weights_source = Path(weights_path)
    metadata_source = Path(metadata_path)
    payload = json.loads(metadata_source.read_text(encoding="utf-8"))
    expected_sha256 = str(payload.get("weights_sha256", ""))
    actual_sha256 = _sha256_file(weights_source)
    if expected_sha256 != actual_sha256:
        raise ValueError("portable climate model weights SHA-256 mismatch")
    metadata = ClimateModelMetadata(
        schema_version=int(payload["schema_version"]),
        contract_hash=str(payload["contract_hash"]),
        feature_names=tuple(str(value) for value in payload["feature_names"]),
        output_names=tuple(str(value) for value in payload["output_names"]),
        training_seed=int(payload["training_seed"]),
        candidate_name=str(payload["candidate_name"]),
        source_commit=str(payload["source_commit"]),
    )
    with np.load(weights_source, allow_pickle=False) as archive:
        if set(archive.files) != set(_WEIGHT_KEYS):
            raise ValueError("portable climate model has unexpected weight keys")
        weights = tuple(np.asarray(archive[key], dtype=np.float32) for key in _WEIGHT_KEYS)
    model = ClimatePortableModel(metadata=metadata, weights=weights)
    if int(payload.get("parameter_count", -1)) != model.parameter_count:
        raise ValueError("portable climate model parameter count metadata mismatch")
    if payload.get("weights_format") != "npz-float32-v1":
        raise ValueError("unsupported portable climate model weight format")
    if payload.get("weights_file") != weights_source.name:
        raise ValueError("portable climate model weights filename mismatch")
    return model


def max_prediction_delta(
    keras_model: Any,
    portable: ClimatePortableModel,
    features: np.ndarray,
) -> float:
    keras_prediction = np.asarray(keras_model(features, training=False), dtype=np.float32)
    portable_prediction = portable.predict(features)
    if keras_prediction.shape != portable_prediction.shape:
        raise ValueError("Keras and portable prediction shapes differ")
    delta = float(
        np.max(np.abs(keras_prediction.astype(np.float64) - portable_prediction.astype(np.float64)))
    )
    if not math.isfinite(delta):
        raise ValueError("prediction delta is not finite")
    return delta


__all__ = [
    "ClimateModelMetadata",
    "ClimatePortableModel",
    "from_keras_model",
    "load_portable_model",
    "max_prediction_delta",
    "save_portable_model",
]
