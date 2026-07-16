from __future__ import annotations

import csv
import json

import pytest

from tools.analysis.report import analyse_records, export_csv, main, parse_log


def _decision() -> dict[str, object]:
    return {
        "type": "decision",
        "step": 1,
        "simulated_time_s": 30,
        "sensors": {
            "air_temperature_c": 23.0,
            "air_humidity_pct": 60.0,
            "co2_ppm": 900.0,
            "soil_moisture_pct": 50.0,
        },
        "validity": {
            "air_temperature_c": True,
            "air_humidity_pct": True,
            "co2_ppm": True,
            "soil_moisture_pct": True,
        },
        "targets": {
            "air_temperature_c": 25.0,
            "air_humidity_pct": 65.0,
            "co2_ppm": 850.0,
            "soil_moisture_pct": 52.0,
        },
        "safe_output": {
            "heater": 0.5,
            "fan": 0.2,
            "humidifier": 0.0,
            "irrigation": 0.0,
        },
        "diagnostics": {
            "inference_us": 120,
            "safety_modified": False,
            "inference_status": "ok",
        },
    }


@pytest.mark.parametrize("field", ("sensors", "validity", "targets", "safe_output", "diagnostics"))
@pytest.mark.parametrize("invalid_value", (None, [], "not-an-object"))
def test_malformed_nested_objects_are_validation_errors(field, invalid_value):
    record = _decision()
    record[field] = invalid_value

    report = analyse_records([record])

    assert f"decision {field} must be an object" in report["validation_errors"]
    assert report["validation_error_count"] >= 1


def test_metric_extraction_ignores_invalid_types_and_overflowing_integers():
    record = _decision()
    record["sensors"] = {
        "air_temperature_c": [],
        "air_humidity_pct": 10**1000,
        "co2_ppm": {"value": 900},
        "soil_moisture_pct": True,
    }
    record["safe_output"] = {
        "heater": [],
        "fan": 10**1000,
        "humidifier": None,
        "irrigation": True,
    }
    record["diagnostics"] = {
        "inference_us": 10**1000,
        "safety_modified": [],
        "inference_status": [],
    }

    report = analyse_records([record])

    assert all(
        summary["mean_absolute_error"] is None for summary in report["target_errors"].values()
    )
    assert report["mean_inference_us"] is None
    assert report["maximum_inference_us"] is None
    assert report["output_oscillations"] == {
        "heater": 0,
        "fan": 0,
        "humidifier": 0,
        "irrigation": 0,
    }


def test_target_errors_skip_sensors_with_false_validity_mask():
    masked = _decision()
    masked["sensors"]["air_temperature_c"] = -100.0  # type: ignore[index]
    masked["validity"]["air_temperature_c"] = False  # type: ignore[index]

    valid = _decision()
    valid["sensors"]["air_temperature_c"] = 24.0  # type: ignore[index]

    report = analyse_records([masked, valid])

    assert report["target_errors"]["air_temperature_c"] == {
        "mean_absolute_error": 1.0,
        "maximum_absolute_error": 1.0,
    }
    assert report["target_errors"]["air_humidity_pct"]["mean_absolute_error"] == 5.0


def test_csv_export_handles_malformed_nested_objects(tmp_path):
    record = _decision()
    for field, value in {
        "sensors": None,
        "targets": [],
        "safe_output": "not-an-object",
        "diagnostics": 3,
    }.items():
        record[field] = value
    destination = tmp_path / "report.csv"

    export_csv([record], destination)

    with destination.open(newline="", encoding="utf-8") as source:
        rows = list(csv.DictReader(source))
    assert len(rows) == 1
    assert rows[0]["step"] == "1"
    assert rows[0]["air_temperature_c"] == ""
    assert rows[0]["output_heater"] == ""
    assert rows[0]["inference_us"] == ""


def test_invalid_serial_capture_marker_is_a_parse_error_and_fails_cli(tmp_path, capsys):
    path = tmp_path / "corrupt-capture.ndjson"
    path.write_text(
        json.dumps(
            {
                "type": "invalid_serial_line",
                "captured_at": "2026-07-11T10:00:00+00:00",
                "error": "Expecting value",
                "line": "not-json",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    records, errors = parse_log(path)
    assert records == []
    assert errors == ["line 1: captured invalid serial line: Expecting value"]

    assert main([str(path)]) == 1
    report = json.loads(capsys.readouterr().out)
    assert report["decision_steps"] == 0
    assert report["parse_error_count"] == 1
