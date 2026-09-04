#!/usr/bin/env bash
set -euo pipefail

EXPECTED=c8141d8b4a0c0d4bce5d330c2e65225ce93f4220
BRANCH=mvp/environment-controller

git fetch -q origin "$BRANCH"
git reset --hard "$EXPECTED"
test "$(git rev-parse HEAD)" = "$EXPECTED"
test "$(git rev-parse origin/$BRANCH)" = "$EXPECTED"
test -z "$(git status --porcelain)"

export GROWBOX_FIRMWARE_GIT_SHA="$EXPECTED"
export GROWBOX_RF433_LOOPBACK_ENABLED=1
export GROWBOX_RF433_LOOPBACK_AUTO_SMOKE=0
export GROWBOX_RF433_REMOTE_CAPTURE_ENABLED=0
export GROWBOX_STAGE28_SERVICE_CONSOLE_ENABLED=1
export STAGE27C_BUILD_DIR=build/idf-stage28d-service-console-hw-smoke-v2
export CMAKE_BUILD_PARALLEL_LEVEL=2

bash scripts/stage27c_crowpanel.sh flash

PY="$(git rev-parse --show-toplevel)/.venv/bin/python"
if [[ ! -x "$PY" ]]; then
  PY="$(command -v python3)"
fi

"$PY" - "$EXPECTED" <<'PY'
import sys
import time
from pathlib import Path

import serial
from tools.stage27c_soak import detect_ch340_port

expected = sys.argv[1]
port = detect_ch340_port()
if not port:
    raise SystemExit("CrowPanel CH340 serial port was not detected")
print("SERVICE_CONSOLE_PRIMARY_PORT", port)

chunks = []
with serial.Serial(port, 115200, timeout=0.12, write_timeout=1.0) as handle:
    try:
        handle.dtr = False
        handle.rts = False
    except Exception:
        pass
    time.sleep(1.5)
    handle.reset_input_buffer()
    for command in [b"\n", b"help\n", b"status\n", b"sensors\n", b"rf list\n"]:
        handle.write(command)
        handle.flush()
        deadline = time.monotonic() + 1.5
        while time.monotonic() < deadline:
            data = handle.read(4096)
            if data:
                chunks.append(data)
    deadline = time.monotonic() + 1.5
    while time.monotonic() < deadline:
        data = handle.read(4096)
        if data:
            chunks.append(data)

text = b"".join(chunks).decode("utf-8", errors="replace")
Path("/tmp/stage28d_service_console_hw_smoke_v2.log").write_text(text)
print(text[-16000:])

required = [
    "Commands:",
    f"status firmware_sha={expected}",
    "outputs=fake-locked",
    "rf_ready=1",
    "sensors:",
    "scd41",
    "tp357",
    "xiaomi",
    "rtc",
    "rf transport_ready=1",
    "lamp label=remote_socket_2",
    "fan label=remote_socket_1",
    "humidifier label=remote_socket_3",
]
missing = [token for token in required if token not in text]
if missing:
    raise SystemExit("service console response missing: " + ", ".join(missing))

for forbidden in ["manual_rf_tx", "Guru Meditation", "abort() was called"]:
    if forbidden in text:
        raise SystemExit(f"forbidden smoke-test evidence observed: {forbidden}")

print(
    "STAGE28D_SERVICE_CONSOLE_HW_SMOKE_PASS "
    f"sha={expected} console_port={port} menu=pass status=pass sensors=pass "
    "rf_list=pass rf_ready=1 manual_rf_tx=0 runtime_outputs=fake-locked"
)
PY

test -z "$(git status --porcelain)"
