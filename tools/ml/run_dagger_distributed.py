from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict
from pathlib import Path

import numpy as np

from tools.ml.climate_benchmark import ClimateBenchmarkConfig, run_closed_loop_benchmark
from tools.ml.climate_dagger import (
    DaggerCollectionConfig,
    DaggerRows,
    _EpisodeWork,
    _collect_episode,
    append_train_only,
    frozen_split_fingerprint,
)
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
    save_portable_model,
)
from tools.ml.climate_scenarios import structured_training_episodes
from tools.ml.climate_simulator import CLIMATE_OUTPUT_NAMES
from tools.ml.climate_training_weighted import (
    DEFAULT_WEIGHTED_CANDIDATES,
    WeightedTrainingConfig,
    control_prediction_metrics,
    train_weighted_candidate,
)
from tools.ml.contract import load_contract
from tools.ml.dataset import Dataset

BASE_SEED = 1847
DAGGER_SEED = 720_003
DEV_SEED = 314_159
FINAL_SEED = 577_215
DEFAULT_SCENARIOS_PER_FAMILY = 12
DEFAULT_STEPS_PER_SCENARIO = 100
DEFAULT_EPOCHS = 36


def shard_episode_indices(total: int, shard_index: int, shard_count: int) -> tuple[int, ...]:
    if total <= 0:
        raise ValueError("total must be positive")
    if shard_count <= 0:
        raise ValueError("shard_count must be positive")
    if not 0 <= shard_index < shard_count:
        raise ValueError("shard_index must be in [0, shard_count)")
    return tuple(index for index in range(total) if index % shard_count == shard_index)


def _concat(parts: tuple[tuple[np.ndarray, ...], ...], index: int) -> np.ndarray:
    return np.concatenate([part[index] for part in parts], axis=0)


def collect_dagger_shard(
    *,
    weights: Path,
    metadata: Path,
    seed: int,
    scenarios_per_family: int,
    steps_per_scenario: int,
    workers: int,
    shard_index: int,
    shard_count: int,
) -> tuple[DaggerRows, np.ndarray]:
    model = load_portable_model(weights, metadata)
    contract = load_contract(CLIMATE_V6_CONTRACT_PATH)
    if model.metadata.schema_version != 6:
        raise ValueError("distributed DAgger requires climate-v6 model")
    if model.metadata.feature_names != contract.feature_names:
        raise ValueError("distributed DAgger model feature order mismatch")
    if model.metadata.output_names != contract.outputs or contract.outputs != CLIMATE_OUTPUT_NAMES:
        raise ValueError("distributed DAgger output order mismatch")

    config = DaggerCollectionConfig(
        seed=seed,
        scenarios_per_family=scenarios_per_family,
        steps_per_scenario=steps_per_scenario,
        workers=workers,
    )
    episodes = structured_training_episodes(
        scenarios_per_family=scenarios_per_family,
        seed=seed,
    )
    selected_indices = shard_episode_indices(len(episodes), shard_index, shard_count)
    if not selected_indices:
        raise ValueError("shard has no episodes")
    work = tuple(
        _EpisodeWork(
            episode=episodes[index],
            episode_index=index,
            config=config,
            model=model,
            contract=contract,
        )
        for index in selected_indices
    )
    if workers <= 1:
        parts = tuple(_collect_episode(item) for item in work)
    else:
        with ProcessPoolExecutor(max_workers=min(workers, len(work))) as executor:
            parts = tuple(executor.map(_collect_episode, work, chunksize=1))

    dataset = Dataset(
        features=_concat(parts, 0),
        labels=_concat(parts, 1),
        scenario_ids=_concat(parts, 2),
        scenario_seeds=_concat(parts, 3),
        splits=_concat(parts, 4),
        feature_names=contract.feature_names,
        output_names=contract.outputs,
    )
    rows = DaggerRows(
        dataset=dataset,
        families=_concat(parts, 5),
        humidity_modes=_concat(parts, 6),
        safe_fallbacks=_concat(parts, 7),
    )
    row_order = np.concatenate(
        [
            np.arange(
                episode_index * steps_per_scenario,
                (episode_index + 1) * steps_per_scenario,
                dtype=np.int64,
            )
            for episode_index in selected_indices
        ]
    )
    if len(row_order) != len(dataset.features):
        raise AssertionError("distributed DAgger row-order length mismatch")
    return rows, row_order


