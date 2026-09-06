from __future__ import annotations

import importlib.util
import json
import math
import os
import re
import statistics
import subprocess
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

EXPECTED = "dfc6dc86a47ad2158e36bb0d5241b0153dbce387"
BRANCH = "mvp/environment-controller"
PORT = "/dev/cu.usbserial-1130"
ACTIVE_BUILD = "build/idf-ah-arbiter-clean-v2-active"
SAFE_BUILD = "build/idf-ah-arbiter-clean-v2-safe"
WARSAW = ZoneInfo("Europe/Warsaw")
UTC = ZoneInfo("UTC")
BASE_PATH = "/tmp/growbox-fan30-base.py"
STARTUP_MAX_S = 1050.0
CLEAN_MAX_S = 300.0
AH_WINDOW_MAX_S = 900.0
POST_FAN_S = 180.0

spec = importlib.util.spec_from_file_location("fan30_base", BASE_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError("unable to load proven fan30 base harness")
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)


def out(cmd: list[str]) -> str:
    return subprocess.check_output(cmd, text=True).strip()


def run(cmd: list[str], *, env: dict[str, str] | None = None) -> None:
    subprocess.run(cmd, check=True, env=env)


def fw_env(real_outputs: bool, build_dir: str, storage_enabled: bool) -> dict[str, str]:
    env = base.firmware_env(real_outputs, build_dir)
    env["GROWBOX_STAGE27_SD_ENABLED"] = "1" if storage_enabled else "0"
    env["GROWBOX_STAGE27_FLASH_FALLBACK_ENABLED"] = "1" if storage_enabled else "0"
    env["PORT"] = PORT
    return env


def build_checked(real_outputs: bool, build_dir: str, storage_enabled: bool) -> None:
    env = fw_env(real_outputs, build_dir, storage_enabled)
    run(["bash", "scripts/stage27c_crowpanel.sh", "build"], env=env)
    cache = Path(build_dir, "CMakeCache.txt").read_text(errors="replace")
    want_real = "1" if real_outputs else "0"
    want_storage = "1" if storage_enabled else "0"
    required = [
        f"GROWBOX_STAGE28_REAL_OUTPUTS_ENABLED:STRING={want_real}",
        "GROWBOX_STAGE28_THERMAL_TEST_SEQUENCE_ENABLED:STRING=0",
        "GROWBOX_RF433_LOOPBACK_ENABLED:STRING=1",
        "GROWBOX_RF433_LOOPBACK_AUTO_SMOKE:STRING=0",
        f"GROWBOX_STAGE27_SD_ENABLED:STRING={want_storage}",
        f"GROWBOX_STAGE27_FLASH_FALLBACK_ENABLED:STRING={want_storage}",
    ]
    missing = [item for item in required if item not in cache]
    if missing:
        raise RuntimeError(f"build cache mismatch {build_dir}: {missing}")
    print(f"AHV2_BUILD_PASS real={want_real} storage={want_storage} dir={build_dir}", flush=True)


def flash(real_outputs: bool, build_dir: str, storage_enabled: bool) -> None:
    run(["bash", "scripts/stage27c_crowpanel.sh", "flash"], env=fw_env(real_outputs, build_dir, storage_enabled))


def choose_day_epoch(original_epoch: int) -> tuple[int, str]:
    local = datetime.fromtimestamp(original_epoch, tz=UTC).astimezone(WARSAW)
    if 6 <= local.hour < 22:
        test_local = local.replace(hour=12, minute=0, second=0, microsecond=0)
    elif local.hour >= 22:
        test_local = local.replace(hour=12, minute=0, second=0, microsecond=0)
    else:
        test_local = (local - timedelta(days=1)).replace(hour=12, minute=0, second=0, microsecond=0)
    return int(test_local.astimezone(UTC).timestamp()), test_local.isoformat()


def latest_line(text: str, marker: str) -> str | None:
    found = None
    for line in text.splitlines():
        if marker in line:
            found = line.strip()
    return found


