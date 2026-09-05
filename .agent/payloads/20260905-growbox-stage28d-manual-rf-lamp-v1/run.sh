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
print("MANUAL_RF_LAMP_PORT", port)

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

def command(handle, text, duration=1.8):
    handle.write(text.encode("ascii") + b"\n")
    handle.flush()
    return collect(handle, duration)

with serial.Serial(port, 115200, timeout=0.12, write_timeout=1.0) as handle:
    try:
        handle.dtr = False
        handle.rts = False
    except Exception:
        pass
    time.sleep(1.0)
    handle.reset_input_buffer()

    command(handle, "", 0.5)
    status_before = command(handle, "status", 1.8)
    if f"status firmware_sha={expected_firmware}" not in status_before:
        raise SystemExit("firmware identity check failed before lamp actuation")
    if "outputs=fake-locked" not in status_before or "rf_ready=1" not in status_before:
        raise SystemExit("safe runtime/RF precondition failed before lamp actuation")

    lamp_on = command(handle, "rf lamp on", 2.0)
    if "manual_rf_tx device=lamp state=on code=235030016" not in lamp_on:
        raise SystemExit("lamp ON transmit evidence missing")
    if "tx_queued=1 tx_started=1 tx_completed=1" not in lamp_on:
        raise SystemExit("lamp ON transmit did not complete locally")

    # Leave the lamp commanded ON long enough for the present operator to observe it.
    time.sleep(4.0)

    lamp_off = command(handle, "rf lamp off", 2.0)
    if "manual_rf_tx device=lamp state=off code=16926208" not in lamp_off:
        raise SystemExit("lamp OFF transmit evidence missing")
    if "tx_queued=1 tx_started=1 tx_completed=1" not in lamp_off:
        raise SystemExit("lamp OFF transmit did not complete locally")

    status_after = command(handle, "status", 1.5)
    if "outputs=fake-locked" not in status_after:
        raise SystemExit("runtime outputs are not fake-locked after lamp validation")

text = b"".join(all_chunks).decode("utf-8", errors="replace")
Path("/tmp/stage28d_manual_rf_lamp_v1.log").write_text(text)
print(text[-12000:])

for forbidden in ["Guru Meditation", "abort() was called"]:
    if forbidden in text:
        raise SystemExit(f"forbidden runtime failure observed: {forbidden}")

print(
    "STAGE28D_MANUAL_RF_LAMP_LOCAL_PASS "
    f"sha={expected_firmware} console_port={port} on_tx=pass off_tx=pass "
    "final_command=off runtime_outputs=fake-locked physical_observation_required=1"
)
PY

test -z "$(git status --porcelain)"
