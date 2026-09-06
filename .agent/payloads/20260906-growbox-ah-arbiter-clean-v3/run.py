from __future__ import annotations

import importlib.util
import math

V2_PATH = "/tmp/growbox-ah-arbiter-clean-v2.py"
spec = importlib.util.spec_from_file_location("ahv2", V2_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError("unable to load v2 harness")
ahv2 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ahv2)


def startup_tolerant_snapshot(handle) -> dict:
    text = ahv2.base.collect(handle, 10.8)
    stage = ahv2.parse_stage(text)
    sensor_text = ahv2.base.send(handle, "sensors", 2.5)
    if stage is None:
        stage = ahv2.parse_stage(sensor_text)
    if stage is None:
        extra = ahv2.base.collect(handle, 10.8)
        stage = ahv2.parse_stage(extra)
    if stage is None:
        raise RuntimeError("no stage28d_output telemetry")

    if stage["real"] != 1:
        raise RuntimeError("automatic outputs left real-bounded mode")
    if stage["tx_errors"] != 0:
        raise RuntimeError(f"RF tx error count={stage['tx_errors']}")

    tp = ahv2.parse_sensor_line(sensor_text, "tp357")
    xi = ahv2.parse_sensor_line(sensor_text, "xiaomi")
    if tp is None or xi is None:
        # This is expected immediately after reboot: LampSafety intentionally enters
        # TemperatureUnavailable/RecoveryHold before BLE has produced fresh samples.
        # Tolerate it ONLY while safety is actively latched/forcing exhaust.
        if stage["safety"] == 1 or stage["force"] == 1:
            stage.update({
                "tp_t": float("nan"), "tp_rh": float("nan"), "tp_age": 999999999,
                "xi_t": float("nan"), "xi_rh": float("nan"), "xi_age": 999999999,
                "inside_ah": float("nan"), "intake_ah": float("nan"), "ah_gap": float("nan"),
            })
            return stage
        raise RuntimeError("TP357/Xiaomi sample unavailable after safety cleared")

    inside_ah = ahv2.base.absolute_humidity(tp["temp"], tp["rh"])
    intake_ah = ahv2.base.absolute_humidity(xi["temp"], xi["rh"])
    if not (math.isfinite(inside_ah) and math.isfinite(intake_ah)):
        raise RuntimeError("non-finite AH")
    stage.update({
        "tp_t": tp["temp"], "tp_rh": tp["rh"], "tp_age": tp["age"],
        "xi_t": xi["temp"], "xi_rh": xi["rh"], "xi_age": xi["age"],
        "inside_ah": inside_ah, "intake_ah": intake_ah, "ah_gap": inside_ah - intake_ah,
    })
    if tp["age"] > 30000 or xi["age"] > 30000:
        raise RuntimeError("BLE sample stale >30s")
    if tp["temp"] >= 31.0:
        raise RuntimeError(f"authoritative TP357 unsafe {tp['temp']:.2f}C")
    return stage


ahv2.snapshot = startup_tolerant_snapshot
ahv2.main()
