from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from tools.ml.climate_input import CLIMATE_V6_CONTRACT_PATH
from tools.ml.climate_model_artifact import load_portable_model
from tools.ml.contract import load_contract

ROOT = Path(__file__).resolve().parents[1]
WEIGHTS = ROOT / "reports" / "ml" / "climate_v6_model_stage13_compat.npz"
METADATA = ROOT / "reports" / "ml" / "climate_v6_model_stage13_compat.json"
OLD_WEIGHTS = ROOT / "reports" / "ml" / "climate_v6_model_seed1847.npz"


def test_stage13_compat_artifact_preserves_historical_weights_and_zeros_new_inputs() -> None:
    contract = load_contract(CLIMATE_V6_CONTRACT_PATH)
    model = load_portable_model(WEIGHTS, METADATA)
    assert model.metadata.contract_hash == contract.hash_hex
    assert model.metadata.feature_names == contract.feature_names
    assert model.weights[0].shape == (44, 32)
    np.testing.assert_array_equal(model.weights[0][32:38], np.zeros((6, 32), dtype=np.float32))

    with np.load(OLD_WEIGHTS, allow_pickle=False) as old:
        np.testing.assert_array_equal(model.weights[0][:32], old["w1"][:32])
        np.testing.assert_array_equal(model.weights[0][38:], old["w1"][32:])
        np.testing.assert_array_equal(model.weights[1], old["b1"])
        np.testing.assert_array_equal(model.weights[2], old["w2"])
        np.testing.assert_array_equal(model.weights[3], old["b2"])
        np.testing.assert_array_equal(model.weights[4], old["w3"])
        np.testing.assert_array_equal(model.weights[5], old["b3"])

    payload = json.loads(METADATA.read_text(encoding="utf-8"))
    migration = payload["migration"]
    assert migration["kind"] == "stage13_zero_weight_input_expansion"
    assert migration["inserted_first_layer_weights"] == "all_zero"
    assert migration["trained_on_new_features"] is False
    assert float(migration["prediction_max_delta"]) <= 2.0e-6
