from __future__ import annotations

import json
import math
import re
import statistics
import subprocess
import time
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import serial

EXPECTED = "dfc6dc86a47ad2158e36bb0d5241b0153dbce387"
BRANCH = "mvp/environment-controller"
PORT = "/dev/cu.usbserial-1130"
SHELLY = "http://192.168.0.16"
ACTIVE_BUILD = "build/idf-fan-30m-day-real-v1"
SAFE_BUILD = "build/idf-fan-30m-day-safe-v1"
OBSERVE_S = 1800.0
WARSAW = ZoneInfo("Europe/Warsaw")
UTC = ZoneInfo("UTC")


def run(cmd: list[str], *, env: dict[str, str] | None = None) -> None:
    subprocess.run(cmd, check=True, env=env)


def output(cmd: list[str]) -> str:
    return subprocess.check_output(cmd, text=True).strip()


def firmware_env(real_outputs: bool, build_dir: str) -> dict[str, str]:
    import os
    env = os.environ.copy()
    env.update(
        {
            "CMAKE_BUILD_PARALLEL_LEVEL": "1",
            "GROWBOX_RF433_LOOPBACK_ENABLED": "1",
            "GROWBOX_RF433_LOOPBACK_AUTO_SMOKE": "0",
            "GROWBOX_STAGE28_REAL_OUTPUTS_ENABLED": "1" if real_outputs else "0",
            "GROWBOX_STAGE28_THERMAL_TEST_SEQUENCE_ENABLED": "0",
            "GROWBOX_FIRMWARE_GIT_SHA": EXPECTED,
            "STAGE27C_BUILD_DIR": build_dir,
            "PORT": PORT,
        }
    )
    return env


def build(real_outputs: bool, build_dir: str) -> None:
    run(["bash", "scripts/stage27c_crowpanel.sh", "build"], env=firmware_env(real_outputs, build_dir))
    cache = Path(build_dir, "CMakeCache.txt").read_text(errors="replace")
    want = "1" if real_outputs else "0"
    required = [
        f"GROWBOX_STAGE28_REAL_OUTPUTS_ENABLED:STRING={want}",
        "GROWBOX_STAGE28_THERMAL_TEST_SEQUENCE_ENABLED:STRING=0",
        "GROWBOX_RF433_LOOPBACK_ENABLED:STRING=1",
        "GROWBOX_RF433_LOOPBACK_AUTO_SMOKE:STRING=0",
    ]
    missing = [x for x in required if x not in cache]
    if missing:
        raise RuntimeError(f"build cache mismatch: {missing}")


def flash(real_outputs: bool, build_dir: str) -> None:
    run(["bash", "scripts/stage27c_crowpanel.sh", "flash"], env=firmware_env(real_outputs, build_dir))


def shelly_status() -> dict:
    with urllib.request.urlopen(SHELLY + "/rpc/Switch.GetStatus?id=0", timeout=5) as response:
        return json.loads(response.read().decode())


def median_power(n: int = 7, delay: float = 0.35) -> float:
    values: list[float] = []
    for _ in range(n):
        status = shelly_status()
        if not bool(status.get("output", False)):
            raise RuntimeError("Shelly master unexpectedly OFF")
        values.append(float(status.get("apower", 0.0)))
        time.sleep(delay)
    return statistics.median(values)


def collect(handle: serial.Serial, seconds: float) -> str:
    end = time.monotonic() + seconds
    chunks: list[bytes] = []
    while time.monotonic() < end:
        data = handle.read(4096)
        if data:
            chunks.append(data)
    return b"".join(chunks).decode(errors="replace")


def open_console(boot_wait: float = 14.0) -> serial.Serial:
    last: BaseException | None = None
    for attempt in range(3):
        handle = serial.Serial(port=None, baudrate=115200, timeout=0.08, write_timeout=1)
        handle.dtr = False
        handle.rts = False
        handle.port = PORT
        try:
            handle.open()
            collect(handle, boot_wait if attempt == 0 else 8.0)
            return handle
        except BaseException as exc:
            last = exc
            try:
                handle.close()
            except Exception:
                pass
            time.sleep(2.0)
    raise RuntimeError(f"unable to open fixed growbox serial port: {last}")


