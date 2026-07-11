"""Run the deterministic dataset, Keras training, emlearn export, and verification."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import importlib.metadata
import json
from pathlib import Path
import tempfile
from typing import Any

import numpy as np

from .contract import PROJECT_ROOT, load_contract
from .export_model import (
    DEFAULT_GENERATED_DIR,
    DEFAULT_GOLDEN_HEADER,
    DEFAULT_GOLDEN_JSON,
    ExportResult,
    export_model,
    render_golden_header,
)
from .generate_dataset import Dataset, DatasetConfig, generate_dataset
from .teacher import CostConfig, RolloutTeacher
from .train_model import TrainingConfig, TrainingResult, train
from .verify_export import VerificationResult, verify_export


DEFAULT_ARTIFACT_ROOT = PROJECT_ROOT / "build" / "ml"
GOLDEN_FEATURE_ATOL = 5.0e-7
GOLDEN_EXPECTED_ATOL = 2.0e-5


@dataclass(frozen=True)
class PipelineResult:
    mode: str
    dataset: Dataset
    training: TrainingResult
    export: ExportResult
    verification: VerificationResult
    report_path: Path


def _package_version(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "not-installed"


def _dataset_report(dataset: Dataset) -> dict[str, object]:
    splits: dict[str, object] = {}
    for split in ("train", "validation", "test"):
        mask = dataset.splits == split
        splits[split] = {
            "rows": int(np.count_nonzero(mask)),
            "scenarios": int(len(set(dataset.scenario_ids[mask].tolist()))),
        }
    return {
        "rows": int(len(dataset.features)),
        "scenarios": int(len(set(dataset.scenario_ids.tolist()))),
        "feature_count": int(dataset.features.shape[1]),
        "output_count": int(dataset.labels.shape[1]),
        "splits": splits,
    }


def _write_report(
    path: Path,
    *,
    mode: str,
    seed: int,
    dataset: Dataset,
    training: TrainingResult,
    exported: ExportResult,
    verification: VerificationResult,
    teacher: RolloutTeacher,
) -> None:
    contract = load_contract()
    document: dict[str, Any] = {
        "schema_version": contract.schema_version,
        "schema_hash": contract.short_hash,
        "model_version": exported.model_version,
        "weight_hash": exported.weight_hash,
        "mode": mode,
        "training_seed": seed,
        "dataset": _dataset_report(dataset),
        "teacher": {
            "candidate_count": len(teacher.candidates),
            "horizon_steps": teacher.horizon_steps,
            "cost": asdict(teacher.cost_config),
        },
        "model": {
            "architecture": [32, 32, len(contract.outputs)],
            "hidden_activation": "relu",
            "output_activation": "sigmoid",
            "format": "emlearn-net-float32-loadable",
            "parameter_count": training.metrics["parameter_count"],
            "export_weight_decimal_places": training.metrics["export_weight_decimals"],
        },
        "metrics": training.metrics,
        "python_c_verification": asdict(verification),
        "dependencies": {
            "numpy": _package_version("numpy"),
            "tensorflow": _package_version("tensorflow"),
            "keras": _package_version("keras"),
            "emlearn": _package_version("emlearn"),
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_pipeline(
    *,
    mode: str,
    seed: int = 1847,
    artifact_root: Path = DEFAULT_ARTIFACT_ROOT,
    generated_dir: Path = DEFAULT_GENERATED_DIR,
    golden_json: Path = DEFAULT_GOLDEN_JSON,
    golden_header: Path = DEFAULT_GOLDEN_HEADER,
) -> PipelineResult:
    if mode not in ("quick", "full"):
        raise ValueError("mode must be quick or full")
    contract = load_contract()
    dataset_config = (
        DatasetConfig.quick(seed) if mode == "quick" else DatasetConfig.full(seed)
    )
    training_config = (
        TrainingConfig.quick(seed) if mode == "quick" else TrainingConfig.full(seed)
    )
    teacher = RolloutTeacher(horizon_steps=2 if mode == "quick" else 4)
    dataset = generate_dataset(
        dataset_config, contract=contract, teacher=teacher
    )

    mode_artifacts = artifact_root / mode
    mode_artifacts.mkdir(parents=True, exist_ok=True)
    dataset_path = mode_artifacts / "dataset.npz"
    model_path = mode_artifacts / "environment_model.keras"
    dataset.save(dataset_path)
    training = train(dataset, training_config)
    training.model.save(model_path)
    exported = export_model(
        training.model,
        dataset,
        training.metrics,
        contract=contract,
        mode=mode,
        training_seed=seed,
        generated_dir=generated_dir,
        golden_json=golden_json,
        golden_header=golden_header,
    )
    verification = verify_export(
        environment_header=exported.environment_model_header,
        golden_json=exported.golden_json,
        golden_header=exported.golden_header,
    )
    report_path = mode_artifacts / "report.json"
    _write_report(
        report_path,
        mode=mode,
        seed=seed,
        dataset=dataset,
        training=training,
        exported=exported,
        verification=verification,
        teacher=teacher,
    )
    return PipelineResult(
        mode=mode,
        dataset=dataset,
        training=training,
        export=exported,
        verification=verification,
        report_path=report_path,
    )


def _golden_mismatches(
    temporary: dict[str, Any], committed: dict[str, Any]
) -> list[str]:
    if not isinstance(temporary, dict) or not isinstance(committed, dict):
        return ["golden-vector documents must be JSON objects"]
    mismatches: list[str] = []
    temporary_metadata = {
        key: value for key, value in temporary.items() if key != "vectors"
    }
    committed_metadata = {
        key: value for key, value in committed.items() if key != "vectors"
    }
    if temporary_metadata != committed_metadata:
        mismatches.append("golden-vector metadata or feature/output order differs")

    try:
        temporary_vectors = temporary["vectors"]
        committed_vectors = committed["vectors"]
        if (
            not isinstance(temporary_vectors, list)
            or not isinstance(committed_vectors, list)
            or not temporary_vectors
            or not committed_vectors
            or any(
                not isinstance(vector, dict)
                or set(vector) != {"features", "expected"}
                for vector in temporary_vectors + committed_vectors
            )
        ):
            raise ValueError("vectors must be non-empty feature/expected objects")
        temporary_features = np.asarray(
            [vector["features"] for vector in temporary_vectors], dtype=np.float64
        )
        committed_features = np.asarray(
            [vector["features"] for vector in committed_vectors], dtype=np.float64
        )
        temporary_expected = np.asarray(
            [vector["expected"] for vector in temporary_vectors], dtype=np.float64
        )
        committed_expected = np.asarray(
            [vector["expected"] for vector in committed_vectors], dtype=np.float64
        )
    except (KeyError, TypeError, ValueError) as error:
        return mismatches + [f"invalid golden-vector structure: {error}"]

    if not all(
        np.all(np.isfinite(values))
        for values in (
            temporary_features,
            committed_features,
            temporary_expected,
            committed_expected,
        )
    ):
        mismatches.append("golden vectors must contain only finite numbers")

    if temporary_features.shape != committed_features.shape:
        mismatches.append("golden-vector feature shapes differ")
    elif not np.allclose(
        temporary_features,
        committed_features,
        rtol=0.0,
        atol=GOLDEN_FEATURE_ATOL,
    ):
        mismatches.append("golden-vector features differ beyond tolerance")

    if temporary_expected.shape != committed_expected.shape:
        mismatches.append("golden-vector prediction shapes differ")
    elif not np.allclose(
        temporary_expected,
        committed_expected,
        rtol=0.0,
        atol=GOLDEN_EXPECTED_ATOL,
    ):
        mismatches.append("golden-vector predictions differ beyond tolerance")
    return mismatches


def _compare_generated(temporary: ExportResult) -> None:
    byte_exact_pairs = (
        (temporary.environment_model_header, DEFAULT_GENERATED_DIR / "EnvironmentModel.h"),
        (temporary.model_manifest_header, DEFAULT_GENERATED_DIR / "ModelManifest.h"),
    )
    mismatches: list[str] = []
    for actual, committed in byte_exact_pairs:
        if not committed.exists():
            mismatches.append(f"missing committed file: {committed}")
        elif actual.read_bytes() != committed.read_bytes():
            mismatches.append(f"non-deterministic or stale generated file: {committed}")

    try:
        temporary_golden = json.loads(temporary.golden_json.read_text(encoding="utf-8"))
        committed_golden = json.loads(DEFAULT_GOLDEN_JSON.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as error:
        mismatches.append(f"cannot read golden vectors: {error}")
    else:
        mismatches.extend(_golden_mismatches(temporary_golden, committed_golden))
        for document, header, label in (
            (temporary_golden, temporary.golden_header, "temporary"),
            (committed_golden, DEFAULT_GOLDEN_HEADER, "committed"),
        ):
            try:
                header_text = header.read_text(encoding="utf-8")
                expected_header = render_golden_header(document)
            except (FileNotFoundError, KeyError, TypeError, ValueError) as error:
                mismatches.append(f"cannot validate {label} golden header: {error}")
            else:
                if header_text != expected_header:
                    mismatches.append(
                        f"{label} golden header does not match its JSON fixture"
                    )
    if mismatches:
        raise RuntimeError("\n".join(mismatches))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--quick", action="store_true")
    mode.add_argument("--full", action="store_true")
    parser.add_argument("--seed", type=int, default=1847)
    parser.add_argument(
        "--check-generated",
        action="store_true",
        help="retrain in a temporary directory and compare with committed generated files",
    )
    parser.add_argument("--artifact-root", type=Path, default=DEFAULT_ARTIFACT_ROOT)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    mode = "quick" if args.quick else "full"
    if args.check_generated:
        with tempfile.TemporaryDirectory(prefix="growbox-determinism-") as directory:
            root = Path(directory)
            result = run_pipeline(
                mode=mode,
                seed=args.seed,
                artifact_root=root / "artifacts",
                generated_dir=root / "generated",
                golden_json=root / "fixtures" / "golden_vectors.json",
                golden_header=root / "fixtures" / "ModelGoldenVectors.h",
            )
            _compare_generated(result.export)
            print(
                "generated model and manifest are byte-deterministic; "
                "golden vectors are numerically reproducible"
            )
            return 0

    result = run_pipeline(
        mode=mode,
        seed=args.seed,
        artifact_root=args.artifact_root,
    )
    test_metrics = result.training.metrics["test"]
    print(
        f"{mode} pipeline complete: rows={len(result.dataset.features)}, "
        f"model={result.export.model_version}, test_mae={test_metrics['mae']:.6f}, "
        f"python_c_max_abs={result.verification.max_abs_error:.9g}"
    )
    print(f"report: {result.report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
