"""Scientific 3D twin view for the lumped growbox simulator (PyVista).

Minimal stable scene:
  - single white wireframe chamber outline (no fill, no T/RH color map)
  - fixed-color pot + inlet/outlet rings
  - at most two fixed-color fan arrows (visibility toggle only)
  - HUD tables for numbers (temperature lives only in the table)
  - mouse trackball rotate/zoom + keyboard camera presets (7/c HOME, 8/9/0/i)

No temperature/humidity geometric overlays. No solid chamber wash.
No orientation gizmo (VTK camera orientation widget removed — poor UX).
"""

from __future__ import annotations

import argparse
import struct
import tempfile
import zlib
from pathlib import Path
from typing import Any

from .simulator import (
    ControlAction,
    SequentialEnvironmentSimulator,
    default_scenario_v2,
)
from .twin_scene import (
    TwinSnapshot,
    pot_layout_positions,
    pot_radius_height,
    snapshot_from_simulator,
    vent_port_centers,
)

# Single font for all twin text (HUD + 3D labels) — no size/style mix
_FONT_FAMILY = "courier"
_FONT_SIZE = 12
_FONT_COLOR = "white"
# Radial studio BG: darker center → slightly brighter edges (subtle, not washed out)
_BG_CENTER = (0x1C, 0x20, 0x2A)  # cool dark hub
_BG_EDGE = (0x32, 0x38, 0x46)  # soft rim — only a mild lift vs center
# Wide enough for 16:9 / typical twin window (avoids black letterbox bars)
_BG_RADIAL_W = 1280
_BG_RADIAL_H = 800
_BG_RADIAL_VERSION = 3  # bump to regenerate cached PNG
_WIRE = "#e8e8e8"
_POT = "#6b5b4b"
_INLET = "#5cb85c"
_OUTLET = "#5b9bd5"
_ARROW = "#c8e6f5"


def _hud_table(title: str, rows: list[tuple[str, str]]) -> str:
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


def _runtime_controls_table() -> str:
    """Simulation / actuator keys (lower-left)."""
    return _hud_table(
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
            ("green", "INLET"),
            ("blue", "OUTLET"),
        ],
    )


def _view_controls_table() -> str:
    """Camera / view keys only (lower-right)."""
    return _hud_table(
        "view",
        [
            ("7 / c", "HOME"),
            ("8", "TOP"),
            ("9", "FRONT"),
            ("0", "SIDE"),
            ("i", "ISO"),
            ("mouse", "orbit / pan / zoom"),
            ("m", "force mono"),
        ],
    )


def _require_pyvista() -> Any:
    try:
        import pyvista as pv
    except ImportError as exc:  # pragma: no cover
        raise SystemExit(f"PyVista required: pip install pyvista\nOriginal error: {exc}") from exc
    return pv


def _safe_remove(pl: Any, name: str) -> None:
    try:
        pl.remove_actor(name)
    except Exception:
        pass


def _clip01(value: float) -> float:
    return min(1.0, max(0.0, float(value)))


def _clean(mesh: Any) -> Any:
    """Strip all point/cell arrays so VTK never applies a colormap (purple wash)."""
    out = mesh.copy(deep=True)
    try:
        out.clear_data()
    except Exception:
        pass
    try:
        out.set_active_scalars(None)
    except Exception:
        pass
    return out


def _add_solid(
    pl: Any,
    mesh: Any,
    *,
    color: str,
    name: str,
    style: str = "surface",
    line_width: float = 1.0,
    lighting: bool = False,
) -> Any:
    """Add mesh with forced flat RGB — never scalars, never edges-as-second-outline."""
    actor = pl.add_mesh(
        _clean(mesh),
        style=style,
        color=color,
        line_width=line_width,
        name=name,
        lighting=lighting,
        smooth_shading=False,
        show_edges=False,
        show_scalar_bar=False,
        ambient=1.0 if not lighting else 0.45,
        diffuse=0.0 if not lighting else 0.55,
        specular=0.0,
        render_lines_as_tubes=False,
    )
    try:
        mapper = actor.GetMapper() if hasattr(actor, "GetMapper") else actor.mapper
        if mapper is not None:
            mapper.ScalarVisibilityOff()
    except Exception:
        pass
    try:
        prop = actor.GetProperty() if hasattr(actor, "GetProperty") else actor.prop
        if prop is not None and hasattr(prop, "EdgeVisibilityOff"):
            prop.EdgeVisibilityOff()
    except Exception:
        pass
    return actor


