#!/usr/bin/env python3
"""Wire Stage 13 effective-state features and add a behavior-preserving compatibility model."""

from __future__ import annotations

from pathlib import Path

ROOT = Path.cwd()


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, text: str) -> None:
    (ROOT / path).write_text(text, encoding="utf-8")


def replace_once(path: str, old: str, new: str) -> None:
    text = read(path)
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected exactly one occurrence of {old!r}, found {count}")
    write(path, text.replace(old, new, 1))


# Benchmark: estimator state must be passed to the ML encoder and advanced from applied commands.
replace_once(
    "tools/ml/climate_benchmark.py",
    "    ClimateInputConfig,\n    ClimateTrendEstimator,",
    "    ClimateEffectiveActionEstimator,\n    ClimateInputConfig,\n    ClimateTrendEstimator,",
)
replace_once(
    "tools/ml/climate_benchmark.py",
    "    model: ClimatePortableModel,\n    trend_estimator: ClimateTrendEstimator,\n) -> tuple[ClimateAction, dict[str, MeasurementStatus]]:",
    "    model: ClimatePortableModel,\n    trend_estimator: ClimateTrendEstimator,\n    effective_estimator: ClimateEffectiveActionEstimator,\n) -> tuple[ClimateAction, dict[str, MeasurementStatus]]:",
)
replace_once(
    "tools/ml/climate_benchmark.py",
    "        previous=simulator.previous_command,\n        trends=trends,",
    "        previous=simulator.previous_command,\n        estimated_effective=effective_estimator.state,\n        trends=trends,",
)
replace_once(
    "tools/ml/climate_benchmark.py",
    "    trend_estimator = ClimateTrendEstimator()\n    previous_applied = ClimateAction()",
    "    trend_estimator = ClimateTrendEstimator()\n    effective_estimator = ClimateEffectiveActionEstimator()\n    previous_applied = ClimateAction()",
)
replace_once(
    "tools/ml/climate_benchmark.py",
    "            work.model,\n            trend_estimator,\n        )",
    "            work.model,\n            trend_estimator,\n            effective_estimator,\n        )",
)
replace_once(
    "tools/ml/climate_benchmark.py",
    "        simulator.step(applied, add_sensor_noise=False, light_level=profile.light_level)\n        previous_applied = applied",
    "        simulator.step(applied, add_sensor_noise=False, light_level=profile.light_level)\n        effective_estimator.update(simulator.scenario, applied)\n        previous_applied = applied",
)

# Parallel dataset generator: mirror the sequential Stage 13 estimator semantics.
replace_once(
    "tools/ml/climate_dataset_parallel.py",
    "    CLIMATE_V6_CONTRACT_PATH,\n    ClimateInputConfig,",
    "    CLIMATE_V6_CONTRACT_PATH,\n    ClimateEffectiveActionEstimator,\n    ClimateInputConfig,",
)
replace_once(
    "tools/ml/climate_dataset_parallel.py",
    "    trend_estimator = ClimateTrendEstimator()\n    status_rng =",
    "    trend_estimator = ClimateTrendEstimator()\n    effective_estimator = ClimateEffectiveActionEstimator()\n    status_rng =",
)
replace_once(
    "tools/ml/climate_dataset_parallel.py",
    "                previous=simulator.previous_command,\n                trends=trends,",
    "                previous=simulator.previous_command,\n                estimated_effective=effective_estimator.state,\n                trends=trends,",
)
replace_once(
    "tools/ml/climate_dataset_parallel.py",
    "        simulator.step(\n            teacher_result.action,\n            add_sensor_noise=False,\n            light_level=profile.light_level,\n        )",
    "        simulator.step(\n            teacher_result.action,\n            add_sensor_noise=False,\n            light_level=profile.light_level,\n        )\n        effective_estimator.update(simulator.scenario, teacher_result.action)",
)

