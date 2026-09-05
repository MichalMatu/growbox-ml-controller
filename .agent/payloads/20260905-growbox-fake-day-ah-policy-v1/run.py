from __future__ import annotations

import json
import re
import sys
import time
import urllib.request
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import serial

EXPECTED = "dfc6dc86a47ad2158e36bb0d5241b0153dbce387"
PORT = "/dev/cu.usbserial-1130"
SHELLY = "http://192.168.0.16"
WARSAW = ZoneInfo("Europe/Warsaw")
UTC = ZoneInfo("UTC")


def shelly_master_on() -> bool:
    with urllib.request.urlopen(SHELLY + "/rpc/Switch.GetStatus?id=0", timeout=5) as response:
        return bool(json.loads(response.read().decode()).get("output", False))


def collect(handle: serial.Serial, seconds: float) -> str:
    end = time.monotonic() + seconds
    chunks: list[bytes] = []
    while time.monotonic() < end:
        data = handle.read(4096)
        if data:
            chunks.append(data)
    return b"".join(chunks).decode(errors="replace")


def send(handle: serial.Serial, command: str, seconds: float = 3.0) -> str:
    handle.write(command.encode() + b"\n")
    handle.flush()
    return collect(handle, seconds)


def parse_rtc_epoch(text: str) -> int:
    matches = re.findall(r"rtc sampled=1 available=1 trusted=1 unix_time_s=(\d+).*?local_valid=1", text)
    if not matches:
        raise RuntimeError("trusted RTC snapshot not found")
    return int(matches[-1])


def field(line: str, key: str, cast, default):
    match = re.search(r"(?:^|\s)" + re.escape(key) + r"=([^\s]+)", line)
    if not match:
        return default
    try:
        return cast(match.group(1))
    except Exception:
        return default


def choose_day_epoch(original_epoch: int) -> tuple[int, str]:
    local = datetime.fromtimestamp(original_epoch, tz=UTC).astimezone(WARSAW)
    if 6 <= local.hour < 22:
        test_local = local.replace(minute=0, second=0, microsecond=0)
    elif local.hour >= 22:
        test_local = local.replace(hour=21, minute=0, second=0, microsecond=0)
    else:
        test_local = (local - timedelta(days=1)).replace(hour=21, minute=0, second=0, microsecond=0)
    return int(test_local.astimezone(UTC).timestamp()), test_local.isoformat()


if shelly_master_on():
    raise SystemExit("FAKE_DAY_AH refusing test: Shelly master is ON")

handle = serial.Serial(port=None, baudrate=115200, timeout=0.08, write_timeout=1)
handle.dtr = False
handle.rts = False
handle.port = PORT
handle.open()