def save_shard(path: Path, rows: DaggerRows, row_order: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    dataset = rows.dataset
    np.savez_compressed(
        path,
        features=dataset.features,
        labels=dataset.labels,
        scenario_ids=dataset.scenario_ids,
        scenario_seeds=dataset.scenario_seeds,
        splits=dataset.splits,
        feature_names=np.asarray(dataset.feature_names),
        output_names=np.asarray(dataset.output_names),
        families=rows.families,
        humidity_modes=rows.humidity_modes,
        safe_fallbacks=rows.safe_fallbacks,
        row_order=np.asarray(row_order, dtype=np.int64),
    )


def load_shard(path: Path) -> tuple[DaggerRows, np.ndarray]:
    with np.load(path, allow_pickle=False) as data:
        dataset = Dataset(
            features=data["features"],
            labels=data["labels"],
            scenario_ids=data["scenario_ids"],
            scenario_seeds=data["scenario_seeds"],
            splits=data["splits"],
            feature_names=tuple(str(value) for value in data["feature_names"]),
            output_names=tuple(str(value) for value in data["output_names"]),
        )
        rows = DaggerRows(
            dataset=dataset,
            families=data["families"],
            humidity_modes=data["humidity_modes"],
            safe_fallbacks=data["safe_fallbacks"],
        )
        row_order = np.asarray(data["row_order"], dtype=np.int64)
    return rows, row_order


def merge_shards(paths: list[Path], *, expected_rows: int) -> DaggerRows:
    if not paths:
        raise ValueError("no DAgger shard files supplied")
    loaded = [load_shard(path) for path in sorted(paths)]
    first = loaded[0][0].dataset
    feature_names = first.feature_names
    output_names = first.output_names
    for rows, _order in loaded:
        if rows.dataset.feature_names != feature_names or rows.dataset.output_names != output_names:
            raise ValueError("DAgger shard contract mismatch")

    row_order = np.concatenate([order for _rows, order in loaded])
    if len(row_order) != expected_rows:
        raise AssertionError(f"expected {expected_rows} DAgger rows, got {len(row_order)}")
    sorted_order = np.sort(row_order)
    expected_order = np.arange(expected_rows, dtype=np.int64)
    if not np.array_equal(sorted_order, expected_order):
        raise AssertionError("DAgger shards do not form one complete non-overlapping row order")
    permutation = np.argsort(row_order, kind="stable")

    def cat_dataset(name: str) -> np.ndarray:
        return np.concatenate(
            [getattr(rows.dataset, name) for rows, _order in loaded], axis=0
        )[permutation]

    def cat_meta(name: str) -> np.ndarray:
        return np.concatenate([getattr(rows, name) for rows, _order in loaded], axis=0)[
            permutation
        ]

    dataset = Dataset(
        features=cat_dataset("features"),
        labels=cat_dataset("labels"),
        scenario_ids=cat_dataset("scenario_ids"),
        scenario_seeds=cat_dataset("scenario_seeds"),
        splits=cat_dataset("splits"),
        feature_names=feature_names,
        output_names=output_names,
    )
    return DaggerRows(
        dataset=dataset,
        families=cat_meta("families"),
        humidity_modes=cat_meta("humidity_modes"),
        safe_fallbacks=cat_meta("safe_fallbacks"),
    )


def generate_base(output: Path, workers: int) -> None:
    started = time.monotonic()
    bundle = generate_climate_dataset_parallel(
        ClimateDatasetConfig.full(seed=BASE_SEED), workers=workers
    )
    audit = audit_climate_dataset(bundle)
    assert_climate_dataset_ready(
        audit,
        require_family_coverage_in_each_split=True,
        require_humidity_mode_coverage_in_each_split=True,
        bundle=bundle,
    )
    if bundle.dataset.features.shape != (7200, 38) or bundle.dataset.labels.shape != (7200, 6):
        raise AssertionError("Stage 11 regenerated base dataset shape mismatch")
    split_counts = {
        split: int(np.sum(bundle.dataset.splits == split))
        for split in ("train", "validation", "test")
    }
    if split_counts != {"train": 4800, "validation": 1200, "test": 1200}:
        raise AssertionError(f"Stage 11 regenerated base split mismatch: {split_counts}")
    bundle.dataset.save(output)
    print(
        f"STAGE11_BASE rows=7200 workers={workers} elapsed_s={time.monotonic() - started:.1f}",
        flush=True,
    )


def merge_with_base(
    *,
    base_path: Path,
    shard_paths: list[Path],
    output: Path,
    scenarios_per_family: int,
    steps_per_scenario: int,
    summary: Path,
) -> None:
    base = Dataset.load(base_path)
    validation_fp = frozen_split_fingerprint(base, "validation")
    test_fp = frozen_split_fingerprint(base, "test")
    expected_rows = 15 * scenarios_per_family * steps_per_scenario
    dagger = merge_shards(shard_paths, expected_rows=expected_rows)
    merged = append_train_only(base, dagger.dataset)
    if frozen_split_fingerprint(merged, "validation") != validation_fp:
        raise AssertionError("distributed DAgger modified frozen validation split")
    if frozen_split_fingerprint(merged, "test") != test_fp:
        raise AssertionError("distributed DAgger modified frozen test split")
    merged.save(output)
    payload = {
        "base_rows": int(len(base.features)),
        "dagger_rows": int(len(dagger.dataset.features)),
        "total_rows": int(len(merged.features)),
        "train_rows": int(np.sum(merged.splits == "train")),
        "validation_rows": int(np.sum(merged.splits == "validation")),
        "test_rows": int(np.sum(merged.splits == "test")),
        "safe_fallback_fraction": float(np.mean(dagger.safe_fallbacks)),
        "humidity_mode_counts": {
            "RH": int(np.sum(dagger.humidity_modes == "RH")),
            "VPD": int(np.sum(dagger.humidity_modes == "VPD")),
        },
        "validation_fingerprint": validation_fp,
        "test_fingerprint": test_fp,
    }
    summary.parent.mkdir(parents=True, exist_ok=True)
    summary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        f"STAGE11_MERGE base={payload['base_rows']} dagger={payload['dagger_rows']} "
        f"total={payload['total_rows']}",
        flush=True,
    )


