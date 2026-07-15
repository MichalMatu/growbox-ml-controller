"""Build panel form metadata and default scenario payloads from contract v2."""

from __future__ import annotations

import re
from typing import Any

from tools.ml.contract import V2_CONTRACT_PATH, Contract, load_contract

INACTIVE_ZONE_PRESET: dict[str, Any] = {
    "available": False,
    "sensors": {"soil_moisture_pct": 50.0, "soil_temperature_c": 20.0},
    "validity": {"soil_moisture_pct": False, "soil_temperature_c": False},
    "cultivation": {
        "pot_volume_l": 10.0,
        "substrate_water_capacity_ml": 3000.0,
        "transpiration_factor": 1.0,
    },
    "targets": {"soil_moisture_pct": 50.0},
    "irrigation": {
        "available": False,
        "flow_ml_s": 0.0,
        "maximum_pulse_s": 0.0,
        "minimum_interval_s": 0.0,
        "control_type": "binary",
    },
    "previous": {"irrigation": 0.0},
}

NOMINAL_PRESET: dict[str, Any] = {
    "sensors": {
        "air_temperature_c": 22.0,
        "air_humidity_pct": 58.0,
        "co2_ppm": 920.0,
        "nutrient_solution_temperature_c": 20.0,
        "outside_temperature_c": 18.0,
        "outside_humidity_pct": 52.0,
        "outside_co2_ppm": 420.0,
    },
    "validity": {
        "air_temperature_c": True,
        "air_humidity_pct": True,
        "co2_ppm": True,
        "nutrient_solution_temperature_c": True,
        "outside_temperature_c": True,
        "outside_humidity_pct": True,
        "outside_co2_ppm": True,
    },
    "zones": [
        {
            "available": True,
            "sensors": {"soil_moisture_pct": 44.0, "soil_temperature_c": 20.0},
            "validity": {"soil_moisture_pct": True, "soil_temperature_c": True},
            "cultivation": {
                "pot_volume_l": 12.0,
                "substrate_water_capacity_ml": 3600.0,
                "transpiration_factor": 1.0,
            },
            "targets": {"soil_moisture_pct": 50.0},
            "irrigation": {
                "available": True,
                "flow_ml_s": 22.0,
                "maximum_pulse_s": 4.0,
                "minimum_interval_s": 600.0,
                "control_type": "binary",
            },
            "previous": {"irrigation": 0.0},
        },
        dict(INACTIVE_ZONE_PRESET),
        dict(INACTIVE_ZONE_PRESET),
        dict(INACTIVE_ZONE_PRESET),
    ],
    "pseudo": {"lights_active": False},
    "environment": {
        "growbox_volume_m3": 1.2,
        "thermal_mass_j_per_k": 48000.0,
        "heat_loss_w_per_k": 7.0,
        "air_leak_rate_ach": 0.25,
    },
    "actuators": {
        "heater": {
            "available": True,
            "max_power_w": 180.0,
            "efficiency": 0.9,
        },
        "fan": {
            "available": True,
            "max_airflow_m3_h": 120.0,
            "minimum_command": 0.2,
        },
        "humidifier": {
            "available": True,
            "max_output_g_h": 180.0,
        },
        "dehumidifier": {
            "available": False,
            "max_removal_g_h": 80.0,
        },
        "cooler": {
            "available": False,
            "max_cooling_w": 200.0,
        },
        "co2_doser": {
            "available": False,
            "dose_ppm_per_full_pulse": 120.0,
            "maximum_pulse_s": 3.0,
        },
    },
    "targets": {
        "air_temperature_c": 25.0,
        "air_humidity_pct": 65.0,
        "co2_ppm": 850.0,
    },
    "previous": {
        "heater": 0.0,
        "fan": 0.0,
        "humidifier": 0.0,
        "dehumidifier": 0.0,
        "cooler": 0.0,
        "co2_doser": 0.0,
    },
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
    "dehumidifier_minimum_on_s",
    "dehumidifier_minimum_off_s",
    "cooler_minimum_on_s",
    "cooler_minimum_off_s",
    "co2_doser_minimum_interval_s",
    "co2_doser_maximum_pulse_s",
    "fan_venting_co2_threshold",
    "maximum_nutrient_soil_delta_c",
    "minimum_nutrient_solution_temperature_c",
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
    "dehumidifier_minimum_on_s": (0.0, 86400.0),
    "dehumidifier_minimum_off_s": (0.0, 86400.0),
    "cooler_minimum_on_s": (0.0, 86400.0),
    "cooler_minimum_off_s": (0.0, 86400.0),
    "co2_doser_minimum_interval_s": (0.0, 86400.0),
    "co2_doser_maximum_pulse_s": (0.0, 60.0),
    "fan_venting_co2_threshold": (0.0, 1.0),
    "maximum_nutrient_soil_delta_c": (0.0, 30.0),
    "minimum_nutrient_solution_temperature_c": (-10.0, 50.0),
}

