from __future__ import annotations

import json
from pathlib import Path

ROOT = Path.cwd()


def feature(
    name: str,
    path: str,
    kind: str,
    unit: str,
    minimum: float,
    maximum: float,
    default: float,
    encoding: dict[str, float] | None = None,
) -> dict[str, object]:
    item: dict[str, object] = {
        "name": name,
        "path": path,
        "type": kind,
        "unit": unit,
        "minimum": minimum,
        "maximum": maximum,
        "default": default,
    }
    if encoding is not None:
        item["encoding"] = encoding
    return item


FEATURES = [
    feature("air_temperature_c", "measurements.air_temperature_c.value", "number", "degC", -20.0, 60.0, 24.0),
    feature("relative_humidity_pct", "measurements.relative_humidity_pct.value", "number", "percent", 0.0, 100.0, 60.0),
    feature("co2_ppm", "measurements.co2_ppm.value", "number", "ppm", 250.0, 5000.0, 420.0),
    feature("outside_temperature_c", "measurements.outside_temperature_c.value", "number", "degC", -40.0, 60.0, 20.0),
    feature("outside_humidity_pct", "measurements.outside_humidity_pct.value", "number", "percent", 0.0, 100.0, 50.0),
    feature("air_temperature_valid", "measurements.air_temperature_c.valid", "boolean", "mask", 0.0, 1.0, 1.0),
    feature("air_temperature_fresh", "measurements.air_temperature_c.fresh", "boolean", "mask", 0.0, 1.0, 1.0),
    feature("relative_humidity_valid", "measurements.relative_humidity_pct.valid", "boolean", "mask", 0.0, 1.0, 1.0),
    feature("relative_humidity_fresh", "measurements.relative_humidity_pct.fresh", "boolean", "mask", 0.0, 1.0, 1.0),
    feature("co2_valid", "measurements.co2_ppm.valid", "boolean", "mask", 0.0, 1.0, 0.0),
    feature("co2_fresh", "measurements.co2_ppm.fresh", "boolean", "mask", 0.0, 1.0, 0.0),
    feature("outside_temperature_valid", "measurements.outside_temperature_c.valid", "boolean", "mask", 0.0, 1.0, 0.0),
    feature("outside_temperature_fresh", "measurements.outside_temperature_c.fresh", "boolean", "mask", 0.0, 1.0, 0.0),
    feature("outside_humidity_valid", "measurements.outside_humidity_pct.valid", "boolean", "mask", 0.0, 1.0, 0.0),
    feature("outside_humidity_fresh", "measurements.outside_humidity_pct.fresh", "boolean", "mask", 0.0, 1.0, 0.0),
    feature("air_vpd_kpa", "derived.air_vpd_kpa", "number", "kPa", 0.0, 6.0, 1.0),
    feature(
        "humidity_control_mode",
        "control.humidity_control_mode",
        "enum",
        "enum",
        0.0,
        1.0,
        0.0,
        {"RH": 0.0, "VPD": 1.0},
    ),
    feature("target_air_temperature_c", "targets.air_temperature_c", "number", "degC", 10.0, 40.0, 24.0),
    feature("target_relative_humidity_pct", "targets.relative_humidity_pct", "number", "percent", 20.0, 90.0, 60.0),
    feature("target_air_vpd_kpa", "targets.air_vpd_kpa", "number", "kPa", 0.2, 3.5, 1.2),
    feature("co2_control_enabled", "targets.co2_enabled", "boolean", "mask", 0.0, 1.0, 0.0),
    feature("target_co2_ppm", "targets.co2_ppm", "number", "ppm", 400.0, 2000.0, 800.0),
    feature("light_level", "schedule.light_level", "number", "ratio", 0.0, 1.0, 0.0),
    feature("temperature_rate_c_min", "trends.temperature_rate_c_min", "number", "degC/min", -5.0, 5.0, 0.0),
    feature("humidity_rate_pct_min", "trends.humidity_rate_pct_min", "number", "percent/min", -20.0, 20.0, 0.0),
    feature("co2_rate_ppm_min", "trends.co2_rate_ppm_min", "number", "ppm/min", -1000.0, 1000.0, 0.0),
    feature("previous_heater", "previous.heater", "number", "ratio", 0.0, 1.0, 0.0),
    feature("previous_cooler", "previous.cooler", "number", "ratio", 0.0, 1.0, 0.0),
    feature("previous_exhaust_fan", "previous.exhaust_fan", "number", "ratio", 0.0, 1.0, 0.0),
    feature("previous_humidifier", "previous.humidifier", "number", "ratio", 0.0, 1.0, 0.0),
    feature("previous_dehumidifier", "previous.dehumidifier", "number", "ratio", 0.0, 1.0, 0.0),
    feature("previous_co2_doser", "previous.co2_doser", "number", "ratio", 0.0, 1.0, 0.0),
    feature("heater_available", "capabilities.heater.available", "boolean", "mask", 0.0, 1.0, 1.0),
    feature("cooler_available", "capabilities.cooler.available", "boolean", "mask", 0.0, 1.0, 0.0),
    feature("exhaust_fan_available", "capabilities.exhaust_fan.available", "boolean", "mask", 0.0, 1.0, 1.0),
    feature("humidifier_available", "capabilities.humidifier.available", "boolean", "mask", 0.0, 1.0, 1.0),
    feature("dehumidifier_available", "capabilities.dehumidifier.available", "boolean", "mask", 0.0, 1.0, 0.0),
    feature("co2_doser_available", "capabilities.co2_doser.available", "boolean", "mask", 0.0, 1.0, 0.0),
]

