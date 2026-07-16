"""Growbox environment simulator for the active contract (v4 pots).

Up to 4 irrigation pots, 15 ML outputs (climate + irrigation + nutrient/heat mats).
Chamber air uses Van Henten-structured dynamics (see tools.ml.physics); pots keep
lumped substrate water/temperature. Training-only — not runtime on device.

Output names must stay byte-equal to ``contract.outputs`` for
``schemas/environment-controller.json`` — enforced by ``tools.ml.alignment``.
"""

from __future__ import annotations

import copy
import math
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from typing import ClassVar, Literal

import numpy as np

from .physics.actuators import build_chamber_forcing
from .physics.pots_substrate import (
    PotPhysicsConfig,
    PotPhysicsState,
    step_pot,
    water_ml_to_humidity_pp,
)
from .physics.van_henten import step_chamber_van_henten

MAX_POTS = 4

GLOBAL_OUTPUT_NAMES = (
    "heater",
    "fan",
    "humidifier",
    "dehumidifier",
    "cooler",
    "co2_doser",
)

POT_IRRIGATION_NAMES = tuple(f"irrigation_pot_{index}" for index in range(1, MAX_POTS + 1))
HEATING_OUTPUT_NAMES = ("nutrient_heater",) + tuple(
    f"heat_mat_pot_{index}" for index in range(1, MAX_POTS + 1)
)

OUTPUT_NAMES = GLOBAL_OUTPUT_NAMES + POT_IRRIGATION_NAMES + HEATING_OUTPUT_NAMES


def _clamp(value: float, low: float, high: float) -> float:
    return min(high, max(low, float(value)))


@dataclass(frozen=True)
class EnvironmentParameters:
    growbox_volume_m3: float = 0.8
    thermal_mass_j_per_k: float = 35_000.0
    heat_loss_w_per_k: float = 7.0
    air_leak_rate_ach: float = 0.25


@dataclass(frozen=True)
class PotCultivation:
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
class NutrientHeaterCapabilities:
    available: bool = False
    max_power_w: float = 150.0
    efficiency: float = 0.95


@dataclass(frozen=True)
class PumpCapabilities:
    available: bool = False
    flow_ml_s: float = 18.0
    maximum_pulse_s: float = 4.0
    minimum_interval_s: float = 300.0


@dataclass(frozen=True)
class HeatMatCapabilities:
    available: bool = False
    max_power_w: float = 25.0


@dataclass(frozen=True)
class LightsConfig:
    integrated: bool = True
    max_heat_w: float = 120.0


@dataclass(frozen=True)
class PotConfig:
    available: bool = False
    soil_moisture_valid: bool = False
    soil_temperature_valid: bool = False
    cultivation: PotCultivation = field(default_factory=PotCultivation)
    irrigation: PumpCapabilities = field(default_factory=PumpCapabilities)
    heat_mat: HeatMatCapabilities = field(default_factory=HeatMatCapabilities)
    target_soil_moisture_pct: float = 52.0
    target_soil_temperature_c: float = 22.0


@dataclass(frozen=True)
class GlobalActuators:
    heater: HeaterCapabilities = field(default_factory=HeaterCapabilities)
    fan: FanCapabilities = field(default_factory=FanCapabilities)
    humidifier: HumidifierCapabilities = field(default_factory=HumidifierCapabilities)
    dehumidifier: DehumidifierCapabilities = field(default_factory=DehumidifierCapabilities)
    cooler: CoolerCapabilities = field(default_factory=CoolerCapabilities)
    co2_doser: Co2DoserCapabilities = field(default_factory=Co2DoserCapabilities)
    nutrient_heater: NutrientHeaterCapabilities = field(default_factory=NutrientHeaterCapabilities)
    lights: LightsConfig = field(default_factory=LightsConfig)


@dataclass(frozen=True)
class ControlTargets:
    target_air_temperature_c: float = 25.0
    target_air_humidity_pct: float = 65.0
    target_co2_ppm: float = 850.0
    target_nutrient_solution_temperature_c: float = 20.0


@dataclass(frozen=True)
class ControlAction:
    heater: float = 0.0
    fan: float = 0.0
    humidifier: float = 0.0
    dehumidifier: float = 0.0
    cooler: float = 0.0
    co2_doser: float = 0.0
    irrigation_pot_1: float = 0.0
    irrigation_pot_2: float = 0.0
    irrigation_pot_3: float = 0.0
    irrigation_pot_4: float = 0.0
    nutrient_heater: float = 0.0
    heat_mat_pot_1: float = 0.0
    heat_mat_pot_2: float = 0.0
    heat_mat_pot_3: float = 0.0
    heat_mat_pot_4: float = 0.0

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
class PotState:
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
    pots: list[PotState] = field(default_factory=lambda: [PotState() for _ in range(MAX_POTS)])
    lights_active: bool = False

    def __post_init__(self) -> None:
        if len(self.pots) != MAX_POTS:
            raise ValueError(f"expected {MAX_POTS} pot states")


