from __future__ import annotations

import json
import os
import re
import statistics
import subprocess
import time
import urllib.request
from pathlib import Path

import serial

EXPECTED = "dfc6dc86a47ad2158e36bb0d5241b0153dbce387"
BRANCH = "mvp/environment-controller"
PORT = "/dev/cu.usbserial-1130"
SHELLY = "http://192.168.0.16"
SAFE_BUILD = "build/idf-interrupted-test-recovery-v1"


def run(cmd: list[str], *, env: dict[str, str] | None = None) -> None:
    subprocess.run(cmd, check=True, env=env)


def out(cmd: list[str]) -> str:
    return subprocess.check_output(cmd, text=True).strip()


def shelly_status() -> dict:
    with urllib.request.urlopen(SHELLY + "/rpc/Switch.GetStatus?id=0", timeout=5) as response:
        return json.loads(response.read().decode())


def median_power(n: int = 7) -> float:
    vals: list[float] = []
    for _ in range(n):
        s = shelly_status()
        if not bool(s.get("output", False)):
            raise RuntimeError("Shelly master is OFF; recovery will not change master state")
        vals.append(float(s.get("apower", 0.0)))
        time.sleep(0.35)
    return statistics.median(vals)


def collect(h: serial.Serial, seconds: float) -> str:
    end = time.monotonic() + seconds
    chunks: list[bytes] = []
    while time.monotonic() < end:
        b = h.read(4096)
        if b:
            chunks.append(b)
    return b"".join(chunks).decode(errors="replace")


def open_console(wait_s: float = 12.0) -> serial.Serial:
    h = serial.Serial(port=None, baudrate=115200, timeout=0.08, write_timeout=1)
    h.dtr = False
    h.rts = False
    h.port = PORT
    h.open()
    collect(h, wait_s)
    return h


def send(h: serial.Serial, cmd: str, seconds: float = 3.0) -> str:
    h.write(cmd.encode() + b"\n")
    h.flush()
    return collect(h, seconds)


def field(line: str, key: str, cast, default):
    m = re.search(r"(?:^|\s)" + re.escape(key) + r"=([^\s]+)", line)
    if not m:
        return default
    try:
        return cast(m.group(1))
    except Exception:
        return default


def latest_tp(text: str) -> float | None:
    value: float | None = None
    for line in text.splitlines():
        if "soak_v=2 " in line and field(line, "tp_sample", int, 0) == 1:
            value = field(line, "tp_t", float, None)
    return value


def parse_rtc_epoch(text: str) -> int | None:
    m = re.findall(r"rtc sampled=1 available=1 trusted=1 unix_time_s=(\d+).*?local_valid=1", text)
    return int(m[-1]) if m else None


def manual_rf(h: serial.Serial, fan_on: bool) -> None:
    for cmd in ("rf lamp on", f"rf fan {'on' if fan_on else 'off'}", "rf humidifier off"):
        resp = send(h, cmd, 2.5)
        print("RECOVERY_RF " + cmd + " response=" + json.dumps(resp[-600:]), flush=True)


def sample_temp(h: serial.Serial, seconds: float = 16.0) -> float | None:
    text = collect(h, seconds)
    return latest_tp(text)


# Repository fail-closed preflight.
run(["git", "fetch", "-q", "origin", BRANCH, "agent-control"])
if out(["git", "rev-parse", "HEAD"]) != EXPECTED:
    raise RuntimeError("workspace HEAD mismatch")
if out(["git", "rev-parse", f"origin/{BRANCH}"]) != EXPECTED:
    raise RuntimeError("origin branch HEAD mismatch")
if out(["git", "status", "--porcelain"]):
    raise RuntimeError("workspace is dirty")

initial_shelly = shelly_status()
if not bool(initial_shelly.get("output", False)):
    raise RuntimeError("Shelly master is OFF; refusing to change it")
print("RECOVERY_SHELLY_INITIAL " + json.dumps(initial_shelly, sort_keys=True, separators=(",", ":")), flush=True)

