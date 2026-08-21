"""Lightweight psychrometrics for growbox humidity capacity.

Uses Magnus/Tetens saturation vapour pressure. Replaces the fixed
``20 g/m³ ≈ 100 %RH`` span with a temperature-aware absolute humidity capacity
so humidifier/irrigation → RH scales realistically with chamber T.

Not a full moist-air library — only the helpers used by the training simulator.
"""

from __future__ import annotations

import math


def clamp(value: float, low: float, high: float) -> float:
    return min(high, max(low, float(value)))


def sat_vapour_pressure_pa(temperature_c: float) -> float:
    """Saturation vapour pressure of water [Pa] (Magnus / Tetens over liquid water)."""
    t = clamp(temperature_c, -40.0, 80.0)
    return 610.94 * math.exp((17.625 * t) / (t + 243.04))


def sat_absolute_humidity_g_m3(temperature_c: float) -> float:
    """Saturated water vapour density [g/m³] at air temperature."""
    t_k = clamp(temperature_c, -40.0, 80.0) + 273.15
    # Ideal gas: ρ = p * M / (R * T); M_water = 0.018015 kg/mol, R = 8.314 J/mol/K
    density_kg_m3 = sat_vapour_pressure_pa(temperature_c) * 0.018015 / (8.314462618 * t_k)
    return max(0.1, density_kg_m3 * 1000.0)


def air_moisture_capacity_g(
    growbox_volume_m3: float,
    air_temperature_c: float = 25.0,
) -> float:
    """Grams of vapour corresponding to a 0→100 %RH swing at the given T.

    Approximately ρ_sat(T) * V. Used to convert g/s humidification into RH
    percentage points.
    """
    volume = max(0.05, float(growbox_volume_m3))
    return max(1.0, sat_absolute_humidity_g_m3(air_temperature_c) * volume)


def water_ml_to_humidity_pp(
    water_ml: float,
    *,
    growbox_volume_m3: float,
    air_temperature_c: float = 25.0,
    fraction_to_vapor: float = 1.0,
) -> float:
    """Convert liquid water [ml ≈ g] added as vapour into approximate RH pp."""
    capacity = air_moisture_capacity_g(growbox_volume_m3, air_temperature_c)
    vapor_g = max(0.0, float(water_ml)) * clamp(fraction_to_vapor, 0.0, 1.0)
    return vapor_g * 100.0 / capacity
