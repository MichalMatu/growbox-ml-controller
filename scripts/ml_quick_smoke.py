#!/usr/bin/env python3
"""Run the quick ML pipeline without touching or comparing committed full-model artifacts."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.ml.pipeline import run_pipeline


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="growbox-quick-smoke-") as directory:
        root = Path(directory)
        result = run_pipeline(
            mode="quick",
            seed=1847,
            artifact_root=root / "artifacts",
            generated_dir=root / "generated",
            golden_json=root / "fixtures" / "golden_vectors.json",
            golden_header=root / "fixtures" / "ModelGoldenVectors.h",
        )
        test_metrics = result.training.metrics["test"]
        print(
            "quick ML smoke passed: "
            f"rows={len(result.dataset.features)}, "
            f"model={result.export.model_version}, "
            f"test_mae={test_metrics['mae']:.6f}, "
            f"python_c_max_abs={result.verification.max_abs_error:.9g}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
