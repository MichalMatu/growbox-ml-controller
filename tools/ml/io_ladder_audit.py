"""I/O ladder audit: start from empty (all off), grow sensors/actuators one-by-one.

All actuators forced to control_type=binary. Strict safety assertions; policy
residuals recorded as errors when the corresponding actuator is available.
Designed for on-device serial (and optional panel) until matrix is fully green.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import serial
from tools.ml.scenario_payload import default_scenario

BINARY_OUTPUTS = (
    "heater",
    "fan",
    "humidifier",
    "dehumidifier",
    "cooler",
    "co2_doser",
    "irrigation_pot_1",
    "irrigation_pot_2",
    "irrigation_pot_3",
    "irrigation_pot_4",
    "nutrient_heater",
    "heat_mat_pot_1",
    "heat_mat_pot_2",
    "heat_mat_pot_3",
    "heat_mat_pot_4",
)

SCHEMA_HASH_EXPECTED = None  # filled from contract at runtime


@dataclass
class Finding:
    severity: str  # error | warn | info
    case: str
    code: str
    message: str
    detail: dict[str, Any] = field(default_factory=dict)


def contract_hash() -> str:
    from tools.ml.contract import ACTIVE_CONTRACT_PATH, load_contract

    return load_contract(ACTIVE_CONTRACT_PATH).short_hash


def force_all_binary(scenario: dict[str, Any]) -> dict[str, Any]:
    sc = copy.deepcopy(scenario)
    for name, act in (sc.get("actuators") or {}).items():
        if isinstance(act, dict):
            act["control_type"] = "binary"
    for pot in sc.get("pots") or []:
        if not isinstance(pot, dict):
            continue
        if isinstance(pot.get("irrigation"), dict):
            pot["irrigation"]["control_type"] = "binary"
        if isinstance(pot.get("heat_mat"), dict):
            pot["heat_mat"]["control_type"] = "binary"
    return sc


def empty_base(*, seed: int = 9000) -> dict[str, Any]:
    """L0: full wire-complete scenario, every actuator off/unavailable, pots inactive."""
    sc = force_all_binary(default_scenario(seed=seed, preset="nominal"))
    # Sensors present (finite) but all validity false — no trusted measurements.
    for key in list(sc["validity"].keys()):
        sc["validity"][key] = False
    sc["sensors"] = {
        "air_temperature_c": 22.0,
        "air_humidity_pct": 50.0,
        "co2_ppm": 420.0,
        "nutrient_solution_temperature_c": 20.0,
        "outside_temperature_c": 18.0,
        "outside_humidity_pct": 50.0,
        "outside_co2_ppm": 420.0,
    }
    sc["targets"] = {
        "air_temperature_c": 25.0,
        "air_humidity_pct": 65.0,
        "co2_ppm": 900.0,
        "nutrient_solution_temperature_c": 20.0,
    }
    sc["pseudo"] = {"lights_active": False}
    # Kill every global actuator
    for name, caps in {
        "heater": {"available": False, "max_power_w": 0.0, "efficiency": 0.0},
        "fan": {"available": False, "max_airflow_m3_h": 0.0, "minimum_command": 0.0},
        "humidifier": {"available": False, "max_output_g_h": 0.0},
        "dehumidifier": {"available": False, "max_removal_g_h": 0.0},
        "cooler": {"available": False, "max_cooling_w": 0.0},
        "co2_doser": {
            "available": False,
            "dose_ppm_per_full_pulse": 0.0,
            "maximum_pulse_s": 0.0,
        },
        "nutrient_heater": {"available": False, "max_power_w": 0.0, "efficiency": 0.0},
    }.items():
        sc["actuators"][name].update(caps)
        sc["actuators"][name]["control_type"] = "binary"
    # All pots inactive
    from tools.ml.scenario_payload import INACTIVE_POT_PRESET

    sc["pots"] = [copy.deepcopy(INACTIVE_POT_PRESET) for _ in range(4)]
    for pot in sc["pots"]:
        pot["irrigation"]["control_type"] = "binary"
        pot["heat_mat"]["control_type"] = "binary"
    for k in sc["previous"]:
        sc["previous"][k] = 0.0
    # Short dwell so ladder steps engage quickly
    sc["safety"]["heater_minimum_on_s"] = 0.0
    sc["safety"]["heater_minimum_off_s"] = 0.0
    sc["safety"]["humidifier_minimum_on_s"] = 0.0
    sc["safety"]["humidifier_minimum_off_s"] = 0.0
    sc["safety"]["dehumidifier_minimum_on_s"] = 0.0
    sc["safety"]["dehumidifier_minimum_off_s"] = 0.0
    sc["safety"]["cooler_minimum_on_s"] = 0.0
    sc["safety"]["cooler_minimum_off_s"] = 0.0
    sc["safety"]["co2_doser_minimum_interval_s"] = 0.0
    sc["safety"]["fan_venting_co2_threshold"] = 0.5
    sc["seed"] = seed
    return force_all_binary(sc)


def enable_sensor_air_t(sc: dict[str, Any]) -> None:
    sc["validity"]["air_temperature_c"] = True
    sc["sensors"]["air_temperature_c"] = 22.0


def enable_sensor_air_rh(sc: dict[str, Any]) -> None:
    sc["validity"]["air_humidity_pct"] = True
    sc["sensors"]["air_humidity_pct"] = 55.0


def enable_sensor_co2(sc: dict[str, Any]) -> None:
    sc["validity"]["co2_ppm"] = True
    sc["sensors"]["co2_ppm"] = 500.0


def enable_sensor_outside(sc: dict[str, Any]) -> None:
    sc["validity"]["outside_temperature_c"] = True
    sc["validity"]["outside_humidity_pct"] = True
    sc["validity"]["outside_co2_ppm"] = True


def enable_sensor_nutrient(sc: dict[str, Any]) -> None:
    sc["validity"]["nutrient_solution_temperature_c"] = True
    sc["sensors"]["nutrient_solution_temperature_c"] = 18.0


def enable_actuator_fan(sc: dict[str, Any]) -> None:
    sc["actuators"]["fan"].update(
        {
            "available": True,
            "max_airflow_m3_h": 120.0,
            "minimum_command": 0.0,
            "control_type": "binary",
        }
    )


def enable_actuator_heater(sc: dict[str, Any]) -> None:
    sc["actuators"]["heater"].update(
        {
            "available": True,
            "max_power_w": 180.0,
            "efficiency": 0.9,
            "control_type": "binary",
        }
    )


def enable_actuator_humidifier(sc: dict[str, Any]) -> None:
    sc["actuators"]["humidifier"].update(
        {"available": True, "max_output_g_h": 180.0, "control_type": "binary"}
    )


def enable_actuator_dehumidifier(sc: dict[str, Any]) -> None:
    sc["actuators"]["dehumidifier"].update(
        {"available": True, "max_removal_g_h": 150.0, "control_type": "binary"}
    )


def enable_actuator_cooler(sc: dict[str, Any]) -> None:
    sc["actuators"]["cooler"].update(
        {"available": True, "max_cooling_w": 200.0, "control_type": "binary"}
    )


def enable_actuator_co2(sc: dict[str, Any]) -> None:
    sc["actuators"]["co2_doser"].update(
        {
            "available": True,
            "dose_ppm_per_full_pulse": 120.0,
            "maximum_pulse_s": 5.0,
            "control_type": "binary",
        }
    )


def enable_actuator_nutrient(sc: dict[str, Any]) -> None:
    sc["actuators"]["nutrient_heater"].update(
        {
            "available": True,
            "max_power_w": 80.0,
            "efficiency": 0.9,
            "control_type": "binary",
        }
    )


def enable_pot(
    sc: dict[str, Any],
    index: int,
    *,
    irrigation: bool = False,
    heat_mat: bool = False,
    soil_m: float = 40.0,
    soil_t: float = 18.0,
) -> None:
    from tools.ml.scenario_payload import ACTIVE_POT_PRESET

    pot = copy.deepcopy(ACTIVE_POT_PRESET)
    pot["sensors"]["soil_moisture_pct"] = soil_m
    pot["sensors"]["soil_temperature_c"] = soil_t
    pot["targets"]["soil_moisture_pct"] = 50.0
    pot["targets"]["soil_temperature_c"] = 22.0
    pot["validity"] = {"soil_moisture_pct": True, "soil_temperature_c": True}
    pot["irrigation"]["available"] = irrigation
    if irrigation:
        pot["irrigation"].update(
            {
                "flow_ml_s": 22.0,
                "maximum_pulse_s": 4.0,
                "minimum_interval_s": 0.0,
                "control_type": "binary",
            }
        )
    else:
        pot["irrigation"].update(
            {
                "available": False,
                "flow_ml_s": 0.0,
                "maximum_pulse_s": 0.0,
                "minimum_interval_s": 0.0,
                "control_type": "binary",
            }
        )
    pot["heat_mat"]["available"] = heat_mat
    pot["heat_mat"]["max_power_w"] = 40.0 if heat_mat else 0.0
    pot["heat_mat"]["control_type"] = "binary"
    sc["pots"][index] = pot


def build_ladder_cases() -> list[tuple[str, dict[str, Any], dict[str, Any]]]:
    """Return (case_id, scenario, meta) for progressive I/O enablement + stresses."""
    cases: list[tuple[str, dict[str, Any], dict[str, Any]]] = []
    seed = 9100

    def add(case_id: str, sc: dict[str, Any], **meta: Any) -> None:
        sc = force_all_binary(sc)
        sc["seed"] = seed + len(cases)
        cases.append((case_id, sc, meta))

    # --- L0 empty ---
    base = empty_base(seed=seed)
    add("L0_empty_all_off", base, expect_all_zero=True)

    # Stress: garbage raw values with nothing available still zero
    sc = empty_base()
    sc["previous"] = {k: 1.0 for k in sc["previous"]}
    add("L0_previous_on_but_unavailable", sc, expect_all_zero=True)

    # --- Progressive enable ---
    # L1 sensors T only + nothing
    sc = empty_base()
    enable_sensor_air_t(sc)
    add("L1_sensor_T_only", sc, expect_all_zero=True)

    # L2 + RH sensors, still no actuators
    sc = empty_base()
    enable_sensor_air_t(sc)
    enable_sensor_air_rh(sc)
    add("L2_sensors_T_RH_no_actuators", sc, expect_all_zero=True)

    # L3 + fan only
    sc = empty_base()
    enable_sensor_air_t(sc)
    enable_sensor_air_rh(sc)
    enable_actuator_fan(sc)
    add("L3_T_RH_fan_nominal", sc, available_outputs=("fan",))
    # overtemp with only fan
    sc = empty_base()
    enable_sensor_air_t(sc)
    enable_sensor_air_rh(sc)
    enable_actuator_fan(sc)
    sc["sensors"]["air_temperature_c"] = 36.0
    add(
        "L3_T_RH_fan_overtemp",
        sc,
        available_outputs=("fan",),
        require_fan_min=True,
    )

    # L4 + heater
    sc = empty_base()
    enable_sensor_air_t(sc)
    enable_sensor_air_rh(sc)
    enable_actuator_fan(sc)
    enable_actuator_heater(sc)
    sc["sensors"]["air_temperature_c"] = 16.0
    sc["targets"]["air_temperature_c"] = 25.0
    add(
        "L4_cold_need_heater",
        sc,
        available_outputs=("fan", "heater"),
        expect_on=("heater",),
    )
    sc = empty_base()
    enable_sensor_air_t(sc)
    enable_sensor_air_rh(sc)
    enable_actuator_fan(sc)
    enable_actuator_heater(sc)
    sc["sensors"]["air_temperature_c"] = 36.0
    sc["previous"]["heater"] = 1.0
    add(
        "L4_overtemp_heater_must_off",
        sc,
        available_outputs=("fan", "heater"),
        expect_off=("heater",),
        require_fan_min=True,
    )
    sc = empty_base()
    enable_sensor_air_t(sc)
    enable_sensor_air_rh(sc)
    enable_actuator_fan(sc)
    enable_actuator_heater(sc)
    sc["validity"]["air_temperature_c"] = False
    sc["sensors"]["air_temperature_c"] = 10.0
    add(
        "L4_invalid_T_heater_off",
        sc,
        available_outputs=("fan", "heater"),
        expect_off=("heater",),
    )

    # L5 humidifier
    sc = empty_base()
    enable_sensor_air_t(sc)
    enable_sensor_air_rh(sc)
    enable_actuator_fan(sc)
    enable_actuator_heater(sc)
    enable_actuator_humidifier(sc)
    sc["sensors"]["air_humidity_pct"] = 25.0
    sc["targets"]["air_humidity_pct"] = 65.0
    sc["sensors"]["air_temperature_c"] = 22.0
    add(
        "L5_dry_need_humidifier",
        sc,
        available_outputs=("fan", "heater", "humidifier"),
        expect_on=("humidifier",),
    )
    sc = empty_base()
    enable_sensor_air_t(sc)
    enable_sensor_air_rh(sc)
    enable_actuator_humidifier(sc)
    sc["validity"]["air_humidity_pct"] = False
    sc["sensors"]["air_humidity_pct"] = 20.0
    add(
        "L5_invalid_RH_humidifier_off",
        sc,
        available_outputs=("humidifier",),
        expect_off=("humidifier",),
    )

    # L6 dehumidifier + conflict
    sc = empty_base()
    enable_sensor_air_t(sc)
    enable_sensor_air_rh(sc)
    enable_actuator_fan(sc)
    enable_actuator_humidifier(sc)
    enable_actuator_dehumidifier(sc)
    sc["sensors"]["air_humidity_pct"] = 90.0
    sc["targets"]["air_humidity_pct"] = 60.0
    add(
        "L6_wet_need_dehumidifier",
        sc,
        available_outputs=("fan", "humidifier", "dehumidifier"),
        expect_on=("dehumidifier",),
        expect_off=("humidifier",),
        forbid_both=("humidifier", "dehumidifier"),
    )

    # L7 cooler
    sc = empty_base()
    enable_sensor_air_t(sc)
    enable_sensor_air_rh(sc)
    enable_actuator_fan(sc)
    enable_actuator_heater(sc)
    enable_actuator_cooler(sc)
    sc["sensors"]["air_temperature_c"] = 30.0
    sc["targets"]["air_temperature_c"] = 24.0
    add(
        "L7_hot_need_cooler",
        sc,
        available_outputs=("fan", "heater", "cooler"),
        expect_on=("cooler",),
        expect_off=("heater",),
        forbid_both=("heater", "cooler"),
    )

    # L8 CO2
    sc = empty_base()
    enable_sensor_air_t(sc)
    enable_sensor_air_rh(sc)
    enable_sensor_co2(sc)
    enable_actuator_fan(sc)
    enable_actuator_co2(sc)
    sc["sensors"]["co2_ppm"] = 400.0
    sc["targets"]["co2_ppm"] = 1100.0
    sc["sensors"]["air_temperature_c"] = 22.0
    # keep fan soft so venting does not kill CO2 — use previous fan 0
    sc["previous"]["fan"] = 0.0
    add(
        "L8_low_co2_need_doser",
        sc,
        available_outputs=("fan", "co2_doser"),
        expect_on=("co2_doser",),
        co2_binary=True,
    )
    sc = empty_base()
    enable_sensor_air_t(sc)
    enable_sensor_co2(sc)
    enable_actuator_fan(sc)
    enable_actuator_co2(sc)
    sc["sensors"]["co2_ppm"] = 1300.0
    sc["targets"]["co2_ppm"] = 900.0
    add(
        "L8_high_co2_doser_off",
        sc,
        available_outputs=("fan", "co2_doser"),
        expect_off=("co2_doser",),
    )
    sc = empty_base()
    enable_sensor_air_t(sc)
    enable_sensor_co2(sc)
    enable_actuator_fan(sc)
    enable_actuator_co2(sc)
    sc["sensors"]["co2_ppm"] = 400.0
    sc["targets"]["co2_ppm"] = 1100.0
    sc["sensors"]["air_temperature_c"] = 34.0  # alarm fan
    add(
        "L8_co2_blocked_by_alarm_fan",
        sc,
        available_outputs=("fan", "co2_doser"),
        expect_off=("co2_doser",),
        require_fan_min=True,
    )

    # L9 outside sensors (no new actuator)
    sc = empty_base()
    enable_sensor_air_t(sc)
    enable_sensor_air_rh(sc)
    enable_sensor_outside(sc)
    enable_actuator_fan(sc)
    enable_actuator_heater(sc)
    sc["sensors"]["air_temperature_c"] = 18.0
    add(
        "L9_outside_context_heater",
        sc,
        available_outputs=("fan", "heater"),
        expect_on=("heater",),
    )

    # L10 nutrient
    sc = empty_base()
    enable_sensor_air_t(sc)
    enable_sensor_nutrient(sc)
    enable_actuator_fan(sc)
    enable_actuator_nutrient(sc)
    sc["sensors"]["nutrient_solution_temperature_c"] = 12.0
    sc["targets"]["nutrient_solution_temperature_c"] = 22.0
    add(
        "L10_cold_nutrient_heater",
        sc,
        available_outputs=("fan", "nutrient_heater"),
        expect_on=("nutrient_heater",),
    )

    # L11 pot1 irrigation
    sc = empty_base()
    enable_sensor_air_t(sc)
    enable_sensor_air_rh(sc)
    enable_sensor_nutrient(sc)
    enable_actuator_fan(sc)
    enable_pot(sc, 0, irrigation=True, soil_m=18.0)
    sc["sensors"]["nutrient_solution_temperature_c"] = 20.0  # warm enough to irrigate
    add(
        "L11_dry_soil_irrigation",
        sc,
        available_outputs=("fan", "irrigation_pot_1"),
        expect_on=("irrigation_pot_1",),
    )
    sc = empty_base()
    enable_sensor_air_t(sc)
    enable_sensor_nutrient(sc)
    enable_actuator_fan(sc)
    enable_pot(sc, 0, irrigation=True, soil_m=18.0)
    sc["sensors"]["nutrient_solution_temperature_c"] = 10.0  # blocks irrigation
    sc["validity"]["nutrient_solution_temperature_c"] = True
    add(
        "L11_irrigation_blocked_cold_nutrient",
        sc,
        available_outputs=("fan", "irrigation_pot_1"),
        expect_off=("irrigation_pot_1",),
    )
    sc = empty_base()
    enable_sensor_air_t(sc)
    enable_pot(sc, 0, irrigation=True, soil_m=60.0)
    add(
        "L11_saturated_no_irrigation",
        sc,
        available_outputs=("irrigation_pot_1",),
        expect_off=("irrigation_pot_1",),
    )

    # L12 heat mat pot1
    sc = empty_base()
    enable_sensor_air_t(sc)
    enable_pot(sc, 0, irrigation=False, heat_mat=True, soil_t=14.0)
    add(
        "L12_cold_soil_heat_mat",
        sc,
        available_outputs=("heat_mat_pot_1",),
        expect_on=("heat_mat_pot_1",),
    )

    # L13 pots 2-4
    for pot_i in (1, 2, 3):
        sc = empty_base()
        enable_sensor_air_t(sc)
        enable_sensor_nutrient(sc)
        sc["sensors"]["nutrient_solution_temperature_c"] = 20.0
        enable_pot(sc, pot_i, irrigation=True, heat_mat=True, soil_m=20.0, soil_t=15.0)
        out_irr = f"irrigation_pot_{pot_i + 1}"
        out_hm = f"heat_mat_pot_{pot_i + 1}"
        add(
            f"L13_pot{pot_i + 1}_dry_cold",
            sc,
            available_outputs=(out_irr, out_hm),
            expect_on=(out_irr, out_hm),
        )

    # L14 lights
    sc = empty_base()
    enable_sensor_air_t(sc)
    enable_sensor_air_rh(sc)
    enable_actuator_fan(sc)
    enable_actuator_heater(sc)
    sc["pseudo"]["lights_active"] = True
    sc["sensors"]["air_temperature_c"] = 18.0
    add(
        "L14_lights_on_cold",
        sc,
        available_outputs=("fan", "heater"),
        expect_on=("heater",),
    )

    # L15 full stack all binary
    sc = force_all_binary(default_scenario(seed=seed + 500, preset="all_pots"))
    for name in sc["actuators"]:
        sc["actuators"][name]["available"] = True
        sc["actuators"][name]["control_type"] = "binary"
    sc["actuators"]["heater"].update({"max_power_w": 180.0, "efficiency": 0.9})
    sc["actuators"]["fan"].update({"max_airflow_m3_h": 120.0, "minimum_command": 0.0})
    sc["actuators"]["humidifier"]["max_output_g_h"] = 180.0
    sc["actuators"]["dehumidifier"]["max_removal_g_h"] = 150.0
    sc["actuators"]["cooler"]["max_cooling_w"] = 200.0
    sc["actuators"]["co2_doser"].update({"dose_ppm_per_full_pulse": 120.0, "maximum_pulse_s": 5.0})
    sc["actuators"]["nutrient_heater"].update({"max_power_w": 80.0, "efficiency": 0.9})
    for pot in sc["pots"]:
        pot["available"] = True
        pot["irrigation"]["available"] = True
        pot["irrigation"].update(
            {
                "flow_ml_s": 22.0,
                "maximum_pulse_s": 4.0,
                "minimum_interval_s": 0.0,
                "control_type": "binary",
            }
        )
        pot["heat_mat"]["available"] = True
        pot["heat_mat"]["max_power_w"] = 40.0
        pot["heat_mat"]["control_type"] = "binary"
        pot["validity"] = {"soil_moisture_pct": True, "soil_temperature_c": True}
    sc["sensors"]["air_temperature_c"] = 16.0
    sc["sensors"]["air_humidity_pct"] = 30.0
    sc["sensors"]["co2_ppm"] = 450.0
    sc["sensors"]["nutrient_solution_temperature_c"] = 16.0
    sc["targets"]["air_temperature_c"] = 26.0
    sc["targets"]["air_humidity_pct"] = 65.0
    sc["targets"]["co2_ppm"] = 1100.0
    sc["targets"]["nutrient_solution_temperature_c"] = 22.0
    for pot in sc["pots"]:
        pot["sensors"]["soil_moisture_pct"] = 20.0
        pot["sensors"]["soil_temperature_c"] = 15.0
    sc["safety"]["heater_minimum_on_s"] = 0.0
    sc["safety"]["heater_minimum_off_s"] = 0.0
    sc["safety"]["co2_doser_minimum_interval_s"] = 0.0
    add(
        "L15_full_stack_multi_need",
        sc,
        available_outputs=BINARY_OUTPUTS,
        expect_on=("heater", "humidifier"),
        forbid_both_pairs=(("heater", "cooler"), ("humidifier", "dehumidifier")),
    )

    # L15 overtemp full stack
    sc2 = copy.deepcopy(sc)
    sc2["sensors"]["air_temperature_c"] = 37.0
    sc2["previous"]["heater"] = 1.0
    add(
        "L15_full_overtemp",
        sc2,
        available_outputs=BINARY_OUTPUTS,
        expect_off=("heater",),
        require_fan_min=True,
    )

    return cases


class BoardSession:
    def __init__(self, port: str, timeout: float = 8.0) -> None:
        self.port = port
        self.timeout = timeout
        self._ser: serial.Serial | None = None

    def __enter__(self) -> BoardSession:
        self._ser = serial.Serial(self.port, 115200, timeout=0.15)
        time.sleep(0.45)
        self._ser.reset_input_buffer()
        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline:
            self._ser.readline()
        return self

    def __exit__(self, *args: object) -> None:
        if self._ser:
            self._ser.close()
            self._ser = None

    def send(
        self, command: dict[str, Any], *, expect: str, expect_cmd: str | None = None
    ) -> dict[str, Any]:
        assert self._ser is not None
        self._ser.write(json.dumps(command, separators=(",", ":")).encode() + b"\n")
        self._ser.flush()
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            raw = self._ser.readline()
            if not raw:
                continue
            line = raw.decode("utf-8", errors="replace").strip()
            if not line.startswith("{"):
                continue
            try:
                response = json.loads(line)
            except json.JSONDecodeError:
                continue
            if response.get("type") == "error":
                raise RuntimeError(f"board error: {response}")
            if response.get("type") != expect:
                continue
            if expect == "ack" and expect_cmd and response.get("command") != expect_cmd:
                continue
            return response
        raise TimeoutError(f"timeout {expect} after {command.get('command')}")


def evaluate(
    case: str,
    scenario: dict[str, Any],
    decision: dict[str, Any],
    meta: dict[str, Any],
    schema_hash: str,
) -> list[Finding]:
    findings: list[Finding] = []
    raw = decision.get("raw_output") or {}
    safe = decision.get("safe_output") or {}
    diag = decision.get("diagnostics") or {}
    thr = float((scenario.get("safety") or {}).get("binary_threshold", 0.5))
    actuators = scenario.get("actuators") or {}

    if decision.get("schema_version") != 4:
        findings.append(
            Finding("error", case, "schema_version", str(decision.get("schema_version")))
        )
    if decision.get("schema_hash") != schema_hash:
        findings.append(
            Finding("error", case, "schema_hash", f"{decision.get('schema_hash')} != {schema_hash}")
        )
    if diag.get("inference_status") not in (None, "ok"):
        findings.append(Finding("error", case, "inference", str(diag.get("inference_status"))))

    # Binary + range + unavailable
    for name in BINARY_OUTPUTS:
        if name not in safe:
            findings.append(Finding("error", case, "missing_output", name))
            continue
        val = float(safe[name])
        if not (0.0 <= val <= 1.0 + 1e-6):
            findings.append(Finding("error", case, "range", f"{name}={val}"))
        if abs(val) > 1e-6 and abs(val - 1.0) > 1e-6:
            findings.append(
                Finding("error", case, "non_binary", f"{name}={val}", {"raw": raw.get(name)})
            )

    def actuator_available(out_name: str) -> bool:
        if out_name in actuators:
            return bool((actuators.get(out_name) or {}).get("available"))
        if out_name.startswith("irrigation_pot_"):
            idx = int(out_name.rsplit("_", 1)[1]) - 1
            pot = (scenario.get("pots") or [None] * 4)[idx]
            return bool(
                pot and pot.get("available") and (pot.get("irrigation") or {}).get("available")
            )
        if out_name.startswith("heat_mat_pot_"):
            idx = int(out_name.rsplit("_", 1)[1]) - 1
            pot = (scenario.get("pots") or [None] * 4)[idx]
            return bool(
                pot and pot.get("available") and (pot.get("heat_mat") or {}).get("available")
            )
        return False

    for name in BINARY_OUTPUTS:
        if not actuator_available(name) and float(safe.get(name, 0)) > 1e-6:
            findings.append(
                Finding(
                    "error",
                    case,
                    "unavailable_nonzero",
                    f"{name}={safe.get(name)}",
                    {"raw": raw.get(name)},
                )
            )

    if meta.get("expect_all_zero"):
        for name in BINARY_OUTPUTS:
            if float(safe.get(name, 0)) > 1e-6:
                findings.append(
                    Finding("error", case, "expected_all_zero", f"{name}={safe.get(name)}")
                )

    for name in meta.get("expect_off") or ():
        if float(safe.get(name, 0)) > 1e-6:
            findings.append(Finding("error", case, "expected_off", f"{name}={safe.get(name)}"))

    for name in meta.get("expect_on") or ():
        if float(safe.get(name, 0)) < thr:
            findings.append(
                Finding(
                    "error",
                    case,
                    "expected_on",
                    f"{name} raw={raw.get(name)} safe={safe.get(name)}",
                )
            )

    if meta.get("require_fan_min"):
        # Binary fan + thermal alarm → safe fan must be full ON.
        if actuator_available("fan") and float(safe.get("fan", 0)) + 1e-6 < 1.0:
            findings.append(Finding("error", case, "fan_not_alarm", f"fan={safe.get('fan')}"))

    for a, b in meta.get("forbid_both_pairs") or ():
        if float(safe.get(a, 0)) >= thr and float(safe.get(b, 0)) >= thr:
            findings.append(Finding("error", case, "conflict", f"{a}+{b}"))
    pair = meta.get("forbid_both")
    if pair and len(pair) == 2:
        a, b = pair
        if float(safe.get(a, 0)) >= thr and float(safe.get(b, 0)) >= thr:
            findings.append(Finding("error", case, "conflict", f"{a}+{b}"))

    if meta.get("co2_binary") and "co2_doser" in safe:
        v = float(safe["co2_doser"])
        if v not in (0.0, 1.0) and abs(v) > 1e-6 and abs(v - 1.0) > 1e-6:
            findings.append(Finding("error", case, "co2_non_binary", str(v)))

    findings.append(
        Finding(
            "info",
            case,
            "snapshot",
            decision.get("model_version", ""),
            {
                "raw": {k: raw.get(k) for k in BINARY_OUTPUTS},
                "safe": {k: safe.get(k) for k in BINARY_OUTPUTS},
                "diagnostics": diag,
                "model_version": decision.get("model_version"),
                "meta": meta,
            },
        )
    )
    return findings


def run_on_board(port: str, report_path: Path) -> int:
    schema_hash = contract_hash()
    cases = build_ladder_cases()
    all_findings: list[Finding] = []
    case_rows: list[dict[str, Any]] = []

    # disconnect panel
    try:
        import urllib.request

        urllib.request.urlopen(
            urllib.request.Request(
                "http://127.0.0.1:8765/api/disconnect",
                data=b"{}",
                method="POST",
                headers={"Content-Type": "application/json"},
            ),
            timeout=2,
        )
    except Exception:
        pass
    time.sleep(0.5)

    print(f"ladder cases={len(cases)} schema={schema_hash} port={port}", flush=True)
    with BoardSession(port) as session:
        for case_id, scenario, meta in cases:
            print(f"  {case_id}...", flush=True)
            try:
                session.send({"command": "pause"}, expect="ack", expect_cmd="pause")
                session.send(
                    {"command": "mode", "value": "replay"}, expect="ack", expect_cmd="mode"
                )
                cmd = {"command": "load_scenario", **scenario}
                session.send(cmd, expect="ack", expect_cmd="load_scenario")
                decision = session.send({"command": "step"}, expect="decision")
                findings = evaluate(case_id, scenario, decision, meta, schema_hash)
            except Exception as exc:  # noqa: BLE001
                findings = [Finding("error", case_id, "session", str(exc))]
            all_findings.extend(findings)
            errs = [f for f in findings if f.severity == "error"]
            warns = [f for f in findings if f.severity == "warn"]
            snap = next((f for f in findings if f.code == "snapshot"), None)
            case_rows.append(
                {
                    "case": case_id,
                    "errors": [asdict(f) for f in errs],
                    "warns": [asdict(f) for f in warns],
                    "snapshot": snap.detail if snap else {},
                    "meta": meta,
                }
            )
            print(f"    e={len(errs)} w={len(warns)}", flush=True)

    errors = [f for f in all_findings if f.severity == "error"]
    warns = [f for f in all_findings if f.severity == "warn"]
    by_code: dict[str, int] = {}
    for f in errors + warns:
        by_code[f.code] = by_code.get(f.code, 0) + 1
    # Classify if retrain likely needed
    retrain_codes = {"expected_on"}
    retrain_hits = [f for f in errors if f.code in retrain_codes]
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "schema_hash": schema_hash,
        "case_count": len(cases),
        "summary": {
            "error_count": len(errors),
            "warn_count": len(warns),
            "by_code": dict(sorted(by_code.items(), key=lambda kv: -kv[1])),
            "errors": [asdict(f) for f in errors],
            "warns": [asdict(f) for f in warns],
            "retrain_recommended": len(retrain_hits) > 0,
            "retrain_hits": [asdict(f) for f in retrain_hits],
        },
        "cases": case_rows,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], indent=2))
    print(f"report: {report_path}")
    return 1 if errors else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", default="/dev/cu.usbmodem1101")
    parser.add_argument("--report", type=Path, default=Path("build/audit/io_ladder.json"))
    parser.add_argument("--list", action="store_true", help="list cases only")
    args = parser.parse_args(argv)
    if args.list:
        for case_id, _, meta in build_ladder_cases():
            print(case_id, meta)
        return 0
    if not Path(args.port).exists():
        print(f"missing port {args.port}", file=sys.stderr)
        return 2
    return run_on_board(args.port, args.report)


if __name__ == "__main__":
    raise SystemExit(main())
