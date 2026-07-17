"""HUD text tables for the scientific twin view (no PyVista import)."""

from __future__ import annotations

from typing import Any

from .config import ConfigEditor, editor_panel
from .scene import TwinSnapshot

FONT_FAMILY = "courier"
FONT_SIZE = 12
FONT_COLOR = "white"

# Section rows: (label, value). Empty label + value used as blank spacer is avoided;
# section headers are drawn on the mid rule line.


def hud_table(title: str, rows: list[tuple[str, str]]) -> str:
    """Single-section fixed-width box (legacy / simple panels)."""
    return hud_sections(title, [("", rows)])


def hud_sections(title: str, sections: list[tuple[str, list[tuple[str, str]]]]) -> str:
    """One box with titled mid-rules between logical groups.

    ``sections``: list of (section_title, rows). Empty section_title = no mid header
    (only used for the first block under the main title).
    """
    all_rows: list[tuple[str, str]] = []
    for _sec, rows in sections:
        all_rows.extend(rows)
    if not all_rows:
        all_rows = [("", "")]
    label_w = max((len(k) for k, _ in all_rows), default=1)
    value_w = max((len(v) for _, v in all_rows), default=1)
    # Section titles need room on the separator line
    sec_w = max((len(s) for s, _ in sections if s), default=0)
    inner = max(label_w + value_w + 3, len(title), sec_w)
    top = "┌" + "─" * (inner + 2) + "┐"
    bot = "└" + "─" * (inner + 2) + "┘"
    lines = [top, f"│ {title.ljust(inner)} │"]
    for sec_title, rows in sections:
        if sec_title:
            # ├ section ──────┤
            pad = max(0, inner - len(sec_title) - 1)
            mid = "├ " + sec_title + " " + "─" * pad + "┤"
            if len(mid) < len(top):
                mid = "├" + "─" * (inner + 2) + "┤"
                # rebuild with title embedded
                body = f" {sec_title} "
                dash = max(0, (inner + 2) - len(body))
                left = dash // 2
                right = dash - left
                mid = "├" + "─" * left + body + "─" * right + "┤"
            lines.append(mid)
        else:
            lines.append("├" + "─" * (inner + 2) + "┤")
        for key, value in rows:
            lines.append(f"│ {key.ljust(label_w)} : {value.ljust(value_w)} │")
    lines.append(bot)
    return "\n".join(lines)


def runtime_controls_table(*, playing: bool = False) -> str:
    """Lower-left: keys only, grouped by role (not mixed with live values)."""
    return hud_sections(
        "keys · control",
        [
            (
                "playback",
                [
                    ("mode", "PLAY" if playing else "PAUSE"),
                    ("space", "play / pause"),
                    ("s", "step +10 s"),
                    ("r", "reset + stop"),
                ],
            ),
            (
                "actuators",
                [
                    ("1 / 2", "heater on / off"),
                    ("3 / 4", "fan on / off"),
                    ("5 / 6", "humid on / off"),
                    ("h / H", "heater ±0.25"),
                    ("f / F", "fan ±0.25"),
                    ("u / U", "humid ±0.25"),
                ],
            ),
            (
                "menu",
                [
                    ("p", "open configurator"),
                ],
            ),
        ],
    )


def config_root_keys_table() -> str:
    return hud_sections(
        "keys · config",
        [
            (
                "menu",
                [
                    ("j / k", "select section"),
                    ("Enter / =", "open section"),
                    ("p / Esc", "exit to runtime"),
                ],
            ),
        ],
    )


def config_section_keys_table(*, flags: bool) -> str:
    _ = flags
    return hud_sections(
        "keys · config",
        [
            (
                "edit",
                [
                    ("j / k", "next / prev field"),
                    ("- / =", "value or toggle"),
                    ("[ / ]", "coarse step"),
                    ("sp/Enter", "toggle flag"),
                ],
            ),
            (
                "nav",
                [
                    ("Esc", "back to menu"),
                    ("p", "exit to runtime"),
                ],
            ),
        ],
    )


def view_controls_table() -> str:
    """Lower-right: camera / view only (no actuator keys)."""
    return hud_sections(
        "keys · view",
        [
            (
                "camera",
                [
                    ("7 / c", "HOME"),
                    ("8", "TOP"),
                    ("9", "FRONT"),
                    ("0", "SIDE"),
                    ("i", "ISO"),
                    ("mouse", "orbit / pan / zoom"),
                ],
            ),
            (
                "display",
                [
                    ("m", "force mono"),
                ],
            ),
        ],
    )


