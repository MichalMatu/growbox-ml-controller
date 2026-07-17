"""Twin keyboard configurator — full GrowboxProfile hardware edit.

Root menu (EN): Chamber / Pots / Sensors / Outputs
  Esc = back one level · p = full exit to RUNTIME

Numeric rows: -/= fine, [/] coarse
Flag rows: -/=/space/Enter toggle ON/off
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Literal

from ..profile import (
    PROFILE_GEOMETRY_KEYS,
    ActuatorSlotProfile,
    GrowboxProfile,
    PotProfile,
    apply_profile_to_simulator,
    needs_geometry_rebuild,
    profile_from_simulator,
)
from ..simulator import SequentialEnvironmentSimulator

GEOMETRY_KEYS = PROFILE_GEOMETRY_KEYS
Level = Literal["root", "section"]
RowKind = Literal["flag", "num"]

MENU_SECTIONS: tuple[tuple[str, str], ...] = (
    ("chamber", "Chamber"),
    ("pots", "Pots"),
    ("sensors", "Sensors"),
    ("outputs", "Outputs"),
)
SECTION_ORDER: tuple[str, ...] = tuple(sid for sid, _ in MENU_SECTIONS)
SECTION_LABELS: dict[str, str] = {sid: label for sid, label in MENU_SECTIONS}


@dataclass(frozen=True)
class ConfigField:
    """Legacy alias for numeric field metadata (tests / GROWBOX_FIELDS)."""

    key: str
    label: str
    step: float
    coarse_step: float
    min_value: float
    max_value: float
    decimals: int = 2
    display_scale: float = 1.0
    display_suffix: str = ""


@dataclass(frozen=True)
class FlagField:
    key: str
    label: str


@dataclass(frozen=True)
class Row:
    """One HUD line: flag toggle or numeric scalar."""

    kind: RowKind
    key: str
    label: str
    step: float = 1.0
    coarse_step: float = 1.0
    min_value: float = 0.0
    max_value: float = 100.0
    decimals: int = 2
    display_scale: float = 1.0
    display_suffix: str = ""


def _num(
    key: str,
    label: str,
    step: float,
    coarse: float,
    lo: float,
    hi: float,
    decimals: int = 2,
    scale: float = 1.0,
    suffix: str = "",
) -> Row:
    return Row(
        "num",
        key,
        label,
        step,
        coarse,
        lo,
        hi,
        decimals,
        scale,
        suffix,
    )


def _flag(key: str, label: str) -> Row:
    return Row("flag", key, label)


CHAMBER_ROWS: tuple[Row, ...] = (
    _num("growbox_volume_m3", "volume", 0.1, 0.5, 0.2, 5.0, 2, 1.0, " m3"),
    _num("thermal_mass_j_per_k", "thermal mass", 1000, 5000, 5000, 120000, 0, 0.001, " kJ/K"),
    _num("heat_loss_w_per_k", "heat loss", 0.5, 2.0, 1.0, 40.0, 1, 1.0, " W/K"),
    _num("air_leak_rate_ach", "leak ACH", 0.05, 0.25, 0.0, 3.0, 2, 1.0, " /h"),
)

POTS_ROWS: tuple[Row, ...] = (
    _num("active_pots", "active pots", 1, 1, 0, 4, 0),
    _num("pot_volume_l", "pot volume", 1, 5, 1, 50, 1, 1.0, " L"),
    _num("substrate_water_capacity_ml", "pot water cap", 100, 500, 200, 15000, 0, 1.0, " ml"),
    _num("transpiration_factor", "transpiration", 0.1, 0.5, 0.0, 5.0, 2),
    _num("irrigation_flow_ml_s", "irr flow", 1, 5, 0, 100, 1, 1.0, " ml/s"),
    _num("irrigation_maximum_pulse_s", "irr pulse", 0.5, 2.0, 0.5, 60, 1, 1.0, " s"),
    _num("irrigation_minimum_interval_s", "irr interval", 30, 60, 0, 7200, 0, 1.0, " s"),
    _num("heat_mat_max_power_w", "mat max", 5, 25, 0, 200, 0, 1.0, " W"),
    _num("target_soil_moisture_pct", "tgt soil", 1, 5, 0, 100, 0, 1.0, " %"),
    _num("target_soil_temperature_c", "tgt soil T", 0.5, 2.0, 5, 40, 1, 1.0, " C"),
)

SENSOR_ROWS: tuple[Row, ...] = (
    _flag("air_temperature_c", "air T"),
    _flag("air_humidity_pct", "air RH"),
    _flag("co2_ppm", "CO2"),
    _flag("outside_temperature_c", "out T"),
    _flag("outside_humidity_pct", "out RH"),
    _flag("outside_co2_ppm", "out CO2"),
    _flag("nutrient_solution_temperature_c", "nutrient T"),
    _flag("lights_active", "lights sched"),
    _flag("pot1_soil_moisture", "P1 soil moist"),
    _flag("pot1_soil_temperature", "P1 soil T"),
    _flag("pot2_soil_moisture", "P2 soil moist"),
    _flag("pot2_soil_temperature", "P2 soil T"),
    _flag("pot3_soil_moisture", "P3 soil moist"),
    _flag("pot3_soil_temperature", "P3 soil T"),
    _flag("pot4_soil_moisture", "P4 soil moist"),
    _flag("pot4_soil_temperature", "P4 soil T"),
)

OUTPUT_ROWS: tuple[Row, ...] = (
    _flag("heater", "heater"),
    _num("heater_max_power_w", "  heater max", 10, 50, 0, 2000, 0, 1.0, " W"),
    _num("heater_efficiency", "  heater eff", 0.01, 0.05, 0.1, 1.0, 2),
    _flag("fan", "fan"),
    _num("fan_max_airflow_m3_h", "  fan max", 5, 20, 0, 1000, 0, 1.0, " m3/h"),
    _num("fan_minimum_command", "  fan min cmd", 0.05, 0.1, 0.0, 1.0, 2),
    _flag("humidifier", "humidifier"),
    _num("humidifier_max_output_g_h", "  humid max", 10, 50, 0, 2000, 0, 1.0, " g/h"),
    _flag("dehumidifier", "dehumidifier"),
    _num("dehumidifier_max_removal_g_h", "  dehum max", 10, 50, 0, 2000, 0, 1.0, " g/h"),
    _flag("cooler", "cooler"),
    _num("cooler_max_cooling_w", "  cooler max", 10, 50, 0, 2000, 0, 1.0, " W"),
    _flag("co2_doser", "CO2 doser"),
    _num("co2_dose_ppm", "  CO2 dose", 10, 50, 0, 2000, 0, 1.0, " ppm"),
    _num("co2_maximum_pulse_s", "  CO2 pulse", 0.5, 1.0, 0, 30, 1, 1.0, " s"),
    _flag("nutrient_heater", "nutrient heat"),
    _num("nutrient_heater_max_power_w", "  nutr max", 10, 50, 0, 1000, 0, 1.0, " W"),
    _num("nutrient_heater_efficiency", "  nutr eff", 0.01, 0.05, 0.1, 1.0, 2),
    _flag("lights_heat", "lights heat"),
    _num("lights_max_heat_w", "  lights max", 10, 50, 0, 1000, 0, 1.0, " W"),
    _flag("irrigation_pot_1", "irr pot 1"),
    _flag("irrigation_pot_2", "irr pot 2"),
    _flag("irrigation_pot_3", "irr pot 3"),
    _flag("irrigation_pot_4", "irr pot 4"),
    _flag("heat_mat_pot_1", "mat pot 1"),
    _flag("heat_mat_pot_2", "mat pot 2"),
    _flag("heat_mat_pot_3", "mat pot 3"),
    _flag("heat_mat_pot_4", "mat pot 4"),
)

SECTION_ROWS: dict[str, tuple[Row, ...]] = {
    "chamber": CHAMBER_ROWS,
    "pots": POTS_ROWS,
    "sensors": SENSOR_ROWS,
    "outputs": OUTPUT_ROWS,
}

# Back-compat names used by tests
CHAMBER_FIELDS = tuple(
    ConfigField(
        r.key,
        r.label,
        r.step,
        r.coarse_step,
        r.min_value,
        r.max_value,
        r.decimals,
        r.display_scale,
        r.display_suffix,
    )
    for r in CHAMBER_ROWS
)
POTS_FIELDS = tuple(
    ConfigField(
        r.key,
        r.label,
        r.step,
        r.coarse_step,
        r.min_value,
        r.max_value,
        r.decimals,
        r.display_scale,
        r.display_suffix,
    )
    for r in POTS_ROWS
    if r.kind == "num"
)
SENSOR_FLAGS = tuple(FlagField(r.key, r.label) for r in SENSOR_ROWS)
OUTPUT_FLAGS = tuple(FlagField(r.key, r.label) for r in OUTPUT_ROWS if r.kind == "flag")
SECTION_FIELDS: dict[str, tuple[ConfigField, ...]] = {
    "chamber": CHAMBER_FIELDS,
    "pots": POTS_FIELDS,
}
SECTION_FLAGS: dict[str, tuple[FlagField, ...]] = {
    "sensors": SENSOR_FLAGS,
    "outputs": OUTPUT_FLAGS,
}
GROWBOX_FIELDS: tuple[ConfigField, ...] = CHAMBER_FIELDS + POTS_FIELDS


@dataclass
class GrowboxConfig:
    """Flat numeric bag for chamber/pots/actuator limits."""

    values: dict[str, float] = field(default_factory=dict)

    # Attribute-style access for older tests
    @property
    def growbox_volume_m3(self) -> float:
        return self.get("growbox_volume_m3")

    @property
    def thermal_mass_j_per_k(self) -> float:
        return self.get("thermal_mass_j_per_k")

    @property
    def heat_loss_w_per_k(self) -> float:
        return self.get("heat_loss_w_per_k")

    @property
    def air_leak_rate_ach(self) -> float:
        return self.get("air_leak_rate_ach")

    @property
    def active_pots(self) -> int:
        return int(round(self.get("active_pots")))

    @property
    def pot_volume_l(self) -> float:
        return self.get("pot_volume_l")

    @property
    def substrate_water_capacity_ml(self) -> float:
        return self.get("substrate_water_capacity_ml")

    def as_dict(self) -> dict[str, float]:
        return dict(self.values)

    def get(self, key: str) -> float:
        if key not in self.values:
            raise KeyError(key)
        return float(self.values[key])

    def with_value(self, key: str, value: float) -> GrowboxConfig:
        data = dict(self.values)
        data[key] = float(value)
        return GrowboxConfig(values=data)


def _act(profile: GrowboxProfile, name: str) -> ActuatorSlotProfile:
    return profile.actuators.get(name, ActuatorSlotProfile())


def flat_from_profile(profile: GrowboxProfile) -> GrowboxConfig:
    pot = profile.shared_pot_template()
    h, f, u = _act(profile, "heater"), _act(profile, "fan"), _act(profile, "humidifier")
    d, c, co2 = _act(profile, "dehumidifier"), _act(profile, "cooler"), _act(profile, "co2_doser")
    n, li = _act(profile, "nutrient_heater"), _act(profile, "lights")
    data = {
        "growbox_volume_m3": float(profile.chamber.growbox_volume_m3),
        "thermal_mass_j_per_k": float(profile.chamber.thermal_mass_j_per_k),
        "heat_loss_w_per_k": float(profile.chamber.heat_loss_w_per_k),
        "air_leak_rate_ach": float(profile.chamber.air_leak_rate_ach),
        "active_pots": float(max(0, min(4, profile.active_pot_count()))),
        "pot_volume_l": float(pot.pot_volume_l),
        "substrate_water_capacity_ml": float(pot.substrate_water_capacity_ml),
        "transpiration_factor": float(pot.transpiration_factor),
        "irrigation_flow_ml_s": float(pot.irrigation_flow_ml_s),
        "irrigation_maximum_pulse_s": float(pot.irrigation_maximum_pulse_s),
        "irrigation_minimum_interval_s": float(pot.irrigation_minimum_interval_s),
        "heat_mat_max_power_w": float(pot.heat_mat_max_power_w),
        "target_soil_moisture_pct": float(pot.target_soil_moisture_pct),
        "target_soil_temperature_c": float(pot.target_soil_temperature_c),
        "heater_max_power_w": float(h.max_power_w if h.max_power_w is not None else 180.0),
        "heater_efficiency": float(h.efficiency if h.efficiency is not None else 0.92),
        "fan_max_airflow_m3_h": float(
            f.max_airflow_m3_h if f.max_airflow_m3_h is not None else 90.0
        ),
        "fan_minimum_command": float(f.minimum_command if f.minimum_command is not None else 0.0),
        "humidifier_max_output_g_h": float(
            u.max_output_g_h if u.max_output_g_h is not None else 110.0
        ),
        "dehumidifier_max_removal_g_h": float(
            d.max_removal_g_h if d.max_removal_g_h is not None else 80.0
        ),
        "cooler_max_cooling_w": float(c.max_cooling_w if c.max_cooling_w is not None else 200.0),
        "co2_dose_ppm": float(
            co2.dose_ppm_per_full_pulse if co2.dose_ppm_per_full_pulse is not None else 120.0
        ),
        "co2_maximum_pulse_s": float(
            co2.maximum_pulse_s if co2.maximum_pulse_s is not None else 3.0
        ),
        "nutrient_heater_max_power_w": float(n.max_power_w if n.max_power_w is not None else 150.0),
        "nutrient_heater_efficiency": float(n.efficiency if n.efficiency is not None else 0.95),
        "lights_max_heat_w": float(li.max_power_w if li.max_power_w is not None else 120.0),
    }
    return GrowboxConfig(values=data)


def profile_apply_flat(profile: GrowboxProfile, flat: GrowboxConfig) -> GrowboxProfile:
    n = max(0, min(4, int(round(flat.get("active_pots")))))
    pot_vol = float(flat.get("pot_volume_l"))
    water = float(flat.get("substrate_water_capacity_ml"))
    transp = float(flat.get("transpiration_factor"))
    irr_flow = float(flat.get("irrigation_flow_ml_s"))
    irr_pulse = float(flat.get("irrigation_maximum_pulse_s"))
    irr_int = float(flat.get("irrigation_minimum_interval_s"))
    mat_w = float(flat.get("heat_mat_max_power_w"))
    tgt_m = float(flat.get("target_soil_moisture_pct"))
    tgt_t = float(flat.get("target_soil_temperature_c"))

    new_pots: list[PotProfile] = []
    for index in range(4):
        prev = profile.pots[index] if index < len(profile.pots) else PotProfile()
        if index < n:
            base = (
                prev
                if prev.available
                else PotProfile(
                    available=True,
                    soil_moisture_valid=True,
                    soil_temperature_valid=True,
                    irrigation_available=True,
                )
            )
            new_pots.append(
                replace(
                    base,
                    available=True,
                    pot_volume_l=pot_vol,
                    substrate_water_capacity_ml=water,
                    transpiration_factor=transp,
                    irrigation_flow_ml_s=irr_flow,
                    irrigation_maximum_pulse_s=irr_pulse,
                    irrigation_minimum_interval_s=irr_int,
                    heat_mat_max_power_w=mat_w,
                    target_soil_moisture_pct=tgt_m,
                    target_soil_temperature_c=tgt_t,
                    # preserve per-pot toggles from outputs / sensors
                    irrigation_available=base.irrigation_available if prev.available else True,
                    heat_mat_available=base.heat_mat_available if prev.available else False,
                    soil_moisture_valid=base.soil_moisture_valid if prev.available else True,
                    soil_temperature_valid=base.soil_temperature_valid if prev.available else True,
                )
            )
        else:
            # Keep per-pot scalar memory but force unavailable (prefix model)
            new_pots.append(PotProfile())

    chamber = replace(
        profile.chamber,
        growbox_volume_m3=float(flat.get("growbox_volume_m3")),
        thermal_mass_j_per_k=float(flat.get("thermal_mass_j_per_k")),
        heat_loss_w_per_k=float(flat.get("heat_loss_w_per_k")),
        air_leak_rate_ach=float(flat.get("air_leak_rate_ach")),
    )

    def slot(name: str, **kwargs: float | None) -> ActuatorSlotProfile:
        prev = profile.actuators.get(name, ActuatorSlotProfile())
        return replace(prev, **kwargs)

    acts = dict(profile.actuators)
    acts["heater"] = slot(
        "heater",
        max_power_w=float(flat.get("heater_max_power_w")),
        efficiency=float(flat.get("heater_efficiency")),
    )
    acts["fan"] = slot(
        "fan",
        max_airflow_m3_h=float(flat.get("fan_max_airflow_m3_h")),
        minimum_command=float(flat.get("fan_minimum_command")),
    )
    acts["humidifier"] = slot(
        "humidifier", max_output_g_h=float(flat.get("humidifier_max_output_g_h"))
    )
    acts["dehumidifier"] = slot(
        "dehumidifier", max_removal_g_h=float(flat.get("dehumidifier_max_removal_g_h"))
    )
    acts["cooler"] = slot("cooler", max_cooling_w=float(flat.get("cooler_max_cooling_w")))
    acts["co2_doser"] = slot(
        "co2_doser",
        dose_ppm_per_full_pulse=float(flat.get("co2_dose_ppm")),
        maximum_pulse_s=float(flat.get("co2_maximum_pulse_s")),
    )
    acts["nutrient_heater"] = slot(
        "nutrient_heater",
        max_power_w=float(flat.get("nutrient_heater_max_power_w")),
        efficiency=float(flat.get("nutrient_heater_efficiency")),
    )
    acts["lights"] = slot("lights", max_power_w=float(flat.get("lights_max_heat_w")))

    return replace(profile, chamber=chamber, pots=new_pots, actuators=acts)


@dataclass
class ConfigEditor:
    active: bool = False
    level: Level = "root"
    section: str = "chamber"
    menu_cursor: int = 0
    cursor: int = 0
    profile: GrowboxProfile | None = None
    values: GrowboxConfig | None = None

    def ensure_profile(self, sim: SequentialEnvironmentSimulator) -> GrowboxProfile:
        if self.profile is None:
            self.profile = profile_from_simulator(sim)
        if self.values is None:
            self.values = flat_from_profile(self.profile)
        return self.profile

    def sync_from_simulator(self, sim: SequentialEnvironmentSimulator) -> GrowboxProfile:
        self.profile = profile_from_simulator(sim)
        self.values = flat_from_profile(self.profile)
        return self.profile

    def ensure_values(self, sim: SequentialEnvironmentSimulator) -> GrowboxConfig:
        self.ensure_profile(sim)
        if self.values is None:
            self.values = flat_from_profile(self.profile)
        return self.values

    def open_root(self, sim: SequentialEnvironmentSimulator) -> None:
        self.active = True
        self.level = "root"
        self.menu_cursor = 0
        self.sync_from_simulator(sim)

    def close(self) -> None:
        self.active = False
        self.level = "root"

    def enter_section(self) -> None:
        if not self.active or self.level != "root":
            return
        sid, _ = MENU_SECTIONS[self.menu_cursor % len(MENU_SECTIONS)]
        self.section = sid
        self.level = "section"
        self.cursor = 0

    def back(self) -> bool:
        if not self.active:
            return False
        if self.level == "section":
            self.level = "root"
            self.cursor = 0
            return False
        self.close()
        return True

    def rows(self) -> tuple[Row, ...]:
        return SECTION_ROWS.get(self.section, ())

    def fields(self) -> tuple[ConfigField, ...]:
        return SECTION_FIELDS.get(self.section, ())

    def flags(self) -> tuple[FlagField, ...]:
        return SECTION_FLAGS.get(self.section, ())

    def is_flag_section(self) -> bool:
        """True if section is mostly flags (sensors) — used by HUD help text."""
        return self.section == "sensors"

    def row_at_cursor(self) -> Row | None:
        rows = self.rows()
        if not rows:
            return None
        return rows[max(0, min(self.cursor, len(rows) - 1))]

    def is_flag_at_cursor(self) -> bool:
        row = self.row_at_cursor()
        return row is not None and row.kind == "flag"


def read_growbox_config(sim: SequentialEnvironmentSimulator) -> GrowboxConfig:
    return flat_from_profile(profile_from_simulator(sim))


def _clamp_row(row: Row, value: float) -> float:
    v = min(row.max_value, max(row.min_value, float(value)))
    if row.decimals == 0:
        return float(int(round(v)))
    return round(v, row.decimals)


def _rows_by_key() -> dict[str, Row]:
    out: dict[str, Row] = {}
    for rows in SECTION_ROWS.values():
        for r in rows:
            if r.kind == "num":
                out[r.key] = r
    return out


def format_field_value(field: ConfigField | Row, raw: float) -> str:
    if isinstance(field, Row):
        scale, decimals, suffix = field.display_scale, field.decimals, field.display_suffix
    else:
        scale, decimals, suffix = field.display_scale, field.decimals, field.display_suffix
    shown = float(raw) * scale
    body = f"{shown:.0f}" if decimals == 0 else f"{shown:.{decimals}f}"
    return f"{body}{suffix}"


def _box(title: str, rows: list[tuple[str, str]]) -> str:
    label_w = max((len(k) for k, _ in rows), default=1)
    value_w = max((len(v) for _, v in rows), default=1)
    inner = max(label_w + value_w + 3, len(title))
    top = "┌" + "─" * (inner + 2) + "┐"
    mid = "├" + "─" * (inner + 2) + "┤"
    bot = "└" + "─" * (inner + 2) + "┘"
    lines = [top, f"│ {title.ljust(inner)} │", mid]
    for key, value in rows:
        lines.append(f"│ {key.ljust(label_w)} : {value.rjust(value_w)} │")
    lines.append(bot)
    return "\n".join(lines)


def root_menu_table(menu_cursor: int) -> str:
    rows = [
        (f"{'>' if i == menu_cursor % len(MENU_SECTIONS) else ' '}{label}", "enter")
        for i, (_sid, label) in enumerate(MENU_SECTIONS)
    ]
    return _box("configurator", rows)


def _flag_on_off(on: bool) -> str:
    return "ON" if on else "off"


def read_sensor_flag(profile: GrowboxProfile, key: str) -> bool:
    s = profile.sensors
    if key in s.as_dict():
        return bool(getattr(s, key))
    if key.startswith("pot") and "_soil_" in key:
        pot_i = int(key[3]) - 1
        if not (0 <= pot_i < len(profile.pots)):
            return False
        pot = profile.pots[pot_i]
        if not pot.available:
            return False
        if key.endswith("moisture"):
            return bool(pot.soil_moisture_valid)
        if key.endswith("temperature"):
            return bool(pot.soil_temperature_valid)
    return False


def write_sensor_flag(profile: GrowboxProfile, key: str, value: bool) -> GrowboxProfile:
    s = profile.sensors
    if key in s.as_dict():
        return replace(profile, sensors=replace(s, **{key: bool(value)}))
    if key.startswith("pot") and "_soil_" in key:
        pot_i = int(key[3]) - 1
        pots = list(profile.pots)
        while len(pots) < 4:
            pots.append(PotProfile())
        pot = pots[pot_i]
        # Inactive pot: do not store ghost validity (read would always show off).
        if not pot.available:
            return profile
        if key.endswith("moisture"):
            pots[pot_i] = replace(pot, soil_moisture_valid=bool(value))
        elif key.endswith("temperature"):
            pots[pot_i] = replace(pot, soil_temperature_valid=bool(value))
        return replace(profile, pots=pots)
    return profile


def read_output_flag(profile: GrowboxProfile, key: str) -> bool:
    if key == "lights_heat":
        slot = profile.actuators.get("lights", ActuatorSlotProfile(available=True))
        return bool(slot.available)
    if key in profile.actuators:
        return bool(profile.actuators[key].available)
    if key.startswith("irrigation_pot_"):
        idx = int(key.rsplit("_", 1)[-1]) - 1
        if 0 <= idx < len(profile.pots):
            return bool(profile.pots[idx].irrigation_available and profile.pots[idx].available)
    if key.startswith("heat_mat_pot_"):
        idx = int(key.rsplit("_", 1)[-1]) - 1
        if 0 <= idx < len(profile.pots):
            return bool(profile.pots[idx].heat_mat_available and profile.pots[idx].available)
    return False


def _ensure_prefix_pots_available(pots: list[PotProfile], up_to_idx: int) -> list[PotProfile]:
    """Prefix model: enabling pot K implies pots 0..K are available."""
    out = list(pots)
    while len(out) < 4:
        out.append(PotProfile())
    for i in range(max(0, up_to_idx) + 1):
        pot = out[i]
        if not pot.available:
            out[i] = replace(
                pot,
                available=True,
                soil_moisture_valid=True,
                soil_temperature_valid=True,
                irrigation_available=True if i == up_to_idx else pot.irrigation_available,
            )
    return out


def write_output_flag(profile: GrowboxProfile, key: str, value: bool) -> GrowboxProfile:
    if key == "lights_heat":
        acts = dict(profile.actuators)
        prev = acts.get("lights", ActuatorSlotProfile(available=True, max_power_w=120.0))
        acts["lights"] = replace(prev, available=bool(value))
        return replace(profile, actuators=acts)
    if key in profile.actuators or key in (
        "heater",
        "fan",
        "humidifier",
        "dehumidifier",
        "cooler",
        "co2_doser",
        "nutrient_heater",
    ):
        acts = dict(profile.actuators)
        prev = acts.get(key, ActuatorSlotProfile())
        acts[key] = replace(prev, available=bool(value))
        return replace(profile, actuators=acts)
    if key.startswith("irrigation_pot_"):
        idx = int(key.rsplit("_", 1)[-1]) - 1
        pots = list(profile.pots)
        while len(pots) < 4:
            pots.append(PotProfile())
        if value:
            pots = _ensure_prefix_pots_available(pots, idx)
            pots[idx] = replace(pots[idx], irrigation_available=True)
        else:
            pots[idx] = replace(pots[idx], irrigation_available=False)
        return replace(profile, pots=pots)
    if key.startswith("heat_mat_pot_"):
        idx = int(key.rsplit("_", 1)[-1]) - 1
        pots = list(profile.pots)
        while len(pots) < 4:
            pots.append(PotProfile())
        if value:
            pots = _ensure_prefix_pots_available(pots, idx)
            pots[idx] = replace(pots[idx], heat_mat_available=True)
        else:
            pots[idx] = replace(pots[idx], heat_mat_available=False)
        return replace(profile, pots=pots)
    return profile


def config_table(
    cfg: GrowboxConfig,
    cursor: int,
    *,
    section: str = "chamber",
    profile: GrowboxProfile | None = None,
) -> str:
    label = SECTION_LABELS.get(section, section)
    title = f"config:{label}"
    rows_def = SECTION_ROWS.get(section, ())
    rows: list[tuple[str, str]] = []
    for i, row in enumerate(rows_def):
        mark = ">" if i == cursor else " "
        if row.kind == "flag":
            if profile is None:
                val = "off"
            elif section == "sensors":
                val = _flag_on_off(read_sensor_flag(profile, row.key))
            else:
                val = _flag_on_off(read_output_flag(profile, row.key))
            rows.append((f"{mark}{row.label}", val))
        else:
            try:
                raw = cfg.get(row.key)
            except KeyError:
                raw = 0.0
            rows.append((f"{mark}{row.label}", format_field_value(row, raw)))
    return _box(title, rows if rows else [("empty", "")])


def editor_panel(editor: ConfigEditor) -> str:
    if not editor.active:
        return ""
    if editor.level == "root":
        return root_menu_table(editor.menu_cursor)
    if editor.values is None or editor.profile is None:
        return root_menu_table(editor.menu_cursor)
    return config_table(
        editor.values, editor.cursor, section=editor.section, profile=editor.profile
    )


def bump_growbox_config(
    cfg: GrowboxConfig,
    field_index: int,
    *,
    direction: int,
    coarse: bool = False,
    section: str = "chamber",
) -> GrowboxConfig:
    rows = SECTION_ROWS.get(section, ())
    if not rows:
        return cfg
    idx = max(0, min(int(field_index), len(rows) - 1))
    row = rows[idx]
    if row.kind != "num":
        return cfg
    step = row.coarse_step if coarse else row.step
    try:
        cur = cfg.get(row.key)
    except KeyError:
        cur = row.min_value
    new_val = _clamp_row(row, cur + step * (1.0 if direction >= 0 else -1.0))
    out = cfg.with_value(row.key, new_val)
    if row.key == "pot_volume_l" and cur > 1e-9:
        ratio = new_val / cur
        cap_row = _rows_by_key().get("substrate_water_capacity_ml")
        if cap_row is not None:
            try:
                cap = cfg.get("substrate_water_capacity_ml")
            except KeyError:
                cap = 3000.0
            out = out.with_value("substrate_water_capacity_ml", _clamp_row(cap_row, cap * ratio))
    return out


def move_cursor(cursor: int, delta: int, *, n_items: int) -> int:
    if n_items <= 0:
        return 0
    return (int(cursor) + int(delta)) % n_items


def next_section(section: str, delta: int = 1) -> str:
    if section not in SECTION_ORDER:
        return SECTION_ORDER[0]
    idx = SECTION_ORDER.index(section)
    return SECTION_ORDER[(idx + int(delta)) % len(SECTION_ORDER)]


def apply_growbox_config(
    sim: SequentialEnvironmentSimulator,
    cfg: GrowboxConfig,
) -> set[str]:
    profile = profile_from_simulator(sim)
    # Clamp all known numeric rows
    by_key = _rows_by_key()
    data = dict(cfg.values)
    for key, row in by_key.items():
        if key in data:
            data[key] = _clamp_row(row, data[key])
    clamped = GrowboxConfig(values=data)
    new_profile = profile_apply_flat(profile, clamped)
    return apply_profile_to_simulator(sim, new_profile, preserve_state=True)


def _sync_flat_active_pots(editor: ConfigEditor) -> None:
    """Keep flat bag active_pots in sync after flag writes expand pots."""
    if editor.profile is None:
        return
    n = float(max(0, min(4, editor.profile.active_pot_count())))
    if editor.values is None:
        editor.values = flat_from_profile(editor.profile)
    else:
        editor.values = editor.values.with_value("active_pots", n)


def apply_editor_to_simulator(
    sim: SequentialEnvironmentSimulator,
    editor: ConfigEditor,
) -> set[str]:
    if editor.profile is None:
        return set()
    if editor.values is not None:
        # Flag toggles call _sync_flat_active_pots first so active_pots is not stale.
        # Numeric bumps of active_pots must be allowed to shrink (do not re-expand here).
        editor.profile = profile_apply_flat(editor.profile, editor.values)
    changed = apply_profile_to_simulator(sim, editor.profile, preserve_state=True)
    editor.values = flat_from_profile(editor.profile)
    return changed


def toggle_flag_at_cursor(editor: ConfigEditor) -> None:
    if editor.profile is None:
        return
    row = editor.row_at_cursor()
    if row is None or row.kind != "flag":
        return
    if editor.section == "sensors":
        cur = read_sensor_flag(editor.profile, row.key)
        editor.profile = write_sensor_flag(editor.profile, row.key, not cur)
    else:
        cur = read_output_flag(editor.profile, row.key)
        editor.profile = write_output_flag(editor.profile, row.key, not cur)
    _sync_flat_active_pots(editor)


__all__ = [
    "CHAMBER_FIELDS",
    "ConfigEditor",
    "ConfigField",
    "FlagField",
    "GEOMETRY_KEYS",
    "GROWBOX_FIELDS",
    "GrowboxConfig",
    "MENU_SECTIONS",
    "OUTPUT_FLAGS",
    "POTS_FIELDS",
    "Row",
    "SECTION_FIELDS",
    "SECTION_FLAGS",
    "SECTION_LABELS",
    "SECTION_ORDER",
    "SECTION_ROWS",
    "SENSOR_FLAGS",
    "apply_editor_to_simulator",
    "apply_growbox_config",
    "bump_growbox_config",
    "config_table",
    "editor_panel",
    "flat_from_profile",
    "format_field_value",
    "move_cursor",
    "needs_geometry_rebuild",
    "next_section",
    "read_growbox_config",
    "root_menu_table",
    "toggle_flag_at_cursor",
]
