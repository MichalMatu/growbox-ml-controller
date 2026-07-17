"""HUD text tables for the scientific twin view (no PyVista import)."""

from __future__ import annotations

from typing import Any

from .config import ConfigEditor, editor_panel
from .scene import TwinSnapshot

FONT_FAMILY = "courier"
FONT_SIZE = 12
FONT_COLOR = "white"


def hud_table(title: str, rows: list[tuple[str, str]]) -> str:
    """Fixed-width box table for HUD panels."""
    label_w = max(len(k) for k, _ in rows)
    value_w = max(len(v) for _, v in rows)
    inner = label_w + value_w + 3
    top = "┌" + "─" * (inner + 2) + "┐"
    mid = "├" + "─" * (inner + 2) + "┤"
    bot = "└" + "─" * (inner + 2) + "┘"
    lines = [top, f"│ {title.ljust(inner)} │", mid]
    for key, value in rows:
        lines.append(f"│ {key.ljust(label_w)} : {value.ljust(value_w)} │")
    lines.append(bot)
    return "\n".join(lines)


def runtime_controls_table(*, playing: bool = False) -> str:
    return hud_table(
        "runtime",
        [
            ("mode", "PLAY" if playing else "PAUSE"),
            ("space", "play / pause"),
            ("s", "step +10 s"),
            ("r", "reset + stop"),
            ("1 / 2", "heater on / off"),
            ("3 / 4", "fan on / off"),
            ("5 / 6", "humid on / off"),
            ("h / H", "heater ±0.25"),
            ("f / F", "fan ±0.25"),
            ("u / U", "humid ±0.25"),
            ("p", "configurator"),
            ("green", "INLET"),
            ("blue", "OUTLET"),
        ],
    )


def config_root_keys_table() -> str:
    return hud_table(
        "config menu",
        [
            ("j / k", "select section"),
            ("Enter / =", "open section"),
            ("p / Esc", "exit"),
        ],
    )


def config_section_keys_table(*, flags: bool) -> str:
    _ = flags
    return hud_table(
        "config keys",
        [
            ("j / k", "next / prev"),
            ("- / =", "value or toggle"),
            ("[ / ]", "coarse step"),
            ("sp/Enter", "toggle flag"),
            ("Esc", "back to menu"),
            ("p", "exit config"),
        ],
    )


def view_controls_table() -> str:
    return hud_table(
        "view",
        [
            ("7 / c", "HOME"),
            ("8", "TOP"),
            ("9", "FRONT"),
            ("0", "SIDE"),
            ("i", "ISO"),
            ("mouse", "orbit / pan / zoom"),
            ("m", "force mono"),
            ("p", "configurator"),
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
    # First create or non-CornerAnnotation fallback
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
    return [
        ("run", "PLAY" if playing else "PAUSE"),
        ("steps", f"{int(steps)}/{int(max_steps)}"),
    ]


def merge_params_panel(snap: TwinSnapshot, status_rows: list[tuple[str, str]]) -> str:
    """Parameters table with playback status rows prepended."""
    # Rebuild with status so column widths stay aligned
    base = snap.params_table()
    if not status_rows:
        return base
    # Parse is fragile; rebuild from snapshot fields + status
    rows: list[tuple[str, str]] = list(status_rows)
    rows.extend(
        [
            ("time", f"{snap.elapsed_s:.0f} s"),
            ("air T", f"{snap.air_temperature_c:.1f} °C"),
            ("air RH", f"{snap.air_humidity_pct:.0f} %"),
            ("CO2", f"{snap.co2_ppm:.0f} ppm"),
            ("out T", f"{snap.outside_temperature_c:.1f} °C"),
            ("out RH", f"{snap.outside_humidity_pct:.0f} %"),
            ("out CO2", f"{snap.outside_co2_ppm:.0f} ppm"),
            ("heater", f"{snap.action.heater:.2f}"),
            ("fan", f"{snap.action.fan:.2f}"),
            ("humid", f"{snap.action.humidifier:.2f}"),
            ("fan ACH", f"{snap.exchange.fan_ach_proxy:.1f} /h"),
        ]
    )
    for index, active in enumerate(snap.pot_active):
        if not active:
            continue
        rows.append((f"P{index + 1} soil", f"{snap.pot_moisture[index]:.0f} %"))
        rows.append((f"P{index + 1} soil T", f"{snap.pot_temperature[index]:.1f} °C"))
    return hud_table("parameters", rows)


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
    """Parameters / configurator upper-left; keys lower-left / lower-right.

    Text is updated in place when possible so soft steps do not flash HUD.
    """
    if config_editor is not None and config_editor.active:
        panel = editor_panel(config_editor)
    else:
        panel = merge_params_panel(
            snap,
            params_status_rows(playing=playing, steps=steps, max_steps=max_steps),
        )
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
