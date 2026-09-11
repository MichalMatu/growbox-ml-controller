#!/usr/bin/env python3
"""Bounded Stage28E Phase H physical E2E harness.

This harness never creates an actuator request. Observe mode waits for the real
controller/sensor path to produce a natural exhaust request. Serial-open reset
is treated as pre-baseline only; any reset/session restart after the stabilized
baseline fails the run.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import time
import urllib.request

import serial

KV_RE = re.compile(r"([A-Za-z0-9_]+)=([^ ]+)")
SHELLY_URL = "http://192.168.0.16/rpc/Switch.GetStatus?id=0"


def shelly_status() -> tuple[bool | None, float | None]:
    try:
        with urllib.request.urlopen(SHELLY_URL, timeout=3) as response:
            payload = json.load(response)
        return bool(payload.get("output", False)), float(payload.get("apower", 0.0))
    except Exception:
        return None, None


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


def observe(args: argparse.Namespace) -> int:
    start = time.monotonic()
    deadline = start + args.timeout
    handle = open_serial(args.port)
    opened = time.monotonic()
    baseline = None
    bad_after: list[str] = []
    first_request = None
    pre_state = None
    transition = None
    pre_power: list[float] = []
    post_power: list[float] = []
    last_status_send = 0.0

    try:
        while time.monotonic() < deadline:
            now = time.monotonic()
            raw = handle.readline()
            if raw:
                line = raw.decode(errors="replace").strip()
                print(line, flush=True)

                if baseline is not None and (
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
                        if baseline is None:
                            baseline = values
                            print(
                                "STAGE28E_H_BASELINE "
                                f"boot_id={values.get('boot_id')} "
                                f"reset_reason={values.get('reset_reason')} "
                                f"uptime_ms={values.get('uptime_ms')} "
                                f"outputs={values.get('outputs')} rf_ready={values.get('rf_ready')} "
                                f"internal_free={values.get('internal_free')} "
                                f"internal_min={values.get('internal_min')} "
                                f"internal_largest={values.get('internal_largest')}",
                                flush=True,
                            )
                        else:
                            assert values.get("boot_id") == baseline.get("boot_id"), (
                                baseline,
                                values,
                            )

                if line.startswith("stage28d_output ") and baseline is not None:
                    values = dict(KV_RE.findall(line))
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
                    except (TypeError, ValueError):
                        continue

                    if safety == 0 and force == 0 and reason == 0 and fan_on == 0:
                        if pre_state is None or request >= 0.10:
                            pre_state = values
                        if request >= 0.10 and first_request is None:
                            first_request = (now, values)
                            print(
                                "STAGE28E_H_REQUEST_SEEN "
                                f"requested_fan={request:.3f} transitions={transitions} "
                                f"dwell={dwell} tx={tx_count}",
                                flush=True,
                            )

                    if (
                        first_request is not None
                        and safety == 0
                        and force == 0
                        and reason == 0
                        and request >= 0.10
                        and fan_on == 1
                        and applied >= 0.99
                        and tx_errors == 0
                    ):
                        initial_transitions = int(first_request[1].get("arbiter_transitions", "0"))
                        initial_tx = int(first_request[1].get("tx", "0"))
                        if transitions > initial_transitions and tx_count > initial_tx:
                            transition = (now, values)
                            print(
                                "STAGE28E_H_TRANSITION_SEEN "
                                f"requested_fan={request:.3f} fan_on=1 "
                                f"applied_fan={applied:.3f} transitions={transitions} "
                                f"dwell={dwell} tx={tx_count} tx_errors={tx_errors}",
                                flush=True,
                            )
                            break

            if now - opened >= 6 and now - last_status_send >= 20:
                try:
                    send(handle, "status")
                except Exception:
                    pass
                last_status_send = now

            if baseline is not None and transition is None and int(now * 2) % 4 == 0:
                on, power = shelly_status()
                if on is not None and power is not None:
                    assert on, "Shelly master output turned off before transition"
                    pre_power.append(power)

            time.sleep(0.01)

        assert baseline is not None, "no stabilized real-bounded baseline"
        assert not bad_after, ("post-baseline reset/lifecycle marker", bad_after[-3:])
        assert first_request is not None, (
            "natural requested_fan>=0.10 not observed in bounded window"
        )
        assert transition is not None, (
            "AH request did not complete fan transition in bounded window"
        )

        for _ in range(8):
            on, power = shelly_status()
            if on is not None and power is not None:
                assert on, "Shelly master output turned off after transition"
                post_power.append(power)
            time.sleep(0.5)
        assert post_power, "no Shelly post-transition evidence"

        # Collect one post-transition diagnostic snapshot for memory/stack/timing evidence.
        send(handle, "status")
        status_deadline = time.monotonic() + 5.0
        while time.monotonic() < status_deadline:
            raw = handle.readline()
            if raw:
                line = raw.decode(errors="replace").strip()
                print(line, flush=True)
                if "ESP-ROM:esp32s3-" in line or "stage28e_runtime_lifecycle entry_count=" in line:
                    bad_after.append(line)
        assert not bad_after, ("post-transition reset/lifecycle marker", bad_after[-3:])

        before = pre_state or first_request[1]
        after = transition[1]
        pre_median = statistics.median(pre_power[-8:]) if pre_power else None
        post_median = statistics.median(post_power)
        power_delta = None if pre_median is None else post_median - pre_median

        print(
            "STAGE28E_H_E2E_PRE "
            f"requested_fan={before.get('requested_fan')} fan_on={before.get('fan_on')} "
            f"applied_fan={before.get('applied_fan')} "
            f"transitions={before.get('arbiter_transitions')} "
            f"dwell={before.get('arbiter_dwell_holds')} tx={before.get('tx')} "
            f"tx_errors={before.get('tx_errors')}",
            flush=True,
        )
        print(
            "STAGE28E_H_E2E_TRANSITION "
            f"requested_fan={after.get('requested_fan')} fan_on={after.get('fan_on')} "
            f"applied_fan={after.get('applied_fan')} "
            f"transitions={after.get('arbiter_transitions')} "
            f"dwell={after.get('arbiter_dwell_holds')} tx={after.get('tx')} "
            f"tx_errors={after.get('tx_errors')}",
            flush=True,
        )
        print(
            "STAGE28E_H_SHELLY_SUPPORT output_on=1 "
            f"pre_median={'na' if pre_median is None else f'{pre_median:.2f}'} "
            f"post_median={post_median:.2f} "
            f"delta_w={'na' if power_delta is None else f'{power_delta:.2f}'} "
            f"post_samples={post_power}",
            flush=True,
        )
        if power_delta is not None:
            assert power_delta >= 1.0, (
                "Shelly power did not independently support fan load transition",
                pre_median,
                post_median,
            )
        print("STAGE28E_H_PHYSICAL_E2E_OBSERVATION_PASS", flush=True)
        return 0
    finally:
        handle.close()


def recovery(args: argparse.Namespace) -> int:
    handle = open_serial(args.port)
    output: list[str] = []
    try:
        start = time.monotonic()
        while time.monotonic() - start < 7:
            text = handle.readline().decode(errors="replace")
            if text:
                output.append(text)
                print(text.strip(), flush=True)

        for command in ("rf fan off", "rf humidifier off", "rf lamp on", "status"):
            send(handle, command)
            time.sleep(1.3)

        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            text = handle.readline().decode(errors="replace")
            if text:
                output.append(text)
                print(text.strip(), flush=True)

        text = "".join(output)
        assert "outputs=fake-locked" in text or "Automatic output mode: fake-locked." in text, (
            "recovery image not fake-locked"
        )
        assert "rf_ready=1" in text or "transport_ready=1" in text, "recovery RF unavailable"
        assert "manual RF TX blocked while automatic outputs are real-bounded" not in text

        for device, state in (("fan", "off"), ("humidifier", "off"), ("lamp", "on")):
            marker = f"manual_rf_tx device={device} state={state}"
            assert marker in text, marker
            line = text[text.index(marker) :].splitlines()[0]
            assert "tx_queued=1" in line and "tx_started=1" in line and "tx_completed=1" in line, (
                line
            )

        values: list[float] = []
        outputs: list[bool] = []
        for _ in range(5):
            on, power = shelly_status()
            assert on is not None and power is not None, "Shelly recovery evidence unavailable"
            outputs.append(on)
            values.append(power)
            time.sleep(0.4)
        assert all(outputs), "Shelly master not ON during recovery"
        print(
            "STAGE28E_H_MANUAL_SAFE_RECOVERY_PASS "
            "outputs=fake-locked fan=off humidifier=off lamp=on shelly_master=on "
            f"median_apower_w={statistics.median(values):.2f} samples={values}",
            flush=True,
        )
        return 0
    finally:
        handle.close()


def final_check(args: argparse.Namespace) -> int:
    handle = open_serial(args.port)
    output: list[str] = []
    try:
        start = time.monotonic()
        sent = False
        while time.monotonic() - start < 18:
            if time.monotonic() - start > 7 and not sent:
                send(handle, "status")
                sent = True
            text = handle.readline().decode(errors="replace")
            if text:
                output.append(text)
                print(text.strip(), flush=True)
        text = "".join(output)
        assert f"firmware_sha={args.sha}" in text
        assert "outputs=fake-locked" in text
        assert "rf_ready=0" in text

        values: list[float] = []
        outputs: list[bool] = []
        for _ in range(5):
            on, power = shelly_status()
            assert on is not None and power is not None, "Shelly final evidence unavailable"
            outputs.append(on)
            values.append(power)
            time.sleep(0.4)
        assert all(outputs)
        print(
            f"STAGE28E_H_FINAL_FAKE_LOCKED_PASS sha={args.sha} "
            "outputs=fake-locked rf_ready=0 shelly_master=on "
            f"median_apower_w={statistics.median(values):.2f} samples={values}",
            flush=True,
        )
        return 0
    finally:
        handle.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("observe", "recovery", "final"))
    parser.add_argument("--port", required=True)
    parser.add_argument("--sha", required=True)
    parser.add_argument("--timeout", type=float, default=780.0)
    args = parser.parse_args()
    if args.port != "/dev/cu.usbserial-1130":
        raise SystemExit("refusing non-Growbox serial port")
    if args.mode == "observe":
        return observe(args)
    if args.mode == "recovery":
        return recovery(args)
    return final_check(args)


if __name__ == "__main__":
    raise SystemExit(main())