# Inspect current board state and restore RTC from the host clock before any flash.
h = open_console(12.0)
try:
    status_before = send(h, "status", 4.0)
    sensors_before = send(h, "sensors", 4.0)
    rtc_before = parse_rtc_epoch(sensors_before)
    print("RECOVERY_STATUS_BEFORE " + json.dumps(status_before[-1800:]), flush=True)
    print("RECOVERY_RTC_BEFORE " + json.dumps({"rtc_epoch": rtc_before, "host_epoch": int(time.time())}, sort_keys=True), flush=True)

    host_epoch = int(time.time())
    rtc_set = send(h, f"rtc set-unix {host_epoch}", 4.0)
    if "rtc_set_utc ok=1" not in rtc_set:
        raise RuntimeError("failed to restore RTC from host epoch")
    sensors_after = send(h, "sensors", 4.0)
    rtc_after = parse_rtc_epoch(sensors_after)
    if rtc_after is None or abs(rtc_after - int(time.time())) > 10:
        raise RuntimeError(f"RTC verification failed rtc_after={rtc_after} host={int(time.time())}")
    print("RECOVERY_RTC_RESTORED " + json.dumps({"rtc_epoch": rtc_after, "host_epoch": int(time.time())}, sort_keys=True), flush=True)

    tp_before = sample_temp(h, 16.0)
    fan_before_flash = tp_before is None or tp_before >= 28.0
    manual_rf(h, fan_before_flash)
    print("RECOVERY_PRE_FLASH_STATE " + json.dumps({"tp_t": tp_before, "lamp": "on", "fan": "on" if fan_before_flash else "off", "humidifier": "off"}, sort_keys=True), flush=True)
finally:
    h.close()

# Build and flash exact-SHA fake-locked firmware with normal storage enabled.
env = os.environ.copy()
env.update({
    "CMAKE_BUILD_PARALLEL_LEVEL": "1",
    "GROWBOX_RF433_LOOPBACK_ENABLED": "1",
    "GROWBOX_RF433_LOOPBACK_AUTO_SMOKE": "0",
    "GROWBOX_STAGE28_REAL_OUTPUTS_ENABLED": "0",
    "GROWBOX_STAGE28_THERMAL_TEST_SEQUENCE_ENABLED": "0",
    "GROWBOX_STAGE27_SD_ENABLED": "1",
    "GROWBOX_STAGE27_FLASH_FALLBACK_ENABLED": "1",
    "GROWBOX_FIRMWARE_GIT_SHA": EXPECTED,
    "STAGE27C_BUILD_DIR": SAFE_BUILD,
    "PORT": PORT,
})
run(["bash", "scripts/stage27c_crowpanel.sh", "flash"], env=env)
cache = Path(SAFE_BUILD, "CMakeCache.txt").read_text(errors="replace")
for required in (
    "GROWBOX_STAGE28_REAL_OUTPUTS_ENABLED:STRING=0",
    "GROWBOX_STAGE28_THERMAL_TEST_SEQUENCE_ENABLED:STRING=0",
    "GROWBOX_RF433_LOOPBACK_ENABLED:STRING=1",
    "GROWBOX_RF433_LOOPBACK_AUTO_SMOKE:STRING=0",
    "GROWBOX_STAGE27_SD_ENABLED:STRING=1",
    "GROWBOX_STAGE27_FLASH_FALLBACK_ENABLED:STRING=1",
):
    if required not in cache:
        raise RuntimeError(f"safe build cache missing {required}")

h = open_console(14.0)
try:
    status_after = send(h, "status", 4.0)
    if f"status firmware_sha={EXPECTED}" not in status_after:
        raise RuntimeError("safe firmware SHA not confirmed after flash")
    if "outputs=fake-locked" not in status_after or "rf_ready=1" not in status_after:
        raise RuntimeError("safe firmware is not fake-locked/rf-ready")

    tp_after = sample_temp(h, 20.0)
    fan_final = tp_after is None or tp_after >= 28.0
    manual_rf(h, fan_final)
    time.sleep(12.0)
    final_power = median_power()
    if not (60.0 <= final_power <= 130.0):
        raise RuntimeError(f"unexpected final lamp-on power {final_power:.2f}W")

    final = {
        "sha": EXPECTED,
        "outputs": "fake-locked",
        "port": PORT,
        "shelly_master": "on",
        "lamp": "on",
        "fan": "on" if fan_final else "off",
        "humidifier": "off",
        "tp_t": tp_after,
        "power_w": final_power,
        "rtc_host_delta_s": None,
    }
    sensors_final = send(h, "sensors", 4.0)
    rtc_final = parse_rtc_epoch(sensors_final)
    if rtc_final is not None:
        final["rtc_host_delta_s"] = abs(rtc_final - int(time.time()))
    print("RECOVERY_FINAL " + json.dumps(final, sort_keys=True, separators=(",", ":")), flush=True)
    if final["rtc_host_delta_s"] is None or final["rtc_host_delta_s"] > 10:
        raise RuntimeError("final RTC is not synchronized to host")
    if fan_final:
        raise RuntimeError("fan intentionally left ON because final temperature was >=28C or unavailable")
finally:
    h.close()

print("INTERRUPTED_TEST_RECOVERY_PASS lamp=on fan=off humidifier=off shelly_master=on outputs=fake-locked", flush=True)