def send(handle: serial.Serial, command: str, seconds: float = 3.0) -> str:
    handle.write(command.encode() + b"\n")
    handle.flush()
    return collect(handle, seconds)


def field(line: str, key: str, cast, default):
    match = re.search(r"(?:^|\s)" + re.escape(key) + r"=([^\s]+)", line)
    if not match:
        return default
    try:
        return cast(match.group(1))
    except Exception:
        return default


def parse_rtc_epoch(text: str) -> int:
    matches = re.findall(r"rtc sampled=1 available=1 trusted=1 unix_time_s=(\d+).*?local_valid=1", text)
    if not matches:
        raise RuntimeError("trusted RTC snapshot not found")
    return int(matches[-1])


def choose_day_epoch(original_epoch: int) -> tuple[int, str]:
    local = datetime.fromtimestamp(original_epoch, tz=UTC).astimezone(WARSAW)
    if 6 <= local.hour < 22:
        test_local = local.replace(minute=0, second=0, microsecond=0)
    elif local.hour >= 22:
        test_local = local.replace(hour=21, minute=0, second=0, microsecond=0)
    else:
        test_local = (local - timedelta(days=1)).replace(hour=21, minute=0, second=0, microsecond=0)
    return int(test_local.astimezone(UTC).timestamp()), test_local.isoformat()


def absolute_humidity(temp_c: float, rh_pct: float) -> float:
    if not (-40.0 <= temp_c <= 80.0 and 0.0 <= rh_pct <= 100.0):
        return float("nan")
    es = 6.112 * math.exp((17.67 * temp_c) / (temp_c + 243.5))
    e = (rh_pct / 100.0) * es
    return 216.7 * e / (273.15 + temp_c)


def linear_slope_per_min(points: list[tuple[float, float]]) -> float | None:
    pts = [(x, y) for x, y in points if math.isfinite(y)]
    if len(pts) < 5:
        return None
    x0 = statistics.mean(x for x, _ in pts)
    y0 = statistics.mean(y for _, y in pts)
    den = sum((x - x0) ** 2 for x, _ in pts)
    if den <= 0:
        return None
    slope_per_s = sum((x - x0) * (y - y0) for x, y in pts) / den
    return slope_per_s * 60.0


def manual_rf(handle: serial.Serial, lamp: str, fan: str, humidifier: str) -> None:
    for command in (f"rf lamp {lamp}", f"rf fan {fan}", f"rf humidifier {humidifier}"):
        response = send(handle, command, 2.5)
        print("FAN30_RF " + command + " response=" + json.dumps(response[-800:]), flush=True)


def latest_tp_from_text(text: str) -> float | None:
    found: float | None = None
    for line in text.splitlines():
        if "soak_v=2 " not in line:
            continue
        if field(line, "tp_sample", int, 0) != 1:
            continue
        found = field(line, "tp_t", float, None)
    return found


