from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np

from tools.ml.climate_dataset import (
    ClimateDatasetConfig,
    assert_climate_dataset_ready,
    audit_climate_dataset,
)
from tools.ml.climate_dataset_parallel import generate_climate_dataset_parallel
from tools.ml.climate_input import CLIMATE_V6_CONTRACT_PATH
from tools.ml.climate_model_artifact import (
    ClimateModelMetadata,
    from_keras_model,
    load_portable_model,
    max_prediction_delta,
    save_portable_model,
)
from tools.ml.climate_training import ClimateTrainingConfig, compare_candidates
from tools.ml.contract import load_contract
from tools.ml.dataset import Dataset

SEED = 1847
CACHE_PATH = Path("build/climate_v6_full_seed1847.npz")
TRAINING_REPORT = Path("reports/ml/climate_v6_training_seed1847.json")
WEIGHTS_PATH = Path("reports/ml/climate_v6_model_seed1847.npz")
METADATA_PATH = Path("reports/ml/climate_v6_model_seed1847.json")


def _worker_count() -> int:
    override = os.environ.get("CLIMATE_DATASET_WORKERS")
    if override is not None:
        workers = int(override)
        if workers <= 0:
            raise ValueError("CLIMATE_DATASET_WORKERS must be positive")
        return workers
    cpu_count = os.cpu_count() or 2
    return max(1, min(6, max(1, cpu_count - 2)))


def _load_or_generate_dataset() -> tuple[Dataset, int, bool]:
    if CACHE_PATH.exists():
        dataset = Dataset.load(CACHE_PATH)
        return dataset, 0, True
    workers = _worker_count()
    config = ClimateDatasetConfig.full(seed=SEED)
    bundle = generate_climate_dataset_parallel(config, workers=workers)
    audit = audit_climate_dataset(bundle)
    assert_climate_dataset_ready(
        audit,
        require_family_coverage_in_each_split=True,
        bundle=bundle,
    )
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    bundle.dataset.save(CACHE_PATH)
    return bundle.dataset, workers, False


def _metric_delta(actual: float, expected: float) -> float:
    return abs(float(actual) - float(expected))


def main() -> None:
    report = json.loads(TRAINING_REPORT.read_text(encoding="utf-8"))
    contract = load_contract(CLIMATE_V6_CONTRACT_PATH)
    if report["schema_version"] != 6 or report["contract_hash"] != contract.hash_hex:
        raise ValueError("training report contract does not match active climate-v6 contract")

    dataset, generation_workers, cache_reused = _load_or_generate_dataset()
    if dataset.features.shape != (6240, 38) or dataset.labels.shape != (6240, 6):
        raise ValueError("unexpected full climate-v6 dataset shape")
    if dataset.output_names != contract.outputs or dataset.feature_names != contract.feature_names:
        raise ValueError("cached dataset contract ordering mismatch")

    config = ClimateTrainingConfig.full(seed=SEED)
    comparison = compare_candidates(dataset, config=config)
    winner = comparison.winner
    if winner.test is None:
        raise AssertionError("winner test metrics are missing")
    expected_winner = str(report["training"]["winner"])
    if winner.spec.name != expected_winner:
        raise AssertionError(
            f"reproduced winner {winner.spec.name!r} differs from report {expected_winner!r}"
        )

    reported_test = report["training"]["winner_test"]
    for metric_name in ("balanced_mae", "mae", "rmse", "macro_f1"):
        delta = _metric_delta(getattr(winner.test, metric_name), reported_test[metric_name])
        if delta > 1.0e-6:
            raise AssertionError(
                f"reproduced {metric_name} differs from report by {delta:.9g}"
            )

    metadata = ClimateModelMetadata(
        schema_version=contract.schema_version,
        contract_hash=contract.hash_hex,
        feature_names=contract.feature_names,
        output_names=contract.outputs,
        training_seed=SEED,
        candidate_name=winner.spec.name,
        source_commit=str(report["git_commit"]),
    )
    portable = from_keras_model(winner.model, metadata)
    verification_features = dataset.features[: min(512, len(dataset.features))]
    prediction_delta = max_prediction_delta(
        winner.model,
        portable,
        verification_features,
    )
    if prediction_delta > 2.0e-5:
        raise AssertionError(
            f"portable inference differs from Keras by {prediction_delta:.9g}"
        )

    save_portable_model(portable, WEIGHTS_PATH, METADATA_PATH)
    loaded = load_portable_model(WEIGHTS_PATH, METADATA_PATH)
    np.testing.assert_array_equal(
        loaded.predict(verification_features),
        portable.predict(verification_features),
    )

    artifact_metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
    report["artifact"] = {
        "weights_file": str(WEIGHTS_PATH),
        "metadata_file": str(METADATA_PATH),
        "weights_sha256": artifact_metadata["weights_sha256"],
        "weights_format": artifact_metadata["weights_format"],
        "portable_max_prediction_delta": prediction_delta,
        "dataset_cache_reused": cache_reused,
        "dataset_generation_workers": generation_workers,
    }
    TRAINING_REPORT.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"PORTABLE_MODEL_WINNER={winner.spec.name}", flush=True)
    print(f"PORTABLE_MODEL_MAX_DELTA={prediction_delta:.9g}", flush=True)
    print(f"PORTABLE_MODEL_WEIGHTS={WEIGHTS_PATH}", flush=True)
    print("CLIMATE_V6_PORTABLE_MODEL=PASS", flush=True)


if __name__ == "__main__":
    main()
