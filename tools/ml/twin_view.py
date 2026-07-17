"""Scientific 3D twin view for the lumped growbox simulator (PyVista).

Not a game engine and not CFD — chamber box + pots + inlet/outlet flow glyphs
(fan on exhaust; no air through walls).

Examples::

  pip install 'growbox-ml-controller-tools[twin]'   # or: pip install pyvista
  python -m tools.ml.twin_view --screenshot build/twin.png
  python -m tools.ml.twin_view --live
  python -m tools.ml.twin_view --fan 1 --heater 0 --steps 40 --screenshot build/twin-fan.png

Live mode is keyboard-only (VTK 2D sliders can SIGSEGV on macOS).
"""

from __future__ import annotations

import argparse
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
    soil_moisture_to_rgb,
    vent_port_centers,
)

# Single HUD text size (tables + scene labels)
_HUD_FONT = 14
_LABEL_FONT = 14

# Fixed chamber look — do NOT map T→RGB on the translucent cube (causes purple wash
# under VTK lighting when combined with cyan glyphs / double edges).
_CHAMBER_COLOR = "#4a5a48"
_CHAMBER_OPACITY = 0.20
_ARROW_COLOR = "#7ec8e8"
_ARROW_LEN_FRAC = 0.09  # of box length — small preview only


def _legend_table() -> str:
    """Fixed-width help panel for lower-left (same style as params table)."""
    rows: list[tuple[str, str]] = [
        ("s / space", "step +10 s"),
        ("r", "reset"),
        ("1 / 2", "heater on / off"),
        ("3 / 4", "fan on / off"),
        ("5 / 6", "humid on / off"),
        ("h / H", "heater ±0.25"),
        ("f / F", "fan ±0.25"),
        ("u / U", "humid ±0.25"),
        ("7 / c", "HOME (product)"),
        ("8", "camera TOP"),
        ("9", "camera FRONT"),
        ("0", "camera SIDE"),
        ("i", "camera ISO"),
        ("green ring", "INLET"),
        ("blue ring", "OUTLET"),
        ("arrows", "1 at inlet + 1 at outlet"),
        ("cube (R)", "view cube · axis dots"),
    ]
    label_w = max(len(k) for k, _ in rows)
    value_w = max(len(v) for _, v in rows)
    inner = label_w + value_w + 3
    top = "┌" + "─" * (inner + 2) + "┐"
    mid = "├" + "─" * (inner + 2) + "┤"
    bot = "└" + "─" * (inner + 2) + "┘"
    head = f"│ {'controls'.ljust(inner)} │"
    lines = [top, head, mid]
    for key, value in rows:
        lines.append(f"│ {key.ljust(label_w)} : {value.ljust(value_w)} │")
    lines.append(bot)
    return "\n".join(lines)


def _require_pyvista() -> Any:
    try:
        import pyvista as pv
    except ImportError as exc:  # pragma: no cover - optional dep
        raise SystemExit(
            "PyVista is required for twin_view.\n"
            "  pip install pyvista\n"
            "  # or: pip install -e '.[twin]'\n"
            f"Original error: {exc}"
        ) from exc
    return pv