original_epoch: int | None = None
original_monotonic: float | None = None
main_error: BaseException | None = None
restore_error: BaseException | None = None
try:
    # Opening CH340 may reset the ESP32-S3. Drain the complete startup first.
    collect(handle, 14.0)
    status_text = send(handle, "status", 3.0)
    expected_status = f"status firmware_sha={EXPECTED}"
    if expected_status not in status_text:
        raise RuntimeError("exact installed firmware SHA not confirmed")
    if "outputs=fake-locked" not in status_text or "rf_ready=1" not in status_text:
        raise RuntimeError("installed image is not fake-locked with RF diagnostics ready")

    sensor_text = send(handle, "sensors", 3.0)
    original_epoch = parse_rtc_epoch(sensor_text)
    original_monotonic = time.monotonic()
    test_epoch, test_local = choose_day_epoch(original_epoch)
    print(
        "FAKE_DAY_AH_RTC_BASELINE "
        + json.dumps(
            {
                "original_epoch": original_epoch,
                "original_local": datetime.fromtimestamp(original_epoch, tz=UTC).astimezone(WARSAW).isoformat(),
                "test_epoch": test_epoch,
                "test_local": test_local,
            },
            sort_keys=True,
            separators=(",", ":"),
        ),
        flush=True,
    )

    set_text = send(handle, f"rtc set-unix {test_epoch}", 4.0)
    if "rtc_set_utc ok=1" not in set_text:
        raise RuntimeError("day-profile RTC write/readback failed")

    # Collect about one minute of fake-locked telemetry under a real day profile.
    records: list[dict[str, object]] = []
    buf = ""
    deadline = time.monotonic() + 65.0
    next_status = time.monotonic() + 12.0
    while time.monotonic() < deadline:
        now = time.monotonic()
        if now >= next_status:
            handle.write(b"status\n")
            handle.flush()
            next_status += 20.0
        data = handle.read(4096)
        if not data:
            continue
        buf += data.decode(errors="replace")
        while "\n" in buf:
            line, buf = buf.split("\n", 1)
            line = line.strip()
            if "soak_v=2 " not in line:
                continue
            record = {
                "sha": field(line, "firmware_sha", str, ""),
                "uptime_ms": field(line, "uptime_ms", int, 0),
                "mode": field(line, "outputs", str, ""),
                "requested_fan": field(line, "requested_fan", float, 0.0),
                "physical_fan": field(line, "physical_fan", int, 0),
                "tp_sample": field(line, "tp_sample", int, 0),
                "tp_t": field(line, "tp_t", float, 0.0),
                "tp_rh": field(line, "tp_rh", float, 0.0),
                "xiaomi_sample": field(line, "xiaomi_sample", int, 0),
                "xiaomi_t": field(line, "xiaomi_t", float, 0.0),
                "xiaomi_rh": field(line, "xiaomi_rh", float, 0.0),
                "xiaomi_age_ms": field(line, "xiaomi_age_ms", int, 0),
                "xiaomi_packets": field(line, "xiaomi_packets", int, 0),
                "xiaomi_accepted": field(line, "xiaomi_accepted", int, 0),
                "xiaomi_rejected": field(line, "xiaomi_rejected", int, 0),
                "ble_scan_errors": field(line, "ble_scan_errors", int, 0),
                "ble_lock_drops": field(line, "ble_adv_lock_drops", int, 0),
                "storage_write_errors": field(line, "storage_write_errors", int, 0),
                "storage_queue_drops": field(line, "storage_queue_drops", int, 0),
            }
            if record["sha"] != EXPECTED:
                raise RuntimeError(f"unexpected telemetry SHA {record['sha']}")
            if record["mode"] != "fake-locked" or record["physical_fan"] != 0:
                raise RuntimeError("physical output escaped fake-locked state")
            if record["storage_write_errors"] != 0 or record["storage_queue_drops"] != 0:
                raise RuntimeError("storage error/drop during fake-day observation")
            records.append(record)

    if len(records) < 5:
        raise RuntimeError(f"insufficient fake-day telemetry records={len(records)}")
    fresh = [r for r in records if r["xiaomi_sample"] == 1 and r["xiaomi_age_ms"] <= 30000]
    request_records = [r for r in records if r["requested_fan"] >= 0.10]
    first = records[0]
    last = records[-1]
    summary = {
        "records": len(records),
        "fresh_xiaomi_records": len(fresh),
        "max_xiaomi_age_ms": max((int(r["xiaomi_age_ms"]) for r in records if r["xiaomi_sample"] == 1), default=None),
        "max_requested_fan": max(float(r["requested_fan"]) for r in records),
        "request_records_ge_010": len(request_records),
        "xiaomi_packet_delta": max(0, int(last["xiaomi_packets"]) - int(first["xiaomi_packets"])),
        "xiaomi_accepted_delta": max(0, int(last["xiaomi_accepted"]) - int(first["xiaomi_accepted"])),
        "xiaomi_rejected_delta": max(0, int(last["xiaomi_rejected"]) - int(first["xiaomi_rejected"])),
        "ble_scan_errors_max": max(int(r["ble_scan_errors"]) for r in records),
        "ble_lock_drops_max": max(int(r["ble_lock_drops"]) for r in records),
        "first_tp": [first["tp_t"], first["tp_rh"]],
        "last_tp": [last["tp_t"], last["tp_rh"]],
        "first_xiaomi": [first["xiaomi_t"], first["xiaomi_rh"]],
        "last_xiaomi": [last["xiaomi_t"], last["xiaomi_rh"]],
    }
    print("FAKE_DAY_AH_SUMMARY " + json.dumps(summary, sort_keys=True, separators=(",", ":")), flush=True)
    if len(fresh) < max(1, len(records) // 2):
        raise RuntimeError("Xiaomi was not fresh for enough fake-day records")
    if not request_records:
        raise RuntimeError("day profile did not produce requested_fan >= 0.10")
    print("FAKE_DAY_AH_POLICY_PASS requested_fan_ge_010=1 outputs=fake-locked rf_tx=0", flush=True)
except BaseException as exc:
    main_error = exc
finally:
    if original_epoch is not None and original_monotonic is not None:
        try:
            elapsed = max(0, int(round(time.monotonic() - original_monotonic)))
            restore_epoch = original_epoch + elapsed
            restore_text = send(handle, f"rtc set-unix {restore_epoch}", 4.0)
            if "rtc_set_utc ok=1" not in restore_text:
                raise RuntimeError("RTC restoration write/readback failed")
            verify_text = send(handle, "sensors", 4.0)
            restored_epoch = parse_rtc_epoch(verify_text)
            delta = abs(restored_epoch - (restore_epoch + 4))
            if delta > 8:
                raise RuntimeError(f"RTC restoration verification delta too large: {delta}s")
            print(
                "FAKE_DAY_AH_RTC_RESTORE_PASS "
                + json.dumps(
                    {
                        "restore_requested_epoch": restore_epoch,
                        "restored_epoch": restored_epoch,
                        "verification_delta_s": delta,
                        "restored_local": datetime.fromtimestamp(restored_epoch, tz=UTC).astimezone(WARSAW).isoformat(),
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                flush=True,
            )
        except BaseException as exc:
            restore_error = exc
    handle.close()

if shelly_master_on():
    raise RuntimeError("Shelly master unexpectedly ON after fake-day observation")
if restore_error is not None:
    raise restore_error
if main_error is not None:
    raise main_error
print("FAKE_DAY_AH_COMPLETE port=/dev/cu.usbserial-1130 shelly_master=off", flush=True)
