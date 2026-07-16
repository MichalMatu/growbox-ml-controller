"""Live hardware + panel API integration tests (requires ESP32 on usbmodem)."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import pytest

from tools.panel.bridge import SerialBridge
from tools.panel.form_schema import build_panel_schema, default_scenario
from tools.serial.board_scenario import nominal_replay_commands
from tools.serial.replay import ReplayError, replay

BOARD_PORT_ENV = "GROWBOX_BOARD_PORT"
DEFAULT_BOARD_PORT = "/dev/cu.usbmodem1101"
PANEL_BASE_ENV = "GROWBOX_PANEL_BASE"
DEFAULT_PANEL_BASE = "http://127.0.0.1:8765"


def _resolve_board_port() -> str | None:
    explicit = os.environ.get(BOARD_PORT_ENV, "").strip()
    if explicit:
        return explicit if Path(explicit).exists() else None
    if Path(DEFAULT_BOARD_PORT).exists():
        return DEFAULT_BOARD_PORT
    return None


def _panel_base() -> str:
    return os.environ.get(PANEL_BASE_ENV, DEFAULT_PANEL_BASE).rstrip("/")


def _http_json(
    method: str,
    path: str,
    body: dict[str, Any] | None = None,
    *,
    timeout: float = 15.0,
) -> tuple[int, Any]:
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        f"{_panel_base()}{path}",
        data=data,
        method=method,
    )
    if data is not None:
        request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
            return response.status, payload
    except urllib.error.HTTPError as exc:
        payload = json.loads(exc.read().decode("utf-8"))
        return exc.code, payload


@pytest.fixture(scope="module")
def board_port() -> str:
    port = _resolve_board_port()
    if port is None:
        pytest.skip(f"no board serial port (set {BOARD_PORT_ENV})")
    return port


@pytest.fixture(scope="module")
def panel_available() -> str:
    try:
        status, payload = _http_json("GET", "/api/schema")
    except (urllib.error.URLError, TimeoutError) as exc:
        pytest.skip(f"panel not running at {_panel_base()}: {exc}")
    if status != 200:
        pytest.skip(f"panel schema returned {status}")
    assert payload["schema_hash"] == "457ddca8b0e5"
    return _panel_base()


def _badge_payload_python(doc: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "sensors",
        "validity",
        "pots",
        "pseudo",
        "environment",
        "actuators",
        "targets",
        "safety",
    )
    payload: dict[str, Any] = {"seed": doc.get("seed", 101)}
    for key in keys:
        if key in doc:
            payload[key] = json.loads(json.dumps(doc[key]))
    pots = payload.get("pots")
    if isinstance(pots, list):
        payload["pots"] = [
            {k: v for k, v in pot.items() if k != "previous"} if isinstance(pot, dict) else pot
            for pot in pots
        ]
    return payload


def _stable_stringify(value: Any) -> str:
    if isinstance(value, list):
        return "[" + ",".join(_stable_stringify(item) for item in value) + "]"
    if isinstance(value, dict):
        keys = sorted(value.keys())
        return (
            "{"
            + ",".join(f"{json.dumps(key)}:{_stable_stringify(value[key])}" for key in keys)
            + "}"
        )
    return json.dumps(value)


def _badge_fingerprint(doc: dict[str, Any]) -> str:
    return _stable_stringify(_badge_payload_python(doc))


@pytest.mark.hardware
def test_panel_schema_endpoint(panel_available: str):
    status, schema = _http_json("GET", "/api/schema")
    assert status == 200
    assert schema["schema_version"] == 4
    assert len(schema["outputs"]) == 15
    assert "default_scenario" in schema


@pytest.mark.hardware
def test_panel_ports_lists_board(board_port: str, panel_available: str):
    status, payload = _http_json("GET", "/api/ports")
    assert status == 200
    devices = [entry["device"] for entry in payload["ports"]]
    assert board_port in devices


@pytest.mark.hardware
def test_panel_connect_load_resume_loop_produces_decisions(board_port: str, panel_available: str):
    _http_json("POST", "/api/disconnect", {})
    time.sleep(0.2)

    status, connected = _http_json("POST", "/api/connect", {"port": board_port, "baud": 115200})
    assert status == 200, connected
    assert connected["connected"] is True
    assert connected.get("last_firmware_error") is None

    scenario = default_scenario(seed=101)
    seed = scenario.pop("seed")
    status, load_ok = _http_json(
        "POST",
        "/api/load_scenario",
        {"seed": seed, "scenario": scenario},
    )
    assert status == 200, load_ok
    assert load_ok == {"ok": True}

    status, _ = _http_json("POST", "/api/command", {"command": "mode", "value": "closed_loop"})
    assert status == 200
    status, _ = _http_json("POST", "/api/command", {"command": "resume"})
    assert status == 200

    decision = None
    deadline = time.monotonic() + 8.0
    while time.monotonic() < deadline:
        time.sleep(0.35)
        status, state = _http_json("GET", "/api/state")
        assert status == 200
        assert state["connected"] is True
        assert state.get("last_firmware_error") is None
        candidate = state.get("last_decision")
        if isinstance(candidate, dict) and candidate.get("type") == "decision":
            decision = candidate
            if (candidate.get("step") or 0) >= 1:
                break

    assert decision is not None, "expected decision frame after resume in closed_loop"
    assert decision.get("schema_hash") == "457ddca8b0e5"
    diagnostics = decision.get("diagnostics", {})
    assert diagnostics.get("inference_status") == "ok"
    safe = decision.get("safe_output", {})
    assert isinstance(safe, dict)
    schema = build_panel_schema()
    for name in schema["outputs"]:
        assert name in safe, f"missing actuator output {name}"
        assert 0.0 <= float(safe[name]) <= 1.0, name
    pulse = safe.get("irrigation_pulse_s")
    assert isinstance(pulse, list)
    assert len(pulse) == 4

    status_step = None
    decision_step = None
    deadline = time.monotonic() + 3.0
    while time.monotonic() < deadline:
        _, state = _http_json("GET", "/api/state")
        status_step = (state.get("last_status") or {}).get("step")
        decision_step = (state.get("last_decision") or {}).get("step")
        if decision_step is not None and status_step == decision_step:
            break
        time.sleep(0.2)
    assert decision_step is not None
    assert status_step == decision_step, "bridge should mirror decision step into last_status"


@pytest.mark.hardware
def test_panel_replay_resume_without_loop_does_not_auto_step(board_port: str, panel_available: str):
    _http_json("POST", "/api/disconnect", {})
    time.sleep(0.2)
    _http_json("POST", "/api/connect", {"port": board_port, "baud": 115200})

    scenario = default_scenario(seed=101)
    seed = scenario.pop("seed")
    _http_json("POST", "/api/load_scenario", {"seed": seed, "scenario": scenario})
    _http_json("POST", "/api/command", {"command": "mode", "value": "replay"})
    _http_json("POST", "/api/command", {"command": "resume"})

    time.sleep(2.5)
    status, state = _http_json("GET", "/api/state")
    assert status == 200
    st = state.get("last_status") or {}
    assert st.get("mode") == "replay"
    assert st.get("paused") is False
    assert (state.get("last_decision") or {}).get("step") in {None, 0}


@pytest.mark.hardware
def test_panel_step_in_replay_advances(board_port: str, panel_available: str):
    _http_json("POST", "/api/disconnect", {})
    time.sleep(0.2)
    _http_json("POST", "/api/connect", {"port": board_port, "baud": 115200})

    scenario = default_scenario(seed=101)
    seed = scenario.pop("seed")
    _http_json("POST", "/api/load_scenario", {"seed": seed, "scenario": scenario})
    _http_json("POST", "/api/command", {"command": "mode", "value": "replay"})
    _http_json("POST", "/api/command", {"command": "resume"})
    status, _ = _http_json("POST", "/api/step", {})
    assert status == 200

    deadline = time.monotonic() + 5.0
    decision = None
    while time.monotonic() < deadline:
        time.sleep(0.25)
        _, state = _http_json("GET", "/api/state")
        candidate = state.get("last_decision")
        if isinstance(candidate, dict) and candidate.get("type") == "decision":
            decision = candidate
            break
    assert decision is not None
    assert decision.get("diagnostics", {}).get("inference_status") == "ok"


@pytest.mark.hardware
def test_load_scenario_status_snapshot_matches_badge_contract(
    board_port: str, panel_available: str
):
    _http_json("POST", "/api/disconnect", {})
    time.sleep(0.2)
    _http_json("POST", "/api/connect", {"port": board_port, "baud": 115200})

    scenario = default_scenario(seed=303, preset="nominal")
    sent_fp = _badge_fingerprint(scenario)
    seed = scenario.pop("seed")
    _http_json("POST", "/api/load_scenario", {"seed": seed, "scenario": scenario})

    _, state = _http_json("GET", "/api/state")
    snap = (state.get("last_status") or {}).get("scenario")
    assert isinstance(snap, dict)
    merged = dict(scenario)
    merged["seed"] = seed
    for key, value in snap.items():
        merged[key] = value
    device_fp = _badge_fingerprint(merged)
    assert device_fp == sent_fp


@pytest.mark.hardware
def test_direct_serial_replay_when_panel_disconnected(board_port: str, panel_available: str):
    _http_json("POST", "/api/disconnect", {})
    time.sleep(1.2)

    tmp = Path(os.environ.get("PYTEST_TMPDIR", "/tmp")) / "panel-hw-replay.jsonl"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        json.dumps(command, separators=(",", ":")) for command in nominal_replay_commands(seed=101)
    ]
    tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    out = tmp.with_suffix(".ndjson")

    try:
        responses = replay(board_port, tmp, out, timeout=8.0, settle=0.2)
    except ReplayError as exc:
        pytest.fail(f"direct serial replay failed: {exc}")

    assert responses >= 2
    decisions = []
    for line in out.read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        if record.get("direction") != "rx":
            continue
        payload = record.get("payload")
        if isinstance(payload, dict) and payload.get("type") == "decision":
            decisions.append(payload)
    assert decisions
    assert decisions[0].get("diagnostics", {}).get("inference_status") == "ok"


@pytest.mark.hardware
def test_bridge_handshake_classifies_real_port(board_port: str):
    bridge = SerialBridge()
    ports = bridge.list_ports()
    match = next((entry for entry in ports if entry["device"] == board_port), None)
    assert match is not None
    assert match["recommended"] is True
    assert bridge.classify_port(board_port, match.get("description", "")) == "likely_esp"
