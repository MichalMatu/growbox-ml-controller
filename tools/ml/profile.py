"""Growbox hardware profile — single source for twin, panel payload, and training.

A profile describes *what is installed* (sensors, actuators, pots) and physical
scalars (chamber, pot size). It does not store live process values (current T/RH).

Map to:
  - ``Scenario`` for ``SequentialEnvironmentSimulator`` / twin
  - contract-shaped payload for panel / board ``load_scenario``
"""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .scenario_payload import default_scenario
from .simulator import (
    MAX_POTS,
    ControlTargets,
    EnvironmentParameters,
    EnvironmentState,
    FanCapabilities,
    GlobalActuators,
    HeaterCapabilities,
    HeatMatCapabilities,
    HumidifierCapabilities,
    PotConfig,
    PotCultivation,
    PotState,
    PumpCapabilities,
    Scenario,
    SensorValidity,
    SequentialEnvironmentSimulator,
    default_scenario_v2,
)

PROFILE_VERSION = 1

# Default directory for checked-in / user profiles (repo root relative).
PROFILES_DIR = Path(__file__).resolve().parents[2] / "profiles"

CHAMBER_SENSOR_KEYS: tuple[str, ...] = (
    "air_temperature_c",
    "air_humidity_pct",
    "co2_ppm",
    "outside_temperature_c",
    "outside_humidity_pct",
    "outside_co2_ppm",
    "nutrient_solution_temperature_c",
)

GLOBAL_ACTUATOR_KEYS: tuple[str, ...] = (
    "heater",
    "fan",
    "humidifier",
    "dehumidifier",
    "cooler",
    "co2_doser",
    "nutrient_heater",
)


@dataclass
class ChamberProfile:
    growbox_volume_m3: float = 0.8
    thermal_mass_j_per_k: float = 35_000.0
    heat_loss_w_per_k: float = 7.0
    air_leak_rate_ach: float = 0.25


@dataclass
class PotProfile:
    available: bool = False
    pot_volume_l: float = 12.0
    substrate_water_capacity_ml: float = 3_000.0
    transpiration_factor: float = 1.0
    soil_moisture_valid: bool = False
    soil_temperature_valid: bool = False
    irrigation_available: bool = False
    irrigation_flow_ml_s: float = 18.0
    irrigation_maximum_pulse_s: float = 4.0
    irrigation_minimum_interval_s: float = 300.0
    heat_mat_available: bool = False
    heat_mat_max_power_w: float = 25.0
    target_soil_moisture_pct: float = 52.0
    target_soil_temperature_c: float = 22.0


@dataclass
class SensorsProfile:
    """Which contract sensors are installed (→ validity flags)."""

    air_temperature_c: bool = True
    air_humidity_pct: bool = True
    co2_ppm: bool = True
    outside_temperature_c: bool = True
    outside_humidity_pct: bool = True
    outside_co2_ppm: bool = True
    nutrient_solution_temperature_c: bool = False
    lights_active: bool = False  # pseudo / schedule integration

    def as_dict(self) -> dict[str, bool]:
        return asdict(self)


@dataclass
class ActuatorSlotProfile:
    available: bool = False
    # Optional capability scalars (ignored when available is false).
    max_power_w: float | None = None
    efficiency: float | None = None
    max_airflow_m3_h: float | None = None
    minimum_command: float | None = None
    max_output_g_h: float | None = None
    max_removal_g_h: float | None = None
    max_cooling_w: float | None = None
    dose_ppm_per_full_pulse: float | None = None
    maximum_pulse_s: float | None = None
    control_type: str | None = None


