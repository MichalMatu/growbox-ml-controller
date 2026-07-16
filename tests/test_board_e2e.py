"""On-device serial E2E against flashed v3 firmware."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest

from tools.serial.board_scenario import nominal_replay_commands, write_replay_script
from tools.serial.replay import ReplayError, replay

BOARD_PORT_ENV = "GROWBOX_BOARD_PORT"
DEFAULT_BOARD_PORT = "/dev/cu.usbmodem1101"
EXAMPLES_DIR = Path(__file__).resolve().parents[1] / "examples" / "scenarios"


def _resolve_board_port() -> str | None:
    explicit = os.environ.get(BOARD_PORT_ENV, "").strip()
    if explicit:
        return explicit if Path(explicit).exists() else None
    if Path(DEFAULT_BOARD_PORT).exists():
        return DEFAULT_BOARD_PORT
    return None


@pytest.fixture(scope="module")
def board_port() -> str:
    port = _resolve_board_port()
    if port is None:
        pytest.skip(f"no board serial port (set {BOARD_PORT_ENV})")
    return port


def test_v3_replay_script_fits_serial_limit(tmp_path: Path):
    scenario_path = tmp_path / "v3-nominal.jsonl"
    write_replay_script(scenario_path, seed=101)
    for line_number, line in enumerate(scenario_path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        assert len(line.encode("utf-8")) <= 8192, f"line {line_number} exceeds serial limit"


def test_examples_v3_nominal_script_matches_panel_preset():
    example_path = EXAMPLES_DIR / "v3-nominal.jsonl"
    assert example_path.exists()
    commands = [
        json.loads(line)
        for line in example_path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    assert commands == nominal_replay_commands(seed=101)


@pytest.mark.hardware
def test_board_replay_produces_v3_decision(board_port: str, tmp_path: Path):
    if shutil.which("python3") is None:
        pytest.skip("python3 not available")
    scenario_path = tmp_path / "v3-board.jsonl"
    output_path = tmp_path / "session.ndjson"
    write_replay_script(scenario_path, seed=101)

    try:
        responses = replay(board_port, scenario_path, output_path, timeout=8.0, settle=0.2)
    except ReplayError as exc:
        pytest.fail(f"board replay failed: {exc}")

    assert responses >= 2

    decisions: list[dict] = []
    for line in output_path.read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        if record.get("direction") != "rx":
            continue
        payload = record.get("payload")
        if isinstance(payload, dict) and payload.get("type") == "decision":
            decisions.append(payload)

    assert decisions, "expected at least one decision frame from firmware"
    decision = decisions[0]
    assert decision.get("schema_version") == 3
    assert decision.get("schema_hash") == "c91e249af9d3"
    diagnostics = decision.get("diagnostics", {})
    assert diagnostics.get("inference_status") == "ok"
    assert diagnostics.get("inference_status") != "schema_mismatch"

    safe_output = decision.get("safe_output", {})
    for output_name in (
        "heater",
        "fan",
        "humidifier",
        "dehumidifier",
        "cooler",
        "co2_doser",
        "irrigation_zone_1",
        "irrigation_zone_2",
        "irrigation_zone_3",
        "irrigation_zone_4",
        "nutrient_heater",
        "heat_mat_zone_1",
        "heat_mat_zone_2",
        "heat_mat_zone_3",
        "heat_mat_zone_4",
    ):
        assert output_name in safe_output
        value = float(safe_output[output_name])
        assert 0.0 <= value <= 1.0
