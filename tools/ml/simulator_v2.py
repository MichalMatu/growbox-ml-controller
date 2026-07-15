"""Growbox environment simulator v2 — up to 4 irrigation zones, 10 ML outputs.

Physically inspired lumped-parameter model for training (not runtime on device).
Inactive zones (``available=False``) contribute no soil/evaporation/irrigation physics.
"""

from __future__ import annotations

import copy
import math
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from typing import ClassVar

import numpy as np

MAX_ZONES = 4

GLOBAL_OUTPUT_NAMES = (
    "heater",
    "fan",
    "humidifier",
    "dehumidifier",
    "cooler",
    "co2_doser",
)

ZONE_OUTPUT_NAMES = tuple(f"irrigation_zone_{index}" for index in range(1, MAX_ZONES + 1))

OUTPUT_NAMES = GLOBAL_OUTPUT_NAMES + ZONE_OUTPUT_NAMES


def _clamp(value: float, low: float, high: float) -> float:
    return min(high, max(low, float(value)))


@dataclass(frozen=True)
class EnvironmentParameters:
    growbox_volume_m3: float = 0.8
    thermal_mass_j_per_k: float = 35_000.0
    heat_loss_w_per_k: float = 7.0
    air_leak_rate_ach: float = 0.25


@dataclass(frozen=True)
class ZoneCultivation:
    pot_volume_l: float = 12.0
    substrate_water_capacity_ml: float = 3_000.0
    transpiration_factor: float = 1.0


@dataclass(frozen=True)
class HeaterCapabilities:
    available: bool = True
    max_power_w: float = 180.0
    efficiency: float = 0.92


@dataclass(frozen=True)
class FanCapabilities:
    available: bool = True
    max_airflow_m3_h: float = 90.0
    minimum_command: float = 0.0


@dataclass(frozen=True)
class HumidifierCapabilities:
    available: bool = True
    max_output_g_h: float = 110.0


@dataclass(frozen=True)
class DehumidifierCapabilities:
    available: bool = False
    max_removal_g_h: float = 80.0


@dataclass(frozen=True)
class CoolerCapabilities:
    available: bool = False
    max_cooling_w: float = 200.0


@dataclass(frozen=True)
class Co2DoserCapabilities:
    available: bool = False
    dose_ppm_per_full_pulse: float = 120.0
    maximum_pulse_s: float = 3.0


@dataclass(frozen=True)
class PumpCapabilities:
    available: bool = False
    flow_ml_s: float = 18.0
    maximum_pulse_s: float = 4.0
    minimum_interval_s: float = 300.0


@dataclass(frozen=True)
class LightsConfig:
    integrated: bool = True
    max_heat_w: float = 120.0


@dataclass(frozen=True)
class ZoneConfig:
    available: bool = False
    soil_moisture_valid: bool = False
    soil_temperature_valid: bool = False
    cultivation: ZoneCultivation = field(default_factory=ZoneCultivation)
    irrigation: PumpCapabilities = field(default_factory=PumpCapabilities)
    target_soil_moisture_pct: float = 52.0


@dataclass(frozen=True)
class GlobalActuators:
    heater: HeaterCapabilities = field(default_factory=HeaterCapabilities)
    fan: FanCapabilities = field(default_factory=FanCapabilities)
    humidifier: HumidifierCapabilities = field(default_factory=HumidifierCapabilities)
    dehumidifier: DehumidifierCapabilities = field(default_factory=DehumidifierCapabilities)
    cooler: CoolerCapabilities = field(default_factory=CoolerCapabilities)
    co2_doser: Co2DoserCapabilities = field(default_factory=Co2DoserCapabilities)
    lights: LightsConfig = field(default_factory=LightsConfig)


@dataclass(frozen=True)
class ControlTargets:
    target_air_temperature_c: float = 25.0
    target_air_humidity_pct: float = 65.0
    target_co2_ppm: float = 850.0


