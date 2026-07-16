"""Contract-shaped scenario payloads for training, serial replay, and panel.

Lives under tools.ml so ML and serial tools do not depend on the panel package.
Panel re-exports these symbols for UI compatibility.
"""

from __future__ import annotations

from typing import Any

from .contract import ACTIVE_CONTRACT_PATH, Contract, load_contract

INACTIVE_POT_PRESET: dict[str, Any] = {
    "available": False,
    "sensors": {"soil_moisture_pct": 50.0, "soil_temperature_c": 20.0},
    "validity": {"soil_moisture_pct": False, "soil_temperature_c": False},
    "cultivation": {
        "pot_volume_l": 10.0,
        "substrate_water_capacity_ml": 3000.0,
        "transpiration_factor": 1.0,
    },
    "targets": {"soil_moisture_pct": 50.0, "soil_temperature_c": 20.0},
    "irrigation": {
        "available": False,
        "flow_ml_s": 0.0,
        "maximum_pulse_s": 0.0,
        "minimum_interval_s": 0.0,
        "control_type": "binary",
    },
    "heat_mat": {
        "available": False,
        "max_power_w": 0.0,
        "control_type": "binary",
    },
    "previous": {"irrigation": 0.0, "heat_mat": 0.0},
}

ACTIVE_POT_PRESET: dict[str, Any] = {
    "available": True,
    "sensors": {"soil_moisture_pct": 44.0, "soil_temperature_c": 22.0},
    "validity": {"soil_moisture_pct": True, "soil_temperature_c": True},
    "cultivation": {
        "pot_volume_l": 12.0,
        "substrate_water_capacity_ml": 3600.0,
        "transpiration_factor": 1.0,
    },
    "targets": {"soil_moisture_pct": 50.0, "soil_temperature_c": 22.0},
    "irrigation": {
        "available": True,
        "flow_ml_s": 22.0,
        "maximum_pulse_s": 4.0,
        "minimum_interval_s": 600.0,
        "control_type": "binary",
    },
    "heat_mat": {
        "available": False,
        "max_power_w": 0.0,
        "control_type": "binary",
    },
    "previous": {"irrigation": 0.0, "heat_mat": 0.0},
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
    "pots": [
        {
            "available": True,
            "sensors": {"soil_moisture_pct": 44.0, "soil_temperature_c": 20.0},
            "validity": {"soil_moisture_pct": True, "soil_temperature_c": True},
            "cultivation": {
                "pot_volume_l": 12.0,
                "substrate_water_capacity_ml": 3600.0,
                "transpiration_factor": 1.0,
            },
            "targets": {"soil_moisture_pct": 50.0, "soil_temperature_c": 22.0},
            "irrigation": {
                "available": True,
                "flow_ml_s": 22.0,
                "maximum_pulse_s": 4.0,
                "minimum_interval_s": 600.0,
                "control_type": "binary",
            },
            "heat_mat": {
                "available": False,
                "max_power_w": 0.0,
                "control_type": "binary",
            },
            "previous": {"irrigation": 0.0, "heat_mat": 0.0},
        },
        dict(INACTIVE_POT_PRESET),
        dict(INACTIVE_POT_PRESET),
        dict(INACTIVE_POT_PRESET),
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
        "dehumidifier": {
            "available": False,
            "max_removal_g_h": 80.0,
            "control_type": "binary",
        },
        "cooler": {
            "available": False,
            "max_cooling_w": 200.0,
            "control_type": "binary",
        },
        "co2_doser": {
            "available": False,
            "dose_ppm_per_full_pulse": 120.0,
            # Match safety_defaults.co2_doser_maximum_pulse_s when doser is enabled
            "maximum_pulse_s": 5.0,
            "control_type": "binary",
        },
        "nutrient_heater": {
            "available": False,
            "max_power_w": 0.0,
            "efficiency": 0.0,
            "control_type": "binary",
        },
    },
    "targets": {
        "air_temperature_c": 25.0,
        "air_humidity_pct": 65.0,
        "co2_ppm": 850.0,
        "nutrient_solution_temperature_c": 20.0,
    },
    "previous": {
        "heater": 0.0,
        "fan": 0.0,
        "humidifier": 0.0,
        "dehumidifier": 0.0,
        "cooler": 0.0,
        "co2_doser": 0.0,
        "nutrient_heater": 0.0,
    },
}

