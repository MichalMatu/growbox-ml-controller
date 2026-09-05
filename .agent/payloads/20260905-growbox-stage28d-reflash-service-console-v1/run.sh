#!/usr/bin/env bash
set -euo pipefail

FIRMWARE=af16aebde8f69d1a1257256c7711e9721c07c9d5
CURRENT=7f8ed8588408fccdfcd2ed8b3531f40f530bb02f
BRANCH=mvp/environment-controller

git fetch -q origin "$BRANCH"
test "$(git rev-parse origin/$BRANCH)" = "$CURRENT"
git reset --hard "$FIRMWARE"
test "$(git rev-parse HEAD)" = "$FIRMWARE"
test -z "$(git status --porcelain)"

export GROWBOX_FIRMWARE_GIT_SHA="$FIRMWARE"
export GROWBOX_RF433_LOOPBACK_ENABLED=1
export GROWBOX_RF433_LOOPBACK_AUTO_SMOKE=0
export GROWBOX_RF433_REMOTE_CAPTURE_ENABLED=0
export GROWBOX_STAGE28_SERVICE_CONSOLE_ENABLED=1
export STAGE27C_BUILD_DIR=build/idf-stage28d-service-console-reflash-v1
export CMAKE_BUILD_PARALLEL_LEVEL=2

bash scripts/stage27c_crowpanel.sh flash

PY="$(git rev-parse --show-toplevel)/.venv/bin/python"
if [[ ! -x "$PY" ]]; then
  PY="$(command -v python3)"
fi

"$PY" - "$FIRMWARE" <<'PY'
import sys
import time

import serial
from tools.stage27c_soak import detect_ch340_port

expected = sys.argv[1]
port = detect_ch340_port()
if not port:
    raise SystemExit("CrowPanel CH340 serial port was not detected")
print("REFLASH_SERVICE_CONSOLE_PORT", port)

chunks = []
with serial.Serial(port, 115200, timeout=0.12, write_timeout=1.0) as handle:
    try:
        handle.dtr = False
        handle.rts = False
    except Exception:
        pass
    time.sleep(1.5)
    handle.reset_input_buffer()
    handle.write(b"status\n")
    handle.flush()
    deadline = time.monotonic() + 3.0
    while time.monotonic() < deadline:
        data = handle.read(4096)
        if data:
            chunks.append(data)

text = b"".join(chunks).decode("utf-8", errors="replace")
print(text[-12000:])
required = [
    f"status firmware_sha={expected}",
    "outputs=fake-locked",
    "rf_ready=1",
]
missing = [token for token in required if token not in text]
if missing:
    raise SystemExit("reflash verification missing: " + ", ".join(missing))
for forbidden in ["manual_rf_tx", "Guru Meditation", "abort() was called"]:
    if forbidden in text:
        raise SystemExit(f"forbidden reflash evidence observed: {forbidden}")
print(
    "STAGE28D_SERVICE_CONSOLE_REFLASH_PASS "
    f"sha={expected} console_port={port} status=pass rf_ready=1 manual_rf_tx=0 runtime_outputs=fake-locked"
)
PY

git reset --hard "$CURRENT"
test "$(git rev-parse HEAD)" = "$CURRENT"
test -z "$(git status --porcelain)"
