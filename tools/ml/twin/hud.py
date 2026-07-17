"""HUD text tables for the scientific twin view (no PyVista import)."""

from __future__ import annotations

from typing import Any

from .config import ConfigEditor, editor_panel
from .plotter import safe_remove
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


def runtime_controls_table() -> str:
    return hud_table(
        "runtime",
        [
            ("s / space", "step +10 s"),
            ("r", "reset"),
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
    if flags:
        return hud_table(
            "config keys",
            [
                ("j / k", "next / prev"),
                ("- / = / sp", "toggle ON/off"),
                ("Esc", "back to menu"),
                ("p", "exit config"),
            ],
        )
    return hud_table(
        "config keys",
        [
            ("j / k", "next / prev field"),
            ("- / =", "value - / +"),
            ("[ / ]", "coarse - / +"),
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


def set_hud(
    pl: Any,
    snap: TwinSnapshot,
    *,
    legend: bool,
    config_editor: ConfigEditor | None = None,
) -> None:
    """Parameters / configurator upper-left; keys lower-left / lower-right."""
    safe_remove(pl, "params")
    if config_editor is not None and config_editor.active:
        panel = editor_panel(config_editor)
    else:
        panel = snap.params_table()
    pl.add_text(
        panel,
        position="upper_left",
        font_size=FONT_SIZE,
        color=FONT_COLOR,
        font=FONT_FAMILY,
        name="params",
    )
    if legend:
        safe_remove(pl, "help")
        safe_remove(pl, "runtime_keys")
        safe_remove(pl, "view_keys")
        if config_editor is not None and config_editor.active:
            if config_editor.level == "root":
                left = config_root_keys_table()
            else:
                left = config_section_keys_table(flags=config_editor.is_flag_section())
        else:
            left = runtime_controls_table()
        pl.add_text(
            left,
            position="lower_left",
            font_size=FONT_SIZE,
            color=FONT_COLOR,
            font=FONT_FAMILY,
            name="runtime_keys",
        )
        pl.add_text(
            view_controls_table(),
            position="lower_right",
            font_size=FONT_SIZE,
            color=FONT_COLOR,
            font=FONT_FAMILY,
            name="view_keys",
        )
