from __future__ import annotations

import numpy as np

from tools.ml.climate_simulator import CLIMATE_OUTPUT_NAMES
from tools.ml.climate_training import (
    CandidateSpec,
    ClimateTrainingConfig,
    build_climate_model,
    compare_candidates,
    prediction_metrics,
)
from tools.ml.dataset import Dataset


def _tiny_dataset() -> Dataset:
    rng = np.random.default_rng(17)
    rows = 18
    features = rng.uniform(0.0, 1.0, size=(rows, 38)).astype(np.float32)
    labels = np.zeros((rows, 6), dtype=np.float32)
    for row in range(rows):
        labels[row, row % 6] = 0.75
        labels[row, (row + 2) % 6] = 0.25
    scenario_ids = np.asarray([f"scenario-{row:02d}" for row in range(rows)])
    splits = np.asarray(["train"] * 10 + ["validation"] * 4 + ["test"] * 4)
    return Dataset(
        features=features,
        labels=labels,
        scenario_ids=scenario_ids,
        scenario_seeds=np.arange(rows, dtype=np.int64),
        splits=splits,
        feature_names=tuple(f"feature_{index}" for index in range(38)),
        output_names=CLIMATE_OUTPUT_NAMES,
    )


def test_climate_model_is_fixed_small_38_32_32_6_mlp() -> None:
    model = build_climate_model(config=ClimateTrainingConfig.quick(seed=9))
    dense_layers = [layer for layer in model.layers if layer.__class__.__name__ == "Dense"]
    assert [layer.units for layer in dense_layers] == [32, 32, 6]
    assert [layer.activation.__name__ for layer in dense_layers] == ["relu", "relu", "sigmoid"]
    assert model.input_shape == (None, 38)
    assert model.count_params() == 2502


def test_balanced_mae_penalizes_always_off_for_active_labels() -> None:
    expected = np.zeros((12, 6), dtype=np.float32)
    for output in range(6):
        expected[output : output + 3, output] = 1.0
    predicted = np.zeros_like(expected)
    metrics = prediction_metrics(expected, predicted, activity_threshold=0.05)
    assert metrics.mae < metrics.balanced_mae
    assert metrics.macro_recall == 0.0
    assert metrics.balanced_mae > 0.45


def test_candidate_selection_uses_validation_and_only_winner_gets_test_metrics() -> None:
    dataset = _tiny_dataset()
    config = ClimateTrainingConfig(seed=23, epochs=1, batch_size=8)
    candidates = (
        CandidateSpec("adam_mse", "adam", "mse", 0.001),
        CandidateSpec("sgd_mse", "sgd", "mse", 0.01),
    )
    comparison = compare_candidates(dataset, config=config, candidates=candidates)
    assert comparison.winner.test is not None
    assert sum(result.test is not None for result in comparison.candidates) == 1
    validation_scores = [result.validation.balanced_mae for result in comparison.candidates]
    assert comparison.winner_index == min(
        range(len(validation_scores)), key=lambda index: validation_scores[index]
    )


def test_scenario_leakage_is_rejected_before_training() -> None:
    dataset = _tiny_dataset()
    leaking_splits = dataset.splits.copy()
    leaking_ids = dataset.scenario_ids.copy()
    leaking_ids[-1] = leaking_ids[0]
    leaking = Dataset(
        features=dataset.features,
        labels=dataset.labels,
        scenario_ids=leaking_ids,
        scenario_seeds=dataset.scenario_seeds,
        splits=leaking_splits,
        feature_names=dataset.feature_names,
        output_names=dataset.output_names,
    )
    candidates = (CandidateSpec("adam_mse", "adam", "mse", 0.001),)
    try:
        compare_candidates(
            leaking,
            config=ClimateTrainingConfig(seed=2, epochs=1, batch_size=8),
            candidates=candidates,
        )
    except ValueError as exc:
        assert "scenario leakage" in str(exc)
    else:
        raise AssertionError("scenario leakage must be rejected")
