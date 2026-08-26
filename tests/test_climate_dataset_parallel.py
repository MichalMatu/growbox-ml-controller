from __future__ import annotations

import numpy as np
import pytest

from tools.ml.climate_dataset import ClimateDatasetConfig, generate_climate_dataset
from tools.ml.climate_dataset_parallel import generate_climate_dataset_parallel


def _assert_same_bundle(reference, parallel) -> None:
    assert reference.dataset.feature_names == parallel.dataset.feature_names
    assert reference.dataset.output_names == parallel.dataset.output_names
    np.testing.assert_array_equal(reference.dataset.features, parallel.dataset.features)
    np.testing.assert_array_equal(reference.dataset.labels, parallel.dataset.labels)
    np.testing.assert_array_equal(reference.dataset.scenario_ids, parallel.dataset.scenario_ids)
    np.testing.assert_array_equal(reference.dataset.scenario_seeds, parallel.dataset.scenario_seeds)
    np.testing.assert_array_equal(reference.dataset.splits, parallel.dataset.splits)
    np.testing.assert_array_equal(reference.families, parallel.families)
    np.testing.assert_array_equal(reference.profiles, parallel.profiles)
    np.testing.assert_array_equal(reference.safe_fallbacks, parallel.safe_fallbacks)


def test_one_worker_is_reference_generator() -> None:
    config = ClimateDatasetConfig(
        scenarios_per_family=1,
        steps_per_scenario=1,
        seed=301,
        random_invalid_probability=0.0,
        random_stale_probability=0.0,
    )
    reference = generate_climate_dataset(config)
    generated = generate_climate_dataset_parallel(config, workers=1)
    _assert_same_bundle(reference, generated)


def test_two_workers_are_bit_exact_with_reference() -> None:
    config = ClimateDatasetConfig(
        scenarios_per_family=1,
        steps_per_scenario=1,
        seed=302,
        random_invalid_probability=0.0,
        random_stale_probability=0.0,
    )
    reference = generate_climate_dataset(config)
    parallel = generate_climate_dataset_parallel(config, workers=2)
    _assert_same_bundle(reference, parallel)


def test_parallel_generator_rejects_invalid_worker_count() -> None:
    with pytest.raises(ValueError, match="workers must be positive"):
        generate_climate_dataset_parallel(ClimateDatasetConfig.quick(), workers=0)