@dataclass(frozen=True)
class ControlAction:
    heater: float = 0.0
    fan: float = 0.0
    humidifier: float = 0.0
    dehumidifier: float = 0.0
    cooler: float = 0.0
    co2_doser: float = 0.0
    irrigation_zone_1: float = 0.0
    irrigation_zone_2: float = 0.0
    irrigation_zone_3: float = 0.0
    irrigation_zone_4: float = 0.0

    def clipped(self) -> ControlAction:
        return ControlAction(*(_clamp(value, 0.0, 1.0) for value in self.as_tuple()))

    def as_tuple(self) -> tuple[float, ...]:
        return tuple(getattr(self, name) for name in OUTPUT_NAMES)

    def as_dict(self) -> dict[str, float]:
        return dict(zip(OUTPUT_NAMES, self.as_tuple()))

    @classmethod
    def from_mapping(cls, values: Mapping[str, float]) -> ControlAction:
        return cls(**{name: float(values.get(name, 0.0)) for name in OUTPUT_NAMES})


@dataclass
class ZoneState:
    soil_moisture_pct: float = 44.0
    soil_temperature_c: float = 20.0


@dataclass
class EnvironmentState:
    air_temperature_c: float = 21.0
    air_humidity_pct: float = 52.0
    co2_ppm: float = 720.0
    outside_temperature_c: float = 16.0
    outside_humidity_pct: float = 55.0
    outside_co2_ppm: float = 420.0
    nutrient_solution_temperature_c: float = 20.0
    zones: list[ZoneState] = field(default_factory=lambda: [ZoneState() for _ in range(MAX_ZONES)])
    lights_active: bool = False

    def __post_init__(self) -> None:
        if len(self.zones) != MAX_ZONES:
            raise ValueError(f"expected {MAX_ZONES} zone states")


@dataclass(frozen=True)
class SensorValidity:
    air_temperature_c: bool = True
    air_humidity_pct: bool = True
    co2_ppm: bool = True
    outside_temperature_c: bool = True
    outside_humidity_pct: bool = True
    outside_co2_ppm: bool = True
    nutrient_solution_temperature_c: bool = False
    zone_soil_moisture: tuple[bool, bool, bool, bool] = (False, False, False, False)
    zone_soil_temperature: tuple[bool, bool, bool, bool] = (False, False, False, False)


@dataclass(frozen=True)
class ResponseLag:
    heater_s: float = 35.0
    fan_s: float = 8.0
    humidifier_s: float = 20.0
    dehumidifier_s: float = 20.0
    cooler_s: float = 45.0


@dataclass(frozen=True)
class Scenario:
    scenario_id: str
    seed: int
    initial_state: EnvironmentState
    environment: EnvironmentParameters
    actuators: GlobalActuators
    zones: tuple[ZoneConfig, ZoneConfig, ZoneConfig, ZoneConfig]
    targets: ControlTargets = field(default_factory=ControlTargets)
    validity: SensorValidity = field(default_factory=SensorValidity)
    timestep_s: float = 10.0
    response_lag: ResponseLag = field(default_factory=ResponseLag)

    def active_zone_indices(self) -> tuple[int, ...]:
        return tuple(index for index, zone in enumerate(self.zones) if zone.available)