def preflight_and_force_day() -> dict:
    if not bool(shelly_status().get("output", False)):
        raise RuntimeError("Shelly master is OFF; refusing to change it")
    handle = open_console(14.0)
    state: dict = {}
    try:
        status_text = send(handle, "status", 4.0)
        if f"status firmware_sha={EXPECTED}" not in status_text:
            raise RuntimeError("exact safe firmware SHA not confirmed before test")
        if "outputs=fake-locked" not in status_text or "rf_ready=1" not in status_text:
            raise RuntimeError("preflight image is not fake-locked/rf-ready")
        sensor_text = send(handle, "sensors", 4.0)
        original_epoch = parse_rtc_epoch(sensor_text)
        original_monotonic = time.monotonic()
        test_epoch, test_local = choose_day_epoch(original_epoch)
        state.update(
            {
                "original_epoch": original_epoch,
                "original_monotonic": original_monotonic,
                "original_local": datetime.fromtimestamp(original_epoch, tz=UTC).astimezone(WARSAW).isoformat(),
                "test_epoch": test_epoch,
                "test_local": test_local,
            }
        )
        print("FAN30_RTC_BASELINE " + json.dumps(state, sort_keys=True, separators=(",", ":")), flush=True)
        set_text = send(handle, f"rtc set-unix {test_epoch}", 4.0)
        if "rtc_set_utc ok=1" not in set_text:
            raise RuntimeError("unable to switch RTC to bounded day-profile time")
        state["rtc_changed"] = True
        manual_rf(handle, "on", "off", "off")
    finally:
        handle.close()
    time.sleep(12.0)
    baseline = median_power()
    state["lamp_baseline_w"] = baseline
    if not (60.0 <= baseline <= 125.0):
        raise RuntimeError(f"unexpected lamp-on baseline {baseline:.2f}W")
    print(f"FAN30_PREFLIGHT_PASS lamp_baseline_w={baseline:.3f} master=on port={PORT}", flush=True)
    return state


