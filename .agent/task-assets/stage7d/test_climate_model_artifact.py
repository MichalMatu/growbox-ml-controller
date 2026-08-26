from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from tools.ml.climate_input import CLIMATE_V6_CONTRACT_PATH
from tools.ml.climate_model_artifact import (
    ClimateModelMetadata,
    ClimatePortableModel,
    from_keras_model,
    load_portable_model,
    max_prediction_delta,
    save_portable_model,
)
from tools.ml.climate_training import ClimateTrainingConfig, build_climate_model
from tools.ml.contract import load_contract


def _metadata() -> ClimateModelMetadata:
    contract = load_contract(CLIMATE_V6_CONTRACT_PATH)
    return ClimateModelMetadata(
        schema_version=contract.schema_version,
        contract_hash=contract.hash_hex,
        feature_names=contract.feature_names,
        output_names=contract.outputs,
        training_seed=1847,
        candidate_name="unit-test",
        source_commit="0123456789abcdef",
    )


def test_portable_model_matches_keras_predictions() -> None:
    config = ClimateTrainingConfig.quick(seed=1847)
    keras_model = build_climate_model(config=config)
    portable = from_keras_model(keras_model, _metadata())
    features = np.random.default_rng(13).uniform(0.0, 1.0, size=(32, 38)).astype(np.float32)
    assert portable.parameter_count == 2502
    assert max_prediction_delta(keras_model, portable, features) <= 2.0e-6
    prediction = portable.predict(features)
    assert prediction.shape == (32, 6)
    assert np.isfinite(prediction).all()
    assert np.all((prediction >= 0.0) & (prediction <= 1.0))


def test_portable_model_round_trip(tmp_path: Path) -> None:
    config = ClimateTrainingConfig.quick(seed=1847)
    keras_model = build_climate_model(config=config)
    portable = from_keras_model(keras_model, _metadata())
    weights_path = tmp_path / "model.npz"
    metadata_path = tmp_path / "model.json"
    save_portable_model(portable, weights_path, metadata_path)
    loaded = load_portable_model(weights_path, metadata_path)
    features = np.random.default_rng(21).uniform(0.0, 1.0, size=(7, 38)).astype(np.float32)
    np.testing.assert_array_equal(loaded.predict(features), portable.predict(features))
    assert loaded.metadata == portable.metadata
    assert loaded.parameter_count == 2502


def test_portable_model_rejects_bad_shape() -> None:
    weights = (
        np.zeros((37, 32), dtype=np.float32),
        np.zeros((32,), dtype=np.float32),
        np.zeros((32, 32), dtype=np.float32),
        np.zeros((32,), dtype=np.float32),
        np.zeros((32, 6), dtype=np.float32),
        np.zeros((6,), dtype=np.float32),
    )
    with pytest.raises(ValueError, match="weight 0"):
        ClimatePortableModel(_metadata(), weights)


def test_portable_model_rejects_nonfinite_input() -> None:
    config = ClimateTrainingConfig.quick(seed=1847)
    portable = from_keras_model(build_climate_model(config=config), _metadata())
    bad = np.zeros((38,), dtype=np.float32)
    bad[3] = np.nan
    with pytest.raises(ValueError, match="NaN/Inf"):
        portable.predict(bad)
