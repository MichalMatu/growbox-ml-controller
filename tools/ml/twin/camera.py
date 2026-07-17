"""Camera presets and trackball controls for the twin view."""

from __future__ import annotations

from typing import Any


def scene_focus(pl: Any) -> tuple[float, float, float, float]:
    """Return (cx, cy, cz, span) from plotter bounds."""
    b = pl.bounds
    cx = 0.5 * (float(b[0]) + float(b[1]))
    cy = 0.5 * (float(b[2]) + float(b[3]))
    cz = 0.5 * (float(b[4]) + float(b[5]))
    span = max(float(b[1]) - float(b[0]), float(b[3]) - float(b[2]), float(b[5]) - float(b[4]), 0.5)
    return cx, cy, cz, span


def set_standard_view(pl: Any, name: str) -> None:
    """CAD-style camera presets. HOME = default product angle.

    Always sets absolute camera_position (elevation/azimuth alone is easy to
    miss if the interactor already moved the camera).
    """
    cx, cy, cz, span = scene_focus(pl)
    if name == "home":
        # Product angle: step back a bit (less zoom), slightly lower framing
        # (old: 1.7/1.85/1.35 + focal below center → box too high and too tight)
        pl.camera_position = [
            (cx + 2.05 * span, cy - 2.2 * span, cz + 1.1 * span),
            (cx, cy, cz + 0.08 * span),
            (0.0, 0.0, 1.0),
        ]
    elif name == "iso":
        pl.camera_position = [
            (cx + 1.5 * span, cy - 1.5 * span, cz + 1.5 * span),
            (cx, cy, cz),
            (0.0, 0.0, 1.0),
        ]
    elif name == "top":
        pl.camera_position = [
            (cx, cy, cz + 2.4 * span),
            (cx, cy, cz),
            (0.0, 1.0, 0.0),
        ]
    elif name == "front":
        pl.camera_position = [
            (cx, cy - 2.4 * span, cz),
            (cx, cy, cz),
            (0.0, 0.0, 1.0),
        ]
    elif name == "side":
        pl.camera_position = [
            (cx + 2.4 * span, cy, cz),
            (cx, cy, cz),
            (0.0, 0.0, 1.0),
        ]
    else:
        set_standard_view(pl, "home")
        return
    try:
        pl.reset_camera_clipping_range()
    except Exception:
        pass
    pl.render()


def bind_camera_keys(pl: Any) -> None:
    """HOME / view presets. Bind several KeySym aliases (macOS / numpad)."""

    def home() -> None:
        set_standard_view(pl, "home")

    def iso() -> None:
        set_standard_view(pl, "iso")

    def top() -> None:
        set_standard_view(pl, "top")

    def front() -> None:
        set_standard_view(pl, "front")

    def side() -> None:
        set_standard_view(pl, "side")

    for key in ("7", "KP_7", "c", "C"):
        pl.add_key_event(key, home)
    for key in ("i", "I"):
        pl.add_key_event(key, iso)
    for key in ("8", "KP_8"):
        pl.add_key_event(key, top)
    for key in ("9", "KP_9"):
        pl.add_key_event(key, front)
    for key in ("0", "KP_0"):
        pl.add_key_event(key, side)


def attach_camera_controls(pl: Any, window_size: tuple[int, int] = (1200, 860)) -> None:
    """Mouse trackball + keyboard camera presets (no orientation gizmo)."""
    _ = window_size
    try:
        pl.enable_trackball_style()
    except Exception:
        pass
    bind_camera_keys(pl)
