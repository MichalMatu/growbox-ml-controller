from __future__ import annotations

import numpy as np

from tools.ml.climate_dagger import (
    DaggerCollectionConfig,
    _make_teacher,
    append_train_only,
    frozen_split_fingerprint,
)
from tools.ml.climate_sequence_teacher import ClimateSequenceRolloutTeacher
from tools.ml.climate_simulator import CLIMATE_OUTPUT_NAMES
from tools.ml.climate_teacher import ClimateRolloutTeacher
from tools.ml.dataset import Dataset


def _dataset(prefix: str, splits: list[str]) -> Dataset:
    rows = len(splits)
    features = np.arange(rows * 44, dtype=np.float32).reshape(rows, 44) / 100.0
    labels = np.zeros((rows, 6), dtype=np.float32)
    for index in range(rows):
        labels[index, index % 6] = 0.5
    return Dataset(
        features=features,
        labels=labels,
        scenario_ids=np.asarray([f"{prefix}-{index}" for index in range(rows)]),
        scenario_seeds=np.arange(rows, dtype=np.int64) + 100,
        splits=np.asarray(splits),
        feature_names=tuple(f"f{index}" for index in range(44)),
        output_names=CLIMATE_OUTPUT_NAMES,
    )


def test_append_train_only_preserves_frozen_validation_and_test() -> None:
    base = _dataset("base", ["train", "train", "validation", "test"])
    dagger = _dataset("dagger-longer-scenario-name", ["train", "train"])
    validation_before = frozen_split_fingerprint(base, "validation")
    test_before = frozen_split_fingerprint(base, "test")
    combined = append_train_only(base, dagger)
    assert len(combined.features) == 6
    assert frozen_split_fingerprint(combined, "validation") == validation_before
    assert frozen_split_fingerprint(combined, "test") == test_before
    assert int(np.sum(combined.splits == "validation")) == 1
    assert int(np.sum(combined.splits == "test")) == 1


def test_append_train_only_rejects_non_train_rows() -> None:
    base = _dataset("base", ["train", "validation", "test"])
    dagger = _dataset("dagger", ["validation"])
    try:
        append_train_only(base, dagger)
    except ValueError as exc:
        assert "train-only" in str(exc)
    else:
        raise AssertionError("non-train DAgger rows must be rejected")


def test_append_train_only_rejects_scenario_overlap() -> None:
    base = _dataset("base", ["train", "validation", "test"])
    dagger = _dataset("dagger", ["train"])
    dagger = Dataset(
        features=dagger.features,
        labels=dagger.labels,
        scenario_ids=np.asarray([base.scenario_ids[0]]),
        scenario_seeds=dagger.scenario_seeds,
        splits=dagger.splits,
        feature_names=dagger.feature_names,
        output_names=dagger.output_names,
    )
    try:
        append_train_only(base, dagger)
    except ValueError as exc:
        assert "overlap" in str(exc)
    else:
        raise AssertionError("overlapping DAgger scenarios must be rejected")


def test_frozen_split_fingerprint_changes_when_content_changes() -> None:
    dataset = _dataset("base", ["train", "validation", "test"])
    before = frozen_split_fingerprint(dataset, "validation")
    features = dataset.features.copy()
    features[1, 0] += 1.0
    changed = Dataset(
        features=features,
        labels=dataset.labels,
        scenario_ids=dataset.scenario_ids,
        scenario_seeds=dataset.scenario_seeds,
        splits=dataset.splits,
        feature_names=dataset.feature_names,
        output_names=dataset.output_names,
    )
    assert frozen_split_fingerprint(changed, "validation") != before


def test_dagger_teacher_kind_preserves_rollout_default_and_allows_sequence_opt_in() -> None:
    default = DaggerCollectionConfig(seed=1)
    assert default.teacher_kind == "rollout"
    assert isinstance(_make_teacher(default.teacher_kind), ClimateRolloutTeacher)

    sequence = DaggerCollectionConfig(seed=1, teacher_kind="sequence")
    assert sequence.teacher_kind == "sequence"
    assert isinstance(_make_teacher(sequence.teacher_kind), ClimateSequenceRolloutTeacher)


def test_dagger_teacher_kind_rejects_unknown_value() -> None:
    try:
        DaggerCollectionConfig(seed=1, teacher_kind="unknown")
    except ValueError as exc:
        assert "teacher_kind" in str(exc)
    else:
        raise AssertionError("unknown DAgger teacher_kind must be rejected")