ACTIVE_ZONE_PRESET: dict[str, Any] = {
    "available": True,
    "sensors": {"soil_moisture_pct": 44.0, "soil_temperature_c": 22.0},
    "validity": {"soil_moisture_pct": True, "soil_temperature_c": True},
    "cultivation": {
        "pot_volume_l": 12.0,
        "substrate_water_capacity_ml": 3600.0,
        "transpiration_factor": 1.0,
    },
    "targets": {"soil_moisture_pct": 50.0},
    "irrigation": {
        "available": True,
        "flow_ml_s": 22.0,
        "maximum_pulse_s": 4.0,
        "minimum_interval_s": 600.0,
        "control_type": "binary",
    },
    "previous": {"irrigation": 0.0},
}

SCENARIO_PRESETS: dict[str, dict[str, Any]] = {
    "nominal": {
        "title": "Nominalny (1 strefa)",
        "description": "Domyślny profil: strefa 0 aktywna, grzałka/fan/nawilżacz włączone.",
        "overlay": NOMINAL_PRESET,
    },
    "all_zones": {
        "title": "4 strefy aktywne",
        "description": "Wszystkie donice i pompy włączone — test mix & match 0–4.",
        "overlay": {
            "zones": [dict(ACTIVE_ZONE_PRESET) for _ in range(4)],
        },
    },
    "disabled_actuators": {
        "title": "Wyłączone aktuary",
        "description": "Tylko fan dostępny — safety wymusza 0 na pozostałych wyjściach.",
        "overlay": {
            "actuators": {
                "heater": {"available": False, "max_power_w": 0.0, "efficiency": 0.0},
                "fan": {"available": True, "max_airflow_m3_h": 120.0, "minimum_command": 0.2},
                "humidifier": {"available": False, "max_output_g_h": 0.0},
                "dehumidifier": {"available": False, "max_removal_g_h": 0.0},
                "cooler": {"available": False, "max_cooling_w": 0.0},
                "co2_doser": {
                    "available": False,
                    "dose_ppm_per_full_pulse": 0.0,
                    "maximum_pulse_s": 0.0,
                },
            },
            "zones": [
                {
                    **ACTIVE_ZONE_PRESET,
                    "irrigation": {**ACTIVE_ZONE_PRESET["irrigation"], "available": False},
                },
                dict(INACTIVE_ZONE_PRESET),
                dict(INACTIVE_ZONE_PRESET),
                dict(INACTIVE_ZONE_PRESET),
            ],
        },
    },
    "saturated_soil": {
        "title": "Gleba nasączona",
        "description": "Wilgotność gleby ≥ cel — safety blokuje podlewanie strefy 0.",
        "overlay": {
            "zones": [
                {
                    **ACTIVE_ZONE_PRESET,
                    "sensors": {"soil_moisture_pct": 58.0, "soil_temperature_c": 24.0},
                    "targets": {"soil_moisture_pct": 50.0},
                },
                dict(INACTIVE_ZONE_PRESET),
                dict(INACTIVE_ZONE_PRESET),
                dict(INACTIVE_ZONE_PRESET),
            ],
            "sensors": {"nutrient_solution_temperature_c": 10.0},
            "validity": {"nutrient_solution_temperature_c": True},
        },
    },
    "minimal_sensors": {
        "title": "Minimalne czujniki",
        "description": "Tylko T/RH powietrza valid — CO₂, gleba i zewnętrzne wyłączone.",
        "overlay": {
            "validity": {
                "air_temperature_c": True,
                "air_humidity_pct": True,
                "co2_ppm": False,
                "nutrient_solution_temperature_c": False,
                "outside_temperature_c": False,
                "outside_humidity_pct": False,
                "outside_co2_ppm": False,
            },
            "zones": [dict(INACTIVE_ZONE_PRESET) for _ in range(4)],
        },
    },
    "co2_high": {
        "title": "CO₂ ≥ cel",
        "description": "Stężenie CO₂ powyżej celu — safety blokuje dozowanie.",
        "overlay": {
            "sensors": {"co2_ppm": 1200.0},
            "validity": {"co2_ppm": True},
            "actuators": {
                "co2_doser": {
                    "available": True,
                    "dose_ppm_per_full_pulse": 120.0,
                    "maximum_pulse_s": 3.0,
                },
            },
            "targets": {"co2_ppm": 900.0},
        },
    },
}

