"""Open-loop probe of growbox training simulator — human + CI sanity checks.

Run before ML training to validate directional physics:

  python -m tools.ml.probe_simulator
  python -m tools.ml.probe_simulator --json build/sim-probe/report.json

Does not train models. Writes JSON (+ optional CSV series) under --out-dir.
"""

from __future__ import annotations

import argparse
import json
import math
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any

from .simulator import (
    Co2DoserCapabilities,
    ControlAction,
    EnvironmentParameters,
    EnvironmentState,
    GlobalActuators,
    HeaterCapabilities,
    HeatMatCapabilities,
    HumidifierCapabilities,
    LightsConfig,
    PotConfig,
    PotCultivation,
    PotState,
    PumpCapabilities,
    Scenario,
    SequentialEnvironmentSimulator,
    default_scenario_v2,
)

CheckFn = Callable[[dict[str, Any]], tuple[bool, str]]


def _series_dict(
    times: list[float],
    air_t: list[float],
    air_rh: list[float],
    co2: list[float],
    soil_m: list[float],
    soil_t: list[float],
    nutrient_t: list[float],
    outside_t: list[float] | None = None,
    outside_rh: list[float] | None = None,
    outside_co2: list[float] | None = None,
) -> dict[str, list[float]]:
    payload: dict[str, list[float]] = {
        "t_s": times,
        "air_temperature_c": air_t,
        "air_humidity_pct": air_rh,
        "co2_ppm": co2,
        "soil_moisture_pct": soil_m,
        "soil_temperature_c": soil_t,
        "nutrient_solution_temperature_c": nutrient_t,
    }
    if outside_t is not None:
        payload["outside_temperature_c"] = outside_t
    if outside_rh is not None:
        payload["outside_humidity_pct"] = outside_rh
    if outside_co2 is not None:
        payload["outside_co2_ppm"] = outside_co2
    return payload


def _rollout(
    scenario: Scenario,
    action_fn: Callable[[int, EnvironmentState], ControlAction],
    *,
    steps: int,
    seed: int = 0,
) -> dict[str, list[float]]:
    sim = SequentialEnvironmentSimulator(scenario, seed=seed)
    times: list[float] = [0.0]
    air_t = [sim.state.air_temperature_c]
    air_rh = [sim.state.air_humidity_pct]
    co2 = [sim.state.co2_ppm]
    soil_m = [sim.state.pots[0].soil_moisture_pct]
    soil_t = [sim.state.pots[0].soil_temperature_c]
    nutrient_t = [sim.state.nutrient_solution_temperature_c]
    outside_t = [sim.state.outside_temperature_c]
    outside_rh = [sim.state.outside_humidity_pct]
    outside_co2 = [sim.state.outside_co2_ppm]
    for step_i in range(steps):
        action = action_fn(step_i, sim.state)
        state = sim.step(action, add_sensor_noise=False)
        times.append(sim.elapsed_s)
        air_t.append(state.air_temperature_c)
        air_rh.append(state.air_humidity_pct)
        co2.append(state.co2_ppm)
        soil_m.append(state.pots[0].soil_moisture_pct)
        soil_t.append(state.pots[0].soil_temperature_c)
        nutrient_t.append(state.nutrient_solution_temperature_c)
        outside_t.append(state.outside_temperature_c)
        outside_rh.append(state.outside_humidity_pct)
        outside_co2.append(state.outside_co2_ppm)
    return _series_dict(
        times,
        air_t,
        air_rh,
        co2,
        soil_m,
        soil_t,
        nutrient_t,
        outside_t=outside_t,
        outside_rh=outside_rh,
        outside_co2=outside_co2,
    )


def _base_pot(**kwargs: Any) -> PotConfig:
    defaults = dict(
        available=True,
        soil_moisture_valid=True,
        soil_temperature_valid=True,
        cultivation=PotCultivation(
            pot_volume_l=12.0,
            substrate_water_capacity_ml=3000.0,
            transpiration_factor=1.2,
        ),
        irrigation=PumpCapabilities(
            available=True, flow_ml_s=22.0, maximum_pulse_s=4.0, minimum_interval_s=120.0
        ),
        heat_mat=HeatMatCapabilities(available=True, max_power_w=35.0),
    )
    defaults.update(kwargs)
    return PotConfig(**defaults)


