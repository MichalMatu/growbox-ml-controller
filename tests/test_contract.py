from __future__ import annotations

import json
import math
import re
from pathlib import Path

import numpy as np
import pytest

from tools.ml.contract import load_contract
from tools.ml.generate_dataset import controller_input_record
from tools.ml.simulator import ControlAction

CANONICAL_GROUPS = (
    "sensors",
    "validity",
    "environment",
    "cultivation",
    "actuators.heater",
    "actuators.fan",
    "actuators.humidifier",
    "actuators.irrigation",
    "targets",
    "previous",
)


def _resolve_path(document, path):
    value = document
    for part in path.split("."):
        value = value[part]
    return value


def test_contract_count_order_and_hash_match_generated_cpp(scenario):
    contract = load_contract()
    header = (
        contract.path.parent.parent / "lib/environment_control/src/EnvironmentSchema.h"
    ).read_text(encoding="utf-8")
    cpp_hash = re.search(r'kSchemaHash\[\] = "([0-9a-f]+)"', header)
    assert cpp_hash is not None
    assert contract.short_hash == cpp_hash.group(1)
    assert len(contract.features) == 43
    assert contract.outputs == ("heater", "fan", "humidifier", "irrigation")
    assert contract.feature_names[:3] == (
        "air_temperature_c",
        "air_humidity_pct",
        "co2_ppm",
    )
    paths_block = re.search(r"kFeaturePaths\{\{(?P<paths>.*?)\}\};", header, flags=re.DOTALL)
    assert paths_block is not None
    assert tuple(re.findall(r'"([^"]+)"', paths_block.group("paths"))) == tuple(
        feature.path for feature in contract.features
    )


def test_feature_paths_are_explicit_and_match_canonical_groups():
    contract = load_contract()
    raw_features = contract.document["model"]["features"]
    groups = contract.document["groups"]
    assert tuple(groups) == CANONICAL_GROUPS
    assert all("path" in feature and "source" not in feature for feature in raw_features)

    by_name = {feature.name: feature for feature in contract.features}
    for group_path, feature_names in groups.items():
        for feature_name in feature_names:
            assert by_name[feature_name].path.rsplit(".", 1)[0] == group_path