def f(line: str, key: str, cast, default):
    return base.field(line, key, cast, default)


def parse_stage(text: str) -> dict | None:
    line = latest_line(text, "stage28d_output ")
    if line is None:
        return None
    return {
        "real": f(line, "real", int, -1),
        "light": f(line, "lamp_on", int, -1),
        "fan": f(line, "fan_on", int, -1),
        "hum": f(line, "humidifier_on", int, -1),
        "safety": f(line, "safety_latched", int, -1),
        "force": f(line, "force_fan", int, -1),
        "reason": f(line, "safety_reason", int, -1),
        "req_fan": f(line, "requested_fan", float, float("nan")),
        "req_hum": f(line, "requested_humidifier", float, float("nan")),
        "applied_fan": f(line, "applied_fan", float, float("nan")),
        "transitions": f(line, "arbiter_transitions", int, -1),
        "dwell": f(line, "arbiter_dwell_holds", int, -1),
        "overrides": f(line, "arbiter_safety_overrides", int, -1),
        "tx": f(line, "tx", int, -1),
        "tx_errors": f(line, "tx_errors", int, -1),
        "line": line,
    }


def parse_sensor_line(text: str, name: str) -> dict | None:
    line = latest_line(text, f"  {name} ")
    if line is None or "valid=0" in line:
        return None
    return {
        "temp": f(line, "temp_c", float, float("nan")),
        "rh": f(line, "rh_pct", float, float("nan")),
        "age": f(line, "age_ms", int, 999999999),
        "line": line,
    }


def snapshot(handle) -> dict:
    # 10 s telemetry cadence; collect long enough to guarantee a fresh stage28d line,
    # then ask sensors for exact current BLE values.
    text = base.collect(handle, 10.8)
    stage = parse_stage(text)
    sensor_text = base.send(handle, "sensors", 2.5)
    if stage is None:
        stage = parse_stage(sensor_text)
    if stage is None:
        extra = base.collect(handle, 10.8)
        stage = parse_stage(extra)
        text += extra
    if stage is None:
        raise RuntimeError("no stage28d_output telemetry")
    tp = parse_sensor_line(sensor_text, "tp357")
    xi = parse_sensor_line(sensor_text, "xiaomi")
    if tp is None or xi is None:
        raise RuntimeError("TP357/Xiaomi sample unavailable")
    inside_ah = base.absolute_humidity(tp["temp"], tp["rh"])
    intake_ah = base.absolute_humidity(xi["temp"], xi["rh"])
    if not (math.isfinite(inside_ah) and math.isfinite(intake_ah)):
        raise RuntimeError("non-finite AH")
    stage.update({
        "tp_t": tp["temp"], "tp_rh": tp["rh"], "tp_age": tp["age"],
        "xi_t": xi["temp"], "xi_rh": xi["rh"], "xi_age": xi["age"],
        "inside_ah": inside_ah, "intake_ah": intake_ah, "ah_gap": inside_ah - intake_ah,
    })
    if stage["real"] != 1:
        raise RuntimeError("automatic outputs left real-bounded mode")
    if stage["tx_errors"] != 0:
        raise RuntimeError(f"RF tx error count={stage['tx_errors']}")
    if tp["age"] > 30000 or xi["age"] > 30000:
        raise RuntimeError("BLE sample stale >30s")
    if tp["temp"] >= 31.0:
        raise RuntimeError(f"authoritative TP357 unsafe {tp['temp']:.2f}C")
    return stage


def power_sample() -> float:
    status = base.shelly_status()
    if not bool(status.get("output", False)):
        raise RuntimeError("Shelly master unexpectedly OFF")
    p = float(status.get("apower", 0.0))
    if p > 135.0:
        raise RuntimeError(f"unexpected Shelly power {p:.2f}W")
    return p


def print_snap(tag: str, s: dict) -> None:
    data = {k: v for k, v in s.items() if k != "line"}
    data["power_w"] = power_sample()
    print(tag + " " + json.dumps(data, sort_keys=True, separators=(",", ":")), flush=True)


