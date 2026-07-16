"""Build controller-input JSON records from simulator state (training path).

This is the bridge between physics state (simulator) and the feature encoder
(contract). Kept separate from dataset generation so a standalone growbox
simulation script can import only this module + simulator + contract.
"""

from __future__ import annotations

from collections.abc import Mapping

from .simulator_v2 import (
    MAX_ZONES,
    ControlAction,
    EnvironmentState,
    Scenario,
)

GLOBAL_SENSOR_NAMES = (
    "air_temperature_c",
    "air_humidity_pct",
    "co2_ppm",
    "nutrient_solution_temperature_c",
    "outside_temperature_c",
    "outside_humidity_pct",
    "outside_co2_ppm",
)

ZONE_SENSOR_NAMES = ("soil_moisture_pct", "soil_temperature_c")


def controller_input_record(
    scenario: Scenario,
    state: EnvironmentState,
    *,
    validity: Mapping[str, bool],
    zone_validity: Mapping[int, Mapping[str, bool]],
    previous: ControlAction,
) -> dict[str, object]:
    """Map simulator observation + scenario config into a contract-shaped dict."""
    sensors = {
        "air_temperature_c": state.air_temperature_c,
        "air_humidity_pct": state.air_humidity_pct,
        "co2_ppm": state.co2_ppm,
        "nutrient_solution_temperature_c": state.nutrient_solution_temperature_c,
        "outside_temperature_c": state.outside_temperature_c,
        "outside_humidity_pct": state.outside_humidity_pct,
        "outside_co2_ppm": state.outside_co2_ppm,
    }
    for name in GLOBAL_SENSOR_NAMES:
        if not validity.get(name, True):
            if name not in sensors:
                continue
            sensors.pop(name, None)

    zones_payload: list[dict[str, object]] = []
    for zone_index, zone in enumerate(scenario.zones):
        zone_state = state.zones[zone_index]
        zone_valid = zone_validity.get(zone_index, {})
        zone_sensors: dict[str, float] = {}
        if zone_valid.get("soil_moisture_pct", False):
            zone_sensors["soil_moisture_pct"] = zone_state.soil_moisture_pct
        if zone_valid.get("soil_temperature_c", False):
            zone_sensors["soil_temperature_c"] = zone_state.soil_temperature_c
        irrigation = zone.irrigation
        heat_mat = zone.heat_mat
        irrigation_name = f"irrigation_zone_{zone_index + 1}"
        heat_mat_name = f"heat_mat_zone_{zone_index + 1}"
        zones_payload.append(
            {
                "available": zone.available,
                "sensors": zone_sensors,
                "validity": {
                    "soil_moisture_pct": bool(zone_valid.get("soil_moisture_pct", False)),
                    "soil_temperature_c": bool(zone_valid.get("soil_temperature_c", False)),
                },
                "cultivation": {
                    "pot_volume_l": zone.cultivation.pot_volume_l,
                    "substrate_water_capacity_ml": zone.cultivation.substrate_water_capacity_ml,
                    "transpiration_factor": zone.cultivation.transpiration_factor,
                },
                "targets": {
                    "soil_moisture_pct": zone.target_soil_moisture_pct,
                    "soil_temperature_c": zone.target_soil_temperature_c,
                },
                "irrigation": {
                    "available": irrigation.available,
                    "flow_ml_s": irrigation.flow_ml_s,
                    "maximum_pulse_s": irrigation.maximum_pulse_s,
                    "minimum_interval_s": irrigation.minimum_interval_s,
                    "control_type": "pwm",
                },
                "heat_mat": {
                    "available": heat_mat.available,
                    "max_power_w": heat_mat.max_power_w,
                    "control_type": "binary",
                },
                "previous": {
                    "irrigation": getattr(previous, irrigation_name),
                    "heat_mat": getattr(previous, heat_mat_name),
                },
            }
        )

    caps = scenario.actuators
    return {
        "sensors": sensors,
        "validity": {
            "air_temperature_c": bool(validity.get("air_temperature_c", True)),
            "air_humidity_pct": bool(validity.get("air_humidity_pct", True)),
            "co2_ppm": bool(validity.get("co2_ppm", scenario.validity.co2_ppm)),
            "nutrient_solution_temperature_c": bool(
                validity.get(
                    "nutrient_solution_temperature_c",
                    scenario.validity.nutrient_solution_temperature_c,
                )
            ),
            "outside_temperature_c": bool(validity.get("outside_temperature_c", True)),
            "outside_humidity_pct": bool(validity.get("outside_humidity_pct", True)),
            "outside_co2_ppm": bool(
                validity.get("outside_co2_ppm", scenario.validity.outside_co2_ppm)
            ),
        },
        "environment": {
            "growbox_volume_m3": scenario.environment.growbox_volume_m3,
            "thermal_mass_j_per_k": scenario.environment.thermal_mass_j_per_k,
            "heat_loss_w_per_k": scenario.environment.heat_loss_w_per_k,
            "air_leak_rate_ach": scenario.environment.air_leak_rate_ach,
        },
        "actuators": {
            "heater": {
                "available": caps.heater.available,
                "max_power_w": caps.heater.max_power_w,
                "efficiency": caps.heater.efficiency,
            },
            "fan": {
                "available": caps.fan.available,
                "max_airflow_m3_h": caps.fan.max_airflow_m3_h,
                "minimum_command": caps.fan.minimum_command,
            },
            "humidifier": {
                "available": caps.humidifier.available,
                "max_output_g_h": caps.humidifier.max_output_g_h,
            },
            "dehumidifier": {
                "available": caps.dehumidifier.available,
                "max_removal_g_h": caps.dehumidifier.max_removal_g_h,
            },
            "cooler": {
                "available": caps.cooler.available,
                "max_cooling_w": caps.cooler.max_cooling_w,
            },
            "co2_doser": {
                "available": caps.co2_doser.available,
                "dose_ppm_per_full_pulse": caps.co2_doser.dose_ppm_per_full_pulse,
                "maximum_pulse_s": caps.co2_doser.maximum_pulse_s,
            },
            "nutrient_heater": {
                "available": caps.nutrient_heater.available,
                "max_power_w": caps.nutrient_heater.max_power_w,
                "efficiency": caps.nutrient_heater.efficiency,
            },
        },
        "targets": {
            "air_temperature_c": scenario.targets.target_air_temperature_c,
            "air_humidity_pct": scenario.targets.target_air_humidity_pct,
            "co2_ppm": scenario.targets.target_co2_ppm,
            "nutrient_solution_temperature_c": (
                scenario.targets.target_nutrient_solution_temperature_c
            ),
        },
        "previous": {
            "heater": previous.heater,
            "fan": previous.fan,
            "humidifier": previous.humidifier,
            "dehumidifier": previous.dehumidifier,
            "cooler": previous.cooler,
            "co2_doser": previous.co2_doser,
            "nutrient_heater": previous.nutrient_heater,
        },
        "zones": zones_payload,
        "pseudo": {"lights_active": state.lights_active},
    }


# Backward-compatible alias used by v2/v3 dataset and tests.
controller_input_record_v2 = controller_input_record

__all__ = [
    "GLOBAL_SENSOR_NAMES",
    "MAX_ZONES",
    "ZONE_SENSOR_NAMES",
    "controller_input_record",
    "controller_input_record_v2",
]
