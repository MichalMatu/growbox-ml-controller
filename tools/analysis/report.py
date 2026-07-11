"""Validate and summarize NDJSON emitted by the demo firmware."""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections.abc import Mapping
from pathlib import Path
from statistics import fmean
from typing import Any, Iterable

TRACKED_OUTPUTS = ("heater", "fan", "humidifier", "irrigation")
TRACKED_TARGETS = {
    "air_temperature_c": "air_temperature_c",
    "air_humidity_pct": "air_humidity_pct",
    "co2_ppm": "co2_ppm",
    "soil_moisture_pct": "soil_moisture_pct",
}


def parse_log(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    records: list[dict[str, Any]] = []
    errors: list[str] = []
    with path.open(encoding="utf-8") as source:
        for line_number, line in enumerate(source, 1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                record = json.loads(stripped)
            except json.JSONDecodeError as exc:
                errors.append(f"line {line_number}: invalid JSON: {exc.msg}")
                continue
            if not isinstance(record, dict) or "type" not in record:
                errors.append(f"line {line_number}: expected an object with a type field")
                continue
            if record.get("type") == "invalid_serial_line":
                detail = record.get("error")
                suffix = f": {detail}" if isinstance(detail, str) and detail else ""
                errors.append(f"line {line_number}: captured invalid serial line{suffix}")
                continue
            records.append(record)
    return records, errors


def _finite_number(value: Any) -> float | None:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (OverflowError, TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def validate_decision(record: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for field in ("step", "sensors", "targets", "safe_output", "diagnostics"):
        if field not in record:
            errors.append(f"decision missing {field}")

    for field in ("sensors", "targets", "safe_output", "diagnostics"):
        if field in record and not isinstance(record[field], Mapping):
            errors.append(f"decision {field} must be an object")
    if "validity" in record and not isinstance(record["validity"], Mapping):
        errors.append("decision validity must be an object")

    safe_output = record.get("safe_output")
    if isinstance(safe_output, Mapping):
        for output_name in TRACKED_OUTPUTS:
            value = _finite_number(safe_output.get(output_name))
            if value is None or not 0.0 <= value <= 1.0:
                errors.append(f"safe_output.{output_name} must be finite and within 0..1")
    return errors


def analyse_records(records: Iterable[dict[str, Any]]) -> dict[str, Any]:
    decisions = [record for record in records if record.get("type") == "decision"]
    validation_errors = [error for record in decisions for error in validate_decision(record)]

    errors_by_target: dict[str, list[float]] = {name: [] for name in TRACKED_TARGETS}
    inference_times: list[float] = []
    safety_modifications = 0
    inference_errors = 0
    outputs: dict[str, list[float]] = {name: [] for name in TRACKED_OUTPUTS}

    for record in decisions:
        sensors = _mapping(record.get("sensors"))
        validity = _mapping(record.get("validity"))
        targets = _mapping(record.get("targets"))
        for sensor_name, target_name in TRACKED_TARGETS.items():
            if validity.get(sensor_name) is False:
                continue
            sensor = _finite_number(sensors.get(sensor_name))
            target = _finite_number(targets.get(target_name))
            if sensor is not None and target is not None:
                errors_by_target[sensor_name].append(abs(sensor - target))

        diagnostics = _mapping(record.get("diagnostics"))
        inference = _finite_number(diagnostics.get("inference_us"))
        if inference is not None:
            inference_times.append(inference)
        if diagnostics.get("safety_modified") is True:
            safety_modifications += 1
        status = diagnostics.get("inference_status", "ok")
        if status not in ("ok", 0, None):
            inference_errors += 1

        safe_output = _mapping(record.get("safe_output"))
        for name in TRACKED_OUTPUTS:
            value = _finite_number(safe_output.get(name))
            if value is not None:
                outputs[name].append(value)

    error_summary = {
        name: {
            "mean_absolute_error": fmean(values) if values else None,
            "maximum_absolute_error": max(values) if values else None,
        }
        for name, values in errors_by_target.items()
    }
    oscillations = {
        name: sum(
            1
            for previous_delta, delta in zip(
                (b - a for a, b in zip(values, values[1:])),
                (c - b for b, c in zip(values[1:], values[2:])),
            )
            if previous_delta * delta < 0
        )
        for name, values in outputs.items()
    }

    return {
        "decision_steps": len(decisions),
        "validation_error_count": len(validation_errors),
        "validation_errors": validation_errors,
        "target_errors": error_summary,
        "safety_modifications": safety_modifications,
        "inference_errors": inference_errors,
        "output_oscillations": oscillations,
        "mean_inference_us": fmean(inference_times) if inference_times else None,
        "maximum_inference_us": max(inference_times) if inference_times else None,
    }


def export_csv(records: Iterable[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "step",
        "simulated_time_s",
        *TRACKED_TARGETS,
        *(f"target_{name}" for name in TRACKED_TARGETS),
        *(f"output_{name}" for name in TRACKED_OUTPUTS),
        "inference_us",
        "safety_modified",
    ]
    with path.open("w", newline="", encoding="utf-8") as destination:
        writer = csv.DictWriter(destination, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            if record.get("type") != "decision":
                continue
            sensors = _mapping(record.get("sensors"))
            targets = _mapping(record.get("targets"))
            safe_output = _mapping(record.get("safe_output"))
            diagnostics = _mapping(record.get("diagnostics"))
            row: dict[str, Any] = {
                "step": record.get("step"),
                "simulated_time_s": record.get("simulated_time_s"),
                "inference_us": diagnostics.get("inference_us"),
                "safety_modified": diagnostics.get("safety_modified"),
            }
            for name in TRACKED_TARGETS:
                row[name] = sensors.get(name)
                row[f"target_{name}"] = targets.get(name)
            for name in TRACKED_OUTPUTS:
                row[f"output_{name}"] = safe_output.get(name)
            writer.writerow(row)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", type=Path)
    parser.add_argument("--csv", type=Path, help="Optionally export decision rows as CSV")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        records, parse_errors = parse_log(args.log)
    except OSError as exc:
        print(f"cannot read log: {exc}", file=sys.stderr)
        return 2
    report = analyse_records(records)
    report["parse_error_count"] = len(parse_errors)
    report["parse_errors"] = parse_errors
    if args.csv:
        export_csv(records, args.csv)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 1 if parse_errors or report["validation_error_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
