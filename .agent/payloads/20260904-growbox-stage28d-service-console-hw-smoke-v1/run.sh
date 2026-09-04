#!/usr/bin/env bash
set -euo pipefail

EXPECTED=fd4c16c7f3ae454d50d1ce3bd7bc6b9daddf1f3e
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
export STAGE27C_BUILD_DIR=build/idf-stage28d-service-console-hw-smoke
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
from serial.tools import list_ports

expected = sys.argv[1]

try:
    from tools.stage27c_soak import detect_ch340_port
    detected = detect_ch340_port()
except Exception:
    detected = ""

ports = []
if detected:
    ports.append(detected)
for item in list_ports.comports():
    device = item.device
    if device and device not in ports:
        ports.append(device)

# Prefer USB serial-looking endpoints and the known CrowPanel CH340 port, but keep
# every enumerated serial endpoint as a bounded fallback so native USB Serial/JTAG
# can be discovered if it is separate from the CH340 bridge.
preferred = []
for device in ports:
    lower = device.lower()
    if device == detected or "usb" in lower or "modem" in lower or "wch" in lower:
        preferred.append(device)
for device in ports:
    if device not in preferred:
        preferred.append(device)

print("SERVICE_CONSOLE_PORT_CANDIDATES", preferred)
if not preferred:
    raise SystemExit("no serial ports available after flash")

commands = [b"\n", b"help\n", b"status\n", b"sensors\n", b"rf list\n"]
results = {}

for device in preferred:
    chunks = []
    try:
        with serial.Serial(device, 115200, timeout=0.15, write_timeout=1.0) as handle:
            # Do not intentionally request bootloader/reset control-line states.
            try:
                handle.dtr = False
                handle.rts = False
            except Exception:
                pass
            time.sleep(1.2)
            handle.reset_input_buffer()
            for command in commands:
                handle.write(command)
                handle.flush()
                deadline = time.monotonic() + 1.2
                while time.monotonic() < deadline:
                    data = handle.read(4096)
                    if data:
                        chunks.append(data)
            deadline = time.monotonic() + 2.0
            while time.monotonic() < deadline:
                data = handle.read(4096)
                if data:
                    chunks.append(data)
    except Exception as exc:
        results[device] = f"OPEN_ERROR {exc}"
        continue

    text = b"".join(chunks).decode("utf-8", errors="replace")
    results[device] = text
    safe_name = device.replace("/", "_").replace("\\", "_")
    Path(f"/tmp/stage28d_console_{safe_name}.log").write_text(text)
    print(f"--- SERIAL {device} ---")
    print(text[-12000:])

console_port = None
console_text = ""
for device, text in results.items():
    if not isinstance(text, str) or text.startswith("OPEN_ERROR"):
        continue
    if "status firmware_sha=" in text and "rf transport_ready=" in text:
        console_port = device
        console_text = text
        break
    if "=== Growbox service console ===" in text or "growbox>" in text:
        console_port = device
        console_text = text

if console_port is None:
    raise SystemExit("service console was not observed on any enumerated serial port")

required = [
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
missing = [token for token in required if token not in console_text]
if missing:
    raise SystemExit("service console response missing: " + ", ".join(missing))

for forbidden in ["manual_rf_tx", "Guru Meditation", "abort() was called"]:
    if forbidden in console_text:
        raise SystemExit(f"forbidden smoke-test evidence observed: {forbidden}")

print(
    "STAGE28D_SERVICE_CONSOLE_HW_SMOKE_PASS "
    f"sha={expected} console_port={console_port} menu=pass status=pass sensors=pass "
    "rf_list=pass rf_ready=1 manual_rf_tx=0 runtime_outputs=fake-locked"
)
PY

test -z "$(git status --porcelain)"