SCENARIO_PRESETS: dict[str, dict[str, Any]] = {
    "nominal": {
        "title": "Nominalny (1 strefa)",
        "description": "Domyślny profil: strefa 0 aktywna, grzałka/fan/nawilżacz włączone.",
        "overlay": NOMINAL_PRESET,
    },
    "all_pots": {
        "title": "4 strefy aktywne",
        "description": "Wszystkie donice i pompy włączone — test mix & match 0–4.",
        "overlay": {
            "pots": [dict(ACTIVE_POT_PRESET) for _ in range(4)],
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
            "pots": [
                {
                    **ACTIVE_POT_PRESET,
                    "irrigation": {**ACTIVE_POT_PRESET["irrigation"], "available": False},
                },
                dict(INACTIVE_POT_PRESET),
                dict(INACTIVE_POT_PRESET),
                dict(INACTIVE_POT_PRESET),
            ],
        },
    },
    "saturated_soil": {
        "title": "Gleba nasączona",
        "description": "Wilgotność gleby ≥ cel — safety blokuje podlewanie strefy 0.",
        "overlay": {
            "pots": [
                {
                    **ACTIVE_POT_PRESET,
                    "sensors": {"soil_moisture_pct": 58.0, "soil_temperature_c": 24.0},
                    "targets": {"soil_moisture_pct": 50.0},
                },
                dict(INACTIVE_POT_PRESET),
                dict(INACTIVE_POT_PRESET),
                dict(INACTIVE_POT_PRESET),
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
            "pots": [dict(INACTIVE_POT_PRESET) for _ in range(4)],
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
                    # Keep actuator pulse ≥ safety.co2_doser_maximum_pulse_s (default 5.0)
                    "maximum_pulse_s": 5.0,
                },
            },
            "targets": {"co2_ppm": 900.0},
        },
    },
}

# Global actuator control_type fields used by panel/serial payloads.
# They are not ML features on v3 (encoder ignores them) but firmware/UI need them.
ACTUATOR_CONTROL_FIELDS: tuple[tuple[str, str, str], ...] = (
    ("heater_control_type", "actuators.heater.control_type", "binary"),
    ("fan_control_type", "actuators.fan.control_type", "pwm"),
    ("humidifier_control_type", "actuators.humidifier.control_type", "binary"),
    ("dehumidifier_control_type", "actuators.dehumidifier.control_type", "binary"),
    ("cooler_control_type", "actuators.cooler.control_type", "binary"),
    ("co2_doser_control_type", "actuators.co2_doser.control_type", "binary"),
    ("nutrient_heater_control_type", "actuators.nutrient_heater.control_type", "binary"),
)

# Backward-compatible name used by panel form metadata.
PANEL_ACTUATOR_CONTROL_FIELDS = ACTUATOR_CONTROL_FIELDS


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
        if key == "pots" and isinstance(value, list):
            merged[key] = [dict(pot) for pot in value]
        elif isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _normalize_pots(scenario: dict[str, Any]) -> None:
    pots = scenario.get("pots")
    if isinstance(pots, dict):
        scenario["pots"] = [dict(pots.get(str(index), INACTIVE_POT_PRESET)) for index in range(4)]
    elif isinstance(pots, list):
        normalized = [dict(pot) for pot in pots]
        while len(normalized) < 4:
            normalized.append(dict(INACTIVE_POT_PRESET))
        scenario["pots"] = normalized[:4]


def default_scenario(
    *,
    seed: int = 101,
    preset: str = "nominal",
    contract: Contract | None = None,
) -> dict[str, Any]:
    """Build a full controller-input scenario from the active contract + preset."""
    contract = contract or load_contract(ACTIVE_CONTRACT_PATH)
    scenario: dict[str, Any] = {"seed": seed}
    for feature in contract.features:
        path = feature.path
        # Contract stores mask/bool features as 0/1 floats; wire protocol needs JSON bools.
        # Paths include top-level validity.* and per-pot pots.N.validity.*.
        is_validity = path.startswith("validity.") or ".validity." in path
        is_available = path.endswith(".available")
        is_lights = path.endswith("lights_active") or path == "pseudo.lights_active"
        if is_validity or is_available or is_lights:
            _set_nested(scenario, path, feature.default >= 0.5)
        elif feature.encoding is not None:
            default_name = next(
                (name for name, encoded in feature.encoding.items() if encoded == feature.default),
                "binary",
            )
            _set_nested(scenario, path, default_name)
        else:
            _set_nested(scenario, path, feature.default)
    # Always start from a complete nominal demo profile so partial preset overlays
    # (all_pots, co2_high, …) keep finite actuators/sensors/validity for firmware.
    scenario = _deep_merge(scenario, NOMINAL_PRESET)
    if preset != "nominal":
        preset_overlay = SCENARIO_PRESETS.get(preset, {}).get("overlay")
        if preset_overlay is None:
            raise ValueError(f"unknown scenario preset: {preset}")
        scenario = _deep_merge(scenario, preset_overlay)
    safety_defaults = contract.document.get("safety_defaults", {})
    if safety_defaults:
        scenario = _deep_merge(scenario, {"safety": dict(safety_defaults)})
    for _, path, default_name in ACTUATOR_CONTROL_FIELDS:
        _set_nested(scenario, path, default_name)
    _normalize_pots(scenario)
    # Ensure pot targets keep soil temperature when overlays omit it.
    for pot in scenario.get("pots", []):
        if not isinstance(pot, dict):
            continue
        targets = pot.setdefault("targets", {})
        if "soil_temperature_c" not in targets:
            sensors = pot.get("sensors") or {}
            targets["soil_temperature_c"] = float(sensors.get("soil_temperature_c", 20.0))
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
