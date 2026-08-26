"""Deterministic climate-v6 MLP training and candidate comparison.

This module is deliberately separate from the legacy trainer.  It consumes the
38 -> 6 climate-v6 dataset, keeps scenario-level splits intact, shuffles rows
deterministically inside the training split, selects candidates using validation
only, and evaluates the test split only after a winner is frozen.
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass
from typing import Any, Literal

import numpy as np

from .climate_simulator import CLIMATE_OUTPUT_NAMES
from .dataset import Dataset

OptimizerName = Literal["adam", "sgd"]
LossName = Literal["huber", "mse"]


@dataclass(frozen=True)
class ClimateTrainingConfig:
    seed: int = 1847
    epochs: int = 28
    batch_size: int = 64
    hidden_units: int = 32
    activity_threshold: float = 0.05

    @classmethod
    def quick(cls, seed: int = 1847) -> ClimateTrainingConfig:
        return cls(seed=seed, epochs=6, batch_size=32)

    @classmethod
    def full(cls, seed: int = 1847) -> ClimateTrainingConfig:
        return cls(seed=seed, epochs=28, batch_size=64)


@dataclass(frozen=True)
class CandidateSpec:
    name: str
    optimizer: OptimizerName
    loss: LossName
    learning_rate: float


DEFAULT_CANDIDATES: tuple[CandidateSpec, ...] = (
    CandidateSpec("adam_huber", "adam", "huber", 0.0010),
    CandidateSpec("adam_mse", "adam", "mse", 0.0010),
    CandidateSpec("sgd_huber", "sgd", "huber", 0.0200),
    CandidateSpec("sgd_mse", "sgd", "mse", 0.0200),
)


@dataclass(frozen=True)
class SplitMetrics:
    mae: float
    rmse: float
    balanced_mae: float
    macro_precision: float
    macro_recall: float
    macro_f1: float
    per_output: dict[str, dict[str, float]]


@dataclass
class CandidateResult:
    spec: CandidateSpec
    model: Any
    validation: SplitMetrics
    history: dict[str, list[float]]
    test: SplitMetrics | None = None


@dataclass
class ClimateTrainingComparison:
    candidates: tuple[CandidateResult, ...]
    winner_index: int

    @property
    def winner(self) -> CandidateResult:
        return self.candidates[self.winner_index]


def configure_tensorflow_determinism(seed: int) -> Any:
    os.environ["TF_DETERMINISTIC_OPS"] = "1"
    os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
    os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")
    import tensorflow as tf

    tf.keras.utils.set_random_seed(seed)
    tf.config.experimental.enable_op_determinism()
    try:
        tf.config.threading.set_inter_op_parallelism_threads(1)
        tf.config.threading.set_intra_op_parallelism_threads(1)
    except RuntimeError:
        pass
    return tf


def _assert_climate_dataset(dataset: Dataset) -> None:
    if dataset.features.ndim != 2 or dataset.features.shape[1] != 38:
        raise ValueError("climate-v6 training requires exactly 38 features")
    if dataset.labels.ndim != 2 or dataset.labels.shape[1] != 6:
        raise ValueError("climate-v6 training requires exactly 6 outputs")
    if dataset.output_names != CLIMATE_OUTPUT_NAMES:
        raise ValueError("dataset output order does not match climate-v6")
    if len(set(dataset.feature_names)) != 38:
        raise ValueError("climate-v6 feature names must be unique")
    if not np.isfinite(dataset.features).all() or not np.isfinite(dataset.labels).all():
        raise ValueError("training dataset contains NaN/Inf")

    split_by_scenario: dict[str, set[str]] = {}
    for scenario_id, split in zip(dataset.scenario_ids, dataset.splits, strict=True):
        split_by_scenario.setdefault(str(scenario_id), set()).add(str(split))
    leaking = sorted(name for name, splits in split_by_scenario.items() if len(splits) != 1)
    if leaking:
        raise ValueError("scenario leakage across dataset splits: " + ", ".join(leaking[:5]))
    for split in ("train", "validation", "test"):
        if not np.any(dataset.splits == split):
            raise ValueError(f"dataset split {split!r} is empty")


def build_climate_model(*, config: ClimateTrainingConfig) -> Any:
    tf = configure_tensorflow_determinism(config.seed)
    keras = tf.keras
    model = keras.Sequential(
        [
            keras.layers.Input(shape=(38,), name="climate_v6_features"),
            keras.layers.Dense(
                config.hidden_units,
                activation="relu",
                kernel_initializer=keras.initializers.GlorotUniform(seed=config.seed + 1),
                bias_initializer="zeros",
                name="hidden_1",
            ),
            keras.layers.Dense(
                config.hidden_units,
                activation="relu",
                kernel_initializer=keras.initializers.GlorotUniform(seed=config.seed + 2),
                bias_initializer="zeros",
                name="hidden_2",
            ),
            keras.layers.Dense(
                6,
                activation="sigmoid",
                kernel_initializer=keras.initializers.GlorotUniform(seed=config.seed + 3),
                bias_initializer="zeros",
                name="climate_requests",
            ),
        ],
        name="growbox_climate_v6_controller",
    )
    if model.count_params() != 2502:
        raise AssertionError(f"unexpected climate-v6 parameter count: {model.count_params()}")
    return model


def _binary_metrics(expected_active: np.ndarray, predicted_active: np.ndarray) -> tuple[float, float, float]:
    tp = int(np.sum(expected_active & predicted_active))
    fp = int(np.sum(~expected_active & predicted_active))
    fn = int(np.sum(expected_active & ~predicted_active))
    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    f1 = 2.0 * precision * recall / (precision + recall) if precision + recall else 0.0
    return float(precision), float(recall), float(f1)


def prediction_metrics(
    expected: np.ndarray,
    predicted: np.ndarray,
    *,
    activity_threshold: float,
) -> SplitMetrics:
    expected = np.asarray(expected, dtype=np.float64)
    predicted = np.asarray(predicted, dtype=np.float64)
    if expected.shape != predicted.shape or expected.ndim != 2 or expected.shape[1] != 6:
        raise ValueError("prediction and climate-v6 label shapes do not match")
    if len(expected) == 0:
        raise ValueError("cannot evaluate an empty split")
    if not np.isfinite(predicted).all():
        raise ValueError("predictions contain NaN/Inf")

    errors = predicted - expected
    per_output: dict[str, dict[str, float]] = {}
    balanced_values: list[float] = []
    precisions: list[float] = []
    recalls: list[float] = []
    f1_values: list[float] = []

    for index, name in enumerate(CLIMATE_OUTPUT_NAMES):
        absolute = np.abs(errors[:, index])
        active = expected[:, index] > activity_threshold
        inactive = ~active
        active_mae = float(np.mean(absolute[active])) if np.any(active) else float(np.mean(absolute))
        inactive_mae = (
            float(np.mean(absolute[inactive])) if np.any(inactive) else float(np.mean(absolute))
        )
        balanced = 0.5 * (active_mae + inactive_mae)
        precision, recall, f1 = _binary_metrics(
            active, predicted[:, index] > activity_threshold
        )
        balanced_values.append(balanced)
        precisions.append(precision)
        recalls.append(recall)
        f1_values.append(f1)
        per_output[name] = {
            "mae": float(np.mean(absolute)),
            "rmse": float(np.sqrt(np.mean(np.square(errors[:, index])))),
            "active_mae": active_mae,
            "inactive_mae": inactive_mae,
            "balanced_mae": balanced,
            "precision": precision,
            "recall": recall,
            "f1": f1,
        }

    return SplitMetrics(
        mae=float(np.mean(np.abs(errors))),
        rmse=float(np.sqrt(np.mean(np.square(errors)))),
        balanced_mae=float(np.mean(balanced_values)),
        macro_precision=float(np.mean(precisions)),
        macro_recall=float(np.mean(recalls)),
        macro_f1=float(np.mean(f1_values)),
        per_output=per_output,
    )


def _optimizer(tf: Any, spec: CandidateSpec) -> Any:
    if spec.optimizer == "adam":
        return tf.keras.optimizers.Adam(learning_rate=spec.learning_rate)
    if spec.optimizer == "sgd":
        return tf.keras.optimizers.SGD(
            learning_rate=spec.learning_rate,
            momentum=0.9,
            nesterov=False,
        )
    raise ValueError(f"unsupported optimizer {spec.optimizer!r}")


def _loss(tf: Any, spec: CandidateSpec) -> Any:
    if spec.loss == "huber":
        return tf.keras.losses.Huber(delta=0.15)
    if spec.loss == "mse":
        return tf.keras.losses.MeanSquaredError()
    raise ValueError(f"unsupported loss {spec.loss!r}")


def _predict(model: Any, features: np.ndarray) -> np.ndarray:
    return np.asarray(model(features, training=False), dtype=np.float32)


def train_candidate(
    dataset: Dataset,
    spec: CandidateSpec,
    *,
    config: ClimateTrainingConfig,
) -> CandidateResult:
    _assert_climate_dataset(dataset)
    x_train, y_train = dataset.select("train")
    x_validation, y_validation = dataset.select("validation")

    tf = configure_tensorflow_determinism(config.seed)
    tf.keras.backend.clear_session()
    model = build_climate_model(config=config)
    model.compile(optimizer=_optimizer(tf, spec), loss=_loss(tf, spec))

    history: dict[str, list[float]] = {"train_loss": [], "validation_balanced_mae": []}
    batch_size = min(config.batch_size, len(x_train))
    rng = np.random.default_rng(config.seed)

    for _epoch in range(config.epochs):
        order = rng.permutation(len(x_train))
        epoch_losses: list[float] = []
        for start in range(0, len(order), batch_size):
            indices = order[start : start + batch_size]
            loss = model.train_on_batch(x_train[indices], y_train[indices])
            epoch_losses.append(float(np.asarray(loss).reshape(-1)[0]))
        validation_prediction = _predict(model, x_validation)
        validation_metrics = prediction_metrics(
            y_validation,
            validation_prediction,
            activity_threshold=config.activity_threshold,
        )
        history["train_loss"].append(float(np.mean(epoch_losses)))
        history["validation_balanced_mae"].append(validation_metrics.balanced_mae)

    validation_prediction = _predict(model, x_validation)
    validation = prediction_metrics(
        y_validation,
        validation_prediction,
        activity_threshold=config.activity_threshold,
    )
    return CandidateResult(spec=spec, model=model, validation=validation, history=history)


def compare_candidates(
    dataset: Dataset,
    *,
    config: ClimateTrainingConfig | None = None,
    candidates: tuple[CandidateSpec, ...] = DEFAULT_CANDIDATES,
) -> ClimateTrainingComparison:
    config = config or ClimateTrainingConfig.full()
    _assert_climate_dataset(dataset)
    if not candidates:
        raise ValueError("at least one training candidate is required")
    if len({candidate.name for candidate in candidates}) != len(candidates):
        raise ValueError("candidate names must be unique")

    results = tuple(train_candidate(dataset, spec, config=config) for spec in candidates)
    winner_index = min(
        range(len(results)),
        key=lambda index: (
            results[index].validation.balanced_mae,
            -results[index].validation.macro_f1,
            results[index].validation.mae,
            results[index].spec.name,
        ),
    )

    # Test data remains untouched until the winner has been selected from validation metrics.
    x_test, y_test = dataset.select("test")
    winner = results[winner_index]
    winner.test = prediction_metrics(
        y_test,
        _predict(winner.model, x_test),
        activity_threshold=config.activity_threshold,
    )
    return ClimateTrainingComparison(candidates=results, winner_index=winner_index)


def comparison_summary(comparison: ClimateTrainingComparison) -> tuple[str, ...]:
    lines: list[str] = []
    for result in comparison.candidates:
        validation = result.validation
        lines.append(
            f"{result.spec.name}: val_balanced_mae={validation.balanced_mae:.6f} "
            f"val_mae={validation.mae:.6f} val_rmse={validation.rmse:.6f} "
            f"val_f1={validation.macro_f1:.4f}"
        )
    winner = comparison.winner
    if winner.test is None:
        raise AssertionError("winner test metrics are missing")
    lines.append(f"winner={winner.spec.name}")
    lines.append(
        f"test_balanced_mae={winner.test.balanced_mae:.6f} "
        f"test_mae={winner.test.mae:.6f} test_rmse={winner.test.rmse:.6f} "
        f"test_f1={winner.test.macro_f1:.4f}"
    )
    return tuple(lines)


__all__ = [
    "CandidateResult",
    "CandidateSpec",
    "ClimateTrainingComparison",
    "ClimateTrainingConfig",
    "DEFAULT_CANDIDATES",
    "SplitMetrics",
    "build_climate_model",
    "compare_candidates",
    "comparison_summary",
    "configure_tensorflow_determinism",
    "prediction_metrics",
    "train_candidate",
]