def test_example_scenarios_contain_every_contract_feature_path():
    contract = load_contract()
    scenario_dir = contract.path.parent.parent / "examples" / "scenarios"
    scenario_paths = sorted(Path(scenario_dir).glob("*.jsonl"))
    assert scenario_paths

    for scenario_path in scenario_paths:
        if scenario_path.name.startswith("v3-"):
            continue
        records = [
            json.loads(line)
            for line in scenario_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        scenario = next(record for record in records if record.get("command") == "load_scenario")
        for feature in contract.features:
            _resolve_path(scenario, feature.path)
        encoded = contract.encode(scenario)
        assert encoded.shape == (len(contract.features),)
        assert np.all(np.isfinite(encoded))


def test_controller_input_record_uses_canonical_wire_shape(scenario):
    sensors = scenario.initial_state.as_dict()
    record = controller_input_record(
        scenario,
        sensors,
        {name: True for name in sensors},
        ControlAction(),
    )
    assert set(record) == {
        "sensors",
        "validity",
        "environment",
        "cultivation",
        "actuators",
        "targets",
        "previous",
    }
    assert set(record["actuators"]) == {
        "heater",
        "fan",
        "humidifier",
        "irrigation",
    }
    assert set(record["actuators"]["heater"]) == {
        "available",
        "max_power_w",
        "efficiency",
        "control_type",
    }
    assert set(record["actuators"]["fan"]) == {
        "available",
        "max_airflow_m3_h",
        "minimum_command",
        "control_type",
    }
    assert set(record["actuators"]["humidifier"]) == {
        "available",
        "max_output_g_h",
        "control_type",
    }
    assert set(record["actuators"]["irrigation"]) == {
        "available",
        "flow_ml_s",
        "maximum_pulse_s",
        "minimum_interval_s",
        "control_type",
    }
    contract = load_contract()
    for feature in contract.features:
        _resolve_path(record, feature.path)


def test_conservative_omission_defaults_are_in_contract():
    contract = load_contract()
    by_name = {feature.name: feature for feature in contract.features}
    for name in (
        "air_temperature_valid",
        "air_humidity_valid",
        "co2_valid",
        "soil_moisture_valid",
        "outside_temperature_valid",
        "outside_humidity_valid",
        "heater_available",
        "heater_max_power_w",
        "fan_available",
        "fan_max_airflow_m3_h",
        "humidifier_available",
        "humidifier_max_output_g_h",
        "irrigation_available",
        "irrigation_flow_ml_s",
    ):
        assert by_name[name].default == 0.0


def test_encoder_clamps_ranges_and_applies_validity_masks(scenario):
    contract = load_contract()
    sensors = scenario.initial_state.as_dict()
    sensors["air_temperature_c"] = 1.0e9
    sensors["air_humidity_pct"] = 200.0
    sensors["soil_moisture_pct"] = -1.0e9
    validity = {name: True for name in sensors}
    validity["air_temperature_c"] = False
    record = controller_input_record(scenario, sensors, validity, ControlAction())
    encoded = contract.encode(record)
    temperature = contract.features[0]
    expected_default = (temperature.default - temperature.minimum) / (
        temperature.maximum - temperature.minimum
    )
    assert encoded.dtype == np.float32
    assert encoded.shape == (43,)
    assert math.isclose(float(encoded[0]), expected_default, abs_tol=1e-7)
    assert encoded[1] == 1.0
    assert encoded[3] == 0.0
    assert encoded[6] == 0.0
    assert np.all(np.isfinite(encoded))
    assert np.all((0.0 <= encoded) & (encoded <= 1.0))


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
@pytest.mark.parametrize("valid", [True, False])
def test_encoder_rejects_non_finite_sensor_even_when_masked(scenario, value, valid):
    contract = load_contract()
    sensors = scenario.initial_state.as_dict()
    sensors["air_temperature_c"] = value
    validity = {name: True for name in sensors}
    validity["air_temperature_c"] = valid
    record = controller_input_record(scenario, sensors, validity, ControlAction())
    with pytest.raises(ValueError, match="non-finite value for air_temperature_c"):
        contract.encode(record)


def test_enum_encoding_comes_from_schema(scenario):
    contract = load_contract()
    sensors = scenario.initial_state.as_dict()
    validity = {name: True for name in sensors}
    record = controller_input_record(scenario, sensors, validity, ControlAction())
    record["actuators"]["heater"]["control_type"] = "pwm"
    encoded = contract.encode(record)
    index = contract.feature_names.index("heater_control_type")
    assert encoded[index] == 1.0


def test_omitted_sensor_and_actuator_use_conservative_schema_defaults(scenario):
    contract = load_contract()
    sensors = scenario.initial_state.as_dict()
    del sensors["air_temperature_c"]
    validity = {name: True for name in scenario.initial_state.as_dict()}
    validity["air_temperature_c"] = False
    record = controller_input_record(scenario, sensors, validity, ControlAction())
    del record["actuators"]["heater"]
    encoded = contract.encode(record)
    by_name = {name: index for index, name in enumerate(contract.feature_names)}
    temperature = contract.features[by_name["air_temperature_c"]]
    normalized_default = (temperature.default - temperature.minimum) / (
        temperature.maximum - temperature.minimum
    )
    assert math.isclose(
        float(encoded[by_name["air_temperature_c"]]), normalized_default, abs_tol=1e-7
    )
    assert encoded[by_name["air_temperature_valid"]] == 0.0
    assert encoded[by_name["heater_available"]] == 0.0
    assert encoded[by_name["heater_max_power_w"]] == 0.0
