"""Build panel form metadata and default scenario payloads from contract v1."""

from __future__ import annotations

from typing import Any

from tools.ml.contract import Contract, load_contract

NOMINAL_PRESET: dict[str, Any] = {
    "sensors": {
        "air_temperature_c": 22.0,
        "air_humidity_pct": 58.0,
        "co2_ppm": 920.0,
        "soil_moisture_pct": 44.0,
        "outside_temperature_c": 18.0,
        "outside_humidity_pct": 52.0,
        "outside_co2_ppm": 420.0,
    },
    "validity": {
        "air_temperature_c": True,
        "air_humidity_pct": True,
        "co2_ppm": True,
        "soil_moisture_pct": True,
        "outside_temperature_c": True,
        "outside_humidity_pct": True,
        "outside_co2_ppm": True,
    },
    "environment": {
        "growbox_volume_m3": 1.2,
        "thermal_mass_j_per_k": 48000.0,
        "heat_loss_w_per_k": 7.0,
        "air_leak_rate_ach": 0.25,
    },
    "cultivation": {
        "pot_volume_l": 12.0,
        "substrate_water_capacity_ml": 3600.0,
        "transpiration_factor": 1.0,
    },
    "actuators": {
        "heater": {
            "available": True,
            "max_power_w": 180.0,
            "efficiency": 0.9,
            "control_type": "binary",
        },
        "fan": {
            "available": True,
            "max_airflow_m3_h": 120.0,
            "minimum_command": 0.2,
            "control_type": "pwm",
        },
        "humidifier": {
            "available": True,
            "max_output_g_h": 180.0,
            "control_type": "binary",
        },
        "irrigation": {
            "available": True,
            "flow_ml_s": 22.0,
            "maximum_pulse_s": 4.0,
            "minimum_interval_s": 600.0,
            "control_type": "binary",
        },
    },
    "targets": {
        "air_temperature_c": 25.0,
        "air_humidity_pct": 65.0,
        "co2_ppm": 850.0,
        "soil_moisture_pct": 50.0,
    },
    "previous": {"heater": 0.0, "fan": 0.0, "humidifier": 0.0, "irrigation": 0.0},
}

SAFETY_FIELD_ORDER = (
    "maximum_air_temperature_c",
    "alarm_air_temperature_c",
    "alarm_minimum_fan",
    "binary_threshold",
    "heater_minimum_on_s",
    "heater_minimum_off_s",
    "humidifier_minimum_on_s",
    "humidifier_minimum_off_s",
)

SAFETY_FIELD_BOUNDS: dict[str, tuple[float, float]] = {
    "maximum_air_temperature_c": (-20.0, 60.0),
    "alarm_air_temperature_c": (-20.0, 60.0),
    "alarm_minimum_fan": (0.0, 1.0),
    "binary_threshold": (0.0, 1.0),
    "heater_minimum_on_s": (0.0, 86400.0),
    "heater_minimum_off_s": (0.0, 86400.0),
    "humidifier_minimum_on_s": (0.0, 86400.0),
    "humidifier_minimum_off_s": (0.0, 86400.0),
}

SECTION_ORDER = (
    "connection",
    "sensors",
    "validity",
    "environment",
    "cultivation",
    "actuators",
    "targets",
    "safety",
    "previous",
)

SECTION_TITLES = {
    "connection": "Połączenie i runtime",
    "sensors": "Czujniki",
    "validity": "Ważność czujników",
    "environment": "Parametry growboxa",
    "cultivation": "Uprawa / doniczka",
    "actuators": "Aktuary",
    "targets": "Cele",
    "safety": "Limity safety",
    "previous": "Poprzedni stan aktuatorów",
}


def _safety_fields(contract: Contract) -> list[dict[str, Any]]:
    defaults = contract.document.get("safety_defaults", {})
    fields: list[dict[str, Any]] = []
    for name in SAFETY_FIELD_ORDER:
        if name not in defaults:
            continue
        minimum, maximum = SAFETY_FIELD_BOUNDS.get(name, (0.0, 1.0))
        fields.append(
            {
                "name": name,
                "path": f"safety.{name}",
                "label": name,
                "type": "number",
                "minimum": minimum,
                "maximum": maximum,
                "default": float(defaults[name]),
            }
        )
    return fields