def _probe_scenario(
    *,
    scenario_id: str,
    seed: int = 1,
    air_t: float = 22.0,
    air_rh: float = 50.0,
    co2: float = 800.0,
    outside_t: float = 12.0,
    outside_rh: float = 55.0,
    outside_co2: float = 420.0,
    soil_m: float = 45.0,
    soil_t: float = 20.0,
    nutrient_t: float = 20.0,
    lights: bool = False,
    chamber_model: str = "van_henten",
    timestep_s: float = 10.0,
    heaters_w: float = 200.0,
) -> Scenario:
    pot0 = _base_pot()
    inactive = PotConfig()
    return Scenario(
        scenario_id=scenario_id,
        seed=seed,
        initial_state=EnvironmentState(
            air_temperature_c=air_t,
            air_humidity_pct=air_rh,
            co2_ppm=co2,
            outside_temperature_c=outside_t,
            outside_humidity_pct=outside_rh,
            outside_co2_ppm=outside_co2,
            nutrient_solution_temperature_c=nutrient_t,
            lights_active=lights,
            pots=[
                PotState(soil_moisture_pct=soil_m, soil_temperature_c=soil_t),
                PotState(),
                PotState(),
                PotState(),
            ],
        ),
        environment=EnvironmentParameters(
            growbox_volume_m3=0.8,
            thermal_mass_j_per_k=35_000.0,
            heat_loss_w_per_k=7.0,
            air_leak_rate_ach=0.2,
        ),
        actuators=GlobalActuators(
            heater=HeaterCapabilities(available=True, max_power_w=heaters_w, efficiency=0.95),
            humidifier=HumidifierCapabilities(available=True, max_output_g_h=150.0),
            lights=LightsConfig(integrated=True, max_heat_w=120.0),
        ),
        pots=(pot0, inactive, inactive, inactive),
        timestep_s=timestep_s,
        chamber_model=chamber_model,  # type: ignore[arg-type]
    )


def _delta(series: list[float]) -> float:
    return float(series[-1] - series[0])


def _finite(series: list[float]) -> bool:
    return all(math.isfinite(v) for v in series)


