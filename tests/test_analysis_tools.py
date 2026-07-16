from __future__ import annotations

import json

import pytest

from tools.analysis.report import analyse_records, parse_log
from tools.serial import replay as replay_module
from tools.serial.replay import ReplayError, load_commands, replay


def _decision(step: int, temperature: float, output: float, inference_us: int):
    return {
        "type": "decision",
        "step": step,
        "sensors": {
            "air_temperature_c": temperature,
            "air_humidity_pct": 60.0,
            "co2_ppm": 900.0,
            "soil_moisture_pct": 50.0,
        },
        "targets": {
            "air_temperature_c": 25.0,
            "air_humidity_pct": 65.0,
            "co2_ppm": 850.0,
            "soil_moisture_pct": 52.0,
        },
        "safe_output": {
            "heater": output,
            "fan": 0.2,
            "humidifier": 0.0,
            "irrigation": 0.0,
        },
        "diagnostics": {
            "inference_us": inference_us,
            "safety_modified": step == 2,
            "inference_status": "ok",
        },
    }


def test_log_parser_and_metrics(tmp_path):
    path = tmp_path / "capture.ndjson"
    decisions = [_decision(1, 23.0, 0.0, 100), _decision(2, 24.0, 1.0, 140)]
    path.write_text(
        "\n".join(json.dumps(record) for record in decisions) + "\nnot-json\n",
        encoding="utf-8",
    )
    records, errors = parse_log(path)
    report = analyse_records(records)
    assert len(errors) == 1
    assert report["decision_steps"] == 2
    assert report["target_errors"]["air_temperature_c"]["mean_absolute_error"] == 1.5
    assert report["safety_modifications"] == 1
    assert report["mean_inference_us"] == 120
    assert report["maximum_inference_us"] == 140


def test_replay_command_parser_accepts_comments_and_rejects_non_objects(tmp_path):
    valid = tmp_path / "valid.jsonl"
    valid.write_text(
        '# scenario\n{"command":"reset"}\n{"command":"step"}\n',
        encoding="utf-8",
    )
    assert load_commands(valid) == [
        {"command": "reset"},
        {"command": "step"},
    ]
    invalid = tmp_path / "invalid.jsonl"
    invalid.write_text("[]\n", encoding="utf-8")
    with pytest.raises(ValueError, match="command must be a JSON object"):
        load_commands(invalid)


def test_replay_correlates_responses_and_captures_unsolicited_json(tmp_path, monkeypatch):
    scenario = tmp_path / "scenario.jsonl"
    scenario.write_text(
        '{"command":"reset"}\n{"command":"status"}\n{"command":"step"}\n',
        encoding="utf-8",
    )
    output = tmp_path / "session.jsonl"
    received = [
        {"type": "startup"},
        {"type": "ack", "command": "pause"},
        {"type": "ack", "command": "reset"},
        {"type": "ack", "command": "status"},
        {"type": "status", "step": 0},
        {"type": "ack", "command": "step"},
        {"type": "decision", "step": 0},
    ]

    class FakeSerial:
        def __init__(self, **kwargs):
            self.writes = []

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def reset_input_buffer(self):
            return None

        def write(self, value):
            self.writes.append(value)

        def flush(self):
            return None

        def readline(self):
            if not received:
                return b""
            return json.dumps(received.pop(0)).encode("utf-8") + b"\n"

    monkeypatch.setattr(replay_module.serial, "Serial", FakeSerial)
    monkeypatch.setattr(replay_module.time, "sleep", lambda _seconds: None)

    assert replay("test-port", scenario, output, settle=0) == 3
    entries = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
    assert [entry["direction"] for entry in entries] == [
        "tx",
        "rx",
        "rx",
        "rx",
        "tx",
        "rx",
        "rx",
        "tx",
        "rx",
        "rx",
    ]
    assert [entry["payload"]["type"] for entry in entries if entry["direction"] == "rx"] == [
        "startup",
        "ack",
        "ack",
        "ack",
        "status",
        "ack",
        "decision",
    ]


def test_replay_fails_on_firmware_error_and_preserves_session(tmp_path, monkeypatch):
    scenario = tmp_path / "scenario.jsonl"
    scenario.write_text('{"command":"seed","value":"bad"}\n', encoding="utf-8")
    output = tmp_path / "session.jsonl"
    received = [
        {"type": "startup"},
        {
            "type": "error",
            "code": "invalid_seed",
            "message": "value must be an unsigned integer",
        },
    ]

    class FakeSerial:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def reset_input_buffer(self):
            return None

        def write(self, _value):
            return None

        def flush(self):
            return None

        def readline(self):
            return json.dumps(received.pop(0)).encode("utf-8") + b"\n"

    monkeypatch.setattr(replay_module.serial, "Serial", FakeSerial)
    monkeypatch.setattr(replay_module.time, "sleep", lambda _seconds: None)

    with pytest.raises(
        ReplayError,
        match="invalid_seed: value must be an unsigned integer",
    ):
        replay("test-port", scenario, output, settle=0)

    entries = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
    assert [entry["direction"] for entry in entries] == ["tx", "rx", "rx"]
    assert entries[-1]["payload"]["code"] == "invalid_seed"


def test_replay_times_out_waiting_for_a_correlated_ack(tmp_path, monkeypatch):
    scenario = tmp_path / "scenario.jsonl"
    scenario.write_text('{"command":"pause"}\n', encoding="utf-8")
    output = tmp_path / "session.jsonl"
    received = [{"type": "ack", "command": "resume"}]
    serial_options = {}

    class FakeSerial:
        def __init__(self, **kwargs):
            serial_options.update(kwargs)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def reset_input_buffer(self):
            return None

        def write(self, _value):
            return None

        def flush(self):
            return None

        def readline(self):
            return json.dumps(received.pop(0)).encode("utf-8") + b"\n"

    ticks = iter((0.0, 0.01, 0.2))
    monkeypatch.setattr(replay_module.serial, "Serial", FakeSerial)
    monkeypatch.setattr(replay_module.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(replay_module.time, "monotonic", lambda: next(ticks))

    with pytest.raises(TimeoutError, match="ack for command 'pause'"):
        replay("test-port", scenario, output, timeout=0.05, settle=0)

    assert serial_options["timeout"] == 0.05
    entries = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
    assert [entry["direction"] for entry in entries] == ["tx", "rx"]


def test_replay_main_reports_errors_and_returns_exit_2(tmp_path, monkeypatch, capsys):
    def fail_replay(*args, **kwargs):
        raise ReplayError("invalid_seed: value must be an unsigned integer")

    monkeypatch.setattr(replay_module, "replay", fail_replay)

    result = replay_module.main(
        [
            "--port",
            "test-port",
            "--scenario",
            str(tmp_path / "scenario.jsonl"),
            "--output",
            str(tmp_path / "session.jsonl"),
        ]
    )

    assert result == 2
    assert capsys.readouterr().err == (
        "replay failed: invalid_seed: value must be an unsigned integer\n"
    )
