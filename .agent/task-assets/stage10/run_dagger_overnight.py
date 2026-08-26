from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import threading
import time
from dataclasses import asdict
from pathlib import Path

import numpy as np

from tools.ml.climate_benchmark import ClimateBenchmarkConfig, run_closed_loop_benchmark
from tools.ml.climate_dagger import (
    DaggerCollectionConfig,
    append_train_only,
    collect_dagger_rows,
    frozen_split_fingerprint,
)
from tools.ml.climate_input import CLIMATE_V6_CONTRACT_PATH
from tools.ml.climate_model_artifact import (
    ClimateModelMetadata,
    from_keras_model,
    load_portable_model,
    save_portable_model,
)
from tools.ml.climate_training_weighted import (
    DEFAULT_WEIGHTED_CANDIDATES,
    WeightedTrainingConfig,
    control_prediction_metrics,
    train_weighted_candidate,
)
from tools.ml.contract import load_contract
from tools.ml.dataset import Dataset

BASE_DATASET = Path("build/climate_v6_full_seed1847_vpd.npz")
INITIAL_WEIGHTS = Path("reports/ml/climate_v6_model_seed1847_vpd.npz")
INITIAL_METADATA = Path("reports/ml/climate_v6_model_seed1847_vpd.json")
WORK_DIR = Path("build/dagger_stage10")
STATE_PATH = WORK_DIR / "state.json"
CURRENT_DATASET = WORK_DIR / "dataset_current.npz"
CURRENT_WEIGHTS = WORK_DIR / "model_current.npz"
CURRENT_METADATA = WORK_DIR / "model_current.json"
BEST_WEIGHTS = WORK_DIR / "model_best.npz"
BEST_METADATA = WORK_DIR / "model_best.json"
REPORT_PATH = Path("reports/ml/climate_v6_dagger_overnight.json")
FINAL_WEIGHTS = Path("reports/ml/climate_v6_model_dagger_candidate.npz")
FINAL_METADATA = Path("reports/ml/climate_v6_model_dagger_candidate.json")

BASE_SEED = 1847
DAGGER_SEED_BASE = 610_000
DEV_SEED = 314_159
FINAL_SEED = 271_828
SCENARIOS_PER_FAMILY = 12
STEPS_PER_SCENARIO = 100
WORKERS = 6
TRAIN_EPOCHS = 36


def _heartbeat(label: str, stop: threading.Event) -> None:
    started = time.monotonic()
    while not stop.wait(60.0):
        print(f"STAGE10_HEARTBEAT phase={label} elapsed_s={int(time.monotonic() - started)}", flush=True)


def _run_with_heartbeat(label: str, fn):
    stop = threading.Event()
    thread = threading.Thread(target=_heartbeat, args=(label, stop), daemon=True)
    thread.start()
    try:
        return fn()
    finally:
        stop.set()
        thread.join(timeout=2.0)


def _load_state() -> dict[str, object]:
    return json.loads(STATE_PATH.read_text(encoding="utf-8"))


def _save_state(state: dict[str, object]) -> None:
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _copy_model(src_weights: Path, src_metadata: Path, dst_weights: Path, dst_metadata: Path) -> None:
    dst_weights.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src_weights, dst_weights)
    shutil.copy2(src_metadata, dst_metadata)


def _dev_score(report, validation_control_mae: float) -> tuple[float, ...]:
    rule = report.aggregate["rule"]
    ml = report.aggregate["ml"]
    hard_limit_penalty = 1.0 if ml.hard_limit_violation_fraction > 0.0 else 0.0
    safety_excess = max(0.0, ml.safety_intervention_fraction - rule.safety_intervention_fraction)
    return (
        hard_limit_penalty,
        safety_excess,
        ml.tracking_cost,
        ml.outside_deadband_fraction,
        validation_control_mae,
    )


def _score_to_list(score: tuple[float, ...]) -> list[float]:
    return [float(value) for value in score]


def _training_spec():
    return next(spec for spec in DEFAULT_WEIGHTED_CANDIDATES if spec.name == "adam_huber_baseline")


def _portable_from_result(result, *, iteration: int):
    contract = load_contract(CLIMATE_V6_CONTRACT_PATH)
    source_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    metadata = ClimateModelMetadata(
        schema_version=contract.schema_version,
        contract_hash=contract.hash_hex,
        feature_names=contract.feature_names,
        output_names=contract.outputs,
        training_seed=BASE_SEED,
        candidate_name=f"dagger-iter-{iteration}-adam_huber_baseline",
        source_commit=source_commit,
    )
    return from_keras_model(result.model, metadata)


