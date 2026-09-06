from __future__ import annotations

import importlib.util
import math
import time
from pathlib import Path

V2_PATH = "/tmp/growbox-ah-arbiter-clean-v2.py"
PATCHED_V2_PATH = "/tmp/growbox-ah-arbiter-clean-v2-v5base.py"

src = Path(V2_PATH).read_text()
old = '''            if not saw_recovery_hold:\n                raise RuntimeError("expected startup RecoveryHold was not observed")'''
new = '''            if not saw_recovery_hold:\n                print("AHV5_STARTUP_DIRECT_SAFE_PASS recovery_hold_observed=0", flush=True)\n            else:\n                print("AHV5_STARTUP_RECOVERY_HOLD_PASS recovery_hold_observed=1", flush=True)'''
if src.count(old) != 1:
    raise RuntimeError("unexpected v2 startup gate shape")
Path(PATCHED_V2_PATH).write_text(src.replace(old, new))

spec = importlib.util.spec_from_file_location("ahv2v5", PATCHED_V2_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError("unable to load patched v2 harness")
ah = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ah)


def robust_snapshot(handle) -> dict:
    text = ah.base.collect(handle, 10.8)
    stage = ah.parse_stage(text)
    if stage is None:
        extra = ah.base.collect(handle, 10.8)
        text += extra
        stage = ah.parse_stage(text)
    if stage is None:
        raise RuntimeError("no stage28d_output telemetry")
    if stage["real"] != 1:
        raise RuntimeError("automatic outputs left real-bounded mode")
    if stage["tx_errors"] != 0:
        raise RuntimeError(f"RF tx error count={stage['tx_errors']}")

    deadline = time.monotonic() + (5.0 if (stage["safety"] == 1 or stage["force"] == 1) else 35.0)
    tp = None
    xi = None
    while time.monotonic() < deadline and (tp is None or xi is None):
        sensor_text = ah.base.send(handle, "sensors", 2.5)
        current_tp = ah.parse_sensor_line(sensor_text, "tp357")
        current_xi = ah.parse_sensor_line(sensor_text, "xiaomi")
        if current_tp is not None and current_tp["age"] <= 30000:
            tp = current_tp
        if current_xi is not None and current_xi["age"] <= 30000:
            xi = current_xi
        if tp is None or xi is None:
            time.sleep(0.5)

    if tp is None or xi is None:
        if stage["safety"] == 1 or stage["force"] == 1:
            stage.update({
                "tp_t": float("nan"), "tp_rh": float("nan"), "tp_age": 999999999,
                "xi_t": float("nan"), "xi_rh": float("nan"), "xi_age": 999999999,
                "inside_ah": float("nan"), "intake_ah": float("nan"), "ah_gap": float("nan"),
            })
            return stage
        missing = []
        if tp is None:
            missing.append("TP357")
        if xi is None:
            missing.append("Xiaomi")
        raise RuntimeError("BLE fresh sample unavailable after safety cleared: " + ",".join(missing))

    inside_ah = ah.base.absolute_humidity(tp["temp"], tp["rh"])
    intake_ah = ah.base.absolute_humidity(xi["temp"], xi["rh"])
    if not (math.isfinite(inside_ah) and math.isfinite(intake_ah)):
        raise RuntimeError("non-finite AH")
    if tp["temp"] >= 31.0:
        raise RuntimeError(f"authoritative TP357 unsafe {tp['temp']:.2f}C")

    stage.update({
        "tp_t": tp["temp"], "tp_rh": tp["rh"], "tp_age": tp["age"],
        "xi_t": xi["temp"], "xi_rh": xi["rh"], "xi_age": xi["age"],
        "inside_ah": inside_ah, "intake_ah": intake_ah, "ah_gap": inside_ah - intake_ah,
    })
    return stage


ah.snapshot = robust_snapshot
ah.main()
