"""Climate-only simulator for the MVP v6 controller contract.

This module intentionally lives beside the historical v4 pot simulator during
migration. It has no pot, irrigation or nutrient state and exposes only the six
ML-controlled climate requests. Light is scheduled context, not an ML output.

The Van Henten backbone is retained for coupled ventilation, CO2, humidity,
transpiration and plant-light effects. Climate-v6 disables three built-in terms
that would otherwise be counted twice (baseline leakage, envelope heat loss and
radiation-to-temperature gain) and supplies those effects exactly once from the
explicit growbox configuration below.
"""

from __future__ import annotations

import copy
import math
from collections.abc import Mapping
from dataclasses import dataclass, field

import numpy as np

from .physics.psychrometrics import sat_absolute_humidity_g_m3
from .physics.van_henten import (
    P_SCALE,
    U_VENT_MAX,
    VanHentenParams,
    step_chamber_van_henten,
)

CLIMATE_OUTPUT_NAMES = (
    "heater",
    "cooler",
    "exhaust_fan",
    "humidifier",
    "dehumidifier",
    "co2_doser",
)

_REFERENCE_EXHAUST_ACH = 90.0 / 0.8
_MIN_VOLUME_M3 = 0.05
_MIN_THERMAL_MASS_J_K = 5_000.0
_MIN_CO2_PPM = 250.0
_MAX_CO2_PPM = 5_000.0


def _clamp(value: float, low: float, high: float) -> float:
    return min(high, max(low, float(value)))


@dataclass(frozen=True)
class ClimateEnvironmentParameters:
    growbox_volume_m3: float = 0.8
    thermal_mass_j_per_k: float = 35_000.0
    heat_loss_w_per_k: float = 7.0
    air_leak_rate_ach: float = 0.25
    outside_co2_ppm: float = 420.0
    crop_dry_weight: float = 0.0025
    lights_max_heat_w: float = 120.0
    radiation_lights_off: float = 15.0
    radiation_lights_full: float = 80.0


@dataclass(frozen=True)
class HeaterCapabilities:
    available: bool = True
    max_power_w: float = 180.0
    efficiency: float = 0.92


@dataclass(frozen=True)
class CoolerCapabilities:
    available: bool = False
    max_cooling_w: float = 200.0


@dataclass(frozen=True)
class ExhaustFanCapabilities:
    available: bool = True
    max_airflow_m3_h: float = 90.0
    minimum_command: float = 0.0


@dataclass(frozen=True)
class HumidifierCapabilities:
    available: bool = True
    max_output_g_h: float = 110.0
    delivery_efficiency: float = 0.55


@dataclass(frozen=True)
class DehumidifierCapabilities:
    available: bool = False
    max_removal_g_h: float = 80.0
    delivery_efficiency: float = 0.55


@dataclass(frozen=True)
class Co2DoserCapabilities:
    """Effective maximum bulk-air CO2 increase rate.

    ``max_injection_ppm_s`` is an intentionally explicit rate, not a per-step
    pulse. Hardware may later derive this calibrated equivalent from valve flow,
    chamber volume and duty cycle.
    """

    available: bool = False
    max_injection_ppm_s: float = 8.0


@dataclass(frozen=True)
class ClimateActuatorCapabilities:
    heater: HeaterCapabilities = field(default_factory=HeaterCapabilities)
    cooler: CoolerCapabilities = field(default_factory=CoolerCapabilities)
    exhaust_fan: ExhaustFanCapabilities = field(default_factory=ExhaustFanCapabilities)
    humidifier: HumidifierCapabilities = field(default_factory=HumidifierCapabilities)
    dehumidifier: DehumidifierCapabilities = field(default_factory=DehumidifierCapabilities)
    co2_doser: Co2DoserCapabilities = field(default_factory=Co2DoserCapabilities)


@dataclass(frozen=True)
class ClimateResponseLag:
    heater_s: float = 35.0
    cooler_s: float = 45.0
    exhaust_fan_s: float = 8.0
    humidifier_s: float = 20.0
    dehumidifier_s: float = 20.0
    co2_doser_s: float = 0.0


