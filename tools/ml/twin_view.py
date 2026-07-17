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

import numpy as np

from .simulator import (
    ControlAction,
    SequentialEnvironmentSimulator,
    default_scenario_v2,
)
from .twin_scene import (
    TwinSnapshot,
    humidity_opacity,
    pot_layout_positions,
    pot_radius_height,
    snapshot_from_simulator,
    soil_moisture_to_rgb,
    temperature_to_rgb,
    vent_port_centers,
)

# Single HUD text size (tables + scene labels)
_HUD_FONT = 14
_LABEL_FONT = 14


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
        ("7", "camera ISO"),
        ("8", "camera TOP"),
        ("9", "camera FRONT"),
        ("0", "camera SIDE"),
        ("green ring", "INLET"),
        ("blue ring", "OUTLET"),
        ("arrows", "1 at inlet + 1 at outlet"),
        ("cube (R)", "drag faces = view"),
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
    chamber_color = temperature_to_rgb(snap.air_temperature_c)
    chamber_opacity = humidity_opacity(snap.air_humidity_pct)

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
            resolution=40,
        )
        pots.append(cyl)
        pot_colors.append(soil_moisture_to_rgb(snap.pot_moisture[index]))
        pot_labels.append(
            (
                (cx, cy, cz + height + 0.05 * sz),
                f"P{index + 1} θ={snap.pot_moisture[index]:.0f}%",
            )
        )

    # Two small preview arrows only (inlet + outlet centers) when fan ON.
    # Thin geometry + solid color (no scalar lighting) avoids purple wash / lag.
    if snap.exchange.points.shape[0] > 0:
        cloud = pv.PolyData(snap.exchange.points)
        cloud["vectors"] = snap.exchange.vectors
        glyph = cloud.glyph(
            orient="vectors",
            scale=False,
            factor=1.0,
            geom=pv.Arrow(
                tip_length=0.30,
                tip_radius=0.08,
                tip_resolution=12,
                shaft_radius=0.035,
                shaft_resolution=12,
                scale=float(np.mean(snap.exchange.magnitudes)),
            ),
        )
    else:
        glyph = pv.PolyData()

    # Two round wall openings only (no fan tube) — PyVista: Disc, not Disk.
    inlet_c, outlet_c = vent_port_centers(snap.box)
    port_r = 0.14 * min(sx, sy)
    # Ring-like hole (inner radius) so it reads as an opening, not a solid cap
    inlet_disk = pv.Disc(
        center=inlet_c,
        inner=0.35 * port_r,
        outer=port_r,
        normal=(-1.0, 0.0, 0.0),
        r_res=24,
        c_res=24,
    )
    outlet_disk = pv.Disc(
        center=outlet_c,
        inner=0.35 * port_r,
        outer=port_r,
        normal=(1.0, 0.0, 0.0),
        r_res=24,
        c_res=24,
    )
    port_labels = [
        ((inlet_c[0] - 0.06 * sx, inlet_c[1], inlet_c[2] + 0.14 * sz), "INLET"),
        ((outlet_c[0] + 0.06 * sx, outlet_c[1], outlet_c[2] + 0.14 * sz), "OUTLET"),
    ]

    return {
        "chamber": chamber,
        "chamber_color": chamber_color,
        "chamber_opacity": chamber_opacity,
        "outline": outline,
        "pots": pots,
        "pot_colors": pot_colors,
        "pot_labels": pot_labels,
        "glyph": glyph,
        "inlet_disk": inlet_disk,
        "outlet_disk": outlet_disk,
        "port_labels": port_labels,
    }


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

    pl.add_mesh(
        meshes["chamber"],
        color=meshes["chamber_color"],
        opacity=meshes["chamber_opacity"],
        name="chamber",
        smooth_shading=True,
    )
    pl.add_mesh(meshes["outline"], color="white", line_width=3, name="outline")
    for i, (pot, color) in enumerate(zip(meshes["pots"], meshes["pot_colors"])):
        pl.add_mesh(pot, color=color, name=f"pot_{i}", smooth_shading=True)
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
    pl.add_mesh(meshes["inlet_disk"], color="#4caf50", opacity=0.95, name="inlet")
    pl.add_mesh(meshes["outlet_disk"], color="#42a5f5", opacity=0.95, name="outlet")
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
    if meshes["glyph"].n_points > 0:
        pl.add_mesh(
            meshes["glyph"],
            color="#8fd3f4",
            name="exchange",
            opacity=1.0,
            smooth_shading=False,
            ambient=0.7,
            specular=0.0,
            show_scalar_bar=False,
        )

    # Parameter table (upper right) + short legend (lower left) — same font size
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
    """Apply a CAD-style orthographic/isometric preset and re-fit the box."""
    if name == "iso":
        pl.view_isometric()
    elif name == "top":
        pl.view_xy()
    elif name == "front":
        pl.view_xz()
    elif name == "side":
        pl.view_yz()
    else:
        pl.view_isometric()
    pl.reset_camera()
    pl.reset_camera_clipping_range()
    pl.render()