ML_OUTPUT_NAMES = (
    "heater",
    "cooler",
    "exhaust_fan",
    "humidifier",
    "dehumidifier",
    "co2_doser",
)

ML_OUTPUTS = [
    {
        "name": name,
        "path": f"requests.{name}",
        "type": "number",
        "unit": "ratio",
        "minimum": 0.0,
        "maximum": 1.0,
        "default": 0.0,
    }
    for name in ML_OUTPUT_NAMES
]

SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "Growbox Climate-Only Environment Controller Contract",
    "schema_id": "environment-controller",
    "schema_version": 6,
    "status": "migration_target",
    "contract_id": "climate-mvp-v1",
    "draft_note": (
        "Climate-only successor to firmware v4. Browser v5 remains historical "
        "migration input and is not this contract."
    ),
    "migration": {
        "active_runtime_contract_during_stage_1": "schemas/environment-controller.json (v4)",
        "historical_browser_contract": "web/schema/environment-controller.v5.json (v5)",
        "target_contract": "schemas/environment-controller.v6.json (v6)",
        "activation_rule": (
            "Promote v6 to the single active root contract only after controller, "
            "simulator, encoder and tests have migrated."
        ),
    },
    "hash": {
        "algorithm": "sha256",
        "canonicalization": (
            "UTF-8 JSON with lexicographically sorted keys and separators ',' and ':'"
        ),
        "short_hex_characters": 12,
    },
    "measurement_contract": {
        "required": ["air_temperature_c", "relative_humidity_pct"],
        "optional": ["co2_ppm", "outside_temperature_c", "outside_humidity_pct"],
        "state_fields": ["value", "valid", "age_ms"],
        "ml_freshness_rule": (
            "fresh is derived deterministically from age_ms and configured sensor timeout; "
            "valid and fresh remain separate model features"
        ),
        "missing_value_rule": (
            "Never encode missing data as a meaningful zero. Numeric fallback/default is "
            "ignored unless valid and fresh indicate usability."
        ),
        "outside_co2_sensor": False,
    },
    "derived_values": ["air_vpd_kpa"],
    "product_output_roles": [
        "heater",
        "cooler",
        "exhaust_fan",
        "circulation_fan",
        "humidifier",
        "dehumidifier",
        "co2_doser",
        "light",
    ],
    "policy_boundary": {
        "ml_controlled_roles": list(ML_OUTPUT_NAMES),
        "deterministic_roles": ["circulation_fan", "light"],
        "light_semantics": (
            "scheduled normalized level 0..1 is an ML context/disturbance; "
            "ML v1 cannot command light"
        ),
        "circulation_fan_semantics": (
            "deterministic/configured in the single-zone MVP; it is not outside-air exchange"
        ),
        "safety_semantics": (
            "SafetySupervisor remains authoritative after policy output and is never replaced by ML"
        ),
    },
    "model": {
        "normalization": "minmax_to_zero_one",
        "feature_count": len(FEATURES),
        "features": FEATURES,
        "output_count": len(ML_OUTPUTS),
        "outputs": ML_OUTPUTS,
        "trend_window_target_s": 60.0,
        "feature_order_is_contractual": True,
        "output_order_is_contractual": True,
    },
    "future_extension_boundary": {
        "plant_irrigation": (
            "separate module/controller; do not add pot placeholders to climate ML v1"
        ),
        "new_ml_sensor_rule": (
            "A new sensor requires a deliberate model-contract version and benchmarked benefit."
        ),
    },
}

TEST_TEXT = '''from __future__ import annotations

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
'''


def update_frozen_docs() -> None:
    replacements = {
        ROOT / "docs/MVP_ENVIRONMENT_CONTROLLER.md": [
            ("Define climate-only contract/schema v5.", "Define climate-only contract/schema v6."),
            (
                "The exact JSON ordering is defined when schema v5 is implemented",
                "The exact JSON ordering is defined when schema v6 is implemented",
            ),
            (
                "Only after contract v5, climate simulator, teacher, dataset audit and closed-loop benchmark are green",
                "Only after contract v6, climate simulator, teacher, dataset audit and closed-loop benchmark are green",
            ),
        ],
        ROOT / "docs/MVP_REBUILD_CLEANUP_PLAN.md": [
            ("B. climate schema v5", "B. climate schema v6"),
            (
                "then implement the climate-only schema/contract v5 as the first behavioral migration step.",
                "then implement the climate-only schema/contract v6 as the first behavioral migration step.",
            ),
        ],
    }
    for path, pairs in replacements.items():
        text = path.read_text(encoding="utf-8")
        for old, new in pairs:
            count = text.count(old)
            if count != 1:
                raise SystemExit(
                    f"{path}: expected one occurrence of {old!r}, got {count}"
                )
            text = text.replace(old, new, 1)
        text = "\n".join(line.rstrip() for line in text.splitlines()) + "\n"
        path.write_text(text, encoding="utf-8")


def main() -> None:
    (ROOT / "schemas/environment-controller.v6.json").write_text(
        json.dumps(SCHEMA, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (ROOT / "tests/test_mvp_contract_v6.py").write_text(TEST_TEXT, encoding="utf-8")
    update_frozen_docs()
    print(f"generated features={len(FEATURES)} outputs={len(ML_OUTPUTS)}")


if __name__ == "__main__":
    main()