@dataclass(frozen=True)
class ClimateAction:
    heater: float = 0.0
    cooler: float = 0.0
    exhaust_fan: float = 0.0
    humidifier: float = 0.0
    dehumidifier: float = 0.0
    co2_doser: float = 0.0

    def as_tuple(self) -> tuple[float, ...]:
        return tuple(getattr(self, name) for name in CLIMATE_OUTPUT_NAMES)

    def as_dict(self) -> dict[str, float]:
        return dict(zip(CLIMATE_OUTPUT_NAMES, self.as_tuple(), strict=True))

    def clipped(self) -> ClimateAction:
        return ClimateAction(*(_clamp(value, 0.0, 1.0) for value in self.as_tuple()))

    @classmethod
    def from_mapping(cls, values: Mapping[str, float]) -> ClimateAction:
        return cls(**{name: float(values.get(name, 0.0)) for name in CLIMATE_OUTPUT_NAMES})


@dataclass
class ClimateState:
    air_temperature_c: float = 24.0
    relative_humidity_pct: float = 60.0
    co2_ppm: float = 700.0
    outside_temperature_c: float = 20.0
    outside_humidity_pct: float = 50.0
    light_level: float = 0.0


@dataclass(frozen=True)
class ClimateScenario:
    scenario_id: str = "climate-default"
    seed: int = 1
    initial_state: ClimateState = field(default_factory=ClimateState)
    environment: ClimateEnvironmentParameters = field(default_factory=ClimateEnvironmentParameters)
    actuators: ClimateActuatorCapabilities = field(default_factory=ClimateActuatorCapabilities)
    response_lag: ClimateResponseLag = field(default_factory=ClimateResponseLag)
    timestep_s: float = 10.0


