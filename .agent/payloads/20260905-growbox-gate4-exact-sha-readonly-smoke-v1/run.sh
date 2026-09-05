#!/usr/bin/env bash
set -euo pipefail

EXPECTED=8710bf127ad895e262f604e1b4c59ea11b760667
BRANCH=mvp/environment-controller

git fetch -q origin "$BRANCH"
git reset --hard "$EXPECTED"
test "$(git rev-parse HEAD)" = "$EXPECTED"
test "$(git rev-parse origin/$BRANCH)" = "$EXPECTED"
test -z "$(git status --porcelain)"

export GROWBOX_FIRMWARE_GIT_SHA="$EXPECTED"
export GROWBOX_STAGE27_SD_ENABLED=1
export GROWBOX_STAGE27_FLASH_FALLBACK_ENABLED=1
export GROWBOX_RF433_LOOPBACK_ENABLED=1
export GROWBOX_RF433_LOOPBACK_AUTO_SMOKE=0
export GROWBOX_RF433_REMOTE_CAPTURE_ENABLED=0
export GROWBOX_STAGE28_SERVICE_CONSOLE_ENABLED=1
export STAGE27C_BUILD_DIR=build/idf-gate4-exact-sha-readonly-smoke-v1
export CMAKE_BUILD_PARALLEL_LEVEL=1

bash scripts/stage27c_crowpanel.sh flash

PY="$(git rev-parse --show-toplevel)/.venv/bin/python"
if [[ ! -x "$PY" ]]; then
  PY="$(command -v python3)"
fi

"$PY" - "$EXPECTED" <<'PY'
import json
import re
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import serial
from tools.stage27c_soak import detect_ch340_port

expected = sys.argv[1]
port = detect_ch340_port()
if not port:
    raise SystemExit("CrowPanel CH340 serial port was not detected")
print("GATE4_PORT", port)

chunks = []
def collect(handle, duration):
    deadline = time.monotonic() + duration
    local = []
    while time.monotonic() < deadline:
        data = handle.read(4096)
        if data:
            chunks.append(data)
            local.append(data)
    return b"".join(local).decode("utf-8", errors="replace")

def command(handle, text, duration=2.0):
    handle.write(text.encode("ascii") + b"\n")
    handle.flush()
    return collect(handle, duration)

with serial.Serial(port, 115200, timeout=0.12, write_timeout=1.0) as handle:
    try:
        handle.dtr = False
        handle.rts = False
    except Exception:
        pass
    collect(handle, 4.0)

    status_text = ""
    for _ in range(5):
        status_text += command(handle, "status", 2.0)
        if f"status firmware_sha={expected}" in status_text and "outputs=fake-locked" in status_text and "rf_ready=1" in status_text:
            break
    else:
        raise SystemExit("exact firmware/status/rf identity check failed")

    epoch = int(time.time())
    rtc_text = command(handle, f"rtc set-unix {epoch}", 3.0)
    if "rtc_set_utc ok=1" not in rtc_text or "trusted=1" not in rtc_text or "local_valid=1" not in rtc_text:
        raise SystemExit("RTC UTC set/readback/local conversion failed: " + rtc_text[-2000:])
    match = re.search(r"readback_unix_s=(\d+).*?delta_s=(\d+).*?local=(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}).*?offset_s=(-?\d+).*?dst=(\d+)", rtc_text, re.S)
    if not match:
        raise SystemExit("RTC readback line parse failed")
    readback_epoch = int(match.group(1))
    delta_s = int(match.group(2))
    local_text = match.group(3)
    offset_s = int(match.group(4))
    dst = int(match.group(5))
    if delta_s > 1 or abs(readback_epoch - epoch) > 1:
        raise SystemExit("RTC epoch readback outside tolerance")
    host_local = datetime.fromtimestamp(readback_epoch, timezone.utc).astimezone(ZoneInfo("Europe/Warsaw"))
    if local_text != host_local.strftime("%Y-%m-%dT%H:%M:%S"):
        raise SystemExit(f"Europe/Warsaw mismatch firmware={local_text} host={host_local.isoformat()}")
    expected_offset = int(host_local.utcoffset().total_seconds())
    if offset_s != expected_offset:
        raise SystemExit(f"timezone offset mismatch firmware={offset_s} host={expected_offset}")
    if dst != int(bool(host_local.dst() and host_local.dst().total_seconds())):
        raise SystemExit("DST flag mismatch")
    print(f"RTC_GATE_PASS epoch={readback_epoch} local={local_text} offset_s={offset_s} dst={dst}")

    sensor_text = ""
    telemetry_text = ""
    deadline = time.monotonic() + 75.0
    next_sensor = 0.0
    while time.monotonic() < deadline:
        now = time.monotonic()
        if now >= next_sensor:
            sensor_text += command(handle, "sensors", 2.0)
            next_sensor = time.monotonic() + 8.0
        telemetry_text += collect(handle, 1.0)
        combined = b"".join(chunks).decode("utf-8", errors="replace")
        have_sensors = all(token in sensor_text for token in ["scd41 temp_c=", "tp357 temp_c=", "xiaomi temp_c=", "rtc sampled=1 available=1 trusted=1"])
        have_sd = "storage_backend=sd" in combined and "storage_sd_mounted=1" in combined and "storage_queue_drops=0" in combined and "storage_write_errors=0" in combined
        if have_sensors and have_sd:
            break

text = b"".join(chunks).decode("utf-8", errors="replace")
Path("/tmp/growbox_gate4_readonly_smoke_v1.log").write_text(text)
print(text[-24000:])

required = [
    f"firmware_sha={expected}",
    "outputs=fake-locked",
    "rf_ready=1",
    "scd41 temp_c=",
    "tp357 temp_c=",
    "xiaomi temp_c=",
    "rtc sampled=1 available=1 trusted=1",
    "storage_backend=sd",
    "storage_sd_mounted=1",
    "storage_queue_drops=0",
    "storage_write_errors=0",
]
missing = [token for token in required if token not in text]
if missing:
    raise SystemExit("Gate4 smoke missing evidence: " + ", ".join(missing))
for forbidden in ["manual_rf_tx", "Guru Meditation", "abort() was called", "assert failed", "Brownout detector"]:
    if forbidden in text:
        raise SystemExit(f"forbidden Gate4 evidence observed: {forbidden}")

# Shelly is read-only in Gate4.
try:
    with urllib.request.urlopen("http://192.168.0.16/rpc/Switch.GetStatus?id=0", timeout=5) as response:
        shelly = json.loads(response.read().decode("utf-8"))
    print("SHELLY_READONLY", json.dumps({k: shelly.get(k) for k in ("output", "apower", "voltage", "current", "temperature")}, sort_keys=True))
except Exception as exc:
    print("SHELLY_READONLY_DEGRADED", repr(exc))

print(
    "GATE4_EXACT_SHA_READONLY_SMOKE_PASS "
    f"sha={expected} port={port} rtc=pass timezone=Europe/Warsaw sensors=pass "
    "storage=sd outputs=fake-locked manual_rf_tx=0"
)
PY

test -z "$(git status --porcelain)"