@dataclass
class GrowboxProfile:
    """Full mix-and-match description of one physical growbox."""

    profile_id: str = "default"
    version: int = PROFILE_VERSION
    title: str = "Default growbox"
    description: str = ""
    chamber: ChamberProfile = field(default_factory=ChamberProfile)
    pots: list[PotProfile] = field(default_factory=list)
    sensors: SensorsProfile = field(default_factory=SensorsProfile)
    actuators: dict[str, ActuatorSlotProfile] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.pots = _normalize_pots(self.pots)
        self.actuators = _normalize_actuators(self.actuators)
        self.version = int(self.version or PROFILE_VERSION)

    def active_pot_count(self) -> int:
        return sum(1 for pot in self.pots if pot.available)

    def shared_pot_template(self) -> PotProfile:
        """First active pot, or first slot, used as twin shared pot size."""
        for pot in self.pots:
            if pot.available:
                return pot
        return self.pots[0] if self.pots else PotProfile()

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "version": self.version,
            "title": self.title,
            "description": self.description,
            "chamber": asdict(self.chamber),
            "pots": [asdict(p) for p in self.pots],
            "sensors": self.sensors.as_dict(),
            "actuators": {key: _actuator_to_dict(slot) for key, slot in self.actuators.items()},
        }


def _normalize_pots(pots: list[PotProfile] | None) -> list[PotProfile]:
    raw = list(pots or [])
    while len(raw) < MAX_POTS:
        raw.append(PotProfile())
    return raw[:MAX_POTS]


def _default_actuator_map() -> dict[str, ActuatorSlotProfile]:
    return {
        "heater": ActuatorSlotProfile(
            available=True, max_power_w=180.0, efficiency=0.92, control_type="binary"
        ),
        "fan": ActuatorSlotProfile(
            available=True, max_airflow_m3_h=90.0, minimum_command=0.0, control_type="pwm"
        ),
        "humidifier": ActuatorSlotProfile(
            available=True, max_output_g_h=110.0, control_type="binary"
        ),
        "dehumidifier": ActuatorSlotProfile(available=False, max_removal_g_h=80.0),
        "cooler": ActuatorSlotProfile(available=False, max_cooling_w=200.0),
        "co2_doser": ActuatorSlotProfile(
            available=False, dose_ppm_per_full_pulse=120.0, maximum_pulse_s=3.0
        ),
        "nutrient_heater": ActuatorSlotProfile(available=False, max_power_w=150.0, efficiency=0.95),
    }


def _normalize_actuators(
    actuators: dict[str, ActuatorSlotProfile] | None,
) -> dict[str, ActuatorSlotProfile]:
    base = _default_actuator_map()
    if not actuators:
        return base
    for key, slot in actuators.items():
        if key in base:
            base[key] = slot
    return base


def _actuator_to_dict(slot: ActuatorSlotProfile) -> dict[str, Any]:
    data = {"available": bool(slot.available)}
    for name in (
        "max_power_w",
        "efficiency",
        "max_airflow_m3_h",
        "minimum_command",
        "max_output_g_h",
        "max_removal_g_h",
        "max_cooling_w",
        "dose_ppm_per_full_pulse",
        "maximum_pulse_s",
        "control_type",
    ):
        value = getattr(slot, name)
        if value is not None:
            data[name] = value
    return data


def _actuator_from_dict(raw: dict[str, Any] | None) -> ActuatorSlotProfile:
    raw = raw or {}
    return ActuatorSlotProfile(
        available=bool(raw.get("available", False)),
        max_power_w=_opt_float(raw.get("max_power_w")),
        efficiency=_opt_float(raw.get("efficiency")),
        max_airflow_m3_h=_opt_float(raw.get("max_airflow_m3_h")),
        minimum_command=_opt_float(raw.get("minimum_command")),
        max_output_g_h=_opt_float(raw.get("max_output_g_h")),
        max_removal_g_h=_opt_float(raw.get("max_removal_g_h")),
        max_cooling_w=_opt_float(raw.get("max_cooling_w")),
        dose_ppm_per_full_pulse=_opt_float(raw.get("dose_ppm_per_full_pulse")),
        maximum_pulse_s=_opt_float(raw.get("maximum_pulse_s")),
        control_type=str(raw["control_type"]) if raw.get("control_type") is not None else None,
    )