def build_static_meshes(pv: Any, snap: TwinSnapshot) -> dict[str, Any]:
    """Geometry independent of fan command — no T/RH coloring."""
    sx, sy, sz = snap.box.size_xyz
    # Outline only (line cells). Cube surface + FaceIndex caused multi-color edges.
    solid = pv.Box(bounds=(-0.5 * sx, 0.5 * sx, -0.5 * sy, 0.5 * sy, 0.0, sz))
    chamber = solid.outline()

    pots: list[Any] = []
    pot_labels: list[tuple[tuple[float, float, float], str]] = []
    radius, height = pot_radius_height(snap.box)
    for index, cx, cy, cz in pot_layout_positions(snap.box, snap.pot_active):
        pots.append(
            pv.Cylinder(
                center=(cx, cy, cz + 0.5 * height),
                direction=(0.0, 0.0, 1.0),
                radius=radius,
                height=height,
                resolution=24,
            )
        )
        pot_labels.append(
            ((cx, cy, cz + height + 0.05 * sz), f"P{index + 1} θ={snap.pot_moisture[index]:.0f}%")
        )

    inlet_c, outlet_c = vent_port_centers(snap.box)
    port_r = 0.14 * min(sx, sy)
    inlet = pv.Disc(
        center=inlet_c,
        inner=0.4 * port_r,
        outer=port_r,
        normal=(-1.0, 0.0, 0.0),
        r_res=16,
        c_res=16,
    )
    outlet = pv.Disc(
        center=outlet_c,
        inner=0.4 * port_r,
        outer=port_r,
        normal=(1.0, 0.0, 0.0),
        r_res=16,
        c_res=16,
    )
    port_labels = [
        ((inlet_c[0] - 0.06 * sx, inlet_c[1], inlet_c[2] + 0.14 * sz), "INLET"),
        ((outlet_c[0] + 0.06 * sx, outlet_c[1], outlet_c[2] + 0.14 * sz), "OUTLET"),
    ]
    return {
        "chamber": chamber,
        "pots": pots,
        "pot_labels": pot_labels,
        "inlet": inlet,
        "outlet": outlet,
        "port_labels": port_labels,
        "box_len": sx,
        "inlet_c": inlet_c,
        "outlet_c": outlet_c,
    }


def build_arrow_meshes(pv: Any, snap: TwinSnapshot, box_len: float) -> list[Any]:
    """At most two small arrows (inlet + outlet centers) when fan is on."""
    if snap.exchange.points.shape[0] < 2 or snap.action.fan <= 0.02:
        return []
    length = max(0.04, 0.08 * box_len)
    arrows: list[Any] = []
    for origin in snap.exchange.points[:2]:
        arrows.append(
            pv.Arrow(
                start=tuple(float(v) for v in origin),
                direction=(1.0, 0.0, 0.0),
                tip_length=0.35,
                tip_radius=0.1,
                tip_resolution=12,
                shaft_radius=0.04,
                shaft_resolution=12,
                scale=length,
            )
        )
    return arrows


