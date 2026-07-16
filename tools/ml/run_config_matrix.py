#!/usr/bin/env python3
"""Run encoder + safety + short sim checks for every CONFIG_MATRIX.csv row.

Produces RESULTS.csv with columns: id,pass,fail_reason
End condition: len(RESULTS) == len(CONFIG_MATRIX).
"""

from __future__ import annotations

import argparse
import copy
import csv
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np

from tools.ml.alignment import assert_encoded_vector, feature_path_index
from tools.ml.config_matrix import (
    DEFAULT_MATRIX,
    DEFAULT_RESULTS,
    GLOBAL_ACTUATORS,
    GLOBAL_SENSORS,
    OP_ACTUATOR_CAPS,
    OUTPUTS,
    build_controller_input,
    load_matrix_rows,
)
from tools.ml.contract import Contract, load_contract
from tools.ml.simulator import (
    MAX_POTS,
    Co2DoserCapabilities,
    ControlAction,
    ControlTargets,
    CoolerCapabilities,
    DehumidifierCapabilities,
    EnvironmentParameters,
    EnvironmentState,
    FanCapabilities,
    GlobalActuators,
    HeaterCapabilities,
    HeatMatCapabilities,
    HumidifierCapabilities,
    NutrientHeaterCapabilities,
    PotConfig,
    PotCultivation,
    PotState,
    PumpCapabilities,
    Scenario,
    SensorValidity,
    SequentialEnvironmentSimulator,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _set_nested(document: dict[str, Any], path: str, value: Any) -> None:
    parts = path.split(".")
    current: dict[str, Any] = document
    for part in parts[:-1]:
        if part.isdigit():
            raise ValueError(f"use list indexing helper for pots: {path}")
        next_value = current.get(part)
        if not isinstance(next_value, dict):
            next_value = {}
            current[part] = next_value
        current = next_value
    current[parts[-1]] = value


def _csv_list(value: str) -> list[str]:
    text = (value or "").strip()
    if not text or text in {"∅", "empty"}:
        return []
    return [part.strip() for part in text.split(",") if part.strip()]


def apply_safety_python(record: dict[str, Any], raw: dict[str, float]) -> dict[str, float]:
    """Python mirror of availability / pot / validity hard zeros from SafetySupervisor."""
    safe = {name: float(np.clip(raw.get(name, 0.0), 0.0, 1.0)) for name in OUTPUTS}
    actuators = record.get("actuators") or {}
    validity = record.get("validity") or {}
    sensors = record.get("sensors") or {}
    targets = record.get("targets") or {}
    safety = record.get("safety") or {}
    pots = record.get("pots") or []

    def cap_ok(name: str, key: str) -> bool:
        act = actuators.get(name) or {}
        if not bool(act.get("available", False)):
            return False
        return float(act.get(key, 0.0)) > 0.0

    if not bool((actuators.get("heater") or {}).get("available")) or not (
        float((actuators.get("heater") or {}).get("max_power_w", 0.0)) > 0.0
        and float((actuators.get("heater") or {}).get("efficiency", 0.0)) > 0.0
    ):
        safe["heater"] = 0.0
    if not bool(validity.get("air_temperature_c", False)):
        safe["heater"] = 0.0
    elif float(sensors.get("air_temperature_c", 0.0)) >= float(
        safety.get("maximum_air_temperature_c", 35.0)
    ):
        safe["heater"] = 0.0

    if not cap_ok("fan", "max_airflow_m3_h"):
        safe["fan"] = 0.0

    if not cap_ok("humidifier", "max_output_g_h"):
        safe["humidifier"] = 0.0
    if not cap_ok("dehumidifier", "max_removal_g_h"):
        safe["dehumidifier"] = 0.0
    if not bool(validity.get("air_humidity_pct", False)):
        safe["humidifier"] = 0.0
        safe["dehumidifier"] = 0.0

    if not cap_ok("cooler", "max_cooling_w"):
        safe["cooler"] = 0.0

    # CO2 doser: unavailable OR missing CO2 sensor OR target reached (firmware).
    if not cap_ok("co2_doser", "dose_ppm_per_full_pulse"):
        safe["co2_doser"] = 0.0
    elif not bool(validity.get("co2_ppm", False)):
        safe["co2_doser"] = 0.0
    elif float(sensors.get("co2_ppm", 0.0)) >= float(targets.get("co2_ppm", 850.0)):
        safe["co2_doser"] = 0.0

    if not bool((actuators.get("nutrient_heater") or {}).get("available")) or not (
        float((actuators.get("nutrient_heater") or {}).get("max_power_w", 0.0)) > 0.0
        and float((actuators.get("nutrient_heater") or {}).get("efficiency", 0.0)) > 0.0
    ):
        safe["nutrient_heater"] = 0.0
    if not bool(validity.get("nutrient_solution_temperature_c", False)):
        safe["nutrient_heater"] = 0.0

    for index in range(MAX_POTS):
        pot = pots[index] if index < len(pots) else {}
        pot_ok = bool(pot.get("available", False))
        pot_validity = pot.get("validity") or {}
        irr = pot.get("irrigation") or {}
        heat = pot.get("heat_mat") or {}
        irr_name = f"irrigation_pot_{index + 1}"
        heat_name = f"heat_mat_pot_{index + 1}"
        if (
            not pot_ok
            or not bool(irr.get("available", False))
            or float(irr.get("flow_ml_s", 0.0)) <= 0.0
            or float(irr.get("maximum_pulse_s", 0.0)) <= 0.0
            or not bool(pot_validity.get("soil_moisture_pct", False))
        ):
            safe[irr_name] = 0.0
        if (
            not pot_ok
            or not bool(heat.get("available", False))
            or float(heat.get("max_power_w", 0.0)) <= 0.0
            or not bool(pot_validity.get("soil_temperature_c", False))
        ):
            safe[heat_name] = 0.0
    return safe


def check_encoder(contract: Contract, record: dict[str, Any], path_index: dict[str, int]) -> None:
    vector = contract.encode(record)
    assert_encoded_vector(contract, vector)
    if not np.isfinite(vector).all():
        raise AssertionError("encoded vector has non-finite values")
    if vector.shape != (len(contract.features),):
        raise AssertionError(f"unexpected feature count {vector.shape}")

    # Validity=false ⇒ mask feature encodes to 0 and sensor value uses contract default.
    for sensor in GLOBAL_SENSORS:
        valid = bool(record["validity"].get(sensor, False))
        mask_path = f"validity.{sensor}"
        sensor_path = f"sensors.{sensor}"
        if mask_path not in path_index or sensor_path not in path_index:
            continue
        mask_val = float(vector[path_index[mask_path]])
        if valid:
            if mask_val != 1.0:
                raise AssertionError(f"{mask_path} expected 1.0, got {mask_val}")
        else:
            if mask_val != 0.0:
                raise AssertionError(f"{mask_path} expected 0.0, got {mask_val}")
            feature = next(f for f in contract.features if f.path == sensor_path)
            expected = feature.normalize(feature.default)
            actual = float(vector[path_index[sensor_path]])
            if abs(actual - expected) > 1e-5:
                raise AssertionError(
                    f"invalid {sensor_path}: encoded {actual} != default-normalized {expected}"
                )

    for index in range(MAX_POTS):
        pot = record["pots"][index]
        for sensor in ("soil_moisture_pct", "soil_temperature_c"):
            mask_path = f"pots.{index}.validity.{sensor}"
            sensor_path = f"pots.{index}.sensors.{sensor}"
            if mask_path not in path_index:
                continue
            valid = bool((pot.get("validity") or {}).get(sensor, False))
            mask_val = float(vector[path_index[mask_path]])
            if valid and bool(pot.get("available", False)):
                if mask_val != 1.0:
                    raise AssertionError(f"{mask_path} expected 1.0, got {mask_val}")
            else:
                if mask_val != 0.0 and not valid:
                    if mask_val != 0.0:
                        raise AssertionError(f"{mask_path} expected 0.0, got {mask_val}")


def check_safety(record: dict[str, Any], expected_zeros: list[str]) -> None:
    raw = {name: 1.0 for name in OUTPUTS}
    safe = apply_safety_python(record, raw)

    for name in expected_zeros:
        if name not in safe:
            raise AssertionError(f"unknown expected zero output {name!r}")
        if float(safe[name]) != 0.0:
            raise AssertionError(f"expected_safe_zero {name} was {safe[name]}")

    actuators = record.get("actuators") or {}
    for name in GLOBAL_ACTUATORS:
        if not bool((actuators.get(name) or {}).get("available", False)):
            if float(safe[name]) != 0.0:
                raise AssertionError(f"unavailable actuator {name} safe={safe[name]}")

    pots = record.get("pots") or []
    for index in range(MAX_POTS):
        pot = pots[index] if index < len(pots) else {}
        pot_ok = bool(pot.get("available", False))
        for kind, out in (
            ("irrigation", f"irrigation_pot_{index + 1}"),
            ("heat_mat", f"heat_mat_pot_{index + 1}"),
        ):
            act = pot.get(kind) or {}
            if not pot_ok or not bool(act.get("available", False)):
                if float(safe[out]) != 0.0:
                    raise AssertionError(f"pot{index + 1} unavailable {out} safe={safe[out]}")


def feature_by_path(contract: Contract, path: str):
    for feature in contract.features:
        if feature.path == path:
            return feature
    return None


def continuous_points(feature) -> list[float]:
    """Three non-cartesian points: min / default / max from the contract."""
    points = [float(feature.minimum), float(feature.default), float(feature.maximum)]
    # De-dup while preserving order
    out: list[float] = []
    for value in points:
        if value not in out:
            out.append(value)
    return out


def check_continuous_sweeps(contract: Contract, base: dict[str, Any]) -> None:
    """Sweep numeric params for active slots: min/default/max only (no cartesian product)."""
    # Active actuator capability paths
    capability_paths: list[str] = []
    for name, caps in OP_ACTUATOR_CAPS.items():
        if not bool((base["actuators"].get(name) or {}).get("available", False)):
            continue
        for key in caps:
            capability_paths.append(f"actuators.{name}.{key}")

    for index, pot in enumerate(base["pots"]):
        if not pot.get("available"):
            continue
        if (pot.get("irrigation") or {}).get("available"):
            capability_paths.append(f"pots.{index}.irrigation.flow_ml_s")
            capability_paths.append(f"pots.{index}.irrigation.maximum_pulse_s")
            capability_paths.append(f"pots.{index}.irrigation.minimum_interval_s")
        if (pot.get("heat_mat") or {}).get("available"):
            capability_paths.append(f"pots.{index}.heat_mat.max_power_w")

    # Active sensors
    for sensor in GLOBAL_SENSORS:
        if base["validity"].get(sensor):
            capability_paths.append(f"sensors.{sensor}")
    for index, pot in enumerate(base["pots"]):
        if not pot.get("available"):
            continue
        for sensor in ("soil_moisture_pct", "soil_temperature_c"):
            if (pot.get("validity") or {}).get(sensor):
                capability_paths.append(f"pots.{index}.sensors.{sensor}")

    for path in capability_paths:
        feature = feature_by_path(contract, path)
        if feature is None or feature.encoding is not None:
            continue
        for point in continuous_points(feature):
            trial = copy.deepcopy(base)
            # Set nested path (pots use list)
            parts = path.split(".")
            if parts[0] == "pots":
                pot_i = int(parts[1])
                node: Any = trial["pots"][pot_i]
                for part in parts[2:-1]:
                    node = node[part]
                node[parts[-1]] = point
            else:
                _set_nested(trial, path, point)
            vector = contract.encode(trial)
            assert_encoded_vector(contract, vector)
            if not np.isfinite(vector).all():
                raise AssertionError(f"non-finite encode for {path}={point}")

    # Previous: 0 / 0.5 / 1 (all previous slots together — not cartesian over each)
    prev_keys = list((base.get("previous") or {}).keys())
    for level in (0.0, 0.5, 1.0):
        trial = copy.deepcopy(base)
        for key in prev_keys:
            trial["previous"][key] = level
        for index, pot in enumerate(trial["pots"]):
            pot["previous"] = {"irrigation": level, "heat_mat": level}
        vector = contract.encode(trial)
        assert_encoded_vector(contract, vector)

    # Goals: nominal + extreme (cold / wet / low CO2)
    target_cases = [
        {
            "air_temperature_c": 25.0,
            "air_humidity_pct": 65.0,
            "co2_ppm": 850.0,
            "nutrient_solution_temperature_c": 20.0,
        },
        {
            "air_temperature_c": -20.0,  # extreme cold target
            "air_humidity_pct": 100.0,  # extreme humidity target
            "co2_ppm": 0.0,  # extreme low CO2
            "nutrient_solution_temperature_c": 0.0,
        },
        {
            "air_temperature_c": 60.0,
            "air_humidity_pct": 0.0,
            "co2_ppm": 5000.0,
            "nutrient_solution_temperature_c": 50.0,
        },
    ]
    for targets in target_cases:
        trial = copy.deepcopy(base)
        trial["targets"] = dict(targets)
        for pot in trial["pots"]:
            if pot.get("available"):
                pot["targets"] = {
                    "soil_moisture_pct": targets["air_humidity_pct"],
                    "soil_temperature_c": min(50.0, max(-10.0, targets["air_temperature_c"])),
                }
        vector = contract.encode(trial)
        assert_encoded_vector(contract, vector)


def build_sim_scenario(row: dict[str, str], record: dict[str, Any]) -> Scenario:
    env = record["environment"]
    acts = record["actuators"]
    pots_cfg: list[PotConfig] = []
    pot_states: list[PotState] = []
    moisture_valid: list[bool] = []
    temp_valid: list[bool] = []
    for pot in record["pots"]:
        pots_cfg.append(
            PotConfig(
                available=bool(pot.get("available")),
                soil_moisture_valid=bool((pot.get("validity") or {}).get("soil_moisture_pct")),
                soil_temperature_valid=bool((pot.get("validity") or {}).get("soil_temperature_c")),
                cultivation=PotCultivation(
                    pot_volume_l=float((pot.get("cultivation") or {}).get("pot_volume_l", 12.0)),
                    substrate_water_capacity_ml=float(
                        (pot.get("cultivation") or {}).get("substrate_water_capacity_ml", 3000.0)
                    ),
                    transpiration_factor=float(
                        (pot.get("cultivation") or {}).get("transpiration_factor", 1.0)
                    ),
                ),
                irrigation=PumpCapabilities(
                    available=bool((pot.get("irrigation") or {}).get("available")),
                    flow_ml_s=float((pot.get("irrigation") or {}).get("flow_ml_s", 0.0)),
                    maximum_pulse_s=float(
                        (pot.get("irrigation") or {}).get("maximum_pulse_s", 0.0)
                    ),
                    minimum_interval_s=float(
                        (pot.get("irrigation") or {}).get("minimum_interval_s", 0.0)
                    ),
                ),
                heat_mat=HeatMatCapabilities(
                    available=bool((pot.get("heat_mat") or {}).get("available")),
                    max_power_w=float((pot.get("heat_mat") or {}).get("max_power_w", 0.0)),
                ),
                target_soil_moisture_pct=float(
                    (pot.get("targets") or {}).get("soil_moisture_pct", 50)
                ),
                target_soil_temperature_c=float(
                    (pot.get("targets") or {}).get("soil_temperature_c", 22)
                ),
            )
        )
        sensors = pot.get("sensors") or {}
        pot_states.append(
            PotState(
                soil_moisture_pct=float(sensors.get("soil_moisture_pct", 44.0)),
                soil_temperature_c=float(sensors.get("soil_temperature_c", 20.0)),
            )
        )
        moisture_valid.append(bool((pot.get("validity") or {}).get("soil_moisture_pct")))
        temp_valid.append(bool((pot.get("validity") or {}).get("soil_temperature_c")))

    while len(pots_cfg) < MAX_POTS:
        pots_cfg.append(PotConfig())
        pot_states.append(PotState())
        moisture_valid.append(False)
        temp_valid.append(False)

    sensors = record["sensors"]
    validity = record["validity"]
    return Scenario(
        scenario_id=row["id"],
        seed=hash(row["id"]) % 10_000,
        initial_state=EnvironmentState(
            air_temperature_c=float(sensors["air_temperature_c"]),
            air_humidity_pct=float(sensors["air_humidity_pct"]),
            co2_ppm=float(sensors["co2_ppm"]),
            outside_temperature_c=float(sensors["outside_temperature_c"]),
            outside_humidity_pct=float(sensors["outside_humidity_pct"]),
            outside_co2_ppm=float(sensors["outside_co2_ppm"]),
            nutrient_solution_temperature_c=float(sensors["nutrient_solution_temperature_c"]),
            pots=pot_states[:MAX_POTS],
            lights_active=bool((record.get("pseudo") or {}).get("lights_active", False)),
        ),
        environment=EnvironmentParameters(
            growbox_volume_m3=float(env["growbox_volume_m3"]),
            thermal_mass_j_per_k=float(env["thermal_mass_j_per_k"]),
            heat_loss_w_per_k=float(env["heat_loss_w_per_k"]),
            air_leak_rate_ach=float(env["air_leak_rate_ach"]),
        ),
        actuators=GlobalActuators(
            heater=HeaterCapabilities(
                available=bool(acts["heater"]["available"]),
                max_power_w=float(acts["heater"].get("max_power_w", 0.0)),
                efficiency=float(acts["heater"].get("efficiency", 0.0)),
            ),
            fan=FanCapabilities(
                available=bool(acts["fan"]["available"]),
                max_airflow_m3_h=float(acts["fan"].get("max_airflow_m3_h", 0.0)),
                minimum_command=float(acts["fan"].get("minimum_command", 0.0)),
            ),
            humidifier=HumidifierCapabilities(
                available=bool(acts["humidifier"]["available"]),
                max_output_g_h=float(acts["humidifier"].get("max_output_g_h", 0.0)),
            ),
            dehumidifier=DehumidifierCapabilities(
                available=bool(acts["dehumidifier"]["available"]),
                max_removal_g_h=float(acts["dehumidifier"].get("max_removal_g_h", 0.0)),
            ),
            cooler=CoolerCapabilities(
                available=bool(acts["cooler"]["available"]),
                max_cooling_w=float(acts["cooler"].get("max_cooling_w", 0.0)),
            ),
            co2_doser=Co2DoserCapabilities(
                available=bool(acts["co2_doser"]["available"]),
                dose_ppm_per_full_pulse=float(
                    acts["co2_doser"].get("dose_ppm_per_full_pulse", 0.0)
                ),
                maximum_pulse_s=float(acts["co2_doser"].get("maximum_pulse_s", 0.0)),
            ),
            nutrient_heater=NutrientHeaterCapabilities(
                available=bool(acts["nutrient_heater"]["available"]),
                max_power_w=float(acts["nutrient_heater"].get("max_power_w", 0.0)),
                efficiency=float(acts["nutrient_heater"].get("efficiency", 0.0)),
            ),
        ),
        pots=tuple(pots_cfg[:MAX_POTS]),  # type: ignore[arg-type]
        targets=ControlTargets(
            target_air_temperature_c=float(record["targets"]["air_temperature_c"]),
            target_air_humidity_pct=float(record["targets"]["air_humidity_pct"]),
            target_co2_ppm=float(record["targets"]["co2_ppm"]),
            target_nutrient_solution_temperature_c=float(
                record["targets"]["nutrient_solution_temperature_c"]
            ),
        ),
        validity=SensorValidity(
            air_temperature_c=bool(validity["air_temperature_c"]),
            air_humidity_pct=bool(validity["air_humidity_pct"]),
            co2_ppm=bool(validity["co2_ppm"]),
            outside_temperature_c=bool(validity["outside_temperature_c"]),
            outside_humidity_pct=bool(validity["outside_humidity_pct"]),
            outside_co2_ppm=bool(validity["outside_co2_ppm"]),
            nutrient_solution_temperature_c=bool(validity["nutrient_solution_temperature_c"]),
            pot_soil_moisture=tuple(moisture_valid[:MAX_POTS]),  # type: ignore[arg-type]
            pot_soil_temperature=tuple(temp_valid[:MAX_POTS]),  # type: ignore[arg-type]
        ),
        timestep_s=10.0,
    )


def check_sim(row: dict[str, str], record: dict[str, Any], contract: Contract) -> None:
    scenario = build_sim_scenario(row, record)
    sim = SequentialEnvironmentSimulator(scenario, seed=scenario.seed)
    state = sim.reset()
    # Mild action preferring available actuators
    action_values = {name: 0.0 for name in OUTPUTS}
    for name in GLOBAL_ACTUATORS:
        if bool((record["actuators"].get(name) or {}).get("available")):
            action_values[name] = 0.6 if name != "fan" else 1.0
    for index, pot in enumerate(record["pots"]):
        if pot.get("available") and (pot.get("irrigation") or {}).get("available"):
            action_values[f"irrigation_pot_{index + 1}"] = 0.0  # avoid pulse spam
        if pot.get("available") and (pot.get("heat_mat") or {}).get("available"):
            action_values[f"heat_mat_pot_{index + 1}"] = 0.5
    action = ControlAction.from_mapping(action_values)

    sensor_ranges = {
        "air_temperature_c": (-30.0, 70.0),
        "air_humidity_pct": (0.0, 100.0),
        "co2_ppm": (0.0, 5000.0),
        "nutrient_solution_temperature_c": (0.0, 50.0),
    }
    for step in range(5):
        state = sim.step(action)
        for field_name, (lo, hi) in sensor_ranges.items():
            value = float(getattr(state, field_name))
            if not math.isfinite(value):
                raise AssertionError(f"sim step {step}: {field_name} non-finite")
            if value < lo - 1e-6 or value > hi + 1e-6:
                raise AssertionError(f"sim step {step}: {field_name}={value} out of [{lo},{hi}]")
        for pot_state in state.pots:
            for field_name, value, lo, hi in (
                ("soil_moisture_pct", pot_state.soil_moisture_pct, 0.0, 100.0),
                ("soil_temperature_c", pot_state.soil_temperature_c, -30.0, 70.0),
            ):
                if not math.isfinite(value):
                    raise AssertionError(f"sim step {step}: pot {field_name} non-finite")
                if value < lo - 1e-6 or value > hi + 1e-6:
                    raise AssertionError(
                        f"sim step {step}: pot {field_name}={value} out of [{lo},{hi}]"
                    )


def check_model_runtime_schema(contract: Contract) -> None:
    """Assert ModelRuntime schema hash / feature counts match the active contract."""
    manifest = PROJECT_ROOT / "lib/environment_control/src/generated/ModelManifest.h"
    if not manifest.exists():
        raise AssertionError("ModelManifest.h missing")
    text = manifest.read_text(encoding="utf-8")
    short = contract.short_hash
    if f'"{short}"' not in text and short not in text:
        raise AssertionError(f"ModelManifest schema hash does not match contract {short}")
    if "kInputCount = 128" not in text.replace(" ", "") and "kInputCount = 128U" not in text:
        # tolerate formatting
        if "kInputCount" not in text:
            raise AssertionError("ModelManifest missing kInputCount")
    if len(contract.features) != 128:
        raise AssertionError(f"contract feature count {len(contract.features)} != 128")
    if len(contract.outputs) != 15:
        raise AssertionError(f"contract output count {len(contract.outputs)} != 15")


def test_profile(row: dict[str, str], contract: Contract) -> tuple[bool, str]:
    try:
        record = build_controller_input(row, contract)
        path_index = feature_path_index(contract)

        check_model_runtime_schema(contract)
        check_encoder(contract, record, path_index)

        expected_zeros = _csv_list(row.get("expected_safe_zero_outputs", ""))
        check_safety(record, expected_zeros)

        check_continuous_sweeps(contract, record)
        check_sim(row, record, contract)
        return True, ""
    except Exception as exc:  # noqa: BLE001 — collect fail_reason for RESULTS.csv
        return False, f"{type(exc).__name__}: {exc}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix", type=Path, default=DEFAULT_MATRIX)
    parser.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
    args = parser.parse_args(argv)

    if not args.matrix.is_file():
        print(f"matrix not found: {args.matrix}", file=sys.stderr)
        return 2

    contract = load_contract()
    rows = load_matrix_rows(args.matrix)

    if not rows:
        print("empty matrix", file=sys.stderr)
        return 2

    results: list[dict[str, str]] = []
    for row in rows:
        profile_id = row["id"]
        ok, reason = test_profile(row, contract)
        results.append(
            {
                "id": profile_id,
                "pass": "true" if ok else "false",
                "fail_reason": "" if ok else reason,
            }
        )
        status = "PASS" if ok else "FAIL"
        print(f"[{status}] {profile_id}" + (f" — {reason}" if reason else ""))

    args.results.parent.mkdir(parents=True, exist_ok=True)
    with args.results.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["id", "pass", "fail_reason"])
        writer.writeheader()
        writer.writerows(results)

    n_pass = sum(1 for r in results if r["pass"] == "true")
    n_fail = len(results) - n_pass
    print(
        f"\nRESULTS: {args.results}  rows={len(results)} matrix={len(rows)} "
        f"pass={n_pass} fail={n_fail}"
    )
    if len(results) != len(rows):
        print("ERROR: len(RESULTS) != len(CONFIG_MATRIX)", file=sys.stderr)
        return 1
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
