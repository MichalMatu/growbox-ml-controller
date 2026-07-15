from __future__ import annotations

from tools.ml.contract import V2_CONTRACT_PATH, load_contract


def test_v2_contract_loads_with_ten_outputs():
    contract = load_contract(V2_CONTRACT_PATH)
    assert contract.schema_version == 2
    assert len(contract.outputs) == 10
    assert contract.outputs[0] == "heater"
    assert contract.outputs[-1] == "irrigation_zone_4"


def test_v2_zone_sensor_validity_masking():
    contract = load_contract(V2_CONTRACT_PATH)
    controller_input = {
        "zones": [
            {
                "available": True,
                "sensors": {"soil_moisture_pct": 80.0},
                "validity": {"soil_moisture_pct": False},
            }
        ]
    }
    encoded = contract.encode(controller_input)
    moisture_index = contract.feature_names.index("soil_moisture_zone_1_pct")
    default_norm = contract.features[moisture_index].normalize(50.0)
    assert encoded[moisture_index] == default_norm