# DAgger collector: features describe the estimated plant state produced by previously applied safe commands.
replace_once(
    "tools/ml/climate_dagger.py",
    "    ClimateInputConfig,\n    ClimateTrendEstimator,",
    "    ClimateEffectiveActionEstimator,\n    ClimateInputConfig,\n    ClimateTrendEstimator,",
)
replace_once(
    "tools/ml/climate_dagger.py",
    "    trend_estimator = ClimateTrendEstimator()\n    teacher = ClimateRolloutTeacher()",
    "    trend_estimator = ClimateTrendEstimator()\n    effective_estimator = ClimateEffectiveActionEstimator()\n    teacher = ClimateRolloutTeacher()",
)
replace_once(
    "tools/ml/climate_dagger.py",
    "            previous=simulator.previous_command,\n            trends=trends,",
    "            previous=simulator.previous_command,\n            estimated_effective=effective_estimator.state,\n            trends=trends,",
)
replace_once(
    "tools/ml/climate_dagger.py",
    "        simulator.step(safety.action, add_sensor_noise=False, light_level=profile.light_level)",
    "        simulator.step(safety.action, add_sensor_noise=False, light_level=profile.light_level)\n        effective_estimator.update(simulator.scenario, safety.action)",
)

# CO2 diagnostic: keep estimated state aligned with applied commands for ML encoder calls.
replace_once(
    "tools/ml/climate_co2_audit.py",
    "    ClimateInputConfig,\n    ClimateTrendEstimator,",
    "    ClimateEffectiveActionEstimator,\n    ClimateInputConfig,\n    ClimateTrendEstimator,",
)
replace_once(
    "tools/ml/climate_co2_audit.py",
    "    model: ClimatePortableModel,\n    trends: ClimateTrendEstimator,\n) -> tuple[ClimateAction, ClimateAction, dict[str, MeasurementStatus]]:",
    "    model: ClimatePortableModel,\n    trends: ClimateTrendEstimator,\n    effective: ClimateEffectiveActionEstimator,\n) -> tuple[ClimateAction, ClimateAction, dict[str, MeasurementStatus]]:",
)
replace_once(
    "tools/ml/climate_co2_audit.py",
    "        previous=simulator.previous_command,\n        trends=trend_values,",
    "        previous=simulator.previous_command,\n        estimated_effective=effective.state,\n        trends=trend_values,",
)
replace_once(
    "tools/ml/climate_co2_audit.py",
    "    model: ClimatePortableModel | None,\n    trends: ClimateTrendEstimator,\n) -> tuple[ClimateAction, ClimateAction, dict[str, MeasurementStatus]]:",
    "    model: ClimatePortableModel | None,\n    trends: ClimateTrendEstimator,\n    effective: ClimateEffectiveActionEstimator,\n) -> tuple[ClimateAction, ClimateAction, dict[str, MeasurementStatus]]:",
)
replace_once(
    "tools/ml/climate_co2_audit.py",
    "        return _ml_actions(simulator, episode, step, config, model, trends)",
    "        return _ml_actions(simulator, episode, step, config, model, trends, effective)",
)
replace_once(
    "tools/ml/climate_co2_audit.py",
    "    trends = ClimateTrendEstimator()\n    co2_abs_sum = 0.0",
    "    trends = ClimateTrendEstimator()\n    effective = ClimateEffectiveActionEstimator()\n    co2_abs_sum = 0.0",
)
replace_once(
    "tools/ml/climate_co2_audit.py",
    "            model,\n            trends,\n        )",
    "            model,\n            trends,\n            effective,\n        )",
)
replace_once(
    "tools/ml/climate_co2_audit.py",
    "        next_state = simulator.step(\n            applied,\n            add_sensor_noise=False,\n            light_level=profile.light_level,\n        )",
    "        next_state = simulator.step(\n            applied,\n            add_sensor_noise=False,\n            light_level=profile.light_level,\n        )\n        effective.update(simulator.scenario, applied)",
)

# Regression benchmark must use a dedicated Stage 13 compatibility artifact, not relabel the historical model.
replace_once(
    "tests/test_climate_benchmark.py",
    'WEIGHTS = ROOT / "reports" / "ml" / "climate_v6_model_seed1847.npz"\nMETADATA = ROOT / "reports" / "ml" / "climate_v6_model_seed1847.json"',
    'WEIGHTS = ROOT / "reports" / "ml" / "climate_v6_model_stage13_compat.npz"\nMETADATA = ROOT / "reports" / "ml" / "climate_v6_model_stage13_compat.json"',
)