def _add_static_scene(pl: Any, meshes: dict[str, Any]) -> None:
    """Wireframe outline chamber only — no solid fill, no scalar maps."""
    _add_solid(
        pl,
        meshes["chamber"],
        color=_WIRE,
        name="chamber",
        style="wireframe",
        line_width=2.0,
        lighting=False,
    )
    for i, pot in enumerate(meshes["pots"]):
        _add_solid(pl, pot, color=_POT, name=f"pot_{i}", lighting=True)
    for i, (pos, label) in enumerate(meshes["pot_labels"]):
        pl.add_point_labels(
            [pos],
            [label],
            font_size=_FONT_SIZE,
            text_color=_FONT_COLOR,
            point_size=0,
            shape=None,
            always_visible=True,
            name=f"pot_label_{i}",
        )
    _add_solid(pl, meshes["inlet"], color=_INLET, name="inlet", lighting=False)
    _add_solid(pl, meshes["outlet"], color=_OUTLET, name="outlet", lighting=False)
    for i, (pos, label) in enumerate(meshes["port_labels"]):
        pl.add_point_labels(
            [pos],
            [label],
            font_size=_FONT_SIZE,
            text_color=_FONT_COLOR,
            point_size=0,
            shape=None,
            always_visible=True,
            name=f"port_label_{i}",
        )


def _set_hud(pl: Any, snap: TwinSnapshot, *, legend: bool) -> None:
    """Parameters upper-left; runtime keys lower-left; view keys lower-right."""
    _safe_remove(pl, "params")
    pl.add_text(
        snap.params_table(),
        position="upper_left",
        font_size=_FONT_SIZE,
        color=_FONT_COLOR,
        font=_FONT_FAMILY,
        name="params",
    )
    if legend:
        _safe_remove(pl, "help")
        _safe_remove(pl, "runtime_keys")
        _safe_remove(pl, "view_keys")
        pl.add_text(
            _runtime_controls_table(),
            position="lower_left",
            font_size=_FONT_SIZE,
            color=_FONT_COLOR,
            font=_FONT_FAMILY,
            name="runtime_keys",
        )
        pl.add_text(
            _view_controls_table(),
            position="lower_right",
            font_size=_FONT_SIZE,
            color=_FONT_COLOR,
            font=_FONT_FAMILY,
            name="view_keys",
        )


def _ensure_arrow_actors(
    pl: Any, pv: Any, snap: TwinSnapshot, box_len: float, cache: dict[str, Any]
) -> None:
    """Create arrow actors once (hidden); fan toggle only flips visibility.

    remove_actor/add_mesh on every keypress is what produced purple wash +
    double red/blue outlines on macOS/VTK in interactive sessions.
    """
    if cache.get("arrow_ready"):
        return
    # Build from a synthetic fan-on snapshot geometry using current port points
    # if fan is off, still place arrows at vent centers from static meshes.
    inlet_c = cache.get("inlet_c")
    outlet_c = cache.get("outlet_c")
    length = max(0.04, 0.08 * box_len)
    origins: list[tuple[float, float, float]]
    if snap.exchange.points.shape[0] >= 2:
        origins = [tuple(float(v) for v in p) for p in snap.exchange.points[:2]]
    elif inlet_c is not None and outlet_c is not None:
        hx = 0.5 * box_len
        origins = [
            (float(inlet_c[0]) + 0.02 * hx, float(inlet_c[1]), float(inlet_c[2])),
            (float(outlet_c[0]) - 0.02 * hx, float(outlet_c[1]), float(outlet_c[2])),
        ]
    else:
        origins = []

    for i, origin in enumerate(origins[:2]):
        mesh = pv.Arrow(
            start=origin,
            direction=(1.0, 0.0, 0.0),
            tip_length=0.35,
            tip_radius=0.1,
            tip_resolution=12,
            shaft_radius=0.04,
            shaft_resolution=12,
            scale=length,
        )
        actor = _add_solid(pl, mesh, color=_ARROW, name=f"arrow_{i}", lighting=False)
        try:
            actor.SetVisibility(False)
        except Exception:
            try:
                actor.visibility = False
            except Exception:
                pass
    cache["arrow_ready"] = True
    cache["arrow_count"] = len(origins[:2])


