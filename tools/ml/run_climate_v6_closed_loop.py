"""Run the full held-out climate-v6 closed-loop benchmark."""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path

from tools.ml.climate_benchmark import (
    ClimateBenchmarkConfig,
    benchmark_summary,
    run_closed_loop_benchmark,
)
from tools.ml.climate_model_artifact import load_portable_model

ROOT = Path(__file__).resolve().parents[2]
WEIGHTS = ROOT / "reports" / "ml" / "climate_v6_model_seed1847.npz"
METADATA = ROOT / "reports" / "ml" / "climate_v6_model_seed1847.json"
OUTPUT = ROOT / "build" / "climate_v6_closed_loop_seed91273.json"


def _heartbeat(stop: threading.Event) -> None:
    started = time.monotonic()
    while not stop.wait(60.0):
        elapsed = int(time.monotonic() - started)
        print(f"CLOSED_LOOP_HEARTBEAT elapsed_s={elapsed}", flush=True)


def main() -> None:
    workers = int(os.environ.get("CLIMATE_BENCHMARK_WORKERS", "6"))
    if workers <= 0:
        raise ValueError("CLIMATE_BENCHMARK_WORKERS must be positive")
    print(f"CLIMATE_V6_CLOSED_LOOP_START workers={workers}", flush=True)
    model = load_portable_model(WEIGHTS, METADATA)
    config = ClimateBenchmarkConfig.full(seed=91_273, workers=workers)
    stop = threading.Event()
    heartbeat = threading.Thread(target=_heartbeat, args=(stop,), daemon=True)
    heartbeat.start()
    try:
        report = run_closed_loop_benchmark(model, config=config)
    finally:
        stop.set()
        heartbeat.join(timeout=2.0)

    payload = report.as_dict()
    payload["model"] = {
        "candidate_name": model.metadata.candidate_name,
        "training_seed": model.metadata.training_seed,
        "contract_hash": model.metadata.contract_hash,
        "parameter_count": model.parameter_count,
        "weights_file": WEIGHTS.name,
        "metadata_file": METADATA.name,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    for line in benchmark_summary(report):
        print(line, flush=True)
    for family, policies in sorted(report.families.items()):
        rule = policies["rule"]
        teacher = policies["teacher"]
        ml = policies["ml"]
        print(
            f"family={family} rule_tracking={rule.tracking_cost:.6f} "
            f"teacher_tracking={teacher.tracking_cost:.6f} ml_tracking={ml.tracking_cost:.6f} "
            f"rule_outside={rule.outside_deadband_fraction:.4f} "
            f"ml_outside={ml.outside_deadband_fraction:.4f}",
            flush=True,
        )
    print(f"CLOSED_LOOP_REPORT={OUTPUT.relative_to(ROOT)}", flush=True)
    print("CLIMATE_V6_CLOSED_LOOP=COMPLETE", flush=True)


if __name__ == "__main__":
    main()
