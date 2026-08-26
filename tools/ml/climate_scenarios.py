"""Structured climate-v6 training scenario families.

The old dataset randomized nearly every physical value independently. This
module instead creates named control problems and randomizes correlated physical
properties inside realistic growbox families. Simulator-only physical truth is
never added to the ML feature vector.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Literal

import numpy as np

from .climate_input import ClimateTargets, HumidityControlMode, MeasurementStatus
from .climate_simulator import (
    CLIMATE_OUTPUT_NAMES,
    ClimateActuatorCapabilities,
    ClimateEnvironmentParameters,
    ClimateResponseLag,
    ClimateScenario,
    ClimateState,
    Co2DoserCapabilities,
    CoolerCapabilities,
    DehumidifierCapabilities,
    ExhaustFanCapabilities,
    HeaterCapabilities,
    HumidifierCapabilities,
)

REQUIRED_SCENARIO_FAMILIES = (
    "cold_heating",
    "hot_cooling",
    "dry_humidification",
    "humid_dehumidification",
    "outside_helpful",
    "outside_harmful",
    "day_light_load",
    "day_to_night",
    "night_to_day",
    "co2_enrichment",
    "co2_unavailable",
    "actuator_missing",
    "sensor_fault",
)

FaultMode = Literal["invalid", "stale"]


@dataclass(frozen=True)
class ClimateProfile:
    name: str
    targets: ClimateTargets = field(default_factory=ClimateTargets)
    humidity_control_mode: HumidityControlMode = "RH"
    light_level: float = 0.0


@dataclass(frozen=True)
class ClimateTrainingEpisode:
    family: str
    scenario: ClimateScenario
    first_profile: ClimateProfile
    second_profile: ClimateProfile | None = None
    fault_sensor: str | None = None
    fault_mode: FaultMode | None = None

    def profile_for_step(self, step_index: int, total_steps: int) -> ClimateProfile:
        if self.second_profile is not None and step_index >= max(1, total_steps // 2):
            return self.second_profile
        return self.first_profile

    def forced_status_for_step(
        self, step_index: int, total_steps: int
    ) -> dict[str, MeasurementStatus]:
        if self.fault_sensor is None or self.fault_mode is None:
            return {}
        if step_index < max(1, total_steps // 2):
            return {}
        if self.fault_mode == "invalid":
            return {self.fault_sensor: MeasurementStatus(valid=False, age_ms=0)}
        return {self.fault_sensor: MeasurementStatus(valid=True, age_ms=60_000)}


def _correlated_base(
    rng: np.random.Generator,
) -> tuple[
    ClimateEnvironmentParameters,
    ClimateActuatorCapabilities,
    ClimateResponseLag,
]:
    volume = float(rng.uniform(0.3, 2.4))
    surface_scale = volume ** (2.0 / 3.0)
    thermal_mass = float(volume * rng.uniform(28_000.0, 75_000.0))
    environment = ClimateEnvironmentParameters(
        growbox_volume_m3=volume,
        thermal_mass_j_per_k=max(8_000.0, thermal_mass),
        heat_loss_w_per_k=float(surface_scale * rng.uniform(4.5, 13.0)),
        air_leak_rate_ach=float(rng.uniform(0.08, 0.75)),
        outside_co2_ppm=float(rng.uniform(400.0, 450.0)),
        crop_dry_weight=float(rng.uniform(0.0015, 0.0055)),
        lights_max_heat_w=float(volume * rng.uniform(80.0, 220.0)),
        radiation_lights_off=float(rng.uniform(5.0, 18.0)),
        radiation_lights_full=float(rng.uniform(65.0, 100.0)),
    )
    actuators = ClimateActuatorCapabilities(
        heater=HeaterCapabilities(
            available=True,
            max_power_w=float(volume * rng.uniform(160.0, 340.0)),
            efficiency=float(rng.uniform(0.75, 0.98)),
        ),
        cooler=CoolerCapabilities(
            available=True,
            max_cooling_w=float(volume * rng.uniform(170.0, 360.0)),
        ),
        exhaust_fan=ExhaustFanCapabilities(
            available=True,
            max_airflow_m3_h=float(volume * rng.uniform(75.0, 155.0)),
            minimum_command=float(rng.uniform(0.0, 0.2)),
        ),
        humidifier=HumidifierCapabilities(
            available=True,
            max_output_g_h=float(volume * rng.uniform(90.0, 240.0)),
            delivery_efficiency=float(rng.uniform(0.45, 0.75)),
        ),
        dehumidifier=DehumidifierCapabilities(
            available=True,
            max_removal_g_h=float(volume * rng.uniform(80.0, 220.0)),
            delivery_efficiency=float(rng.uniform(0.45, 0.75)),
        ),
        co2_doser=Co2DoserCapabilities(
            available=True,
            max_injection_ppm_s=float(rng.uniform(1.2, 4.5)),
        ),
    )
    lag = ClimateResponseLag(
        heater_s=float(rng.uniform(20.0, 75.0)),
        cooler_s=float(rng.uniform(20.0, 75.0)),
        exhaust_fan_s=float(rng.uniform(2.0, 15.0)),
        humidifier_s=float(rng.uniform(10.0, 50.0)),
        dehumidifier_s=float(rng.uniform(10.0, 50.0)),
        co2_doser_s=float(rng.uniform(0.0, 5.0)),
    )
    return environment, actuators, lag


def _profile(
    name: str,
    *,
    temperature: float = 24.0,
    humidity: float = 60.0,
    vpd: float = 1.2,
    mode: HumidityControlMode = "RH",
    co2_enabled: bool = False,
    co2_ppm: float = 800.0,
    light: float = 0.0,
) -> ClimateProfile:
    return ClimateProfile(
        name=name,
        targets=ClimateTargets(
            air_temperature_c=temperature,
            relative_humidity_pct=humidity,
            air_vpd_kpa=vpd,
            co2_enabled=co2_enabled,
            co2_ppm=co2_ppm,
        ),
        humidity_control_mode=mode,
        light_level=light,
    )


def _scenario(
    family: str,
    sample_index: int,
    seed: int,
    state: ClimateState,
    environment: ClimateEnvironmentParameters,
    actuators: ClimateActuatorCapabilities,
    response_lag: ClimateResponseLag,
) -> ClimateScenario:
    return ClimateScenario(
        scenario_id=f"v6-{family}-{sample_index:03d}-seed-{seed}",
        seed=int(seed),
        initial_state=state,
        environment=environment,
        actuators=actuators,
        response_lag=response_lag,
        timestep_s=10.0,
    )


def build_training_episode(
    family: str,
    sample_index: int,
    seed: int,
) -> ClimateTrainingEpisode:
    if family not in REQUIRED_SCENARIO_FAMILIES:
        raise ValueError(f"unknown climate scenario family: {family!r}")
    rng = np.random.default_rng(seed)
    env, caps, lag = _correlated_base(rng)
    jitter_t = float(rng.uniform(-0.8, 0.8))
    jitter_rh = float(rng.uniform(-3.0, 3.0))

    state = ClimateState(
        air_temperature_c=24.0 + jitter_t,
        relative_humidity_pct=60.0 + jitter_rh,
        co2_ppm=float(rng.uniform(500.0, 900.0)),
        outside_temperature_c=20.0 + jitter_t,
        outside_humidity_pct=50.0 + jitter_rh,
        light_level=0.0,
    )
    first = _profile("baseline")
    second: ClimateProfile | None = None
    fault_sensor: str | None = None
    fault_mode: FaultMode | None = None

    if family == "cold_heating":
        state = replace(
            state,
            air_temperature_c=float(rng.uniform(14.0, 18.0)),
            outside_temperature_c=float(rng.uniform(5.0, 14.0)),
        )
        first = _profile("heating", temperature=float(rng.uniform(23.0, 26.0)), humidity=60.0)
    elif family == "hot_cooling":
        state = replace(
            state,
            air_temperature_c=float(rng.uniform(31.0, 36.0)),
            outside_temperature_c=float(rng.uniform(31.0, 39.0)),
        )
        first = _profile("cooling", temperature=float(rng.uniform(23.0, 26.0)), humidity=60.0)
    elif family == "dry_humidification":
        state = replace(
            state,
            relative_humidity_pct=float(rng.uniform(24.0, 38.0)),
            outside_humidity_pct=float(rng.uniform(20.0, 38.0)),
        )
        first = _profile("humidify", temperature=state.air_temperature_c, humidity=65.0)
    elif family == "humid_dehumidification":
        state = replace(
            state,
            relative_humidity_pct=float(rng.uniform(78.0, 92.0)),
            outside_humidity_pct=float(rng.uniform(75.0, 95.0)),
        )
        first = _profile("dehumidify", temperature=state.air_temperature_c, humidity=58.0)
    elif family == "outside_helpful":
        state = replace(
            state,
            air_temperature_c=float(rng.uniform(29.0, 33.0)),
            outside_temperature_c=float(rng.uniform(12.0, 19.0)),
            outside_humidity_pct=float(rng.uniform(45.0, 65.0)),
        )
        caps = replace(caps, cooler=CoolerCapabilities(available=False, max_cooling_w=0.0))
        first = _profile("vent-helpful", temperature=24.0, humidity=60.0)
    elif family == "outside_harmful":
        state = replace(
            state,
            air_temperature_c=float(rng.uniform(23.5, 25.0)),
            outside_temperature_c=float(rng.uniform(34.0, 42.0)),
            outside_humidity_pct=float(rng.uniform(82.0, 96.0)),
        )
        first = _profile("vent-harmful", temperature=24.0, humidity=60.0)
    elif family == "day_light_load":
        state = replace(
            state,
            air_temperature_c=float(rng.uniform(23.0, 26.0)),
            light_level=float(rng.uniform(0.7, 1.0)),
        )
        first = _profile(
            "day-light",
            temperature=25.0,
            humidity=60.0,
            co2_enabled=True,
            co2_ppm=950.0,
            light=state.light_level,
        )
    elif family == "day_to_night":
        state = replace(state, light_level=1.0)
        first = _profile(
            "day",
            temperature=25.0,
            humidity=60.0,
            co2_enabled=True,
            co2_ppm=950.0,
            light=1.0,
        )
        second = _profile("night", temperature=21.0, humidity=65.0, light=0.0)
    elif family == "night_to_day":
        state = replace(state, light_level=0.0)
        first = _profile("night", temperature=21.0, humidity=65.0, light=0.0)
        second = _profile(
            "day",
            temperature=25.0,
            humidity=58.0,
            co2_enabled=True,
            co2_ppm=1_000.0,
            light=1.0,
        )
    elif family == "co2_enrichment":
        state = replace(state, co2_ppm=float(rng.uniform(410.0, 550.0)), light_level=1.0)
        first = _profile(
            "co2-enrichment",
            temperature=state.air_temperature_c,
            humidity=state.relative_humidity_pct,
            co2_enabled=True,
            co2_ppm=float(rng.uniform(950.0, 1_250.0)),
            light=1.0,
        )
    elif family == "co2_unavailable":
        state = replace(state, co2_ppm=float(rng.uniform(410.0, 550.0)), light_level=1.0)
        caps = replace(
            caps, co2_doser=Co2DoserCapabilities(available=False, max_injection_ppm_s=0.0)
        )
        first = _profile(
            "co2-unavailable",
            temperature=state.air_temperature_c,
            humidity=state.relative_humidity_pct,
            co2_enabled=True,
            co2_ppm=1_100.0,
            light=1.0,
        )
    elif family == "actuator_missing":
        missing = CLIMATE_OUTPUT_NAMES[sample_index % len(CLIMATE_OUTPUT_NAMES)]
        if missing == "heater":
            caps = replace(caps, heater=HeaterCapabilities(False, 0.0, 0.9))
            state = replace(state, air_temperature_c=16.0, outside_temperature_c=10.0)
            first = _profile("missing-heater", temperature=25.0, humidity=60.0)
        elif missing == "cooler":
            caps = replace(caps, cooler=CoolerCapabilities(False, 0.0))
            state = replace(state, air_temperature_c=34.0, outside_temperature_c=37.0)
            first = _profile("missing-cooler", temperature=24.0, humidity=60.0)
        elif missing == "exhaust_fan":
            caps = replace(caps, exhaust_fan=ExhaustFanCapabilities(False, 0.0, 0.0))
            state = replace(state, air_temperature_c=31.0, outside_temperature_c=15.0)
            first = _profile("missing-exhaust", temperature=24.0, humidity=60.0)
        elif missing == "humidifier":
            caps = replace(caps, humidifier=HumidifierCapabilities(False, 0.0, 0.5))
            state = replace(state, relative_humidity_pct=30.0, outside_humidity_pct=25.0)
            first = _profile(
                "missing-humidifier", temperature=state.air_temperature_c, humidity=65.0
            )
        elif missing == "dehumidifier":
            caps = replace(caps, dehumidifier=DehumidifierCapabilities(False, 0.0, 0.5))
            state = replace(state, relative_humidity_pct=88.0, outside_humidity_pct=90.0)
            first = _profile(
                "missing-dehumidifier", temperature=state.air_temperature_c, humidity=58.0
            )
        else:
            caps = replace(caps, co2_doser=Co2DoserCapabilities(False, 0.0))
            state = replace(state, co2_ppm=450.0, light_level=1.0)
            first = _profile(
                "missing-co2",
                temperature=state.air_temperature_c,
                humidity=state.relative_humidity_pct,
                co2_enabled=True,
                co2_ppm=1_100.0,
                light=1.0,
            )
    elif family == "sensor_fault":
        fault_sensors = (
            "air_temperature_c",
            "relative_humidity_pct",
            "co2_ppm",
            "outside_temperature_c",
            "outside_humidity_pct",
        )
        fault_sensor = fault_sensors[sample_index % len(fault_sensors)]
        fault_mode = "invalid" if sample_index % 2 == 0 else "stale"
        state = replace(
            state,
            air_temperature_c=28.0,
            relative_humidity_pct=70.0,
            co2_ppm=500.0,
            outside_temperature_c=17.0,
            outside_humidity_pct=45.0,
            light_level=0.8,
        )
        first = _profile(
            "sensor-fault",
            temperature=24.0,
            humidity=60.0,
            co2_enabled=True,
            co2_ppm=950.0,
            light=0.8,
        )

    scenario = _scenario(family, sample_index, seed, state, env, caps, lag)
    return ClimateTrainingEpisode(
        family=family,
        scenario=scenario,
        first_profile=first,
        second_profile=second,
        fault_sensor=fault_sensor,
        fault_mode=fault_mode,
    )


def structured_training_episodes(
    *,
    scenarios_per_family: int,
    seed: int,
) -> tuple[ClimateTrainingEpisode, ...]:
    if scenarios_per_family <= 0:
        raise ValueError("scenarios_per_family must be positive")
    rng = np.random.default_rng(seed)
    episodes: list[ClimateTrainingEpisode] = []
    for family in REQUIRED_SCENARIO_FAMILIES:
        seeds = rng.integers(1, np.iinfo(np.int32).max, size=scenarios_per_family)
        for sample_index, scenario_seed in enumerate(seeds):
            episodes.append(build_training_episode(family, sample_index, int(scenario_seed)))
    return tuple(episodes)


__all__ = [
    "REQUIRED_SCENARIO_FAMILIES",
    "ClimateProfile",
    "ClimateTrainingEpisode",
    "build_training_episode",
    "structured_training_episodes",
]
