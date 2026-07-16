"""Shared dataset container and leakage-free scenario splits."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass(frozen=True)
class DatasetConfig:
    scenario_count: int
    steps_per_scenario: int
    seed: int = 1847
    invalid_reading_probability: float = 0.025

    @classmethod
    def quick(cls, seed: int = 1847) -> DatasetConfig:
        return cls(scenario_count=12, steps_per_scenario=20, seed=seed)

    @classmethod
    def full(cls, seed: int = 1847) -> DatasetConfig:
        return cls(scenario_count=72, steps_per_scenario=120, seed=seed)


@dataclass(frozen=True)
class Dataset:
    features: np.ndarray
    labels: np.ndarray
    scenario_ids: np.ndarray
    scenario_seeds: np.ndarray
    splits: np.ndarray
    feature_names: tuple[str, ...]
    output_names: tuple[str, ...]

    def __post_init__(self) -> None:
        rows = self.features.shape[0]
        if self.features.ndim != 2 or self.labels.ndim != 2:
            raise ValueError("features and labels must be matrices")
        if not all(
            len(values) == rows
            for values in (
                self.labels,
                self.scenario_ids,
                self.scenario_seeds,
                self.splits,
            )
        ):
            raise ValueError("dataset columns have inconsistent row counts")

    def select(self, split: str) -> tuple[np.ndarray, np.ndarray]:
        mask = self.splits == split
        return self.features[mask], self.labels[mask]

    def save(self, path: str | Path) -> None:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(
            destination,
            features=self.features,
            labels=self.labels,
            scenario_ids=self.scenario_ids,
            scenario_seeds=self.scenario_seeds,
            splits=self.splits,
            feature_names=np.asarray(self.feature_names),
            output_names=np.asarray(self.output_names),
        )

    @classmethod
    def load(cls, path: str | Path) -> Dataset:
        with np.load(path, allow_pickle=False) as data:
            return cls(
                features=data["features"],
                labels=data["labels"],
                scenario_ids=data["scenario_ids"],
                scenario_seeds=data["scenario_seeds"],
                splits=data["splits"],
                feature_names=tuple(str(value) for value in data["feature_names"]),
                output_names=tuple(str(value) for value in data["output_names"]),
            )


def split_scenarios(
    scenario_ids: Iterable[str],
    *,
    seed: int,
    train_fraction: float = 0.70,
    validation_fraction: float = 0.15,
) -> dict[str, str]:
    unique = sorted(set(str(value) for value in scenario_ids))
    if len(unique) < 3:
        raise ValueError("at least three scenarios are needed for leakage-free splits")
    if not 0.0 < train_fraction < 1.0 or not 0.0 < validation_fraction < 1.0:
        raise ValueError("split fractions must be between zero and one")
    if train_fraction + validation_fraction >= 1.0:
        raise ValueError("train and validation fractions leave no test split")

    order = np.random.default_rng(seed).permutation(len(unique))
    shuffled = [unique[int(index)] for index in order]
    train_count = max(1, int(round(len(unique) * train_fraction)))
    validation_count = max(1, int(round(len(unique) * validation_fraction)))
    if train_count + validation_count >= len(unique):
        train_count = len(unique) - 2
        validation_count = 1
    mapping: dict[str, str] = {}
    for index, scenario_id in enumerate(shuffled):
        if index < train_count:
            mapping[scenario_id] = "train"
        elif index < train_count + validation_count:
            mapping[scenario_id] = "validation"
        else:
            mapping[scenario_id] = "test"
    return mapping