def _training_spec():
    return next(
        spec for spec in DEFAULT_WEIGHTED_CANDIDATES if spec.name == "adam_huber_baseline"
    )


def _portable_from_result(result, *, hidden_units: int):
    contract = load_contract(CLIMATE_V6_CONTRACT_PATH)
    source_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    metadata = ClimateModelMetadata(
        schema_version=contract.schema_version,
        contract_hash=contract.hash_hex,
        feature_names=contract.feature_names,
        output_names=contract.outputs,
        training_seed=BASE_SEED,
        candidate_name=f"stage11-h{hidden_units}-adam-huber",
        source_commit=source_commit,
    )
    return from_keras_model(result.model, metadata)


def _dev_score(report, validation_control_mae: float) -> tuple[float, ...]:
    rule = report.aggregate["rule"]
    ml = report.aggregate["ml"]
    return (
        1.0 if ml.hard_limit_violation_fraction > 0.0 else 0.0,
        max(
            0.0,
            ml.safety_intervention_fraction - rule.safety_intervention_fraction,
        ),
        ml.tracking_cost,
        ml.outside_deadband_fraction,
        validation_control_mae,
    )


def train_candidate(
    *,
    dataset_path: Path,
    hidden_units: int,
    epochs: int,
    workers: int,
    output_dir: Path,
) -> None:
    dataset = Dataset.load(dataset_path)
    config = WeightedTrainingConfig(
        seed=BASE_SEED,
        epochs=epochs,
        batch_size=64,
        hidden_units=hidden_units,
        activity_threshold=0.05,
        strong_threshold=0.30,
        active_loss_weight=2.0,
        strong_loss_weight=5.0,
    )
    started = time.monotonic()
    result = train_weighted_candidate(dataset, _training_spec(), config=config)
    portable = _portable_from_result(result, hidden_units=hidden_units)
    output_dir.mkdir(parents=True, exist_ok=True)
    weights_path = output_dir / f"candidate-h{hidden_units}.npz"
    metadata_path = output_dir / f"candidate-h{hidden_units}.json"
    report_path = output_dir / f"candidate-h{hidden_units}-report.json"
    save_portable_model(portable, weights_path, metadata_path)
    dev = run_closed_loop_benchmark(
        portable,
        config=ClimateBenchmarkConfig(
            seed=DEV_SEED,
            scenarios_per_family=1,
            steps_per_scenario=40,
            workers=workers,
        ),
    )
    score = _dev_score(dev, result.validation.control_mae)
    payload = {
        "hidden_units": hidden_units,
        "epochs": epochs,
        "validation": asdict(result.validation),
        "dev": dev.as_dict(),
        "score": [float(value) for value in score],
        "weights_file": weights_path.name,
        "metadata_file": metadata_path.name,
        "elapsed_seconds": time.monotonic() - started,
    }
    report_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        f"STAGE11_CANDIDATE hidden={hidden_units} "
        f"val_control={result.validation.control_mae:.6f} "
        f"dev_tracking={dev.aggregate['ml'].tracking_cost:.6f} "
        f"elapsed_s={payload['elapsed_seconds']:.1f}",
        flush=True,
    )


