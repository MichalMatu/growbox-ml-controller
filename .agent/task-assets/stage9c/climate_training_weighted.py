"""Stage 9C weighted climate-v6 training.

This module leaves the original Stage 7 trainer intact and adds a controlled
training path that explicitly upweights active and strong actuator requests.
Candidate selection remains validation-only; the test split is evaluated once,
after the winner is frozen.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Literal

import numpy as np

from .climate_simulator import CLIMATE_OUTPUT_NAMES
from .climate_training import ClimateTrainingConfig, build_climate_model, configure_tensorflow_determinism
from .dataset import Dataset

OptimizerName = Literal["adam", "sgd"]
LossName = Literal["huber", "mse"]
WeightingMode = Literal["none", "control"]


@dataclass(frozen=True)
class WeightedTrainingConfig:
    seed: int = 1847
    epochs: int = 28
    batch_size: int = 64
    hidden_units: int = 32
    activity_threshold: float = 0.05
    strong_threshold: float = 0.30
    active_loss_weight: float = 2.0
    strong_loss_weight: float = 5.0

    def __post_init__(self) -> None:
        if self.epochs <= 0 or self.batch_size <= 0 or self.hidden_units <= 0:
            raise ValueError("epochs, batch_size and hidden_units must be positive")
        if not 0.0 <= self.activity_threshold < self.strong_threshold <= 1.0:
            raise ValueError("expected 0 <= activity_threshold < strong_threshold <= 1")
        if self.active_loss_weight < 1.0:
            raise ValueError("active_loss_weight must be >= 1")
        if self.strong_loss_weight < self.active_loss_weight:
            raise ValueError("strong_loss_weight must be >= active_loss_weight")

    @classmethod
    def quick(cls, seed: int = 1847) -> "WeightedTrainingConfig":
        return cls(seed=seed, epochs=3, batch_size=32)

    @classmethod
    def full(cls, seed: int = 1847) -> "WeightedTrainingConfig":
        return cls(seed=seed, epochs=28, batch_size=64)

    def base_model_config(self) -> ClimateTrainingConfig:
        return ClimateTrainingConfig(
            seed=self.seed,
            epochs=self.epochs,
            batch_size=self.batch_size,
            hidden_units=self.hidden_units,
            activity_threshold=self.activity_threshold,
        )


@dataclass(frozen=True)
class WeightedCandidateSpec:
    name: str
    optimizer: OptimizerName
    loss: LossName
    learning_rate: float
    weighting: WeightingMode


DEFAULT_WEIGHTED_CANDIDATES: tuple[WeightedCandidateSpec, ...] = (
    WeightedCandidateSpec("adam_huber_baseline", "adam", "huber", 0.0010, "none"),
    WeightedCandidateSpec("adam_weighted_huber", "adam", "huber", 0.0010, "control"),
    WeightedCandidateSpec("adam_weighted_mse", "adam", "mse", 0.0010, "control"),
    WeightedCandidateSpec("sgd_weighted_huber", "sgd", "huber", 0.0200, "control"),
    WeightedCandidateSpec("sgd_weighted_mse", "sgd", "mse", 0.0200, "control"),
)


@dataclass(frozen=True)
class ControlSplitMetrics:
    mae: float
    rmse: float
    balanced_mae: float
    control_mae: float
    strong_mae: float
    macro_precision: float
    macro_recall: float
    macro_f1: float
    strong_recall: float
    per_output: dict[str, dict[str, float | int]]


@dataclass
class WeightedCandidateResult:
    spec: WeightedCandidateSpec
    model: Any
    validation: ControlSplitMetrics
    history: dict[str, list[float]]
    test: ControlSplitMetrics | None = None


@dataclass
class WeightedTrainingComparison:
    candidates: tuple[WeightedCandidateResult, ...]
    winner_index: int

    @property
    def winner(self) -> WeightedCandidateResult:
        return self.candidates[self.winner_index]


def _assert_dataset(dataset: Dataset) -> None:
    if dataset.features.ndim != 2 or dataset.features.shape[1] != 38:
        raise ValueError("weighted climate-v6 training requires exactly 38 features")
    if dataset.labels.ndim != 2 or dataset.labels.shape[1] != 6:
        raise ValueError("weighted climate-v6 training requires exactly 6 outputs")
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


def label_loss_weights(labels: np.ndarray, config: WeightedTrainingConfig) -> np.ndarray:
    values = np.asarray(labels, dtype=np.float32)
    if not np.isfinite(values).all():
        raise ValueError("labels contain NaN/Inf")
    weights = np.ones_like(values, dtype=np.float32)
    weights = np.where(values > config.activity_threshold, config.active_loss_weight, weights)
    weights = np.where(values > config.strong_threshold, config.strong_loss_weight, weights)
    return np.asarray(weights, dtype=np.float32)


def _binary_metrics(
    expected_active: np.ndarray, predicted_active: np.ndarray
) -> tuple[float, float, float]:
    tp = int(np.sum(expected_active & predicted_active))
    fp = int(np.sum(~expected_active & predicted_active))
    fn = int(np.sum(expected_active & ~predicted_active))
    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    f1 = 2.0 * precision * recall / (precision + recall) if precision + recall else 0.0
    return float(precision), float(recall), float(f1)


def control_prediction_metrics(
    expected: np.ndarray,
    predicted: np.ndarray,
    *,
    config: WeightedTrainingConfig,
) -> ControlSplitMetrics:
    expected = np.asarray(expected, dtype=np.float64)
    predicted = np.asarray(predicted, dtype=np.float64)
    if expected.shape != predicted.shape or expected.ndim != 2 or expected.shape[1] != 6:
        raise ValueError("prediction and climate-v6 label shapes do not match")
    if len(expected) == 0:
        raise ValueError("cannot evaluate an empty split")
    if not np.isfinite(expected).all() or not np.isfinite(predicted).all():
        raise ValueError("expected/predicted values contain NaN/Inf")

    errors = predicted - expected
    per_output: dict[str, dict[str, float | int]] = {}
    balanced_values: list[float] = []
    control_values: list[float] = []
    strong_mae_values: list[float] = []
    precisions: list[float] = []
    recalls: list[float] = []
    f1_values: list[float] = []
    strong_recall_values: list[float] = []

    for index, name in enumerate(CLIMATE_OUTPUT_NAMES):
        absolute = np.abs(errors[:, index])
        labels = expected[:, index]
        predictions = predicted[:, index]
        active = labels > config.activity_threshold
        inactive = ~active
        strong = labels > config.strong_threshold
        moderate = active & ~strong

        active_mae = float(np.mean(absolute[active])) if np.any(active) else 0.0
        inactive_mae = float(np.mean(absolute[inactive])) if np.any(inactive) else 0.0
        if np.any(active) and np.any(inactive):
            balanced = 0.5 * (active_mae + inactive_mae)
        elif np.any(active):
            balanced = active_mae
        else:
            balanced = inactive_mae

        strata_mae: list[float] = []
        for mask in (inactive, moderate, strong):
            if np.any(mask):
                strata_mae.append(float(np.mean(absolute[mask])))
        control_mae = float(np.mean(strata_mae)) if strata_mae else 0.0

        strong_count = int(np.sum(strong))
        strong_mae = float(np.mean(absolute[strong])) if strong_count else 0.0
        strong_recall = (
            float(np.mean(predictions[strong] > config.strong_threshold)) if strong_count else 1.0
        )
        precision, recall, f1 = _binary_metrics(
            active,
            predictions > config.activity_threshold,
        )

        balanced_values.append(balanced)
        control_values.append(control_mae)
        precisions.append(precision)
        recalls.append(recall)
        f1_values.append(f1)
        if strong_count:
            strong_mae_values.append(strong_mae)
            strong_recall_values.append(strong_recall)
        per_output[name] = {
            "mae": float(np.mean(absolute)),
            "rmse": float(np.sqrt(np.mean(np.square(errors[:, index])))),
            "active_mae": active_mae,
            "inactive_mae": inactive_mae,
            "balanced_mae": balanced,
            "control_mae": control_mae,
            "strong_count": strong_count,
            "strong_mae": strong_mae,
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "strong_recall": strong_recall,
        }

    return ControlSplitMetrics(
        mae=float(np.mean(np.abs(errors))),
        rmse=float(np.sqrt(np.mean(np.square(errors)))),
        balanced_mae=float(np.mean(balanced_values)),
        control_mae=float(np.mean(control_values)),
        strong_mae=float(np.mean(strong_mae_values)) if strong_mae_values else 0.0,
        macro_precision=float(np.mean(precisions)),
        macro_recall=float(np.mean(recalls)),
        macro_f1=float(np.mean(f1_values)),
        strong_recall=float(np.mean(strong_recall_values)) if strong_recall_values else 1.0,
        per_output=per_output,
    )


def _optimizer(tf: Any, spec: WeightedCandidateSpec) -> Any:
    if spec.optimizer == "adam":
        return tf.keras.optimizers.Adam(learning_rate=spec.learning_rate)
    if spec.optimizer == "sgd":
        return tf.keras.optimizers.SGD(
            learning_rate=spec.learning_rate,
            momentum=0.9,
            nesterov=False,
        )
    raise ValueError(f"unsupported optimizer {spec.optimizer!r}")


def _base_elementwise_loss(tf: Any, y_true: Any, y_pred: Any, loss_name: LossName) -> Any:
    error = y_pred - y_true
    if loss_name == "mse":
        return tf.square(error)
    if loss_name == "huber":
        delta = tf.cast(0.15, y_pred.dtype)
        absolute = tf.abs(error)
        quadratic = tf.minimum(absolute, delta)
        linear = absolute - quadratic
        return 0.5 * tf.square(quadratic) + delta * linear
    raise ValueError(f"unsupported loss {loss_name!r}")


def _loss(tf: Any, spec: WeightedCandidateSpec, config: WeightedTrainingConfig) -> Any:
    if spec.weighting == "none":
        if spec.loss == "huber":
            return tf.keras.losses.Huber(delta=0.15)
        if spec.loss == "mse":
            return tf.keras.losses.MeanSquaredError()
        raise ValueError(f"unsupported loss {spec.loss!r}")
    if spec.weighting != "control":
        raise ValueError(f"unsupported weighting mode {spec.weighting!r}")

    def weighted_control_loss(y_true: Any, y_pred: Any) -> Any:
        base = _base_elementwise_loss(tf, y_true, y_pred, spec.loss)
        ones = tf.ones_like(y_true)
        active_weight = tf.cast(config.active_loss_weight, y_true.dtype)
        strong_weight = tf.cast(config.strong_loss_weight, y_true.dtype)
        weights = tf.where(y_true > config.activity_threshold, active_weight, ones)
        weights = tf.where(y_true > config.strong_threshold, strong_weight, weights)
        numerator = tf.reduce_sum(base * weights)
        denominator = tf.reduce_sum(weights)
        return tf.math.divide_no_nan(numerator, denominator)

    weighted_control_loss.__name__ = f"{spec.name}_loss"
    return weighted_control_loss


def _predict(model: Any, features: np.ndarray) -> np.ndarray:
    return np.asarray(model(features, training=False), dtype=np.float32)


def train_weighted_candidate(
    dataset: Dataset,
    spec: WeightedCandidateSpec,
    *,
    config: WeightedTrainingConfig,
) -> WeightedCandidateResult:
    _assert_dataset(dataset)
    x_train, y_train = dataset.select("train")
    x_validation, y_validation = dataset.select("validation")

    tf = configure_tensorflow_determinism(config.seed)
    tf.keras.backend.clear_session()
    model = build_climate_model(config=config.base_model_config())
    model.compile(optimizer=_optimizer(tf, spec), loss=_loss(tf, spec, config))

    history: dict[str, list[float]] = {
        "train_loss": [],
        "validation_control_mae": [],
        "validation_strong_mae": [],
    }
    batch_size = min(config.batch_size, len(x_train))
    rng = np.random.default_rng(config.seed)

    for _epoch in range(config.epochs):
        order = rng.permutation(len(x_train))
        epoch_losses: list[float] = []
        for start in range(0, len(order), batch_size):
            indices = order[start : start + batch_size]
            loss = model.train_on_batch(x_train[indices], y_train[indices])
            epoch_losses.append(float(np.asarray(loss).reshape(-1)[0]))
        validation = control_prediction_metrics(
            y_validation,
            _predict(model, x_validation),
            config=config,
        )
        history["train_loss"].append(float(np.mean(epoch_losses)))
        history["validation_control_mae"].append(validation.control_mae)
        history["validation_strong_mae"].append(validation.strong_mae)

    validation = control_prediction_metrics(
        y_validation,
        _predict(model, x_validation),
        config=config,
    )
    return WeightedCandidateResult(
        spec=spec,
        model=model,
        validation=validation,
        history=history,
    )


def compare_weighted_candidates(
    dataset: Dataset,
    *,
    config: WeightedTrainingConfig | None = None,
    candidates: tuple[WeightedCandidateSpec, ...] = DEFAULT_WEIGHTED_CANDIDATES,
) -> WeightedTrainingComparison:
    config = config or WeightedTrainingConfig.full()
    _assert_dataset(dataset)
    if not candidates:
        raise ValueError("at least one weighted training candidate is required")
    if len({candidate.name for candidate in candidates}) != len(candidates):
        raise ValueError("candidate names must be unique")

    results = tuple(train_weighted_candidate(dataset, spec, config=config) for spec in candidates)
    winner_index = min(
        range(len(results)),
        key=lambda index: (
            results[index].validation.control_mae,
            results[index].validation.strong_mae,
            results[index].validation.balanced_mae,
            -results[index].validation.strong_recall,
            -results[index].validation.macro_f1,
            results[index].validation.mae,
            results[index].spec.name,
        ),
    )

    # Test data remains untouched until the winner is selected from validation-only metrics.
    x_test, y_test = dataset.select("test")
    winner = results[winner_index]
    winner.test = control_prediction_metrics(
        y_test,
        _predict(winner.model, x_test),
        config=config,
    )
    return WeightedTrainingComparison(candidates=results, winner_index=winner_index)


def comparison_summary(comparison: WeightedTrainingComparison) -> tuple[str, ...]:
    lines: list[str] = []
    for result in comparison.candidates:
        validation = result.validation
        lines.append(
            f"{result.spec.name}: val_control_mae={validation.control_mae:.6f} "
            f"val_strong_mae={validation.strong_mae:.6f} "
            f"val_balanced_mae={validation.balanced_mae:.6f} "
            f"val_f1={validation.macro_f1:.4f} "
            f"val_strong_recall={validation.strong_recall:.4f}"
        )
    winner = comparison.winner
    if winner.test is None:
        raise AssertionError("winner test metrics are missing")
    lines.append(f"winner={winner.spec.name}")
    lines.append(
        f"test_control_mae={winner.test.control_mae:.6f} "
        f"test_strong_mae={winner.test.strong_mae:.6f} "
        f"test_balanced_mae={winner.test.balanced_mae:.6f} "
        f"test_f1={winner.test.macro_f1:.4f} "
        f"test_strong_recall={winner.test.strong_recall:.4f}"
    )
    return tuple(lines)


__all__ = [
    "ControlSplitMetrics",
    "DEFAULT_WEIGHTED_CANDIDATES",
    "WeightedCandidateResult",
    "WeightedCandidateSpec",
    "WeightedTrainingComparison",
    "WeightedTrainingConfig",
    "compare_weighted_candidates",
    "comparison_summary",
    "control_prediction_metrics",
    "label_loss_weights",
    "train_weighted_candidate",
]
