from __future__ import annotations

import numpy as np
import pytest

from tools.ml.climate_dagger import DaggerRows
from tools.ml.dataset import Dataset
from tools.ml.run_dagger_distributed import (
    load_shard,
    merge_shards,
    save_shard,
    shard_episode_indices,
)


def _rows(values: list[int]) -> DaggerRows:
    row_count = len(values)
    dataset = Dataset(
        features=np.asarray([[float(value)] * 38 for value in values], dtype=np.float32),
        labels=np.asarray([[float(value) / 10.0] * 6 for value in values], dtype=np.float32),
        scenario_ids=np.asarray([f"scenario-{value}" for value in values]),
        scenario_seeds=np.asarray(values, dtype=np.int64),
        splits=np.full(row_count, "train"),
        feature_names=tuple(f"feature-{index}" for index in range(38)),
        output_names=(
            "heater",
            "cooler",
            "exhaust_fan",
            "humidifier",
            "dehumidifier",
            "co2_doser",
        ),
    )
    return DaggerRows(
        dataset=dataset,
        families=np.asarray([f"family-{value}" for value in values]),
        humidity_modes=np.asarray(["RH" if value % 2 == 0 else "VPD" for value in values]),
        safe_fallbacks=np.asarray([False] * row_count, dtype=np.bool_),
    )


def test_shard_episode_indices_partition_complete_range() -> None:
    shards = [shard_episode_indices(17, index, 6) for index in range(6)]
    flattened = sorted(value for shard in shards for value in shard)
    assert flattened == list(range(17))
    assert len(flattened) == len(set(flattened))


@pytest.mark.parametrize(
    ("shard_index", "shard_count"),
    [(-1, 2), (2, 2), (0, 0)],
)
def test_shard_episode_indices_rejects_invalid_configuration(
    shard_index: int, shard_count: int
) -> None:
    with pytest.raises(ValueError):
        shard_episode_indices(10, shard_index, shard_count)


def test_merge_shards_restores_global_row_order(tmp_path) -> None:
    first = tmp_path / "shard-0.npz"
    second = tmp_path / "shard-1.npz"
    save_shard(first, _rows([0, 2, 4]), np.asarray([0, 2, 4], dtype=np.int64))
    save_shard(second, _rows([1, 3, 5]), np.asarray([1, 3, 5], dtype=np.int64))

    restored, order = load_shard(first)
    assert len(restored.dataset.features) == 3
    assert np.array_equal(order, np.asarray([0, 2, 4], dtype=np.int64))

    merged = merge_shards([second, first], expected_rows=6)
    assert merged.dataset.scenario_seeds.tolist() == [0, 1, 2, 3, 4, 5]
    assert merged.families.tolist() == [
        "family-0",
        "family-1",
        "family-2",
        "family-3",
        "family-4",
        "family-5",
    ]


def test_merge_shards_rejects_duplicate_or_missing_row_order(tmp_path) -> None:
    first = tmp_path / "shard-0.npz"
    second = tmp_path / "shard-1.npz"
    save_shard(first, _rows([0, 1]), np.asarray([0, 1], dtype=np.int64))
    save_shard(second, _rows([2, 3]), np.asarray([1, 3], dtype=np.int64))
    with pytest.raises(AssertionError, match="complete non-overlapping"):
        merge_shards([first, second], expected_rows=4)