def _set_arrows_visible(pl: Any, visible: bool, cache: dict[str, Any]) -> None:
    n = int(cache.get("arrow_count", 2))
    for i in range(n):
        actor = None
        try:
            actor = pl.actors.get(f"arrow_{i}")
        except Exception:
            actor = None
        if actor is None:
            continue
        try:
            actor.SetVisibility(bool(visible))
        except Exception:
            try:
                actor.visibility = bool(visible)
            except Exception:
                pass


def _scene_focus(pl: Any) -> tuple[float, float, float, float]:
    """Return (cx, cy, cz, span) from plotter bounds."""
    b = pl.bounds
    cx = 0.5 * (float(b[0]) + float(b[1]))
    cy = 0.5 * (float(b[2]) + float(b[3]))
    cz = 0.5 * (float(b[4]) + float(b[5]))
    span = max(float(b[1]) - float(b[0]), float(b[3]) - float(b[2]), float(b[5]) - float(b[4]), 0.5)
    return cx, cy, cz, span


def _set_standard_view(pl: Any, name: str) -> None:
    """CAD-style camera presets. HOME = default product angle.

    Always sets absolute camera_position (elevation/azimuth alone is easy to
    miss if the interactor already moved the camera).
    """
    cx, cy, cz, span = _scene_focus(pl)
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
        _set_standard_view(pl, "home")
        return
    try:
        pl.reset_camera_clipping_range()
    except Exception:
        pass
    pl.render()


def _bind_camera_keys(pl: Any) -> None:
    """HOME / view presets. Bind several KeySym aliases (macOS / numpad)."""

    def home() -> None:
        _set_standard_view(pl, "home")

    def iso() -> None:
        _set_standard_view(pl, "iso")

    def top() -> None:
        _set_standard_view(pl, "top")

    def front() -> None:
        _set_standard_view(pl, "front")

    def side() -> None:
        _set_standard_view(pl, "side")

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


def _attach_camera_controls(pl: Any, window_size: tuple[int, int] = (1200, 860)) -> None:
    """Mouse trackball + keyboard camera presets (no orientation gizmo)."""
    _ = window_size
    try:
        pl.enable_trackball_style()
    except Exception:
        pass
    _bind_camera_keys(pl)


def _force_mono_render(pl: Any) -> None:
    """Kill red/blue anaglyph stereo and MSAA line fringes (macOS VTK).

    Root cause of the purple scene + double red/blue chamber edges: VTK's
    default interactor binds key ``3`` to *toggle stereo* (RedBlue anaglyph).
    Our live mode also uses ``3`` for fan ON — so every fan press enabled stereo.

    Only StereoRenderOff — never SetStereoTypeTo* (Cocoa logs WARN for
    CrystalEyes / unsupported stereo type changes on the window).
    """
    try:
        rw = pl.render_window
    except Exception:
        return
    try:
        if rw.GetStereoRender():
            rw.StereoRenderOff()
    except Exception:
        try:
            rw.StereoRenderOff()
        except Exception:
            pass
    try:
        if rw.GetMultiSamples() != 0:
            rw.SetMultiSamples(0)
    except Exception:
        pass
    try:
        pv_theme = _require_pyvista().global_theme
        if getattr(pv_theme, "multi_samples", None) != 0:
            pv_theme.multi_samples = 0
    except Exception:
        pass


def _install_stereo_guard(pl: Any) -> None:
    """Re-assert mono every frame / key so VTK default '3'=stereo cannot stick."""

    def _on_start(_obj: Any = None, _evt: Any = None) -> None:
        _force_mono_render(pl)

    try:
        pl.render_window.AddObserver("StartEvent", _on_start)
    except Exception:
        pass
    # VTK CharEvent handles '3' as stereo toggle *after* some key callbacks.
    # Kill stereo on every key so fan key never leaves anaglyph on.
    try:
        iren = pl.iren.interactor if hasattr(pl, "iren") and pl.iren is not None else None
        if iren is not None:
            iren.AddObserver("KeyPressEvent", _on_start)
            iren.AddObserver("CharEvent", _on_start)
    except Exception:
        pass
    _force_mono_render(pl)


