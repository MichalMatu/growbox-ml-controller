#!/usr/bin/env python3
"""Stage 16C: one bounded Sequence-Teacher DAgger iteration on DEV only."""

from __future__ import annotations

import json
import math
import subprocess
import time
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path

import numpy as np

from tools.ml.climate_benchmark import _tracking_terms
from tools.ml.climate_dagger import (
    DaggerCollectionConfig,
    append_train_only,
    collect_dagger_rows,
    frozen_split_fingerprint,
)
from tools.ml.climate_input import (
    CLIMATE_V6_CONTRACT_PATH,
    ClimateEffectiveActionEstimator,
    ClimateInputConfig,
    ClimateTrendEstimator,
    encode_climate_input,
)
from tools.ml.climate_model_artifact import (
    ClimateModelMetadata,
    from_keras_model,
    load_portable_model,
)
from tools.ml.climate_policy import (
    ClimateRulePolicy,
    apply_climate_safety,
    apply_ml_request_deadzone,
    arbitrate_climate_action,
    hard_limit_violations,
)
from tools.ml.climate_scenarios import REQUIRED_SCENARIO_FAMILIES, structured_training_episodes
from tools.ml.climate_simulator import CLIMATE_OUTPUT_NAMES, ClimateAction, ClimateSimulator
from tools.ml.climate_training_weighted import (
    DEFAULT_WEIGHTED_CANDIDATES,
    WeightedTrainingConfig,
    train_weighted_candidate,
)
from tools.ml.contract import load_contract
from tools.ml.dataset import Dataset

BASE_DATASET = Path("build/climate_v6_full_seed1847_vpd.npz")
CURRENT_WEIGHTS = Path("reports/ml/climate_v6_model_stage13_compat.npz")
CURRENT_METADATA = Path("reports/ml/climate_v6_model_stage13_compat.json")
DAGGER_SEED = 707_107
DEV_SEED = 282_843
DAGGER_SCENARIOS_PER_FAMILY = 1
DAGGER_STEPS_PER_SCENARIO = 6
DAGGER_WORKERS = 4
DEV_SCENARIOS_PER_FAMILY = 1
DEV_STEPS_PER_SCENARIO = 24
TRAIN_SEED = 1847
TRAIN_EPOCHS = 28
EFFECTIVE_FEATURES = (
    "estimated_effective_heater",
    "estimated_effective_cooler",
    "estimated_effective_exhaust_fan",
    "estimated_effective_humidifier",
    "estimated_effective_dehumidifier",
    "estimated_effective_co2_doser",
)


def _migrate_cached_dataset(base: Dataset, contract) -> tuple[Dataset, bool]:
    current_names = tuple(contract.feature_names)
    if base.feature_names == current_names:
        if base.features.shape[1] != 44:
            raise AssertionError("current feature names do not have 44 columns")
        return base, False

    missing = tuple(name for name in current_names if name not in base.feature_names)
    extra = tuple(name for name in base.feature_names if name not in current_names)
    if set(missing) != set(EFFECTIVE_FEATURES) or extra:
        raise ValueError(
            "cached base dataset is not Stage-13-compatible: "
            f"missing={missing!r} extra={extra!r}"
        )
    if base.features.shape[1] != 38 or len(base.feature_names) != 38:
        raise ValueError(
            f"unexpected cached base shape before compatibility migration: {base.features.shape}"
        )
    if tuple(base.output_names) != tuple(contract.outputs):
        raise ValueError("cached base dataset output order does not match current contract")

    migrated = np.zeros((len(base.features), 44), dtype=np.float32)
    destination = {name: index for index, name in enumerate(current_names)}
    for source_index, name in enumerate(base.feature_names):
        migrated[:, destination[name]] = np.asarray(base.features[:, source_index], dtype=np.float32)

    for name in EFFECTIVE_FEATURES:
        if not np.all(migrated[:, destination[name]] == 0.0):
            raise AssertionError(f"compatibility column {name} is not zero")

    return (
        Dataset(
            features=migrated,
            labels=np.asarray(base.labels, dtype=np.float32),
            scenario_ids=base.scenario_ids,
            scenario_seeds=base.scenario_seeds,
            splits=base.splits,
            feature_names=current_names,
            output_names=tuple(contract.outputs),
        ),
        True,
    )


