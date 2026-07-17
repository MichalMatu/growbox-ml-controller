"""Scientific 3D twin view for the lumped growbox simulator (PyVista).

Minimal stable scene:
  - single white wireframe chamber outline (no fill, no T/RH color map)
  - fixed-color pot + inlet/outlet rings
  - at most two fixed-color fan arrows (visibility toggle only)
  - HUD tables for numbers (temperature lives only in the table)
  - orientation cross (UR) with white HOME center node (logo + click + keys 7/c)

No temperature/humidity geometric overlays. No solid chamber wash.
"""

from __future__ import annotations

import argparse
import struct
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

_HUD_FONT = 14
_LABEL_FONT = 14
_BG = "#12141a"
_WIRE = "#e8e8e8"
_POT = "#6b5b4b"
_INLET = "#5cb85c"
_OUTLET = "#5b9bd5"
_ARROW = "#c8e6f5"

# Camera orientation cube layout (must match _style_camera_widget)
_CAM_CUBE_SIZE = 200
_CAM_CUBE_PAD = 40
# Small center node only (pixels / normalized window fractions)
_HOME_DOT_SIZE = 28
_HOME_LOGO_FRAC = (0.028, 0.039)  # ~34×34 px on 1200×860
_HOME_PNG = Path(__file__).resolve().parent / "_twin_home_dot.png"


def _legend_table() -> str:
    rows: list[tuple[str, str]] = [
        ("s / space", "step +10 s"),
        ("r", "reset"),
        ("1 / 2", "heater on / off"),
        ("3 / 4", "fan on / off"),
        ("5 / 6", "humid on / off"),
        ("7 / c", "HOME (white center)"),
        ("8", "TOP"),
        ("9", "FRONT"),
        ("0", "SIDE"),
        ("i", "ISO"),
        ("m", "force mono (no stereo)"),
        ("green", "INLET"),
        ("blue", "OUTLET"),
    ]
    label_w = max(len(k) for k, _ in rows)
    value_w = max(len(v) for _, v in rows)
    inner = label_w + value_w + 3
    top = "┌" + "─" * (inner + 2) + "┐"
    mid = "├" + "─" * (inner + 2) + "┤"
    bot = "└" + "─" * (inner + 2) + "┘"
    lines = [top, f"│ {'controls'.ljust(inner)} │", mid]
    for key, value in rows:
        lines.append(f"│ {key.ljust(label_w)} : {value.ljust(value_w)} │")
    lines.append(bot)
    return "\n".join(lines)


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
            font_size=_LABEL_FONT,
            text_color="white",
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
            font_size=_LABEL_FONT,
            text_color="white",
            point_size=0,
            shape=None,
            always_visible=True,
            name=f"port_label_{i}",
        )


