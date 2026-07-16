"""CONFIG_MATRIX.csv — load rows, build scenarios, board replay bundles."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from .contract import ACTIVE_CONTRACT_PATH, Contract, load_contract
from .scenario_payload import default_scenario
from .simulator import MAX_POTS

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MATRIX = PROJECT_ROOT / "docs" / "CONFIG_MATRIX.csv"
DEFAULT_RESULTS = PROJECT_ROOT / "build" / "audit" / "CONFIG_MATRIX_RESULTS.csv"

GLOBAL_SENSORS = (
    "air_temperature_c",
    "air_humidity_pct",
    "co2_ppm",
    "nutrient_solution_temperature_c",
    "outside_temperature_c",
    "outside_humidity_pct",
    "outside_co2_ppm",
)

GLOBAL_ACTUATORS = (
    "heater",
    "fan",
    "humidifier",
    "dehumidifier",
    "cooler",
    "co2_doser",
    "nutrient_heater",
)

OUTPUTS = (
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

OP_ACTUATOR_CAPS: dict[str, dict[str, float]] = {
    "heater": {"max_power_w": 180.0, "efficiency": 0.9},
    "fan": {"max_airflow_m3_h": 120.0, "minimum_command": 0.2},
    "humidifier": {"max_output_g_h": 180.0},
    "dehumidifier": {"max_removal_g_h": 80.0},
    "cooler": {"max_cooling_w": 200.0},
    "co2_doser": {"dose_ppm_per_full_pulse": 120.0, "maximum_pulse_s": 5.0},
    "nutrient_heater": {"max_power_w": 150.0, "efficiency": 0.95},
}

SENSOR_NOMINAL: dict[str, float] = {
    "air_temperature_c": 22.0,
    "air_humidity_pct": 58.0,
    "co2_ppm": 920.0,
    "nutrient_solution_temperature_c": 20.0,
    "outside_temperature_c": 18.0,
    "outside_humidity_pct": 52.0,
    "outside_co2_ppm": 420.0,
}

# Below contract target (850 ppm) so co2_doser availability is testable, not target-reached.
CO2_BELOW_TARGET_PPM = 500.0


def _parse_bool(value: str) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def csv_list(value: str) -> list[str]:
    text = (value or "").strip()
    if not text or text in {"∅", "empty"}:
        return []
    return [part.strip() for part in text.split(",") if part.strip()]


def load_matrix_rows(path: Path | None = None) -> list[dict[str, str]]:
    matrix_path = path or DEFAULT_MATRIX
    with matrix_path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def build_controller_input(row: dict[str, str], contract: Contract) -> dict[str, Any]:
    """Build a full wire-protocol scenario from one CONFIG_MATRIX row."""
    record = default_scenario(seed=hash(row["id"]) % 10_000, contract=contract)

    for sensor in GLOBAL_SENSORS:
        valid = _parse_bool(row[f"valid_{sensor}"])
        record["validity"][sensor] = valid
        record["sensors"][sensor] = float(SENSOR_NOMINAL[sensor])

    if _parse_bool(row.get("avail_co2_doser", "")) and _parse_bool(row.get("valid_co2_ppm", "")):
        record["sensors"]["co2_ppm"] = CO2_BELOW_TARGET_PPM

    for name in GLOBAL_ACTUATORS:
        available = _parse_bool(row[f"avail_{name}"])
        act = record["actuators"].setdefault(name, {})
        act["available"] = available
        caps = OP_ACTUATOR_CAPS[name]
        for key, value in caps.items():
            act[key] = float(value if available else 0.0)
        if "control_type" not in act:
            act["control_type"] = "binary" if name != "fan" else "pwm"

    pots: list[dict[str, Any]] = []
    for index in range(1, MAX_POTS + 1):
        available = _parse_bool(row[f"pot{index}_available"])
        moisture_valid = _parse_bool(row[f"pot{index}_soil_moisture_valid"])
        temp_valid = _parse_bool(row[f"pot{index}_soil_temperature_valid"])
        irr_available = _parse_bool(row[f"pot{index}_irrigation_available"])
        heat_available = _parse_bool(row[f"pot{index}_heat_mat_available"])
        irr_type = (row.get(f"pot{index}_irrigation_control_type") or "binary").strip()
        heat_type = (row.get(f"pot{index}_heat_mat_control_type") or "binary").strip()
        pot = {
            "available": available,
            "sensors": {
                "soil_moisture_pct": 44.0 if moisture_valid else 50.0,
                "soil_temperature_c": 22.0 if temp_valid else 20.0,
            },
            "validity": {
                "soil_moisture_pct": moisture_valid,
                "soil_temperature_c": temp_valid,
            },
            "cultivation": {
                "pot_volume_l": 12.0 if available else 10.0,
                "substrate_water_capacity_ml": 3600.0 if available else 3000.0,
                "transpiration_factor": 1.0,
            },
            "targets": {
                "soil_moisture_pct": 50.0,
                "soil_temperature_c": 22.0,
            },
            "irrigation": {
                "available": irr_available and available,
                "flow_ml_s": 22.0 if irr_available and available else 0.0,
                "maximum_pulse_s": 4.0 if irr_available and available else 0.0,
                "minimum_interval_s": 600.0 if irr_available and available else 0.0,
                "control_type": irr_type if irr_type in {"binary", "pwm"} else "binary",
            },
            "heat_mat": {
                "available": heat_available and available,
                "max_power_w": 25.0 if heat_available and available else 0.0,
                "control_type": heat_type if heat_type in {"binary", "pwm"} else "binary",
            },
            "previous": {"irrigation": 0.0, "heat_mat": 0.0},
        }
        pots.append(pot)
    record["pots"] = pots

    lights = row["id"] == "L1" or row.get("name") == "lights_on_runtime"
    record.setdefault("pseudo", {})["lights_active"] = bool(lights)

    record["targets"] = {
        "air_temperature_c": 25.0,
        "air_humidity_pct": 65.0,
        "co2_ppm": 850.0,
        "nutrient_solution_temperature_c": 20.0,
    }
    record["previous"] = {name: 0.0 for name in GLOBAL_ACTUATORS}
    return record


def matrix_cases(
    path: Path | None = None,
    *,
    contract: Contract | None = None,
) -> list[tuple[str, dict[str, Any], list[str]]]:
    """Return (case_id, scenario, expected_safe_zero_outputs) for each matrix row."""
    contract = contract or load_contract(ACTIVE_CONTRACT_PATH)
    cases: list[tuple[str, dict[str, Any], list[str]]] = []
    for row in load_matrix_rows(path):
        scenario = build_controller_input(row, contract)
        expected = csv_list(row.get("expected_safe_zero_outputs", ""))
        cases.append((f"matrix:{row['id']}", scenario, expected))
    return cases


def load_scenario_command(scenario: dict[str, Any]) -> dict[str, Any]:
    command: dict[str, Any] = {"command": "load_scenario"}
    for key, value in scenario.items():
        command[key] = value
    return command


def replay_commands_for_scenario(scenario: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {"command": "pause"},
        {"command": "mode", "value": "replay"},
        load_scenario_command(scenario),
        {"command": "step"},
    ]


def write_replay_scripts(
    out_dir: Path,
    path: Path | None = None,
    *,
    contract: Contract | None = None,
) -> list[Path]:
    """Write one JSONL replay script per matrix profile (pause/mode/load/step)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    manifest_rows: list[dict[str, str]] = []
    for case_id, scenario, expected in matrix_cases(path, contract=contract):
        profile_id = case_id.removeprefix("matrix:")
        destination = out_dir / f"{profile_id}.jsonl"
        lines = [
            json.dumps(command, separators=(",", ":"))
            for command in replay_commands_for_scenario(scenario)
        ]
        destination.write_text("\n".join(lines) + "\n", encoding="utf-8")
        written.append(destination)
        manifest_rows.append(
            {
                "id": profile_id,
                "case": case_id,
                "script": str(destination.relative_to(out_dir)),
                "expected_safe_zero_outputs": ",".join(expected),
            }
        )
    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps({"profiles": manifest_rows, "count": len(manifest_rows)}, indent=2) + "\n",
        encoding="utf-8",
    )
    written.append(manifest_path)
    return written


def main(argv: list[str] | None = None) -> int:
    import argparse
    import sys

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix", type=Path, default=DEFAULT_MATRIX)
    parser.add_argument(
        "--write-scripts",
        type=Path,
        metavar="OUT_DIR",
        help="Write per-profile JSONL replay scripts for board_engine_audit / serial replay",
    )
    args = parser.parse_args(argv)

    if args.write_scripts is None:
        parser.print_help()
        return 2

    if not args.matrix.is_file():
        print(f"matrix not found: {args.matrix}", file=sys.stderr)
        return 2

    written = write_replay_scripts(args.write_scripts, args.matrix)
    print(f"wrote {len(written) - 1} replay scripts + manifest under {args.write_scripts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
