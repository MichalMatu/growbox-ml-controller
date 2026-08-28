from __future__ import annotations

import numpy as np
import pytest

from tools.ml.climate_simulator import CLIMATE_OUTPUT_NAMES
from tools.ml.climate_training_weighted import (
    WeightedCandidateSpec,
    WeightedTrainingConfig,
    compare_weighted_candidates,
    control_prediction_metrics,
    label_loss_weights,
)
from tools.ml.dataset import Dataset


def _dataset() -> Dataset:
    rng = np.random.default_rng(117)
    rows = 30
    features = rng.uniform(0.0, 1.0, size=(rows, 44)).astype(np.float32)
    labels = np.zeros((rows, 6), dtype=np.float32)
    for row in range(rows):
        labels[row, row % 6] = 0.80
        labels[row, (row + 2) % 6] = 0.20
    return Dataset(
        features=features,
        labels=labels,
        scenario_ids=np.asarray([f"weighted-{row:02d}" for row in range(rows)]),
        scenario_seeds=np.arange(rows, dtype=np.int64),
        splits=np.asarray(["train"] * 18 + ["validation"] * 6 + ["test"] * 6),
        feature_names=tuple(f"feature_{index}" for index in range(44)),
        output_names=CLIMATE_OUTPUT_NAMES,
    )


def test_label_weights_prioritize_active_and_strong_targets() -> None:
    config = WeightedTrainingConfig.quick(seed=3)
    labels = np.asarray([[0.0, 0.05, 0.051, 0.30, 0.301, 1.0]], dtype=np.float32)
    weights = label_loss_weights(labels, config)
    np.testing.assert_array_equal(
        weights,
        np.asarray([[1.0, 1.0, 2.0, 2.0, 5.0, 5.0]], dtype=np.float32),
    )


def test_control_metrics_expose_strong_command_collapse() -> None:
    config = WeightedTrainingConfig.quick(seed=4)
    expected = np.zeros((60, 6), dtype=np.float32)
    for output in range(6):
        expected[output, output] = 1.0
        expected[output + 6, output] = 0.20
    metrics = control_prediction_metrics(expected, np.zeros_like(expected), config=config)
    assert metrics.mae < metrics.control_mae
    assert metrics.strong_mae == pytest.approx(1.0)
    assert metrics.strong_recall == 0.0


def test_validation_selects_winner_before_test_evaluation() -> None:
    dataset = _dataset()
    config = WeightedTrainingConfig(seed=23, epochs=1, batch_size=8)
    candidates = (
        WeightedCandidateSpec("baseline", "adam", "huber", 0.001, "none"),
        WeightedCandidateSpec("weighted", "adam", "huber", 0.001, "control"),
    )
    comparison = compare_weighted_candidates(dataset, config=config, candidates=candidates)
    assert comparison.winner.test is not None
    assert sum(result.test is not None for result in comparison.candidates) == 1
    expected_index = min(
        range(len(comparison.candidates)),
        key=lambda index: (
            comparison.candidates[index].validation.control_mae,
            comparison.candidates[index].validation.strong_mae,
            comparison.candidates[index].validation.balanced_mae,
            -comparison.candidates[index].validation.strong_recall,
            -comparison.candidates[index].validation.macro_f1,
            comparison.candidates[index].validation.mae,
            comparison.candidates[index].spec.name,
        ),
    )
    assert comparison.winner_index == expected_index


def test_invalid_weight_configuration_is_rejected() -> None:
    with pytest.raises(ValueError):
        WeightedTrainingConfig(activity_threshold=0.4, strong_threshold=0.3)
    with pytest.raises(ValueError):
        WeightedTrainingConfig(active_loss_weight=0.9)
    with pytest.raises(ValueError):
        WeightedTrainingConfig(active_loss_weight=3.0, strong_loss_weight=2.0)
