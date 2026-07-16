"""On-device engine audit: preset + stress matrix against flashed demo firmware.

Drives serial JSON protocol (replay mode), records raw/safe outputs and safety
reasons, evaluates control-policy heuristics, and writes a JSON report.
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import serial
from tools.ml.config_matrix import DEFAULT_MATRIX, matrix_cases
from tools.ml.scenario_payload import SCENARIO_PRESETS, default_scenario

DEFAULT_PORT = os.environ.get("GROWBOX_BOARD_PORT", "/dev/cu.usbmodem1101")
OUTPUT_NAMES = (
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


@dataclass
class Finding:
    severity: str  # info | warn | error
    case: str
    code: str
    message: str
    detail: dict[str, Any] = field(default_factory=dict)


class BoardSession:
    def __init__(self, port: str, *, baud: int = 115_200, timeout: float = 6.0) -> None:
        self.port = port
        self.baud = baud
        self.timeout = timeout
        self._ser: serial.Serial | None = None

    def __enter__(self) -> BoardSession:
        self._ser = serial.Serial(port=self.port, baudrate=self.baud, timeout=0.15)
        time.sleep(0.4)
        self._ser.reset_input_buffer()
        # Drain boot noise
        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline:
            self._ser.readline()
        return self

    def __exit__(self, *args: object) -> None:
        if self._ser is not None:
            self._ser.close()
            self._ser = None

    def send(
        self, command: dict[str, Any], *, expect: str, expect_cmd: str | None = None
    ) -> dict[str, Any]:
        assert self._ser is not None
        payload = json.dumps(command, separators=(",", ":")).encode("utf-8") + b"\n"
        self._ser.write(payload)
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
                raise RuntimeError(f"board error for {command.get('command')}: {response}")
            if response.get("type") != expect:
                continue
            if expect == "ack" and expect_cmd is not None and response.get("command") != expect_cmd:
                continue
            return response
        raise TimeoutError(f"timeout waiting for {expect} after {command.get('command')}")


def load_scenario_command(scenario: dict[str, Any]) -> dict[str, Any]:
    command: dict[str, Any] = {"command": "load_scenario"}
    for key, value in scenario.items():
        command[key] = value
    return command


def deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], value)  # type: ignore[arg-type]
        else:
            out[key] = copy.deepcopy(value)
    return out


def stress_cases() -> list[tuple[str, dict[str, Any]]]:
    """Named scenario overlays on top of nominal v4 pots scenario."""
    base = default_scenario(seed=200, preset="nominal")
    cases: list[tuple[str, dict[str, Any]]] = []

    for preset in SCENARIO_PRESETS:
        cases.append((f"preset:{preset}", default_scenario(seed=201, preset=preset)))

    cases.append(
        (
            "cold_below_target",
            deep_merge(
                base,
                {
                    "seed": 210,
                    "sensors": {"air_temperature_c": 16.0},
                    "targets": {"air_temperature_c": 25.0},
                },
            ),
        )
    )
    cases.append(
        (
            "hot_above_target",
            deep_merge(
                base,
                {
                    "seed": 211,
                    "sensors": {"air_temperature_c": 30.0},
                    "targets": {"air_temperature_c": 24.0},
                    "actuators": {
                        "cooler": {"available": True, "max_cooling_w": 200.0},
                    },
                },
            ),
        )
    )
    cases.append(
        (
            "overtemperature_alarm",
            deep_merge(
                base,
                {
                    "seed": 212,
                    "sensors": {"air_temperature_c": 36.0},
                    "previous": {"heater": 1.0, "fan": 0.0},
                    "actuators": {"fan": {"minimum_command": 0.2}},
                    "safety": {"maximum_air_temperature_c": 35.0, "alarm_air_temperature_c": 32.0},
                },
            ),
        )
    )
    cases.append(
        (
            "dry_air",
            deep_merge(
                base,
                {
                    "seed": 213,
                    "sensors": {"air_humidity_pct": 28.0},
                    "targets": {"air_humidity_pct": 65.0},
                },
            ),
        )
    )
    cases.append(
        (
            "wet_air",
            deep_merge(
                base,
                {
                    "seed": 214,
                    "sensors": {"air_humidity_pct": 88.0},
                    "targets": {"air_humidity_pct": 60.0},
                    "actuators": {
                        "dehumidifier": {"available": True, "max_removal_g_h": 200.0},
                        "humidifier": {"available": True, "max_output_g_h": 180.0},
                    },
                },
            ),
        )
    )
    cases.append(
        (
            "low_co2_with_doser",
            deep_merge(
                base,
                {
                    "seed": 215,
                    "sensors": {"co2_ppm": 420.0},
                    "targets": {"co2_ppm": 1000.0},
                    "actuators": {
                        "co2_doser": {
                            "available": True,
                            "dose_ppm_per_full_pulse": 120.0,
                            "maximum_pulse_s": 5.0,
                        }
                    },
                },
            ),
        )
    )
    cases.append(
        (
            "high_co2_with_doser",
            deep_merge(
                base,
                {
                    "seed": 216,
                    "sensors": {"co2_ppm": 1400.0},
                    "targets": {"co2_ppm": 900.0},
                    "actuators": {
                        "co2_doser": {
                            "available": True,
                            "dose_ppm_per_full_pulse": 120.0,
                            "maximum_pulse_s": 5.0,
                        }
                    },
                },
            ),
        )
    )
    cases.append(
        (
            "invalid_air_temperature",
            deep_merge(
                base,
                {
                    "seed": 217,
                    "validity": {"air_temperature_c": False},
                    "sensors": {"air_temperature_c": 0.0},
                },
            ),
        )
    )
    cases.append(
        (
            "invalid_humidity",
            deep_merge(base, {"seed": 218, "validity": {"air_humidity_pct": False}}),
        )
    )
    dry_soil = copy.deepcopy(base)
    dry_soil["seed"] = 219
    dry_soil["pots"][0]["sensors"]["soil_moisture_pct"] = 20.0
    dry_soil["pots"][0]["targets"]["soil_moisture_pct"] = 50.0
    dry_soil["pots"][0]["irrigation"]["available"] = True
    cases.append(("dry_soil_needs_irrigation", dry_soil))

    cold_soil = copy.deepcopy(base)
    cold_soil["seed"] = 220
    cold_soil["pots"][0]["sensors"]["soil_moisture_pct"] = 48.0
    cold_soil["pots"][0]["sensors"]["soil_temperature_c"] = 15.0
    cold_soil["pots"][0]["targets"]["soil_temperature_c"] = 24.0
    cold_soil["pots"][0]["heat_mat"] = {
        "available": True,
        "max_power_w": 40.0,
        "control_type": "binary",
    }
    cases.append(("cold_soil_heat_mat", cold_soil))
    cases.append(
        (
            "all_actuators_enabled_mixed",
            deep_merge(
                base,
                {
                    "seed": 221,
                    "sensors": {
                        "air_temperature_c": 20.0,
                        "air_humidity_pct": 45.0,
                        "co2_ppm": 500.0,
                        "nutrient_solution_temperature_c": 16.0,
                    },
                    "targets": {
                        "air_temperature_c": 26.0,
                        "air_humidity_pct": 65.0,
                        "co2_ppm": 1100.0,
                        "nutrient_solution_temperature_c": 22.0,
                    },
                    "actuators": {
                        "heater": {"available": True, "max_power_w": 180.0, "efficiency": 0.9},
                        "fan": {
                            "available": True,
                            "max_airflow_m3_h": 120.0,
                            "minimum_command": 0.2,
                        },
                        "humidifier": {"available": True, "max_output_g_h": 180.0},
                        "dehumidifier": {"available": True, "max_removal_g_h": 150.0},
                        "cooler": {"available": True, "max_cooling_w": 200.0},
                        "co2_doser": {
                            "available": True,
                            "dose_ppm_per_full_pulse": 120.0,
                            "maximum_pulse_s": 5.0,
                        },
                        "nutrient_heater": {
                            "available": True,
                            "max_power_w": 80.0,
                            "efficiency": 0.9,
                        },
                    },
                    "pots": [dict(p) for p in default_scenario(seed=1, preset="all_pots")["pots"]],
                },
            ),
        )
    )
    cases.append(
        (
            "lights_on_heat_assist",
            deep_merge(base, {"seed": 222, "pseudo": {"lights_active": True}}),
        )
    )
    cases.append(
        (
            "fan_only_disabled_rest",
            default_scenario(seed=223, preset="disabled_actuators"),
        )
    )
    return cases


def evaluate_expected_safe_zeros(
    case: str, safe: dict[str, Any], expected_zeros: list[str]
) -> list[Finding]:
    findings: list[Finding] = []
    for name in expected_zeros:
        if name not in OUTPUT_NAMES:
            findings.append(
                Finding("error", case, "unknown_expected_output", f"unknown output {name}")
            )
            continue
        value = float(safe.get(name, 0.0))
        if value > 1e-6:
            findings.append(
                Finding(
                    "error",
                    case,
                    "expected_safe_zero",
                    f"{name} safe={value} expected 0",
                    {"safe": safe.get(name), "raw": None},
                )
            )
    return findings


def evaluate_decision(
    case: str,
    scenario: dict[str, Any],
    decision: dict[str, Any],
    *,
    expected_safe_zeros: list[str] | None = None,
) -> list[Finding]:
    findings: list[Finding] = []
    diag = decision.get("diagnostics") or {}
    raw = decision.get("raw_output") or {}
    safe = decision.get("safe_output") or {}
    reasons = diag.get("safety_reasons") or decision.get("safety_reasons") or []

    if decision.get("schema_version") != 4:
        findings.append(
            Finding(
                "error", case, "schema_version", f"expected 4 got {decision.get('schema_version')}"
            )
        )
    if decision.get("schema_hash") != "457ddca8b0e5":
        findings.append(
            Finding("error", case, "schema_hash", f"unexpected hash {decision.get('schema_hash')}")
        )
    if diag.get("inference_status") not in (None, "ok"):
        # some firmwares nest differently
        status = diag.get("inference_status") or diag.get("model_status")
        if status not in ("ok", "Ok", None):
            findings.append(
                Finding("error", case, "inference", f"status={status}", {"diagnostics": diag})
            )

    for name in OUTPUT_NAMES:
        if name not in safe:
            findings.append(Finding("error", case, "missing_output", f"safe missing {name}"))
            continue
        val = float(safe[name])
        if not (0.0 <= val <= 1.0):
            findings.append(Finding("error", case, "out_of_range", f"{name}={val}"))

    if expected_safe_zeros:
        findings.extend(evaluate_expected_safe_zeros(case, safe, expected_safe_zeros))

    sensors = scenario.get("sensors") or {}
    targets = scenario.get("targets") or {}
    actuators = scenario.get("actuators") or {}
    validity = scenario.get("validity") or {}
    safety = scenario.get("safety") or {}

    # Unavailable actuators must be zeroed by safety
    for act_name, out_name in (
        ("heater", "heater"),
        ("fan", "fan"),
        ("humidifier", "humidifier"),
        ("dehumidifier", "dehumidifier"),
        ("cooler", "cooler"),
        ("co2_doser", "co2_doser"),
        ("nutrient_heater", "nutrient_heater"),
    ):
        act = actuators.get(act_name) or {}
        if act.get("available") is False and float(safe.get(out_name, 0)) > 1e-6:
            findings.append(
                Finding(
                    "error",
                    case,
                    "unavailable_not_zeroed",
                    f"{out_name} safe={safe.get(out_name)} but actuator unavailable",
                    {"raw": raw.get(out_name)},
                )
            )

    # Overtemperature: heater off, fan boosted
    t_air = float(sensors.get("air_temperature_c", 0))
    t_max = float(safety.get("maximum_air_temperature_c", 35))
    t_alarm = float(safety.get("alarm_air_temperature_c", 32))
    if validity.get("air_temperature_c", True) and t_air >= t_max:
        if float(safe.get("heater", 0)) > 1e-6:
            findings.append(
                Finding(
                    "error", case, "heater_on_overtemp", f"heater={safe.get('heater')} T={t_air}"
                )
            )
        alarm_fan = float(safety.get("alarm_minimum_fan", 0.6))
        if float(safe.get("fan", 0)) + 1e-6 < alarm_fan:
            findings.append(
                Finding(
                    "error",
                    case,
                    "fan_not_boosted_overtemp",
                    f"fan={safe.get('fan')} < alarm_min={alarm_fan}",
                )
            )

    # CO2 target reached -> doser off
    if (actuators.get("co2_doser") or {}).get("available") and validity.get("co2_ppm", True):
        if float(sensors.get("co2_ppm", 0)) >= float(targets.get("co2_ppm", 1e9)):
            if float(safe.get("co2_doser", 0)) > 1e-6:
                findings.append(
                    Finding(
                        "error", case, "co2_doser_above_target", f"safe co2={safe.get('co2_doser')}"
                    )
                )

    # Heater vs cooler mutual exclusion
    thr = float(safety.get("binary_threshold", 0.5))
    if float(safe.get("heater", 0)) >= thr and float(safe.get("cooler", 0)) >= thr:
        findings.append(
            Finding("error", case, "heater_cooler_both_on", "mutual exclusion violated")
        )

    # Humidifier vs dehumidifier mutual exclusion
    if float(safe.get("humidifier", 0)) >= thr and float(safe.get("dehumidifier", 0)) >= thr:
        findings.append(
            Finding("error", case, "humidity_both_on", "humidifier+dehumidifier both on")
        )

    # Policy heuristics (warn only): cold should tend to heat
    if (
        validity.get("air_temperature_c", True)
        and t_air < float(targets.get("air_temperature_c", t_air)) - 3.0
        and (actuators.get("heater") or {}).get("available", True)
        and t_air < t_alarm
    ):
        if float(safe.get("heater", 0)) < thr and float(raw.get("heater", 0)) < thr:
            findings.append(
                Finding(
                    "warn",
                    case,
                    "cold_no_heat",
                    f"T={t_air} target={targets.get('air_temperature_c')} heater raw/safe low",
                    {"raw_heater": raw.get("heater"), "safe_heater": safe.get("heater")},
                )
            )

    if (
        validity.get("air_temperature_c", True)
        and t_air > float(targets.get("air_temperature_c", t_air)) + 3.0
        and t_air < t_alarm
        and (actuators.get("cooler") or {}).get("available")
    ):
        if float(safe.get("cooler", 0)) < thr and float(raw.get("cooler", 0)) < thr:
            findings.append(
                Finding(
                    "warn",
                    case,
                    "hot_no_cool",
                    f"T={t_air} cooler not engaged",
                    {"raw_cooler": raw.get("cooler"), "safe_cooler": safe.get("cooler")},
                )
            )

    # Dry air -> humidifier
    rh = float(sensors.get("air_humidity_pct", 50))
    if (
        validity.get("air_humidity_pct", True)
        and rh < float(targets.get("air_humidity_pct", rh)) - 15.0
        and (actuators.get("humidifier") or {}).get("available", True)
    ):
        if float(safe.get("humidifier", 0)) < thr and float(raw.get("humidifier", 0)) < thr:
            findings.append(
                Finding(
                    "warn",
                    case,
                    "dry_no_humidify",
                    f"RH={rh} humidifier off",
                    {"raw": raw.get("humidifier"), "safe": safe.get("humidifier")},
                )
            )

    # Dry soil -> irrigation pot 1
    pots = scenario.get("pots") or []
    if pots:
        pot0 = pots[0]
        if pot0.get("available") and (pot0.get("irrigation") or {}).get("available"):
            soil = float((pot0.get("sensors") or {}).get("soil_moisture_pct", 50))
            target_soil = float((pot0.get("targets") or {}).get("soil_moisture_pct", 50))
            if (pot0.get("validity") or {}).get(
                "soil_moisture_pct", True
            ) and soil < target_soil - 10:
                if (
                    float(safe.get("irrigation_pot_1", 0)) < thr
                    and float(raw.get("irrigation_pot_1", 0)) < thr
                ):
                    findings.append(
                        Finding(
                            "warn",
                            case,
                            "dry_soil_no_irrigation",
                            f"soil={soil} target={target_soil} irrigation off",
                            {
                                "raw": raw.get("irrigation_pot_1"),
                                "safe": safe.get("irrigation_pot_1"),
                            },
                        )
                    )

    # Invalid air temp: heater should be forced off by safety
    if validity.get("air_temperature_c") is False and float(safe.get("heater", 0)) > 1e-6:
        findings.append(
            Finding("error", case, "heater_with_invalid_temp", f"heater={safe.get('heater')}")
        )

    # Saturated soil preset should not irrigate
    if case.endswith("saturated_soil") or "saturated" in case:
        if float(safe.get("irrigation_pot_1", 0)) > thr:
            findings.append(
                Finding(
                    "warn",
                    case,
                    "irrigate_when_saturated",
                    f"irrigation={safe.get('irrigation_pot_1')}",
                )
            )

    findings.append(
        Finding(
            "info",
            case,
            "snapshot",
            "decision snapshot",
            {
                "raw": {k: raw.get(k) for k in OUTPUT_NAMES},
                "safe": {k: safe.get(k) for k in OUTPUT_NAMES},
                "reasons": reasons,
                "diagnostics": diag,
                "model_version": decision.get("model_version"),
            },
        )
    )
    return findings


def run_case(
    session: BoardSession,
    case: str,
    scenario: dict[str, Any],
    *,
    steps: int = 1,
    expected_safe_zeros: list[str] | None = None,
) -> list[Finding]:
    findings: list[Finding] = []
    session.send({"command": "pause"}, expect="ack", expect_cmd="pause")
    session.send({"command": "mode", "value": "replay"}, expect="ack", expect_cmd="mode")
    session.send(load_scenario_command(scenario), expect="ack", expect_cmd="load_scenario")
    last_decision: dict[str, Any] | None = None
    for step_i in range(steps):
        decision = session.send({"command": "step"}, expect="decision")
        last_decision = decision
        findings.extend(
            evaluate_decision(
                f"{case}#s{step_i}",
                scenario,
                decision,
                expected_safe_zeros=expected_safe_zeros,
            )
        )
        # After first step sensors evolve on device; for multi-step closed physics
        # we only re-evaluate last decision strictly.
    if last_decision is not None and steps > 1:
        # keep multi-step roll summary
        findings.append(
            Finding(
                "info",
                case,
                "multistep_done",
                f"completed {steps} steps",
                {"last_safe": last_decision.get("safe_output")},
            )
        )
    return findings


def run_closed_loop_burst(session: BoardSession, steps: int = 20) -> list[Finding]:
    findings: list[Finding] = []
    case = "closed_loop_burst"
    session.send({"command": "pause"}, expect="ack", expect_cmd="pause")
    session.send({"command": "mode", "value": "closed_loop"}, expect="ack", expect_cmd="mode")
    # load nominal then step repeatedly (device advances demo sim)
    scenario = default_scenario(seed=300, preset="nominal")
    session.send(load_scenario_command(scenario), expect="ack", expect_cmd="load_scenario")
    trajectory: list[dict[str, Any]] = []
    for i in range(steps):
        decision = session.send({"command": "step"}, expect="decision")
        safe = decision.get("safe_output") or {}
        trajectory.append({"step": i, "safe": safe, "diag": decision.get("diagnostics")})
        findings.extend(evaluate_decision(f"{case}#s{i}", scenario, decision))
    findings.append(
        Finding(
            "info", case, "trajectory", f"{steps} closed-loop steps", {"trajectory": trajectory}
        )
    )
    return findings


def summarize(findings: list[Finding]) -> dict[str, Any]:
    errors = [f for f in findings if f.severity == "error"]
    warns = [f for f in findings if f.severity == "warn"]
    by_code: dict[str, int] = {}
    for f in findings:
        if f.severity in ("error", "warn"):
            by_code[f.code] = by_code.get(f.code, 0) + 1
    return {
        "error_count": len(errors),
        "warn_count": len(warns),
        "info_count": sum(1 for f in findings if f.severity == "info"),
        "by_code": dict(sorted(by_code.items(), key=lambda kv: -kv[1])),
        "errors": [asdict(f) for f in errors],
        "warns": [asdict(f) for f in warns],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", default=DEFAULT_PORT)
    parser.add_argument("--report", type=Path, default=Path("build/audit/board_engine_audit.json"))
    parser.add_argument(
        "--matrix",
        type=Path,
        default=None,
        help="Run CONFIG_MATRIX profiles (default: docs/CONFIG_MATRIX.csv when --matrix-only)",
    )
    parser.add_argument(
        "--matrix-only",
        action="store_true",
        help="Run only CONFIG_MATRIX profiles (no built-in stress cases)",
    )
    parser.add_argument("--closed-loop-steps", type=int, default=15)
    parser.add_argument("--timeout", type=float, default=8.0)
    args = parser.parse_args(argv)

    if not Path(args.port).exists():
        print(f"board port missing: {args.port}", file=sys.stderr)
        return 2

    matrix_path = args.matrix
    if args.matrix_only and matrix_path is None:
        matrix_path = DEFAULT_MATRIX

    matrix_profile_cases: list[tuple[str, dict[str, Any], list[str]]] = []
    if matrix_path is not None:
        if not matrix_path.is_file():
            print(f"matrix not found: {matrix_path}", file=sys.stderr)
            return 2
        matrix_profile_cases = matrix_cases(matrix_path)

    cases: list[tuple[str, dict[str, Any], list[str] | None]] = []
    if not args.matrix_only:
        cases.extend((name, scenario, None) for name, scenario in stress_cases())
    cases.extend((name, scenario, expected) for name, scenario, expected in matrix_profile_cases)
    all_findings: list[Finding] = []
    case_results: list[dict[str, Any]] = []

    print(f"audit start port={args.port} cases={len(cases)}", flush=True)
    with BoardSession(args.port, timeout=args.timeout) as session:
        for name, scenario, expected_safe_zeros in cases:
            print(f"  case {name}...", flush=True)
            try:
                findings = run_case(
                    session,
                    name,
                    scenario,
                    steps=1,
                    expected_safe_zeros=expected_safe_zeros,
                )
                # a few multi-step stress cases (not for CONFIG_MATRIX rows)
                if expected_safe_zeros is None and name in {
                    "cold_below_target",
                    "hot_above_target",
                    "dry_soil_needs_irrigation",
                    "all_actuators_enabled_mixed",
                    "preset:nominal",
                }:
                    findings.extend(run_case(session, f"{name}/roll5", scenario, steps=5))
            except Exception as exc:  # noqa: BLE001
                findings = [Finding("error", name, "session_exception", str(exc))]
            all_findings.extend(findings)
            snap = next((f for f in findings if f.code == "snapshot"), None)
            case_results.append(
                {
                    "case": name,
                    "errors": [asdict(f) for f in findings if f.severity == "error"],
                    "warns": [asdict(f) for f in findings if f.severity == "warn"],
                    "snapshot": snap.detail if snap else {},
                }
            )
            err_n = sum(1 for f in findings if f.severity == "error")
            warn_n = sum(1 for f in findings if f.severity == "warn")
            print(f"    -> errors={err_n} warns={warn_n}", flush=True)

        if not args.matrix_only:
            print("  closed_loop_burst...", flush=True)
            try:
                cl = run_closed_loop_burst(session, steps=args.closed_loop_steps)
                all_findings.extend(cl)
            except Exception as exc:  # noqa: BLE001
                all_findings.append(
                    Finding("error", "closed_loop_burst", "session_exception", str(exc))
                )

    summary = summarize(all_findings)
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "port": args.port,
        "case_count": len(cases),
        "summary": summary,
        "cases": case_results,
        "findings": [
            asdict(f)
            for f in all_findings
            if f.severity != "info" or f.code in {"trajectory", "multistep_done"}
        ],
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"report: {args.report}")
    return 1 if summary["error_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