class ClimateSimulator:
    """Deterministic, climate-only closed-loop simulator for contract v6."""

    def __init__(self, scenario: ClimateScenario, *, seed: int | None = None):
        self.scenario = copy.deepcopy(scenario)
        self.state = copy.deepcopy(scenario.initial_state)
        self.seed = int(scenario.seed if seed is None else seed)
        self.rng = np.random.default_rng(self.seed)
        self.elapsed_s = 0.0
        self.effective_action = ClimateAction()
        self.previous_command = ClimateAction()
        self._van_henten_params = self._build_van_henten_params()

    def reset(self, *, seed: int | None = None) -> ClimateState:
        if seed is not None:
            self.seed = int(seed)
        self.rng = np.random.default_rng(self.seed)
        self.state = copy.deepcopy(self.scenario.initial_state)
        self.elapsed_s = 0.0
        self.effective_action = ClimateAction()
        self.previous_command = ClimateAction()
        return copy.deepcopy(self.state)

    def clone(self) -> ClimateSimulator:
        other = ClimateSimulator(self.scenario, seed=self.seed)
        other.state = copy.deepcopy(self.state)
        other.elapsed_s = self.elapsed_s
        other.effective_action = self.effective_action
        other.previous_command = self.previous_command
        other.rng.bit_generator.state = copy.deepcopy(self.rng.bit_generator.state)
        return other

    def set_light_level(self, level: float) -> None:
        self.state.light_level = _clamp(level, 0.0, 1.0)

    def observe(self, *, add_sensor_noise: bool = False) -> ClimateState:
        observed = copy.deepcopy(self.state)
        if add_sensor_noise:
            observed.air_temperature_c += float(self.rng.normal(0.0, 0.08))
            observed.relative_humidity_pct += float(self.rng.normal(0.0, 0.25))
            observed.co2_ppm += float(self.rng.normal(0.0, 4.0))
        observed.relative_humidity_pct = _clamp(observed.relative_humidity_pct, 0.0, 100.0)
        observed.co2_ppm = _clamp(observed.co2_ppm, _MIN_CO2_PPM, _MAX_CO2_PPM)
        return observed

    def step(
        self,
        action: ClimateAction,
        timestep_s: float | None = None,
        *,
        light_level: float | None = None,
        add_sensor_noise: bool = False,
    ) -> ClimateState:
        dt = float(self.scenario.timestep_s if timestep_s is None else timestep_s)
        if not math.isfinite(dt) or dt <= 0.0:
            raise ValueError("timestep_s must be finite and positive")
        if light_level is not None:
            self.set_light_level(light_level)

        command = self._mask_unavailable(action.clipped())
        self._advance_effective_action(command, dt)
        self._advance_physics(dt)
        self.elapsed_s += dt
        self.previous_command = command
        return self.observe(add_sensor_noise=add_sensor_noise)

    @staticmethod
    def _lag(previous: float, requested: float, dt: float, time_constant: float) -> float:
        if time_constant <= 0.0:
            return requested
        alpha = 1.0 - math.exp(-dt / time_constant)
        return previous + alpha * (requested - previous)

    def _mask_unavailable(self, command: ClimateAction) -> ClimateAction:
        caps = self.scenario.actuators
        values = command.as_dict()
        values["heater"] = values["heater"] if caps.heater.available else 0.0
        values["cooler"] = values["cooler"] if caps.cooler.available else 0.0
        if caps.exhaust_fan.available:
            fan = values["exhaust_fan"]
            if 0.0 < fan < caps.exhaust_fan.minimum_command:
                fan = 0.0
            values["exhaust_fan"] = fan
        else:
            values["exhaust_fan"] = 0.0
        values["humidifier"] = values["humidifier"] if caps.humidifier.available else 0.0
        values["dehumidifier"] = values["dehumidifier"] if caps.dehumidifier.available else 0.0
        values["co2_doser"] = values["co2_doser"] if caps.co2_doser.available else 0.0
        return ClimateAction.from_mapping(values)

    def _advance_effective_action(self, command: ClimateAction, dt: float) -> None:
        lag = self.scenario.response_lag
        old = self.effective_action
        self.effective_action = ClimateAction(
            heater=self._lag(old.heater, command.heater, dt, lag.heater_s),
            cooler=self._lag(old.cooler, command.cooler, dt, lag.cooler_s),
            exhaust_fan=self._lag(old.exhaust_fan, command.exhaust_fan, dt, lag.exhaust_fan_s),
            humidifier=self._lag(old.humidifier, command.humidifier, dt, lag.humidifier_s),
            dehumidifier=self._lag(old.dehumidifier, command.dehumidifier, dt, lag.dehumidifier_s),
            co2_doser=self._lag(old.co2_doser, command.co2_doser, dt, lag.co2_doser_s),
        )

    def _build_van_henten_params(self) -> VanHentenParams:
        env = self.scenario.environment
        p = np.ones(P_SCALE.size, dtype=np.float64)

        # p10: built-in baseline leakage. Climate-v6 supplies configured ACH once.
        p[10] = 0.0
        # The temperature equation scales with p15 / P_SCALE[15]. Configure it as
        # 1 / explicit thermal mass instead of retaining a hidden fixed capacity.
        thermal_mass = max(_MIN_THERMAL_MASS_J_K, float(env.thermal_mass_j_per_k))
        p[15] = P_SCALE[15] / thermal_mass
        # p17: built-in envelope heat loss. Climate-v6 applies configured W/K once.
        p[17] = 0.0
        # p18: radiation heat gain. Radiation remains available to plant equations;
        # lamp heat is applied once below in explicit watts.
        p[18] = 0.0
        return VanHentenParams(p=p)

    def _vent_forcing(self) -> float:
        env = self.scenario.environment
        caps = self.scenario.actuators.exhaust_fan
        volume = max(_MIN_VOLUME_M3, float(env.growbox_volume_m3))
        exhaust_ach = self.effective_action.exhaust_fan * max(0.0, caps.max_airflow_m3_h) / volume
        total_ach = max(0.0, float(env.air_leak_rate_ach)) + exhaust_ach
        u_vent = total_ach / _REFERENCE_EXHAUST_ACH * U_VENT_MAX
        return min(u_vent, U_VENT_MAX * 4.0)

    def _radiation(self) -> float:
        env = self.scenario.environment
        level = _clamp(self.state.light_level, 0.0, 1.0)
        off = max(0.0, float(env.radiation_lights_off))
        full = max(off, float(env.radiation_lights_full))
        return off + level * (full - off)

    def _advance_physics(self, dt: float) -> None:
        env = self.scenario.environment
        caps = self.scenario.actuators
        state = self.state
        effective = self.effective_action
        volume = max(_MIN_VOLUME_M3, float(env.growbox_volume_m3))
        thermal_mass = max(_MIN_THERMAL_MASS_J_K, float(env.thermal_mass_j_per_k))

        vh_t, vh_rh, vh_co2, _ = step_chamber_van_henten(
            air_temperature_c=state.air_temperature_c,
            air_humidity_pct=state.relative_humidity_pct,
            co2_ppm=state.co2_ppm,
            outside_temperature_c=state.outside_temperature_c,
            outside_humidity_pct=state.outside_humidity_pct,
            outside_co2_ppm=max(_MIN_CO2_PPM, float(env.outside_co2_ppm)),
            u_co2=0.0,
            u_vent=self._vent_forcing(),
            u_heat=0.0,
            radiation=self._radiation(),
            dt_s=dt,
            crop_dry_weight=max(0.0, float(env.crop_dry_weight)),
            params=self._van_henten_params,
            evolve_crop=False,
        )

        heater_w = (
            effective.heater
            * max(0.0, caps.heater.max_power_w)
            * _clamp(caps.heater.efficiency, 0.0, 1.0)
        )
        cooler_w = effective.cooler * max(0.0, caps.cooler.max_cooling_w)
        light_w = _clamp(state.light_level, 0.0, 1.0) * max(0.0, env.lights_max_heat_w)
        envelope_w = max(0.0, env.heat_loss_w_per_k) * (state.outside_temperature_c - vh_t)
        final_t = _clamp(
            vh_t + (heater_w + light_w - cooler_w + envelope_w) * dt / thermal_mass,
            -30.0,
            70.0,
        )

        # Convert the backbone RH to water-vapour density before adding/removing
        # explicit grams. Recompute RH at the final temperature so heater/cooler
        # changes do not create or destroy water mass implicitly.
        vapour_g_m3 = _clamp(vh_rh, 0.0, 100.0) / 100.0 * sat_absolute_humidity_g_m3(vh_t)
        humidifier_g_s = (
            effective.humidifier
            * max(0.0, caps.humidifier.max_output_g_h)
            / 3600.0
            * _clamp(caps.humidifier.delivery_efficiency, 0.0, 1.0)
        )
        dehumidifier_g_s = (
            effective.dehumidifier
            * max(0.0, caps.dehumidifier.max_removal_g_h)
            / 3600.0
            * _clamp(caps.dehumidifier.delivery_efficiency, 0.0, 1.0)
        )
        vapour_g_m3 = max(
            0.0,
            vapour_g_m3 + (humidifier_g_s - dehumidifier_g_s) * dt / volume,
        )
        final_rh = _clamp(
            100.0 * vapour_g_m3 / sat_absolute_humidity_g_m3(final_t),
            0.0,
            100.0,
        )

        # Exactly one CO2 injection path. The capability is a rate, therefore the
        # same command over the same elapsed time is independent of simulator dt.
        injection_ppm = effective.co2_doser * max(0.0, caps.co2_doser.max_injection_ppm_s) * dt
        final_co2 = _clamp(vh_co2 + injection_ppm, _MIN_CO2_PPM, _MAX_CO2_PPM)

        state.air_temperature_c = final_t
        state.relative_humidity_pct = final_rh
        state.co2_ppm = final_co2
        state.light_level = _clamp(state.light_level, 0.0, 1.0)
