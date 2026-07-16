"""Audit all 2^15 sensor validity masks on the board (32 768 combinations).

Each case fixes actuator availability and off-target sensor *values*; only validity
checkboxes vary. Verification is rule-based:

  ERRORS (must pass):
    - inference ok, outputs in [0,1]
    - safety hard zeros when sensor invalid or actuator unavailable
    - mutual exclusion (heater+cooler, humidifier+dehumidifier)

  WARNS (ML policy — only when that sensor is valid and actuator available):
    - cold air -> heater should engage
    - dry air -> humidifier
    - low CO2 -> co2_doser
    - dry soil pot1 -> irrigation_pot_1

Checkpoint: build/audit/validity_matrix_checkpoint.jsonl
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
import time
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tools.ml.board_engine_audit import (
    BoardSession,
    Finding,
    evaluate_decision,
    load_scenario_command,
    summarize,
)
from tools.ml.scenario_payload import default_scenario

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CHECKPOINT = PROJECT_ROOT / "build" / "audit" / "validity_matrix_checkpoint.jsonl"
DEFAULT_REPORT = PROJECT_ROOT / "build" / "audit" / "validity_matrix_audit.json"
MASK_COUNT = 1 << 15

# Bit order for mask 0..32767 (matches panel validity paths).
VALIDITY_SLOTS: tuple[tuple[str, str], ...] = (
    ("global", "air_temperature_c"),
    ("global", "air_humidity_pct"),
    ("global", "co2_ppm"),
    ("global", "nutrient_solution_temperature_c"),
    ("global", "outside_temperature_c"),
    ("global", "outside_humidity_pct"),
    ("global", "outside_co2_ppm"),
    ("pot0", "soil_moisture_pct"),
    ("pot0", "soil_temperature_c"),
    ("pot1", "soil_moisture_pct"),
    ("pot1", "soil_temperature_c"),
    ("pot2", "soil_moisture_pct"),
    ("pot2", "soil_temperature_c"),
    ("pot3", "soil_moisture_pct"),
    ("pot3", "soil_temperature_c"),
)


def mask_label(mask: int) -> str:
    parts: list[str] = []
    for bit, (kind, name) in enumerate(VALIDITY_SLOTS):
        if (mask >> bit) & 1:
            short = name.replace("soil_", "").replace("_pct", "").replace("_c", "")
            parts.append(f"pot{kind[-1]}_{short}" if kind.startswith("pot") else short)
    return "+".join(parts) if parts else "none"


def apply_mask(scenario: dict[str, Any], mask: int) -> None:
    for bit, (kind, name) in enumerate(VALIDITY_SLOTS):
        on = bool((mask >> bit) & 1)
        if kind == "global":
            scenario["validity"][name] = on
        else:
            pot_index = int(kind[-1])
            scenario["pots"][pot_index]["available"] = True
            scenario["pots"][pot_index]["validity"][name] = on
            if name == "soil_moisture_pct":
                scenario["pots"][pot_index]["irrigation"]["available"] = True
                scenario["pots"][pot_index]["irrigation"]["flow_ml_s"] = 22.0
                scenario["pots"][pot_index]["irrigation"]["maximum_pulse_s"] = 4.0
            if name == "soil_temperature_c":
                scenario["pots"][pot_index]["heat_mat"]["available"] = True
                scenario["pots"][pot_index]["heat_mat"]["max_power_w"] = 25.0


def base_audit_scenario() -> dict[str, Any]:
    """Full SKU, all actuators on, readings clearly off-target for ML heuristics."""
    scenario = default_scenario(seed=9001, preset="all_pots")
    scenario["sensors"].update(
        {
            "air_temperature_c": 16.0,
            "air_humidity_pct": 35.0,
            "co2_ppm": 500.0,
            "nutrient_solution_temperature_c": 14.0,
            "outside_temperature_c": 10.0,
            "outside_humidity_pct": 40.0,
            "outside_co2_ppm": 420.0,
        }
    )
    scenario["targets"].update(
        {
            "air_temperature_c": 25.0,
            "air_humidity_pct": 65.0,
            "co2_ppm": 1000.0,
            "nutrient_solution_temperature_c": 22.0,
        }
    )
    scenario["actuators"].update(
        {
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
            "humidifier": {"available": True, "max_output_g_h": 180.0, "control_type": "binary"},
            "dehumidifier": {"available": True, "max_removal_g_h": 80.0, "control_type": "binary"},
            "cooler": {"available": True, "max_cooling_w": 200.0, "control_type": "binary"},
            "co2_doser": {
                "available": True,
                "dose_ppm_per_full_pulse": 120.0,
                "maximum_pulse_s": 5.0,
                "control_type": "binary",
            },
            "nutrient_heater": {
                "available": True,
                "max_power_w": 150.0,
                "efficiency": 0.95,
                "control_type": "binary",
            },
        }
    )
    for index in range(4):
        pot = scenario["pots"][index]
        pot["available"] = True
        pot["validity"] = copy.deepcopy(pot.get("validity") or {})
        pot["sensors"] = copy.deepcopy(pot.get("sensors") or {})
        pot["targets"] = copy.deepcopy(pot.get("targets") or {})
        pot["irrigation"] = copy.deepcopy(pot.get("irrigation") or {})
        pot["heat_mat"] = copy.deepcopy(pot.get("heat_mat") or {})
        pot["sensors"]["soil_moisture_pct"] = 30.0
        pot["sensors"]["soil_temperature_c"] = 18.0
        pot["targets"]["soil_moisture_pct"] = 50.0
        pot["targets"]["soil_temperature_c"] = 22.0
        pot["irrigation"]["available"] = True
        pot["irrigation"]["flow_ml_s"] = 22.0
        pot["irrigation"]["maximum_pulse_s"] = 4.0
        pot["heat_mat"]["available"] = True
        pot["heat_mat"]["max_power_w"] = 25.0
    return scenario


def scenario_for_mask(mask: int) -> dict[str, Any]:
    scenario = copy.deepcopy(base_audit_scenario())
    scenario["seed"] = 9000 + mask
    apply_mask(scenario, mask)
    return scenario


def evaluate_validity_rules(
    case: str, scenario: dict[str, Any], decision: dict[str, Any]
) -> list[Finding]:
    """Safety + ML policy via evaluate_decision; extra hard zeros when validity is off."""
    findings = list(evaluate_decision(case, scenario, decision, expected_safe_zeros=None))

    validity = scenario.get("validity") or {}
    safe = decision.get("safe_output") or {}

    def hard_zero(output: str, code: str, message: str) -> None:
        if float(safe.get(output, 0)) > 1e-6:
            findings.append(Finding("error", case, code, message, {"safe": safe.get(output)}))

    if not validity.get("air_temperature_c", False):
        hard_zero("heater", "invalid_temp_heater_on", "heater must be 0 without valid air T")
    if not validity.get("air_humidity_pct", False):
        hard_zero("humidifier", "invalid_rh_humidifier_on", "humidifier must be 0")
        hard_zero("dehumidifier", "invalid_rh_dehumidifier_on", "dehumidifier must be 0")
    if not validity.get("co2_ppm", False):
        hard_zero("co2_doser", "invalid_co2_doser_on", "co2_doser must be 0")
    if not validity.get("nutrient_solution_temperature_c", False):
        hard_zero("nutrient_heater", "invalid_nutrient_heater_on", "nutrient_heater must be 0")

    for index in range(4):
        pot = scenario["pots"][index]
        pot_validity = pot.get("validity") or {}
        irr_out = f"irrigation_pot_{index + 1}"
        heat_out = f"heat_mat_pot_{index + 1}"
        if not pot_validity.get("soil_moisture_pct", False):
            hard_zero(irr_out, f"invalid_moisture_{irr_out}", f"{irr_out} must be 0")
        if not pot_validity.get("soil_temperature_c", False):
            hard_zero(heat_out, f"invalid_soil_t_{heat_out}", f"{heat_out} must be 0")

    return findings


def _load_done(checkpoint: Path) -> set[int]:
    if not checkpoint.is_file():
        return set()
    done: set[int] = set()
    for line in checkpoint.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        if record.get("status") in ("ok", "fail"):
            done.add(int(record["mask"]))
    return done


def _append_checkpoint(checkpoint: Path, record: dict[str, Any]) -> None:
    checkpoint.parent.mkdir(parents=True, exist_ok=True)
    with checkpoint.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, separators=(",", ":")) + "\n")


def run_board_case(session: BoardSession, mask: int) -> dict[str, Any]:
    scenario = scenario_for_mask(mask)
    session.send({"command": "pause"}, expect="ack", expect_cmd="pause")
    session.send({"command": "mode", "value": "replay"}, expect="ack", expect_cmd="mode")
    session.send(load_scenario_command(scenario), expect="ack", expect_cmd="load_scenario")
    return session.send({"command": "step"}, expect="decision")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", default="/dev/cu.usbmodem1101")
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--timeout", type=float, default=8.0)
    parser.add_argument("--max-cases", type=int, default=None, help="Limit new cases (debug)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    print(f"validity masks: {MASK_COUNT} (2^15 sensor slots)")
    if args.dry_run:
        print("examples:")
        for mask in (0, 1, 7, 32767):
            print(f"  mask={mask:5d} on=[{mask_label(mask)}]")
        est_h = MASK_COUNT * 0.35 / 3600
        print(f"estimated board time @0.35s/case: ~{est_h:.1f} h")
        return 0

    if not Path(args.port).exists():
        print(f"port missing: {args.port}", file=sys.stderr)
        return 2

    done = _load_done(args.checkpoint)
    pending = MASK_COUNT - len(done)
    print(f"checkpoint done={len(done)} pending={pending}", flush=True)

    all_findings: list[Finding] = []
    failures: list[dict[str, Any]] = []
    ran = 0

    with BoardSession(args.port, timeout=args.timeout) as session:
        for mask in range(MASK_COUNT):
            if mask in done:
                continue
            if args.max_cases is not None and ran >= args.max_cases:
                break
            t0 = time.monotonic()
            case = f"V{mask:05d}:{mask_label(mask)}"
            try:
                decision = run_board_case(session, mask)
                findings = evaluate_validity_rules(case, scenario_for_mask(mask), decision)
                errs = [f for f in findings if f.severity == "error"]
                status = "ok" if not errs else "fail"
            except Exception as exc:  # noqa: BLE001
                findings = [Finding("error", case, "session_exception", str(exc))]
                errs = findings
                status = "error"
            elapsed_ms = int((time.monotonic() - t0) * 1000)
            warns = [f for f in findings if f.severity == "warn"]
            _append_checkpoint(
                args.checkpoint,
                {
                    "mask": mask,
                    "case": case,
                    "status": status,
                    "errors": len(errs),
                    "warns": len(warns),
                    "elapsed_ms": elapsed_ms,
                    "ts": datetime.now(UTC).isoformat(),
                },
            )
            all_findings.extend(findings)
            if errs or warns:
                failures.append(
                    {
                        "mask": mask,
                        "case": case,
                        "errors": [asdict(f) for f in errs],
                        "warns": [asdict(f) for f in warns],
                    }
                )
            ran += 1
            if ran % 100 == 0 or errs:
                print(
                    f"  [{len(done) + ran}/{MASK_COUNT}] {case} e={len(errs)} w={len(warns)} {elapsed_ms}ms",
                    flush=True,
                )

    summary = summarize(all_findings)
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "mask_count": MASK_COUNT,
        "executed_this_run": ran,
        "checkpoint_done": len(done) + ran,
        "summary": summary,
        "failures": failures[:500],
        "failure_truncated": max(0, len(failures) - 500),
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"report: {args.report}")
    return 1 if summary["error_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