def _opt_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def _pot_from_dict(raw: dict[str, Any] | None) -> PotProfile:
    raw = raw or {}
    return PotProfile(
        available=bool(raw.get("available", False)),
        pot_volume_l=float(raw.get("pot_volume_l", 12.0)),
        substrate_water_capacity_ml=float(raw.get("substrate_water_capacity_ml", 3_000.0)),
        transpiration_factor=float(raw.get("transpiration_factor", 1.0)),
        soil_moisture_valid=bool(raw.get("soil_moisture_valid", False)),
        soil_temperature_valid=bool(raw.get("soil_temperature_valid", False)),
        irrigation_available=bool(raw.get("irrigation_available", False)),
        irrigation_flow_ml_s=float(raw.get("irrigation_flow_ml_s", 18.0)),
        irrigation_maximum_pulse_s=float(raw.get("irrigation_maximum_pulse_s", 4.0)),
        irrigation_minimum_interval_s=float(raw.get("irrigation_minimum_interval_s", 300.0)),
        heat_mat_available=bool(raw.get("heat_mat_available", False)),
        heat_mat_max_power_w=float(raw.get("heat_mat_max_power_w", 25.0)),
        target_soil_moisture_pct=float(raw.get("target_soil_moisture_pct", 52.0)),
        target_soil_temperature_c=float(raw.get("target_soil_temperature_c", 22.0)),
    )


def profile_from_dict(data: dict[str, Any]) -> GrowboxProfile:
    chamber_raw = data.get("chamber") or {}
    sensors_raw = data.get("sensors") or {}
    pots_raw = data.get("pots") or []
    actuators_raw = data.get("actuators") or {}
    return GrowboxProfile(
        profile_id=str(data.get("profile_id", "unnamed")),
        version=int(data.get("version", PROFILE_VERSION)),
        title=str(data.get("title", "")),
        description=str(data.get("description", "")),
        chamber=ChamberProfile(
            growbox_volume_m3=float(chamber_raw.get("growbox_volume_m3", 0.8)),
            thermal_mass_j_per_k=float(chamber_raw.get("thermal_mass_j_per_k", 35_000.0)),
            heat_loss_w_per_k=float(chamber_raw.get("heat_loss_w_per_k", 7.0)),
            air_leak_rate_ach=float(chamber_raw.get("air_leak_rate_ach", 0.25)),
        ),
        pots=[_pot_from_dict(p if isinstance(p, dict) else {}) for p in pots_raw],
        sensors=SensorsProfile(
            **{
                key: bool(sensors_raw.get(key, getattr(SensorsProfile(), key)))
                for key in SensorsProfile().as_dict()
            }
        ),
        actuators={
            key: _actuator_from_dict(actuators_raw.get(key)) for key in _default_actuator_map()
        },
    )


def default_profile(
    *, profile_id: str = "default", title: str = "Default growbox"
) -> GrowboxProfile:
    """Matches ``default_scenario_v2`` hardware: 1 pot, heater/fan/humid, basic sensors."""
    pots = [PotProfile() for _ in range(MAX_POTS)]
    pots[0] = PotProfile(
        available=True,
        pot_volume_l=12.0,
        substrate_water_capacity_ml=3_000.0,
        soil_moisture_valid=True,
        soil_temperature_valid=True,
        irrigation_available=True,
    )
    return GrowboxProfile(
        profile_id=profile_id,
        title=title,
        description="Single active pot; heater, fan, humidifier available.",
        chamber=ChamberProfile(),
        pots=pots,
        sensors=SensorsProfile(
            air_temperature_c=True,
            air_humidity_pct=True,
            co2_ppm=True,
            outside_temperature_c=True,
            outside_humidity_pct=True,
            outside_co2_ppm=True,
            nutrient_solution_temperature_c=False,
            lights_active=False,
        ),
        actuators=_default_actuator_map(),
    )