def monitor_active(state: dict) -> dict:
    handle = open_console(16.0)
    records: list[dict] = []
    powers: list[dict] = []
    tx_errors_max = 0
    thermal_seen = False
    buf = ""
    try:
        status_text = send(handle, "status", 4.0)
        if f"status firmware_sha={EXPECTED}" not in status_text or "outputs=real-bounded" not in status_text:
            raise RuntimeError("active image exact SHA/real-bounded mode not confirmed")
        start = time.monotonic()
        deadline = start + OBSERVE_S
        last_serial = time.monotonic()
        next_power = start
        next_heartbeat = start + 30.0
        while time.monotonic() < deadline:
            data = handle.read(4096)
            if data:
                last_serial = time.monotonic()
                buf += data.decode(errors="replace")
                while "\n" in buf:
                    line, buf = buf.split("\n", 1)
                    line = line.strip()
                    if not line:
                        continue
                    if "stage28d_output " in line:
                        tx_errors_max = max(tx_errors_max, field(line, "tx_errors", int, 0))
                    if "soak_v=2 " not in line:
                        continue
                    r = {
                        "t": time.monotonic() - start,
                        "sha": field(line, "firmware_sha", str, ""),
                        "uptime": field(line, "uptime_ms", int, 0),
                        "mode": field(line, "outputs", str, ""),
                        "storage": field(line, "storage_backend", str, ""),
                        "we": field(line, "storage_write_errors", int, 0),
                        "qd": field(line, "storage_queue_drops", int, 0),
                        "tp_sample": field(line, "tp_sample", int, 0),
                        "tp_t": field(line, "tp_t", float, 0.0),
                        "tp_rh": field(line, "tp_rh", float, 0.0),
                        "xiaomi_sample": field(line, "xiaomi_sample", int, 0),
                        "xiaomi_t": field(line, "xiaomi_t", float, 0.0),
                        "xiaomi_rh": field(line, "xiaomi_rh", float, 0.0),
                        "xiaomi_age": field(line, "xiaomi_age_ms", int, 999999999),
                        "xiaomi_packets": field(line, "xiaomi_packets", int, 0),
                        "xiaomi_accepted": field(line, "xiaomi_accepted", int, 0),
                        "xiaomi_rejected": field(line, "xiaomi_rejected", int, 0),
                        "ble_scan_errors": field(line, "ble_scan_errors", int, 0),
                        "ble_lock_drops": field(line, "ble_adv_lock_drops", int, 0),
                        "requested_fan": field(line, "requested_fan", float, 0.0),
                        "applied_fan": field(line, "applied_fan", float, 0.0),
                        "physical_light": field(line, "physical_light", int, 0),
                        "physical_fan": field(line, "physical_fan", int, 0),
                        "physical_hum": field(line, "physical_humidifier", int, 0),
                        "thermal": field(line, "thermal_latched", int, 0),
                        "force_fan": field(line, "force_fan", int, 0),
                        "transitions": field(line, "arbiter_transitions", int, 0),
                        "dwell": field(line, "arbiter_dwell_holds", int, 0),
                    }
                    if r["sha"] != EXPECTED or r["mode"] != "real-bounded":
                        raise RuntimeError("telemetry exact-SHA/mode gate failed")
                    if r["we"] != 0 or r["qd"] != 0:
                        raise RuntimeError("storage write/drop during test")
                    if r["physical_light"] != 1:
                        raise RuntimeError("lamp left ON state during forced daytime test")
                    if r["applied_fan"] not in (0.0, 1.0) or int(r["applied_fan"]) != r["physical_fan"]:
                        raise RuntimeError("fan applied/physical state mismatch")
                    if r["tp_sample"] and r["tp_t"] >= 31.0:
                        raise RuntimeError(f"authoritative TP357 temperature unsafe {r['tp_t']:.2f}C")
                    thermal_seen = thermal_seen or bool(r["thermal"] or r["force_fan"])
                    r["inside_ah"] = absolute_humidity(r["tp_t"], r["tp_rh"]) if r["tp_sample"] else float("nan")
                    r["intake_ah"] = absolute_humidity(r["xiaomi_t"], r["xiaomi_rh"]) if r["xiaomi_sample"] else float("nan")
                    records.append(r)
            now = time.monotonic()
            if now - last_serial > 45.0:
                raise RuntimeError("serial telemetry silent >45s")
            if now >= next_power and records:
                r = records[-1]
                p = median_power(n=5, delay=0.25)
                if p > 130.0:
                    raise RuntimeError(f"unsafe Shelly power {p:.2f}W")
                sample = {
                    "t": now - start,
                    "p": p,
                    "light": r["physical_light"],
                    "fan": r["physical_fan"],
                    "hum": r["physical_hum"],
                }
                powers.append(sample)
                print("FAN30_POWER " + json.dumps(sample, sort_keys=True, separators=(",", ":")), flush=True)
                next_power = time.monotonic() + 10.0
            if now >= next_heartbeat:
                print(f"FAN30_HEARTBEAT elapsed_s={now-start:.1f} records={len(records)} powers={len(powers)}", flush=True)
                next_heartbeat = now + 30.0
    finally:
        handle.close()

    if len(records) < 120:
        raise RuntimeError(f"insufficient telemetry records={len(records)}")
    first, last = records[0], records[-1]
    fresh = [r for r in records if r["xiaomi_sample"] and r["xiaomi_age"] <= 30000]
    post120_req = [r for r in records if r["uptime"] >= 120000 and r["requested_fan"] >= 0.10 and not r["thermal"] and not r["force_fan"]]
    fan_on = [r for r in records if r["physical_fan"] == 1]
    first_fan_on = next((r for r in records if r["physical_fan"] == 1), None)
    fan_power = [x["p"] for x in powers if x["light"] == 1 and x["fan"] == 1 and x["hum"] == 0]
    off_power = [x["p"] for x in powers if x["light"] == 1 and x["fan"] == 0 and x["hum"] == 0]
    fan_delta = None
    if fan_power and off_power:
        fan_delta = statistics.median(fan_power) - statistics.median(off_power)
    elif fan_power:
        fan_delta = statistics.median(fan_power) - float(state["lamp_baseline_w"])
    on_ah = [(r["t"], r["inside_ah"]) for r in records if r["physical_fan"] == 1 and r["tp_sample"]]
    off_ah = [(r["t"], r["inside_ah"]) for r in records if r["physical_fan"] == 0 and r["tp_sample"]]
    summary = {
        "sha": EXPECTED,
        "records": len(records),
        "duration_s": OBSERVE_S,
        "lamp_baseline_w": state["lamp_baseline_w"],
        "max_requested_fan": max(r["requested_fan"] for r in records),
        "post120_requested_fan_ge_010": len(post120_req),
        "fan_on_records": len(fan_on),
        "first_fan_on_uptime_ms": first_fan_on["uptime"] if first_fan_on else None,
        "arbiter_transitions_max": max(r["transitions"] for r in records),
        "arbiter_dwell_holds_max": max(r["dwell"] for r in records),
        "fan_power_samples": len(fan_power),
        "fan_off_power_samples": len(off_power),
        "fan_power_delta_w": fan_delta,
        "inside_ah_fan_on_slope_gm3_min": linear_slope_per_min(on_ah),
        "inside_ah_fan_off_slope_gm3_min": linear_slope_per_min(off_ah),
        "fresh_xiaomi_records": len(fresh),
        "max_xiaomi_age_ms": max((r["xiaomi_age"] for r in records if r["xiaomi_sample"]), default=None),
        "xiaomi_packet_delta": max(0, last["xiaomi_packets"] - first["xiaomi_packets"]),
        "xiaomi_accepted_delta": max(0, last["xiaomi_accepted"] - first["xiaomi_accepted"]),
        "xiaomi_rejected_delta": max(0, last["xiaomi_rejected"] - first["xiaomi_rejected"]),
        "ble_scan_errors_max": max(r["ble_scan_errors"] for r in records),
        "ble_lock_drops_max": max(r["ble_lock_drops"] for r in records),
        "thermal_seen": thermal_seen,
        "tx_errors_max": tx_errors_max,
        "first_tp": [first["tp_t"], first["tp_rh"]],
        "last_tp": [last["tp_t"], last["tp_rh"]],
        "first_xiaomi": [first["xiaomi_t"], first["xiaomi_rh"]],
        "last_xiaomi": [last["xiaomi_t"], last["xiaomi_rh"]],
    }
    print("FAN30_SUMMARY " + json.dumps(summary, sort_keys=True, separators=(",", ":")), flush=True)
    state["thermal_seen"] = thermal_seen
    if thermal_seen:
        raise RuntimeError("thermal safety activated; fan policy diagnostic is confounded")
    if len(fresh) < int(len(records) * 0.8):
        raise RuntimeError("Xiaomi freshness below 80%")
    if tx_errors_max != 0:
        raise RuntimeError(f"RF tx errors observed: {tx_errors_max}")
    if not post120_req:
        raise RuntimeError("no requested_fan >=0.10 after 120s dwell window")
    if not fan_on:
        raise RuntimeError("physical fan never turned ON")
    if first_fan_on is not None and first_fan_on["uptime"] < 115000:
        raise RuntimeError(f"fan turned on before expected min-off dwell: {first_fan_on['uptime']}ms")
    if max(r["transitions"] for r in records) < 1:
        raise RuntimeError("arbiter transition not observed")
    if fan_delta is None or not (0.8 <= fan_delta <= 7.0):
        raise RuntimeError(f"Shelly fan power signature not confirmed: delta={fan_delta}")
    print("FAN30_REAL_CLOSED_LOOP_PASS fan_on=1 shelly_signature=1 lamp_stayed_on=1", flush=True)
    return summary


