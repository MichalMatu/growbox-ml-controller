"""Build panel form metadata from contract v3.

Scenario payloads live in ``tools.ml.scenario_payload`` so ML/serial paths do not
import the panel package. This module re-exports them for panel API compatibility.
"""

from __future__ import annotations

import re
from typing import Any

from tools.ml.contract import ACTIVE_CONTRACT_PATH, Contract, load_contract
from tools.ml.scenario_payload import (
    ACTIVE_ZONE_PRESET,
    INACTIVE_ZONE_PRESET,
    NOMINAL_PRESET,
    PANEL_ACTUATOR_CONTROL_FIELDS,
    SCENARIO_PRESETS,
    default_scenario,
    list_scenario_presets,
)

__all__ = [
    "ACTIVE_ZONE_PRESET",
    "INACTIVE_ZONE_PRESET",
    "NOMINAL_PRESET",
    "PANEL_ACTUATOR_CONTROL_FIELDS",
    "SCENARIO_PRESETS",
    "SECTION_ORDER",
    "SECTION_TITLES",
    "build_panel_schema",
    "default_scenario",
    "list_scenario_presets",
]

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


def _field_type(feature_path: str, encoding: dict[str, float] | None) -> str:
    if encoding is not None:
        return "enum"
    # Checkbox-backed flags in the panel (not continuous measurements).
    if (
        feature_path.endswith(".available")
        or feature_path.startswith("validity.")
        or ".validity." in feature_path
        or feature_path.endswith(".lights_active")
        or feature_path == "pseudo.lights_active"
    ):
        return "boolean"
    return "number"


_BINARY_PWM_ENCODING: dict[str, float] = {"binary": 0.0, "pwm": 1.0}


def _panel_actuator_control_fields() -> list[dict[str, Any]]:
    fields: list[dict[str, Any]] = []
    for name, path, default_name in PANEL_ACTUATOR_CONTROL_FIELDS:
        default_encoded = _BINARY_PWM_ENCODING[default_name]
        fields.append(
            {
                "feature_index": -1,
                "name": name,
                "path": path,
                "label": name,
                "type": "enum",
                "minimum": 0.0,
                "maximum": 1.0,
                "default": default_encoded,
                "options": [
                    {"value": option, "encoded": encoded}
                    for option, encoded in _BINARY_PWM_ENCODING.items()
                ],
            }
        )
    return fields


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
    contract = contract or load_contract(ACTIVE_CONTRACT_PATH)
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

    sections["actuators"].extend(_panel_actuator_control_fields())

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