def build_plotter_meshes(pv: Any, snap: TwinSnapshot) -> dict[str, Any]:
    """Create PyVista meshes for one snapshot (no plotter show)."""
    sx, sy, sz = snap.box.size_xyz
    # Box centered on floor: PyVista Cube is center-based
    chamber = pv.Cube(
        center=(0.0, 0.0, 0.5 * sz),
        x_length=sx,
        y_length=sy,
        z_length=sz,
    )
    # Wireframe outline for walls (always visible)
    outline = chamber.extract_feature_edges(boundary_edges=True, feature_edges=False)

    pots: list[Any] = []
    pot_colors: list[tuple[float, float, float]] = []
    pot_labels: list[tuple[tuple[float, float, float], str]] = []
    radius, height = pot_radius_height(snap.box)
    for index, cx, cy, cz in pot_layout_positions(snap.box, snap.pot_active):
        # Stocky pot: wide cylinder (not a thin pipe)
        cyl = pv.Cylinder(
            center=(cx, cy, cz + 0.5 * height),
            direction=(0.0, 0.0, 1.0),
            radius=radius,
            height=height,
            resolution=28,
        )
        pots.append(cyl)
        pot_colors.append(soil_moisture_to_rgb(snap.pot_moisture[index]))
        pot_labels.append(
            (
                (cx, cy, cz + height + 0.05 * sz),
                f"P{index + 1} θ={snap.pot_moisture[index]:.0f}%",
            )
        )

    # Exactly two tiny arrows when fan ON — plain Arrow meshes (no glyph filter / no scalars)
    arrows: list[Any] = []
    if snap.exchange.points.shape[0] >= 2:
        arrow_len = max(0.04, _ARROW_LEN_FRAC * sx)
        for origin in snap.exchange.points[:2]:
            arrows.append(
                pv.Arrow(
                    start=tuple(origin),
                    direction=(1.0, 0.0, 0.0),
                    tip_length=0.28,
                    tip_radius=0.07,
                    tip_resolution=8,
                    shaft_radius=0.03,
                    shaft_resolution=8,
                    scale=arrow_len,
                )
            )

    # Two round wall openings only (no fan tube) — PyVista: Disc, not Disk.
    inlet_c, outlet_c = vent_port_centers(snap.box)
    port_r = 0.14 * min(sx, sy)
    # Ring-like hole (inner radius) so it reads as an opening, not a solid cap
    inlet_disk = pv.Disc(
        center=inlet_c,
        inner=0.35 * port_r,
        outer=port_r,
        normal=(-1.0, 0.0, 0.0),
        r_res=20,
        c_res=20,
    )
    outlet_disk = pv.Disc(
        center=outlet_c,
        inner=0.35 * port_r,
        outer=port_r,
        normal=(1.0, 0.0, 0.0),
        r_res=20,
        c_res=20,
    )
    port_labels = [
        ((inlet_c[0] - 0.06 * sx, inlet_c[1], inlet_c[2] + 0.14 * sz), "INLET"),
        ((outlet_c[0] + 0.06 * sx, outlet_c[1], outlet_c[2] + 0.14 * sz), "OUTLET"),
    ]

    return {
        "chamber": chamber,
        "chamber_color": _CHAMBER_COLOR,
        "chamber_opacity": _CHAMBER_OPACITY,
        "outline": outline,
        "pots": pots,
        "pot_colors": pot_colors,
        "pot_labels": pot_labels,
        "arrows": arrows,
        "inlet_disk": inlet_disk,
        "outlet_disk": outlet_disk,
        "port_labels": port_labels,
    }


def _safe_remove(pl: Any, name: str) -> None:
    try:
        pl.remove_actor(name)
    except Exception:
        pass


def _add_scene_meshes(pl: Any, meshes: dict[str, Any], *, with_arrows: bool) -> None:
    """Add static-ish scene pieces (no full clear — call after targeted removes)."""
    pl.add_mesh(
        meshes["chamber"],
        color=meshes["chamber_color"],
        opacity=meshes["chamber_opacity"],
        name="chamber",
        smooth_shading=True,
        show_edges=False,
    )
    pl.add_mesh(meshes["outline"], color="white", line_width=2, name="outline")
    for i, (pot, color) in enumerate(zip(meshes["pots"], meshes["pot_colors"])):
        pl.add_mesh(pot, color=color, name=f"pot_{i}", smooth_shading=True, show_edges=False)
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
    pl.add_mesh(meshes["inlet_disk"], color="#4caf50", opacity=0.95, name="inlet", show_edges=False)
    pl.add_mesh(
        meshes["outlet_disk"], color="#42a5f5", opacity=0.95, name="outlet", show_edges=False
    )
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
    if with_arrows:
        for i, arrow in enumerate(meshes["arrows"]):
            pl.add_mesh(
                arrow,
                color=_ARROW_COLOR,
                name=f"arrow_{i}",
                smooth_shading=False,
                ambient=0.85,
                specular=0.0,
                show_edges=False,
                show_scalar_bar=False,
            )


