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
print("MANUAL_RF_HUMIDIFIER_PORT", port)

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

def status_ready(handle):
    for _ in range(4):
        text = command(handle, "status", 1.8)
        if (
            f"status firmware_sha={expected_firmware}" in text
            and "outputs=fake-locked" in text
            and "rf_ready=1" in text
        ):
            return True
        command(handle, "", 0.3)
    return False

def transmit_with_evidence(handle, command_text, evidence, attempts=3):
    combined = ""
    for _ in range(attempts):
        combined += command(handle, command_text, 2.0)
        if evidence in combined and "tx_queued=1 tx_started=1 tx_completed=1" in combined:
            return combined
    raise RuntimeError(f"transmit evidence missing for {command_text}")

with serial.Serial(port, 115200, timeout=0.12, write_timeout=1.0) as handle:
    try:
        handle.dtr = False
        handle.rts = False
    except Exception:
        pass
    time.sleep(1.0)
    handle.reset_input_buffer()
    command(handle, "", 0.5)

    if not status_ready(handle):
        raise SystemExit("firmware/safety identity check failed before humidifier actuation")

    on_attempted = False
    try:
        on_attempted = True
        transmit_with_evidence(
            handle,
            "rf humidifier on",
            "manual_rf_tx device=humidifier state=on code=637683200",
        )
        print("HUMIDIFIER_ON_LOCAL_PASS")
        time.sleep(4.0)
        transmit_with_evidence(
            handle,
            "rf humidifier off",
            "manual_rf_tx device=humidifier state=off code=771900928",
        )
        print("HUMIDIFIER_OFF_LOCAL_PASS")
    except Exception:
        if on_attempted:
            try:
                for _ in range(3):
                    text = command(handle, "rf humidifier off", 1.5)
                    if "manual_rf_tx device=humidifier state=off code=771900928" in text:
                        break
            except Exception:
                pass
        raise

    if not status_ready(handle):
        raise SystemExit("safe runtime/RF status check failed after humidifier actuation")

text = b"".join(all_chunks).decode("utf-8", errors="replace")
Path("/tmp/stage28d_manual_rf_humidifier_v1.log").write_text(text)
print(text[-12000:])

for forbidden in ["Guru Meditation", "abort() was called"]:
    if forbidden in text:
        raise SystemExit(f"forbidden runtime failure observed: {forbidden}")

print(
    "STAGE28D_MANUAL_RF_HUMIDIFIER_V1_LOCAL_PASS "
    f"sha={expected_firmware} console_port={port} on_tx=pass off_tx=pass "
    "final_command=off runtime_outputs=fake-locked physical_observation_required=1"
)
PY

test -z "$(git status --porcelain)"