@dataclass(frozen=True)
class SensorValidity:
    air_temperature_c: bool = True
    air_humidity_pct: bool = True
    co2_ppm: bool = True
    outside_temperature_c: bool = True
    outside_humidity_pct: bool = True
    outside_co2_ppm: bool = True
    nutrient_solution_temperature_c: bool = False
    pot_soil_moisture: tuple[bool, bool, bool, bool] = (False, False, False, False)
    pot_soil_temperature: tuple[bool, bool, bool, bool] = (False, False, False, False)


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
    pots: tuple[PotConfig, PotConfig, PotConfig, PotConfig]
    targets: ControlTargets = field(default_factory=ControlTargets)
    validity: SensorValidity = field(default_factory=SensorValidity)
    timestep_s: float = 10.0
    response_lag: ResponseLag = field(default_factory=ResponseLag)
    # Tier A default: Van Henten chamber; "legacy" keeps pure engineering balances.
    chamber_model: Literal["van_henten", "legacy"] = "van_henten"

    def active_pot_indices(self) -> tuple[int, ...]:
        return tuple(index for index, pot in enumerate(self.pots) if pot.available)


class SequentialEnvironmentSimulator:
    """Closed-loop growbox simulator with per-pot irrigation timers."""

    irrigation_output_names: ClassVar[tuple[str, ...]] = POT_IRRIGATION_NAMES
    heat_mat_output_names: ClassVar[tuple[str, ...]] = tuple(
        name for name in HEATING_OUTPUT_NAMES if name.startswith("heat_mat_")
    )

    def __init__(self, scenario: Scenario, *, seed: int | None = None):
        self.scenario = copy.deepcopy(scenario)
        self.state = copy.deepcopy(scenario.initial_state)
        self.seed = int(scenario.seed if seed is None else seed)
        self.rng = np.random.default_rng(self.seed)
        self.elapsed_s = 0.0
        self.last_irrigation_s = [-1.0e30] * MAX_POTS
        self.effective_action = ControlAction()
        self.previous_command = ControlAction()
        # Internal crop dry-weight for Van Henten canopy terms (not a contract sensor).
        self._crop_dry_weight = 0.0025

    def reset(self, *, seed: int | None = None) -> EnvironmentState:
        if seed is not None:
            self.seed = int(seed)
        self.rng = np.random.default_rng(self.seed)
        self.state = copy.deepcopy(self.scenario.initial_state)
        self.elapsed_s = 0.0
        self.last_irrigation_s = [-1.0e30] * MAX_POTS
        self.effective_action = ControlAction()
        self.previous_command = ControlAction()
        self._crop_dry_weight = 0.0025
        return copy.deepcopy(self.state)

    def clone(self) -> SequentialEnvironmentSimulator:
        other = SequentialEnvironmentSimulator(self.scenario, seed=self.seed)
        other.state = copy.deepcopy(self.state)
        other.elapsed_s = self.elapsed_s
        other.last_irrigation_s = list(self.last_irrigation_s)
        other.effective_action = self.effective_action
        other.previous_command = self.previous_command
        other._crop_dry_weight = self._crop_dry_weight
        other.rng.bit_generator.state = copy.deepcopy(self.rng.bit_generator.state)
        return other

    def irrigation_ready(self, pot_index: int) -> bool:
        pot = self.scenario.pots[pot_index]
        interval = pot.irrigation.minimum_interval_s
        return self.elapsed_s - self.last_irrigation_s[pot_index] >= interval

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
        values["nutrient_heater"] = (
            values["nutrient_heater"] if caps.nutrient_heater.available else 0.0
        )
        for index, pot in enumerate(self.scenario.pots):
            name = self.irrigation_output_names[index]
            if not pot.available or not pot.irrigation.available:
                values[name] = 0.0
            heat_name = self.heat_mat_output_names[index]
            if not pot.available or not pot.heat_mat.available:
                values[heat_name] = 0.0
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
            irrigation_pot_1=command.irrigation_pot_1,
            irrigation_pot_2=command.irrigation_pot_2,
            irrigation_pot_3=command.irrigation_pot_3,
            irrigation_pot_4=command.irrigation_pot_4,
            nutrient_heater=self._lag(
                old.nutrient_heater, command.nutrient_heater, dt, lag.heater_s
            ),
            heat_mat_pot_1=command.heat_mat_pot_1,
            heat_mat_pot_2=command.heat_mat_pot_2,
            heat_mat_pot_3=command.heat_mat_pot_3,
            heat_mat_pot_4=command.heat_mat_pot_4,
        )

    def _pot_physics_config(self, pot_index: int) -> PotPhysicsConfig:
        pot_cfg = self.scenario.pots[pot_index]
        return PotPhysicsConfig(
            available=pot_cfg.available,
            soil_moisture_valid=pot_cfg.soil_moisture_valid,
            soil_temperature_valid=pot_cfg.soil_temperature_valid,
            pot_volume_l=pot_cfg.cultivation.pot_volume_l,
            substrate_water_capacity_ml=pot_cfg.cultivation.substrate_water_capacity_ml,
            transpiration_factor=pot_cfg.cultivation.transpiration_factor,
            irrigation_available=pot_cfg.irrigation.available,
            irrigation_flow_ml_s=pot_cfg.irrigation.flow_ml_s,
            irrigation_maximum_pulse_s=pot_cfg.irrigation.maximum_pulse_s,
            heat_mat_available=pot_cfg.heat_mat.available,
            heat_mat_max_power_w=pot_cfg.heat_mat.max_power_w,
        )

    def _advance_physics(self, command: ControlAction, dt: float) -> None:
        env = self.scenario.environment
        caps = self.scenario.actuators
        state = self.state
        effective = self.effective_action

        volume = max(0.05, env.growbox_volume_m3)
        air_moisture_capacity_g = max(1.0, volume * 20.0)

        nutrient_heater_w = (
            effective.nutrient_heater
            * caps.nutrient_heater.max_power_w
            * caps.nutrient_heater.efficiency
            if caps.nutrient_heater.available
            else 0.0
        )
        nutrient_thermal_mass_j_k = 84_000.0
        nutrient_loss_w_per_k = 3.5
        nutrient_loss_w = nutrient_loss_w_per_k * (
            state.outside_temperature_c - state.nutrient_solution_temperature_c
        )
        nutrient_temp_delta = (nutrient_heater_w + nutrient_loss_w) * dt / nutrient_thermal_mass_j_k

        # --- Tier B: pots first (irrigation + evaporate + soil T) ---
        free_water_ml = 0.0
        evaporated_ml = 0.0
        air_t_for_pots = state.air_temperature_c
        air_rh_for_pots = state.air_humidity_pct
        for index in range(MAX_POTS):
            pot_state = state.pots[index]
            irr_name = self.irrigation_output_names[index]
            heat_name = self.heat_mat_output_names[index]
            ready = self.irrigation_ready(index)
            result = step_pot(
                PotPhysicsState(
                    soil_moisture_pct=pot_state.soil_moisture_pct,
                    soil_temperature_c=pot_state.soil_temperature_c,
                ),
                self._pot_physics_config(index),
                air_temperature_c=air_t_for_pots,
                air_humidity_pct=air_rh_for_pots,
                heat_mat_command_0_1=getattr(effective, heat_name),
                dt_s=dt,
                irrigation_command_0_1=getattr(command, irr_name),
                nutrient_solution_temperature_c=state.nutrient_solution_temperature_c,
                irrigation_ready=ready,
            )
            if result.applied_irrigation_ml > 0.0:
                self.last_irrigation_s[index] = self.elapsed_s
            pot_state.soil_moisture_pct = result.soil_moisture_pct
            pot_state.soil_temperature_c = result.soil_temperature_c
            free_water_ml += result.irrigation_free_water_ml
            evaporated_ml += max(0.0, result.water_to_air_ml - result.irrigation_free_water_ml)

        # Splash/surface water only partially becomes bulk vapor in one step.
        pot_humidity_pp = water_ml_to_humidity_pp(
            free_water_ml, growbox_volume_m3=volume, fraction_to_vapor=0.20
        ) + water_ml_to_humidity_pp(evaporated_ml, growbox_volume_m3=volume, fraction_to_vapor=1.0)

        # --- Chamber air (Tier A: Van Henten backbone or legacy balances) ---
        if self.scenario.chamber_model == "van_henten":
            forcing = build_chamber_forcing(
                heater=effective.heater,
                fan=effective.fan,
                humidifier=effective.humidifier,
                dehumidifier=effective.dehumidifier,
                cooler=effective.cooler,
                co2_doser=command.co2_doser,
                lights_active=state.lights_active,
                heater_max_power_w=caps.heater.max_power_w,
                heater_efficiency=caps.heater.efficiency,
                fan_max_airflow_m3_h=caps.fan.max_airflow_m3_h,
                growbox_volume_m3=volume,
                humidifier_max_output_g_h=caps.humidifier.max_output_g_h,
                dehumidifier_max_removal_g_h=caps.dehumidifier.max_removal_g_h,
                cooler_max_cooling_w=caps.cooler.max_cooling_w,
                co2_dose_ppm_per_full_pulse=caps.co2_doser.dose_ppm_per_full_pulse,
                lights_max_heat_w=caps.lights.max_heat_w,
                lights_integrated=caps.lights.integrated,
            )
            leak_boost = max(0.0, env.air_leak_rate_ach) * 0.15
            u_vent = forcing.u_vent + leak_boost
            new_t, new_rh, new_co2, self._crop_dry_weight = step_chamber_van_henten(
                air_temperature_c=state.air_temperature_c,
                air_humidity_pct=state.air_humidity_pct,
                co2_ppm=state.co2_ppm,
                outside_temperature_c=state.outside_temperature_c,
                outside_humidity_pct=state.outside_humidity_pct,
                outside_co2_ppm=state.outside_co2_ppm,
                u_co2=forcing.u_co2,
                u_vent=u_vent,
                u_heat=forcing.u_heat,
                radiation=forcing.radiation,
                dt_s=dt,
                crop_dry_weight=self._crop_dry_weight,
                evolve_crop=False,
            )
            hum_pp = forcing.humidifier_g_s * 100.0 / air_moisture_capacity_g
            dehum_pp = -forcing.dehumidifier_g_s * 100.0 / air_moisture_capacity_g
            new_rh = _clamp(
                new_rh + (hum_pp + dehum_pp) * dt + pot_humidity_pp,
                0.0,
                100.0,
            )
            if command.co2_doser > 0.0 and caps.co2_doser.available:
                new_co2 = _clamp(
                    new_co2 + command.co2_doser * caps.co2_doser.dose_ppm_per_full_pulse,
                    250.0,
                    5000.0,
                )
            state.air_temperature_c = new_t
            state.air_humidity_pct = new_rh
            state.co2_ppm = new_co2
        else:
            thermal_mass = max(500.0, env.thermal_mass_j_per_k)
            fan_airflow = effective.fan * caps.fan.max_airflow_m3_h
            exchange_ach = max(0.0, env.air_leak_rate_ach + fan_airflow / volume)
            exchange_rate_s = exchange_ach / 3600.0
            heater_w = effective.heater * caps.heater.max_power_w * caps.heater.efficiency
            cooler_w = effective.cooler * caps.cooler.max_cooling_w
            lights_w = (
                caps.lights.max_heat_w if state.lights_active and caps.lights.integrated else 0.0
            )
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
                (heater_w + lights_w - cooler_w + passive_heat_w + exchange_heat_w)
                * dt
                / thermal_mass
            )
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
            humidity_delta = (
                humidity_exchange_pp_s + humidifier_pp_s + dehumidifier_pp_s
            ) * dt + pot_humidity_pp
            co2_exchange_ppm_s = exchange_rate_s * (state.outside_co2_ppm - state.co2_ppm)
            co2_dose_ppm = 0.0
            if command.co2_doser > 0.0 and caps.co2_doser.available:
                co2_dose_ppm = command.co2_doser * caps.co2_doser.dose_ppm_per_full_pulse
            biological_co2_ppm_s = 0.0020 * (850.0 - state.co2_ppm)
            state.air_temperature_c = _clamp(
                state.air_temperature_c + temperature_delta, -30.0, 70.0
            )
            state.air_humidity_pct = _clamp(state.air_humidity_pct + humidity_delta, 0.0, 100.0)
            state.co2_ppm = _clamp(
                state.co2_ppm + (co2_exchange_ppm_s + biological_co2_ppm_s) * dt + co2_dose_ppm,
                250.0,
                5000.0,
            )

        state.nutrient_solution_temperature_c = _clamp(
            state.nutrient_solution_temperature_c + nutrient_temp_delta, 0.0, 50.0
        )


def default_scenario_v2(*, scenario_id: str = "v2-default", seed: int = 0) -> Scenario:
    """Single active pot for smoke tests."""

    pot_one = PotConfig(
        available=True,
        soil_moisture_valid=True,
        irrigation=PumpCapabilities(available=True),
    )
    inactive = PotConfig()
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
            pots=[PotState(soil_moisture_pct=40.0), PotState(), PotState(), PotState()],
        ),
        environment=EnvironmentParameters(),
        actuators=GlobalActuators(),
        pots=(pot_one, inactive, inactive, inactive),
    )


def scenario_to_dict(scenario: Scenario) -> dict[str, object]:
    return asdict(scenario)