def restore(state: dict) -> None:
    print("AHV2_RECOVERY_BEGIN", flush=True)
    try:
        flash(False, SAFE_BUILD, True)
    except Exception as exc:
        print(f"AHV2_RECOVERY_SAFE_FLASH_RETRY error={exc!r}", flush=True)
        time.sleep(3.0)
        flash(False, SAFE_BUILD, True)
    handle = base.open_console(14.0)
    try:
        status = base.send(handle, "status", 4.0)
        if f"status firmware_sha={EXPECTED}" not in status or "outputs=fake-locked" not in status or "rf_ready=1" not in status:
            raise RuntimeError("safe return exact SHA/fake-locked/rf-ready not confirmed")
        if state.get("rtc_changed"):
            elapsed = max(0, int(round(time.monotonic() - float(state["original_monotonic"]))))
            restore_epoch = int(state["original_epoch"]) + elapsed
            set_started = time.monotonic()
            response = base.send(handle, f"rtc set-unix {restore_epoch}", 4.0)
            if "rtc_set_utc ok=1" not in response:
                raise RuntimeError("RTC restore failed")
            verify = base.send(handle, "sensors", 4.0)
            restored = base.parse_rtc_epoch(verify)
            expected_now = restore_epoch + int(round(time.monotonic() - set_started))
            delta = abs(restored - expected_now)
            if delta > 8:
                raise RuntimeError(f"RTC restore delta {delta}s")
            print(f"AHV2_RTC_RESTORE_PASS restored={restored} delta_s={delta}", flush=True)
        base.manual_rf(handle, "on", "off", "off")
    finally:
        handle.close()
    time.sleep(10.0)
    final_power = base.median_power(n=7, delay=0.35)
    if not (50.0 <= final_power <= 90.0):
        raise RuntimeError(f"final lamp-on power outside expected cluster {final_power:.2f}W")
    print(f"AHV2_RECOVERY_PASS sha={EXPECTED} outputs=fake-locked lamp=on fan=off humidifier=off shelly_master=on power_w={final_power:.3f} port={PORT}", flush=True)


