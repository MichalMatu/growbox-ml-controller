"""Calibrate lumped growbox simulator scalars from open-loop measurements.

Does **not** add GES/Richards physics. Fits the 8–12 engineering parameters that
actually move training fidelity:

- thermal response (heater → ΔT)
- fan / leak air exchange
- humidifier delivery
- CO₂ pulse dose
- irrigation water retention / capacity
- response lags (optional manual)

Closed-form estimators from series endpoints (no SciPy required).
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

from .physics.psychrometrics import air_moisture_capacity_g
from .simulator import Scenario


@dataclass(frozen=True)
class CalibrationProtocolStep:
    id: str
    title: str
    duration_min: float
    procedure: str
    records: str
    estimates: tuple[str, ...]


@dataclass(frozen=True)
class CalibrationEstimate:
    name: str
    value: float
    unit: str
    method: str
    confidence: str  # high | medium | low
    notes: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


# --- Protocol (human + automated checklist) ---------------------------------


def calibration_protocol() -> tuple[CalibrationProtocolStep, ...]:
    """Open-loop tests on a real growbox or high-fidelity twin."""
    return (
        CalibrationProtocolStep(
            id="heater_step",
            title="Heater step response",
            duration_min=10.0,
            procedure=(
                "Start near steady T, lights fixed. Heater command=1 for 5–10 min, "
                "fan=0, humidifier=0. Log air T every 10 s."
            ),
            records="t_s, air_temperature_c, heater (1.0 constant)",
            estimates=("heater_effective_power_w", "thermal_mass_j_per_k"),
        ),
        CalibrationProtocolStep(
            id="fan_exchange",
            title="Fan + outside exchange",
            duration_min=8.0,
            procedure=(
                "Warm chamber (~5–8 °C above outside), then fan=1, heater=0. "
                "Log air T toward outside T."
            ),
            records="t_s, air_temperature_c, outside_temperature_c, fan=1",
            estimates=("effective_ach", "fan_max_airflow_m3_h"),
        ),
        CalibrationProtocolStep(
            id="humidifier_step",
            title="Humidifier delivery",
            duration_min=5.0,
            procedure="RH mid-range, fan low. Humidifier=1 for 3–5 min. Log RH.",
            records="t_s, air_humidity_pct, air_temperature_c, humidifier=1",
            estimates=("humidifier_effective_g_h", "vapor_delivery_factor"),
        ),
        CalibrationProtocolStep(
            id="co2_pulse",
            title="CO₂ pulse dose",
            duration_min=3.0,
            procedure="Fan=0. Fire 1–3 full CO₂ pulses. Log ppm before/after each pulse.",
            records="co2_ppm before/after pulse, pulse count",
            estimates=("co2_dose_ppm_per_full_pulse",),
        ),
        CalibrationProtocolStep(
            id="irrigation_pulse",
            title="Irrigation → soil moisture",
            duration_min=2.0,
            procedure=(
                "One full irrigation pulse on pot 0 with known flow_ml_s and pulse_s. "
                "Read soil moisture before/after (settled)."
            ),
            records="soil_moisture_pct before/after, applied_ml (or flow×pulse)",
            estimates=("substrate_water_capacity_ml",),
        ),
        CalibrationProtocolStep(
            id="idle_leak",
            title="Idle leak / heat loss (optional)",
            duration_min=15.0,
            procedure="All actuators off, lights fixed. Log T drift toward outside.",
            records="t_s, air_temperature_c, outside_temperature_c",
            estimates=("air_leak_rate_ach", "heat_loss_w_per_k"),
        ),
    )


def protocol_as_markdown() -> str:
    lines = [
        "# Growbox open-loop calibration protocol",
        "",
        "Run each step with fixed commands. Export series as JSON "
        "(`{t_s, air_temperature_c, ...}`) or NDJSON decisions.",
        "",
    ]
    for step in calibration_protocol():
        lines.append(f"## {step.id} — {step.title}")
        lines.append(f"- **Duration:** ~{step.duration_min:g} min")
        lines.append(f"- **Procedure:** {step.procedure}")
        lines.append(f"- **Log:** {step.records}")
        lines.append(f"- **Estimates:** {', '.join(step.estimates)}")
        lines.append("")
    lines.append("Apply results with `apply_estimates_to_scenario` or the CLI.")
    return "\n".join(lines)


# --- Series helpers ---------------------------------------------------------


def _series_values(series: Mapping[str, Sequence[float]], key: str) -> list[float]:
    if key not in series:
        raise KeyError(f"series missing {key!r}")
    return [float(v) for v in series[key]]


def _dt_s(series: Mapping[str, Sequence[float]]) -> float:
    times = _series_values(series, "t_s")
    if len(times) < 2:
        raise ValueError("series needs at least 2 samples")
    return max(1e-6, times[-1] - times[0])


def load_series_json(path: Path) -> dict[str, list[float]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("series JSON must be an object of arrays")
    out: dict[str, list[float]] = {}
    for key, values in payload.items():
        if isinstance(values, list) and values and isinstance(values[0], int | float):
            out[key] = [float(v) for v in values]
    if "t_s" not in out:
        raise ValueError("series JSON must include t_s")
    return out


# --- Estimators -------------------------------------------------------------


def estimate_thermal_mass_from_heater(
    series: Mapping[str, Sequence[float]],
    *,
    heater_power_w: float,
    heater_efficiency: float = 0.92,
    heater_command: float = 1.0,
) -> CalibrationEstimate:
    """J/K from ΔT ≈ (η P u Δt) / C  over a heater-on window."""
    temps = _series_values(series, "air_temperature_c")
    dt = _dt_s(series)
    delta_t = temps[-1] - temps[0]
    power = (
        max(1.0, heater_power_w)
        * max(0.0, min(1.0, heater_efficiency))
        * max(0.0, min(1.0, heater_command))
    )
    energy_j = power * dt
    if delta_t < 0.05:
        return CalibrationEstimate(
            name="thermal_mass_j_per_k",
            value=float("nan"),
            unit="J/K",
            method="heater_step",
            confidence="low",
            notes=(
                "ΔT too small or negative; need clear heating "
                f"(ΔT={delta_t:.2f} °C over {dt:.0f} s)"
            ),
        )
    mass = energy_j / delta_t
    # Sanity clamp for ~0.3–2 m³ hobby growbox
    mass = max(5_000.0, min(200_000.0, mass))
    return CalibrationEstimate(
        name="thermal_mass_j_per_k",
        value=mass,
        unit="J/K",
        method="heater_step",
        confidence="medium" if delta_t >= 0.5 else "low",
        notes=f"ΔT={delta_t:.2f} °C over {dt:.0f} s at ~{power:.0f} W effective",
    )


def estimate_effective_ach_from_fan(
    series: Mapping[str, Sequence[float]],
    *,
    growbox_volume_m3: float = 0.8,
) -> CalibrationEstimate:
    """ACH from exponential approach of chamber T to outside with fan on.

    T(t) → T_out:  ln((T0-Tout)/(Tt-Tout)) / t * 3600 ≈ ACH (mixed-air approx).

    If the endpoint has nearly equilibrated (ratio < 0.15), prefer the first
    sample that reaches ~half the initial error so ACH does not saturate at the
    clamp.
    """
    temps = _series_values(series, "air_temperature_c")
    times = _series_values(series, "t_s")
    if "outside_temperature_c" not in series:
        return CalibrationEstimate(
            name="effective_ach",
            value=float("nan"),
            unit="1/h",
            method="fan_exchange",
            confidence="low",
            notes="series missing outside_temperature_c (required; do not use final air T)",
        )
    outs = _series_values(series, "outside_temperature_c")
    t_out = sum(outs) / len(outs)
    e0 = temps[0] - t_out
    if abs(e0) < 0.3:
        return CalibrationEstimate(
            name="effective_ach",
            value=float("nan"),
            unit="1/h",
            method="fan_exchange",
            confidence="low",
            notes="start ΔT to outside too small",
        )

    # Choose evaluation sample: endpoint, or half-life sample if nearly settled.
    end_index = len(temps) - 1
    e_end = temps[end_index] - t_out
    ratio_end = abs(e_end) / abs(e0) if abs(e0) > 1e-12 else 1.0
    eval_index = end_index
    if e0 * e_end >= 0 and 0.0 < ratio_end < 0.15 and len(temps) >= 3:
        half_target = abs(e0) * 0.5
        best_i = None
        best_dist = math.inf
        for i in range(1, len(temps)):
            err = abs(temps[i] - t_out)
            # only while still approaching and same side as start
            if (temps[i] - t_out) * e0 <= 0:
                break
            dist = abs(err - half_target)
            if dist < best_dist and err < abs(e0):
                best_dist = dist
                best_i = i
        if best_i is not None and times[best_i] > times[0]:
            eval_index = best_i

    e1 = temps[eval_index] - t_out
    dt = max(1e-6, times[eval_index] - times[0])

    # Temperature error must shrink toward outside (same sign, |e1| < |e0|).
    if e0 * e1 < 0:
        return CalibrationEstimate(
            name="effective_ach",
            value=float("nan"),
            unit="1/h",
            method="fan_exchange",
            confidence="low",
            notes="temperature crossed outside setpoint; shorten window or reduce fan",
        )
    if abs(e1) >= abs(e0) - 1e-9:
        return CalibrationEstimate(
            name="effective_ach",
            value=float("nan"),
            unit="1/h",
            method="fan_exchange",
            confidence="low",
            notes="temperature did not approach outside; check fan/outside sensors",
        )
    ratio = abs(e1) / abs(e0)
    ratio = max(ratio, 1e-3)
    tau_inv_s = -math.log(ratio) / dt
    ach = tau_inv_s * 3600.0
    ach = max(0.05, min(60.0, ach))
    airflow = ach * max(0.05, growbox_volume_m3)
    confidence = "high" if 0.2 <= ratio <= 0.8 else "medium"
    window_note = (
        f"window t={dt:.0f}s (index {eval_index})"
        if eval_index != end_index
        else f"window t={dt:.0f}s"
    )
    return CalibrationEstimate(
        name="effective_ach",
        value=ach,
        unit="1/h",
        method="fan_exchange",
        confidence=confidence,
        notes=(
            f"≈ fan_max_airflow_m3_h {airflow:.1f} at full fan "
            f"(volume={growbox_volume_m3}, {window_note})"
        ),
    )


def estimate_humidifier_g_h(
    series: Mapping[str, Sequence[float]],
    *,
    growbox_volume_m3: float = 0.8,
    humidifier_command: float = 1.0,
) -> CalibrationEstimate:
    """Nameplate-equivalent g/h from ΔRH using T-aware moisture capacity."""
    rhs = _series_values(series, "air_humidity_pct")
    if "air_temperature_c" in series:
        temps = _series_values(series, "air_temperature_c")
        t_air = sum(temps) / len(temps)
    else:
        t_air = 25.0
    dt = _dt_s(series)
    delta_rh = rhs[-1] - rhs[0]
    capacity = air_moisture_capacity_g(growbox_volume_m3, t_air)
    if delta_rh < 1.0:
        return CalibrationEstimate(
            name="humidifier_effective_g_h",
            value=float("nan"),
            unit="g/h",
            method="humidifier_step",
            confidence="low",
            notes=f"RH did not rise enough (ΔRH={delta_rh:.1f} pp); check humidifier/fan",
        )
    # ΔRH% → grams: (ΔRH/100) * capacity
    grams = (delta_rh / 100.0) * capacity
    cmd = max(0.05, min(1.0, humidifier_command))
    g_h = (grams / max(1e-3, dt)) * 3600.0 / cmd
    g_h = max(1.0, min(500.0, g_h))
    return CalibrationEstimate(
        name="humidifier_effective_g_h",
        value=g_h,
        unit="g/h",
        method="humidifier_step",
        confidence="medium" if delta_rh >= 2.0 else "low",
        notes=f"ΔRH={delta_rh:.1f} pp, capacity≈{capacity:.1f} g at {t_air:.1f} °C",
    )


def estimate_co2_dose_ppm(
    *,
    co2_before_ppm: float,
    co2_after_ppm: float,
    pulses: float = 1.0,
) -> CalibrationEstimate:
    delta = float(co2_after_ppm) - float(co2_before_ppm)
    if delta < 5.0:
        return CalibrationEstimate(
            name="co2_dose_ppm_per_full_pulse",
            value=float("nan"),
            unit="ppm/pulse",
            method="co2_pulse",
            confidence="low",
            notes=f"CO₂ did not rise (Δppm={delta:.1f}); check doser/fan",
        )
    per = delta / max(1.0, pulses)
    per = max(5.0, min(800.0, per))
    return CalibrationEstimate(
        name="co2_dose_ppm_per_full_pulse",
        value=per,
        unit="ppm/pulse",
        method="co2_pulse",
        confidence="high" if delta >= 20.0 else "low",
        notes=f"Δppm={delta:.1f} over {pulses:g} pulse(s)",
    )


def estimate_substrate_capacity_ml(
    *,
    soil_before_pct: float,
    soil_after_pct: float,
    applied_ml: float,
    retained_fraction: float = 0.98,
) -> CalibrationEstimate:
    """Capacity from moisture rise: Δθ% ≈ retained_ml * 100 / capacity."""
    delta = float(soil_after_pct) - float(soil_before_pct)
    retained = max(0.0, applied_ml) * max(0.5, min(1.0, retained_fraction))
    if delta <= 0.2:
        return CalibrationEstimate(
            name="substrate_water_capacity_ml",
            value=float("nan"),
            unit="ml",
            method="irrigation_pulse",
            confidence="low",
            notes="soil moisture did not rise; check sensor/pulse",
        )
    capacity = retained * 100.0 / delta
    capacity = max(200.0, min(20_000.0, capacity))
    return CalibrationEstimate(
        name="substrate_water_capacity_ml",
        value=capacity,
        unit="ml",
        method="irrigation_pulse",
        confidence="medium",
        notes=f"Δθ={delta:.1f} pp for {retained:.0f} ml retained",
    )


def estimate_all_from_bundle(
    bundle: Mapping[str, Any],
    *,
    growbox_volume_m3: float = 0.8,
    heater_power_w: float = 180.0,
) -> list[CalibrationEstimate]:
    """Fit whatever series / scalars are present in a calibration bundle JSON."""
    estimates: list[CalibrationEstimate] = []
    if "heater_series" in bundle and isinstance(bundle["heater_series"], Mapping):
        estimates.append(
            estimate_thermal_mass_from_heater(
                bundle["heater_series"],
                heater_power_w=float(bundle.get("heater_power_w", heater_power_w)),
                heater_efficiency=float(bundle.get("heater_efficiency", 0.92)),
            )
        )
    if "fan_series" in bundle and isinstance(bundle["fan_series"], Mapping):
        estimates.append(
            estimate_effective_ach_from_fan(
                bundle["fan_series"],
                growbox_volume_m3=float(bundle.get("growbox_volume_m3", growbox_volume_m3)),
            )
        )
    if "humidifier_series" in bundle and isinstance(bundle["humidifier_series"], Mapping):
        estimates.append(
            estimate_humidifier_g_h(
                bundle["humidifier_series"],
                growbox_volume_m3=float(bundle.get("growbox_volume_m3", growbox_volume_m3)),
            )
        )
    if "co2_pulse" in bundle and isinstance(bundle["co2_pulse"], Mapping):
        pulse = bundle["co2_pulse"]
        estimates.append(
            estimate_co2_dose_ppm(
                co2_before_ppm=float(pulse["before_ppm"]),
                co2_after_ppm=float(pulse["after_ppm"]),
                pulses=float(pulse.get("pulses", 1.0)),
            )
        )
    if "irrigation_pulse" in bundle and isinstance(bundle["irrigation_pulse"], Mapping):
        irr = bundle["irrigation_pulse"]
        estimates.append(
            estimate_substrate_capacity_ml(
                soil_before_pct=float(irr["soil_before_pct"]),
                soil_after_pct=float(irr["soil_after_pct"]),
                applied_ml=float(irr["applied_ml"]),
            )
        )
    return estimates


def apply_estimates_to_scenario(
    scenario: Scenario,
    estimates: Sequence[CalibrationEstimate],
    *,
    pot_index: int = 0,
) -> Scenario:
    """Return a copy of ``scenario`` with finite estimates applied."""
    env = scenario.environment
    actuators = scenario.actuators
    pots = list(scenario.pots)

    by_name = {e.name: e for e in estimates if math.isfinite(e.value)}

    if "thermal_mass_j_per_k" in by_name:
        env = replace(env, thermal_mass_j_per_k=by_name["thermal_mass_j_per_k"].value)

    if "effective_ach" in by_name:
        ach = by_name["effective_ach"].value
        volume = max(0.05, env.growbox_volume_m3)
        # Split: keep a modest leak, put the rest on fan max airflow.
        leak = min(1.0, max(0.05, ach * 0.05))
        fan_ach = max(0.0, ach - leak)
        env = replace(env, air_leak_rate_ach=leak)
        actuators = replace(
            actuators,
            fan=replace(actuators.fan, max_airflow_m3_h=fan_ach * volume),
        )

    if "humidifier_effective_g_h" in by_name:
        g_h = by_name["humidifier_effective_g_h"].value
        # Simulator multiplies by vapor_delivery≈0.55 in build_chamber_forcing;
        # store nameplate so effective ≈ measured: nameplate = g_h / 0.55
        nameplate = g_h / 0.55
        actuators = replace(
            actuators,
            humidifier=replace(actuators.humidifier, max_output_g_h=nameplate),
        )

    if "co2_dose_ppm_per_full_pulse" in by_name:
        dose = by_name["co2_dose_ppm_per_full_pulse"].value
        actuators = replace(
            actuators,
            co2_doser=replace(
                actuators.co2_doser,
                available=True,
                dose_ppm_per_full_pulse=dose,
            ),
        )

    if "substrate_water_capacity_ml" in by_name and 0 <= pot_index < len(pots):
        capacity = by_name["substrate_water_capacity_ml"].value
        pot = pots[pot_index]
        cultivation = replace(pot.cultivation, substrate_water_capacity_ml=capacity)
        pots[pot_index] = replace(pot, cultivation=cultivation)

    return replace(
        scenario,
        environment=env,
        actuators=actuators,
        pots=tuple(pots),  # type: ignore[arg-type]
    )


def estimates_to_jsonable(estimates: Sequence[CalibrationEstimate]) -> list[dict[str, Any]]:
    return [e.as_dict() for e in estimates]
