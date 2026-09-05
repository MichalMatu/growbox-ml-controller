#!/usr/bin/env bash
set -euo pipefail

EXPECTED_BRANCH_HEAD=7f8ed8588408fccdfcd2ed8b3531f40f530bb02f
EXPECTED_FIRMWARE=af16aebde8f69d1a1257256c7711e9721c07c9d5
BRANCH=mvp/environment-controller

git fetch -q origin "$BRANCH"
git reset --hard "$EXPECTED_BRANCH_HEAD"
test "$(git rev-parse HEAD)" = "$EXPECTED_BRANCH_HEAD"
test "$(git rev-parse origin/$BRANCH)" = "$EXPECTED_BRANCH_HEAD"
test -z "$(git status --porcelain)"

PY="$(git rev-parse --show-toplevel)/.venv/bin/python"
if [[ ! -x "$PY" ]]; then
  PY="$(command -v python3)"
fi

"$PY" - "$EXPECTED_FIRMWARE" <<'PY'
import sys
import time
from pathlib import Path

import serial
from tools.stage27c_soak import detect_ch340_port

expected_firmware = sys.argv[1]
port = detect_ch340_port()
if not port:
    raise SystemExit("CrowPanel CH340 serial port was not detected")
print("MANUAL_RF_LAMP_REPEAT_V2_PORT", port)

all_chunks = []

def collect(handle, duration):
    deadline = time.monotonic() + duration
    chunks = []
    while time.monotonic() < deadline:
        data = handle.read(4096)
        if data:
            chunks.append(data)
            all_chunks.append(data)
    return b"".join(chunks).decode("utf-8", errors="replace")

def command(handle, text, duration=1.2):
    handle.write(text.encode("ascii") + b"\n")
    handle.flush()
    return collect(handle, duration)

def require_tx(text, device, state, code):
    token = f"manual_rf_tx device={device} state={state} code={code}"
    if token not in text:
        raise RuntimeError(f"{device} {state} transmit evidence missing")
    if "tx_queued=1 tx_started=1 tx_completed=1" not in text:
        raise RuntimeError(f"{device} {state} transmit did not complete locally")

with serial.Serial(port, 115200, timeout=0.12, write_timeout=1.0) as handle:
    try:
        handle.dtr = False
        handle.rts = False
    except Exception:
        pass

    time.sleep(2.0)
    handle.reset_input_buffer()

    status_ok = False
    status_text = ""
    for _ in range(8):
        status_text += command(handle, "status", 1.0)
        if (
            f"status firmware_sha={expected_firmware}" in status_text
            and "outputs=fake-locked" in status_text
            and "rf_ready=1" in status_text
        ):
            status_ok = True
            break
        time.sleep(0.35)

    if not status_ok:
        raise SystemExit("firmware identity/safe runtime check failed before repeated lamp actuation")

    actuation_started = False
    try:
        for cycle in range(1, 4):
            lamp_on = command(handle, "rf lamp on", 1.6)
            require_tx(lamp_on, "lamp", "on", 235030016)
            actuation_started = True
            print(f"LAMP_CYCLE_{cycle}_ON_LOCAL_PASS")
            time.sleep(2.0)

            lamp_off = command(handle, "rf lamp off", 1.6)
            require_tx(lamp_off, "lamp", "off", 16926208)
            print(f"LAMP_CYCLE_{cycle}_OFF_LOCAL_PASS")
            time.sleep(2.0)

        status_after = command(handle, "status", 1.5)
        if "outputs=fake-locked" not in status_after or "rf_ready=1" not in status_after:
            raise RuntimeError("safe runtime/RF postcondition failed after repeated lamp actuation")
    except Exception:
        if actuation_started:
            try:
                command(handle, "rf lamp off", 1.6)
            except Exception:
                pass
        raise

text = b"".join(all_chunks).decode("utf-8", errors="replace")
Path("/tmp/stage28d_manual_rf_lamp_repeat_v2.log").write_text(text)
print(text[-12000:])

for forbidden in ["Guru Meditation", "abort() was called"]:
    if forbidden in text:
        raise SystemExit(f"forbidden runtime failure observed: {forbidden}")

print(
    "STAGE28D_MANUAL_RF_LAMP_REPEAT_V2_LOCAL_PASS "
    f"sha={expected_firmware} console_port={port} cycles=3 on_tx=3 off_tx=3 "
    "final_command=off runtime_outputs=fake-locked physical_observation_required=1"
)
PY

test -z "$(git status --porcelain)"
