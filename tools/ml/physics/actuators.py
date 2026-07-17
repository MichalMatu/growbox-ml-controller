"""Map contract [0, 1] actuator commands to chamber forcing terms.

See docs/simulator/SLOT_MAP.md.
"""

from __future__ import annotations

from dataclasses import dataclass

from .van_henten import U_CO2_MAX, U_HEAT_MAX, U_VENT_MAX


@dataclass(frozen=True)
class ChamberForcing:
    """Inputs for chamber climate step (mixed SI + S03-native)."""

    # S03-native controls for Van Henten backbone
    u_co2: float
    u_vent: float
    u_heat: float
    radiation: float  # d0 light / solar proxy
    # Extra SI fluxes not in classic Van Henten triple
    humidifier_g_s: float = 0.0
    dehumidifier_g_s: float = 0.0
    cooler_w: float = 0.0
    lights_w: float = 0.0


def build_chamber_forcing(
    *,
    heater: float,
    fan: float,
    humidifier: float,
    dehumidifier: float,
    cooler: float,
    co2_doser: float,
    lights_active: bool,
    heater_max_power_w: float,
    heater_efficiency: float,
    fan_max_airflow_m3_h: float,
    growbox_volume_m3: float,
    humidifier_max_output_g_h: float,
    dehumidifier_max_removal_g_h: float,
    cooler_max_cooling_w: float,
    co2_dose_ppm_per_full_pulse: float,
    lights_max_heat_w: float,
    lights_integrated: bool,
    # Optional: scale S03 heat channel by growbox heater watts vs reference
    heat_reference_w: float = 150.0,
) -> ChamberForcing:
    """Convert effective [0,1] commands + capabilities into forcing."""
    heater = _clip01(heater)
    fan = _clip01(fan)
    humidifier = _clip01(humidifier)
    dehumidifier = _clip01(dehumidifier)
    cooler = _clip01(cooler)
    co2_doser = _clip01(co2_doser)

    # Fan: map command × nameplate airflow to ACH, then to S03 vent units.
    # Reference (default profile): 90 m³/h in 0.8 m³ ≈ 112.5 ACH → u_vent = U_VENT_MAX at fan=1.
    volume = max(0.05, float(growbox_volume_m3))
    fan_ach = fan * max(0.0, float(fan_max_airflow_m3_h)) / volume
    ref_ach = 90.0 / 0.8
    u_vent = (fan_ach / ref_ach) * U_VENT_MAX if ref_ach > 0.0 else 0.0
    u_vent = min(u_vent, U_VENT_MAX * 4.0)

    # Heat: SI watts folded into S03 heat channel; residual cooler applied in simulator.
    heater_w = heater * max(0.0, heater_max_power_w) * _clip01(heater_efficiency)
    lights_w = max(0.0, lights_max_heat_w) if lights_active and lights_integrated else 0.0
    cooler_w = cooler * max(0.0, cooler_max_cooling_w)
    net_heat_w = heater_w + lights_w - cooler_w
    ref = max(1.0, heat_reference_w)
    u_heat = min(U_HEAT_MAX * 2.0, (max(0.0, net_heat_w) / ref) * U_HEAT_MAX)

    # CO2: S03 continuous supply + our pulse semantics (dose applied in simulator).
    u_co2 = co2_doser * U_CO2_MAX
    _ = co2_dose_ppm_per_full_pulse

    # Radiation proxy: modest daylight when lights on (S03 d0).
    radiation = 80.0 if lights_active else 15.0

    # Effective vapor delivery to bulk air is less than nameplate (wall losses, mixing).
    vapor_delivery = 0.55
    return ChamberForcing(
        u_co2=u_co2,
        u_vent=u_vent,
        u_heat=u_heat,
        radiation=radiation,
        humidifier_g_s=humidifier * max(0.0, humidifier_max_output_g_h) / 3600.0 * vapor_delivery,
        dehumidifier_g_s=dehumidifier
        * max(0.0, dehumidifier_max_removal_g_h)
        / 3600.0
        * vapor_delivery,
        cooler_w=cooler_w,
        lights_w=lights_w,
    )


def _clip01(value: float) -> float:
    return min(1.0, max(0.0, float(value)))
