from __future__ import annotations

import json
import subprocess
from dataclasses import asdict
from pathlib import Path

import numpy as np

from tools.ml.climate_input import CLIMATE_V6_CONTRACT_PATH
from tools.ml.climate_model_artifact import (
    ClimateModelMetadata,
    from_keras_model,
    load_portable_model,
    max_prediction_delta,
    save_portable_model,
)
from tools.ml.climate_simulator import CLIMATE_OUTPUT_NAMES
from tools.ml.climate_training_weighted import (
    WeightedTrainingConfig,
    compare_weighted_candidates,
    comparison_summary,
)
from tools.ml.contract import load_contract
from tools.ml.dataset import Dataset

SEED = 1847
DATASET_CACHE = Path("build/climate_v6_full_seed1847_vpd.npz")
METADATA_CACHE = Path("build/climate_v6_full_seed1847_vpd_metadata.npz")
AUDIT_REPORT = Path("reports/ml/climate_v6_dataset_audit_seed1847_vpd.json")
BUILD_REPORT = Path("build/climate_v6_weighted_training_seed1847_vpd.json")
REPORT_PATH = Path("reports/ml/climate_v6_weighted_training_seed1847_vpd.json")
WEIGHTS_PATH = Path("reports/ml/climate_v6_model_seed1847_vpd.npz")
MODEL_METADATA_PATH = Path("reports/ml/climate_v6_model_seed1847_vpd.json")


def _load_audited_dataset() -> tuple[Dataset, dict[str, object], dict[str, np.ndarray]]:
    if not DATASET_CACHE.exists() or not METADATA_CACHE.exists():
        raise FileNotFoundError(
            "Stage 9B audited dataset cache is missing; rerun Stage 9B before Stage 9C"
        )
    audit = json.loads(AUDIT_REPORT.read_text(encoding="utf-8"))
    if audit["audit"]["ready_for_training"] is not True:
        raise ValueError("Stage 9B report is not ready for training")
    if audit["config"]["rows"] != 7200 or audit["config"]["families"] != 15:
        raise ValueError("Stage 9B report does not describe the expected 7200-row dataset")

    dataset = Dataset.load(DATASET_CACHE)
    if dataset.features.shape != (7200, 38) or dataset.labels.shape != (7200, 6):
        raise ValueError("Stage 9B cached dataset shape mismatch")
    if dataset.output_names != CLIMATE_OUTPUT_NAMES:
        raise ValueError("Stage 9B cached dataset output order mismatch")
    split_counts = {
        split: int(np.sum(dataset.splits == split)) for split in ("train", "validation", "test")
    }
    if split_counts != {"train": 4800, "validation": 1200, "test": 1200}:
        raise ValueError(f"unexpected Stage 9B split counts: {split_counts}")

    with np.load(METADATA_CACHE, allow_pickle=False) as archive:
        metadata = {name: np.asarray(archive[name]) for name in archive.files}
    for required in ("families", "profiles", "humidity_modes", "safe_fallbacks"):
        if required not in metadata or len(metadata[required]) != 7200:
            raise ValueError(f"Stage 9B metadata cache missing/invalid field {required!r}")
    modes = metadata["humidity_modes"]
    if int(np.sum(modes == "VPD")) != 960 or int(np.sum(modes == "RH")) != 6240:
        raise ValueError("Stage 9B humidity-mode cache does not match audited coverage")
    return dataset, audit, metadata


def _strong_ratio_report(dataset: Dataset, predictions: np.ndarray, strong_threshold: float) -> dict[str, dict[str, float | int]]:
    _, y_test = dataset.select("test")
    result: dict[str, dict[str, float | int]] = {}
    for index, name in enumerate(CLIMATE_OUTPUT_NAMES):
        expected = y_test[:, index]
        predicted = predictions[:, index]
        mask = expected > strong_threshold
        if not np.any(mask):
            raise ValueError(f"test split has no strong labels for {name}")
        ratio = predicted[mask] / np.maximum(expected[mask], np.float32(1.0e-6))
        result[name] = {
            "strong_count": int(np.sum(mask)),
            "mean_expected": float(np.mean(expected[mask])),
            "mean_predicted": float(np.mean(predicted[mask])),
            "mean_prediction_to_teacher_ratio": float(np.mean(ratio)),
            "p10_prediction_to_teacher_ratio": float(np.quantile(ratio, 0.10)),
            "strong_recall": float(np.mean(predicted[mask] > strong_threshold)),
        }
    return result