def _attach_camera_controls(pl: Any) -> None:
    """Fusion-like camera aids: orientation cube (upper-right) + view keys.

    VTK camera orientation widget = clickable/draggable view cube.
    Keys 7/8/9/0 snap to ISO / TOP / FRONT / SIDE without fighting trackball.
    """
    try:
        pl.enable_trackball_style()
    except Exception:
        pass
    try:
        # Interactive view cube (upper-right corner of the 3D view)
        pl.add_camera_orientation_widget(animate=True)
    except TypeError:
        try:
            pl.add_camera_orientation_widget()
        except Exception:
            # Older / headless builds — keys still work
            pass
    except Exception:
        pass

    pl.add_key_event("7", lambda: _set_standard_view(pl, "iso"))
    pl.add_key_event("8", lambda: _set_standard_view(pl, "top"))
    pl.add_key_event("9", lambda: _set_standard_view(pl, "front"))
    pl.add_key_event("0", lambda: _set_standard_view(pl, "side"))


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

    def current_action() -> ControlAction:
        return ControlAction(
            heater=state["heater"],
            fan=state["fan"],
            humidifier=state["humidifier"],
        )

    def redraw() -> None:
        snap = snapshot_from_simulator(sim, action=current_action())
        meshes = build_plotter_meshes(pv, snap)
        # clear_actors avoids wiping interactor state (safer than pl.clear() on macOS)
        pl.clear_actors()
        pl.set_background("#1a1f2b")
        pl.add_mesh(
            meshes["chamber"],
            color=meshes["chamber_color"],
            opacity=meshes["chamber_opacity"],
            name="chamber",
            smooth_shading=True,
        )
        pl.add_mesh(meshes["outline"], color="white", line_width=3, name="outline")
        for i, (pot, color) in enumerate(zip(meshes["pots"], meshes["pot_colors"])):
            pl.add_mesh(pot, color=color, name=f"pot_{i}", smooth_shading=True)
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
        pl.add_mesh(meshes["inlet_disk"], color="#4caf50", opacity=0.95, name="inlet")
        pl.add_mesh(meshes["outlet_disk"], color="#42a5f5", opacity=0.95, name="outlet")
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
        if meshes["glyph"].n_points > 0:
            pl.add_mesh(
                meshes["glyph"],
                color="#8fd3f4",
                opacity=1.0,
                name="exchange",
                smooth_shading=False,
                ambient=0.7,
                specular=0.0,
                show_scalar_bar=False,
            )
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
        if state["first_draw"]:
            _set_standard_view(pl, "iso")
            state["first_draw"] = False
        else:
            pl.render()

    def bump(key: str, delta: float) -> None:
        state[key] = _clip01(state[key] + delta)
        redraw()

    def set_cmd(key: str, value: float) -> None:
        state[key] = _clip01(value)
        redraw()

    def step_once() -> None:
        if state["steps_done"] >= max_auto_steps:
            return
        sim.step(current_action(), add_sensor_noise=False)
        state["steps_done"] += 1
        redraw()

    def reset_sim() -> None:
        sim.reset(seed=seed)
        state["steps_done"] = 0
        state["first_draw"] = True
        redraw()

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
    redraw()
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