def safe_return(state: dict, active_flash_attempted: bool) -> None:
    if active_flash_attempted:
        flash(False, SAFE_BUILD)
    handle = open_console(14.0)
    try:
        status_text = send(handle, "status", 4.0)
        if f"status firmware_sha={EXPECTED}" not in status_text:
            raise RuntimeError("safe return exact SHA not confirmed")
        if "outputs=fake-locked" not in status_text or "rf_ready=1" not in status_text:
            raise RuntimeError("safe return is not fake-locked/rf-ready")
        if state.get("rtc_changed"):
            elapsed = max(0, int(round(time.monotonic() - float(state["original_monotonic"]))))
            restore_epoch = int(state["original_epoch"]) + elapsed
            set_start = time.monotonic()
            restore_text = send(handle, f"rtc set-unix {restore_epoch}", 4.0)
            if "rtc_set_utc ok=1" not in restore_text:
                raise RuntimeError("RTC restore write/readback failed")
            verify_text = send(handle, "sensors", 4.0)
            restored_epoch = parse_rtc_epoch(verify_text)
            expected_now = restore_epoch + int(round(time.monotonic() - set_start))
            delta = abs(restored_epoch - expected_now)
            if delta > 8:
                raise RuntimeError(f"RTC restore verification delta too large: {delta}s")
            print("FAN30_RTC_RESTORE_PASS " + json.dumps({"restore_requested_epoch": restore_epoch, "restored_epoch": restored_epoch, "verification_delta_s": delta}, sort_keys=True, separators=(",", ":")), flush=True)
        probe = collect(handle, 12.0)
        tp_t = latest_tp_from_text(probe)
        keep_fan_on = bool(state.get("thermal_seen")) or tp_t is None or tp_t >= 28.0
        manual_rf(handle, "on", "on" if keep_fan_on else "off", "off")
        time.sleep(12.0)
        final_power = median_power()
        if not (60.0 <= final_power <= 130.0):
            raise RuntimeError(f"final lamp-on power signature unexpected: {final_power:.2f}W")
        print("FAN30_SAFE_RETURN " + json.dumps({"sha": EXPECTED, "outputs": "fake-locked", "port": PORT, "shelly_master": "on", "lamp": "on", "fan": "on" if keep_fan_on else "off", "humidifier": "off", "tp_t": tp_t, "power_w": final_power}, sort_keys=True, separators=(",", ":")), flush=True)
        if keep_fan_on:
            raise RuntimeError("fan intentionally left ON because final thermal state was not proven safe")
    finally:
        handle.close()