def main() -> None:
    print("STAGE9C_WEIGHTED_TRAINING_START", flush=True)
    dataset, audit, metadata = _load_audited_dataset()
    config = WeightedTrainingConfig.full(seed=SEED)
    comparison = compare_weighted_candidates(dataset, config=config)
    for line in comparison_summary(comparison):
        print(line, flush=True)

    winner = comparison.winner
    if winner.test is None:
        raise AssertionError("winner test metrics are missing")
    x_test, _ = dataset.select("test")
    test_predictions = np.asarray(winner.model(x_test, training=False), dtype=np.float32)
    strong_ratio = _strong_ratio_report(dataset, test_predictions, config.strong_threshold)

    contract = load_contract(CLIMATE_V6_CONTRACT_PATH)
    source_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    model_metadata = ClimateModelMetadata(
        schema_version=contract.schema_version,
        contract_hash=contract.hash_hex,
        feature_names=contract.feature_names,
        output_names=contract.outputs,
        training_seed=SEED,
        candidate_name=winner.spec.name,
        source_commit=source_commit,
    )
    portable = from_keras_model(winner.model, model_metadata)
    verification_features = dataset.features[:512]
    portable_delta = max_prediction_delta(winner.model, portable, verification_features)
    if portable_delta > 2.0e-5:
        raise AssertionError(f"portable inference differs from Keras by {portable_delta:.9g}")
    save_portable_model(portable, WEIGHTS_PATH, MODEL_METADATA_PATH)
    loaded = load_portable_model(WEIGHTS_PATH, MODEL_METADATA_PATH)
    np.testing.assert_array_equal(
        loaded.predict(verification_features),
        portable.predict(verification_features),
    )

    baseline = next(
        result for result in comparison.candidates if result.spec.name == "adam_huber_baseline"
    )
    validation_improvement = (
        baseline.validation.control_mae - winner.validation.control_mae
    ) / max(baseline.validation.control_mae, 1.0e-12)

    payload = {
        "schema_version": contract.schema_version,
        "contract_hash": contract.hash_hex,
        "git_commit": source_commit,
        "dataset": {
            "cache": str(DATASET_CACHE),
            "metadata_cache": str(METADATA_CACHE),
            "rows": int(dataset.features.shape[0]),
            "split_counts": audit["audit"]["split_counts"],
            "humidity_mode_counts": audit["audit"]["humidity_mode_counts"],
            "vpd_rows": int(np.sum(metadata["humidity_modes"] == "VPD")),
        },
        "training": {
            "config": asdict(config),
            "selection_metric": [
                "validation.control_mae",
                "validation.strong_mae",
                "validation.balanced_mae",
                "-validation.strong_recall",
                "-validation.macro_f1",
                "validation.mae",
            ],
            "winner": winner.spec.name,
            "baseline": baseline.spec.name,
            "validation_control_mae_relative_improvement_vs_baseline": validation_improvement,
            "candidates": [
                {
                    "spec": asdict(result.spec),
                    "validation": asdict(result.validation),
                }
                for result in comparison.candidates
            ],
            "winner_test": asdict(winner.test),
            "winner_test_strong_ratio": strong_ratio,
        },
        "artifact": {
            "weights_file": str(WEIGHTS_PATH),
            "metadata_file": str(MODEL_METADATA_PATH),
            "portable_max_prediction_delta": portable_delta,
            "parameter_count": portable.parameter_count,
        },
    }
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    BUILD_REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    BUILD_REPORT.write_text(text, encoding="utf-8")
    REPORT_PATH.write_text(text, encoding="utf-8")

    print(
        "STAGE9C_VALIDATION_CONTROL_IMPROVEMENT="
        f"{validation_improvement:.6f}",
        flush=True,
    )
    print(f"STAGE9C_STRONG_RATIO={strong_ratio}", flush=True)
    print(f"STAGE9C_PORTABLE_MAX_DELTA={portable_delta:.9g}", flush=True)
    print(f"STAGE9C_REPORT={REPORT_PATH}", flush=True)
    print("STAGE9C_WEIGHTED_TRAINING=PASS", flush=True)


if __name__ == "__main__":
    main()
