from __future__ import annotations

import json
import subprocess
from dataclasses import asdict
from pathlib import Path

from tools.ml.climate_dataset import ClimateDatasetConfig, assert_climate_dataset_ready, audit_climate_dataset
from tools.ml.climate_dataset_parallel import generate_climate_dataset_parallel
from tools.ml.climate_input import CLIMATE_V6_CONTRACT_PATH
from tools.ml.climate_training import ClimateTrainingConfig, compare_candidates, comparison_summary
from tools.ml.contract import load_contract


def main() -> None:
    seed = 1847
    print("CLIMATE_V6_FULL_TRAINING_START", flush=True)
    dataset_config = ClimateDatasetConfig.full(seed=seed)
    bundle = generate_climate_dataset_parallel(dataset_config, workers=4)
    audit = audit_climate_dataset(bundle)
    assert_climate_dataset_ready(
        audit,
        require_family_coverage_in_each_split=True,
        bundle=bundle,
    )
    cache_path = Path("build/climate_v6_full_seed1847.npz")
    bundle.dataset.save(cache_path)
    print(f"DATASET_CACHE={cache_path}", flush=True)

    training_config = ClimateTrainingConfig.full(seed=seed)
    comparison = compare_candidates(bundle.dataset, config=training_config)
    for line in comparison_summary(comparison):
        print(line, flush=True)

    contract = load_contract(CLIMATE_V6_CONTRACT_PATH)
    winner = comparison.winner
    assert winner.test is not None
    payload = {
        "schema_version": contract.schema_version,
        "contract_hash": contract.hash_hex,
        "feature_count": len(contract.features),
        "output_names": list(contract.outputs),
        "dataset": {
            "seed": seed,
            "rows": int(bundle.dataset.features.shape[0]),
            "scenarios_per_family": dataset_config.scenarios_per_family,
            "steps_per_scenario": dataset_config.steps_per_scenario,
            "split_counts": audit.split_counts,
            "family_counts": audit.family_counts,
            "active_fraction": audit.active_fraction,
            "safe_fallback_fraction": audit.safe_fallback_fraction,
            "all_zero_fraction": audit.all_zero_fraction,
        },
        "training": {
            "seed": training_config.seed,
            "epochs": training_config.epochs,
            "batch_size": training_config.batch_size,
            "hidden_units": training_config.hidden_units,
            "parameter_count": int(winner.model.count_params()),
            "selection_metric": "validation.balanced_mae",
            "winner": winner.spec.name,
            "candidates": [
                {
                    "spec": asdict(result.spec),
                    "validation": asdict(result.validation),
                }
                for result in comparison.candidates
            ],
            "winner_test": asdict(winner.test),
        },
        "git_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True
        ).strip(),
    }
    report_path = Path("build/climate_v6_training_seed1847.json")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"TRAINING_REPORT={report_path}", flush=True)
    print("CLIMATE_V6_FULL_TRAINING=PASS", flush=True)


if __name__ == "__main__":
    main()