def load_profile(path: str | Path) -> GrowboxProfile:
    path = Path(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"profile must be a JSON object: {path}")
    return profile_from_dict(data)


def save_profile(profile: GrowboxProfile, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(profile.to_dict(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return path


def list_profiles(directory: str | Path | None = None) -> list[Path]:
    root = Path(directory) if directory is not None else PROFILES_DIR
    if not root.is_dir():
        return []
    return sorted(root.glob("*.json"))


def _pot_config_from_profile(pot: PotProfile) -> PotConfig:
    if not pot.available:
        return PotConfig()
    return PotConfig(
        available=True,
        soil_moisture_valid=bool(pot.soil_moisture_valid),
        soil_temperature_valid=bool(pot.soil_temperature_valid),
        cultivation=PotCultivation(
            pot_volume_l=float(pot.pot_volume_l),
            substrate_water_capacity_ml=float(pot.substrate_water_capacity_ml),
            transpiration_factor=float(pot.transpiration_factor),
        ),
        irrigation=PumpCapabilities(
            available=bool(pot.irrigation_available),
            flow_ml_s=float(pot.irrigation_flow_ml_s),
            maximum_pulse_s=float(pot.irrigation_maximum_pulse_s),
            minimum_interval_s=float(pot.irrigation_minimum_interval_s),
        ),
        heat_mat=HeatMatCapabilities(
            available=bool(pot.heat_mat_available),
            max_power_w=float(pot.heat_mat_max_power_w),
        ),
        target_soil_moisture_pct=float(pot.target_soil_moisture_pct),
        target_soil_temperature_c=float(pot.target_soil_temperature_c),
    )


def _global_actuators_from_profile(profile: GrowboxProfile) -> GlobalActuators:
    defaults = GlobalActuators()
    act = profile.actuators

    def heater() -> HeaterCapabilities:
        slot = act.get("heater", ActuatorSlotProfile())
        base = defaults.heater
        return HeaterCapabilities(
            available=bool(slot.available),
            max_power_w=float(
                slot.max_power_w if slot.max_power_w is not None else base.max_power_w
            ),
            efficiency=float(slot.efficiency if slot.efficiency is not None else base.efficiency),
        )

    def fan() -> FanCapabilities:
        slot = act.get("fan", ActuatorSlotProfile())
        base = defaults.fan
        return FanCapabilities(
            available=bool(slot.available),
            max_airflow_m3_h=float(
                slot.max_airflow_m3_h
                if slot.max_airflow_m3_h is not None
                else base.max_airflow_m3_h
            ),
            minimum_command=float(
                slot.minimum_command if slot.minimum_command is not None else base.minimum_command
            ),
        )

    def humid() -> HumidifierCapabilities:
        slot = act.get("humidifier", ActuatorSlotProfile())
        base = defaults.humidifier
        return HumidifierCapabilities(
            available=bool(slot.available),
            max_output_g_h=float(
                slot.max_output_g_h if slot.max_output_g_h is not None else base.max_output_g_h
            ),
        )

    # Keep other actuators from defaults with availability from profile
    from .simulator import (
        Co2DoserCapabilities,
        CoolerCapabilities,
        DehumidifierCapabilities,
        LightsConfig,
        NutrientHeaterCapabilities,
    )

    deh = act.get("dehumidifier", ActuatorSlotProfile())
    cool = act.get("cooler", ActuatorSlotProfile())
    co2 = act.get("co2_doser", ActuatorSlotProfile())
    nut = act.get("nutrient_heater", ActuatorSlotProfile())
    return GlobalActuators(
        heater=heater(),
        fan=fan(),
        humidifier=humid(),
        dehumidifier=DehumidifierCapabilities(
            available=bool(deh.available),
            max_removal_g_h=float(
                deh.max_removal_g_h
                if deh.max_removal_g_h is not None
                else defaults.dehumidifier.max_removal_g_h
            ),
        ),
        cooler=CoolerCapabilities(
            available=bool(cool.available),
            max_cooling_w=float(
                cool.max_cooling_w
                if cool.max_cooling_w is not None
                else defaults.cooler.max_cooling_w
            ),
        ),
        co2_doser=Co2DoserCapabilities(
            available=bool(co2.available),
            dose_ppm_per_full_pulse=float(
                co2.dose_ppm_per_full_pulse
                if co2.dose_ppm_per_full_pulse is not None
                else defaults.co2_doser.dose_ppm_per_full_pulse
            ),
            maximum_pulse_s=float(
                co2.maximum_pulse_s
                if co2.maximum_pulse_s is not None
                else defaults.co2_doser.maximum_pulse_s
            ),
        ),
        nutrient_heater=NutrientHeaterCapabilities(
            available=bool(nut.available),
            max_power_w=float(
                nut.max_power_w
                if nut.max_power_w is not None
                else defaults.nutrient_heater.max_power_w
            ),
            efficiency=float(
                nut.efficiency
                if nut.efficiency is not None
                else defaults.nutrient_heater.efficiency
            ),
        ),
        lights=LightsConfig(),
    )


def _sensor_validity_from_profile(profile: GrowboxProfile) -> SensorValidity:
    s = profile.sensors
    pot_m = tuple(bool(p.available and p.soil_moisture_valid) for p in profile.pots[:MAX_POTS])
    pot_t = tuple(bool(p.available and p.soil_temperature_valid) for p in profile.pots[:MAX_POTS])
    while len(pot_m) < MAX_POTS:
        pot_m = (*pot_m, False)
        pot_t = (*pot_t, False)
    return SensorValidity(
        air_temperature_c=bool(s.air_temperature_c),
        air_humidity_pct=bool(s.air_humidity_pct),
        co2_ppm=bool(s.co2_ppm),
        outside_temperature_c=bool(s.outside_temperature_c),
        outside_humidity_pct=bool(s.outside_humidity_pct),
        outside_co2_ppm=bool(s.outside_co2_ppm),
        nutrient_solution_temperature_c=bool(s.nutrient_solution_temperature_c),
        pot_soil_moisture=(pot_m[0], pot_m[1], pot_m[2], pot_m[3]),
        pot_soil_temperature=(pot_t[0], pot_t[1], pot_t[2], pot_t[3]),
    )


def profile_to_scenario(
    profile: GrowboxProfile,
    *,
    seed: int = 0,
    scenario_id: str | None = None,
    initial_state: EnvironmentState | None = None,
) -> Scenario:
    """Build a simulator Scenario from a hardware profile."""
    base = default_scenario_v2(scenario_id=scenario_id or profile.profile_id, seed=seed)
    pots = tuple(_pot_config_from_profile(p) for p in profile.pots)
    # Ensure exactly 4
    pot_list = list(pots)
    while len(pot_list) < MAX_POTS:
        pot_list.append(PotConfig())
    pots_t = (pot_list[0], pot_list[1], pot_list[2], pot_list[3])

    state = deepcopy(initial_state) if initial_state is not None else deepcopy(base.initial_state)
    # Align pot state length; leave values, mark lights from sensors pseudo
    state.lights_active = bool(profile.sensors.lights_active and state.lights_active)

    return Scenario(
        scenario_id=scenario_id or profile.profile_id,
        seed=seed,
        initial_state=state,
        environment=EnvironmentParameters(
            growbox_volume_m3=float(profile.chamber.growbox_volume_m3),
            thermal_mass_j_per_k=float(profile.chamber.thermal_mass_j_per_k),
            heat_loss_w_per_k=float(profile.chamber.heat_loss_w_per_k),
            air_leak_rate_ach=float(profile.chamber.air_leak_rate_ach),
        ),
        actuators=_global_actuators_from_profile(profile),
        pots=pots_t,
        targets=ControlTargets(),
        validity=_sensor_validity_from_profile(profile),
        timestep_s=base.timestep_s,
        response_lag=base.response_lag,
        chamber_model=base.chamber_model,
    )


def profile_from_scenario(scenario: Scenario, *, profile_id: str | None = None) -> GrowboxProfile:
    """Extract a profile from an existing simulator Scenario."""
    pots: list[PotProfile] = []
    for pot in scenario.pots:
        pots.append(
            PotProfile(
                available=bool(pot.available),
                pot_volume_l=float(pot.cultivation.pot_volume_l),
                substrate_water_capacity_ml=float(pot.cultivation.substrate_water_capacity_ml),
                transpiration_factor=float(pot.cultivation.transpiration_factor),
                soil_moisture_valid=bool(pot.soil_moisture_valid),
                soil_temperature_valid=bool(pot.soil_temperature_valid),
                irrigation_available=bool(pot.irrigation.available),
                irrigation_flow_ml_s=float(pot.irrigation.flow_ml_s),
                irrigation_maximum_pulse_s=float(pot.irrigation.maximum_pulse_s),
                irrigation_minimum_interval_s=float(pot.irrigation.minimum_interval_s),
                heat_mat_available=bool(pot.heat_mat.available),
                heat_mat_max_power_w=float(pot.heat_mat.max_power_w),
                target_soil_moisture_pct=float(pot.target_soil_moisture_pct),
                target_soil_temperature_c=float(pot.target_soil_temperature_c),
            )
        )
    val = scenario.validity
    caps = scenario.actuators
    actuators = {
        "heater": ActuatorSlotProfile(
            available=caps.heater.available,
            max_power_w=caps.heater.max_power_w,
            efficiency=caps.heater.efficiency,
        ),
        "fan": ActuatorSlotProfile(
            available=caps.fan.available,
            max_airflow_m3_h=caps.fan.max_airflow_m3_h,
            minimum_command=caps.fan.minimum_command,
        ),
        "humidifier": ActuatorSlotProfile(
            available=caps.humidifier.available,
            max_output_g_h=caps.humidifier.max_output_g_h,
        ),
        "dehumidifier": ActuatorSlotProfile(
            available=caps.dehumidifier.available,
            max_removal_g_h=caps.dehumidifier.max_removal_g_h,
        ),
        "cooler": ActuatorSlotProfile(
            available=caps.cooler.available,
            max_cooling_w=caps.cooler.max_cooling_w,
        ),
        "co2_doser": ActuatorSlotProfile(
            available=caps.co2_doser.available,
            dose_ppm_per_full_pulse=caps.co2_doser.dose_ppm_per_full_pulse,
            maximum_pulse_s=caps.co2_doser.maximum_pulse_s,
        ),
        "nutrient_heater": ActuatorSlotProfile(
            available=caps.nutrient_heater.available,
            max_power_w=caps.nutrient_heater.max_power_w,
            efficiency=caps.nutrient_heater.efficiency,
        ),
    }
    return GrowboxProfile(
        profile_id=profile_id or scenario.scenario_id,
        title=scenario.scenario_id,
        chamber=ChamberProfile(
            growbox_volume_m3=float(scenario.environment.growbox_volume_m3),
            thermal_mass_j_per_k=float(scenario.environment.thermal_mass_j_per_k),
            heat_loss_w_per_k=float(scenario.environment.heat_loss_w_per_k),
            air_leak_rate_ach=float(scenario.environment.air_leak_rate_ach),
        ),
        pots=pots,
        sensors=SensorsProfile(
            air_temperature_c=bool(val.air_temperature_c),
            air_humidity_pct=bool(val.air_humidity_pct),
            co2_ppm=bool(val.co2_ppm),
            outside_temperature_c=bool(val.outside_temperature_c),
            outside_humidity_pct=bool(val.outside_humidity_pct),
            outside_co2_ppm=bool(val.outside_co2_ppm),
            nutrient_solution_temperature_c=bool(val.nutrient_solution_temperature_c),
            lights_active=bool(scenario.initial_state.lights_active),
        ),
        actuators=actuators,
    )


def profile_from_simulator(sim: SequentialEnvironmentSimulator) -> GrowboxProfile:
    return profile_from_scenario(sim.scenario, profile_id=sim.scenario.scenario_id)


def apply_profile_to_simulator(
    sim: SequentialEnvironmentSimulator,
    profile: GrowboxProfile,
    *,
    preserve_state: bool = True,
) -> set[str]:
    """Replace simulator scenario from profile. Returns changed geometry-ish keys."""
    before = profile_from_simulator(sim)
    changed: set[str] = set()
    if abs(before.chamber.growbox_volume_m3 - profile.chamber.growbox_volume_m3) > 1e-12:
        changed.add("growbox_volume_m3")
    if before.active_pot_count() != profile.active_pot_count():
        changed.add("active_pots")
    b_pot = before.shared_pot_template()
    a_pot = profile.shared_pot_template()
    if abs(b_pot.pot_volume_l - a_pot.pot_volume_l) > 1e-12:
        changed.add("pot_volume_l")
    if abs(b_pot.substrate_water_capacity_ml - a_pot.substrate_water_capacity_ml) > 1e-9:
        changed.add("substrate_water_capacity_ml")
    if abs(before.chamber.thermal_mass_j_per_k - profile.chamber.thermal_mass_j_per_k) > 1e-9:
        changed.add("thermal_mass_j_per_k")
    if abs(before.chamber.heat_loss_w_per_k - profile.chamber.heat_loss_w_per_k) > 1e-12:
        changed.add("heat_loss_w_per_k")
    if abs(before.chamber.air_leak_rate_ach - profile.chamber.air_leak_rate_ach) > 1e-12:
        changed.add("air_leak_rate_ach")

    state = deepcopy(sim.state) if preserve_state else None
    new_scenario = profile_to_scenario(
        profile,
        seed=sim.seed,
        scenario_id=profile.profile_id,
        initial_state=sim.scenario.initial_state,
    )
    sim.scenario = new_scenario
    if state is not None:
        sim.state = state
        # Ensure pot list length
        while len(sim.state.pots) < MAX_POTS:
            sim.state.pots.append(PotState())
        sim.state.pots = sim.state.pots[:MAX_POTS]
    return changed


def profile_to_payload(profile: GrowboxProfile, *, seed: int = 101) -> dict[str, Any]:
    """Contract-shaped scenario dict for panel / board (merged onto nominal defaults)."""
    payload = default_scenario(seed=seed, preset="nominal")
    payload["seed"] = seed
    payload["environment"] = {
        "growbox_volume_m3": float(profile.chamber.growbox_volume_m3),
        "thermal_mass_j_per_k": float(profile.chamber.thermal_mass_j_per_k),
        "heat_loss_w_per_k": float(profile.chamber.heat_loss_w_per_k),
        "air_leak_rate_ach": float(profile.chamber.air_leak_rate_ach),
    }
    s = profile.sensors
    payload["validity"] = {
        "air_temperature_c": bool(s.air_temperature_c),
        "air_humidity_pct": bool(s.air_humidity_pct),
        "co2_ppm": bool(s.co2_ppm),
        "outside_temperature_c": bool(s.outside_temperature_c),
        "outside_humidity_pct": bool(s.outside_humidity_pct),
        "outside_co2_ppm": bool(s.outside_co2_ppm),
        "nutrient_solution_temperature_c": bool(s.nutrient_solution_temperature_c),
    }
    payload["pseudo"] = {"lights_active": bool(s.lights_active)}

    pots_out: list[dict[str, Any]] = []
    for pot in profile.pots:
        if not pot.available:
            pots_out.append(
                {
                    "available": False,
                    "sensors": {"soil_moisture_pct": 50.0, "soil_temperature_c": 20.0},
                    "validity": {"soil_moisture_pct": False, "soil_temperature_c": False},
                    "cultivation": {
                        "pot_volume_l": float(pot.pot_volume_l),
                        "substrate_water_capacity_ml": float(pot.substrate_water_capacity_ml),
                        "transpiration_factor": float(pot.transpiration_factor),
                    },
                    "targets": {
                        "soil_moisture_pct": float(pot.target_soil_moisture_pct),
                        "soil_temperature_c": float(pot.target_soil_temperature_c),
                    },
                    "irrigation": {
                        "available": False,
                        "flow_ml_s": 0.0,
                        "maximum_pulse_s": 0.0,
                        "minimum_interval_s": 0.0,
                        "control_type": "binary",
                    },
                    "heat_mat": {
                        "available": False,
                        "max_power_w": 0.0,
                        "control_type": "binary",
                    },
                    "previous": {"irrigation": 0.0, "heat_mat": 0.0},
                }
            )
            continue
        pots_out.append(
            {
                "available": True,
                "sensors": {"soil_moisture_pct": 44.0, "soil_temperature_c": 22.0},
                "validity": {
                    "soil_moisture_pct": bool(pot.soil_moisture_valid),
                    "soil_temperature_c": bool(pot.soil_temperature_valid),
                },
                "cultivation": {
                    "pot_volume_l": float(pot.pot_volume_l),
                    "substrate_water_capacity_ml": float(pot.substrate_water_capacity_ml),
                    "transpiration_factor": float(pot.transpiration_factor),
                },
                "targets": {
                    "soil_moisture_pct": float(pot.target_soil_moisture_pct),
                    "soil_temperature_c": float(pot.target_soil_temperature_c),
                },
                "irrigation": {
                    "available": bool(pot.irrigation_available),
                    "flow_ml_s": float(pot.irrigation_flow_ml_s),
                    "maximum_pulse_s": float(pot.irrigation_maximum_pulse_s),
                    "minimum_interval_s": float(pot.irrigation_minimum_interval_s),
                    "control_type": "binary",
                },
                "heat_mat": {
                    "available": bool(pot.heat_mat_available),
                    "max_power_w": float(pot.heat_mat_max_power_w),
                    "control_type": "binary",
                },
                "previous": {"irrigation": 0.0, "heat_mat": 0.0},
            }
        )
    payload["pots"] = pots_out

    # Overlay global actuators availability + known limits
    acts = payload.setdefault("actuators", {})
    for key, slot in profile.actuators.items():
        entry = dict(acts.get(key) or {})
        entry["available"] = bool(slot.available)
        for attr, json_key in (
            ("max_power_w", "max_power_w"),
            ("efficiency", "efficiency"),
            ("max_airflow_m3_h", "max_airflow_m3_h"),
            ("minimum_command", "minimum_command"),
            ("max_output_g_h", "max_output_g_h"),
            ("max_removal_g_h", "max_removal_g_h"),
            ("max_cooling_w", "max_cooling_w"),
            ("dose_ppm_per_full_pulse", "dose_ppm_per_full_pulse"),
            ("maximum_pulse_s", "maximum_pulse_s"),
            ("control_type", "control_type"),
        ):
            value = getattr(slot, attr)
            if value is not None:
                entry[json_key] = value
        if not slot.available:
            # Zero dangerous limits when disabled
            for zero_key in (
                "max_power_w",
                "max_airflow_m3_h",
                "max_output_g_h",
                "max_removal_g_h",
                "max_cooling_w",
                "dose_ppm_per_full_pulse",
            ):
                if zero_key in entry:
                    entry[zero_key] = 0.0
        acts[key] = entry
    payload["actuators"] = acts
    payload["profile_id"] = profile.profile_id
    return payload


# Geometry keys for twin hard refresh (shared with twin.config)
PROFILE_GEOMETRY_KEYS = frozenset({"growbox_volume_m3", "active_pots", "pot_volume_l"})


def needs_geometry_rebuild(changed_keys: set[str]) -> bool:
    return bool(changed_keys & PROFILE_GEOMETRY_KEYS)
