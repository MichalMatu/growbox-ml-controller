"""Per-pot substrate water and temperature (Tier B).

Lumped single water pool + thermal mass per pot. Chamber moisture coupling via
evaporation/transpiration of liquid water into air (order-of-magnitude growbox
scale). Inspired by GES mat node (soil T capacity) and Van Henten transpiration
drivers (vapor deficit, canopy strength) — see docs/simulator/FORMULAS.md.

Not a full Richards / dual-porosity soil model.
"""

from __future__ import annotations

from dataclasses import dataclass


def _clamp(value: float, low: float, high: float) -> float:
    return min(high, max(low, float(value)))


@dataclass(frozen=True)
class PotPhysicsConfig:
    available: bool
    soil_moisture_valid: bool
    soil_temperature_valid: bool
    pot_volume_l: float
    substrate_water_capacity_ml: float
    transpiration_factor: float
    irrigation_available: bool
    irrigation_flow_ml_s: float
    irrigation_maximum_pulse_s: float
    heat_mat_available: bool
    heat_mat_max_power_w: float


@dataclass
class PotPhysicsState:
    soil_moisture_pct: float
    soil_temperature_c: float


@dataclass(frozen=True)
class PotStepResult:
    soil_moisture_pct: float
    soil_temperature_c: float
    # Liquid water that left the pot and entered chamber air [ml] over this step
    water_to_air_ml: float
    # Instant humidity boost from irrigation splash/evap of free water [ml]
    irrigation_free_water_ml: float
    applied_irrigation_ml: float


def apply_irrigation_pulse(
    pot: PotPhysicsState,
    config: PotPhysicsConfig,
    *,
    command_0_1: float,
    nutrient_solution_temperature_c: float,
    irrigation_ready: bool,
) -> tuple[PotPhysicsState, float, float]:
    """Apply one discrete irrigation command.

    Returns (updated pot, applied_ml, free_water_ml_to_air).
    """
    if (
        not config.available
        or not config.irrigation_available
        or command_0_1 <= 0.0
        or not irrigation_ready
    ):
        return pot, 0.0, 0.0

    pulse_s = _clamp(command_0_1, 0.0, 1.0) * max(0.0, config.irrigation_maximum_pulse_s)
    applied_ml = max(0.0, config.irrigation_flow_ml_s) * pulse_s
    if applied_ml <= 0.0:
        return pot, 0.0, 0.0

    capacity = max(1.0, config.substrate_water_capacity_ml)
    # Most water enters the substrate; a small surface/splash fraction humidifies air.
    # ~2% free vapor keeps small growboxes from saturating on a single pulse.
    retained = 0.98
    free_water_ml = applied_ml * (1.0 - retained)
    into_substrate_ml = applied_ml * retained

    moisture = pot.soil_moisture_pct + into_substrate_ml * 100.0 / capacity
    moisture = _clamp(moisture, 0.0, 100.0)

    soil_t = pot.soil_temperature_c
    if config.soil_temperature_valid and into_substrate_ml > 0.0:
        mix = _clamp(into_substrate_ml / capacity, 0.0, 0.40)
        soil_t = soil_t + (nutrient_solution_temperature_c - soil_t) * mix
        soil_t = _clamp(soil_t, -10.0, 50.0)

    return (
        PotPhysicsState(soil_moisture_pct=moisture, soil_temperature_c=soil_t),
        applied_ml,
        free_water_ml,
    )


def evaporation_ml_s(
    pot: PotPhysicsState,
    config: PotPhysicsConfig,
    *,
    air_temperature_c: float,
    air_humidity_pct: float,
) -> float:
    """Liquid water loss rate from pot to chamber [ml/s]."""
    if not config.available or not config.soil_moisture_valid:
        return 0.0
    if pot.soil_moisture_pct <= 1.0:
        return 0.0

    vapor_deficit = _clamp((100.0 - air_humidity_pct) / 55.0, 0.05, 1.8)
    soil_factor = _clamp(pot.soil_moisture_pct / 50.0, 0.05, 1.4)
    # Dry-down slows as soil dries (non-linear).
    dryness_curve = soil_factor**1.25

    soil_temp_factor = 1.0
    if config.soil_temperature_valid:
        soil_temp_factor = _clamp((pot.soil_temperature_c - 4.0) / 20.0, 0.15, 2.0)
    air_temp_factor = _clamp((air_temperature_c - 4.0) / 22.0, 0.15, 2.0)

    # Base evaporation ~1–4 ml/h for a 12 L pot at mid moisture (growbox scale).
    base_ml_s = 0.00028 * max(0.4, config.pot_volume_l)
    return (
        base_ml_s
        * max(0.0, config.transpiration_factor)
        * vapor_deficit
        * dryness_curve
        * soil_temp_factor
        * air_temp_factor
    )


