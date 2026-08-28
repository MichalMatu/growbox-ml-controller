"""Create a behavior-preserving 44-input compatibility artifact for Stage 13.

This is not retraining. The six new estimated-effective inputs receive zero first-layer
weights, while all historical weights and biases are preserved exactly. The artifact is
therefore only a regression compatibility baseline; later Stage 13 ablation must train a
model that can actually use the new observability features.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from .climate_input import CLIMATE_V6_CONTRACT_PATH
from .climate_model_artifact import ClimateModelMetadata, ClimatePortableModel, save_portable_model
from .contract import load_contract

SOURCE_WEIGHTS = Path("reports/ml/climate_v6_model_seed1847.npz")
SOURCE_METADATA = Path("reports/ml/climate_v6_model_seed1847.json")
DEST_WEIGHTS = Path("reports/ml/climate_v6_model_stage13_compat.npz")
DEST_METADATA = Path("reports/ml/climate_v6_model_stage13_compat.json")
INSERT_AT = 32
INSERTED_FEATURES = (
    "estimated_effective_heater",
    "estimated_effective_cooler",
    "estimated_effective_exhaust_fan",
    "estimated_effective_humidifier",
    "estimated_effective_dehumidifier",
    "estimated_effective_co2_doser",
)


def _old_predict(features: np.ndarray, weights: tuple[np.ndarray, ...]) -> np.ndarray:
    w1, b1, w2, b2, w3, b3 = weights
    h1 = np.maximum(features @ w1 + b1, np.float32(0.0))
    h2 = np.maximum(h1 @ w2 + b2, np.float32(0.0))
    logits = np.clip(h2 @ w3 + b3, np.float32(-60.0), np.float32(60.0))
    return np.asarray(np.float32(1.0) / (np.float32(1.0) + np.exp(-logits)), dtype=np.float32)


def main() -> None:
    contract = load_contract(CLIMATE_V6_CONTRACT_PATH)
    if len(contract.feature_names) != 44:
        raise ValueError("Stage 13 compatibility migration requires a 44-feature contract")
    if tuple(contract.feature_names[INSERT_AT : INSERT_AT + 6]) != INSERTED_FEATURES:
        raise ValueError("Stage 13 estimated-effective feature order is unexpected")

    source_payload = json.loads(SOURCE_METADATA.read_text(encoding="utf-8"))
    old_names = tuple(str(value) for value in source_payload["feature_names"])
    expected_old_names = tuple(
        contract.feature_names[:INSERT_AT] + contract.feature_names[INSERT_AT + 6 :]
    )
    if old_names != expected_old_names:
        raise ValueError(
            "historical regression artifact feature order does not match the Stage 13 base contract"
        )
    if tuple(str(value) for value in source_payload["output_names"]) != contract.outputs:
        raise ValueError(
            "historical regression artifact output order does not match the active contract"
        )

    with np.load(SOURCE_WEIGHTS, allow_pickle=False) as archive:
        old_weights = tuple(
            np.asarray(archive[key], dtype=np.float32)
            for key in ("w1", "b1", "w2", "b2", "w3", "b3")
        )
    old_w1 = old_weights[0]
    if old_w1.ndim != 2 or old_w1.shape[0] != 38:
        raise ValueError(f"historical first-layer shape is {old_w1.shape}, expected (38, H1)")
    zeros = np.zeros((6, old_w1.shape[1]), dtype=np.float32)
    new_w1 = np.concatenate((old_w1[:INSERT_AT], zeros, old_w1[INSERT_AT:]), axis=0)
    new_weights = (new_w1, *old_weights[1:])

    metadata = ClimateModelMetadata(
        schema_version=contract.schema_version,
        contract_hash=contract.hash_hex,
        feature_names=contract.feature_names,
        output_names=contract.outputs,
        training_seed=int(source_payload["training_seed"]),
        candidate_name=str(source_payload["candidate_name"]) + "_stage13_zero_effective_compat",
        source_commit=str(source_payload["source_commit"]),
    )
    model = ClimatePortableModel(metadata=metadata, weights=new_weights)

    rng = np.random.default_rng(13_044)
    old_features = rng.uniform(0.0, 1.0, size=(128, 38)).astype(np.float32)
    new_features = np.concatenate(
        (
            old_features[:, :INSERT_AT],
            np.zeros((len(old_features), 6), dtype=np.float32),
            old_features[:, INSERT_AT:],
        ),
        axis=1,
    )
    old_prediction = _old_predict(old_features, old_weights)
    new_prediction = model.predict(new_features)
    max_delta = float(
        np.max(np.abs(old_prediction.astype(np.float64) - new_prediction.astype(np.float64)))
    )
    if max_delta > 2.0e-6:
        raise AssertionError(
            f"Stage 13 compatibility migration changed predictions by {max_delta:.9g}"
        )

    save_portable_model(model, DEST_WEIGHTS, DEST_METADATA)
    payload = json.loads(DEST_METADATA.read_text(encoding="utf-8"))
    payload["migration"] = {
        "kind": "stage13_zero_weight_input_expansion",
        "source_weights_file": SOURCE_WEIGHTS.name,
        "source_metadata_file": SOURCE_METADATA.name,
        "inserted_feature_names": list(INSERTED_FEATURES),
        "inserted_first_layer_weights": "all_zero",
        "prediction_max_delta": max_delta,
        "trained_on_new_features": False,
    }
    DEST_METADATA.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"STAGE13_COMPAT_PARAMETER_COUNT={model.parameter_count}")
    print(f"STAGE13_COMPAT_MAX_DELTA={max_delta:.9g}")
    print("STAGE13_COMPAT_ARTIFACT=PASS")


if __name__ == "__main__":
    main()