def _clear_vtk_default_keys(pl: Any) -> None:
    """Clear per-key PyVista callbacks we will rebind (never wipe all keys).

    Do **not** call ``clear_key_event_callbacks()`` — that drops every binding
    (including HOME 7/c) and was why camera presets appeared dead in live mode.
    """
    keys = (
        "1",
        "2",
        "3",
        "4",
        "5",
        "6",
        "7",
        "KP_7",
        "8",
        "KP_8",
        "9",
        "KP_9",
        "0",
        "KP_0",
        "s",
        "S",
        "r",
        "R",
        "w",
        "W",
        "c",
        "C",
        "i",
        "I",
        "f",
        "F",
        "h",
        "H",
        "u",
        "U",
        "m",
        "M",
        "space",
    )
    iren = getattr(pl, "iren", None)
    if iren is None:
        return
    clear = getattr(iren, "clear_events_for_key", None)
    if clear is None:
        return
    for key in keys:
        try:
            clear(key)
        except Exception:
            pass


def _radial_bg_cache_path() -> Path:
    """Temp file only — never write into the package tree."""
    name = f"growbox_ml_twin_radial_bg_v{_BG_RADIAL_VERSION}.png"
    return Path(tempfile.gettempdir()) / name


def _write_png_rgb(path: Path, width: int, height: int, rgb: bytes) -> None:
    """Minimal RGB PNG writer (no Pillow dependency)."""

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    raw = bytearray()
    row = width * 3
    for y in range(height):
        raw.append(0)  # filter None
        raw.extend(rgb[y * row : (y + 1) * row])
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(bytes(raw), 6))
        + chunk(b"IEND", b"")
    )


def _ensure_radial_background_png() -> Path:
    """Dark center, brighter outside — elliptical falloff matching window aspect."""
    path = _radial_bg_cache_path()
    if path.is_file() and path.stat().st_size > 200:
        return path

    w, h = _BG_RADIAL_W, _BG_RADIAL_H
    c0 = _BG_CENTER
    c1 = _BG_EDGE
    half_w = (w - 1) * 0.5
    half_h = (h - 1) * 0.5
    r_max = (1.0 + 1.0) ** 0.5  # unit-ellipse corner
    pixels = bytearray(w * h * 3)
    for y in range(h):
        ny = (y - half_h) / half_h
        row = y * w * 3
        for x in range(w):
            nx = (x - half_w) / half_w
            r = (nx * nx + ny * ny) ** 0.5 / r_max
            if r > 1.0:
                r = 1.0
            # Gentle ease-in: keep center flat longer, only soft lift near rim
            t = r * r  # quadratic — subtler than smoothstep at mid radii
            i = row + x * 3
            pixels[i] = int(c0[0] + (c1[0] - c0[0]) * t)
            pixels[i + 1] = int(c0[1] + (c1[1] - c0[1]) * t)
            pixels[i + 2] = int(c0[2] + (c1[2] - c0[2]) * t)
    _write_png_rgb(path, w, h, bytes(pixels))
    return path


def _apply_studio_background(pl: Any) -> None:
    """Circular gradient: darker in the center, brighter toward the edges."""
    edge = [c / 255.0 for c in _BG_EDGE]
    center = [c / 255.0 for c in _BG_CENTER]
    # Letterbox fill matches rim (never pure black bars)
    try:
        pl.set_background(edge)
    except Exception:
        pl.set_background("#323846")

    try:
        try:
            pl.remove_background_image()
        except Exception:
            pass
        png = _ensure_radial_background_png()
        pl.add_background_image(str(png), scale=1.05, auto_resize=True)
    except Exception:
        try:
            pl.set_background(center, top=edge)
        except Exception:
            pass


def _configure_plotter(pl: Any) -> None:
    """Stable look: mono only, no scalar bar, no MSAA color fringes."""
    _apply_studio_background(pl)
    _force_mono_render(pl)
    try:
        pl.disable_anti_aliasing()
    except Exception:
        pass
    try:
        pl.remove_scalar_bar()
    except Exception:
        pass
    _install_stereo_guard(pl)


