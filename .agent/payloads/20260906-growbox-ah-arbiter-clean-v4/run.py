from __future__ import annotations

import importlib.util
import math
import time

V2_PATH = "/tmp/growbox-ah-arbiter-clean-v2.py"
spec = importlib.util.spec_from_file_location("ahv2", V2_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError("unable to load v2 harness")
ahv2 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ahv2)


def robust_snapshot(handle) -> dict:
    text = ahv2.base.collect(handle, 10.8)
    stage = ahv2.parse_stage(text)
    if stage is None:
        extra = ahv2.base.collect(handle, 10.8)
        text += extra
        stage = ahv2.parse_stage(text)
    if stage is None:
        raise RuntimeError("no stage28d_output telemetry")
    if stage["real"] != 1:
        raise RuntimeError("automatic outputs left real-bounded mode")
    if stage["tx_errors"] != 0:
        raise RuntimeError(f"RF tx error count={stage['tx_errors']}")

    # BLE advertisements are asynchronous. During startup safety, do not block waiting
    # for a coincident pair. Once safety is clear, allow a bounded 35 s window and
    # retain the newest valid sample from each sensor independently.
    deadline = time.monotonic() + (5.0 if (stage["safety"] == 1 or stage["force"] == 1) else 35.0)
    tp = None
    xi = None
    while time.monotonic() < deadline and (tp is None or xi is None):
        sensor_text = ahv2.base.send(handle, "sensors", 2.5)
        current_tp = ahv2.parse_sensor_line(sensor_text, "tp357")
        current_xi = ahv2.parse_sensor_line(sensor_text, "xiaomi")
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

    inside_ah = ahv2.base.absolute_humidity(tp["temp"], tp["rh"])
    intake_ah = ahv2.base.absolute_humidity(xi["temp"], xi["rh"])
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


ahv2.snapshot = robust_snapshot
ahv2.main()