def init() -> None:
    if not BASE_DATASET.exists() or not INITIAL_WEIGHTS.exists() or not INITIAL_METADATA.exists():
        raise FileNotFoundError("Stage 10 requires Stage 9B dataset and Stage 9C portable model")
    base = Dataset.load(BASE_DATASET)
    if base.features.shape != (7200, 38) or base.labels.shape != (7200, 6):
        raise ValueError("unexpected Stage 9B base dataset shape")
    split_counts = {split: int(np.sum(base.splits == split)) for split in ("train", "validation", "test")}
    if split_counts != {"train": 4800, "validation": 1200, "test": 1200}:
        raise ValueError(f"unexpected Stage 9B split counts: {split_counts}")

    WORK_DIR.mkdir(parents=True, exist_ok=True)
    base.save(CURRENT_DATASET)
    _copy_model(INITIAL_WEIGHTS, INITIAL_METADATA, CURRENT_WEIGHTS, CURRENT_METADATA)
    _copy_model(INITIAL_WEIGHTS, INITIAL_METADATA, BEST_WEIGHTS, BEST_METADATA)

    validation_fp = frozen_split_fingerprint(base, "validation")
    test_fp = frozen_split_fingerprint(base, "test")
    model = load_portable_model(CURRENT_WEIGHTS, CURRENT_METADATA)
    dev = _run_with_heartbeat(
        "initial-dev",
        lambda: run_closed_loop_benchmark(
            model,
            config=ClimateBenchmarkConfig(
                seed=DEV_SEED,
                scenarios_per_family=1,
                steps_per_scenario=40,
                workers=WORKERS,
            ),
        ),
    )
    initial_score = _dev_score(dev, validation_control_mae=1.0)
    state: dict[str, object] = {
        "schema_version": 1,
        "base_rows": 7200,
        "validation_fingerprint": validation_fp,
        "test_fingerprint": test_fp,
        "completed_iterations": 0,
        "best_iteration": 0,
        "best_score": _score_to_list(initial_score),
        "initial_dev": dev.as_dict(),
        "iterations": [],
        "config": {
            "dagger_seed_base": DAGGER_SEED_BASE,
            "dev_seed": DEV_SEED,
            "final_seed": FINAL_SEED,
            "scenarios_per_family": SCENARIOS_PER_FAMILY,
            "steps_per_scenario": STEPS_PER_SCENARIO,
            "workers": WORKERS,
            "train_epochs": TRAIN_EPOCHS,
        },
    }
    _save_state(state)
    print(f"STAGE10_INIT rows={len(base.features)} dev_tracking={dev.aggregate['ml'].tracking_cost:.6f}", flush=True)


def iteration(iteration_index: int) -> None:
    if iteration_index <= 0:
        raise ValueError("iteration index must be positive")
    state = _load_state()
    expected = int(state["completed_iterations"]) + 1
    if iteration_index != expected:
        raise ValueError(f"expected DAgger iteration {expected}, got {iteration_index}")

    dataset = Dataset.load(CURRENT_DATASET)
    if frozen_split_fingerprint(dataset, "validation") != state["validation_fingerprint"]:
        raise AssertionError("validation split changed before DAgger iteration")
    if frozen_split_fingerprint(dataset, "test") != state["test_fingerprint"]:
        raise AssertionError("test split changed before DAgger iteration")

    model = load_portable_model(CURRENT_WEIGHTS, CURRENT_METADATA)
    contract = load_contract(CLIMATE_V6_CONTRACT_PATH)
    collection_config = DaggerCollectionConfig(
        seed=DAGGER_SEED_BASE + iteration_index * 10_003,
        scenarios_per_family=SCENARIOS_PER_FAMILY,
        steps_per_scenario=STEPS_PER_SCENARIO,
        workers=WORKERS,
    )
    dagger = _run_with_heartbeat(
        f"dagger-collect-{iteration_index}",
        lambda: collect_dagger_rows(model, config=collection_config, contract=contract),
    )
    before_rows = len(dataset.features)
    dataset = append_train_only(dataset, dagger.dataset)
    added_rows = len(dataset.features) - before_rows
    expected_added = 15 * SCENARIOS_PER_FAMILY * STEPS_PER_SCENARIO
    if added_rows != expected_added:
        raise AssertionError(f"unexpected DAgger row count: {added_rows} != {expected_added}")
    if frozen_split_fingerprint(dataset, "validation") != state["validation_fingerprint"]:
        raise AssertionError("DAgger modified frozen validation split")
    if frozen_split_fingerprint(dataset, "test") != state["test_fingerprint"]:
        raise AssertionError("DAgger modified frozen test split")
    dataset.save(CURRENT_DATASET)

    training_config = WeightedTrainingConfig(
        seed=BASE_SEED,
        epochs=TRAIN_EPOCHS,
        batch_size=64,
        hidden_units=32,
        activity_threshold=0.05,
        strong_threshold=0.30,
        active_loss_weight=2.0,
        strong_loss_weight=5.0,
    )
    trained = _run_with_heartbeat(
        f"dagger-train-{iteration_index}",
        lambda: train_weighted_candidate(
            dataset,
            _training_spec(),
            config=training_config,
        ),
    )
    portable = _portable_from_result(trained, iteration=iteration_index)
    save_portable_model(portable, CURRENT_WEIGHTS, CURRENT_METADATA)

    dev = _run_with_heartbeat(
        f"dagger-dev-{iteration_index}",
        lambda: run_closed_loop_benchmark(
            portable,
            config=ClimateBenchmarkConfig(
                seed=DEV_SEED,
                scenarios_per_family=1,
                steps_per_scenario=40,
                workers=WORKERS,
            ),
        ),
    )
    score = _dev_score(dev, trained.validation.control_mae)
    best_score = tuple(float(value) for value in state["best_score"])
    is_best = score < best_score
    if is_best:
        _copy_model(CURRENT_WEIGHTS, CURRENT_METADATA, BEST_WEIGHTS, BEST_METADATA)
        state["best_iteration"] = iteration_index
        state["best_score"] = _score_to_list(score)

    entry = {
        "iteration": iteration_index,
        "seed": collection_config.seed,
        "rows_before": before_rows,
        "rows_added": added_rows,
        "rows_after": len(dataset.features),
        "safe_fallback_fraction": float(np.mean(dagger.safe_fallbacks)),
        "humidity_mode_counts": {
            "RH": int(np.sum(dagger.humidity_modes == "RH")),
            "VPD": int(np.sum(dagger.humidity_modes == "VPD")),
        },
        "validation": asdict(trained.validation),
        "dev": dev.as_dict(),
        "score": _score_to_list(score),
        "is_best": is_best,
    }
    iterations = list(state["iterations"])
    iterations.append(entry)
    state["iterations"] = iterations
    state["completed_iterations"] = iteration_index
    _save_state(state)
    print(
        f"STAGE10_ITERATION={iteration_index} rows_added={added_rows} rows_total={len(dataset.features)} "
        f"val_control={trained.validation.control_mae:.6f} dev_tracking={dev.aggregate['ml'].tracking_cost:.6f} "
        f"dev_safety={dev.aggregate['ml'].safety_intervention_fraction:.4f} best={is_best}",
        flush=True,
    )


