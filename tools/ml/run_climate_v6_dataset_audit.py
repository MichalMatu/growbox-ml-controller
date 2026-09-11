from __future__ import annotations

import json
import os
import threading
import time
from collections import Counter
from pathlib import Path

import numpy as np

from tools.ml.climate_dataset import (
    ClimateDatasetConfig,
    assert_climate_dataset_ready,
    audit_climate_dataset,
)
from tools.ml.climate_dataset_parallel import generate_climate_dataset_parallel
from tools.ml.climate_scenarios import REQUIRED_SCENARIO_FAMILIES
from tools.ml.climate_simulator import CLIMATE_OUTPUT_NAMES

SEED = 1847
DATASET_CACHE = Path("build/climate_v6_full_seed1847_vpd.npz")
METADATA_CACHE = Path("build/climate_v6_full_seed1847_vpd_metadata.npz")
BUILD_REPORT = Path("build/climate_v6_dataset_audit_seed1847_vpd.json")
REPORT_PATH = Path("reports/ml/climate_v6_dataset_audit_seed1847_vpd.json")


def _worker_count() -> int:
    value = int(os.environ.get("CLIMATE_DATASET_WORKERS", "6"))
    if value <= 0:
        raise ValueError("CLIMATE_DATASET_WORKERS must be positive")
    return value


def _heartbeat(stop: threading.Event) -> None:
    started = time.monotonic()
    while not stop.wait(60.0):
        print(f"STAGE9B_HEARTBEAT elapsed_s={int(time.monotonic() - started)}", flush=True)


def _split_mode_counts(modes: np.ndarray, splits: np.ndarray) -> dict[str, dict[str, int]]:
    result: dict[str, dict[str, int]] = {}
    for split in ("train", "validation", "test"):
        mask = splits == split
        counts = Counter(str(value) for value in modes[mask])
        result[split] = {mode: int(counts.get(mode, 0)) for mode in ("RH", "VPD")}
    return result


def _split_family_counts(families: np.ndarray, splits: np.ndarray) -> dict[str, dict[str, int]]:
    result: dict[str, dict[str, int]] = {}
    for split in ("train", "validation", "test"):
        mask = splits == split
        counts = Counter(str(value) for value in families[mask])
        result[split] = {
            family: int(counts.get(family, 0)) for family in REQUIRED_SCENARIO_FAMILIES
        }
    return result


def _label_coverage(
    labels: np.ndarray, splits: np.ndarray
) -> dict[str, dict[str, dict[str, float | int]]]:
    result: dict[str, dict[str, dict[str, float | int]]] = {}
    for split in ("train", "validation", "test"):
        mask = splits == split
        split_labels = labels[mask]
        per_output: dict[str, dict[str, float | int]] = {}
        for index, name in enumerate(CLIMATE_OUTPUT_NAMES):
            values = split_labels[:, index]
            active = values > 0.05
            strong = values > 0.30
            active_values = values[active]
            per_output[name] = {
                "rows": int(values.size),
                "active_count": int(np.sum(active)),
                "active_fraction": float(np.mean(active)),
                "strong_count": int(np.sum(strong)),
                "strong_fraction": float(np.mean(strong)),
                "mean": float(np.mean(values)),
                "active_mean": float(np.mean(active_values)) if active_values.size else 0.0,
                "active_p50": float(np.quantile(active_values, 0.50))
                if active_values.size
                else 0.0,
                "active_p90": float(np.quantile(active_values, 0.90))
                if active_values.size
                else 0.0,
                "max": float(np.max(values)) if values.size else 0.0,
            }
        result[split] = per_output
    return result


def _vpd_output_coverage(
    labels: np.ndarray, modes: np.ndarray
) -> dict[str, dict[str, float | int]]:
    mask = modes == "VPD"
    vpd_labels = labels[mask]
    result: dict[str, dict[str, float | int]] = {}
    for index, name in enumerate(CLIMATE_OUTPUT_NAMES):
        values = vpd_labels[:, index]
        result[name] = {
            "rows": int(values.size),
            "active_count": int(np.sum(values > 0.05)),
            "active_fraction": float(np.mean(values > 0.05)) if values.size else 0.0,
            "strong_count": int(np.sum(values > 0.30)),
            "max": float(np.max(values)) if values.size else 0.0,
        }
    return result