def render_snapshot(
    snap: TwinSnapshot,
    *,
    screenshot: Path | None = None,
    interactive: bool = False,
    window_size: tuple[int, int] = (1100, 800),
    title: str | None = None,
) -> None:
    """Show or screenshot one frame."""
    pv = _require_pyvista()
    # Off-screen for screenshot-only runs (CI / headless)
    off_screen = screenshot is not None and not interactive
    pl = pv.Plotter(off_screen=off_screen, window_size=window_size)
    meshes = build_plotter_meshes(pv, snap)
    _add_scene_meshes(pl, meshes, with_arrows=bool(meshes["arrows"]))

    # Parameter table (upper left) + controls legend (lower left)
    pl.add_text(
        snap.params_table(),
        position="upper_left",
        font_size=_HUD_FONT,
        color="white",
        font="courier",
        name="params",
    )
    pl.add_text(
        _legend_table(),
        position="lower_left",
        font_size=_HUD_FONT,
        color="lightgray",
        font="courier",
        name="help",
    )
    pl.set_background("#1a1f2b")
    pl.camera_position = "iso"
    pl.reset_camera()
    if interactive:
        _attach_camera_controls(pl)

    if screenshot is not None:
        screenshot = Path(screenshot)
        screenshot.parent.mkdir(parents=True, exist_ok=True)
        pl.show(screenshot=str(screenshot), auto_close=not interactive)
        if not interactive:
            pl.close()
            print(f"wrote {screenshot}")
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
    """Advance simulator then render final snapshot."""
    scenario = default_scenario_v2(seed=seed)
    sim = SequentialEnvironmentSimulator(scenario, seed=seed)
    if outside_temperature_c is not None:
        sim.state.outside_temperature_c = float(outside_temperature_c)
    for _ in range(max(0, steps)):
        sim.step(action, add_sensor_noise=False)
    snap = snapshot_from_simulator(sim, action=action)
    render_snapshot(snap, screenshot=screenshot, interactive=interactive)
    return snap


def _clip01(value: float) -> float:
    return min(1.0, max(0.0, float(value)))