def render_snapshot(
    snap: TwinSnapshot,
    *,
    screenshot: Path | None = None,
    interactive: bool = False,
    window_size: tuple[int, int] = (1100, 800),
) -> None:
    pv = _require_pyvista()
    try:
        pv.global_theme.multi_samples = 0
    except Exception:
        pass
    off_screen = screenshot is not None and not interactive
    pl = pv.Plotter(off_screen=off_screen, window_size=window_size)
    _configure_plotter(pl)
    meshes = build_static_meshes(pv, snap)
    _add_static_scene(pl, meshes)
    cache: dict[str, Any] = {
        "inlet_c": meshes["inlet_c"],
        "outlet_c": meshes["outlet_c"],
    }
    _ensure_arrow_actors(pl, pv, snap, meshes["box_len"], cache)
    _set_arrows_visible(pl, snap.action.fan > 0.02, cache)
    _set_hud(pl, snap, legend=True)
    if interactive:
        _attach_camera_controls(pl, window_size)
    _set_standard_view(pl, "home")
    if screenshot is not None:
        path = Path(screenshot)
        path.parent.mkdir(parents=True, exist_ok=True)
        pl.show(screenshot=str(path), auto_close=not interactive)
        if not interactive:
            pl.close()
            print(f"wrote {path}")
            return
    if interactive:
        pl.show()
    else:
        pl.close()


def run_rollout(
    *,
    steps: int,
    action: ControlAction,
    seed: int = 0,
    outside_temperature_c: float | None = None,
    screenshot: Path | None = None,
    interactive: bool = False,
) -> TwinSnapshot:
    scenario = default_scenario_v2(seed=seed)
    sim = SequentialEnvironmentSimulator(scenario, seed=seed)
    if outside_temperature_c is not None:
        sim.state.outside_temperature_c = float(outside_temperature_c)
    for _ in range(max(0, steps)):
        sim.step(action, add_sensor_noise=False)
    snap = snapshot_from_simulator(sim, action=action)
    render_snapshot(snap, screenshot=screenshot, interactive=interactive)
    return snap


