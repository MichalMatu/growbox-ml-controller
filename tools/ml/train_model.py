"""Train and evaluate the compact Keras controller MLP."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from .generate_dataset import Dataset


@dataclass(frozen=True)
class TrainingConfig:
    seed: int = 1847
    epochs: int = 18
    batch_size: int = 32
    learning_rate: float = 0.025
    hidden_units: int = 32
    export_weight_decimals: int = 5

    @classmethod
    def quick(cls, seed: int = 1847) -> "TrainingConfig":
        return cls(seed=seed, epochs=18, batch_size=32, learning_rate=0.025)

    @classmethod
    def full(cls, seed: int = 1847) -> "TrainingConfig":
        return cls(seed=seed, epochs=70, batch_size=64, learning_rate=0.012)


@dataclass
class TrainingResult:
    model: Any
    history: Mapping[str, list[float]]
    metrics: dict[str, object]


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
        # TensorFlow only permits thread configuration before runtime startup.
        pass
    return tf


def build_model(
    input_count: int,
    output_count: int,
    *,
    config: TrainingConfig,
) -> Any:
    tf = configure_tensorflow_determinism(config.seed)
    keras = tf.keras
    return keras.Sequential(
        [
            keras.layers.Input(shape=(input_count,), name="controller_features"),
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
                output_count,
                activation="sigmoid",
                kernel_initializer=keras.initializers.GlorotUniform(seed=config.seed + 3),
                bias_initializer="zeros",
                name="normalized_outputs",
            ),
        ],
        name="growbox_environment_controller",
    )


def prediction_metrics(
    expected: np.ndarray,
    predicted: np.ndarray,
    output_names: tuple[str, ...],
) -> dict[str, object]:
    if expected.shape != predicted.shape:
        raise ValueError("prediction and label shapes do not match")
    errors = np.asarray(predicted, dtype=np.float64) - np.asarray(expected, dtype=np.float64)
    per_output: dict[str, dict[str, float]] = {}
    for index, name in enumerate(output_names):
        column = errors[:, index]
        per_output[name] = {
            "mae": float(np.mean(np.abs(column))),
            "rmse": float(np.sqrt(np.mean(np.square(column)))),
            "max_abs_error": float(np.max(np.abs(column))),
        }
    return {
        "mae": float(np.mean(np.abs(errors))),
        "rmse": float(np.sqrt(np.mean(np.square(errors)))),
        "max_abs_error": float(np.max(np.abs(errors))),
        "per_output": per_output,
    }


def train(dataset: Dataset, config: TrainingConfig) -> TrainingResult:
    x_train, y_train = dataset.select("train")
    x_validation, y_validation = dataset.select("validation")
    x_test, y_test = dataset.select("test")
    if min(len(x_train), len(x_validation), len(x_test)) == 0:
        raise ValueError("train, validation, and test splits must all be non-empty")

    tf = configure_tensorflow_determinism(config.seed)
    tf.keras.backend.clear_session()
    model = build_model(
        dataset.features.shape[1], dataset.labels.shape[1], config=config
    )
    optimizer = tf.keras.optimizers.SGD(
        learning_rate=config.learning_rate, momentum=0.0, nesterov=False
    )
    model.compile(optimizer=optimizer, loss="mse", metrics=["mae"])
    history_values: dict[str, list[float]] = {
        "loss": [],
        "mae": [],
        "val_loss": [],
        "val_mae": [],
    }
    batch_size = min(config.batch_size, len(x_train))
    # Explicit contiguous batches avoid an implicit tf.data pipeline and make
    # the training order obvious and stable.
    for _ in range(config.epochs):
        for start in range(0, len(x_train), batch_size):
            stop = start + batch_size
            model.train_on_batch(x_train[start:stop], y_train[start:stop])
        training_prediction = np.asarray(model(x_train, training=False), dtype=np.float32)
        validation_prediction = np.asarray(
            model(x_validation, training=False), dtype=np.float32
        )
        history_values["loss"].append(
            float(np.mean(np.square(training_prediction - y_train)))
        )
        history_values["mae"].append(
            float(np.mean(np.abs(training_prediction - y_train)))
        )
        history_values["val_loss"].append(
            float(np.mean(np.square(validation_prediction - y_validation)))
        )
        history_values["val_mae"].append(
            float(np.mean(np.abs(validation_prediction - y_validation)))
        )
    # The model remains genuinely Keras-trained. Rounding only the final
    # weights gives the portable C export a stable representation across CPU
    # math kernels and operating systems.
    quantized_weights = [
        np.round(np.asarray(weight, dtype=np.float64), config.export_weight_decimals).astype(
            np.float32
        )
        for weight in model.get_weights()
    ]
    model.set_weights(quantized_weights)
    validation_prediction = np.asarray(model(x_validation, training=False), dtype=np.float32)
    test_prediction = np.asarray(model(x_test, training=False), dtype=np.float32)
    metrics: dict[str, object] = {
        "validation": prediction_metrics(
            y_validation, validation_prediction, dataset.output_names
        ),
        "test": prediction_metrics(y_test, test_prediction, dataset.output_names),
        "parameter_count": int(model.count_params()),
        "epochs": config.epochs,
        "export_weight_decimals": config.export_weight_decimals,
    }
    serial_history = history_values
    return TrainingResult(model=model, history=serial_history, metrics=metrics)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--quick", action="store_true")
    mode.add_argument("--full", action="store_true")
    parser.add_argument("--seed", type=int, default=1847)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--metrics", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    dataset = Dataset.load(args.dataset)
    config = TrainingConfig.quick(args.seed) if args.quick else TrainingConfig.full(args.seed)
    result = train(dataset, config)
    args.model.parent.mkdir(parents=True, exist_ok=True)
    result.model.save(args.model)
    args.metrics.parent.mkdir(parents=True, exist_ok=True)
    args.metrics.write_text(
        json.dumps(result.metrics, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        f"trained {result.metrics['parameter_count']} parameters; "
        f"test MAE={result.metrics['test']['mae']:.6f}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
