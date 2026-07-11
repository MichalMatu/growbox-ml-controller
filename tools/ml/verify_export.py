"""Compile the exported emlearn model and compare it with Python goldens."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

import numpy as np

from .contract import PROJECT_ROOT
from .export_model import (
    DEFAULT_GENERATED_DIR,
    DEFAULT_GOLDEN_HEADER,
    DEFAULT_GOLDEN_JSON,
)


@dataclass(frozen=True)
class VerificationResult:
    vector_count: int
    max_abs_error: float
    mean_abs_error: float
    tolerance: float


def _compiler() -> str:
    for name in ("c++", "clang++", "g++"):
        compiler = shutil.which(name)
        if compiler:
            return compiler
    raise RuntimeError("a C++17 compiler is required to verify the emlearn export")


def _emlearn_include() -> Path:
    import emlearn

    return Path(emlearn.common.get_include_dir()).resolve()


def compiled_predictions(
    *,
    environment_header: Path,
    golden_header: Path,
) -> np.ndarray:
    source = r'''#include <cstdio>
#include "EnvironmentModel.h"
#include "ModelGoldenVectors.h"

int main() {
    for (std::size_t row = 0; row < model_golden_vectors::kVectorCount; ++row) {
        float outputs[model_golden_vectors::kOutputCount]{};
        if (!generated_model::infer(model_golden_vectors::kFeatures[row].data(), outputs)) {
            return 2;
        }
        for (std::size_t column = 0; column < model_golden_vectors::kOutputCount; ++column) {
            std::printf(column == 0 ? "%.9g" : ",%.9g", static_cast<double>(outputs[column]));
        }
        std::printf("\n");
    }
    return 0;
}
'''
    with tempfile.TemporaryDirectory(prefix="growbox-verify-") as directory:
        temporary = Path(directory)
        source_path = temporary / "verify.cpp"
        binary_path = temporary / "verify"
        source_path.write_text(source, encoding="utf-8")
        command = [
            _compiler(),
            "-std=c++17",
            "-O2",
            "-Wall",
            "-Wextra",
            "-Wno-unused-function",
            "-I",
            str(environment_header.resolve().parent),
            "-I",
            str(golden_header.resolve().parent),
            "-I",
            str(_emlearn_include()),
            str(source_path),
            "-o",
            str(binary_path),
        ]
        compilation = subprocess.run(
            command, text=True, capture_output=True, check=False
        )
        if compilation.returncode != 0:
            raise RuntimeError(
                "exported model did not compile:\n"
                + compilation.stdout
                + compilation.stderr
            )
        execution = subprocess.run(
            [str(binary_path)], text=True, capture_output=True, check=False
        )
        if execution.returncode != 0:
            raise RuntimeError(
                f"compiled model inference failed with {execution.returncode}:\n"
                + execution.stderr
            )
    rows = [
        [float(token) for token in line.split(",")]
        for line in execution.stdout.splitlines()
        if line.strip()
    ]
    return np.asarray(rows, dtype=np.float32)


def verify_export(
    *,
    environment_header: Path = DEFAULT_GENERATED_DIR / "EnvironmentModel.h",
    golden_json: Path = DEFAULT_GOLDEN_JSON,
    golden_header: Path = DEFAULT_GOLDEN_HEADER,
    tolerance: float = 2.0e-5,
) -> VerificationResult:
    golden = json.loads(golden_json.read_text(encoding="utf-8"))
    expected = np.asarray(
        [vector["expected"] for vector in golden["vectors"]], dtype=np.float32
    )
    actual = compiled_predictions(
        environment_header=environment_header, golden_header=golden_header
    )
    if actual.shape != expected.shape:
        raise AssertionError(
            f"compiled shape {actual.shape} does not match Python shape {expected.shape}"
        )
    absolute = np.abs(actual.astype(np.float64) - expected.astype(np.float64))
    maximum = float(np.max(absolute))
    result = VerificationResult(
        vector_count=len(expected),
        max_abs_error=maximum,
        mean_abs_error=float(np.mean(absolute)),
        tolerance=float(tolerance),
    )
    if maximum > tolerance:
        raise AssertionError(
            f"Python/C max absolute prediction error {maximum:.9g} exceeds {tolerance:.9g}"
        )
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--environment-header",
        type=Path,
        default=DEFAULT_GENERATED_DIR / "EnvironmentModel.h",
    )
    parser.add_argument("--golden-json", type=Path, default=DEFAULT_GOLDEN_JSON)
    parser.add_argument("--golden-header", type=Path, default=DEFAULT_GOLDEN_HEADER)
    parser.add_argument("--tolerance", type=float, default=2.0e-5)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    result = verify_export(
        environment_header=args.environment_header,
        golden_json=args.golden_json,
        golden_header=args.golden_header,
        tolerance=args.tolerance,
    )
    print(
        f"verified {result.vector_count} Python/C vectors; "
        f"max_abs_error={result.max_abs_error:.9g}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