def main() -> None:
    workers = _worker_count()
    config = ClimateDatasetConfig.full(seed=SEED)
    expected_rows = (
        len(REQUIRED_SCENARIO_FAMILIES) * config.scenarios_per_family * config.steps_per_scenario
    )
    print(
        f"STAGE9B_START workers={workers} families={len(REQUIRED_SCENARIO_FAMILIES)} "
        f"scenarios_per_family={config.scenarios_per_family} steps={config.steps_per_scenario} "
        f"expected_rows={expected_rows}",
        flush=True,
    )

    stop = threading.Event()
    thread = threading.Thread(target=_heartbeat, args=(stop,), daemon=True)
    thread.start()
    try:
        bundle = generate_climate_dataset_parallel(config, workers=workers)
    finally:
        stop.set()
        thread.join(timeout=2.0)

    audit = audit_climate_dataset(bundle)
    assert_climate_dataset_ready(
        audit,
        require_family_coverage_in_each_split=True,
        require_humidity_mode_coverage_in_each_split=True,
        bundle=bundle,
    )

    dataset = bundle.dataset
    if dataset.features.shape != (expected_rows, 44):
        raise AssertionError(f"unexpected feature shape: {dataset.features.shape}")
    if dataset.labels.shape != (expected_rows, 6):
        raise AssertionError(f"unexpected label shape: {dataset.labels.shape}")
    if len(REQUIRED_SCENARIO_FAMILIES) != 15:
        raise AssertionError("Stage 9B expects exactly 15 required scenario families")

    split_mode_counts = _split_mode_counts(bundle.humidity_modes, dataset.splits)
    split_family_counts = _split_family_counts(bundle.families, dataset.splits)
    label_coverage = _label_coverage(dataset.labels, dataset.splits)
    vpd_output_coverage = _vpd_output_coverage(dataset.labels, bundle.humidity_modes)

    gate_errors: list[str] = []
    for split in ("train", "validation", "test"):
        for name in CLIMATE_OUTPUT_NAMES:
            stats = label_coverage[split][name]
            if int(stats["active_count"]) == 0:
                gate_errors.append(f"{name} has no active labels in {split}")
            if int(stats["strong_count"]) == 0:
                gate_errors.append(f"{name} has no >0.30 labels in {split}")
    for name in ("humidifier", "dehumidifier"):
        if int(vpd_output_coverage[name]["active_count"]) == 0:
            gate_errors.append(f"{name} has no active labels in VPD rows")
        if int(vpd_output_coverage[name]["strong_count"]) == 0:
            gate_errors.append(f"{name} has no >0.30 labels in VPD rows")
    if gate_errors:
        raise ValueError("Stage 9B label coverage gate failed: " + " | ".join(gate_errors))

    DATASET_CACHE.parent.mkdir(parents=True, exist_ok=True)
    dataset.save(DATASET_CACHE)
    np.savez_compressed(
        METADATA_CACHE,
        families=bundle.families,
        profiles=bundle.profiles,
        humidity_modes=bundle.humidity_modes,
        safe_fallbacks=bundle.safe_fallbacks,
    )

    report = {
        "schema_version": 6,
        "seed": SEED,
        "workers": workers,
        "config": {
            "families": len(REQUIRED_SCENARIO_FAMILIES),
            "scenarios_per_family": config.scenarios_per_family,
            "steps_per_scenario": config.steps_per_scenario,
            "rows": expected_rows,
        },
        "audit": {
            "ready_for_training": audit.ready_for_training,
            "row_count": audit.row_count,
            "feature_count": audit.feature_count,
            "output_count": audit.output_count,
            "family_counts": audit.family_counts,
            "split_counts": audit.split_counts,
            "humidity_mode_counts": audit.humidity_mode_counts,
            "active_fraction": audit.active_fraction,
            "mean_level": audit.mean_level,
            "safe_fallback_fraction": audit.safe_fallback_fraction,
            "all_zero_fraction": audit.all_zero_fraction,
            "conflicting_temperature_rows": audit.conflicting_temperature_rows,
            "conflicting_humidity_rows": audit.conflicting_humidity_rows,
            "errors": list(audit.errors),
            "warnings": list(audit.warnings),
        },
        "split_humidity_mode_counts": split_mode_counts,
        "split_family_counts": split_family_counts,
        "label_coverage": label_coverage,
        "vpd_output_coverage": vpd_output_coverage,
        "cache": {
            "dataset": str(DATASET_CACHE),
            "metadata": str(METADATA_CACHE),
        },
    }
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    BUILD_REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    BUILD_REPORT.write_text(text, encoding="utf-8")
    REPORT_PATH.write_text(text, encoding="utf-8")

    for line in audit.summary_lines():
        print(line, flush=True)
    print(f"split_humidity_modes={split_mode_counts}", flush=True)
    for split in ("train", "validation", "test"):
        strong = {
            name: label_coverage[split][name]["strong_count"] for name in CLIMATE_OUTPUT_NAMES
        }
        print(f"strong_labels_{split}={strong}", flush=True)
    print(f"vpd_output_coverage={vpd_output_coverage}", flush=True)
    print(f"STAGE9B_REPORT={REPORT_PATH}", flush=True)
    print("STAGE9B_FULL_DATASET_GATE=PASS", flush=True)


if __name__ == "__main__":
    main()
