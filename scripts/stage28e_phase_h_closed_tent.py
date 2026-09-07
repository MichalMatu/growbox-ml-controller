#!/usr/bin/env python3
"""Autonomous closed-tent Stage28E Phase H physical observation.

The harness is observation-only with respect to the controller and actuators:
it never injects a controller request and never writes actuator commands.  It
starts with the grow tent already closed, establishes a stable safety-clear
physical fan-OFF baseline, then proves a natural controller -> arbiter -> RF ->
physical fan transition.  Shelly total-power evidence and environmental
response are collected as independent supporting evidence.

Recovery/final fake-locked handling deliberately remains outside this script
and must be performed by the bounded Local Agent task wrapper even when this
observer fails.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import statistics
import time
import urllib.request
from collections import deque
from dataclasses import dataclass
from typing import Optional

import serial

KV_RE = re.compile(r"([A-Za-z0-9_]+)=([^ ]+)")
SHELLY_URL = "http://192.168.0.16/rpc/Switch.GetStatus?id=0"
GROWBOX_PORT = "/dev/cu.usbserial-1130"
SHELLY_PROOF_SAMPLES = 8
STAGE28D_OUTPUT_MARKER = "stage28d_output "
LAMP_SAFETY_REASON_SAFE = 0
LAMP_SAFETY_REASON_TIMER_OFF = 1
H_SAFETY_CLEAR_REASONS = frozenset(
    (LAMP_SAFETY_REASON_SAFE, LAMP_SAFETY_REASON_TIMER_OFF)
)


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


def is_stage28d_output_line(line: str) -> bool:
    # ESP-IDF serial logs prefix ESP_LOG output with timestamp/tag metadata.
    # Accept both raw service-console-style payloads and prefixed log lines.
    return STAGE28D_OUTPUT_MARKER in line


def is_h_safety_clear(safety_latched: int, force_fan: int, reason: int) -> bool:
    # TimerOff is normal schedule state, not a thermal safety condition.
    return (
        safety_latched == 0
        and force_fan == 0
        and reason in H_SAFETY_CLEAR_REASONS
    )


def absolute_humidity_g_m3(temp_c: float, rh_pct: float) -> float:
    saturation_hpa = 6.112 * math.exp((17.67 * temp_c) / (temp_c + 243.5))
    vapor_hpa = saturation_hpa * rh_pct / 100.0
    return 216.7 * vapor_hpa / (273.15 + temp_c)


def slope_per_min(samples: list[tuple[float, float]]) -> Optional[float]:
    if len(samples) < 4:
        return None
    t0 = samples[0][0]
    xs = [(t - t0) / 60.0 for t, _ in samples]
    ys = [value for _, value in samples]
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
        if (
            values.get("tp_sample") != "1"
            or values.get("xiaomi_sample") != "1"
            or values.get("scd_sample") != "1"
        ):
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


def output_state(values: dict[str, str]) -> Optional[dict[str, float | int]]:
    try:
        return {
            "request": float(values.get("requested_fan", "0")),
            "fan_known": int(values.get("fan_known", "0")),
            "fan_on": int(values.get("fan_on", "0")),
            "applied": float(values.get("applied_fan", "0")),
            "safety": int(values.get("safety_latched", "0")),
            "force": int(values.get("force_fan", "0")),
            "reason": int(values.get("safety_reason", "0")),
            "transitions": int(values.get("arbiter_transitions", "0")),
            "dwell": int(values.get("arbiter_dwell_holds", "0")),
            "tx": int(values.get("tx", "0")),
            "tx_errors": int(values.get("tx_errors", "0")),
            "lamp_on": int(values.get("lamp_on", "0")),
            "humidifier_on": int(values.get("humidifier_on", "0")),
        }
    except (TypeError, ValueError):
        return None


def observe(args: argparse.Namespace) -> int:
    start = time.monotonic()
    deadline = start + args.timeout
    handle = open_serial(args.port)
    opened = time.monotonic()

    runtime_baseline: Optional[dict[str, str]] = None
    bad_after: list[str] = []
    clean_candidates: deque[tuple[float, dict[str, str]]] = deque(maxlen=4)
    off_baseline: Optional[tuple[float, dict[str, str]]] = None
    first_request: Optional[tuple[float, dict[str, str]]] = None
    transition: Optional[tuple[float, dict[str, str]]] = None
    transition_time: Optional[float] = None
    pre_load_state: Optional[tuple[int, int]] = None
    proof_load_state: Optional[tuple[int, int]] = None
    proof_power_sealed = False
    post_state_confirmations = 0

    env_samples: list[EnvSample] = []
    shelly_before: list[float] = []
    shelly_after: list[float] = []
    shelly_voltage: list[float] = []
    last_status_send = 0.0
    last_shelly_poll = 0.0

    print(
        "STAGE28E_H_CLOSED_START "
        f"closure_utc={args.closure_utc or 'unspecified'} "
        f"timeout_s={args.timeout:.0f} post_seconds={args.post_seconds:.0f}",
        flush=True,
    )

    try:
        while time.monotonic() < deadline:
            now = time.monotonic()
            raw = handle.readline()
            if raw:
                line = raw.decode(errors="replace").strip()
                print(line, flush=True)

                if runtime_baseline is not None and (
                    "ESP-ROM:esp32s3-" in line
                    or "stage28e_runtime_lifecycle entry_count=" in line
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
                        if runtime_baseline is None:
                            runtime_baseline = values
                            print(
                                "STAGE28E_H_CLOSED_RUNTIME_BASELINE "
                                f"boot_id={values.get('boot_id')} "
                                f"reset_reason={values.get('reset_reason')} "
                                f"uptime_ms={values.get('uptime_ms')} "
                                f"internal_free={values.get('internal_free')} "
                                f"internal_min={values.get('internal_min')} "
                                f"internal_largest={values.get('internal_largest')}",
                                flush=True,
                            )
                        elif values.get("boot_id") != runtime_baseline.get("boot_id"):
                            bad_after.append("boot_id_changed")

                env = parse_env(line, now)
                if env is not None:
                    env_samples.append(env)
                    if env.tp_t >= args.temperature_guard:
                        print(
                            "STAGE28E_H_CLOSED_TEMPERATURE_GUARD "
                            f"tp_t={env.tp_t:.2f} limit={args.temperature_guard:.2f}",
                            flush=True,
                        )
                        return 42

                if is_stage28d_output_line(line) and runtime_baseline is not None:
                    values = dict(KV_RE.findall(line))
                    state = output_state(values)
                    if state is None:
                        continue

                    request = float(state["request"])
                    fan_known = int(state["fan_known"])
                    fan_on = int(state["fan_on"])
                    applied = float(state["applied"])
                    safety = int(state["safety"])
                    force = int(state["force"])
                    reason = int(state["reason"])
                    transitions = int(state["transitions"])
                    dwell = int(state["dwell"])
                    tx_count = int(state["tx"])
                    tx_errors = int(state["tx_errors"])
                    lamp_on = int(state["lamp_on"])
                    humidifier_on = int(state["humidifier_on"])

                    if off_baseline is None:
                        clean = (
                            is_h_safety_clear(safety, force, reason)
                            and fan_known == 1
                            and fan_on == 0
                            and applied < 0.01
                            and tx_errors == 0
                        )
                        if clean:
                            clean_candidates.append((now, values))
                        else:
                            clean_candidates.clear()

                        if (
                            len(clean_candidates) >= 3
                            and clean_candidates[-1][0] - clean_candidates[0][0]
                            >= args.baseline_seconds
                        ):
                            off_baseline = clean_candidates[-1]
                            pre_load_state = (lamp_on, humidifier_on)
                            on, power, voltage, _ = shelly_status()
                            if on is not None and power is not None:
                                assert on, "Shelly master output OFF at closed-tent baseline"
                                shelly_before.append(power)
                                if voltage is not None:
                                    shelly_voltage.append(voltage)
                            print(
                                "STAGE28E_H_CLOSED_OFF_BASELINE_READY "
                                f"requested_fan={request:.3f} fan_known={fan_known} "
                                f"fan_on={fan_on} applied_fan={applied:.3f} "
                                f"lamp_on={lamp_on} humidifier_on={humidifier_on} "
                                f"safety_latched={safety} force_fan={force} "
                                f"safety_reason={reason} transitions={transitions} "
                                f"dwell={dwell} tx={tx_count} tx_errors={tx_errors} "
                                f"shelly_w={fmt(power, 2)}",
                                flush=True,
                            )
                            if request >= 0.10:
                                first_request = (now, values)
                                proof_load_state = (lamp_on, humidifier_on)
                                print(
                                    "STAGE28E_H_CLOSED_REQUEST_SEEN "
                                    "at_off_baseline=1 "
                                    f"requested_fan={request:.3f} dwell={dwell} "
                                    f"transitions={transitions} tx={tx_count}",
                                    flush=True,
                                )
                            continue

                    else:
                        load_state = (lamp_on, humidifier_on)
                        if proof_load_state is None:
                            if pre_load_state is None:
                                pre_load_state = load_state
                            elif load_state != pre_load_state:
                                shelly_before.clear()
                                pre_load_state = load_state
                        elif not proof_power_sealed and load_state != proof_load_state:
                            raise AssertionError(
                                "Shelly fan proof confounded by lamp/humidifier state change during proof window"
                            )
                        elif (
                            transition_time is not None
                            and not proof_power_sealed
                            and load_state == proof_load_state
                        ):
                            post_state_confirmations += 1

                        if (
                            first_request is None
                            and is_h_safety_clear(safety, force, reason)
                            and fan_known == 1
                            and fan_on == 0
                            and applied < 0.01
                            and request >= 0.10
                            and tx_errors == 0
                        ):
                            first_request = (now, values)
                            proof_load_state = load_state
                            print(
                                "STAGE28E_H_CLOSED_REQUEST_SEEN "
                                "at_off_baseline=0 "
                                f"requested_fan={request:.3f} dwell={dwell} "
                                f"transitions={transitions} tx={tx_count}",
                                flush=True,
                            )

                        if (
                            first_request is not None
                            and is_h_safety_clear(safety, force, reason)
                            and fan_known == 1
                            and request >= 0.10
                            and fan_on == 1
                            and applied >= 0.99
                            and tx_errors == 0
                        ):
                            request_values = first_request[1]
                            initial_transitions = int(
                                request_values.get("arbiter_transitions", "0")
                            )
                            initial_tx = int(request_values.get("tx", "0"))
                            if transitions > initial_transitions and tx_count > initial_tx:
                                if (
                                    values.get("lamp_on") != request_values.get("lamp_on")
                                    or values.get("humidifier_on")
                                    != request_values.get("humidifier_on")
                                ):
                                    raise AssertionError(
                                        "Shelly fan proof confounded by lamp/humidifier state change"
                                    )
                                transition = (now, values)
                                transition_time = now
                                print(
                                    "STAGE28E_H_CLOSED_TRANSITION_SEEN "
                                    f"requested_fan={request:.3f} fan_known={fan_known} "
                                    f"fan_on=1 applied_fan={applied:.3f} "
                                    f"dwell={dwell} transitions={transitions} "
                                    f"tx={tx_count} tx_errors={tx_errors} "
                                    f"lamp_on={lamp_on} humidifier_on={humidifier_on}",
                                    flush=True,
                                )

            if now - opened >= 6.0 and now - last_status_send >= 20.0:
                try:
                    send(handle, "status")
                    send(handle, "sensors")
                except Exception:
                    pass
                last_status_send = now

            if off_baseline is not None and now - last_shelly_poll >= args.shelly_poll_seconds:
                on, power, voltage, _ = shelly_status()
                if on is not None and power is not None:
                    if not on:
                        raise AssertionError(
                            "Shelly master output turned off during closed-tent H"
                        )
                    if transition_time is None:
                        shelly_before.append(power)
                    elif not proof_power_sealed:
                        shelly_after.append(power)
                        if (
                            len(shelly_after) >= SHELLY_PROOF_SAMPLES
                            and post_state_confirmations >= 1
                        ):
                            proof_power_sealed = True
                            print(
                                "STAGE28E_H_CLOSED_SHELLY_PROOF_WINDOW_SEALED "
                                f"samples={len(shelly_after)} confirmations={post_state_confirmations}",
                                flush=True,
                            )
                    if voltage is not None:
                        shelly_voltage.append(voltage)
                last_shelly_poll = now

            if transition_time is not None and now - transition_time >= args.post_seconds:
                break

            time.sleep(0.01)

        assert runtime_baseline is not None, "no stabilized real-bounded runtime baseline"
        assert not bad_after, ("post-baseline reset/lifecycle marker", bad_after[-3:])
        assert off_baseline is not None, (
            "stable safety-clear physical fan-OFF closed-tent baseline not observed"
        )
        assert first_request is not None, (
            "natural requested_fan>=0.10 not observed from physical fan-OFF state"
        )
        assert transition is not None, (
            "natural request did not complete normal physical fan OFF->ON transition"
        )
        assert transition_time is not None
        assert int(transition[1].get("tx_errors", "0")) == 0, transition[1]
        assert shelly_after, "no Shelly evidence after fan transition"
        assert proof_power_sealed, (
            "Shelly proof window did not complete with stable lamp/humidifier state",
            len(shelly_after),
            post_state_confirmations,
        )

        before_power = shelly_before[-SHELLY_PROOF_SAMPLES:]
        after_power = shelly_after[:SHELLY_PROOF_SAMPLES]
        pre_median = statistics.median(before_power) if before_power else None
        post_median = statistics.median(after_power) if after_power else None
        power_delta = (
            None
            if pre_median is None or post_median is None
            else post_median - pre_median
        )
        assert pre_median is not None, "no Shelly evidence before fan transition"
        assert power_delta is not None
        assert power_delta >= args.minimum_power_delta, (
            "Shelly power delta does not support fan ON",
            pre_median,
            post_median,
            power_delta,
        )

        request_time = first_request[0]
        pre_env = [
            sample
            for sample in env_samples
            if request_time - 180.0 <= sample.t < request_time
        ]
        post_env = [
            sample
            for sample in env_samples
            if transition_time + 30.0
            <= sample.t
            <= transition_time + args.post_seconds
        ]

        pre_temp = slope_per_min([(s.t, s.tp_t) for s in pre_env])
        post_temp = slope_per_min([(s.t, s.tp_t) for s in post_env])
        pre_ah = slope_per_min(
            [(s.t, absolute_humidity_g_m3(s.tp_t, s.tp_rh)) for s in pre_env]
        )
        post_ah = slope_per_min(
            [(s.t, absolute_humidity_g_m3(s.tp_t, s.tp_rh)) for s in post_env]
        )
        pre_co2 = slope_per_min([(s.t, s.co2) for s in pre_env])
        post_co2 = slope_per_min([(s.t, s.co2) for s in post_env])

        latest = env_samples[-1] if env_samples else None
        print(
            "STAGE28E_H_CLOSED_SHELLY "
            f"pre_median_w={fmt(pre_median, 2)} "
            f"post_median_w={fmt(post_median, 2)} "
            f"delta_w={fmt(power_delta, 2)} "
            f"voltage_median={fmt(statistics.median(shelly_voltage) if shelly_voltage else None, 2)}",
            flush=True,
        )
        print(
            "STAGE28E_H_CLOSED_ENV_RESPONSE "
            f"pre_samples={len(pre_env)} post_samples={len(post_env)} "
            f"tp_temp_slope_pre_c_min={fmt(pre_temp)} "
            f"tp_temp_slope_post_c_min={fmt(post_temp)} "
            f"ah_slope_pre_g_m3_min={fmt(pre_ah)} "
            f"ah_slope_post_g_m3_min={fmt(post_ah)} "
            f"co2_slope_pre_ppm_min={fmt(pre_co2)} "
            f"co2_slope_post_ppm_min={fmt(post_co2)} "
            f"latest_tp_t={fmt(latest.tp_t if latest else None, 2)} "
            f"latest_tp_rh={fmt(latest.tp_rh if latest else None, 2)} "
            f"latest_xiaomi_t={fmt(latest.xm_t if latest else None, 2)} "
            f"latest_xiaomi_rh={fmt(latest.xm_rh if latest else None, 2)} "
            f"latest_scd_co2={fmt(latest.co2 if latest else None, 2)}",
            flush=True,
        )
        print(
            "STAGE28E_H_CLOSED_PHYSICAL_E2E_PASS "
            f"closure_utc={args.closure_utc or 'unspecified'}",
            flush=True,
        )
        return 0
    finally:
        handle.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", required=True)
    parser.add_argument("--sha", required=True)
    parser.add_argument("--timeout", type=float, default=7200.0)
    parser.add_argument("--post-seconds", type=float, default=600.0)
    parser.add_argument("--baseline-seconds", type=float, default=10.0)
    parser.add_argument("--shelly-poll-seconds", type=float, default=2.0)
    parser.add_argument("--minimum-power-delta", type=float, default=1.0)
    parser.add_argument("--temperature-guard", type=float, default=27.5)
    parser.add_argument("--closure-utc", default="")
    args = parser.parse_args()

    if args.port != GROWBOX_PORT:
        raise SystemExit("refusing non-Growbox serial port")
    if args.timeout <= 0 or args.post_seconds < 0 or args.baseline_seconds < 0:
        raise SystemExit("invalid timing argument")
    if not 26.0 <= args.temperature_guard < 28.0:
        raise SystemExit("temperature guard must remain below the 28 C safety trip")
    return observe(args)


if __name__ == "__main__":
    raise SystemExit(main())