def step_soil_temperature(
    pot: PotPhysicsState,
    config: PotPhysicsConfig,
    *,
    air_temperature_c: float,
    heat_mat_command_0_1: float,
    dt_s: float,
) -> float:
    """Advance soil temperature [°C]."""
    if not config.available or not config.soil_temperature_valid:
        return pot.soil_temperature_c

    # ~ soil/water mix heat capacity; GES mat c_m is area-based — we use pot volume.
    soil_thermal_mass_j_k = max(2_500.0, config.pot_volume_l * 2_200.0)
    heat_mat_w = 0.0
    if config.heat_mat_available:
        heat_mat_w = _clamp(heat_mat_command_0_1, 0.0, 1.0) * max(0.0, config.heat_mat_max_power_w)

    # Air ↔ soil coupling (W/K scale folded into conductance).
    # Slightly stronger than Tier A so mats and air interact visibly.
    ua_air = 0.55 + 0.04 * max(0.5, config.pot_volume_l)
    air_coupling_w = ua_air * (air_temperature_c - pot.soil_temperature_c)

    # Wet soil conducts better to air (small boost).
    wet_boost = 1.0 + 0.25 * _clamp(pot.soil_moisture_pct / 100.0, 0.0, 1.0)
    delta = (heat_mat_w + air_coupling_w * wet_boost) * dt_s / soil_thermal_mass_j_k
    return _clamp(pot.soil_temperature_c + delta, -10.0, 50.0)


def step_pot(
    pot: PotPhysicsState,
    config: PotPhysicsConfig,
    *,
    air_temperature_c: float,
    air_humidity_pct: float,
    heat_mat_command_0_1: float,
    dt_s: float,
    irrigation_command_0_1: float = 0.0,
    nutrient_solution_temperature_c: float = 20.0,
    irrigation_ready: bool = True,
) -> PotStepResult:
    """Full pot step: optional irrigation, evaporation, soil temperature."""
    pot_after_irr, applied_ml, free_ml = apply_irrigation_pulse(
        pot,
        config,
        command_0_1=irrigation_command_0_1,
        nutrient_solution_temperature_c=nutrient_solution_temperature_c,
        irrigation_ready=irrigation_ready,
    )

    moisture = pot_after_irr.soil_moisture_pct
    soil_t = pot_after_irr.soil_temperature_c
    water_to_air = free_ml

    if config.available and config.soil_moisture_valid and dt_s > 0.0:
        evap_s = evaporation_ml_s(
            PotPhysicsState(moisture, soil_t),
            config,
            air_temperature_c=air_temperature_c,
            air_humidity_pct=air_humidity_pct,
        )
        capacity = max(1.0, config.substrate_water_capacity_ml)
        lost_ml = min(evap_s * dt_s, moisture / 100.0 * capacity)
        moisture = _clamp(moisture - lost_ml * 100.0 / capacity, 0.0, 100.0)
        water_to_air += lost_ml

    soil_t = step_soil_temperature(
        PotPhysicsState(moisture, soil_t),
        config,
        air_temperature_c=air_temperature_c,
        heat_mat_command_0_1=heat_mat_command_0_1,
        dt_s=dt_s,
    )

    return PotStepResult(
        soil_moisture_pct=moisture,
        soil_temperature_c=soil_t,
        water_to_air_ml=water_to_air,
        irrigation_free_water_ml=free_ml,
        applied_irrigation_ml=applied_ml,
    )


def water_ml_to_humidity_pp(
    water_ml: float, *, growbox_volume_m3: float, fraction_to_vapor: float = 1.0
) -> float:
    """Convert liquid water [ml] added as vapor into approximate RH percentage points."""
    volume = max(0.05, growbox_volume_m3)
    # ~20 g absolute humidity span ≈ 100 %RH lumped capacity (same as chamber helpers).
    air_capacity_g = max(1.0, volume * 20.0)
    vapor_g = max(0.0, water_ml) * _clamp(fraction_to_vapor, 0.0, 1.0)
    return vapor_g * 100.0 / air_capacity_g
