from __future__ import annotations

from tools.ml.train_model import TrainingConfig, build_model


def test_model_is_small_two_layer_sigmoid_mlp():
    model = build_model(40, 4, config=TrainingConfig.quick(seed=9))
    dense_layers = [layer for layer in model.layers if layer.__class__.__name__ == "Dense"]
    assert [layer.units for layer in dense_layers] == [32, 32, 4]
    assert [layer.activation.__name__ for layer in dense_layers] == [
        "relu",
        "relu",
        "sigmoid",
    ]
    assert model.count_params() == 2500