def _training_spec():
    return next(spec for spec in DEFAULT_WEIGHTED_CANDIDATES if spec.name == "adam_huber_baseline")


def _portable_candidate(trained, contract):
    source_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    metadata = ClimateModelMetadata(
        schema_version=contract.schema_version,
        contract_hash=contract.hash_hex,
        feature_names=contract.feature_names,
        output_names=contract.outputs,
        training_seed=TRAIN_SEED,
        candidate_name="stage16c-sequence-dagger-iter1-adam-huber",
        source_commit=source_commit,
    )
    return from_keras_model(trained.model, metadata)


def _run_policy(policy_name: str, model, contract, episodes):
    totals = defaultdict(float)
    family_totals = {family: defaultdict(float) for family in REQUIRED_SCENARIO_FAMILIES}
    rule = ClimateRulePolicy()

    for episode in episodes:
        simulator = ClimateSimulator(episode.scenario)
        trend_estimator = ClimateTrendEstimator()
        effective_estimator = ClimateEffectiveActionEstimator()
        previous_applied = ClimateAction()
        fam = family_totals[episode.family]

        for step in range(DEV_STEPS_PER_SCENARIO):
            profile = episode.profile_for_step(step, DEV_STEPS_PER_SCENARIO)
            simulator.set_light_level(profile.light_level)
            state = simulator.observe(add_sensor_noise=False)
            status = episode.forced_status_for_step(step, DEV_STEPS_PER_SCENARIO)
            tracking, *_ = _tracking_terms(state, profile, status, 30_000)
            hard = int(bool(hard_limit_violations(state)))
            totals["tracking"] += float(tracking)
            totals["hard"] += hard
            fam["tracking"] += float(tracking)
            fam["hard"] += hard

            if policy_name == "rule":
                raw = rule.choose(
                    simulator.scenario,
                    state,
                    profile,
                    status=status,
                    sensor_timeout_ms=30_000,
                )
            else:
                monotonic_ms = int(round(simulator.elapsed_s * 1000.0))
                trends = trend_estimator.update(state, monotonic_ms, status=status)
                input_config = ClimateInputConfig(
                    targets=profile.targets,
                    humidity_control_mode=profile.humidity_control_mode,
                )
                row = encode_climate_input(
                    simulator.scenario,
                    state,
                    previous=simulator.previous_command,
                    estimated_effective=effective_estimator.state,
                    trends=trends,
                    status=status,
                    config=input_config,
                    contract=contract,
                )
                prediction = model.predict(row)
                raw = ClimateAction.from_mapping(
                    dict(zip(CLIMATE_OUTPUT_NAMES, (float(v) for v in prediction), strict=True))
                )
                raw = apply_ml_request_deadzone(raw)

            arbitration = arbitrate_climate_action(raw, simulator.scenario)
            safety = apply_climate_safety(
                arbitration.action,
                simulator.scenario,
                state,
                profile,
                status=status,
                sensor_timeout_ms=30_000,
            )
            applied = safety.action
            if arbitration.interventions:
                totals["arbitration"] += 1
                fam["arbitration"] += 1
            if safety.interventions:
                totals["safety"] += 1
                fam["safety"] += 1

            current = applied.as_tuple()
            previous = previous_applied.as_tuple()
            switching = sum(abs(a - b) for a, b in zip(current, previous, strict=True)) / len(
                CLIMATE_OUTPUT_NAMES
            )
            effort = sum(current) / len(CLIMATE_OUTPUT_NAMES)
            totals["switching"] += switching
            totals["effort"] += effort
            fam["switching"] += switching
            fam["effort"] += effort

            simulator.step(applied, add_sensor_noise=False, light_level=profile.light_level)
            if policy_name != "rule":
                effective_estimator.update(simulator.scenario, applied)
            previous_applied = applied
            totals["steps"] += 1
            fam["steps"] += 1

    steps = int(totals["steps"])
    metrics = {
        "steps": steps,
        "tracking_cost": totals["tracking"] / steps,
        "switching_per_step": totals["switching"] / steps,
        "actuator_effort_per_step": totals["effort"] / steps,
        "arbitration_intervention_fraction": totals["arbitration"] / steps,
        "safety_intervention_fraction": totals["safety"] / steps,
        "hard_limit_violation_fraction": totals["hard"] / steps,
    }
    families = {
        family: {
            "tracking_cost": values["tracking"] / values["steps"],
            "switching_per_step": values["switching"] / values["steps"],
            "arbitration_intervention_fraction": values["arbitration"] / values["steps"],
            "safety_intervention_fraction": values["safety"] / values["steps"],
            "hard_limit_violation_fraction": values["hard"] / values["steps"],
        }
        for family, values in family_totals.items()
    }
    return metrics, families