def final() -> None:
    state = _load_state()
    if int(state["completed_iterations"]) < 1:
        raise ValueError("cannot finalize Stage 10 without DAgger iterations")
    dataset = Dataset.load(CURRENT_DATASET)
    if frozen_split_fingerprint(dataset, "validation") != state["validation_fingerprint"]:
        raise AssertionError("validation split changed before final evaluation")
    if frozen_split_fingerprint(dataset, "test") != state["test_fingerprint"]:
        raise AssertionError("test split changed before final evaluation")

    best = load_portable_model(BEST_WEIGHTS, BEST_METADATA)
    final_report = _run_with_heartbeat(
        "final-held-out",
        lambda: run_closed_loop_benchmark(
            best,
            config=ClimateBenchmarkConfig.full(seed=FINAL_SEED, workers=WORKERS),
        ),
    )
    training_ids = set(str(value) for value in np.unique(dataset.scenario_ids))
    final_ids = set(str(item.scenario_id) for item in final_report.episodes)
    overlap = sorted(training_ids & final_ids)
    if overlap:
        raise AssertionError("final held-out scenarios overlap training data")

    x_test, y_test = dataset.select("test")
    test_prediction = best.predict(x_test)
    test_metrics = control_prediction_metrics(
        y_test,
        test_prediction,
        config=WeightedTrainingConfig.full(seed=BASE_SEED),
    )
    _copy_model(BEST_WEIGHTS, BEST_METADATA, FINAL_WEIGHTS, FINAL_METADATA)

    payload = {
        **state,
        "final": {
            "dataset_rows": int(len(dataset.features)),
            "train_rows": int(np.sum(dataset.splits == "train")),
            "validation_rows": int(np.sum(dataset.splits == "validation")),
            "test_rows": int(np.sum(dataset.splits == "test")),
            "scenario_overlap_count": 0,
            "open_loop_test": asdict(test_metrics),
            "closed_loop": final_report.as_dict(),
            "candidate_weights": str(FINAL_WEIGHTS),
            "candidate_metadata": str(FINAL_METADATA),
        },
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    verdict = "PASS" if final_report.verdict.accepted else "NO_GO"
    print(f"STAGE10_BEST_ITERATION={state['best_iteration']}", flush=True)
    print(
        f"STAGE10_FINAL tracking_rule={final_report.aggregate['rule'].tracking_cost:.6f} "
        f"tracking_ml={final_report.aggregate['ml'].tracking_cost:.6f} "
        f"safety_ml={final_report.aggregate['ml'].safety_intervention_fraction:.4f} "
        f"outside_ml={final_report.aggregate['ml'].outside_deadband_fraction:.4f}",
        flush=True,
    )
    print(f"STAGE10_FINAL_VERDICT={verdict}", flush=True)
    for reason in final_report.verdict.reasons:
        print("STAGE10_REASON=" + reason, flush=True)
    print(f"STAGE10_REPORT={REPORT_PATH}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init")
    iteration_parser = sub.add_parser("iteration")
    iteration_parser.add_argument("index", type=int)
    sub.add_parser("final")
    args = parser.parse_args()
    if args.command == "init":
        init()
    elif args.command == "iteration":
        iteration(args.index)
    else:
        final()


if __name__ == "__main__":
    main()