def run_experiments() -> list[dict[str, Any]]:
    experiments: list[dict[str, Any]] = []

    # 1) Heater on vs idle
    sc = _probe_scenario(scenario_id="heater_on", air_t=18.0, outside_t=10.0)
    heat = _rollout(sc, lambda i, s: ControlAction(heater=1.0), steps=60)
    idle = _rollout(
        replace(sc, scenario_id="heater_idle"),
        lambda i, s: ControlAction(),
        steps=60,
    )
    experiments.append(
        {
            "id": "heater_raises_air_t",
            "description": "Full heater raises air temperature more than idle",
            "series": {"heat": heat, "idle": idle},
            "metrics": {
                "delta_t_heat": _delta(heat["air_temperature_c"]),
                "delta_t_idle": _delta(idle["air_temperature_c"]),
            },
            "pass": _delta(heat["air_temperature_c"]) > _delta(idle["air_temperature_c"]) + 0.3
            and _finite(heat["air_temperature_c"]),
        }
    )

    # 2) Fan cools when outside cold
    sc = _probe_scenario(scenario_id="fan_vent", air_t=28.0, outside_t=8.0, air_rh=50.0)
    fan = _rollout(sc, lambda i, s: ControlAction(fan=1.0), steps=40)
    sealed = _rollout(
        replace(sc, scenario_id="fan_sealed"),
        lambda i, s: ControlAction(),
        steps=40,
    )
    experiments.append(
        {
            "id": "fan_cools_toward_outside",
            "description": "Max fan cools warm box faster when outside is cold",
            "series": {"fan": fan, "sealed": sealed},
            "metrics": {
                "delta_t_fan": _delta(fan["air_temperature_c"]),
                "delta_t_sealed": _delta(sealed["air_temperature_c"]),
                "final_t_fan": fan["air_temperature_c"][-1],
                "final_t_sealed": sealed["air_temperature_c"][-1],
            },
            "pass": fan["air_temperature_c"][-1] < sealed["air_temperature_c"][-1] - 0.2,
        }
    )

    # 3) Irrigation raises soil moisture
    sc = _probe_scenario(scenario_id="irrigate", soil_m=35.0)
    # Override min interval so pulses can fire
    pot = replace(
        sc.pots[0],
        irrigation=PumpCapabilities(
            available=True, flow_ml_s=25.0, maximum_pulse_s=5.0, minimum_interval_s=30.0
        ),
    )
    sc = replace(sc, pots=(pot, sc.pots[1], sc.pots[2], sc.pots[3]), timestep_s=10.0)

    def irrigate_action(i: int, s: EnvironmentState) -> ControlAction:
        # Pulse every 3 steps after interval
        return ControlAction(irrigation_pot_1=1.0 if i % 4 == 0 else 0.0)

    irr = _rollout(sc, irrigate_action, steps=24)
    experiments.append(
        {
            "id": "irrigation_raises_soil_moisture",
            "description": "Irrigation pulses increase pot 0 soil moisture",
            "series": {"irrigate": irr},
            "metrics": {
                "soil_start": irr["soil_moisture_pct"][0],
                "soil_end": irr["soil_moisture_pct"][-1],
                "delta_soil": _delta(irr["soil_moisture_pct"]),
                "delta_rh": _delta(irr["air_humidity_pct"]),
            },
            "pass": irr["soil_moisture_pct"][-1] > irr["soil_moisture_pct"][0] + 2.0,
        }
    )

    # 4) Wet pot humidifies more than dry
    wet_sc = _probe_scenario(scenario_id="wet_pot", soil_m=80.0, air_rh=35.0, air_t=24.0)
    dry_sc = _probe_scenario(scenario_id="dry_pot", soil_m=18.0, air_rh=35.0, air_t=24.0)
    wet = _rollout(wet_sc, lambda i, s: ControlAction(), steps=50)
    dry = _rollout(dry_sc, lambda i, s: ControlAction(), steps=50)
    experiments.append(
        {
            "id": "wet_soil_raises_rh_more",
            "description": "Wetter substrate increases chamber RH more than dry soil",
            "series": {"wet": wet, "dry": dry},
            "metrics": {
                "delta_rh_wet": _delta(wet["air_humidity_pct"]),
                "delta_rh_dry": _delta(dry["air_humidity_pct"]),
                "delta_soil_wet": _delta(wet["soil_moisture_pct"]),
            },
            "pass": _delta(wet["air_humidity_pct"]) > _delta(dry["air_humidity_pct"]) + 0.15
            and wet["soil_moisture_pct"][-1] < wet["soil_moisture_pct"][0],
        }
    )

    # 5) Heat mat raises soil T
    sc = _probe_scenario(scenario_id="heat_mat", soil_t=18.0, air_t=18.0)
    mat = _rollout(sc, lambda i, s: ControlAction(heat_mat_pot_1=1.0), steps=40)
    no_mat = _rollout(
        replace(sc, scenario_id="no_mat"),
        lambda i, s: ControlAction(),
        steps=40,
    )
    experiments.append(
        {
            "id": "heat_mat_raises_soil_t",
            "description": "Heat mat warms pot soil more than idle",
            "series": {"mat": mat, "idle": no_mat},
            "metrics": {
                "delta_soil_t_mat": _delta(mat["soil_temperature_c"]),
                "delta_soil_t_idle": _delta(no_mat["soil_temperature_c"]),
            },
            "pass": mat["soil_temperature_c"][-1] > no_mat["soil_temperature_c"][-1] + 0.25,
        }
    )

    # 6) CO2 doser raises CO2 when fan low
    sc = _probe_scenario(scenario_id="co2_dose", co2=600.0, outside_co2=420.0)
    sc = replace(
        sc,
        actuators=replace(
            sc.actuators,
            co2_doser=Co2DoserCapabilities(
                available=True,
                dose_ppm_per_full_pulse=80.0,
                maximum_pulse_s=3.0,
            ),
        ),
    )
    dose = _rollout(
        sc,
        lambda i, s: ControlAction(co2_doser=1.0 if i % 5 == 0 else 0.0, fan=0.0),
        steps=30,
    )
    experiments.append(
        {
            "id": "co2_doser_raises_ppm",
            "description": "CO2 pulses raise chamber ppm above start with fan off",
            "series": {"dose": dose},
            "metrics": {
                "co2_start": dose["co2_ppm"][0],
                "co2_end": dose["co2_ppm"][-1],
                "delta_co2": _delta(dose["co2_ppm"]),
            },
            "pass": dose["co2_ppm"][-1] > dose["co2_ppm"][0] + 50.0,
        }
    )

    # 7) Lights add heat
    dark = _probe_scenario(scenario_id="lights_off", air_t=20.0, lights=False, heaters_w=0.01)
    dark = replace(
        dark,
        actuators=replace(
            dark.actuators,
            heater=HeaterCapabilities(available=False, max_power_w=0.0),
            lights=LightsConfig(integrated=True, max_heat_w=200.0),
        ),
    )
    lit = replace(
        dark,
        scenario_id="lights_on",
        initial_state=replace(dark.initial_state, lights_active=True),
    )
    lit_s = _rollout(lit, lambda i, s: ControlAction(), steps=30)
    dark_s = _rollout(dark, lambda i, s: ControlAction(), steps=30)
    experiments.append(
        {
            "id": "lights_add_heat",
            "description": "lights_active increases air temperature vs dark",
            "series": {"lit": lit_s, "dark": dark_s},
            "metrics": {
                "delta_t_lit": _delta(lit_s["air_temperature_c"]),
                "delta_t_dark": _delta(dark_s["air_temperature_c"]),
            },
            "pass": lit_s["air_temperature_c"][-1] > dark_s["air_temperature_c"][-1] + 0.15,
        }
    )

    # 8) Humidifier raises RH
    sc = _probe_scenario(scenario_id="humidify", air_rh=40.0)
    hum = _rollout(sc, lambda i, s: ControlAction(humidifier=1.0), steps=30)
    experiments.append(
        {
            "id": "humidifier_raises_rh",
            "description": "Humidifier increases air RH",
            "series": {"hum": hum},
            "metrics": {
                "rh_start": hum["air_humidity_pct"][0],
                "rh_end": hum["air_humidity_pct"][-1],
                "delta_rh": _delta(hum["air_humidity_pct"]),
            },
            "pass": hum["air_humidity_pct"][-1] > hum["air_humidity_pct"][0] + 1.0,
        }
    )

    # 9) States stay finite and in broad physical bounds over mixed open loop
    sc = _probe_scenario(scenario_id="mixed_bounds", air_t=22.0, soil_m=50.0)

    def mixed(i: int, s: EnvironmentState) -> ControlAction:
        return ControlAction(
            heater=0.6 if (i // 10) % 2 == 0 else 0.0,
            fan=0.3,
            humidifier=0.2,
            irrigation_pot_1=1.0 if i % 12 == 0 else 0.0,
            heat_mat_pot_1=0.5,
        )

    mixed_s = _rollout(sc, mixed, steps=120)
    ok_bounds = (
        _finite(mixed_s["air_temperature_c"])
        and _finite(mixed_s["air_humidity_pct"])
        and _finite(mixed_s["co2_ppm"])
        and min(mixed_s["air_temperature_c"]) > -20
        and max(mixed_s["air_temperature_c"]) < 60
        and min(mixed_s["air_humidity_pct"]) >= 0
        and max(mixed_s["air_humidity_pct"]) <= 100
        and min(mixed_s["co2_ppm"]) >= 200
        and max(mixed_s["co2_ppm"]) <= 5000
        and min(mixed_s["soil_moisture_pct"]) >= 0
        and max(mixed_s["soil_moisture_pct"]) <= 100
    )
    experiments.append(
        {
            "id": "mixed_open_loop_bounds",
            "description": "Mixed open-loop 20 min keeps states finite and in bounds",
            "series": {"mixed": mixed_s},
            "metrics": {
                "t_min": min(mixed_s["air_temperature_c"]),
                "t_max": max(mixed_s["air_temperature_c"]),
                "rh_min": min(mixed_s["air_humidity_pct"]),
                "rh_max": max(mixed_s["air_humidity_pct"]),
                "co2_min": min(mixed_s["co2_ppm"]),
                "co2_max": max(mixed_s["co2_ppm"]),
                "soil_m_min": min(mixed_s["soil_moisture_pct"]),
                "soil_m_max": max(mixed_s["soil_moisture_pct"]),
            },
            "pass": ok_bounds,
        }
    )

    # 10) Determinism
    sc = default_scenario_v2(seed=99)
    a = _rollout(sc, lambda i, s: ControlAction(heater=0.4, fan=0.2), steps=20, seed=99)
    b = _rollout(sc, lambda i, s: ControlAction(heater=0.4, fan=0.2), steps=20, seed=99)
    experiments.append(
        {
            "id": "determinism",
            "description": "Identical seeds produce identical air temperature trail",
            "series": {},
            "metrics": {
                "max_abs_t_diff": max(
                    abs(x - y) for x, y in zip(a["air_temperature_c"], b["air_temperature_c"])
                )
            },
            "pass": a["air_temperature_c"] == b["air_temperature_c"],
        }
    )

    return experiments


def _strip_heavy_series(experiments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Compact report without full timeseries (for console summary)."""
    compact = []
    for exp in experiments:
        compact.append(
            {
                "id": exp["id"],
                "description": exp["description"],
                "metrics": exp["metrics"],
                "pass": exp["pass"],
            }
        )
    return compact


def write_csv_series(path: Path, series: dict[str, list[float]]) -> None:
    keys = list(series.keys())
    rows = zip(*(series[k] for k in keys))
    lines = [",".join(keys)]
    for row in rows:
        lines.append(",".join(f"{v:.6g}" for v in row))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("build/sim-probe"),
        help="Directory for report.json and CSV series",
    )
    parser.add_argument(
        "--json",
        type=Path,
        default=None,
        help="Optional explicit path for full JSON report",
    )
    parser.add_argument(
        "--save-series",
        action="store_true",
        help="Write per-experiment CSV timeseries",
    )
    args = parser.parse_args(argv)

    experiments = run_experiments()
    passed = sum(1 for e in experiments if e["pass"])
    failed = [e["id"] for e in experiments if not e["pass"]]
    total = len(experiments)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "summary": {
            "total": total,
            "passed": passed,
            "failed": failed,
            "ok": passed == total,
        },
        "experiments": experiments,
    }
    report_path = args.json or (args.out_dir / "report.json")
    # Full report may be large; still useful for debugging
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    compact_path = args.out_dir / "summary.json"
    compact_path.write_text(
        json.dumps(
            {"summary": report["summary"], "experiments": _strip_heavy_series(experiments)},
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    if args.save_series:
        series_dir = args.out_dir / "series"
        series_dir.mkdir(parents=True, exist_ok=True)
        for exp in experiments:
            for name, series in exp.get("series", {}).items():
                if series:
                    write_csv_series(series_dir / f"{exp['id']}__{name}.csv", series)

    print("Growbox simulator probe")
    print("=" * 60)
    for exp in experiments:
        status = "PASS" if exp["pass"] else "FAIL"
        print(f"[{status}] {exp['id']}")
        print(f"       {exp['description']}")
        metrics = exp["metrics"]
        metric_bits = ", ".join(
            f"{k}={v:.4g}" if isinstance(v, float) else f"{k}={v}" for k, v in metrics.items()
        )
        print(f"       {metric_bits}")
    print("=" * 60)
    print(f"Result: {passed}/{total} passed")
    print(f"Report: {report_path}")
    print(f"Summary: {compact_path}")
    if failed:
        print(f"Failed: {', '.join(failed)}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