def _set_corner_text(pl: Any, name: str, position: str, text: str) -> None:
    """Update corner annotation in place — avoid remove/add flicker each step."""
    actor = None
    try:
        actors = getattr(pl, "actors", None) or {}
        actor = actors.get(name)
    except Exception:
        actor = None
    if actor is not None and hasattr(actor, "set_text"):
        try:
            actor.set_text(position, text)
            return
        except Exception:
            pass
    try:
        from .plotter import safe_remove

        safe_remove(pl, name)
    except Exception:
        pass
    pl.add_text(
        text,
        position=position,
        font_size=FONT_SIZE,
        color=FONT_COLOR,
        font=FONT_FAMILY,
        name=name,
        render=False,
    )


def params_status_rows(
    *,
    playing: bool,
    steps: int,
    max_steps: int,
) -> list[tuple[str, str]]:
    """Legacy helper (tests); prefer live_state_panel."""
    return [
        ("run", "PLAY" if playing else "PAUSE"),
        ("steps", f"{int(steps)}/{int(max_steps)}"),
    ]


def live_state_panel(
    snap: TwinSnapshot,
    *,
    playing: bool,
    steps: int,
    max_steps: int,
) -> str:
    """Upper-left live readout: simulation / commands / chamber / outside / pots."""
    sim_rows = [
        ("run", "PLAY" if playing else "PAUSE"),
        ("step", f"{int(steps)}/{int(max_steps)}"),
        ("t", f"{snap.elapsed_s:.0f} s"),
    ]
    cmd_rows = [
        ("heater", f"{snap.action.heater:.2f}"),
        ("fan", f"{snap.action.fan:.2f}"),
        ("humid", f"{snap.action.humidifier:.2f}"),
    ]
    chamber_rows = [
        ("T", f"{snap.air_temperature_c:.1f} °C"),
        ("RH", f"{snap.air_humidity_pct:.0f} %"),
        ("CO2", f"{snap.co2_ppm:.0f} ppm"),
        ("ACH", f"{snap.exchange.fan_ach_proxy:.1f} /h"),
    ]
    outside_rows = [
        ("T", f"{snap.outside_temperature_c:.1f} °C"),
        ("RH", f"{snap.outside_humidity_pct:.0f} %"),
        ("CO2", f"{snap.outside_co2_ppm:.0f} ppm"),
    ]
    pot_rows: list[tuple[str, str]] = []
    for index, active in enumerate(snap.pot_active):
        if not active:
            continue
        pot_rows.append((f"P{index + 1} θ", f"{snap.pot_moisture[index]:.0f} %"))
        pot_rows.append((f"P{index + 1} Ts", f"{snap.pot_temperature[index]:.1f} °C"))
    if not pot_rows:
        pot_rows = [("(none)", "—")]

    return hud_sections(
        "live state",
        [
            ("simulation", sim_rows),
            ("commands", cmd_rows),
            ("chamber", chamber_rows),
            ("outside", outside_rows),
            ("pots", pot_rows),
        ],
    )


def merge_params_panel(snap: TwinSnapshot, status_rows: list[tuple[str, str]]) -> str:
    """Build live state panel; ``status_rows`` may override run/steps (tests)."""
    playing = False
    steps = 0
    max_steps = 200
    for key, value in status_rows:
        if key == "run":
            playing = str(value).upper().startswith("PLAY")
        elif key in ("steps", "step") and "/" in str(value):
            left, _, right = str(value).partition("/")
            try:
                steps = int(left.strip())
                max_steps = int(right.strip())
            except ValueError:
                pass
    return live_state_panel(snap, playing=playing, steps=steps, max_steps=max_steps)


def set_hud(
    pl: Any,
    snap: TwinSnapshot,
    *,
    legend: bool,
    config_editor: ConfigEditor | None = None,
    playing: bool = False,
    steps: int = 0,
    max_steps: int = 200,
) -> None:
    """Upper-left: live state or configurator. Lower-left/right: key maps."""
    if config_editor is not None and config_editor.active:
        panel = editor_panel(config_editor)
    else:
        panel = live_state_panel(snap, playing=playing, steps=steps, max_steps=max_steps)
    _set_corner_text(pl, "params", "upper_left", panel)

    if not legend:
        return

    if config_editor is not None and config_editor.active:
        if config_editor.level == "root":
            left = config_root_keys_table()
        else:
            left = config_section_keys_table(flags=config_editor.is_flag_section())
    else:
        left = runtime_controls_table(playing=playing)

    _set_corner_text(pl, "runtime_keys", "lower_left", left)
    _set_corner_text(pl, "view_keys", "lower_right", view_controls_table())