def _set_hud(pl: Any, snap: TwinSnapshot, *, legend: bool) -> None:
    _safe_remove(pl, "params")
    pl.add_text(
        snap.params_table(),
        position="upper_left",
        font_size=_HUD_FONT,
        color="white",
        font="courier",
        name="params",
    )
    if legend:
        _safe_remove(pl, "help")
        pl.add_text(
            _legend_table(),
            position="lower_left",
            font_size=_HUD_FONT,
            color="#c8c8c8",
            font="courier",
            name="help",
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


def _set_standard_view(pl: Any, name: str) -> None:
    """CAD-style camera presets. HOME = default product angle."""
    if name == "home":
        pl.view_isometric()
        pl.reset_camera()
        try:
            pl.camera.elevation(22.0)
            pl.camera.azimuth(-18.0)
            pl.camera.zoom(0.88)
        except Exception:
            b = pl.bounds
            cx = 0.5 * (b[0] + b[1])
            cy = 0.5 * (b[2] + b[3])
            cz = 0.5 * (b[4] + b[5])
            span = max(b[1] - b[0], b[3] - b[2], b[5] - b[4], 0.5)
            pl.camera_position = [
                (cx + 1.7 * span, cy - 1.85 * span, cz + 1.35 * span),
                (cx, cy, cz - 0.15 * span),
                (0.0, 0.0, 1.0),
            ]
    elif name == "iso":
        pl.view_isometric()
        pl.reset_camera()
    elif name == "top":
        pl.view_xy()
        pl.reset_camera()
    elif name == "front":
        pl.view_xz()
        pl.reset_camera()
    elif name == "side":
        pl.view_yz()
        pl.reset_camera()
    else:
        _set_standard_view(pl, "home")
        return
    pl.reset_camera_clipping_range()
    pl.render()


def _style_camera_widget(widget: Any) -> None:
    """Orientation cross: spaced axis dots. Center HOME is a separate logo (not container).

    VTK's orientation container is a large translucent sphere around the whole
    widget — painting it opaque white floods the UR corner (not a center dot).
    """
    try:
        rep = widget.GetRepresentation()
        rep.AnchorToUpperRight()
        rep.SetSize(_CAM_CUBE_SIZE, _CAM_CUBE_SIZE)
        rep.SetPadding(_CAM_CUBE_PAD, _CAM_CUBE_PAD)
        rep.SetNormalizedHandleDia(0.18)
        # Keep container off — HOME disc is drawn via logo widget at the hub.
        rep.SetContainerVisibility(False)
    except Exception:
        pass


def _home_button_position(window_size: tuple[int, int]) -> tuple[float, float]:
    """Pixel position (VTK origin = bottom-left) of HOME at cube center."""
    w, h = window_size
    x = w - _CAM_CUBE_PAD - _CAM_CUBE_SIZE / 2.0 - _HOME_DOT_SIZE / 2.0
    y = h - _CAM_CUBE_PAD - _CAM_CUBE_SIZE / 2.0 - _HOME_DOT_SIZE / 2.0
    return (float(x), float(y))


def _home_logo_position(window_size: tuple[int, int]) -> tuple[float, float]:
    """Normalized (0–1) bottom-left of logo so its center sits on the cube hub."""
    w, h = float(window_size[0]), float(window_size[1])
    cx = w - _CAM_CUBE_PAD - _CAM_CUBE_SIZE / 2.0
    cy = h - _CAM_CUBE_PAD - _CAM_CUBE_SIZE / 2.0
    sx, sy = _HOME_LOGO_FRAC
    return (cx / w - sx / 2.0, cy / h - sy / 2.0)


def _write_home_dot_png(path: Path, size: int = 64) -> Path:
    """Minimal white circle PNG (no Pillow dependency)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file() and path.stat().st_size > 50:
        return path

    # Build raw RGBA
    raw = bytearray()
    r0 = size / 2.0 - 0.5
    for y in range(size):
        raw.append(0)  # filter None
        for x in range(size):
            dx = x - r0
            dy = y - r0
            d = (dx * dx + dy * dy) ** 0.5
            if d <= r0 - 3:
                raw.extend((245, 245, 245, 255))
            elif d <= r0 - 1:
                raw.extend((220, 220, 220, 255))
            elif d <= r0:
                raw.extend((80, 90, 110, 255))
            else:
                raw.extend((0, 0, 0, 0))

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + chunk(b"IEND", b"")
    )
    path.write_bytes(png)
    return path


def _attach_home_center(pl: Any, window_size: tuple[int, int]) -> None:
    """White HOME node on the orientation cross (visible logo + click + keys)."""

    def _on_home(_state: bool = True) -> None:
        _set_standard_view(pl, "home")

    # 1) Always-visible small white disc at the cross hub (logo — shows in screenshots)
    try:
        png = _write_home_dot_png(_HOME_PNG)
        pos = _home_logo_position(window_size)
        pl.add_logo_widget(str(png), position=pos, size=_HOME_LOGO_FRAC)
    except Exception:
        pass

    # 2) Clickable checkbox on the same hub (same size as logo; logo is the visual)
    try:
        pl.add_checkbox_button_widget(
            _on_home,
            value=True,
            position=_home_button_position(window_size),
            size=_HOME_DOT_SIZE,
            border_size=1,
            color_on="#f5f5f5",
            color_off="#f5f5f5",
            background_color="#2a3140",
        )
    except Exception:
        pass

    # 3) Text label so HOME is discoverable even if widgets fail
    try:
        pl.add_text(
            "HOME · 7",
            position="upper_right",
            font_size=11,
            color="#f0f0f0",
            name="home_hint",
        )
    except Exception:
        pass


def _attach_camera_controls(pl: Any, window_size: tuple[int, int] = (1200, 860)) -> None:
    try:
        pl.enable_trackball_style()
    except Exception:
        pass
    try:
        widget = pl.add_camera_orientation_widget(animate=True)
        _style_camera_widget(widget)
    except Exception:
        try:
            widget = pl.add_camera_orientation_widget()
            _style_camera_widget(widget)
        except Exception:
            pass
    _attach_home_center(pl, window_size)

    pl.add_key_event("7", lambda: _set_standard_view(pl, "home"))
    pl.add_key_event("c", lambda: _set_standard_view(pl, "home"))
    pl.add_key_event("i", lambda: _set_standard_view(pl, "iso"))
    pl.add_key_event("8", lambda: _set_standard_view(pl, "top"))
    pl.add_key_event("9", lambda: _set_standard_view(pl, "front"))
    pl.add_key_event("0", lambda: _set_standard_view(pl, "side"))


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
    """Remove VTK/PyVista default key bindings that conflict with live controls.

    Critical: ``3`` = toggle stereo (RedBlue) in vtkRenderWindowInteractor.
    Also clear ``s``/``r``/``w`` surface-mode bindings we rebind ourselves.
    """
    keys = (
        "1",
        "2",
        "3",
        "4",
        "5",
        "6",
        "7",
        "8",
        "9",
        "0",
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
        "space",
    )
    iren = getattr(pl, "iren", None)
    if iren is None:
        return
    for key in keys:
        for meth in ("clear_events_for_key", "clear_key_event_callbacks"):
            fn = getattr(iren, meth, None)
            if fn is None:
                continue
            try:
                if meth == "clear_events_for_key":
                    fn(key)
                else:
                    fn()
            except TypeError:
                try:
                    fn(key)  # type: ignore[misc]
                except Exception:
                    pass
            except Exception:
                pass
            if meth == "clear_key_event_callbacks":
                return  # cleared all once


def _configure_plotter(pl: Any) -> None:
    """Stable look: mono only, no scalar bar, no MSAA color fringes."""
    pl.set_background(_BG)
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
    # Must clear VTK defaults BEFORE our bindings — key 3 = stereo anaglyph.
    _clear_vtk_default_keys(pl)
    _attach_camera_controls(pl, win)

    print(
        "twin_view LIVE | BUILD stereo-fix-v4\n"
        "  wireframe-only | no T/RH overlay | HOME=white center / key 7\n"
        "  key 3 = fan ON only (VTK stereo toggle DISABLED)\n"
        "  if scene goes purple/red-blue: press 4 then check stereo is off"
    )

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
                "home_hint",
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

    # Re-clear then bind — order matters vs VTK CharEvent stereo on '3'
    _clear_vtk_default_keys(pl)
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
    # Extra: press 'm' to force mono if anything re-enabled stereo
    pl.add_key_event("m", lambda: (_force_mono_render(pl), pl.render()))

    refresh(hard=True)
    _force_mono_render(pl)
    try:
        stereo = pl.render_window.GetStereoRender()
        print(
            f"  stereo_render={stereo} (must be 0) multi_samples={pl.render_window.GetMultiSamples()}"
        )
    except Exception:
        pass
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
