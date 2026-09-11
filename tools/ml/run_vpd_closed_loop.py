from __future__ import annotations

import json
import subprocess
import threading
import time
from pathlib import Path

from tools.ml.climate_benchmark import (
    ClimateBenchmarkConfig,
    benchmark_summary,
    run_closed_loop_benchmark,
)
from tools.ml.climate_model_artifact import load_portable_model
from tools.ml.climate_scenarios import REQUIRED_SCENARIO_FAMILIES
from tools.ml.dataset import Dataset

SEED = 91_273
WORKERS = 6
WEIGHTS = Path("reports/ml/climate_v6_model_seed1847_vpd.npz")
MODEL_METADATA = Path("reports/ml/climate_v6_model_seed1847_vpd.json")
TRAINING_DATASET = Path("build/climate_v6_full_seed1847_vpd.npz")
TRAINING_REPORT = Path("reports/ml/climate_v6_weighted_training_seed1847_vpd.json")
BUILD_REPORT = Path("build/climate_v6_closed_loop_seed91273_vpd.json")
REPORT_PATH = Path("reports/ml/climate_v6_closed_loop_seed91273_vpd.json")


def _heartbeat(stop: threading.Event) -> None:
    started = time.monotonic()
    while not stop.wait(60.0):
        print(f"STAGE9D_HEARTBEAT elapsed_s={int(time.monotonic() - started)}", flush=True)


def main() -> None:
    if len(REQUIRED_SCENARIO_FAMILIES) != 15:
        raise AssertionError("Stage 9D expects exactly 15 scenario families")
    if not TRAINING_DATASET.exists():
        raise FileNotFoundError("audited Stage 9B dataset cache is missing")
    training_payload = json.loads(TRAINING_REPORT.read_text(encoding="utf-8"))
    if training_payload["dataset"]["rows"] != 7200:
        raise ValueError("Stage 9C training report does not describe 7200 rows")

    model = load_portable_model(WEIGHTS, MODEL_METADATA)
    training_dataset = Dataset.load(TRAINING_DATASET)
    training_ids = {str(value) for value in training_dataset.scenario_ids}

    config = ClimateBenchmarkConfig.full(seed=SEED, workers=WORKERS)
    print(
        f"STAGE9D_START seed={SEED} workers={WORKERS} families={len(REQUIRED_SCENARIO_FAMILIES)} "
        f"scenarios_per_family={config.scenarios_per_family} steps={config.steps_per_scenario}",
        flush=True,
    )
    stop = threading.Event()
    thread = threading.Thread(target=_heartbeat, args=(stop,), daemon=True)
    thread.start()
    try:
        report = run_closed_loop_benchmark(model, config=config)
    finally:
        stop.set()
        thread.join(timeout=2.0)

    benchmark_ids = {item.scenario_id for item in report.episodes}
    overlap = sorted(training_ids & benchmark_ids)
    if overlap:
        raise ValueError("training/closed-loop scenario leakage: " + ", ".join(overlap[:5]))
    if len(report.families) != 15:
        raise AssertionError(f"unexpected benchmark family count: {len(report.families)}")
    if len(report.episodes) != 15 * 2 * 3:
        raise AssertionError(f"unexpected benchmark episode count: {len(report.episodes)}")
    for policy in ("rule", "teacher", "ml"):
        metrics = report.aggregate[policy]
        if metrics.episodes != 30 or metrics.steps != 1800:
            raise AssertionError(f"unexpected aggregate coverage for {policy}: {metrics}")

    payload = report.as_dict()
    payload["schema_version"] = 6
    payload["git_commit"] = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    payload["model"] = {
        "weights": str(WEIGHTS),
        "metadata": str(MODEL_METADATA),
        "candidate": model.metadata.candidate_name,
        "training_seed": model.metadata.training_seed,
        "contract_hash": model.metadata.contract_hash,
    }
    payload["leakage_check"] = {
        "training_unique_scenarios": len(training_ids),
        "benchmark_unique_scenarios": len(benchmark_ids),
        "overlap_count": len(overlap),
    }
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    BUILD_REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    BUILD_REPORT.write_text(text, encoding="utf-8")
    REPORT_PATH.write_text(text, encoding="utf-8")

    for line in benchmark_summary(report):
        print(line, flush=True)
    print(f"STAGE9D_SCENARIO_OVERLAP={len(overlap)}", flush=True)
    print(f"STAGE9D_REPORT={REPORT_PATH}", flush=True)
    print("STAGE9D_BENCHMARK_COMPLETE=PASS", flush=True)


if __name__ == "__main__":
    main()
