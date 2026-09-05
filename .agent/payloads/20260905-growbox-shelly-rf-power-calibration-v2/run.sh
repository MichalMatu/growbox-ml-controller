#!/usr/bin/env bash
set -euo pipefail

EXPECTED_BRANCH_HEAD=6f50782d22e51fffbbfd8574db611454ee477a4a
EXPECTED_FIRMWARE=af16aebde8f69d1a1257256c7711e9721c07c9d5
BRANCH=mvp/environment-controller
SETTLE_SECONDS=20

cleanup_git() {
  git reset --hard "$EXPECTED_BRANCH_HEAD" >/dev/null 2>&1 || true
}
trap cleanup_git EXIT

git fetch -q origin "$BRANCH"
git reset --hard "$EXPECTED_BRANCH_HEAD"
test "$(git rev-parse HEAD)" = "$EXPECTED_BRANCH_HEAD"
test "$(git rev-parse origin/$BRANCH)" = "$EXPECTED_BRANCH_HEAD"
test -z "$(git status --porcelain)"

PY="$(git rev-parse --show-toplevel)/.venv/bin/python"
if [[ ! -x "$PY" ]]; then
  PY="$(command -v python3)"
fi

"$PY" - "$EXPECTED_FIRMWARE" "$SETTLE_SECONDS" <<'PY'
import json
import statistics
import sys
import time
import urllib.request
from pathlib import Path

import serial
from tools.stage27c_soak import detect_ch340_port

SHELLY = "http://192.168.0.16"
expected_firmware = sys.argv[1]
settle_seconds = float(sys.argv[2])
port = detect_ch340_port()
if not port:
    raise SystemExit("CrowPanel CH340 serial port was not detected")
print("SHELLY_RF_CAL_V2_PORT", port)
print(f"SETTLE_SECONDS {settle_seconds:.0f}")


