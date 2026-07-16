#!/usr/bin/env python3
"""Live panel + board diagnostic script (run while make panel is up)."""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from typing import Any

from tools.ml.scenario_payload import default_scenario

DEFAULT_BASE = "http://127.0.0.1:8765"
DEFAULT_PORT = "/dev/cu.usbmodem1101"


def http_json(
    base: str,
    method: str,
    path: str,
    body: dict[str, Any] | None = None,
    *,
    timeout: float = 15.0,
) -> tuple[int, Any]:
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        f"{base.rstrip('/')}{path}",
        data=data,
        method=method,
    )
    if data is not None:
        request.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.status, json.loads(response.read().decode("utf-8"))


def badge_payload(doc: dict[str, Any]) -> dict[str, Any]:
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


def stable_stringify(value: Any) -> str:
    if isinstance(value, list):
        return "[" + ",".join(stable_stringify(item) for item in value) + "]"
    if isinstance(value, dict):
        keys = sorted(value.keys())
        return (
            "{"
            + ",".join(f"{json.dumps(key)}:{stable_stringify(value[key])}" for key in keys)
            + "}"
        )
    return json.dumps(value)


def badge_fingerprint(doc: dict[str, Any]) -> str:
    return stable_stringify(badge_payload(doc))


def run_diag(base: str, port: str) -> int:
    issues: list[str] = []
    timings: list[tuple[str, float]] = []

    def step(label: str, fn) -> Any:
        started = time.monotonic()
        result = fn()
        timings.append((label, time.monotonic() - started))
        return result

    print(f"Panel: {base}")
    print(f"Port:  {port}")

    try:
        _, schema = step("GET /api/schema", lambda: http_json(base, "GET", "/api/schema"))
    except (urllib.error.URLError, TimeoutError) as exc:
        print(f"FAIL: panel unreachable: {exc}")
        return 1

    contract_hash = schema.get("schema_hash")
    print(f"Contract: v{schema.get('schema_version')} hash={contract_hash}")

    step("POST /api/disconnect", lambda: http_json(base, "POST", "/api/disconnect", {}))
    time.sleep(0.2)

    try:
        _, connected = step(
            "POST /api/connect",
            lambda: http_json(base, "POST", "/api/connect", {"port": port, "baud": 115200}),
        )
    except urllib.error.HTTPError as exc:
        body = json.loads(exc.read().decode("utf-8"))
        print(f"FAIL: connect {exc.code}: {body.get('error')}")
        return 1

    if not connected.get("connected"):
        issues.append("connect returned connected=false")
    fw_err = connected.get("last_firmware_error")
    if fw_err:
        issues.append(f"firmware error on connect: {fw_err}")

    startup = connected.get("last_startup")
    status = connected.get("last_status") or {}
    device_hash = (startup or {}).get("schema_hash") or status.get("schema_hash")
    if device_hash and contract_hash and device_hash != contract_hash:
        issues.append(f"schema hash mismatch panel={contract_hash} device={device_hash}")
    print(
        f"Device hash: {device_hash or '—'} mode={status.get('mode')} paused={status.get('paused')}"
    )

    scenario = default_scenario(seed=101)
    sent_fp = badge_fingerprint(scenario)
    seed = scenario.pop("seed")
    step(
        "POST /api/load_scenario",
        lambda: http_json(
            base,
            "POST",
            "/api/load_scenario",
            {"seed": seed, "scenario": scenario},
        ),
    )

    _, after_load = http_json(base, "GET", "/api/state")
    if after_load.get("last_firmware_error"):
        issues.append(f"load_scenario error: {after_load['last_firmware_error']}")
    snap = (after_load.get("last_status") or {}).get("scenario")
    if not isinstance(snap, dict):
        issues.append("missing scenario snapshot in last_status after load")
    else:
        merged = dict(scenario)
        merged["seed"] = seed
        merged.update(snap)
        device_fp = badge_fingerprint(merged)
        if device_fp != sent_fp:
            issues.append("badge fingerprint mismatch after Wyślij (bridge snapshot vs form)")

    step(
        "POST mode=closed_loop",
        lambda: http_json(
            base, "POST", "/api/command", {"command": "mode", "value": "closed_loop"}
        ),
    )
    step("POST resume", lambda: http_json(base, "POST", "/api/command", {"command": "resume"}))

    decision = None
    deadline = time.monotonic() + 8.0
    while time.monotonic() < deadline:
        time.sleep(0.4)
        _, state = http_json(base, "GET", "/api/state")
        if state.get("last_firmware_error"):
            issues.append(f"runtime firmware error: {state['last_firmware_error']}")
        candidate = state.get("last_decision")
        if isinstance(candidate, dict) and (candidate.get("step") or 0) >= 1:
            decision = candidate
            status_step = (state.get("last_status") or {}).get("step")
            if status_step != candidate.get("step"):
                issues.append(f"step desync status={status_step} decision={candidate.get('step')}")
            break

    if decision is None:
        issues.append("no decision within 8s after resume in closed_loop")
    else:
        diag = decision.get("diagnostics", {})
        inf = diag.get("inference_status")
        print(f"Decision step={decision.get('step')} inference={inf}")
        if inf != "ok":
            issues.append(f"inference_status={inf}")
        safe = decision.get("safe_output", {})
        active = {
            name: round(float(value), 3)
            for name, value in safe.items()
            if name in schema["outputs"] and float(value) > 0.01
        }
        print(f"Active outputs: {active or '(all near zero)'}")

        mutated = json.loads(json.dumps(scenario))
        mutated["seed"] = seed
        mutated["previous"] = dict(mutated.get("previous") or {})
        mutated["previous"]["fan"] = float(safe.get("fan", 0))
        if badge_fingerprint(mutated) == sent_fp:
            print("OK: previous mutation does not affect badge fingerprint")
        else:
            issues.append("badge fingerprint changed after previous-only mutation")

    print("\nTimings:")
    for label, elapsed in timings:
        print(f"  {label}: {elapsed:.2f}s")

    if issues:
        print("\nISSUES:")
        for item in issues:
            print(f"  - {item}")
        return 1

    print("\nALL CHECKS PASSED")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default=DEFAULT_BASE)
    parser.add_argument("--port", default=DEFAULT_PORT)
    args = parser.parse_args(argv)
    return run_diag(args.base, args.port)


if __name__ == "__main__":
    raise SystemExit(main())
