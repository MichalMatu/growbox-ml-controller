"""Twin keyboard configurator — variant A main menu + sections.

Flow:
  RUNTIME  --p-->  ROOT menu (Chamber / Pots / Sensors / Outputs)
               Enter/=  -->  section fields
               Esc      -->  back one level (section→root, root→RUNTIME)
               p        -->  always exit to RUNTIME

Applies via ``tools.ml.profile.GrowboxProfile``.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
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

# Main menu entries (EN labels). Order is the configurator root.
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
    """Numeric editable row (chamber / pots)."""

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
    """Boolean toggle row (sensors / outputs)."""

    key: str
    label: str


CHAMBER_FIELDS: tuple[ConfigField, ...] = (
    ConfigField("growbox_volume_m3", "volume", 0.1, 0.5, 0.2, 5.0, 2, 1.0, " m3"),
    ConfigField(
        "thermal_mass_j_per_k",
        "thermal mass",
        1_000.0,
        5_000.0,
        5_000.0,
        120_000.0,
        0,
        0.001,
        " kJ/K",
    ),
    ConfigField("heat_loss_w_per_k", "heat loss", 0.5, 2.0, 1.0, 40.0, 1, 1.0, " W/K"),
    ConfigField("air_leak_rate_ach", "leak ACH", 0.05, 0.25, 0.0, 3.0, 2, 1.0, " /h"),
)

POTS_FIELDS: tuple[ConfigField, ...] = (
    ConfigField("active_pots", "active pots", 1.0, 1.0, 1.0, 4.0, 0, 1.0, ""),
    ConfigField("pot_volume_l", "pot volume", 1.0, 5.0, 1.0, 50.0, 1, 1.0, " L"),
    ConfigField(
        "substrate_water_capacity_ml",
        "pot water cap",
        100.0,
        500.0,
        200.0,
        15_000.0,
        0,
        1.0,
        " ml",
    ),
)

SENSOR_FLAGS: tuple[FlagField, ...] = (
    FlagField("air_temperature_c", "air T"),
    FlagField("air_humidity_pct", "air RH"),
    FlagField("co2_ppm", "CO2"),
    FlagField("outside_temperature_c", "out T"),
    FlagField("outside_humidity_pct", "out RH"),
    FlagField("outside_co2_ppm", "out CO2"),
    FlagField("nutrient_solution_temperature_c", "nutrient T"),
    FlagField("lights_active", "lights"),
    FlagField("pot1_soil_moisture", "P1 soil moist"),
    FlagField("pot1_soil_temperature", "P1 soil T"),
    FlagField("pot2_soil_moisture", "P2 soil moist"),
    FlagField("pot2_soil_temperature", "P2 soil T"),
    FlagField("pot3_soil_moisture", "P3 soil moist"),
    FlagField("pot3_soil_temperature", "P3 soil T"),
    FlagField("pot4_soil_moisture", "P4 soil moist"),
    FlagField("pot4_soil_temperature", "P4 soil T"),
)

OUTPUT_FLAGS: tuple[FlagField, ...] = (
    FlagField("heater", "heater"),
    FlagField("fan", "fan"),
    FlagField("humidifier", "humidifier"),
    FlagField("dehumidifier", "dehumidifier"),
    FlagField("cooler", "cooler"),
    FlagField("co2_doser", "CO2 doser"),
    FlagField("nutrient_heater", "nutrient heat"),
    FlagField("irrigation_pot_1", "irr pot 1"),
    FlagField("irrigation_pot_2", "irr pot 2"),
    FlagField("irrigation_pot_3", "irr pot 3"),
    FlagField("irrigation_pot_4", "irr pot 4"),
    FlagField("heat_mat_pot_1", "mat pot 1"),
    FlagField("heat_mat_pot_2", "mat pot 2"),
    FlagField("heat_mat_pot_3", "mat pot 3"),
    FlagField("heat_mat_pot_4", "mat pot 4"),
)

SECTION_FIELDS: dict[str, tuple[ConfigField, ...]] = {
    "chamber": CHAMBER_FIELDS,
    "pots": POTS_FIELDS,
}
SECTION_FLAGS: dict[str, tuple[FlagField, ...]] = {
    "sensors": SENSOR_FLAGS,
    "outputs": OUTPUT_FLAGS,
}

# Back-compat flat list
GROWBOX_FIELDS: tuple[ConfigField, ...] = CHAMBER_FIELDS + POTS_FIELDS


@dataclass
class GrowboxConfig:
    """Flat view of chamber + shared pot settings."""

    growbox_volume_m3: float = 0.8
    thermal_mass_j_per_k: float = 35_000.0
    heat_loss_w_per_k: float = 7.0
    air_leak_rate_ach: float = 0.25
    active_pots: int = 1
    pot_volume_l: float = 12.0
    substrate_water_capacity_ml: float = 3_000.0

    def as_dict(self) -> dict[str, float]:
        return {
            "growbox_volume_m3": float(self.growbox_volume_m3),
            "thermal_mass_j_per_k": float(self.thermal_mass_j_per_k),
            "heat_loss_w_per_k": float(self.heat_loss_w_per_k),
            "air_leak_rate_ach": float(self.air_leak_rate_ach),
            "active_pots": float(self.active_pots),
            "pot_volume_l": float(self.pot_volume_l),
            "substrate_water_capacity_ml": float(self.substrate_water_capacity_ml),
        }

    def get(self, key: str) -> float:
        return float(self.as_dict()[key])

    def with_value(self, key: str, value: float) -> GrowboxConfig:
        data = self.as_dict()
        if key not in data:
            raise KeyError(key)
        data[key] = float(value)
        return GrowboxConfig(
            growbox_volume_m3=data["growbox_volume_m3"],
            thermal_mass_j_per_k=data["thermal_mass_j_per_k"],
            heat_loss_w_per_k=data["heat_loss_w_per_k"],
            air_leak_rate_ach=data["air_leak_rate_ach"],
            active_pots=int(round(data["active_pots"])),
            pot_volume_l=data["pot_volume_l"],
            substrate_water_capacity_ml=data["substrate_water_capacity_ml"],
        )


@dataclass
class ConfigEditor:
    """Keyboard-driven configurator: root menu or section fields."""

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
        sid, _label = MENU_SECTIONS[self.menu_cursor % len(MENU_SECTIONS)]
        self.section = sid
        self.level = "section"
        self.cursor = 0

    def back(self) -> bool:
        """One level up. Returns True if fully closed (was root)."""
        if not self.active:
            return False
        if self.level == "section":
            self.level = "root"
            self.cursor = 0
            return False
        self.close()
        return True

    def fields(self) -> tuple[ConfigField, ...]:
        return SECTION_FIELDS.get(self.section, ())

    def flags(self) -> tuple[FlagField, ...]:
        return SECTION_FLAGS.get(self.section, ())

    def is_flag_section(self) -> bool:
        return self.section in SECTION_FLAGS


def flat_from_profile(profile: GrowboxProfile) -> GrowboxConfig:
    pot = profile.shared_pot_template()
    return GrowboxConfig(
        growbox_volume_m3=float(profile.chamber.growbox_volume_m3),
        thermal_mass_j_per_k=float(profile.chamber.thermal_mass_j_per_k),
        heat_loss_w_per_k=float(profile.chamber.heat_loss_w_per_k),
        air_leak_rate_ach=float(profile.chamber.air_leak_rate_ach),
        active_pots=max(1, profile.active_pot_count()),
        pot_volume_l=float(pot.pot_volume_l),
        substrate_water_capacity_ml=float(pot.substrate_water_capacity_ml),
    )


def profile_apply_flat(profile: GrowboxProfile, flat: GrowboxConfig) -> GrowboxProfile:
    n = max(1, min(4, int(round(flat.active_pots))))
    pot_vol = float(flat.pot_volume_l)
    water = float(flat.substrate_water_capacity_ml)
    new_pots: list[PotProfile] = []
    for index in range(4):
        prev = profile.pots[index] if index < len(profile.pots) else PotProfile()
        if index < n:
            if prev.available:
                new_pots.append(
                    replace(
                        prev,
                        available=True,
                        pot_volume_l=pot_vol,
                        substrate_water_capacity_ml=water,
                    )
                )
            else:
                new_pots.append(
                    PotProfile(
                        available=True,
                        pot_volume_l=pot_vol,
                        substrate_water_capacity_ml=water,
                        soil_moisture_valid=True,
                        soil_temperature_valid=True,
                        irrigation_available=True,
                    )
                )
        else:
            new_pots.append(PotProfile())
    chamber = replace(
        profile.chamber,
        growbox_volume_m3=float(flat.growbox_volume_m3),
        thermal_mass_j_per_k=float(flat.thermal_mass_j_per_k),
        heat_loss_w_per_k=float(flat.heat_loss_w_per_k),
        air_leak_rate_ach=float(flat.air_leak_rate_ach),
    )
    return replace(profile, chamber=chamber, pots=new_pots)


def read_growbox_config(sim: SequentialEnvironmentSimulator) -> GrowboxConfig:
    return flat_from_profile(profile_from_simulator(sim))


def _clamp_field(field: ConfigField, value: float) -> float:
    v = min(field.max_value, max(field.min_value, float(value)))
    if field.decimals == 0:
        return float(int(round(v)))
    return round(v, field.decimals)


def _fields_by_key() -> dict[str, ConfigField]:
    return {f.key: f for f in GROWBOX_FIELDS}


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
    rows: list[tuple[str, str]] = []
    for i, (_sid, label) in enumerate(MENU_SECTIONS):
        mark = ">" if i == menu_cursor % len(MENU_SECTIONS) else " "
        rows.append((f"{mark}{label}", "enter"))
    return _box("configurator", rows)


def format_field_value(field: ConfigField, raw: float) -> str:
    shown = float(raw) * field.display_scale
    if field.decimals == 0:
        body = f"{shown:.0f}"
    else:
        body = f"{shown:.{field.decimals}f}"
    return f"{body}{field.display_suffix}"


def _flag_on_off(on: bool) -> str:
    return "ON" if on else "off"


def read_sensor_flag(profile: GrowboxProfile, key: str) -> bool:
    s = profile.sensors
    if key in s.as_dict():
        return bool(getattr(s, key))
    if key.startswith("pot") and "_soil_" in key:
        # pot1_soil_moisture → index 0
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
        sensors = replace(s, **{key: bool(value)})
        return replace(profile, sensors=sensors)
    if key.startswith("pot") and "_soil_" in key:
        pot_i = int(key[3]) - 1
        pots = list(profile.pots)
        while len(pots) < 4:
            pots.append(PotProfile())
        pot = pots[pot_i]
        if key.endswith("moisture"):
            pots[pot_i] = replace(pot, soil_moisture_valid=bool(value))
        elif key.endswith("temperature"):
            pots[pot_i] = replace(pot, soil_temperature_valid=bool(value))
        return replace(profile, pots=pots)
    return profile


def read_output_flag(profile: GrowboxProfile, key: str) -> bool:
    if key in profile.actuators:
        return bool(profile.actuators[key].available)
    if key.startswith("irrigation_pot_"):
        idx = int(key.rsplit("_", 1)[-1]) - 1
        if 0 <= idx < len(profile.pots):
            return bool(profile.pots[idx].irrigation_available and profile.pots[idx].available)
        return False
    if key.startswith("heat_mat_pot_"):
        idx = int(key.rsplit("_", 1)[-1]) - 1
        if 0 <= idx < len(profile.pots):
            return bool(profile.pots[idx].heat_mat_available and profile.pots[idx].available)
        return False
    return False


def write_output_flag(profile: GrowboxProfile, key: str, value: bool) -> GrowboxProfile:
    if key in profile.actuators:
        acts = dict(profile.actuators)
        prev = acts.get(key, ActuatorSlotProfile())
        acts[key] = replace(prev, available=bool(value))
        return replace(profile, actuators=acts)
    if key.startswith("irrigation_pot_"):
        idx = int(key.rsplit("_", 1)[-1]) - 1
        pots = list(profile.pots)
        while len(pots) < 4:
            pots.append(PotProfile())
        pot = pots[idx]
        if value and not pot.available:
            pot = replace(pot, available=True, soil_moisture_valid=True)
        pots[idx] = replace(pot, irrigation_available=bool(value))
        return replace(profile, pots=pots)
    if key.startswith("heat_mat_pot_"):
        idx = int(key.rsplit("_", 1)[-1]) - 1
        pots = list(profile.pots)
        while len(pots) < 4:
            pots.append(PotProfile())
        pot = pots[idx]
        if value and not pot.available:
            pot = replace(pot, available=True)
        pots[idx] = replace(pot, heat_mat_available=bool(value))
        return replace(profile, pots=pots)
    return profile


def config_table(
    cfg: GrowboxConfig,
    cursor: int,
    *,
    section: str = "chamber",
    profile: GrowboxProfile | None = None,
) -> str:
    """Section field table (numeric or flags)."""
    label = SECTION_LABELS.get(section, section)
    title = f"config:{label}"
    if section in SECTION_FIELDS:
        fields = SECTION_FIELDS[section]
        rows = [
            (
                f"{'>' if i == cursor else ' '}{f.label}",
                format_field_value(f, cfg.get(f.key)),
            )
            for i, f in enumerate(fields)
        ]
        return _box(title, rows)
    if section in SECTION_FLAGS and profile is not None:
        flags = SECTION_FLAGS[section]
        rows = []
        for i, f in enumerate(flags):
            mark = ">" if i == cursor else " "
            if section == "sensors":
                on = read_sensor_flag(profile, f.key)
            else:
                on = read_output_flag(profile, f.key)
            rows.append((f"{mark}{f.label}", _flag_on_off(on)))
        return _box(title, rows)
    return _box(title, [("empty", "")])


def editor_panel(editor: ConfigEditor) -> str:
    """HUD panel for current configurator level."""
    if not editor.active:
        return ""
    if editor.level == "root":
        return root_menu_table(editor.menu_cursor)
    if editor.values is None or editor.profile is None:
        return root_menu_table(editor.menu_cursor)
    return config_table(
        editor.values,
        editor.cursor,
        section=editor.section,
        profile=editor.profile,
    )


def bump_growbox_config(
    cfg: GrowboxConfig,
    field_index: int,
    *,
    direction: int,
    coarse: bool = False,
    section: str = "chamber",
) -> GrowboxConfig:
    fields = SECTION_FIELDS.get(section, ())
    if not fields:
        return cfg
    idx = max(0, min(int(field_index), len(fields) - 1))
    field = fields[idx]
    step = field.coarse_step if coarse else field.step
    delta = step * (1.0 if direction >= 0 else -1.0)
    new_val = _clamp_field(field, cfg.get(field.key) + delta)
    out = cfg.with_value(field.key, new_val)
    if field.key == "pot_volume_l" and cfg.pot_volume_l > 1e-9:
        ratio = out.pot_volume_l / cfg.pot_volume_l
        cap_field = _fields_by_key()["substrate_water_capacity_ml"]
        scaled = _clamp_field(cap_field, cfg.substrate_water_capacity_ml * ratio)
        out = out.with_value("substrate_water_capacity_ml", scaled)
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
    by_key = _fields_by_key()
    clamped = GrowboxConfig(
        growbox_volume_m3=_clamp_field(by_key["growbox_volume_m3"], cfg.growbox_volume_m3),
        thermal_mass_j_per_k=_clamp_field(by_key["thermal_mass_j_per_k"], cfg.thermal_mass_j_per_k),
        heat_loss_w_per_k=_clamp_field(by_key["heat_loss_w_per_k"], cfg.heat_loss_w_per_k),
        air_leak_rate_ach=_clamp_field(by_key["air_leak_rate_ach"], cfg.air_leak_rate_ach),
        active_pots=int(_clamp_field(by_key["active_pots"], float(cfg.active_pots))),
        pot_volume_l=_clamp_field(by_key["pot_volume_l"], cfg.pot_volume_l),
        substrate_water_capacity_ml=_clamp_field(
            by_key["substrate_water_capacity_ml"], cfg.substrate_water_capacity_ml
        ),
    )
    new_profile = profile_apply_flat(profile, clamped)
    return apply_profile_to_simulator(sim, new_profile, preserve_state=True)


def apply_editor_to_simulator(
    sim: SequentialEnvironmentSimulator,
    editor: ConfigEditor,
) -> set[str]:
    if editor.profile is None:
        return set()
    if editor.values is not None and editor.section in SECTION_FIELDS:
        editor.profile = profile_apply_flat(editor.profile, editor.values)
    changed = apply_profile_to_simulator(sim, editor.profile, preserve_state=True)
    editor.values = flat_from_profile(editor.profile)
    return changed


def toggle_flag_at_cursor(editor: ConfigEditor) -> None:
    """Flip sensors/outputs flag under cursor; mutates editor.profile."""
    if editor.profile is None or not editor.is_flag_section():
        return
    flags = editor.flags()
    if not flags:
        return
    idx = max(0, min(editor.cursor, len(flags) - 1))
    key = flags[idx].key
    if editor.section == "sensors":
        cur = read_sensor_flag(editor.profile, key)
        editor.profile = write_sensor_flag(editor.profile, key, not cur)
    else:
        cur = read_output_flag(editor.profile, key)
        editor.profile = write_output_flag(editor.profile, key, not cur)


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
    "SECTION_FIELDS",
    "SECTION_FLAGS",
    "SECTION_LABELS",
    "SECTION_ORDER",
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