def _copy_model(
    src_weights: Path,
    src_metadata: Path,
    dst_weights: Path,
    dst_metadata: Path,
) -> None:
    dst_weights.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src_weights, dst_weights)
    metadata = json.loads(src_metadata.read_text(encoding="utf-8"))
    metadata["weights_file"] = dst_weights.name
    dst_metadata.write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def select_and_finalize(
    *,
    dataset_path: Path,
    candidate_reports: list[Path],
    candidate_root: Path,
    workers: int,
    output_report: Path,
    output_weights: Path,
    output_metadata: Path,
) -> None:
    if not candidate_reports:
        raise ValueError("no Stage 11 candidate reports supplied")
    candidates = [
        json.loads(path.read_text(encoding="utf-8")) for path in candidate_reports
    ]
    winner = min(
        candidates,
        key=lambda item: tuple(float(value) for value in item["score"]),
    )
    hidden_units = int(winner["hidden_units"])
    src_weights = candidate_root / str(winner["weights_file"])
    src_metadata = candidate_root / str(winner["metadata_file"])
    if not src_weights.exists() or not src_metadata.exists():
        raise FileNotFoundError("selected Stage 11 model artifact is missing")
    model = load_portable_model(src_weights, src_metadata)
    final = run_closed_loop_benchmark(
        model,
        config=ClimateBenchmarkConfig.full(seed=FINAL_SEED, workers=workers),
    )
    dataset = Dataset.load(dataset_path)
    training_ids = set(str(value) for value in np.unique(dataset.scenario_ids))
    final_ids = set(str(item.scenario_id) for item in final.episodes)
    overlap = sorted(training_ids & final_ids)
    if overlap:
        raise AssertionError("Stage 11 final held-out scenarios overlap training data")
    x_test, y_test = dataset.select("test")
    test_metrics = control_prediction_metrics(
        y_test,
        model.predict(x_test),
        config=WeightedTrainingConfig.full(seed=BASE_SEED),
    )
    _copy_model(src_weights, src_metadata, output_weights, output_metadata)
    payload = {
        "schema_version": 1,
        "stage": 11,
        "method": "distributed-dagger-architecture-search",
        "base_seed": BASE_SEED,
        "dagger_seed": DAGGER_SEED,
        "dev_seed": DEV_SEED,
        "final_seed": FINAL_SEED,
        "selected_hidden_units": hidden_units,
        "candidate_scores": [
            {
                "hidden_units": int(item["hidden_units"]),
                "score": item["score"],
                "validation_control_mae": item["validation"]["control_mae"],
                "dev_tracking_cost": item["dev"]["aggregate"]["ml"]["tracking_cost"],
            }
            for item in sorted(candidates, key=lambda item: int(item["hidden_units"]))
        ],
        "dataset_rows": int(len(dataset.features)),
        "train_rows": int(np.sum(dataset.splits == "train")),
        "validation_rows": int(np.sum(dataset.splits == "validation")),
        "test_rows": int(np.sum(dataset.splits == "test")),
        "scenario_overlap_count": 0,
        "open_loop_test": asdict(test_metrics),
        "closed_loop": final.as_dict(),
        "candidate_weights": str(output_weights),
        "candidate_metadata": str(output_metadata),
    }
    output_report.parent.mkdir(parents=True, exist_ok=True)
    output_report.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    verdict = "PASS" if final.verdict.accepted else "NO_GO"
    print(f"STAGE11_SELECTED_HIDDEN={hidden_units}", flush=True)
    print(
        f"STAGE11_FINAL tracking_rule={final.aggregate['rule'].tracking_cost:.6f} "
        f"tracking_ml={final.aggregate['ml'].tracking_cost:.6f} "
        f"temp_ml={final.aggregate['ml'].temperature_mae_c:.6f} "
        f"rh_ml={final.aggregate['ml'].rh_mae_pct:.6f} "
        f"vpd_ml={final.aggregate['ml'].vpd_mae_kpa:.6f} "
        f"co2_ml={final.aggregate['ml'].co2_mae_ppm:.3f}",
        flush=True,
    )
    print(f"STAGE11_FINAL_VERDICT={verdict}", flush=True)
    for reason in final.verdict.reasons:
        print(f"STAGE11_REASON={reason}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    base = sub.add_parser("base")
    base.add_argument("--output", type=Path, required=True)
    base.add_argument("--workers", type=int, default=4)

    collect = sub.add_parser("collect")
    collect.add_argument("--weights", type=Path, required=True)
    collect.add_argument("--metadata", type=Path, required=True)
    collect.add_argument("--output", type=Path, required=True)
    collect.add_argument("--seed", type=int, default=DAGGER_SEED)
    collect.add_argument(
        "--scenarios-per-family",
        type=int,
        default=DEFAULT_SCENARIOS_PER_FAMILY,
    )
    collect.add_argument(
        "--steps-per-scenario",
        type=int,
        default=DEFAULT_STEPS_PER_SCENARIO,
    )
    collect.add_argument("--workers", type=int, default=4)
    collect.add_argument("--shard-index", type=int, required=True)
    collect.add_argument("--shard-count", type=int, required=True)

    merge = sub.add_parser("merge")
    merge.add_argument("--base", type=Path, required=True)
    merge.add_argument("--shards", type=Path, nargs="+", required=True)
    merge.add_argument("--output", type=Path, required=True)
    merge.add_argument("--summary", type=Path, required=True)
    merge.add_argument(
        "--scenarios-per-family",
        type=int,
        default=DEFAULT_SCENARIOS_PER_FAMILY,
    )
    merge.add_argument(
        "--steps-per-scenario",
        type=int,
        default=DEFAULT_STEPS_PER_SCENARIO,
    )

    train = sub.add_parser("train")
    train.add_argument("--dataset", type=Path, required=True)
    train.add_argument("--hidden-units", type=int, required=True)
    train.add_argument("--epochs", type=int, default=DEFAULT_EPOCHS)
    train.add_argument("--workers", type=int, default=4)
    train.add_argument("--output-dir", type=Path, required=True)

    final = sub.add_parser("final")
    final.add_argument("--dataset", type=Path, required=True)
    final.add_argument("--candidate-reports", type=Path, nargs="+", required=True)
    final.add_argument("--candidate-root", type=Path, required=True)
    final.add_argument("--workers", type=int, default=4)
    final.add_argument("--output-report", type=Path, required=True)
    final.add_argument("--output-weights", type=Path, required=True)
    final.add_argument("--output-metadata", type=Path, required=True)

    args = parser.parse_args()
    if args.command == "base":
        generate_base(args.output, args.workers)
    elif args.command == "collect":
        rows, row_order = collect_dagger_shard(
            weights=args.weights,
            metadata=args.metadata,
            seed=args.seed,
            scenarios_per_family=args.scenarios_per_family,
            steps_per_scenario=args.steps_per_scenario,
            workers=args.workers,
            shard_index=args.shard_index,
            shard_count=args.shard_count,
        )
        save_shard(args.output, rows, row_order)
        print(
            f"STAGE11_SHARD index={args.shard_index}/{args.shard_count} "
            f"rows={len(rows.dataset.features)}",
            flush=True,
        )
    elif args.command == "merge":
        merge_with_base(
            base_path=args.base,
            shard_paths=args.shards,
            output=args.output,
            scenarios_per_family=args.scenarios_per_family,
            steps_per_scenario=args.steps_per_scenario,
            summary=args.summary,
        )
    elif args.command == "train":
        train_candidate(
            dataset_path=args.dataset,
            hidden_units=args.hidden_units,
            epochs=args.epochs,
            workers=args.workers,
            output_dir=args.output_dir,
        )
    else:
        select_and_finalize(
            dataset_path=args.dataset,
            candidate_reports=args.candidate_reports,
            candidate_root=args.candidate_root,
            workers=args.workers,
            output_report=args.output_report,
            output_weights=args.output_weights,
            output_metadata=args.output_metadata,
        )


if __name__ == "__main__":
    main()