def main() -> None:
    state: dict = {"active_flashed": False, "rtc_changed": False}
    success = False
    primary_error: BaseException | None = None
    try:
        run(["git", "fetch", "-q", "origin", BRANCH, "agent-control"])
        if out(["git", "rev-parse", "HEAD"]) != EXPECTED:
            raise RuntimeError("local HEAD differs from exact expected SHA")
        if out(["git", "rev-parse", f"origin/{BRANCH}"]) != EXPECTED:
            raise RuntimeError("remote work branch differs from exact expected SHA")
        if out(["git", "status", "--porcelain"]):
            raise RuntimeError("workspace not clean")
        if PORT != "/dev/cu.usbserial-1130":
            raise RuntimeError("fixed-port invariant violated")
        if not bool(base.shelly_status().get("output", False)):
            raise RuntimeError("Shelly master OFF before test; refusing to change it")

        safe = base.open_console(14.0)
        try:
            status = base.send(safe, "status", 4.0)
            if f"status firmware_sha={EXPECTED}" not in status or "outputs=fake-locked" not in status or "rf_ready=1" not in status:
                raise RuntimeError("preflight firmware not exact safe fake-locked image")
            sensors = base.send(safe, "sensors", 4.0)
            original_epoch = base.parse_rtc_epoch(sensors)
            state["original_epoch"] = original_epoch
            state["original_monotonic"] = time.monotonic()
            state["original_local"] = datetime.fromtimestamp(original_epoch, tz=UTC).astimezone(WARSAW).isoformat()
            state["safe_power_before_w"] = base.median_power(n=7, delay=0.35)
            print("AHV2_PREFLIGHT_PASS " + json.dumps(state, sort_keys=True, separators=(",", ":")), flush=True)
        finally:
            safe.close()

        # Build BOTH images while hardware remains in the known safe image. Recovery image is ready before active flash.
        build_checked(True, ACTIVE_BUILD, False)
        build_checked(False, SAFE_BUILD, True)

        flash(True, ACTIVE_BUILD, False)
        state["active_flashed"] = True
        handle = base.open_console(16.0)
        try:
            status = base.send(handle, "status", 4.0)
            if f"status firmware_sha={EXPECTED}" not in status or "outputs=real-bounded" not in status or "rf_ready=1" not in status:
                raise RuntimeError("active image exact SHA/real-bounded/rf-ready not confirmed")
            test_epoch, test_local = choose_day_epoch(int(state["original_epoch"]))
            response = base.send(handle, f"rtc set-unix {test_epoch}", 4.0)
            if "rtc_set_utc ok=1" not in response:
                raise RuntimeError("failed to force bounded daytime RTC")
            state["rtc_changed"] = True
            state["test_epoch"] = test_epoch
            state["test_local"] = test_local
            print(f"AHV2_ACTIVE_PASS forced_day={test_local} storage=off", flush=True)

            # Phase A: explicitly observe startup safety and wait for the 10-minute RecoveryHold to clear.
            startup_start = time.monotonic()
            saw_recovery_hold = False
            safety_clear: dict | None = None
            while time.monotonic() - startup_start < STARTUP_MAX_S:
                s = snapshot(handle)
                print_snap("AHV2_STARTUP", s)
                if s["reason"] == 4 and s["safety"] == 1 and s["force"] == 1:
                    saw_recovery_hold = True
                if s["safety"] == 0 and s["force"] == 0:
                    safety_clear = s
                    break
            if safety_clear is None:
                raise RuntimeError("startup safety did not clear within bounded window")
            if not saw_recovery_hold:
                raise RuntimeError("expected startup RecoveryHold was not observed")
            print_snap("AHV2_SAFETY_CLEAR_PASS", safety_clear)

            # Phase B: require a clean controller-owned baseline: day lamp ON, fan OFF, humidifier OFF, no safety.
            clean_start = time.monotonic()
            clean: dict | None = None
            while time.monotonic() - clean_start < CLEAN_MAX_S:
                s = snapshot(handle)
                print_snap("AHV2_CLEAN_WAIT", s)
                if s["safety"] == 0 and s["force"] == 0 and s["light"] == 1 and s["fan"] == 0 and s["hum"] == 0:
                    clean = s
                    break
            if clean is None:
                raise RuntimeError("no clean day baseline (lamp ON/fan OFF/humidifier OFF) after safety release")
            clean_time = time.monotonic()
            clean_transition_count = int(clean["transitions"])
            clean_power = base.median_power(n=9, delay=0.3)
            print("AHV2_CLEAN_BASELINE_PASS " + json.dumps({
                "power_w": clean_power,
                "req_fan": clean["req_fan"],
                "inside_ah": clean["inside_ah"],
                "intake_ah": clean["intake_ah"],
                "ah_gap": clean["ah_gap"],
                "transitions": clean_transition_count,
            }, sort_keys=True, separators=(",", ":")), flush=True)

            # Phase C: do not touch RF manually. Observe natural controller dynamics until AH policy requests fan >=0.10.
            # The controller's own humidifier is allowed to cycle; success requires the eventual fan transition while safety=0.
            window_start = time.monotonic()
            sustained_started: float | None = None
            request_evidence: dict | None = None
            fan_on: dict | None = None
            while time.monotonic() - window_start < AH_WINDOW_MAX_S:
                s = snapshot(handle)
                print_snap("AHV2_AH_WINDOW", s)
                if s["safety"] or s["force"]:
                    sustained_started = None
                    continue
                if s["req_fan"] >= 0.10:
                    if sustained_started is None:
                        sustained_started = time.monotonic()
                        request_evidence = dict(s)
                        request_evidence["seconds_since_clean"] = sustained_started - clean_time
                        print_snap("AHV2_AH_REQUEST_GE_010", request_evidence)
                else:
                    sustained_started = None
                    request_evidence = None
                if s["fan"] == 1 and s["applied_fan"] >= 0.99 and s["req_fan"] >= 0.10 and s["safety"] == 0 and s["force"] == 0:
                    if int(s["transitions"]) <= clean_transition_count:
                        raise RuntimeError("fan ON observed without arbiter transition increment")
                    fan_on = s
                    break
                if sustained_started is not None:
                    # If request remains above threshold beyond a conservative 150 s from clean/off baseline,
                    # the 120 s minimum-OFF dwell must have expired.
                    if time.monotonic() - clean_time > 150.0 and time.monotonic() - sustained_started > 35.0:
                        raise RuntimeError("sustained req_fan>=0.10 after min-OFF expiry but fan did not transition ON")
            if fan_on is None:
                if request_evidence is None:
                    raise RuntimeError("INCONCLUSIVE: environment did not rebuild AH fan request >=0.10 in bounded window")
                raise RuntimeError("AH request evidence seen but no non-safety fan ON transition")

            # Physical confirmation after controller transition. Wait for humidifier OFF so power signature is interpretable.
            post_start = time.monotonic()
            clean_fan_power: float | None = None
            post_records: list[dict] = []
            while time.monotonic() - post_start < POST_FAN_S:
                s = snapshot(handle)
                post_records.append(s)
                print_snap("AHV2_POST_FAN", s)
                if s["safety"] == 0 and s["force"] == 0 and s["fan"] == 1 and s["light"] == 1 and s["hum"] == 0:
                    clean_fan_power = base.median_power(n=9, delay=0.3)
                    break
            if clean_fan_power is None:
                raise RuntimeError("fan transitioned but no clean lamp+fan/humidifier-OFF power window")
            power_delta = clean_fan_power - clean_power
            if not (1.2 <= power_delta <= 8.0):
                raise RuntimeError(f"physical fan power signature mismatch delta={power_delta:.3f}W")

            ah_points = []
            t0 = time.monotonic()
            for s in post_records:
                # post_records are ~13s apart; relative order is sufficient for a conservative slope estimate.
                ah_points.append((float(len(ah_points)) * 13.0, float(s["inside_ah"])))
            ah_slope = base.linear_slope_per_min(ah_points) if len(ah_points) >= 5 else None
            result = {
                "sha": EXPECTED,
                "port": PORT,
                "clean_power_w": clean_power,
                "fan_power_w": clean_fan_power,
                "fan_power_delta_w": power_delta,
                "request_at_transition": fan_on["req_fan"],
                "ah_gap_at_transition": fan_on["ah_gap"],
                "arbiter_transitions_before": clean_transition_count,
                "arbiter_transitions_after": fan_on["transitions"],
                "safety": fan_on["safety"],
                "force_fan": fan_on["force"],
                "tx_errors": fan_on["tx_errors"],
                "ah_slope_post_fan_g_m3_min": ah_slope,
            }
            print("AHV2_CONTROLLER_PATH_PASS " + json.dumps(result, sort_keys=True, separators=(",", ":")), flush=True)
            success = True
        finally:
            handle.close()
    except BaseException as exc:
        primary_error = exc
        print(f"AHV2_PRIMARY_ERROR type={type(exc).__name__} detail={exc}", flush=True)
    finally:
        if state.get("active_flashed"):
            try:
                restore(state)
            except BaseException as recovery_exc:
                print(f"AHV2_RECOVERY_ERROR type={type(recovery_exc).__name__} detail={recovery_exc}", flush=True)
                if primary_error is None:
                    primary_error = recovery_exc
                else:
                    primary_error = RuntimeError(f"primary={primary_error}; recovery={recovery_exc}")
        if primary_error is not None:
            raise primary_error
        if not success:
            raise RuntimeError("test ended without PASS marker")
        print("AHV2_FINAL_PASS controller_ah_to_arbiter_to_rf_to_physical_fan=1 safe_return=1 shelly_master=on", flush=True)


if __name__ == "__main__":
    main()
