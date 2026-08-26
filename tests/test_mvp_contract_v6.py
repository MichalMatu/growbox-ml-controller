from __future__ import annotations

import json
from pathlib import Path

SCHEMA_PATH = Path("schemas/environment-controller.v6.json")
EXPECTED_FEATURES = (
    "air_temperature_c",
    "relative_humidity_pct",
    "co2_ppm",
    "outside_temperature_c",
    "outside_humidity_pct",
    "air_temperature_valid",
    "air_temperature_fresh",
    "relative_humidity_valid",
    "relative_humidity_fresh",
    "co2_valid",
    "co2_fresh",
    "outside_temperature_valid",
    "outside_temperature_fresh",
    "outside_humidity_valid",
    "outside_humidity_fresh",
    "air_vpd_kpa",
    "humidity_control_mode",
    "target_air_temperature_c",
    "target_relative_humidity_pct",
    "target_air_vpd_kpa",
    "co2_control_enabled",
    "target_co2_ppm",
    "light_level",
    "temperature_rate_c_min",
    "humidity_rate_pct_min",
    "co2_rate_ppm_min",
    "previous_heater",
    "previous_cooler",
    "previous_exhaust_fan",
    "previous_humidifier",
    "previous_dehumidifier",
    "previous_co2_doser",
    "heater_available",
    "cooler_available",
    "exhaust_fan_available",
    "humidifier_available",
    "dehumidifier_available",
    "co2_doser_available",
)
EXPECTED_ML_OUTPUTS = (
    "heater",
    "cooler",
    "exhaust_fan",
    "humidifier",
    "dehumidifier",
    "co2_doser",
)
EXPECTED_PRODUCT_ROLES = (
    "heater",
    "cooler",
    "exhaust_fan",
    "circulation_fan",
    "humidifier",
    "dehumidifier",
    "co2_doser",
    "light",
)


def load_schema() -> dict[str, object]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def test_v6_is_climate_only_migration_target() -> None:
    schema = load_schema()
    assert schema["schema_version"] == 6
    assert schema["status"] == "migration_target"
    assert schema["contract_id"] == "climate-mvp-v1"
    assert tuple(schema["product_output_roles"]) == EXPECTED_PRODUCT_ROLES


def test_v6_ml_feature_order_is_frozen_and_small() -> None:
    schema = load_schema()
    model = schema["model"]
    names = tuple(item["name"] for item in model["features"])
    assert names == EXPECTED_FEATURES
    assert model["feature_count"] == len(EXPECTED_FEATURES) == 38
    assert len(names) == len(set(names))
    for item in model["features"]:
        assert item["minimum"] <= item["default"] <= item["maximum"]


def test_v6_ml_outputs_exclude_schedule_and_internal_circulation() -> None:
    schema = load_schema()
    model = schema["model"]
    names = tuple(item["name"] for item in model["outputs"])
    assert names == EXPECTED_ML_OUTPUTS
    assert model["output_count"] == len(EXPECTED_ML_OUTPUTS) == 6
    assert "light" not in names
    assert "circulation_fan" not in names


def test_v6_contract_has_no_pot_or_outside_co2_model_features() -> None:
    schema = load_schema()
    model_names = [item["name"] for item in schema["model"]["features"]]
    model_names += [item["name"] for item in schema["model"]["outputs"]]
    forbidden = (
        "pot_",
        "soil_",
        "irrigation",
        "nutrient",
        "heat_mat",
        "leaf_",
        "outside_co2",
    )
    assert not any(token in name for token in forbidden for name in model_names)
    assert schema["measurement_contract"]["outside_co2_sensor"] is False


def test_v6_keeps_validity_and_freshness_separate() -> None:
    names = {item["name"] for item in load_schema()["model"]["features"]}
    for stem in (
        "air_temperature",
        "relative_humidity",
        "co2",
        "outside_temperature",
        "outside_humidity",
    ):
        assert f"{stem}_valid" in names
        assert f"{stem}_fresh" in names