def _set_nested(document: dict[str, Any], path: str, value: Any) -> None:
    parts = path.split(".")
    current: dict[str, Any] = document
    for part in parts[:-1]:
        next_value = current.get(part)
        if not isinstance(next_value, dict):
            next_value = {}
            current[part] = next_value
        current = next_value
    current[parts[-1]] = value


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def default_scenario(*, seed: int = 101, preset: str = "nominal") -> dict[str, Any]:
    contract = load_contract()
    scenario: dict[str, Any] = {"seed": seed}
    for feature in contract.features:
        path = feature.path
        if path.startswith("validity."):
            _set_nested(scenario, path, feature.default >= 0.5)
        elif feature.encoding is not None:
            default_name = next(
                (name for name, encoded in feature.encoding.items() if encoded == feature.default),
                "binary",
            )
            _set_nested(scenario, path, default_name)
        elif path.endswith(".available"):
            _set_nested(scenario, path, feature.default >= 0.5)
        else:
            _set_nested(scenario, path, feature.default)
    if preset == "nominal":
        scenario = _deep_merge(scenario, NOMINAL_PRESET)
    safety_defaults = contract.document.get("safety_defaults", {})
    if safety_defaults:
        scenario = _deep_merge(scenario, {"safety": dict(safety_defaults)})
    scenario["seed"] = seed
    return scenario


def _field_type(feature_path: str, encoding: dict[str, float] | None) -> str:
    if encoding is not None:
        return "enum"
    if feature_path.endswith(".available") or feature_path.startswith("validity."):
        return "boolean"
    return "number"


def _section_for_path(path: str) -> str:
    if path.startswith("sensors."):
        return "sensors"
    if path.startswith("validity."):
        return "validity"
    if path.startswith("environment."):
        return "environment"
    if path.startswith("cultivation."):
        return "cultivation"
    if path.startswith("actuators."):
        return "actuators"
    if path.startswith("targets."):
        return "targets"
    if path.startswith("previous."):
        return "previous"
    return "other"


def build_panel_schema(contract: Contract | None = None) -> dict[str, Any]:
    contract = contract or load_contract()
    sections: dict[str, list[dict[str, Any]]] = {key: [] for key in SECTION_ORDER}
    sections["other"] = []

    for index, feature in enumerate(contract.features):
        section = _section_for_path(feature.path)
        field: dict[str, Any] = {
            "feature_index": index,
            "name": feature.name,
            "path": feature.path,
            "label": feature.name,
            "type": _field_type(feature.path, feature.encoding),
            "minimum": feature.minimum,
            "maximum": feature.maximum,
            "default": feature.default,
        }
        if feature.encoding is not None:
            field["options"] = [
                {"value": name, "encoded": encoded} for name, encoded in feature.encoding.items()
            ]
        sections.setdefault(section, []).append(field)

    ordered_sections = []
    for section_id in SECTION_ORDER:
        fields = sections.get(section_id, [])
        if not fields:
            continue
        ordered_sections.append(
            {
                "id": section_id,
                "title": SECTION_TITLES.get(section_id, section_id),
                "fields": fields,
            }
        )

    safety_fields = _safety_fields(contract)
    if safety_fields:
        ordered_sections.append(
            {
                "id": "safety",
                "title": SECTION_TITLES["safety"],
                "fields": safety_fields,
            }
        )

    safety = contract.document.get("safety_defaults", {})
    return {
        "schema_version": contract.schema_version,
        "schema_hash": contract.short_hash,
        "feature_count": len(contract.features),
        "outputs": list(contract.outputs),
        "safety_defaults": safety,
        "sections": ordered_sections,
        "default_scenario": default_scenario(),
    }
