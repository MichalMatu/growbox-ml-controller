"""A small, deterministic, physically inspired growbox simulator.

The equations intentionally favor transparency and numerical stability over
physical fidelity.  They are useful for exercising the complete sequential ML
pipeline, but they are not a calibrated model of a real enclosure.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import copy
import math
from typing import Mapping

import numpy as np


SENSOR_NAMES = (
    "air_temperature_c",
    "air_humidity_pct",
    "co2_ppm",
    "soil_moisture_pct",
    "outside_temperature_c",
    "outside_humidity_pct",
)


def _clamp(value: float, low: float, high: float) -> float:
    return min(high, max(low, float(value)))


@dataclass(frozen=True)
class EnvironmentParameters:
    growbox_volume_m3: float = 0.8
    thermal_mass_j_per_k: float = 35_000.0
    heat_loss_w_per_k: float = 7.0
    air_leak_rate_ach: float = 0.25


@dataclass(frozen=True)
class CultivationParameters:
    pot_volume_l: float = 12.0
    substrate_water_capacity_ml: float = 3_000.0
    transpiration_factor: float = 1.0


@dataclass(frozen=True)
class HeaterCapabilities:
    available: bool = True
    max_power_w: float = 180.0
    efficiency: float = 0.92
    control_type: str = "binary"


@dataclass(frozen=True)
class FanCapabilities:
    available: bool = True
    max_airflow_m3_h: float = 90.0
    minimum_command: float = 0.2
    control_type: str = "pwm"


@dataclass(frozen=True)
class HumidifierCapabilities:
    available: bool = True
    max_output_g_h: float = 110.0
    control_type: str = "binary"


@dataclass(frozen=True)
class PumpCapabilities:
    available: bool = True
    flow_ml_s: float = 18.0
    maximum_pulse_s: float = 4.0
    minimum_interval_s: float = 300.0
    control_type: str = "binary"


@dataclass(frozen=True)
class ActuatorCapabilities:
    heater: HeaterCapabilities = field(default_factory=HeaterCapabilities)
    fan: FanCapabilities = field(default_factory=FanCapabilities)
    humidifier: HumidifierCapabilities = field(default_factory=HumidifierCapabilities)
    irrigation_pump: PumpCapabilities = field(default_factory=PumpCapabilities)


@dataclass(frozen=True)
class ControlTargets:
    target_air_temperature_c: float = 25.0
    target_air_humidity_pct: float = 65.0
    target_co2_ppm: float = 850.0
    target_soil_moisture_pct: float = 52.0


@dataclass(frozen=True)
class ControlAction:
    heater: float = 0.0
    fan: float = 0.0
    humidifier: float = 0.0
    irrigation: float = 0.0

    def clipped(self) -> "ControlAction":
        return ControlAction(*(_clamp(v, 0.0, 1.0) for v in self.as_array()))

    def as_array(self) -> tuple[float, float, float, float]:
        return (self.heater, self.fan, self.humidifier, self.irrigation)

    def as_dict(self) -> dict[str, float]:
        return dict(zip(("heater", "fan", "humidifier", "irrigation"), self.as_array()))


@dataclass
class EnvironmentState:
    air_temperature_c: float = 21.0
    air_humidity_pct: float = 52.0
    co2_ppm: float = 720.0
    soil_moisture_pct: float = 44.0
    outside_temperature_c: float = 16.0
    outside_humidity_pct: float = 55.0

    def as_dict(self) -> dict[str, float]:
        return {name: float(getattr(self, name)) for name in SENSOR_NAMES}


@dataclass(frozen=True)
class SensorValidity:
    air_temperature_c: bool = True
    air_humidity_pct: bool = True
    co2_ppm: bool = True
    soil_moisture_pct: bool = True
    outside_temperature_c: bool = True
    outside_humidity_pct: bool = True

    def as_dict(self) -> dict[str, bool]:
        return {name: bool(getattr(self, name)) for name in SENSOR_NAMES}


@dataclass(frozen=True)
class SensorNoise:
    air_temperature_c: float = 0.08
    air_humidity_pct: float = 0.25
    co2_ppm: float = 4.0
    soil_moisture_pct: float = 0.10
    outside_temperature_c: float = 0.05
    outside_humidity_pct: float = 0.20


@dataclass(frozen=True)
class ResponseLag:
    heater_s: float = 35.0
    fan_s: float = 8.0
    humidifier_s: float = 20.0


@dataclass(frozen=True)
class Scenario:
    scenario_id: str
    seed: int
    initial_state: EnvironmentState
    environment: EnvironmentParameters
    cultivation: CultivationParameters
    actuators: ActuatorCapabilities
    targets: ControlTargets
    timestep_s: float = 10.0
    noise: SensorNoise = field(default_factory=SensorNoise)
    response_lag: ResponseLag = field(default_factory=ResponseLag)


class SequentialEnvironmentSimulator:
    """Sequential closed-loop simulator with an explicit local RNG.

    ``state`` stores the latent physical state. ``observe()`` adds sensor noise
    without feeding that noise back into the dynamics. Actuator response uses a
    first-order lag, while irrigation is modeled as a discrete pump pulse.
    """

    def __init__(self, scenario: Scenario, *, seed: int | None = None):
        self.scenario = copy.deepcopy(scenario)
        self.state = copy.deepcopy(scenario.initial_state)
        self.seed = int(scenario.seed if seed is None else seed)
        self.rng = np.random.default_rng(self.seed)
        self.elapsed_s = 0.0
        self.last_irrigation_s = -1.0e30
        self.effective_action = ControlAction()
        self.previous_command = ControlAction()

    def clone(self) -> "SequentialEnvironmentSimulator":
        other = SequentialEnvironmentSimulator(self.scenario, seed=self.seed)
        other.state = copy.deepcopy(self.state)
        other.elapsed_s = self.elapsed_s
        other.last_irrigation_s = self.last_irrigation_s
        other.effective_action = self.effective_action
        other.previous_command = self.previous_command
        other.rng.bit_generator.state = copy.deepcopy(self.rng.bit_generator.state)
        return other

    def reset(self, *, seed: int | None = None) -> EnvironmentState:
        if seed is not None:
            self.seed = int(seed)
        self.rng = np.random.default_rng(self.seed)
        self.state = copy.deepcopy(self.scenario.initial_state)
        self.elapsed_s = 0.0
        self.last_irrigation_s = -1.0e30
        self.effective_action = ControlAction()
        self.previous_command = ControlAction()
        return copy.deepcopy(self.state)

    @property
    def irrigation_ready(self) -> bool:
        interval = self.scenario.actuators.irrigation_pump.minimum_interval_s
        return self.elapsed_s - self.last_irrigation_s >= interval

    def observe(self, *, add_sensor_noise: bool = True) -> EnvironmentState:
        values = self.state.as_dict()
        if add_sensor_noise:
            for name in SENSOR_NAMES:
                sigma = float(getattr(self.scenario.noise, name))
                values[name] += float(self.rng.normal(0.0, sigma))
        values["air_humidity_pct"] = _clamp(values["air_humidity_pct"], 0.0, 100.0)
        values["soil_moisture_pct"] = _clamp(values["soil_moisture_pct"], 0.0, 100.0)
        values["outside_humidity_pct"] = _clamp(values["outside_humidity_pct"], 0.0, 100.0)
        values["co2_ppm"] = max(0.0, values["co2_ppm"])
        return EnvironmentState(**values)

    def step(
        self,
        action: ControlAction,
        timestep_s: float | None = None,
        *,
        add_sensor_noise: bool = True,
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
        return ControlAction(
            command.heater if caps.heater.available else 0.0,
            command.fan if caps.fan.available else 0.0,
            command.humidifier if caps.humidifier.available else 0.0,
            command.irrigation if caps.irrigation_pump.available else 0.0,
        )

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
            irrigation=command.irrigation,
        )

    def _advance_physics(self, command: ControlAction, dt: float) -> None:
        env = self.scenario.environment
        crop = self.scenario.cultivation
        caps = self.scenario.actuators
        state = self.state
        effective = self.effective_action

        volume = max(0.05, env.growbox_volume_m3)
        thermal_mass = max(500.0, env.thermal_mass_j_per_k)
        fan_airflow = effective.fan * caps.fan.max_airflow_m3_h
        exchange_ach = max(0.0, env.air_leak_rate_ach + fan_airflow / volume)
        exchange_rate_s = exchange_ach / 3600.0

        heater_w = effective.heater * caps.heater.max_power_w * caps.heater.efficiency
        passive_heat_w = env.heat_loss_w_per_k * (
            state.outside_temperature_c - state.air_temperature_c
        )
        air_heat_capacity_j_k = volume * 1.225 * 1005.0
        exchange_heat_w = air_heat_capacity_j_k * exchange_rate_s * (
            state.outside_temperature_c - state.air_temperature_c
        )
        temperature_delta = (heater_w + passive_heat_w + exchange_heat_w) * dt / thermal_mass

        humidity_exchange_pp_s = exchange_rate_s * (
            state.outside_humidity_pct - state.air_humidity_pct
        )
        humidifier_g_s = effective.humidifier * caps.humidifier.max_output_g_h / 3600.0
        # Approximate moisture capacity of enclosure air near room temperature.
        air_moisture_capacity_g = max(1.0, volume * 20.0)
        humidifier_pp_s = humidifier_g_s * 100.0 / air_moisture_capacity_g

        vapor_deficit = _clamp((100.0 - state.air_humidity_pct) / 60.0, 0.1, 1.5)
        temperature_factor = _clamp((state.air_temperature_c - 5.0) / 20.0, 0.2, 1.8)
        transpiration_ml_s = (
            0.00035
            * max(0.0, crop.transpiration_factor)
            * max(0.5, crop.pot_volume_l)
            * vapor_deficit
            * temperature_factor
        )
        transpiration_pp_s = transpiration_ml_s * 100.0 / air_moisture_capacity_g

        humidity_delta = (
            humidity_exchange_pp_s + humidifier_pp_s + transpiration_pp_s
        ) * dt

        irrigation_ml = 0.0
        if command.irrigation > 0.0 and self.irrigation_ready:
            pulse_s = command.irrigation * caps.irrigation_pump.maximum_pulse_s
            irrigation_ml = caps.irrigation_pump.flow_ml_s * pulse_s
            self.last_irrigation_s = self.elapsed_s

        water_capacity = max(1.0, crop.substrate_water_capacity_ml)
        irrigation_soil_pp = irrigation_ml * 100.0 / water_capacity
        background_drying_ml_s = (
            0.00012
            * max(0.5, crop.pot_volume_l)
            * max(0.0, crop.transpiration_factor)
            * vapor_deficit
        )
        soil_loss_pp = (transpiration_ml_s + background_drying_ml_s) * dt * 100.0 / water_capacity

        outside_co2_ppm = 420.0
        co2_exchange_ppm_s = exchange_rate_s * (outside_co2_ppm - state.co2_ppm)
        # A gentle source/sink term keeps CO2 dynamic when the fan is off.
        biological_co2_ppm_s = 0.0025 * crop.transpiration_factor * (
            850.0 - state.co2_ppm
        )

        state.air_temperature_c = _clamp(
            state.air_temperature_c + temperature_delta, -30.0, 70.0
        )
        state.air_humidity_pct = _clamp(
            state.air_humidity_pct + humidity_delta, 0.0, 100.0
        )
        state.co2_ppm = _clamp(
            state.co2_ppm + (co2_exchange_ppm_s + biological_co2_ppm_s) * dt,
            250.0,
            5000.0,
        )
        state.soil_moisture_pct = _clamp(
            state.soil_moisture_pct + irrigation_soil_pp - soil_loss_pp,
            0.0,
            100.0,
        )


def scenario_to_dict(scenario: Scenario) -> dict[str, object]:
    """Return a JSON-compatible scenario representation."""

    return asdict(scenario)


def action_from_mapping(values: Mapping[str, float]) -> ControlAction:
    return ControlAction(
        heater=float(values.get("heater", 0.0)),
        fan=float(values.get("fan", 0.0)),
        humidifier=float(values.get("humidifier", 0.0)),
        irrigation=float(values.get("irrigation", 0.0)),
    )