class SequentialEnvironmentSimulatorV2:
    """Closed-loop v2 simulator with per-zone irrigation timers."""

    irrigation_output_names: ClassVar[tuple[str, ...]] = ZONE_OUTPUT_NAMES

    def __init__(self, scenario: Scenario, *, seed: int | None = None):
        self.scenario = copy.deepcopy(scenario)
        self.state = copy.deepcopy(scenario.initial_state)
        self.seed = int(scenario.seed if seed is None else seed)
        self.rng = np.random.default_rng(self.seed)
        self.elapsed_s = 0.0
        self.last_irrigation_s = [-1.0e30] * MAX_ZONES
        self.effective_action = ControlAction()
        self.previous_command = ControlAction()

    def reset(self, *, seed: int | None = None) -> EnvironmentState:
        if seed is not None:
            self.seed = int(seed)
        self.rng = np.random.default_rng(self.seed)
        self.state = copy.deepcopy(self.scenario.initial_state)
        self.elapsed_s = 0.0
        self.last_irrigation_s = [-1.0e30] * MAX_ZONES
        self.effective_action = ControlAction()
        self.previous_command = ControlAction()
        return copy.deepcopy(self.state)

    def clone(self) -> SequentialEnvironmentSimulatorV2:
        other = SequentialEnvironmentSimulatorV2(self.scenario, seed=self.seed)
        other.state = copy.deepcopy(self.state)
        other.elapsed_s = self.elapsed_s
        other.last_irrigation_s = list(self.last_irrigation_s)
        other.effective_action = self.effective_action
        other.previous_command = self.previous_command
        other.rng.bit_generator.state = copy.deepcopy(self.rng.bit_generator.state)
        return other

    def irrigation_ready(self, zone_index: int) -> bool:
        zone = self.scenario.zones[zone_index]
        interval = zone.irrigation.minimum_interval_s
        return self.elapsed_s - self.last_irrigation_s[zone_index] >= interval

    def observe(self, *, add_sensor_noise: bool = False) -> EnvironmentState:
        observed = copy.deepcopy(self.state)
        if add_sensor_noise:
            observed.air_temperature_c += float(self.rng.normal(0.0, 0.08))
            observed.air_humidity_pct += float(self.rng.normal(0.0, 0.25))
            observed.co2_ppm += float(self.rng.normal(0.0, 4.0))
        observed.air_humidity_pct = _clamp(observed.air_humidity_pct, 0.0, 100.0)
        observed.co2_ppm = max(0.0, observed.co2_ppm)
        return observed

    def step(
        self,
        action: ControlAction,
        timestep_s: float | None = None,
        *,
        add_sensor_noise: bool = False,
    ) -> EnvironmentState:
        dt = float(self.scenario.timestep_s if timestep_s is None else timestep_s)
        if not math.isfinite(dt) or dt <= 0.0:
            raise ValueError("timestep_s must be finite and positive")

        command = self._mask_unavailable(action.clipped())
        self._advance_effective_action(command, dt)
        self._advance_physics(command, dt)
        self.elapsed_s += dt
        self.previous_command = command
        return self.observe(add_sensor_noise=add_sensor_noise)

    def _mask_unavailable(self, command: ControlAction) -> ControlAction:
        caps = self.scenario.actuators
        values = command.as_dict()
        values["heater"] = values["heater"] if caps.heater.available else 0.0
        values["fan"] = values["fan"] if caps.fan.available else 0.0
        values["humidifier"] = values["humidifier"] if caps.humidifier.available else 0.0
        values["dehumidifier"] = values["dehumidifier"] if caps.dehumidifier.available else 0.0
        values["cooler"] = values["cooler"] if caps.cooler.available else 0.0
        values["co2_doser"] = values["co2_doser"] if caps.co2_doser.available else 0.0
        for index, zone in enumerate(self.scenario.zones):
            name = self.irrigation_output_names[index]
            if not zone.available or not zone.irrigation.available:
                values[name] = 0.0
        return ControlAction.from_mapping(values)

    @staticmethod
    def _lag(previous: float, requested: float, dt: float, time_constant: float) -> float:
        if time_constant <= 0.0:
            return requested
        alpha = 1.0 - math.exp(-dt / time_constant)
        return previous + alpha * (requested - previous)

    def _advance_effective_action(self, command: ControlAction, dt: float) -> None:
        lag = self.scenario.response_lag
        old = self.effective_action
        self.effective_action = ControlAction(
            heater=self._lag(old.heater, command.heater, dt, lag.heater_s),
            fan=self._lag(old.fan, command.fan, dt, lag.fan_s),
            humidifier=self._lag(old.humidifier, command.humidifier, dt, lag.humidifier_s),
            dehumidifier=self._lag(old.dehumidifier, command.dehumidifier, dt, lag.dehumidifier_s),
            cooler=self._lag(old.cooler, command.cooler, dt, lag.cooler_s),
            co2_doser=command.co2_doser,
            irrigation_zone_1=command.irrigation_zone_1,
            irrigation_zone_2=command.irrigation_zone_2,
            irrigation_zone_3=command.irrigation_zone_3,
            irrigation_zone_4=command.irrigation_zone_4,
        )

    def _zone_evaporation_pp_s(
        self,
        zone_index: int,
        *,
        vapor_deficit: float,
        air_temperature_c: float,
    ) -> float:
        zone_cfg = self.scenario.zones[zone_index]
        if not zone_cfg.available or not zone_cfg.soil_moisture_valid:
            return 0.0
        zone_state = self.state.zones[zone_index]
        soil_factor = _clamp(zone_state.soil_moisture_pct / 55.0, 0.05, 1.2)
        soil_temp_factor = 1.0
        if zone_cfg.soil_temperature_valid:
            soil_temp_factor = _clamp((zone_state.soil_temperature_c - 5.0) / 18.0, 0.2, 1.8)
        air_temp_factor = _clamp((air_temperature_c - 5.0) / 20.0, 0.2, 1.8)
        crop = zone_cfg.cultivation
        transpiration_ml_s = (
            0.00030
            * max(0.0, crop.transpiration_factor)
            * max(0.5, crop.pot_volume_l)
            * vapor_deficit
            * air_temp_factor
            * soil_factor
            * soil_temp_factor
        )
        volume = max(0.05, self.scenario.environment.growbox_volume_m3)
        air_moisture_capacity_g = max(1.0, volume * 20.0)
        return transpiration_ml_s * 100.0 / air_moisture_capacity_g

    def _advance_physics(self, command: ControlAction, dt: float) -> None:
        env = self.scenario.environment
        caps = self.scenario.actuators
        state = self.state
        effective = self.effective_action

        volume = max(0.05, env.growbox_volume_m3)
        thermal_mass = max(500.0, env.thermal_mass_j_per_k)
        fan_airflow = effective.fan * caps.fan.max_airflow_m3_h
        exchange_ach = max(0.0, env.air_leak_rate_ach + fan_airflow / volume)
        exchange_rate_s = exchange_ach / 3600.0

        heater_w = effective.heater * caps.heater.max_power_w * caps.heater.efficiency
        cooler_w = effective.cooler * caps.cooler.max_cooling_w
        lights_w = caps.lights.max_heat_w if state.lights_active and caps.lights.integrated else 0.0
        passive_heat_w = env.heat_loss_w_per_k * (
            state.outside_temperature_c - state.air_temperature_c
        )
        air_heat_capacity_j_k = volume * 1.225 * 1005.0
        exchange_heat_w = (
            air_heat_capacity_j_k
            * exchange_rate_s
            * (state.outside_temperature_c - state.air_temperature_c)
        )
        temperature_delta = (
            (heater_w + lights_w - cooler_w + passive_heat_w + exchange_heat_w) * dt / thermal_mass
        )

        air_moisture_capacity_g = max(1.0, volume * 20.0)
        humidity_exchange_pp_s = exchange_rate_s * (
            state.outside_humidity_pct - state.air_humidity_pct
        )
        humidifier_pp_s = (
            effective.humidifier
            * caps.humidifier.max_output_g_h
            / 3600.0
            * 100.0
            / air_moisture_capacity_g
        )
        dehumidifier_pp_s = (
            -effective.dehumidifier
            * caps.dehumidifier.max_removal_g_h
            / 3600.0
            * 100.0
            / air_moisture_capacity_g
        )

        vapor_deficit = _clamp((100.0 - state.air_humidity_pct) / 60.0, 0.1, 1.5)
        evap_pp_s = sum(
            self._zone_evaporation_pp_s(
                index, vapor_deficit=vapor_deficit, air_temperature_c=state.air_temperature_c
            )
            for index in range(MAX_ZONES)
        )

        irrigation_humidity_boost_pp = 0.0
        for index, zone_cfg in enumerate(self.scenario.zones):
            if not zone_cfg.available or not zone_cfg.irrigation.available:
                continue
            output_name = self.irrigation_output_names[index]
            if getattr(command, output_name) <= 0.0 or not self.irrigation_ready(index):
                continue
            pulse_s = getattr(command, output_name) * zone_cfg.irrigation.maximum_pulse_s
            irrigation_ml = zone_cfg.irrigation.flow_ml_s * pulse_s
            self.last_irrigation_s[index] = self.elapsed_s
            water_capacity = max(1.0, zone_cfg.cultivation.substrate_water_capacity_ml)
            zone_state = state.zones[index]
            zone_state.soil_moisture_pct = _clamp(
                zone_state.soil_moisture_pct + irrigation_ml * 100.0 / water_capacity,
                0.0,
                100.0,
            )
            irrigation_humidity_boost_pp += irrigation_ml * 0.04 * 100.0 / air_moisture_capacity_g

        humidity_delta = (
            humidity_exchange_pp_s + humidifier_pp_s + dehumidifier_pp_s + evap_pp_s
        ) * dt + irrigation_humidity_boost_pp

        co2_exchange_ppm_s = exchange_rate_s * (state.outside_co2_ppm - state.co2_ppm)
        co2_dose_ppm = 0.0
        if command.co2_doser > 0.0 and caps.co2_doser.available:
            co2_dose_ppm = command.co2_doser * caps.co2_doser.dose_ppm_per_full_pulse
        biological_co2_ppm_s = 0.0020 * (850.0 - state.co2_ppm)

        for index, zone_cfg in enumerate(self.scenario.zones):
            if not zone_cfg.available or not zone_cfg.soil_moisture_valid:
                continue
            crop = zone_cfg.cultivation
            zone_state = state.zones[index]
            water_capacity = max(1.0, crop.substrate_water_capacity_ml)
            drying_ml_s = (
                0.00010
                * max(0.5, crop.pot_volume_l)
                * max(0.0, crop.transpiration_factor)
                * vapor_deficit
            )
            soil_loss_pp = drying_ml_s * dt * 100.0 / water_capacity
            zone_state.soil_moisture_pct = _clamp(
                zone_state.soil_moisture_pct - soil_loss_pp, 0.0, 100.0
            )

        state.air_temperature_c = _clamp(state.air_temperature_c + temperature_delta, -30.0, 70.0)
        state.air_humidity_pct = _clamp(state.air_humidity_pct + humidity_delta, 0.0, 100.0)
        state.co2_ppm = _clamp(
            state.co2_ppm + (co2_exchange_ppm_s + biological_co2_ppm_s) * dt + co2_dose_ppm,
            250.0,
            5000.0,
        )


def default_scenario_v2(*, scenario_id: str = "v2-default", seed: int = 0) -> Scenario:
    """Single active zone for smoke tests."""

    zone_one = ZoneConfig(
        available=True,
        soil_moisture_valid=True,
        irrigation=PumpCapabilities(available=True),
    )
    inactive = ZoneConfig()
    return Scenario(
        scenario_id=scenario_id,
        seed=seed,
        initial_state=EnvironmentState(
            air_temperature_c=21.0,
            air_humidity_pct=48.0,
            co2_ppm=760.0,
            outside_temperature_c=14.0,
            outside_humidity_pct=50.0,
            outside_co2_ppm=420.0,
            lights_active=False,
            zones=[ZoneState(soil_moisture_pct=40.0), ZoneState(), ZoneState(), ZoneState()],
        ),
        environment=EnvironmentParameters(),
        actuators=GlobalActuators(),
        zones=(zone_one, inactive, inactive, inactive),
    )


def scenario_to_dict(scenario: Scenario) -> dict[str, object]:
    return asdict(scenario)
