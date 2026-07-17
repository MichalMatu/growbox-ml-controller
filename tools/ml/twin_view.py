"""Scientific 3D twin view for the lumped growbox simulator (PyVista).

Not a game engine and not CFD — chamber box + pots + exchange glyphs from
fan / leak / outside driving forces.

Examples::

  pip install 'growbox-ml-controller-tools[twin]'   # or: pip install pyvista
  python -m tools.ml.twin_view --screenshot build/twin.png
  python -m tools.ml.twin_view --interactive --steps 0
  python -m tools.ml.twin_view --fan 1 --heater 0 --steps 40 --screenshot build/twin-fan.png
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
    humidity_opacity,
    pot_centers,
    pot_radius_height,
    snapshot_from_simulator,
    soil_moisture_to_rgb,
    temperature_to_rgb,
)


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
    radius, height = pot_radius_height(snap.box)
    centers = pot_centers(snap.box, n_pots=4)
    for index, center in enumerate(centers):
        if not snap.pot_active[index]:
            continue
        cx, cy, cz = center
        cyl = pv.Cylinder(
            center=(cx, cy, cz + 0.5 * height),
            direction=(0.0, 0.0, 1.0),
            radius=radius,
            height=height,
            resolution=24,
        )
        pots.append(cyl)
        pot_colors.append(soil_moisture_to_rgb(snap.pot_moisture[index]))

    # Exchange glyphs
    cloud = pv.PolyData(snap.exchange.points)
    cloud["vectors"] = snap.exchange.vectors
    cloud["mag"] = snap.exchange.magnitudes
    # Avoid zero-length arrows when fan off — still show tiny leak glyphs
    glyph = cloud.glyph(
        orient="vectors",
        scale="mag",
        factor=1.0,
        geom=pv.Arrow(tip_length=0.35, tip_radius=0.12, shaft_radius=0.04),
    )

    # Outside marker slab (thin plate beyond inlet wall)
    hx = 0.5 * sx
    outside = pv.Cube(
        center=(-hx - 0.08 * sx, 0.0, 0.5 * sz),
        x_length=0.04 * sx,
        y_length=0.6 * sy,
        z_length=0.6 * sz,
    )
    outside_color = temperature_to_rgb(snap.outside_temperature_c)

    return {
        "chamber": chamber,
        "chamber_color": chamber_color,
        "chamber_opacity": chamber_opacity,
        "outline": outline,
        "pots": pots,
        "pot_colors": pot_colors,
        "glyph": glyph,
        "outside": outside,
        "outside_color": outside_color,
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
    pl.add_mesh(meshes["outline"], color="white", line_width=2, name="outline")
    for i, (pot, color) in enumerate(zip(meshes["pots"], meshes["pot_colors"])):
        pl.add_mesh(pot, color=color, name=f"pot_{i}", smooth_shading=True)
    if meshes["glyph"].n_points > 0:
        pl.add_mesh(
            meshes["glyph"],
            color="#6ec6ff",
            name="exchange",
            opacity=0.9,
        )
    pl.add_mesh(
        meshes["outside"],
        color=meshes["outside_color"],
        opacity=0.55,
        name="outside",
    )

    caption = title or snap.title()
    pl.add_text(caption, font_size=9, color="white")
    pl.add_text(
        (
            f"outside T={snap.outside_temperature_c:.1f}°C  "
            f"RH={snap.outside_humidity_pct:.0f}%  |  "
            f"exchange: fan_ACH≈{snap.exchange.fan_ach_proxy:.1f}/h  "
            f"leak={snap.exchange.leak_ach:.2f}/h\n"
            "Lumped model glyphs — not CFD streamlines"
        ),
        position="lower_left",
        font_size=8,
        color="lightgray",
    )
    pl.set_background("#1a1f2b")
    pl.camera_position = "iso"
    pl.reset_camera()

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


def run_interactive_live(
    *,
    seed: int = 0,
    max_auto_steps: int = 200,
) -> None:
    """Interactive Plotter with sliders (heater / fan) and step button."""
    pv = _require_pyvista()
    scenario = default_scenario_v2(seed=seed)
    sim = SequentialEnvironmentSimulator(scenario, seed=seed)
    state = {
        "heater": 0.0,
        "fan": 0.0,
        "humidifier": 0.0,
        "steps_done": 0,
    }

    pl = pv.Plotter(window_size=(1200, 860))
    pl.set_background("#1a1f2b")

    def current_action() -> ControlAction:
        return ControlAction(
            heater=state["heater"],
            fan=state["fan"],
            humidifier=state["humidifier"],
        )

    def redraw() -> None:
        snap = snapshot_from_simulator(sim, action=current_action())
        meshes = build_plotter_meshes(pv, snap)
        pl.clear()
        pl.set_background("#1a1f2b")
        pl.add_mesh(
            meshes["chamber"],
            color=meshes["chamber_color"],
            opacity=meshes["chamber_opacity"],
            name="chamber",
            smooth_shading=True,
        )
        pl.add_mesh(meshes["outline"], color="white", line_width=2)
        for i, (pot, color) in enumerate(zip(meshes["pots"], meshes["pot_colors"])):
            pl.add_mesh(pot, color=color, name=f"pot_{i}", smooth_shading=True)
        if meshes["glyph"].n_points > 0:
            pl.add_mesh(meshes["glyph"], color="#6ec6ff", opacity=0.9)
        pl.add_mesh(meshes["outside"], color=meshes["outside_color"], opacity=0.55)
        pl.add_text(snap.title(), font_size=9, color="white")
        pl.add_text(
            "Sliders: heater / fan / humidifier  |  keys: s=step  r=reset  q=quit\n"
            "Arrows = lumped air exchange (fan + leak), not CFD",
            position="lower_left",
            font_size=8,
            color="lightgray",
        )
        pl.reset_camera()

    def on_heater(value: float) -> None:
        state["heater"] = float(value)
        redraw()

    def on_fan(value: float) -> None:
        state["fan"] = float(value)
        redraw()

    def on_humid(value: float) -> None:
        state["humidifier"] = float(value)
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
        redraw()

    pl.add_slider_widget(
        on_heater, [0.0, 1.0], value=0.0, title="heater", pointa=(0.05, 0.9), pointb=(0.35, 0.9)
    )
    pl.add_slider_widget(
        on_fan, [0.0, 1.0], value=0.0, title="fan", pointa=(0.05, 0.8), pointb=(0.35, 0.8)
    )
    pl.add_slider_widget(
        on_humid, [0.0, 1.0], value=0.0, title="humidifier", pointa=(0.05, 0.7), pointb=(0.35, 0.7)
    )
    pl.add_key_event("s", step_once)
    pl.add_key_event("r", reset_sim)
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
