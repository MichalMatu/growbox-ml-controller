"""Deterministic climate-v6 rule policy, arbitration and safety gates.

The rule policy is the explicit non-ML reference/fallback for the climate MVP.
Arbitration and safety are deliberately separate from policy selection so the
same gates are applied to rule, teacher and ML commands in closed-loop tests.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from .climate_input import (
    DEFAULT_SENSOR_TIMEOUT_MS,
    ClimateTargets,
    HumidityControlMode,
    MeasurementStatus,
    air_vpd_kpa,
)
from .climate_scenarios import ClimateProfile
from .climate_simulator import ClimateAction, ClimateScenario, ClimateState
from .physics.psychrometrics import sat_vapour_pressure_pa


@dataclass(frozen=True)
class ClimateRuleConfig:
    temperature_deadband_c: float = 0.3
    humidity_deadband_pct: float = 2.0
    vpd_deadband_kpa: float = 0.08
    co2_deadband_ppm: float = 50.0
    temperature_full_scale_c: float = 4.0
    humidity_full_scale_pct: float = 18.0
    vpd_full_scale_kpa: float = 0.7
    co2_full_scale_ppm: float = 500.0
    outside_improvement_margin: float = 0.08


@dataclass(frozen=True)
class ClimateSafetyLimits:
    minimum_temperature_c: float = 8.0
    maximum_temperature_c: float = 42.0
    maximum_humidity_pct: float = 95.0
    maximum_co2_ppm: float = 1_800.0


@dataclass(frozen=True)
class ClimateGateResult:
    action: ClimateAction
    interventions: tuple[str, ...] = ()


def _clip(value: float) -> float:
    return min(1.0, max(0.0, float(value)))


ML_REQUEST_DEADZONE = 0.05


def apply_ml_request_deadzone(
    action: ClimateAction, threshold: float = ML_REQUEST_DEADZONE
) -> ClimateAction:
    threshold = float(threshold)
    if not 0.0 <= threshold < 1.0:
        raise ValueError("ML request dead-zone must be in [0, 1)")
    values = {
        name: 0.0 if float(value) <= threshold else float(value)
        for name, value in action.clipped().as_dict().items()
    }
    return ClimateAction.from_mapping(values).clipped()


def _level(error: float, deadband: float, full_scale: float) -> float:
    excess = max(0.0, abs(float(error)) - float(deadband))
    return _clip(excess / max(1.0e-9, float(full_scale)))


def _absolute_humidity_g_m3(temperature_c: float, relative_humidity_pct: float) -> float:
    humidity = min(100.0, max(0.0, float(relative_humidity_pct)))
    vapor_pressure_hpa = sat_vapour_pressure_pa(temperature_c) / 100.0 * humidity / 100.0
    return 216.7 * vapor_pressure_hpa / (float(temperature_c) + 273.15)


def _usable(
    name: str,
    value: float,
    statuses: Mapping[str, MeasurementStatus],
    timeout_ms: int,
) -> bool:
    return statuses.get(name, MeasurementStatus()).usable(value, timeout_ms)


def _humidity_error(
    temperature_c: float,
    humidity_pct: float,
    targets: ClimateTargets,
    mode: HumidityControlMode,
) -> tuple[float, float]:
    if mode == "RH":
        return humidity_pct - targets.relative_humidity_pct, 20.0
    if mode == "VPD":
        return air_vpd_kpa(temperature_c, humidity_pct) - targets.air_vpd_kpa, 0.7
    raise ValueError(f"unsupported humidity mode: {mode!r}")


class ClimateRulePolicy:
    def __init__(self, config: ClimateRuleConfig | None = None) -> None:
        self.config = config or ClimateRuleConfig()

    def choose(
        self,
        scenario: ClimateScenario,
        state: ClimateState,
        profile: ClimateProfile,
        *,
        status: Mapping[str, MeasurementStatus] | None = None,
        sensor_timeout_ms: int = DEFAULT_SENSOR_TIMEOUT_MS,
    ) -> ClimateAction:
        statuses = status or {}
        timeout = int(sensor_timeout_ms)
        temperature_ok = _usable("air_temperature_c", state.air_temperature_c, statuses, timeout)
        humidity_ok = _usable(
            "relative_humidity_pct", state.relative_humidity_pct, statuses, timeout
        )
        if not temperature_ok or not humidity_ok:
            return ClimateAction()

        cfg = self.config
        targets = profile.targets
        caps = scenario.actuators
        values = {name: 0.0 for name in ClimateAction().as_dict()}

        temperature_error = state.air_temperature_c - targets.air_temperature_c
        temperature_level = _level(
            temperature_error,
            cfg.temperature_deadband_c,
            cfg.temperature_full_scale_c,
        )
        if temperature_error < -cfg.temperature_deadband_c and caps.heater.available:
            values["heater"] = temperature_level
        elif temperature_error > cfg.temperature_deadband_c and caps.cooler.available:
            values["cooler"] = temperature_level

        humidity_error, humidity_scale = _humidity_error(
            state.air_temperature_c,
            state.relative_humidity_pct,
            targets,
            profile.humidity_control_mode,
        )
        if profile.humidity_control_mode == "RH":
            humidity_deadband = cfg.humidity_deadband_pct
            humidity_full_scale = cfg.humidity_full_scale_pct
            too_dry = humidity_error < -humidity_deadband
            too_humid = humidity_error > humidity_deadband
        else:
            humidity_deadband = cfg.vpd_deadband_kpa
            humidity_full_scale = cfg.vpd_full_scale_kpa
            # High VPD means too dry; low VPD means too humid.
            too_dry = humidity_error > humidity_deadband
            too_humid = humidity_error < -humidity_deadband
        humidity_level = _level(humidity_error, humidity_deadband, humidity_full_scale)
        if too_dry and caps.humidifier.available:
            values["humidifier"] = humidity_level
        elif too_humid and caps.dehumidifier.available:
            values["dehumidifier"] = humidity_level

        outside_temperature_ok = _usable(
            "outside_temperature_c", state.outside_temperature_c, statuses, timeout
        )
        outside_humidity_ok = _usable(
            "outside_humidity_pct", state.outside_humidity_pct, statuses, timeout
        )
        if caps.exhaust_fan.available:
            if outside_temperature_ok:
                mix_fraction = 0.20
                mixed_temperature = state.air_temperature_c + mix_fraction * (
                    state.outside_temperature_c - state.air_temperature_c
                )
                current_temp_score = abs(temperature_error) / 5.0
                mixed_temp_score = abs(mixed_temperature - targets.air_temperature_c) / 5.0
                temperature_improvement = current_temp_score - mixed_temp_score
                if temperature_improvement > cfg.outside_improvement_margin:
                    values["exhaust_fan"] = max(
                        values["exhaust_fan"], _clip(temperature_improvement / 0.75)
                    )

            if too_humid and outside_temperature_ok and outside_humidity_ok:
                inside_absolute_humidity = _absolute_humidity_g_m3(
                    state.air_temperature_c, state.relative_humidity_pct
                )
                intake_absolute_humidity = _absolute_humidity_g_m3(
                    state.outside_temperature_c, state.outside_humidity_pct
                )
                drying_gap = inside_absolute_humidity - intake_absolute_humidity
                if drying_gap > 0.5:
                    drying_benefit = _level(drying_gap, 0.5, 3.0)
                    values["exhaust_fan"] = max(
                        values["exhaust_fan"], min(humidity_level, drying_benefit)
                    )

        co2_ok = _usable("co2_ppm", state.co2_ppm, statuses, timeout)
        if targets.co2_enabled and co2_ok and caps.co2_doser.available:
            co2_error = targets.co2_ppm - state.co2_ppm
            if co2_error > cfg.co2_deadband_ppm:
                values["co2_doser"] = _level(
                    co2_error,
                    cfg.co2_deadband_ppm,
                    cfg.co2_full_scale_ppm,
                )

        return ClimateAction.from_mapping(values).clipped()


def arbitrate_climate_action(
    action: ClimateAction,
    scenario: ClimateScenario,
) -> ClimateGateResult:
    values = action.clipped().as_dict()
    interventions: list[str] = []
    caps = scenario.actuators
    availability = {
        "heater": caps.heater.available,
        "cooler": caps.cooler.available,
        "exhaust_fan": caps.exhaust_fan.available,
        "humidifier": caps.humidifier.available,
        "dehumidifier": caps.dehumidifier.available,
        "co2_doser": caps.co2_doser.available,
    }
    for name, available in availability.items():
        if not available and values[name] > 0.0:
            values[name] = 0.0
            interventions.append(f"unavailable:{name}")

    def resolve_opposition(left: str, right: str) -> None:
        if values[left] <= 0.0 or values[right] <= 0.0:
            return
        if values[left] >= values[right]:
            values[right] = 0.0
        else:
            values[left] = 0.0
        interventions.append(f"opposition:{left}:{right}")

    resolve_opposition("heater", "cooler")
    resolve_opposition("humidifier", "dehumidifier")
    return ClimateGateResult(ClimateAction.from_mapping(values).clipped(), tuple(interventions))


def apply_climate_safety(
    action: ClimateAction,
    scenario: ClimateScenario,
    state: ClimateState,
    profile: ClimateProfile,
    *,
    status: Mapping[str, MeasurementStatus] | None = None,
    sensor_timeout_ms: int = DEFAULT_SENSOR_TIMEOUT_MS,
    limits: ClimateSafetyLimits | None = None,
) -> ClimateGateResult:
    statuses = status or {}
    timeout = int(sensor_timeout_ms)
    limits = limits or ClimateSafetyLimits()
    values = action.clipped().as_dict()
    interventions: list[str] = []

    temperature_ok = _usable("air_temperature_c", state.air_temperature_c, statuses, timeout)
    humidity_ok = _usable("relative_humidity_pct", state.relative_humidity_pct, statuses, timeout)
    if not temperature_ok or not humidity_ok:
        if any(value > 0.0 for value in values.values()):
            interventions.append("required_sensor_unusable")
        return ClimateGateResult(ClimateAction(), tuple(interventions))

    co2_ok = _usable("co2_ppm", state.co2_ppm, statuses, timeout)
    if (not profile.targets.co2_enabled or not co2_ok) and values["co2_doser"] > 0.0:
        values["co2_doser"] = 0.0
        interventions.append("co2_dosing_inhibited")

    caps = scenario.actuators
    if state.air_temperature_c >= limits.maximum_temperature_c:
        if values["heater"] > 0.0 or values["humidifier"] > 0.0 or values["co2_doser"] > 0.0:
            interventions.append("high_temperature")
        values["heater"] = 0.0
        values["humidifier"] = 0.0
        values["co2_doser"] = 0.0
        values["cooler"] = 1.0 if caps.cooler.available else 0.0
        values["exhaust_fan"] = 1.0 if caps.exhaust_fan.available else 0.0
    elif state.air_temperature_c <= limits.minimum_temperature_c:
        if values["cooler"] > 0.0 or values["exhaust_fan"] > 0.0:
            interventions.append("low_temperature")
        values["cooler"] = 0.0
        values["exhaust_fan"] = 0.0
        values["heater"] = 1.0 if caps.heater.available else 0.0

    if state.relative_humidity_pct >= limits.maximum_humidity_pct:
        if values["humidifier"] > 0.0:
            interventions.append("high_humidity")
        values["humidifier"] = 0.0
        values["dehumidifier"] = 1.0 if caps.dehumidifier.available else 0.0
        values["co2_doser"] = 0.0

    if co2_ok and state.co2_ppm >= limits.maximum_co2_ppm:
        if values["co2_doser"] > 0.0:
            interventions.append("high_co2")
        values["co2_doser"] = 0.0
        if caps.exhaust_fan.available:
            values["exhaust_fan"] = max(values["exhaust_fan"], 1.0)

    return ClimateGateResult(ClimateAction.from_mapping(values).clipped(), tuple(interventions))


def hard_limit_violations(
    state: ClimateState,
    *,
    limits: ClimateSafetyLimits | None = None,
) -> tuple[str, ...]:
    limits = limits or ClimateSafetyLimits()
    violations: list[str] = []
    if state.air_temperature_c < limits.minimum_temperature_c:
        violations.append("temperature_low")
    if state.air_temperature_c > limits.maximum_temperature_c:
        violations.append("temperature_high")
    if state.relative_humidity_pct > limits.maximum_humidity_pct:
        violations.append("humidity_high")
    if state.co2_ppm > limits.maximum_co2_ppm:
        violations.append("co2_high")
    return tuple(violations)


__all__ = [
    "ClimateGateResult",
    "ClimateRuleConfig",
    "ClimateRulePolicy",
    "ClimateSafetyLimits",
    "ML_REQUEST_DEADZONE",
    "apply_climate_safety",
    "apply_ml_request_deadzone",
    "arbitrate_climate_action",
    "hard_limit_violations",
]