def main() -> None:
    started = time.monotonic()
    if not BASE_DATASET.exists():
        raise FileNotFoundError(
            "cached Stage 9B dataset is missing; refusing to regenerate it with the old Teacher"
        )
    if not CURRENT_WEIGHTS.exists() or not CURRENT_METADATA.exists():
        raise FileNotFoundError("Stage 13 compatibility model is missing")

    contract = load_contract(CLIMATE_V6_CONTRACT_PATH)
    base_raw = Dataset.load(BASE_DATASET)
    base, migrated = _migrate_cached_dataset(base_raw, contract)
    if base.features.shape != (7200, 44) or base.labels.shape != (7200, 6):
        raise ValueError(f"unexpected compatible base dataset shape: {base.features.shape}, {base.labels.shape}")
    split_counts = {
        split: int(np.sum(base.splits == split)) for split in ("train", "validation", "test")
    }
    if split_counts != {"train": 4800, "validation": 1200, "test": 1200}:
        raise ValueError(f"unexpected cached split counts: {split_counts}")

    validation_fp = frozen_split_fingerprint(base, "validation")
    test_fp = frozen_split_fingerprint(base, "test")
    current = load_portable_model(CURRENT_WEIGHTS, CURRENT_METADATA)
    if current.metadata.feature_names != contract.feature_names:
        raise ValueError("Stage 13 compatibility model does not match current contract")

    dagger = collect_dagger_rows(
        current,
        config=DaggerCollectionConfig(
            seed=DAGGER_SEED,
            scenarios_per_family=DAGGER_SCENARIOS_PER_FAMILY,
            steps_per_scenario=DAGGER_STEPS_PER_SCENARIO,
            workers=DAGGER_WORKERS,
            teacher_kind="sequence",
            random_invalid_probability=0.0,
            random_stale_probability=0.0,
        ),
        contract=contract,
    )
    expected_dagger_rows = (
        len(REQUIRED_SCENARIO_FAMILIES)
        * DAGGER_SCENARIOS_PER_FAMILY
        * DAGGER_STEPS_PER_SCENARIO
    )
    if len(dagger.dataset.features) != expected_dagger_rows:
        raise AssertionError(
            f"unexpected Sequence DAgger rows: {len(dagger.dataset.features)} != {expected_dagger_rows}"
        )
    combined = append_train_only(base, dagger.dataset)
    if frozen_split_fingerprint(combined, "validation") != validation_fp:
        raise AssertionError("Sequence DAgger modified frozen validation split")
    if frozen_split_fingerprint(combined, "test") != test_fp:
        raise AssertionError("Sequence DAgger modified frozen test split")

    training_config = WeightedTrainingConfig(
        seed=TRAIN_SEED,
        epochs=TRAIN_EPOCHS,
        batch_size=64,
        hidden_units=32,
        activity_threshold=0.05,
        strong_threshold=0.30,
        active_loss_weight=2.0,
        strong_loss_weight=5.0,
    )
    trained = train_weighted_candidate(combined, _training_spec(), config=training_config)
    candidate = _portable_candidate(trained, contract)

    episodes = structured_training_episodes(
        scenarios_per_family=DEV_SCENARIOS_PER_FAMILY,
        seed=DEV_SEED,
    )
    expected_episodes = len(REQUIRED_SCENARIO_FAMILIES) * DEV_SCENARIOS_PER_FAMILY
    if len(episodes) != expected_episodes:
        raise AssertionError(f"unexpected DEV episode count: {len(episodes)} != {expected_episodes}")

    rule_metrics, rule_families = _run_policy("rule", None, contract, episodes)
    current_metrics, current_families = _run_policy("current", current, contract, episodes)
    candidate_metrics, candidate_families = _run_policy("candidate", candidate, contract, episodes)

    tracking_improvement = (
        (current_metrics["tracking_cost"] - candidate_metrics["tracking_cost"])
        / current_metrics["tracking_cost"]
        if current_metrics["tracking_cost"]
        else 0.0
    )
    switching_ratio = (
        candidate_metrics["switching_per_step"] / current_metrics["switching_per_step"]
        if current_metrics["switching_per_step"]
        else 0.0
    )
    qualifies = (
        tracking_improvement >= 0.002
        and candidate_metrics["hard_limit_violation_fraction"]
        <= current_metrics["hard_limit_violation_fraction"]
        and candidate_metrics["safety_intervention_fraction"]
        <= current_metrics["safety_intervention_fraction"]
        and candidate_metrics["arbitration_intervention_fraction"]
        <= current_metrics["arbitration_intervention_fraction"]
        and switching_ratio <= 1.10
    )

    output = {
        "experiment": "stage16c_sequence_dagger_iter1_dev",
        "source_head": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "base_dataset_path": str(BASE_DATASET),
        "base_dataset_compat_migrated_in_memory": migrated,
        "base_rows": int(len(base.features)),
        "combined_rows": int(len(combined.features)),
        "split_counts": split_counts,
        "dagger_seed": DAGGER_SEED,
        "dagger_scenarios_per_family": DAGGER_SCENARIOS_PER_FAMILY,
        "dagger_steps_per_scenario": DAGGER_STEPS_PER_SCENARIO,
        "dagger_rows": int(len(dagger.dataset.features)),
        "dagger_teacher_kind": "sequence",
        "dagger_safe_fallback_fraction": float(np.mean(dagger.safe_fallbacks)),
        "train_seed": TRAIN_SEED,
        "train_epochs": TRAIN_EPOCHS,
        "training_spec": _training_spec().name,
        "validation": asdict(trained.validation),
        "dev_seed": DEV_SEED,
        "dev_scenarios_per_family": DEV_SCENARIOS_PER_FAMILY,
        "dev_steps_per_scenario": DEV_STEPS_PER_SCENARIO,
        "rule_metrics": rule_metrics,
        "current_metrics": current_metrics,
        "candidate_metrics": candidate_metrics,
        "current_families": current_families,
        "candidate_families": candidate_families,
        "rule_families": rule_families,
        "tracking_improvement_vs_current_fraction": float(tracking_improvement),
        "switching_ratio_vs_current": float(switching_ratio),
        "candidate_qualifies_for_iteration2": bool(qualifies),
        "validation_fingerprint_preserved": True,
        "test_fingerprint_preserved": True,
        "test_metrics_evaluated": False,
        "reserved_stage14ab_test_split_evaluated": False,
        "candidate_persisted": False,
        "wall_seconds": float(time.monotonic() - started),
    }
    if not math.isfinite(output["wall_seconds"]):
        raise AssertionError("Stage 16C produced non-finite wall time")
    print("STAGE16C_JSON=" + json.dumps(output, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
