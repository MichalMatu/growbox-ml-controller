"""CLI: growbox simulator calibration protocol + fit.

Examples::

  python -m tools.ml.calibrate_simulator protocol
  python -m tools.ml.calibrate_simulator protocol --markdown docs/simulator/CALIBRATION_PROTOCOL.generated.md
  python -m tools.ml.calibrate_simulator fit --bundle path/to/bundle.json --out build/calibration.json
  python -m tools.ml.calibrate_simulator demo --out-dir build/calibration-demo
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import replace
from pathlib import Path
from typing import Any

from .calibration import (
    apply_estimates_to_scenario,
    estimate_all_from_bundle,
    estimate_co2_dose_ppm,
    estimate_effective_ach_from_fan,
    estimate_humidifier_g_h,
    estimate_substrate_capacity_ml,
    estimate_thermal_mass_from_heater,
    estimates_to_jsonable,
    protocol_as_markdown,
)
from .deviations import deviations_from_simulator
from .foresight import foresight
from .probe_simulator import _rollout
from .simulator import (
    Co2DoserCapabilities,
    ControlAction,
    EnvironmentState,
    GlobalActuators,
    HeaterCapabilities,
    HumidifierCapabilities,
    PotConfig,
    PotState,
    PumpCapabilities,
    SequentialEnvironmentSimulator,
    default_scenario_v2,
)


def _cmd_protocol(args: argparse.Namespace) -> int:
    text = protocol_as_markdown()
    if args.markdown:
        path = Path(args.markdown)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text + "\n", encoding="utf-8")
        print(f"wrote {path}")
    else:
        print(text)
    return 0


def _cmd_fit(args: argparse.Namespace) -> int:
    bundle_path = Path(args.bundle)
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    if not isinstance(bundle, dict):
        raise SystemExit("bundle must be a JSON object")
    estimates = estimate_all_from_bundle(
        bundle,
        growbox_volume_m3=float(bundle.get("growbox_volume_m3", args.volume)),
        heater_power_w=float(bundle.get("heater_power_w", args.heater_power)),
    )
    payload: dict[str, Any] = {
        "source": str(bundle_path),
        "estimates": estimates_to_jsonable(estimates),
    }
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {out}")
    else:
        print(json.dumps(payload, indent=2))
    return 0


def _synthetic_bundle(volume: float = 0.8) -> dict[str, Any]:
    """Generate open-loop series from the current simulator (self-consistency demo)."""
    base = default_scenario_v2(scenario_id="cal-demo", seed=1)
    pot0 = replace(
        base.pots[0],
        available=True,
        soil_moisture_valid=True,
        irrigation=PumpCapabilities(available=True, flow_ml_s=20.0, maximum_pulse_s=5.0),
    )
    scenario = replace(
        base,
        initial_state=EnvironmentState(
            air_temperature_c=20.0,
            air_humidity_pct=45.0,
            co2_ppm=600.0,
            outside_temperature_c=14.0,
            outside_humidity_pct=50.0,
            outside_co2_ppm=420.0,
            pots=[PotState(soil_moisture_pct=35.0), PotState(), PotState(), PotState()],
        ),
        actuators=GlobalActuators(
            heater=HeaterCapabilities(available=True, max_power_w=180.0, efficiency=0.92),
            humidifier=HumidifierCapabilities(available=True, max_output_g_h=110.0),
            co2_doser=Co2DoserCapabilities(
                available=True, dose_ppm_per_full_pulse=100.0, maximum_pulse_s=3.0
            ),
        ),
        pots=(pot0, PotConfig(), PotConfig(), PotConfig()),
    )

    def heat_only(_i: int, _s: EnvironmentState) -> ControlAction:
        return ControlAction(heater=1.0)

    def fan_only(_i: int, _s: EnvironmentState) -> ControlAction:
        return ControlAction(fan=1.0)

    def humid_only(_i: int, _s: EnvironmentState) -> ControlAction:
        return ControlAction(humidifier=1.0)

    # Pre-warm then fan: start hot for exchange estimate
    hot = replace(
        scenario,
        initial_state=replace(scenario.initial_state, air_temperature_c=28.0),
    )

    heater_series = _rollout(scenario, heat_only, steps=40, seed=1)
    fan_series = _rollout(hot, fan_only, steps=36, seed=2)
    humid_series = _rollout(scenario, humid_only, steps=30, seed=3)

    # CO2 pulses
    sim = SequentialEnvironmentSimulator(scenario, seed=4)
    before = sim.state.co2_ppm
    for _ in range(2):
        sim.step(ControlAction(co2_doser=1.0), add_sensor_noise=False)
    after = sim.state.co2_ppm

    # Irrigation: one pulse
    sim_i = SequentialEnvironmentSimulator(scenario, seed=5)
    soil_before = sim_i.state.pots[0].soil_moisture_pct
    sim_i.step(ControlAction(irrigation_pot_1=1.0), add_sensor_noise=False)
    soil_after = sim_i.state.pots[0].soil_moisture_pct
    applied = 20.0 * 5.0  # flow * pulse

    return {
        "growbox_volume_m3": volume,
        "heater_power_w": 180.0,
        "heater_efficiency": 0.92,
        "heater_series": heater_series,
        "fan_series": fan_series,
        "humidifier_series": humid_series,
        "co2_pulse": {"before_ppm": before, "after_ppm": after, "pulses": 2},
        "irrigation_pulse": {
            "soil_before_pct": soil_before,
            "soil_after_pct": soil_after,
            "applied_ml": applied,
        },
    }


def _cmd_demo(args: argparse.Namespace) -> int:
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    bundle = _synthetic_bundle(volume=args.volume)
    (out_dir / "bundle.json").write_text(json.dumps(bundle, indent=2) + "\n", encoding="utf-8")

    estimates = estimate_all_from_bundle(bundle, growbox_volume_m3=args.volume)
    # Also include explicit estimators for logging
    extra = [
        estimate_thermal_mass_from_heater(
            bundle["heater_series"], heater_power_w=180.0, heater_efficiency=0.92
        ),
        estimate_effective_ach_from_fan(bundle["fan_series"], growbox_volume_m3=args.volume),
        estimate_humidifier_g_h(bundle["humidifier_series"], growbox_volume_m3=args.volume),
        estimate_co2_dose_ppm(
            co2_before_ppm=bundle["co2_pulse"]["before_ppm"],
            co2_after_ppm=bundle["co2_pulse"]["after_ppm"],
            pulses=2,
        ),
        estimate_substrate_capacity_ml(
            soil_before_pct=bundle["irrigation_pulse"]["soil_before_pct"],
            soil_after_pct=bundle["irrigation_pulse"]["soil_after_pct"],
            applied_ml=bundle["irrigation_pulse"]["applied_ml"],
        ),
    ]
    # prefer estimate_all list (dedupe by name keeping first)
    by_name = {e.name: e for e in estimates}
    for e in extra:
        by_name.setdefault(e.name, e)
    estimates = list(by_name.values())

    scenario = default_scenario_v2(scenario_id="cal-applied", seed=0)
    calibrated = apply_estimates_to_scenario(scenario, estimates)

    sim = SequentialEnvironmentSimulator(calibrated, seed=0)
    # Inject off-target climate and show foresight with heater
    from .foresight import inject_state

    inject_state(
        sim,
        {
            "air_temperature_c": 18.0,
            "air_humidity_pct": 40.0,
            "co2_ppm": 500.0,
        },
    )
    report = foresight(sim, ControlAction(heater=1.0, humidifier=0.5), steps=6)
    initial = deviations_from_simulator(sim)

    result = {
        "estimates": estimates_to_jsonable(estimates),
        "applied_environment": {
            "thermal_mass_j_per_k": calibrated.environment.thermal_mass_j_per_k,
            "air_leak_rate_ach": calibrated.environment.air_leak_rate_ach,
            "fan_max_airflow_m3_h": calibrated.actuators.fan.max_airflow_m3_h,
            "humidifier_max_output_g_h": calibrated.actuators.humidifier.max_output_g_h,
            "co2_dose_ppm_per_full_pulse": calibrated.actuators.co2_doser.dose_ppm_per_full_pulse,
            "substrate_water_capacity_ml": calibrated.pots[
                0
            ].cultivation.substrate_water_capacity_ml,
        },
        "deviations_after_inject": initial.as_dict(),
        "foresight": report.as_dict(),
    }
    out_path = out_dir / "result.json"
    out_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out_dir / 'bundle.json'}")
    print(f"wrote {out_path}")
    for est in estimates:
        flag = "" if math.isfinite(est.value) else " (invalid)"
        print(f"  {est.name}: {est.value:.4g} {est.unit} [{est.confidence}]{flag}")
    print(f"  rms_normalized after inject: {initial.rms_normalized:.3f}")
    if report.steps:
        final = report.steps[-1].deviations
        print(f"  rms_normalized after foresight: {final.rms_normalized:.3f}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_proto = sub.add_parser("protocol", help="Print or write calibration protocol")
    p_proto.add_argument("--markdown", type=Path, default=None)
    p_proto.set_defaults(func=_cmd_protocol)

    p_fit = sub.add_parser("fit", help="Fit estimates from a calibration bundle JSON")
    p_fit.add_argument("--bundle", type=Path, required=True)
    p_fit.add_argument("--out", type=Path, default=None)
    p_fit.add_argument("--volume", type=float, default=0.8)
    p_fit.add_argument("--heater-power", type=float, default=180.0)
    p_fit.set_defaults(func=_cmd_fit)

    p_demo = sub.add_parser("demo", help="Synthetic self-consistency calibration demo")
    p_demo.add_argument("--out-dir", type=Path, default=Path("build/calibration-demo"))
    p_demo.add_argument("--volume", type=float, default=0.8)
    p_demo.set_defaults(func=_cmd_demo)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