def http_get(path):
    with urllib.request.urlopen(SHELLY + path, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def rpc(method, params):
    payload = json.dumps({"id": 1, "method": method, "params": params}).encode("utf-8")
    request = urllib.request.Request(
        SHELLY + "/rpc",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def shelly_status():
    status = http_get("/rpc/Switch.GetStatus?id=0")
    required = ("output", "apower", "voltage", "current")
    if not all(key in status for key in required):
        raise RuntimeError(f"Shelly status missing required fields: {status}")
    return status


def set_master(on):
    rpc("Switch.Set", {"id": 0, "on": bool(on), "tag": "growbox-cal-v2"})
    time.sleep(1.0)
    status = shelly_status()
    if bool(status["output"]) != bool(on):
        raise RuntimeError(f"Shelly relay readback mismatch requested={on} status={status}")
    print(f"SHELLY_MASTER_READBACK on={int(on)} apower={status['apower']:.3f} voltage={status['voltage']:.2f}")
    return status


def sample_power(count=9, interval=0.5):
    rows = []
    for _ in range(count):
        status = shelly_status()
        rows.append(status)
        time.sleep(interval)
    powers = [float(row["apower"]) for row in rows]
    volts = [float(row["voltage"]) for row in rows]
    currents = [float(row["current"]) for row in rows]
    return {
        "power_median_w": statistics.median(powers),
        "power_min_w": min(powers),
        "power_max_w": max(powers),
        "voltage_median_v": statistics.median(volts),
        "current_median_a": statistics.median(currents),
        "samples": rows,
    }


all_chunks = []


def collect(handle, duration):
    deadline = time.monotonic() + duration
    chunks = []
    while time.monotonic() < deadline:
        data = handle.read(4096)
        if data:
            chunks.append(data)
            all_chunks.append(data)
    return b"".join(chunks).decode("utf-8", errors="replace")


def command(handle, text, duration=1.8):
    handle.write(text.encode("ascii") + b"\n")
    handle.flush()
    return collect(handle, duration)


def status_ready(handle):
    for _ in range(4):
        text = command(handle, "status", 1.8)
        if (
            f"status firmware_sha={expected_firmware}" in text
            and "outputs=fake-locked" in text
            and "rf_ready=1" in text
        ):
            return True
        command(handle, "", 0.3)
    return False


def transmit(handle, device, state, code, attempts=3):
    expected = f"manual_rf_tx device={device} state={state} code={code}"
    combined = ""
    for _ in range(attempts):
        combined += command(handle, f"rf {device} {state}", 2.0)
        if expected in combined and "tx_queued=1 tx_started=1 tx_completed=1" in combined:
            return
    raise RuntimeError(f"RF evidence missing for {device} {state}")


def force_all_off(handle):
    errors = []
    for device, code in [
        ("lamp", 16926208),
        ("fan", 1040336384),
        ("humidifier", 771900928),
    ]:
        try:
            transmit(handle, device, "off", code)
        except Exception as exc:
            errors.append(f"{device}:{exc}")
    return errors


def calibrate_device(handle, device, on_code, off_code):
    pre = sample_power()
    transmit(handle, device, "on", on_code)
    print(f"WAIT_AFTER_ON device={device} seconds={settle_seconds:.0f}")
    time.sleep(settle_seconds)
    on_state = sample_power()
    transmit(handle, device, "off", off_code)
    print(f"WAIT_AFTER_OFF device={device} seconds={settle_seconds:.0f}")
    time.sleep(settle_seconds)
    off_state = sample_power()
    delta_on = on_state["power_median_w"] - pre["power_median_w"]
    delta_off = on_state["power_median_w"] - off_state["power_median_w"]
    result = {
        "device": device,
        "settle_seconds": settle_seconds,
        "pre": pre,
        "on": on_state,
        "off": off_state,
        "delta_on_w": delta_on,
        "delta_off_w": delta_off,
        "delta_agreement_w": abs(delta_on - delta_off),
    }
    print(
        "POWER_SIGNATURE_20S "
        f"device={device} pre_w={pre['power_median_w']:.3f} "
        f"on_w={on_state['power_median_w']:.3f} off_w={off_state['power_median_w']:.3f} "
        f"delta_on_w={delta_on:.3f} delta_off_w={delta_off:.3f} "
        f"voltage_v={on_state['voltage_median_v']:.2f}"
    )
    return result

initial = shelly_status()
print(
    "SHELLY_INITIAL "
    f"output={int(bool(initial['output']))} apower={initial['apower']:.3f} "
    f"voltage={initial['voltage']:.2f} current={initial['current']:.4f}"
)

if not initial["output"]:
    set_master(True)
else:
    print("SHELLY_MASTER_ALREADY_ON")

results = {"settle_seconds": settle_seconds}
unsafe_cleanup = False
with serial.Serial(port, 115200, timeout=0.12, write_timeout=1.0) as handle:
    try:
        handle.dtr = False
        handle.rts = False
    except Exception:
        pass
    time.sleep(1.0)
    handle.reset_input_buffer()
    command(handle, "", 0.5)

    if not status_ready(handle):
        raise SystemExit("firmware/safety identity check failed before calibration")

    try:
        cleanup_errors = force_all_off(handle)
        if cleanup_errors:
            raise RuntimeError("initial all-off failed: " + ", ".join(cleanup_errors))
        print(f"WAIT_INITIAL_ALL_OFF seconds={settle_seconds:.0f}")
        time.sleep(settle_seconds)
        baseline = sample_power()
        results["baseline"] = baseline
        print(
            "POWER_BASELINE_20S "
            f"apower_w={baseline['power_median_w']:.3f} voltage_v={baseline['voltage_median_v']:.2f}"
        )

        devices = [
            ("lamp", 235030016, 16926208),
            ("fan", 906118656, 1040336384),
            ("humidifier", 637683200, 771900928),
        ]
        for device, on_code, off_code in devices:
            results[device] = calibrate_device(handle, device, on_code, off_code)

    finally:
        cleanup_errors = force_all_off(handle)
        print(f"WAIT_FINAL_ALL_OFF seconds={settle_seconds:.0f}")
        time.sleep(settle_seconds)
        final = sample_power()
        results["final"] = final
        baseline_w = results.get("baseline", final)["power_median_w"]
        final_delta = final["power_median_w"] - baseline_w
        print(
            "POWER_FINAL_20S "
            f"apower_w={final['power_median_w']:.3f} baseline_delta_w={final_delta:.3f} "
            f"cleanup_errors={len(cleanup_errors)}"
        )
        if cleanup_errors or final_delta > 8.0:
            unsafe_cleanup = True

    if not status_ready(handle):
        unsafe_cleanup = True
        print("POST_CAL_RUNTIME_STATUS_FAILED")

if unsafe_cleanup:
    print("CALIBRATION_CLEANUP_UNCERTAIN master_cutoff=1")
    set_master(False)
    raise SystemExit("Calibration cleanup was uncertain; Shelly master cutoff was applied")

output_path = Path("/tmp/growbox_shelly_rf_power_calibration_v2.json")
output_path.write_text(json.dumps(results, indent=2, sort_keys=True))
print(output_path.read_text())
print(
    "SHELLY_RF_POWER_CALIBRATION_20S_COMPLETE "
    "master_final=on lamp_final=off fan_final=off humidifier_final=off"
)
PY

test -z "$(git status --porcelain)"