def main() -> None:
    run(["git", "fetch", "-q", "origin", BRANCH, "agent-control"])
    if output(["git", "rev-parse", "HEAD"]) != EXPECTED:
        raise RuntimeError("local HEAD differs from expected exact SHA")
    if output(["git", "rev-parse", f"origin/{BRANCH}"]) != EXPECTED:
        raise RuntimeError("remote work branch differs from expected exact SHA")
    if output(["git", "status", "--porcelain"]):
        raise RuntimeError("workspace is dirty")
    if PORT != "/dev/cu.usbserial-1130":
        raise RuntimeError("fixed serial-port invariant violated")

    print("FAN30_BUILD_START", flush=True)
    build(True, ACTIVE_BUILD)
    build(False, SAFE_BUILD)
    print("FAN30_BUILD_PASS", flush=True)

    state: dict = {}
    active_flash_attempted = False
    primary_error: BaseException | None = None
    cleanup_error: BaseException | None = None
    try:
        state = preflight_and_force_day()
        active_flash_attempted = True
        print("FAN30_ACTIVE_FLASH_START", flush=True)
        flash(True, ACTIVE_BUILD)
        print("FAN30_ACTIVE_FLASH_PASS", flush=True)
        monitor_active(state)
    except BaseException as exc:
        primary_error = exc
        print(f"FAN30_PRIMARY_ERROR {type(exc).__name__}: {exc}", flush=True)
    finally:
        if state:
            try:
                print("FAN30_SAFE_RETURN_START", flush=True)
                safe_return(state, active_flash_attempted)
                print("FAN30_SAFE_RETURN_PASS", flush=True)
            except BaseException as exc:
                cleanup_error = exc
                print(f"FAN30_SAFE_RETURN_ERROR {type(exc).__name__}: {exc}", flush=True)

    if cleanup_error is not None:
        if primary_error is not None:
            raise RuntimeError(f"test failed ({primary_error}); safe return also failed ({cleanup_error})") from cleanup_error
        raise cleanup_error
    if primary_error is not None:
        raise primary_error
    print("FAN30_COMPLETE pass=1 shelly_master_never_commanded=1 port=/dev/cu.usbserial-1130", flush=True)


if __name__ == "__main__":
    main()