SECTION_ORDER = (
    "connection",
    "sensors",
    "validity",
    "zones",
    "pseudo",
    "environment",
    "actuators",
    "targets",
    "safety",
    "previous",
)

SECTION_TITLES = {
    "connection": "Połączenie i runtime",
    "sensors": "Czujniki",
    "validity": "Ważność czujników",
    "zones": "Strefy uprawy",
    "pseudo": "Wejścia pseudo",
    "environment": "Parametry growboxa",
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
        if key == "zones" and isinstance(value, list):
            merged[key] = [dict(zone) for zone in value]
        elif isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _normalize_zones(scenario: dict[str, Any]) -> None:
    zones = scenario.get("zones")
    if isinstance(zones, dict):
        scenario["zones"] = [
            dict(zones.get(str(index), INACTIVE_ZONE_PRESET)) for index in range(4)
        ]
    elif isinstance(zones, list):
        normalized = [dict(zone) for zone in zones]
        while len(normalized) < 4:
            normalized.append(dict(INACTIVE_ZONE_PRESET))
        scenario["zones"] = normalized[:4]


def default_scenario(*, seed: int = 101, preset: str = "nominal") -> dict[str, Any]:
    contract = load_contract(V2_CONTRACT_PATH)
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
    preset_overlay = SCENARIO_PRESETS.get(preset, {}).get("overlay")
    if preset_overlay is not None:
        scenario = _deep_merge(scenario, preset_overlay)
    elif preset == "nominal":
        scenario = _deep_merge(scenario, NOMINAL_PRESET)
    safety_defaults = contract.document.get("safety_defaults", {})
    if safety_defaults:
        scenario = _deep_merge(scenario, {"safety": dict(safety_defaults)})
    _normalize_zones(scenario)
    scenario["seed"] = seed
    return scenario


def list_scenario_presets() -> list[dict[str, str]]:
    return [
        {
            "id": preset_id,
            "title": str(meta["title"]),
            "description": str(meta["description"]),
        }
        for preset_id, meta in SCENARIO_PRESETS.items()
    ]


def _field_type(feature_path: str, encoding: dict[str, float] | None) -> str:
    if encoding is not None:
        return "enum"
    if feature_path.endswith(".available") or feature_path.startswith("validity."):
        return "boolean"
    return "number"


def _section_for_path(path: str) -> str:
    if path.startswith("pseudo."):
        return "pseudo"
    if re.match(r"zones\.\d+", path):
        return "zones"
    if path.startswith("sensors."):
        return "sensors"
    if path.startswith("validity."):
        return "validity"
    if path.startswith("environment."):
        return "environment"
    if path.startswith("actuators."):
        return "actuators"
    if path.startswith("targets."):
        return "targets"
    if path.startswith("previous."):
        return "previous"
    return "other"


def build_panel_schema(contract: Contract | None = None) -> dict[str, Any]:
    contract = contract or load_contract(V2_CONTRACT_PATH)
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
        "presets": list_scenario_presets(),
    }
