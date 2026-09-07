#!/usr/bin/env python3
"""Interactive bounded Stage28E Phase H v4 physical observation.

The script never injects a controller request and never writes actuator commands.
It waits for a clean open-tent baseline, notifies the local Mac to close the tent,
then observes the natural controller -> arbiter -> RF -> physical fan path and
collects environmental response evidence for shadow/research analysis.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import statistics
import subprocess
import time
import urllib.request
from collections import deque
from dataclasses import dataclass
from typing import Optional

import serial

KV_RE = re.compile(r"([A-Za-z0-9_]+)=([^ ]+)")
SHELLY_URL = "http://192.168.0.16/rpc/Switch.GetStatus?id=0"


@dataclass
class EnvSample:
    t: float
    tp_t: float
    tp_rh: float
    xm_t: float
    xm_rh: float
    scd_t: float
    scd_rh: float
    co2: float


def shelly_status() -> tuple[bool | None, float | None, float | None, float | None]:
    try:
        with urllib.request.urlopen(SHELLY_URL, timeout=3) as response:
            payload = json.load(response)
        return (
            bool(payload.get("output", False)),
            float(payload.get("apower", 0.0)),
            float(payload.get("voltage", 0.0)),
            float(payload.get("current", 0.0)),
        )
    except Exception:
        return None, None, None, None


def open_serial(port: str) -> serial.Serial:
    handle = serial.Serial(port=None, baudrate=115200, timeout=0.1, write_timeout=1)
    handle.dtr = False
    handle.rts = False
    handle.port = port
    handle.open()
    return handle


def send(handle: serial.Serial, command: str) -> None:
    handle.write((command + "\n").encode())
    handle.flush()


def notify_close_tent() -> None:
    script = 'display notification "Clean Phase H baseline is ready. Close the grow tent now." with title "Growbox H v4"'
    try:
        subprocess.run(["osascript", "-e", script], check=False, timeout=5)
    except Exception:
        pass
    try:
        subprocess.run(["say", "Growbox baseline ready. Close the grow tent now."], check=False, timeout=10)
    except Exception:
        pass


def absolute_humidity_g_m3(temp_c: float, rh_pct: float) -> float:
    saturation_hpa = 6.112 * math.exp((17.67 * temp_c) / (temp_c + 243.5))
    vapor_hpa = saturation_hpa * rh_pct / 100.0
    return 216.7 * vapor_hpa / (273.15 + temp_c)


def slope_per_min(samples: list[tuple[float, float]]) -> Optional[float]:
    if len(samples) < 4:
        return None
    t0 = samples[0][0]
    xs = [(t - t0) / 60.0 for t, _ in samples]
    ys = [v for _, v in samples]
    mean_x = statistics.fmean(xs)
    mean_y = statistics.fmean(ys)
    denom = sum((x - mean_x) ** 2 for x in xs)
    if denom <= 0:
        return None
    return sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / denom


def fmt(value: Optional[float], digits: int = 3) -> str:
    return "na" if value is None else f"{value:.{digits}f}"


def parse_env(line: str, now: float) -> Optional[EnvSample]:
    if "soak_v=2" not in line:
        return None
    values = dict(KV_RE.findall(line))
    try:
        if values.get("tp_sample") != "1" or values.get("xiaomi_sample") != "1" or values.get("scd_sample") != "1":
            return None
        return EnvSample(
            t=now,
            tp_t=float(values["tp_t"]),
            tp_rh=float(values["tp_rh"]),
            xm_t=float(values["xiaomi_t"]),
            xm_rh=float(values["xiaomi_rh"]),
            scd_t=float(values["scd_t"]),
            scd_rh=float(values["scd_rh"]),
            co2=float(values["scd_co2"]),
        )
    except (KeyError, TypeError, ValueError):
        return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", required=True)
    parser.add_argument("--sha", required=True)
    parser.add_argument("--timeout", type=float, default=1500.0)
    parser.add_argument("--post-seconds", type=float, default=300.0)
    args = parser.parse_args()
    if args.port != "/dev/cu.usbserial-1130":
        raise SystemExit("refusing non-Growbox serial port")

    start = time.monotonic()
    deadline = start + args.timeout
    handle = open_serial(args.port)
    opened = time.monotonic()
    baseline_status = None
    last_status_send = 0.0
    bad_after: list[str] = []
    clean_candidates: deque[tuple[float, dict[str, str]]] = deque(maxlen=4)
    clean_baseline: Optional[tuple[float, dict[str, str]]] = None
    close_notified_at: Optional[float] = None
    first_request: Optional[tuple[float, dict[str, str]]] = None
    transition: Optional[tuple[float, dict[str, str]]] = None
    transition_time: Optional[float] = None
    last_output: Optional[dict[str, str]] = None
    lamp_off_before_fan = False
    env_samples: list[EnvSample] = []
    shelly_before: list[float] = []
    shelly_after: list[float] = []
    shelly_voltage: list[float] = []
    shelly_last_poll = 0.0

    try:
        while time.monotonic() < deadline:
            now = time.monotonic()
            raw = handle.readline()
            if raw:
                line = raw.decode(errors="replace").strip()
                print(line, flush=True)

                if baseline_status is not None and (
                    "ESP-ROM:esp32s3-" in line or "stage28e_runtime_lifecycle entry_count=" in line
                ):
                    bad_after.append(line)

                if line.startswith("status firmware_sha="):
                    values = dict(KV_RE.findall(line))
                    if (
                        values.get("firmware_sha") == args.sha
                        and values.get("outputs") == "real-bounded"
                        and values.get("rf_ready") == "1"
                        and int(values.get("uptime_ms", "0")) >= 5000
                    ):
                        if baseline_status is None:
                            baseline_status = values
                            print(
                                "STAGE28E_H_V4_RUNTIME_BASELINE "
                                f"boot_id={values.get('boot_id')} reset_reason={values.get('reset_reason')} "
                                f"uptime_ms={values.get('uptime_ms')} internal_free={values.get('internal_free')} "
                                f"internal_min={values.get('internal_min')} internal_largest={values.get('internal_largest')}",
                                flush=True,
                            )
                        elif values.get("boot_id") != baseline_status.get("boot_id"):
                            bad_after.append("boot_id_changed")

                env = parse_env(line, now)
                if env is not None:
                    env_samples.append(env)
                    if env.tp_t >= 27.5:
                        print(f"STAGE28E_H_V4_TEMPERATURE_GUARD tp_t={env.tp_t:.2f}", flush=True)
                        return 42

                if line.startswith("stage28d_output ") and baseline_status is not None:
                    values = dict(KV_RE.findall(line))
                    last_output = values
                    try:
                        request = float(values.get("requested_fan", "0"))
                        fan_on = int(values.get("fan_on", "0"))
                        applied = float(values.get("applied_fan", "0"))
                        safety = int(values.get("safety_latched", "0"))
                        force = int(values.get("force_fan", "0"))
                        reason = int(values.get("safety_reason", "0"))
                        transitions = int(values.get("arbiter_transitions", "0"))
                        dwell = int(values.get("arbiter_dwell_holds", "0"))
                        tx_count = int(values.get("tx", "0"))
                        tx_errors = int(values.get("tx_errors", "0"))
                        lamp_on = int(values.get("lamp_on", "0"))
                    except (TypeError, ValueError):
                        continue

                    if clean_baseline is None:
                        if safety == 0 and force == 0 and reason == 0 and fan_on == 0 and applied < 0.01 and request < 0.10:
                            clean_candidates.append((now, values))
                        else:
                            clean_candidates.clear()
                        if len(clean_candidates) >= 3 and clean_candidates[-1][0] - clean_candidates[0][0] >= 10.0:
                            clean_baseline = clean_candidates[-1]
                            close_notified_at = now
                            on, power, voltage, current = shelly_status()
                            if on is not None and power is not None:
                                shelly_before.append(power)
                                if voltage is not None:
                                    shelly_voltage.append(voltage)
                            print(
                                "STAGE28E_H_V4_OPEN_BASELINE_READY "
                                f"requested_fan={request:.3f} fan_on={fan_on} applied_fan={applied:.3f} "
                                f"lamp_on={lamp_on} safety_latched={safety} force_fan={force} safety_reason={reason} "
                                f"transitions={transitions} dwell={dwell} tx={tx_count} tx_errors={tx_errors} "
                                f"shelly_w={fmt(power,2)}",
                                flush=True,
                            )
                            notify_close_tent()
                            print("STAGE28E_H_V4_USER_ACTION close_tent_now=1", flush=True)
                            continue

                    else:
                        if transition is None and lamp_on == 0 and safety == 0 and force == 0:
                            lamp_off_before_fan = True
                        if safety == 0 and force == 0 and reason == 0 and fan_on == 0 and request >= 0.10 and first_request is None:
                            first_request = (now, values)
                            print(
                                "STAGE28E_H_V4_REQUEST_SEEN "
                                f"seconds_after_close_notice={now - (close_notified_at or now):.1f} "
                                f"requested_fan={request:.3f} dwell={dwell} transitions={transitions} tx={tx_count}",
                                flush=True,
                            )
                        if first_request is not None and safety == 0 and force == 0 and reason == 0 and request >= 0.10 and fan_on == 1 and applied >= 0.99 and tx_errors == 0:
                            initial_transitions = int(first_request[1].get("arbiter_transitions", "0"))
                            initial_tx = int(first_request[1].get("tx", "0"))
                            if transitions > initial_transitions and tx_count > initial_tx:
                                transition = (now, values)
                                transition_time = now
                                print(
                                    "STAGE28E_H_V4_TRANSITION_SEEN "
                                    f"requested_fan={request:.3f} fan_on=1 applied_fan={applied:.3f} "
                                    f"dwell={dwell} transitions={transitions} tx={tx_count} tx_errors={tx_errors} "
                                    f"lamp_on={lamp_on}",
                                    flush=True,
                                )

            if now - opened >= 6.0 and now - last_status_send >= 20.0:
                try:
                    send(handle, "status")
                    send(handle, "sensors")
                except Exception:
                    pass
                last_status_send = now

            if clean_baseline is not None and now - shelly_last_poll >= 2.0:
                on, power, voltage, current = shelly_status()
                if on is not None and power is not None:
                    if not on:
                        raise AssertionError("Shelly master output turned off during H v4")
                    if transition_time is None:
                        shelly_before.append(power)
                    else:
                        shelly_after.append(power)
                    if voltage is not None:
                        shelly_voltage.append(voltage)
                shelly_last_poll = now

            if transition_time is not None and now - transition_time >= args.post_seconds:
                break

            time.sleep(0.01)

        assert baseline_status is not None, "no stabilized real-bounded runtime baseline"
        assert not bad_after, ("post-baseline reset/lifecycle marker", bad_after[-3:])
        assert clean_baseline is not None, "clean safety-clear fan-OFF open-tent baseline not observed"
        assert first_request is not None, "natural requested_fan>=0.10 not observed after close notification"
        assert transition is not None, "natural request did not complete normal fan OFF->ON transition"
        assert not lamp_off_before_fan, "lamp turned OFF before normal fan transition without safety"
        assert int(transition[1].get("tx_errors", "0")) == 0, transition[1]
        assert shelly_after, "no Shelly evidence after fan transition"

        request_time = first_request[0]
        before_power = [v for v in shelly_before[-8:]]
        after_power = shelly_after[:8]
        pre_median = statistics.median(before_power) if before_power else None
        post_median = statistics.median(after_power) if after_power else None
        power_delta = None if pre_median is None or post_median is None else post_median - pre_median
        if power_delta is not None:
            assert power_delta >= 1.0, ("Shelly power delta does not support fan ON", pre_median, post_median)

        pre_env = [s for s in env_samples if request_time - 180.0 <= s.t < request_time]
        post_env = [s for s in env_samples if transition_time is not None and transition_time + 30.0 <= s.t <= transition_time + args.post_seconds]

        pre_temp = slope_per_min([(s.t, s.tp_t) for s in pre_env])
        post_temp = slope_per_min([(s.t, s.tp_t) for s in post_env])
        pre_ah = slope_per_min([(s.t, absolute_humidity_g_m3(s.tp_t, s.tp_rh)) for s in pre_env])
        post_ah = slope_per_min([(s.t, absolute_humidity_g_m3(s.tp_t, s.tp_rh)) for s in post_env])
        pre_co2 = slope_per_min([(s.t, s.co2) for s in pre_env])
        post_co2 = slope_per_min([(s.t, s.co2) for s in post_env])

        latest = env_samples[-1] if env_samples else None
        print(
            "STAGE28E_H_V4_SHELLY "
            f"pre_median_w={fmt(pre_median,2)} post_median_w={fmt(post_median,2)} "
            f"delta_w={fmt(power_delta,2)} voltage_median={fmt(statistics.median(shelly_voltage) if shelly_voltage else None,2)}",
            flush=True,
        )
        print(
            "STAGE28E_H_V4_ENV_RESPONSE "
            f"pre_samples={len(pre_env)} post_samples={len(post_env)} "
            f"tp_temp_slope_pre_c_min={fmt(pre_temp)} tp_temp_slope_post_c_min={fmt(post_temp)} "
            f"ah_slope_pre_g_m3_min={fmt(pre_ah)} ah_slope_post_g_m3_min={fmt(post_ah)} "
            f"co2_slope_pre_ppm_min={fmt(pre_co2)} co2_slope_post_ppm_min={fmt(post_co2)} "
            f"latest_tp_t={fmt(latest.tp_t if latest else None,2)} latest_tp_rh={fmt(latest.tp_rh if latest else None,2)} "
            f"latest_xiaomi_t={fmt(latest.xm_t if latest else None,2)} latest_xiaomi_rh={fmt(latest.xm_rh if latest else None,2)} "
            f"latest_scd_co2={fmt(latest.co2 if latest else None,0)}",
            flush=True,
        )
        print("STAGE28E_H_V4_PHYSICAL_E2E_PASS", flush=True)
        return 0
    finally:
        handle.close()


if __name__ == "__main__":
    raise SystemExit(main())