def run_interactive_live(*, seed: int = 0, max_auto_steps: int = 200) -> None:
    """Live loop: geometry once; fan only toggles arrow visibility + HUD text."""
    pv = _require_pyvista()
    try:
        pv.global_theme.multi_samples = 0
    except Exception:
        pass
    sim = SequentialEnvironmentSimulator(default_scenario_v2(seed=seed), seed=seed)
    state = {"heater": 0.0, "fan": 0.0, "humidifier": 0.0, "steps": 0}
    cache: dict[str, Any] = {"arrow_ready": False, "ready": False}

    win = (1200, 860)
    pl = pv.Plotter(window_size=win)
    _configure_plotter(pl)
    try:
        pl.enable_trackball_style()
    except Exception:
        pass

    def action() -> ControlAction:
        return ControlAction(
            heater=state["heater"],
            fan=state["fan"],
            humidifier=state["humidifier"],
        )

    def refresh(*, hard: bool = False) -> None:
        _force_mono_render(pl)
        snap = snapshot_from_simulator(sim, action=action())
        if hard or not cache.get("ready"):
            # Full rebuild only on start/reset — never clear_actors mid-session.
            for name in list(getattr(pl, "actors", {}) or {}):
                _safe_remove(pl, name)
            for name in (
                "chamber",
                "inlet",
                "outlet",
                "params",
                "help",
                "runtime_keys",
                "view_keys",
                "pot_0",
                "pot_1",
                "pot_2",
                "pot_3",
                "pot_label_0",
                "pot_label_1",
                "port_label_0",
                "port_label_1",
                "arrow_0",
                "arrow_1",
            ):
                _safe_remove(pl, name)
            meshes = build_static_meshes(pv, snap)
            _add_static_scene(pl, meshes)
            cache["box_len"] = meshes["box_len"]
            cache["inlet_c"] = meshes["inlet_c"]
            cache["outlet_c"] = meshes["outlet_c"]
            cache["arrow_ready"] = False
            cache["ready"] = True
            _ensure_arrow_actors(pl, pv, snap, float(cache["box_len"]), cache)
            _set_arrows_visible(pl, snap.action.fan > 0.02, cache)
            _set_hud(pl, snap, legend=True)
            _set_standard_view(pl, "home")
            _force_mono_render(pl)
            return

        # Soft update: params table + arrow visibility only (no add/remove mesh)
        _set_hud(pl, snap, legend=False)
        _set_arrows_visible(pl, snap.action.fan > 0.02, cache)
        _force_mono_render(pl)
        pl.render()

    def set_cmd(key: str, value: float) -> None:
        # Always kill stereo first — VTK may still fire default '3' stereo toggle.
        _force_mono_render(pl)
        state[key] = _clip01(value)
        refresh(hard=False)
        _force_mono_render(pl)

    def bump(key: str, delta: float) -> None:
        _force_mono_render(pl)
        state[key] = _clip01(state[key] + delta)
        refresh(hard=False)
        _force_mono_render(pl)

    def step_once() -> None:
        if state["steps"] >= max_auto_steps:
            return
        _force_mono_render(pl)
        sim.step(action(), add_sensor_noise=False)
        state["steps"] += 1
        refresh(hard=False)

    def reset_sim() -> None:
        _force_mono_render(pl)
        sim.reset(seed=seed)
        state["steps"] = 0
        state["heater"] = 0.0
        state["fan"] = 0.0
        state["humidifier"] = 0.0
        cache["ready"] = False
        refresh(hard=True)

    # One clear + one full bind (camera keys must be re-added after clear).
    _clear_vtk_default_keys(pl)
    _bind_camera_keys(pl)
    pl.add_key_event("s", step_once)
    pl.add_key_event("space", step_once)
    pl.add_key_event("r", reset_sim)
    pl.add_key_event("1", lambda: set_cmd("heater", 1.0))
    pl.add_key_event("2", lambda: set_cmd("heater", 0.0))
    pl.add_key_event("3", lambda: set_cmd("fan", 1.0))
    pl.add_key_event("4", lambda: set_cmd("fan", 0.0))
    pl.add_key_event("5", lambda: set_cmd("humidifier", 1.0))
    pl.add_key_event("6", lambda: set_cmd("humidifier", 0.0))
    pl.add_key_event("h", lambda: bump("heater", 0.25))
    pl.add_key_event("H", lambda: bump("heater", -0.25))
    pl.add_key_event("f", lambda: bump("fan", 0.25))
    pl.add_key_event("F", lambda: bump("fan", -0.25))
    pl.add_key_event("u", lambda: bump("humidifier", 0.25))
    pl.add_key_event("U", lambda: bump("humidifier", -0.25))
    pl.add_key_event("m", lambda: (_force_mono_render(pl), pl.render()))

    refresh(hard=True)
    _force_mono_render(pl)
    pl.show()


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--steps", type=int, default=30)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--heater", type=float, default=0.0)
    p.add_argument("--fan", type=float, default=0.0)
    p.add_argument("--humidifier", type=float, default=0.0)
    p.add_argument("--outside-temperature-c", type=float, default=None)
    p.add_argument("--screenshot", type=Path, default=None)
    p.add_argument("--interactive", action="store_true")
    p.add_argument("--live", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.live or (args.interactive and args.steps == 0 and args.screenshot is None):
        run_interactive_live(seed=args.seed)
        return 0
    action = ControlAction(
        heater=float(args.heater),
        fan=float(args.fan),
        humidifier=float(args.humidifier),
    )
    snap = run_rollout(
        steps=int(args.steps),
        action=action,
        seed=int(args.seed),
        outside_temperature_c=args.outside_temperature_c,
        screenshot=args.screenshot,
        interactive=bool(args.interactive),
    )
    if args.screenshot is None and not args.interactive:
        print(snap.title())
        print(snap.params_table())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