def _set_standard_view(pl: Any, name: str) -> None:
    """Apply a CAD-style view preset and re-fit the box."""
    if name == "home":
        # Product / Fusion-style home: pot on the floor, slight high 3/4 angle.
        pl.view_isometric()
        pl.reset_camera()
        cam = pl.camera
        # Elevate a bit more than pure iso so the floor + pot read clearly.
        try:
            cam.elevation(18.0)
            cam.azimuth(-12.0)
            cam.zoom(1.05)
        except Exception:
            # Fallback absolute camera if elevation API differs
            b = pl.bounds
            cx = 0.5 * (b[0] + b[1])
            cy = 0.5 * (b[2] + b[3])
            cz = 0.5 * (b[4] + b[5])
            span = max(b[1] - b[0], b[3] - b[2], b[5] - b[4], 0.5)
            pl.camera_position = [
                (cx + 1.55 * span, cy - 1.65 * span, cz + 1.15 * span),
                (cx, cy, cz - 0.12 * span),
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


def _style_camera_orientation_widget(widget: Any) -> None:
    """Larger spacing between axis handles; pull widget in from screen edge."""
    try:
        rep = widget.GetRepresentation()
    except Exception:
        return
    try:
        rep.AnchorToUpperRight()
    except Exception:
        pass
    try:
        # Bigger panel + more padding from window edge (default pad was 10,10)
        rep.SetSize(200, 200)
        rep.SetPadding(36, 36)
    except Exception:
        pass
    try:
        # Smaller handle dots relative to panel → more space between them
        rep.SetNormalizedHandleDia(0.26)
    except Exception:
        pass


def _attach_camera_controls(pl: Any) -> None:
    """Fusion-like camera aids: orientation cube (upper-right) + view keys.

    - View cube axis dots: click/drag (styled larger spacing, inset from edge).
    - Keys: 7/c = HOME product view, 8 TOP, 9 FRONT, 0 SIDE, i pure ISO.
    """
    try:
        pl.enable_trackball_style()
    except Exception:
        pass
    widget = None
    try:
        widget = pl.add_camera_orientation_widget(animate=True)
    except TypeError:
        try:
            widget = pl.add_camera_orientation_widget()
        except Exception:
            widget = None
    except Exception:
        widget = None
    if widget is not None:
        _style_camera_orientation_widget(widget)

    pl.add_key_event("7", lambda: _set_standard_view(pl, "home"))
    pl.add_key_event("c", lambda: _set_standard_view(pl, "home"))
    pl.add_key_event("8", lambda: _set_standard_view(pl, "top"))
    pl.add_key_event("9", lambda: _set_standard_view(pl, "front"))
    pl.add_key_event("0", lambda: _set_standard_view(pl, "side"))
    pl.add_key_event("i", lambda: _set_standard_view(pl, "iso"))


def run_interactive_live(
    *,
    seed: int = 0,
    max_auto_steps: int = 200,
) -> None:
    """Interactive Plotter — keyboard only (VTK sliders crash on some macOS/VTK builds).

    Keys
    ----
    s / space  step sim (10 s)
    r          reset
    1 / 2      heater on / off
    3 / 4      fan on / off
    5 / 6      humidifier on / off
    q          close (window)
    """
    pv = _require_pyvista()
    scenario = default_scenario_v2(seed=seed)
    sim = SequentialEnvironmentSimulator(scenario, seed=seed)
    state = {
        "heater": 0.0,
        "fan": 0.0,
        "humidifier": 0.0,
        "steps_done": 0,
        "first_draw": True,
    }

    pl = pv.Plotter(window_size=(1200, 860))
    pl.set_background("#1a1f2b")
    _attach_camera_controls(pl)
    # Track what is on the plotter so we never clear_actors() (that stacked outlines
    # and left purple garbage + lag when fan toggled).
    scene = {"static_built": False, "arrows_on": False, "n_pots": 0}

    def current_action() -> ControlAction:
        return ControlAction(
            heater=state["heater"],
            fan=state["fan"],
            humidifier=state["humidifier"],
        )

    def _remove_arrows() -> None:
        for i in range(4):
            _safe_remove(pl, f"arrow_{i}")
        scene["arrows_on"] = False

    def _remove_static() -> None:
        for name in (
            "chamber",
            "outline",
            "inlet",
            "outlet",
            "params",
            "help",
            "pot_0",
            "pot_1",
            "pot_2",
            "pot_3",
            "pot_label_0",
            "pot_label_1",
            "pot_label_2",
            "pot_label_3",
            "port_label_0",
            "port_label_1",
        ):
            _safe_remove(pl, name)
        _remove_arrows()
        scene["static_built"] = False

    def _update_hud(snap: TwinSnapshot, *, with_legend: bool = False) -> None:
        _safe_remove(pl, "params")
        pl.add_text(
            snap.params_table(),
            position="upper_left",
            font_size=_HUD_FONT,
            color="white",
            font="courier",
            name="params",
        )
        if with_legend:
            _safe_remove(pl, "help")
            pl.add_text(
                _legend_table(),
                position="lower_left",
                font_size=_HUD_FONT,
                color="lightgray",
                font="courier",
                name="help",
            )

    def _update_arrows(meshes: dict[str, Any], fan_on: bool) -> None:
        want = fan_on and bool(meshes["arrows"])
        if want == scene["arrows_on"] and scene["static_built"]:
            return
        _remove_arrows()
        if want:
            for i, arrow in enumerate(meshes["arrows"]):
                pl.add_mesh(
                    arrow,
                    color=_ARROW_COLOR,
                    name=f"arrow_{i}",
                    smooth_shading=False,
                    ambient=0.85,
                    specular=0.0,
                    show_edges=False,
                    show_scalar_bar=False,
                )
            scene["arrows_on"] = True

    def _update_pot_colors(meshes: dict[str, Any]) -> None:
        for i, color in enumerate(meshes["pot_colors"]):
            actor = pl.renderer.actors.get(f"pot_{i}") if hasattr(pl.renderer, "actors") else None
            # Fallback: plotter.actors mapping in recent PyVista
            if actor is None:
                try:
                    actor = pl.actors.get(f"pot_{i}")
                except Exception:
                    actor = None
            if actor is None:
                continue
            try:
                if isinstance(color, str):
                    actor.prop.color = color
                else:
                    actor.prop.color = color
            except Exception:
                pass

    def redraw(*, rebuild_static: bool = False) -> None:
        snap = snapshot_from_simulator(sim, action=current_action())
        meshes = build_plotter_meshes(pv, snap)
        fan_on = current_action().fan > 0.02

        if rebuild_static or not scene["static_built"]:
            _remove_static()
            _add_scene_meshes(pl, meshes, with_arrows=False)
            scene["static_built"] = True
            scene["n_pots"] = len(meshes["pots"])
            _update_hud(snap, with_legend=True)
        else:
            _update_pot_colors(meshes)
            _update_hud(snap, with_legend=False)

        _update_arrows(meshes, fan_on)

        if state["first_draw"]:
            _set_standard_view(pl, "home")
            state["first_draw"] = False
        else:
            pl.render()

    def bump(key: str, delta: float) -> None:
        state[key] = _clip01(state[key] + delta)
        # Fan toggles arrows only — never rebuild whole scene
        redraw(rebuild_static=False)

    def set_cmd(key: str, value: float) -> None:
        state[key] = _clip01(value)
        redraw(rebuild_static=False)

    def step_once() -> None:
        if state["steps_done"] >= max_auto_steps:
            return
        sim.step(current_action(), add_sensor_noise=False)
        state["steps_done"] += 1
        redraw(rebuild_static=False)

    def reset_sim() -> None:
        sim.reset(seed=seed)
        state["steps_done"] = 0
        state["first_draw"] = True
        redraw(rebuild_static=True)

    # No vtkSliderWidget — known SIGSEGV on macOS (GetCell null in SliderRepresentation2D).
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
    redraw(rebuild_static=True)
    pl.show()


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--steps", type=int, default=30, help="Simulator steps before render (10 s each)"
    )
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--heater", type=float, default=0.0)
    p.add_argument("--fan", type=float, default=0.0)
    p.add_argument("--humidifier", type=float, default=0.0)
    p.add_argument("--outside-temperature-c", type=float, default=None)
    p.add_argument("--screenshot", type=Path, default=None, help="Write PNG and exit (off-screen)")
    p.add_argument(
        "--interactive",
        action="store_true",
        help="Open interactive window (with sliders if --steps 0 and live mode)",
    )
    p.add_argument(
        "--live",
        action="store_true",
        help="Interactive live mode with sliders + keyboard step (s/r)",
    )
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
        # Default: print snapshot summary when no display requested
        print(snap.title())
        print(
            f"  exchange fan_ACH≈{snap.exchange.fan_ach_proxy:.2f}/h "
            f"leak={snap.exchange.leak_ach:.2f}/h  vectors={len(snap.exchange.magnitudes)}"
        )
        print("  hint: pass --screenshot path.png or --interactive / --live")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