migration_tool = r'''"""Create a behavior-preserving 44-input compatibility artifact for Stage 13.

This is not retraining. The six new estimated-effective inputs receive zero first-layer
weights, while all historical weights and biases are preserved exactly. The artifact is
therefore only a regression compatibility baseline; later Stage 13 ablation must train a
model that can actually use the new observability features.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from .climate_input import CLIMATE_V6_CONTRACT_PATH
from .climate_model_artifact import ClimateModelMetadata, ClimatePortableModel, save_portable_model
from .contract import load_contract

SOURCE_WEIGHTS = Path("reports/ml/climate_v6_model_seed1847.npz")
SOURCE_METADATA = Path("reports/ml/climate_v6_model_seed1847.json")
DEST_WEIGHTS = Path("reports/ml/climate_v6_model_stage13_compat.npz")
DEST_METADATA = Path("reports/ml/climate_v6_model_stage13_compat.json")
INSERT_AT = 32
INSERTED_FEATURES = (
    "estimated_effective_heater",
    "estimated_effective_cooler",
    "estimated_effective_exhaust_fan",
    "estimated_effective_humidifier",
    "estimated_effective_dehumidifier",
    "estimated_effective_co2_doser",
)


def _old_predict(features: np.ndarray, weights: tuple[np.ndarray, ...]) -> np.ndarray:
    w1, b1, w2, b2, w3, b3 = weights
    h1 = np.maximum(features @ w1 + b1, np.float32(0.0))
    h2 = np.maximum(h1 @ w2 + b2, np.float32(0.0))
    logits = np.clip(h2 @ w3 + b3, np.float32(-60.0), np.float32(60.0))
    return np.asarray(np.float32(1.0) / (np.float32(1.0) + np.exp(-logits)), dtype=np.float32)


def main() -> None:
    contract = load_contract(CLIMATE_V6_CONTRACT_PATH)
    if len(contract.feature_names) != 44:
        raise ValueError("Stage 13 compatibility migration requires a 44-feature contract")
    if tuple(contract.feature_names[INSERT_AT : INSERT_AT + 6]) != INSERTED_FEATURES:
        raise ValueError("Stage 13 estimated-effective feature order is unexpected")

    source_payload = json.loads(SOURCE_METADATA.read_text(encoding="utf-8"))
    old_names = tuple(str(value) for value in source_payload["feature_names"])
    expected_old_names = tuple(contract.feature_names[:INSERT_AT] + contract.feature_names[INSERT_AT + 6 :])
    if old_names != expected_old_names:
        raise ValueError("historical regression artifact feature order does not match the Stage 13 base contract")
    if tuple(str(value) for value in source_payload["output_names"]) != contract.outputs:
        raise ValueError("historical regression artifact output order does not match the active contract")

    with np.load(SOURCE_WEIGHTS, allow_pickle=False) as archive:
        old_weights = tuple(
            np.asarray(archive[key], dtype=np.float32)
            for key in ("w1", "b1", "w2", "b2", "w3", "b3")
        )
    old_w1 = old_weights[0]
    if old_w1.ndim != 2 or old_w1.shape[0] != 38:
        raise ValueError(f"historical first-layer shape is {old_w1.shape}, expected (38, H1)")
    zeros = np.zeros((6, old_w1.shape[1]), dtype=np.float32)
    new_w1 = np.concatenate((old_w1[:INSERT_AT], zeros, old_w1[INSERT_AT:]), axis=0)
    new_weights = (new_w1, *old_weights[1:])

    metadata = ClimateModelMetadata(
        schema_version=contract.schema_version,
        contract_hash=contract.hash_hex,
        feature_names=contract.feature_names,
        output_names=contract.outputs,
        training_seed=int(source_payload["training_seed"]),
        candidate_name=str(source_payload["candidate_name"]) + "_stage13_zero_effective_compat",
        source_commit=str(source_payload["source_commit"]),
    )
    model = ClimatePortableModel(metadata=metadata, weights=new_weights)

    rng = np.random.default_rng(13_044)
    old_features = rng.uniform(0.0, 1.0, size=(128, 38)).astype(np.float32)
    new_features = np.concatenate(
        (
            old_features[:, :INSERT_AT],
            np.zeros((len(old_features), 6), dtype=np.float32),
            old_features[:, INSERT_AT:],
        ),
        axis=1,
    )
    old_prediction = _old_predict(old_features, old_weights)
    new_prediction = model.predict(new_features)
    max_delta = float(np.max(np.abs(old_prediction.astype(np.float64) - new_prediction.astype(np.float64))))
    if max_delta > 2.0e-6:
        raise AssertionError(f"Stage 13 compatibility migration changed predictions by {max_delta:.9g}")

    save_portable_model(model, DEST_WEIGHTS, DEST_METADATA)
    payload = json.loads(DEST_METADATA.read_text(encoding="utf-8"))
    payload["migration"] = {
        "kind": "stage13_zero_weight_input_expansion",
        "source_weights_file": SOURCE_WEIGHTS.name,
        "source_metadata_file": SOURCE_METADATA.name,
        "inserted_feature_names": list(INSERTED_FEATURES),
        "inserted_first_layer_weights": "all_zero",
        "prediction_max_delta": max_delta,
        "trained_on_new_features": False,
    }
    DEST_METADATA.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"STAGE13_COMPAT_PARAMETER_COUNT={model.parameter_count}")
    print(f"STAGE13_COMPAT_MAX_DELTA={max_delta:.9g}")
    print("STAGE13_COMPAT_ARTIFACT=PASS")


if __name__ == "__main__":
    main()
'''
(ROOT / "tools/ml/migrate_climate_v6_stage13_compat.py").write_text(migration_tool, encoding="utf-8")

