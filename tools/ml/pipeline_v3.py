"""Run the deterministic v3 dataset, training, export, and verification pipeline."""

from __future__ import annotations

import argparse
import json
import tempfile
from dataclasses import asdict
from pathlib import Path

from .contract import V3_CONTRACT_PATH, load_contract
from .export_model import (
    DEFAULT_GENERATED_DIR,
    DEFAULT_GOLDEN_HEADER,
    DEFAULT_GOLDEN_JSON,
)
from .generate_dataset import DatasetConfig
from .generate_dataset_v2 import generate_dataset_v2
from .pipeline import DEFAULT_ARTIFACT_ROOT, PipelineResult, _compare_generated, _dataset_report
from .teacher_v2 import RolloutTeacherV2
from .train_model import TrainingConfig, train
from .verify_export import verify_export


def run_pipeline_v3(
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
    contract = load_contract(V3_CONTRACT_PATH)
    dataset_config = DatasetConfig.quick(seed) if mode == "quick" else DatasetConfig.full(seed)
    training_config = TrainingConfig.quick(seed) if mode == "quick" else TrainingConfig.full(seed)
    teacher = RolloutTeacherV2(horizon_steps=2 if mode == "quick" else 4)
    dataset = generate_dataset_v2(dataset_config, contract=contract, teacher=teacher)

    mode_artifacts = artifact_root / f"v3-{mode}"
    mode_artifacts.mkdir(parents=True, exist_ok=True)
    dataset_path = mode_artifacts / "dataset.npz"
    model_path = mode_artifacts / "environment_model.keras"
    dataset.save(dataset_path)
    training = train(dataset, training_config)
    training.model.save(model_path)

    from .export_model import export_model

    exported = export_model(
        training.model,
        dataset,
        training.metrics,
        contract=contract,
        mode=f"v3-{mode}",
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
    report_document = {
        "schema_version": contract.schema_version,
        "schema_hash": contract.short_hash,
        "model_version": exported.model_version,
        "weight_hash": exported.weight_hash,
        "mode": f"v3-{mode}",
        "training_seed": seed,
        "dataset": _dataset_report(dataset),
        "teacher": {
            "horizon_steps": teacher.horizon_steps,
            "cost": asdict(teacher.cost_config),
        },
        "metrics": training.metrics,
        "python_c_verification": asdict(verification),
    }
    report_path.write_text(
        json.dumps(report_document, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return PipelineResult(
        mode=f"v3-{mode}",
        dataset=dataset,
        training=training,
        export=exported,
        verification=verification,
        report_path=report_path,
    )


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
        with tempfile.TemporaryDirectory(prefix="growbox-v3-determinism-") as directory:
            root = Path(directory)
            result = run_pipeline_v3(
                mode=mode,
                seed=args.seed,
                artifact_root=root / "artifacts",
                generated_dir=root / "generated",
                golden_json=root / "fixtures" / "golden_vectors.json",
                golden_header=root / "fixtures" / "ModelGoldenVectors.h",
            )
            _compare_generated(result.export)
            print("v3 generated model and golden vectors are reproducible")
            return 0

    result = run_pipeline_v3(mode=mode, seed=args.seed, artifact_root=args.artifact_root)
    test_metrics = result.training.metrics["test"]
    print(
        f"v3 {mode} pipeline complete: rows={len(result.dataset.features)}, "
        f"model={result.export.model_version}, test_mae={test_metrics['mae']:.6f}, "
        f"python_c_max_abs={result.verification.max_abs_error:.9g}"
    )
    print(f"report: {result.report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
