"""Hit panel HTTP API + drive board through setting combinations; report ML behavior.

Uses the local panel server (default http://127.0.0.1:8765). Connects serial via
/api/connect, loads presets and stress scenarios, steps the controller, and
records raw/safe outputs + diagnostics for analysis.
"""

from __future__ import annotations

import argparse
import copy
import json
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tools.ml.scenario_payload import SCENARIO_PRESETS, default_scenario

OUTPUTS = (
    "heater",
    "fan",
    "humidifier",
    "dehumidifier",
    "cooler",
    "co2_doser",
    "irrigation_pot_1",
    "irrigation_pot_2",
    "irrigation_pot_3",
    "irrigation_pot_4",
    "nutrient_heater",
    "heat_mat_pot_1",
    "heat_mat_pot_2",
    "heat_mat_pot_3",
    "heat_mat_pot_4",
)


@dataclass
class Finding:
    severity: str
    case: str
    code: str
    message: str
    detail: dict[str, Any] = field(default_factory=dict)


class PanelClient:
    def __init__(self, base: str, *, timeout: float = 12.0) -> None:
        self.base = base.rstrip("/")
        self.timeout = timeout

    def request(self, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        data = None if body is None else json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            self.base + path,
            data=data,
            method=method,
            headers={"Content-Type": "application/json"} if body is not None else {},
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            payload = exc.read().decode("utf-8", errors="replace")
            try:
                parsed = json.loads(payload)
            except json.JSONDecodeError:
                parsed = {"error": payload}
            raise RuntimeError(f"{method} {path} -> HTTP {exc.code}: {parsed}") from exc

    def get(self, path: str) -> dict[str, Any]:
        return self.request("GET", path)

    def post(self, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.request("POST", path, body or {})

    def wait_decision(self, *, timeout: float = 6.0) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        last: dict[str, Any] = {}
        while time.monotonic() < deadline:
            state = self.get("/api/state")
            last = state
            decision = state.get("last_decision")
            if isinstance(decision, dict) and decision.get("type") == "decision":
                # Prefer a decision stamped after our step — history has newest first?
                return decision
            time.sleep(0.05)
        raise TimeoutError(f"no decision in state; last={last.get('last_error')}")

    def step_and_decision(self, *, clear_first: bool = True) -> dict[str, Any]:
        before = self.get("/api/state").get("last_decision")
        before_step = before.get("step") if isinstance(before, dict) else None
        self.post("/api/step", {})
        deadline = time.monotonic() + 8.0
        while time.monotonic() < deadline:
            state = self.get("/api/state")
            decision = state.get("last_decision")
            if isinstance(decision, dict) and decision.get("type") == "decision":
                if before_step is None or decision.get("step") != before_step:
                    return decision
            time.sleep(0.05)
        raise TimeoutError("step produced no new decision")


def probe_endpoints(client: PanelClient) -> dict[str, Any]:
    report: dict[str, Any] = {"get": {}, "post_smoke": {}}
    for path in ("/api/schema", "/api/state", "/api/ports", "/api/presets", "/api/diagnostics"):
        try:
            payload = client.get(path)
            summary: dict[str, Any] = {"ok": True, "keys": sorted(payload.keys())[:30]}
            if path == "/api/schema":
                summary["schema_version"] = payload.get("schema_version")
                summary["schema_hash"] = payload.get("schema_hash")
                summary["feature_count"] = payload.get("feature_count")
                summary["outputs"] = len(payload.get("outputs") or [])
                summary["sections"] = len(payload.get("sections") or [])
                summary["preset_count"] = len(payload.get("presets") or [])
            if path == "/api/ports":
                summary["ports"] = payload.get("ports")
            if path == "/api/presets":
                summary["presets"] = [p.get("id") for p in payload.get("presets") or []]
            if path == "/api/state":
                summary["connected"] = payload.get("connected")
            report["get"][path] = summary
        except Exception as exc:  # noqa: BLE001
            report["get"][path] = {"ok": False, "error": str(exc)}

    # defaults endpoint for each preset
    defaults: dict[str, Any] = {}
    for preset in SCENARIO_PRESETS:
        try:
            payload = client.post("/api/defaults", {"seed": 101, "preset": preset})
            sc = payload.get("scenario") or {}
            defaults[preset] = {
                "ok": True,
                "keys": sorted(sc.keys()),
                "pots": len(sc.get("pots") or []),
                "heater_available": (sc.get("actuators") or {}).get("heater", {}).get("available"),
            }
        except Exception as exc:  # noqa: BLE001
            defaults[preset] = {"ok": False, "error": str(exc)}
    report["post_smoke"]["/api/defaults"] = defaults
    return report


def evaluate(case: str, scenario: dict[str, Any], decision: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    raw = decision.get("raw_output") or {}
    safe = decision.get("safe_output") or {}
    diag = decision.get("diagnostics") or {}
    thr = float((scenario.get("safety") or {}).get("binary_threshold", 0.5))

    if decision.get("schema_version") != 4:
        findings.append(
            Finding("error", case, "schema_version", str(decision.get("schema_version")))
        )
    if decision.get("schema_hash") != "457ddca8b0e5":
        findings.append(Finding("error", case, "schema_hash", str(decision.get("schema_hash"))))
    if diag.get("inference_status") not in (None, "ok"):
        findings.append(
            Finding("error", case, "inference", str(diag.get("inference_status")), {"diag": diag})
        )

    binary_outputs = (
        "heater",
        "humidifier",
        "dehumidifier",
        "cooler",
        "co2_doser",
        "irrigation_pot_1",
        "irrigation_pot_2",
        "irrigation_pot_3",
        "irrigation_pot_4",
        "nutrient_heater",
        "heat_mat_pot_1",
        "heat_mat_pot_2",
        "heat_mat_pot_3",
        "heat_mat_pot_4",
    )
    for name in OUTPUTS:
        if name not in safe:
            findings.append(Finding("error", case, "missing_output", name))
            continue
        val = float(safe[name])
        if not (0.0 <= val <= 1.0):
            findings.append(Finding("error", case, "range", f"{name}={val}"))
        if (
            name in binary_outputs
            and val not in (0.0, 1.0)
            and abs(val - 0.0) > 1e-5
            and abs(val - 1.0) > 1e-5
        ):
            findings.append(
                Finding("error", case, "non_binary_safe", f"{name}={val}", {"raw": raw.get(name)})
            )

    sensors = scenario.get("sensors") or {}
    targets = scenario.get("targets") or {}
    actuators = scenario.get("actuators") or {}
    validity = scenario.get("validity") or {}
    safety = scenario.get("safety") or {}

    for act, out in (
        ("heater", "heater"),
        ("fan", "fan"),
        ("humidifier", "humidifier"),
        ("dehumidifier", "dehumidifier"),
        ("cooler", "cooler"),
        ("co2_doser", "co2_doser"),
        ("nutrient_heater", "nutrient_heater"),
    ):
        if (actuators.get(act) or {}).get("available") is False and float(safe.get(out, 0)) > 1e-6:
            findings.append(
                Finding(
                    "error", case, "unavailable_on", f"{out}={safe.get(out)}", {"raw": raw.get(out)}
                )
            )

    t_air = float(sensors.get("air_temperature_c", 22))
    t_max = float(safety.get("maximum_air_temperature_c", 35))
    t_alarm = float(safety.get("alarm_air_temperature_c", 32))
    if validity.get("air_temperature_c", True) and t_air >= t_max:
        if float(safe.get("heater", 0)) > 1e-6:
            findings.append(
                Finding(
                    "error", case, "heater_on_overtemp", f"T={t_air} heater={safe.get('heater')}"
                )
            )
        alarm_fan = float(safety.get("alarm_minimum_fan", 0.6))
        if float(safe.get("fan", 0)) + 1e-6 < alarm_fan and (actuators.get("fan") or {}).get(
            "available", True
        ):
            findings.append(Finding("error", case, "fan_not_boosted", f"fan={safe.get('fan')}"))

    if (actuators.get("co2_doser") or {}).get("available") and validity.get("co2_ppm", True):
        if float(sensors.get("co2_ppm", 0)) >= float(targets.get("co2_ppm", 1e9)):
            if float(safe.get("co2_doser", 0)) > 1e-6:
                findings.append(
                    Finding("error", case, "co2_above_target", str(safe.get("co2_doser")))
                )

    if float(safe.get("heater", 0)) >= thr and float(safe.get("cooler", 0)) >= thr:
        findings.append(Finding("error", case, "heater_cooler_both", "conflict"))
    if float(safe.get("humidifier", 0)) >= thr and float(safe.get("dehumidifier", 0)) >= thr:
        findings.append(Finding("error", case, "hum_dehum_both", "conflict"))

    # Policy: clear residual should engage (safe after sharpen+threshold)
    if (
        validity.get("air_temperature_c", True)
        and (actuators.get("heater") or {}).get("available", True)
        and t_air < float(targets.get("air_temperature_c", t_air)) - 3.0
        and t_air < t_alarm
    ):
        if float(safe.get("heater", 0)) < thr:
            findings.append(
                Finding(
                    "warn",
                    case,
                    "cold_no_heat",
                    f"T={t_air} raw={raw.get('heater')} safe={safe.get('heater')}",
                )
            )

    if (
        validity.get("air_temperature_c", True)
        and (actuators.get("cooler") or {}).get("available")
        and t_air > float(targets.get("air_temperature_c", t_air)) + 3.0
        and t_air < t_alarm
    ):
        if float(safe.get("cooler", 0)) < thr:
            findings.append(
                Finding(
                    "warn",
                    case,
                    "hot_no_cool",
                    f"T={t_air} raw={raw.get('cooler')} safe={safe.get('cooler')}",
                )
            )

    rh = float(sensors.get("air_humidity_pct", 50))
    if (
        validity.get("air_humidity_pct", True)
        and (actuators.get("humidifier") or {}).get("available", True)
        and rh < float(targets.get("air_humidity_pct", rh)) - 15.0
    ):
        if float(safe.get("humidifier", 0)) < thr:
            findings.append(
                Finding(
                    "warn",
                    case,
                    "dry_no_humidify",
                    f"RH={rh} raw={raw.get('humidifier')} safe={safe.get('humidifier')}",
                )
            )

    pots = scenario.get("pots") or []
    nutrient_t = float(sensors.get("nutrient_solution_temperature_c", 20))
    nutrient_min = float(safety.get("minimum_nutrient_solution_temperature_c", 15))
    nutrient_blocks_irrigation = (
        validity.get("nutrient_solution_temperature_c", True) and nutrient_t < nutrient_min
    )
    if (
        pots
        and pots[0].get("available")
        and (pots[0].get("irrigation") or {}).get("available")
        and not nutrient_blocks_irrigation
    ):
        soil = float((pots[0].get("sensors") or {}).get("soil_moisture_pct", 50))
        target_soil = float((pots[0].get("targets") or {}).get("soil_moisture_pct", 50))
        if (pots[0].get("validity") or {}).get(
            "soil_moisture_pct", True
        ) and soil < target_soil - 10:
            if float(safe.get("irrigation_pot_1", 0)) < thr:
                findings.append(
                    Finding(
                        "warn",
                        case,
                        "dry_soil_no_irr",
                        f"soil={soil} raw={raw.get('irrigation_pot_1')} safe={safe.get('irrigation_pot_1')}",
                    )
                )

    if validity.get("air_temperature_c") is False and float(safe.get("heater", 0)) > 1e-6:
        findings.append(Finding("error", case, "heater_invalid_temp", str(safe.get("heater"))))

    findings.append(
        Finding(
            "info",
            case,
            "snapshot",
            decision.get("model_version", ""),
            {
                "raw": {k: raw.get(k) for k in OUTPUTS},
                "safe": {k: safe.get(k) for k in OUTPUTS},
                "diagnostics": diag,
                "model_version": decision.get("model_version"),
            },
        )
    )
    return findings


def build_matrix() -> list[tuple[str, dict[str, Any]]]:
    cases: list[tuple[str, dict[str, Any]]] = []
    for preset in SCENARIO_PRESETS:
        cases.append((f"preset:{preset}", default_scenario(seed=300, preset=preset)))

    base = default_scenario(seed=400, preset="nominal")

    # Temperature sweep relative to target 25
    for t in (12.0, 16.0, 20.0, 24.0, 25.0, 28.0, 30.0, 33.0, 36.0, 40.0):
        sc = copy.deepcopy(base)
        sc["seed"] = 410
        sc["sensors"]["air_temperature_c"] = t
        sc["targets"]["air_temperature_c"] = 25.0
        if t >= 28.0:
            sc["actuators"]["cooler"] = {
                "available": True,
                "max_cooling_w": 200.0,
                "control_type": "binary",
            }
        if t >= 36.0:
            sc["previous"]["heater"] = 1.0
        cases.append((f"temp_sweep:T={t}", sc))

    # Humidity sweep
    for rh in (20.0, 35.0, 50.0, 65.0, 80.0, 95.0):
        sc = copy.deepcopy(base)
        sc["seed"] = 420
        sc["sensors"]["air_humidity_pct"] = rh
        sc["targets"]["air_humidity_pct"] = 65.0
        sc["actuators"]["dehumidifier"] = {
            "available": True,
            "max_removal_g_h": 200.0,
            "control_type": "binary",
        }
        cases.append((f"rh_sweep:RH={rh}", sc))

    # CO2 sweep with doser on
    for co2 in (400.0, 700.0, 900.0, 1100.0, 1400.0):
        sc = copy.deepcopy(base)
        sc["seed"] = 430
        sc["sensors"]["co2_ppm"] = co2
        sc["targets"]["co2_ppm"] = 1000.0
        sc["actuators"]["co2_doser"] = {
            "available": True,
            "dose_ppm_per_full_pulse": 120.0,
            "maximum_pulse_s": 5.0,
            "control_type": "binary",
        }
        cases.append((f"co2_sweep:ppm={co2}", sc))

    # Soil moisture sweep pot0
    for soil in (15.0, 30.0, 45.0, 50.0, 60.0, 75.0):
        sc = copy.deepcopy(base)
        sc["seed"] = 440
        sc["pots"][0]["sensors"]["soil_moisture_pct"] = soil
        sc["pots"][0]["targets"]["soil_moisture_pct"] = 50.0
        cases.append((f"soil_sweep:m={soil}", sc))

    # Soil temperature + heat mat
    for st in (12.0, 18.0, 22.0, 28.0):
        sc = copy.deepcopy(base)
        sc["seed"] = 450
        sc["pots"][0]["sensors"]["soil_temperature_c"] = st
        sc["pots"][0]["targets"]["soil_temperature_c"] = 22.0
        sc["pots"][0]["heat_mat"] = {
            "available": True,
            "max_power_w": 40.0,
            "control_type": "binary",
        }
        cases.append((f"soil_temp:st={st}", sc))

    # Actuator availability combos (key singles)
    for name in ("heater", "fan", "humidifier", "cooler", "co2_doser", "nutrient_heater"):
        sc = copy.deepcopy(base)
        sc["seed"] = 460
        sc["sensors"]["air_temperature_c"] = 16.0
        sc["sensors"]["air_humidity_pct"] = 30.0
        sc["sensors"]["co2_ppm"] = 500.0
        sc["targets"]["air_temperature_c"] = 26.0
        sc["targets"]["air_humidity_pct"] = 65.0
        sc["targets"]["co2_ppm"] = 1100.0
        sc["actuators"]["cooler"] = {
            "available": True,
            "max_cooling_w": 200.0,
            "control_type": "binary",
        }
        sc["actuators"]["co2_doser"] = {
            "available": True,
            "dose_ppm_per_full_pulse": 120.0,
            "maximum_pulse_s": 5.0,
            "control_type": "binary",
        }
        sc["actuators"]["nutrient_heater"] = {
            "available": True,
            "max_power_w": 80.0,
            "efficiency": 0.9,
            "control_type": "binary",
        }
        sc["actuators"][name]["available"] = False
        if name == "heater":
            sc["actuators"][name]["max_power_w"] = 0.0
            sc["actuators"][name]["efficiency"] = 0.0
        cases.append((f"disable:{name}", sc))

    # Validity mask combos
    for sensor in (
        "air_temperature_c",
        "air_humidity_pct",
        "co2_ppm",
        "nutrient_solution_temperature_c",
        "outside_temperature_c",
    ):
        sc = copy.deepcopy(base)
        sc["seed"] = 470
        sc["validity"][sensor] = False
        cases.append((f"invalid:{sensor}", sc))

    # Multi-pot counts
    for n in (0, 1, 2, 3, 4):
        sc = default_scenario(seed=480, preset="all_pots" if n == 4 else "nominal")
        if n < 4:
            for i in range(4):
                if i >= n:
                    sc["pots"][i] = copy.deepcopy(
                        default_scenario(preset="minimal_sensors")["pots"][0]
                    )
                    sc["pots"][i]["available"] = False
                    sc["pots"][i]["irrigation"]["available"] = False
                else:
                    sc["pots"][i] = copy.deepcopy(default_scenario(preset="all_pots")["pots"][0])
        sc["seed"] = 480 + n
        cases.append((f"pots_active:{n}", sc))

    # Lights + cold
    sc = copy.deepcopy(base)
    sc["seed"] = 490
    sc["pseudo"]["lights_active"] = True
    sc["sensors"]["air_temperature_c"] = 18.0
    cases.append(("lights_on_cold", sc))

    # Fan high + CO2 doser (venting should kill doser)
    sc = copy.deepcopy(base)
    sc["seed"] = 491
    sc["sensors"]["co2_ppm"] = 500.0
    sc["targets"]["co2_ppm"] = 1200.0
    sc["actuators"]["co2_doser"] = {
        "available": True,
        "dose_ppm_per_full_pulse": 120.0,
        "maximum_pulse_s": 5.0,
        "control_type": "binary",
    }
    sc["previous"]["fan"] = 1.0
    sc["sensors"]["air_temperature_c"] = 34.0  # may boost fan
    cases.append(("fan_vent_co2", sc))

    # Nutrient heater cold solution
    sc = copy.deepcopy(base)
    sc["seed"] = 492
    sc["sensors"]["nutrient_solution_temperature_c"] = 12.0
    sc["targets"]["nutrient_solution_temperature_c"] = 22.0
    sc["actuators"]["nutrient_heater"] = {
        "available": True,
        "max_power_w": 80.0,
        "efficiency": 0.9,
        "control_type": "binary",
    }
    cases.append(("nutrient_cold", sc))

    # Extreme multi residual
    sc = copy.deepcopy(base)
    sc["seed"] = 493
    sc["sensors"].update(
        {
            "air_temperature_c": 14.0,
            "air_humidity_pct": 25.0,
            "co2_ppm": 450.0,
            "nutrient_solution_temperature_c": 14.0,
        }
    )
    sc["targets"].update(
        {
            "air_temperature_c": 26.0,
            "air_humidity_pct": 70.0,
            "co2_ppm": 1200.0,
            "nutrient_solution_temperature_c": 22.0,
        }
    )
    sc["actuators"]["cooler"] = {
        "available": True,
        "max_cooling_w": 200.0,
        "control_type": "binary",
    }
    sc["actuators"]["dehumidifier"] = {
        "available": True,
        "max_removal_g_h": 150.0,
        "control_type": "binary",
    }
    sc["actuators"]["co2_doser"] = {
        "available": True,
        "dose_ppm_per_full_pulse": 120.0,
        "maximum_pulse_s": 5.0,
        "control_type": "binary",
    }
    sc["actuators"]["nutrient_heater"] = {
        "available": True,
        "max_power_w": 80.0,
        "efficiency": 0.9,
        "control_type": "binary",
    }
    sc["pots"][0]["sensors"]["soil_moisture_pct"] = 18.0
    sc["pots"][0]["targets"]["soil_moisture_pct"] = 55.0
    sc["pots"][0]["sensors"]["soil_temperature_c"] = 14.0
    sc["pots"][0]["targets"]["soil_temperature_c"] = 24.0
    sc["pots"][0]["heat_mat"] = {
        "available": True,
        "max_power_w": 40.0,
        "control_type": "binary",
    }
    cases.append(("extreme_multi_need", sc))

    return cases


def run_case(client: PanelClient, case: str, scenario: dict[str, Any]) -> list[Finding]:
    client.post("/api/command", {"command": "pause"})
    client.post("/api/command", {"command": "mode", "value": "replay"})
    time.sleep(0.05)
    client.post("/api/load_scenario", {"scenario": scenario, "seed": scenario.get("seed")})
    time.sleep(0.05)
    decision = client.step_and_decision()
    return evaluate(case, scenario, decision)


def analyze_ml_behavior(case_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate raw/safe activation rates and residual correlations."""
    by_group: dict[str, list[dict[str, Any]]] = {}
    for row in case_rows:
        group = row["case"].split(":")[0]
        by_group.setdefault(group, []).append(row)

    thr = 0.5
    activation: dict[str, dict[str, float]] = {}
    for out in OUTPUTS:
        raw_on = 0
        safe_on = 0
        n = 0
        for row in case_rows:
            snap = row.get("snapshot") or {}
            raw = snap.get("raw") or {}
            safe = snap.get("safe") or {}
            if out not in safe:
                continue
            n += 1
            if float(raw.get(out, 0) or 0) >= thr:
                raw_on += 1
            if float(safe.get(out, 0) or 0) >= thr:
                safe_on += 1
        activation[out] = {
            "n": n,
            "raw_on_frac": raw_on / n if n else 0.0,
            "safe_on_frac": safe_on / n if n else 0.0,
            "safety_cut_frac": (raw_on - safe_on) / n if n else 0.0,
        }

    temp_curve = []
    for row in case_rows:
        if not row["case"].startswith("temp_sweep:"):
            continue
        t = float(row["case"].split("T=")[1])
        snap = row.get("snapshot") or {}
        raw = snap.get("raw") or {}
        safe = snap.get("safe") or {}
        temp_curve.append(
            {
                "T": t,
                "raw_heater": raw.get("heater"),
                "safe_heater": safe.get("heater"),
                "raw_cooler": raw.get("cooler"),
                "safe_cooler": safe.get("cooler"),
                "raw_fan": raw.get("fan"),
                "safe_fan": safe.get("fan"),
            }
        )

    rh_curve = []
    for row in case_rows:
        if not row["case"].startswith("rh_sweep:"):
            continue
        rh = float(row["case"].split("RH=")[1])
        snap = row.get("snapshot") or {}
        raw = snap.get("raw") or {}
        safe = snap.get("safe") or {}
        rh_curve.append(
            {
                "RH": rh,
                "raw_hum": raw.get("humidifier"),
                "safe_hum": safe.get("humidifier"),
                "raw_dehum": raw.get("dehumidifier"),
                "safe_dehum": safe.get("dehumidifier"),
            }
        )

    return {
        "activation": activation,
        "temp_curve": sorted(temp_curve, key=lambda r: r["T"]),
        "rh_curve": sorted(rh_curve, key=lambda r: r["RH"]),
        "group_counts": {g: len(v) for g, v in by_group.items()},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="http://127.0.0.1:8765")
    parser.add_argument("--port", default="/dev/cu.usbmodem1101")
    parser.add_argument(
        "--report", type=Path, default=Path("build/audit/panel_endpoint_audit.json")
    )
    args = parser.parse_args(argv)

    client = PanelClient(args.base)
    print(f"probing {args.base} ...", flush=True)
    endpoints = probe_endpoints(client)
    print(
        json.dumps(
            {"endpoints_get_ok": {k: v.get("ok") for k, v in endpoints["get"].items()}}, indent=2
        )
    )

    # Connect
    print(f"connect {args.port} ...", flush=True)
    try:
        client.post("/api/disconnect", {})
    except Exception:  # noqa: BLE001
        pass
    time.sleep(0.3)
    connect = client.post("/api/connect", {"port": args.port, "baud": 115200})
    print("connected", connect.get("connected"), "startup", bool(connect.get("last_startup")))

    time.sleep(0.5)
    diag = client.get("/api/diagnostics?refresh=1")
    endpoints["diagnostics_after_connect"] = {
        "keys": sorted(diag.keys()) if isinstance(diag, dict) else [],
        "sample": {k: diag.get(k) for k in list(diag)[:12]} if isinstance(diag, dict) else diag,
    }

    cases = build_matrix()
    print(f"matrix cases={len(cases)}", flush=True)
    all_findings: list[Finding] = []
    case_rows: list[dict[str, Any]] = []

    for name, scenario in cases:
        print(f"  {name}...", flush=True)
        try:
            findings = run_case(client, name, scenario)
        except Exception as exc:  # noqa: BLE001
            findings = [Finding("error", name, "session", str(exc))]
        all_findings.extend(findings)
        snap = next((f for f in findings if f.code == "snapshot"), None)
        errs = [asdict(f) for f in findings if f.severity == "error"]
        warns = [asdict(f) for f in findings if f.severity == "warn"]
        case_rows.append(
            {
                "case": name,
                "errors": errs,
                "warns": warns,
                "snapshot": snap.detail if snap else {},
            }
        )
        print(f"    e={len(errs)} w={len(warns)}", flush=True)

    # Sequential overtemp → warm: min-on must not resurrect heater after hard cut.
    print("  seq_overtemp_warm...", flush=True)

    def step_with_sensors(sensors: dict[str, Any] | None = None) -> dict[str, Any]:
        before = client.get("/api/state").get("last_decision")
        before_step = before.get("step") if isinstance(before, dict) else None
        body: dict[str, Any] = {}
        if sensors is not None:
            body["sensors"] = sensors
            body["validity"] = sc_seq["validity"]
        client.post("/api/step", body)
        deadline = time.monotonic() + 8.0
        while time.monotonic() < deadline:
            decision = client.get("/api/state").get("last_decision")
            if isinstance(decision, dict) and decision.get("type") == "decision":
                if before_step is None or decision.get("step") != before_step:
                    return decision
            time.sleep(0.05)
        raise TimeoutError("no new decision after step")

    try:
        client.post("/api/command", {"command": "pause"})
        client.post("/api/command", {"command": "mode", "value": "replay"})
        sc_seq = default_scenario(seed=701, preset="nominal")
        sc_seq["safety"]["heater_minimum_on_s"] = 60.0
        sc_seq["safety"]["heater_minimum_off_s"] = 60.0
        sc_seq["sensors"]["air_temperature_c"] = 15.0
        sc_seq["targets"]["air_temperature_c"] = 25.0
        client.post("/api/load_scenario", {"scenario": sc_seq, "seed": 701})
        time.sleep(0.05)
        d1 = step_with_sensors()
        d2 = step_with_sensors({**sc_seq["sensors"], "air_temperature_c": 36.0})
        d3 = step_with_sensors({**sc_seq["sensors"], "air_temperature_c": 26.0})
        for label, d in (("cold", d1), ("over", d2), ("warm", d3)):
            safe = d.get("safe_output") or {}
            raw = d.get("raw_output") or {}
            h = float(safe.get("heater", -1))
            errs: list[Finding] = []
            warns: list[Finding] = []
            if label == "cold" and h < 0.5:
                warns.append(
                    Finding(
                        "warn",
                        "seq_overtemp/cold",
                        "expected_heat",
                        f"safe={h} raw={raw.get('heater')}",
                    )
                )
            if label == "over" and h > 1e-6:
                errs.append(
                    Finding("error", "seq_overtemp/over", "heater_on_overtemp", f"safe={h}")
                )
            if label == "warm" and h > 1e-6 and float(raw.get("heater", 0)) < 0.5:
                errs.append(
                    Finding(
                        "error",
                        "seq_overtemp/warm",
                        "min_on_resurrect",
                        f"raw={raw.get('heater')} safe={h}",
                    )
                )
            all_findings.extend(errs)
            all_findings.extend(warns)
            case_rows.append(
                {
                    "case": f"seq_overtemp/{label}",
                    "errors": [asdict(f) for f in errs],
                    "warns": [asdict(f) for f in warns],
                    "snapshot": {
                        "raw": raw,
                        "safe": safe,
                        "diagnostics": d.get("diagnostics"),
                        "model_version": d.get("model_version"),
                    },
                }
            )
        print(
            f"    seq heater cold/over/warm="
            f"{(d1.get('safe_output') or {}).get('heater')}/"
            f"{(d2.get('safe_output') or {}).get('heater')}/"
            f"{(d3.get('safe_output') or {}).get('heater')}",
            flush=True,
        )
    except Exception as exc:  # noqa: BLE001
        all_findings.append(Finding("error", "seq_overtemp", "session", str(exc)))
        print(f"    seq error {exc}", flush=True)

    # Closed-loop multi-step via commands
    print("  closed_loop_10...", flush=True)
    try:
        client.post("/api/command", {"command": "pause"})
        client.post("/api/command", {"command": "mode", "value": "closed_loop"})
        sc = default_scenario(seed=500, preset="nominal")
        client.post("/api/load_scenario", {"scenario": sc, "seed": 500})
        traj = []
        for i in range(10):
            d = client.step_and_decision()
            traj.append(
                {
                    "i": i,
                    "step": d.get("step"),
                    "safe": d.get("safe_output"),
                    "raw_heater": (d.get("raw_output") or {}).get("heater"),
                    "safe_heater": (d.get("safe_output") or {}).get("heater"),
                }
            )
            all_findings.extend(evaluate(f"closed_loop#{i}", sc, d))
        case_rows.append(
            {"case": "closed_loop_10", "errors": [], "warns": [], "snapshot": {"trajectory": traj}}
        )
    except Exception as exc:  # noqa: BLE001
        all_findings.append(Finding("error", "closed_loop_10", "session", str(exc)))

    errors = [f for f in all_findings if f.severity == "error"]
    warns = [f for f in all_findings if f.severity == "warn"]
    by_code: dict[str, int] = {}
    for f in errors + warns:
        by_code[f.code] = by_code.get(f.code, 0) + 1

    ml = analyze_ml_behavior(case_rows)
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "base": args.base,
        "port": args.port,
        "endpoints": endpoints,
        "case_count": len(cases),
        "summary": {
            "error_count": len(errors),
            "warn_count": len(warns),
            "by_code": dict(sorted(by_code.items(), key=lambda kv: -kv[1])),
            "errors": [asdict(f) for f in errors],
            "warns": [asdict(f) for f in warns],
        },
        "ml_behavior": ml,
        "cases": case_rows,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], indent=2))
    print("ml activation (safe_on_frac top):")
    for k, v in sorted(ml["activation"].items(), key=lambda kv: -kv[1]["safe_on_frac"])[:8]:
        print(
            f"  {k}: safe={v['safe_on_frac']:.2f} raw={v['raw_on_frac']:.2f} cut={v['safety_cut_frac']:.2f}"
        )
    print("temp_curve:")
    for row in ml["temp_curve"]:
        print(
            f"  T={row['T']}: H raw/safe={row['raw_heater']}/{row['safe_heater']} "
            f"C={row['raw_cooler']}/{row['safe_cooler']} F={row['raw_fan']}/{row['safe_fan']}"
        )
    print(f"report: {args.report}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