compat_test = r'''from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from tools.ml.climate_input import CLIMATE_V6_CONTRACT_PATH
from tools.ml.climate_model_artifact import load_portable_model
from tools.ml.contract import load_contract

ROOT = Path(__file__).resolve().parents[1]
WEIGHTS = ROOT / "reports" / "ml" / "climate_v6_model_stage13_compat.npz"
METADATA = ROOT / "reports" / "ml" / "climate_v6_model_stage13_compat.json"
OLD_WEIGHTS = ROOT / "reports" / "ml" / "climate_v6_model_seed1847.npz"


def test_stage13_compat_artifact_preserves_historical_weights_and_zeros_new_inputs() -> None:
    contract = load_contract(CLIMATE_V6_CONTRACT_PATH)
    model = load_portable_model(WEIGHTS, METADATA)
    assert model.metadata.contract_hash == contract.hash_hex
    assert model.metadata.feature_names == contract.feature_names
    assert model.weights[0].shape == (44, 32)
    np.testing.assert_array_equal(model.weights[0][32:38], np.zeros((6, 32), dtype=np.float32))

    with np.load(OLD_WEIGHTS, allow_pickle=False) as old:
        np.testing.assert_array_equal(model.weights[0][:32], old["w1"][:32])
        np.testing.assert_array_equal(model.weights[0][38:], old["w1"][32:])
        np.testing.assert_array_equal(model.weights[1], old["b1"])
        np.testing.assert_array_equal(model.weights[2], old["w2"])
        np.testing.assert_array_equal(model.weights[3], old["b2"])
        np.testing.assert_array_equal(model.weights[4], old["w3"])
        np.testing.assert_array_equal(model.weights[5], old["b3"])

    payload = json.loads(METADATA.read_text(encoding="utf-8"))
    migration = payload["migration"]
    assert migration["kind"] == "stage13_zero_weight_input_expansion"
    assert migration["inserted_first_layer_weights"] == "all_zero"
    assert migration["trained_on_new_features"] is False
    assert float(migration["prediction_max_delta"]) <= 2.0e-6
'''
(ROOT / "tests/test_climate_stage13_compat.py").write_text(compat_test, encoding="utf-8")

print("Stage 13 runtime wiring and compatibility migration sources applied")
