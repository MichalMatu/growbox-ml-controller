"""Scientific 3D twin view for the lumped growbox simulator (PyVista).

Minimal stable scene: wireframe chamber, pot, inlet/outlet rings, HUD tables.
No temperature/humidity color mapping (values live only in the params table).

Examples::

  pip install pyvista
  .venv/bin/python -m tools.ml.twin_view --live
  .venv/bin/python -m tools.ml.twin_view --steps 20 --fan 1 --screenshot build/twin.png
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
    vent_port_centers,
)

_HUD_FONT = 14
_LABEL_FONT = 14
_BG = "#12141a"
_WIRE = "#e8e8e8"
_POT = "#6b5b4b"
_INLET = "#5cb85c"
_OUTLET = "#5b9bd5"
_ARROW = "#9ad0f0"


def _legend_table() -> str:
    rows: list[tuple[str, str]] = [
        ("s / space", "step +10 s"),
        ("r", "reset"),
        ("1 / 2", "heater on / off"),
        ("3 / 4", "fan on / off"),
        ("5 / 6", "humid on / off"),
        ("7 / c", "HOME view"),
        ("8", "TOP"),
        ("9", "FRONT"),
        ("0", "SIDE"),
        ("i", "ISO"),
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


def build_static_meshes(pv: Any, snap: TwinSnapshot) -> dict[str, Any]:
    """Geometry that does not depend on fan command (no T/RH coloring)."""
    sx, sy, sz = snap.box.size_xyz
    # Single wireframe box only — solid+outline was the double-edge bug.
    chamber = pv.Cube(center=(0.0, 0.0, 0.5 * sz), x_length=sx, y_length=sy, z_length=sz)

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
                tip_length=0.3,
                tip_radius=0.08,
                tip_resolution=8,
                shaft_radius=0.035,
                shaft_resolution=8,
                scale=length,
            )
        )
    return arrows


def _add_static_scene(pl: Any, meshes: dict[str, Any]) -> None:
    """Wireframe chamber only — never solid fill (avoids double edges + purple wash)."""
    pl.add_mesh(
        meshes["chamber"],
        style="wireframe",
        color=_WIRE,
        line_width=2,
        name="chamber",
        render_lines_as_tubes=False,
    )
    for i, pot in enumerate(meshes["pots"]):
        pl.add_mesh(pot, color=_POT, name=f"pot_{i}", smooth_shading=True, show_edges=False)
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
    pl.add_mesh(meshes["inlet"], color=_INLET, name="inlet", show_edges=False)
    pl.add_mesh(meshes["outlet"], color=_OUTLET, name="outlet", show_edges=False)
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


def _set_arrows(
    pl: Any, pv: Any, snap: TwinSnapshot, box_len: float, flag: dict[str, bool]
) -> None:
    for i in range(4):
        _safe_remove(pl, f"arrow_{i}")
    flag["arrows"] = False
    arrows = build_arrow_meshes(pv, snap, box_len)
    if not arrows:
        return
    for i, mesh in enumerate(arrows):
        pl.add_mesh(
            mesh,
            color=_ARROW,
            name=f"arrow_{i}",
            show_edges=False,
            smooth_shading=False,
            ambient=0.9,
            specular=0.0,
            show_scalar_bar=False,
        )
    flag["arrows"] = True


def _set_standard_view(pl: Any, name: str) -> None:
    if name == "home":
        pl.view_isometric()
        pl.reset_camera()
        try:
            pl.camera.elevation(18.0)
            pl.camera.azimuth(-12.0)
            pl.camera.zoom(1.05)
        except Exception:
            pass
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
    try:
        rep = widget.GetRepresentation()
        rep.AnchorToUpperRight()
        rep.SetSize(200, 200)
        rep.SetPadding(36, 36)
        rep.SetNormalizedHandleDia(0.26)
    except Exception:
        pass


def _attach_camera_controls(pl: Any) -> None:
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
    pl.add_key_event("7", lambda: _set_standard_view(pl, "home"))
    pl.add_key_event("c", lambda: _set_standard_view(pl, "home"))
    pl.add_key_event("8", lambda: _set_standard_view(pl, "top"))
    pl.add_key_event("9", lambda: _set_standard_view(pl, "front"))
    pl.add_key_event("0", lambda: _set_standard_view(pl, "side"))
    pl.add_key_event("i", lambda: _set_standard_view(pl, "iso"))


def render_snapshot(
    snap: TwinSnapshot,
    *,
    screenshot: Path | None = None,
    interactive: bool = False,
    window_size: tuple[int, int] = (1100, 800),
) -> None:
    pv = _require_pyvista()
    off_screen = screenshot is not None and not interactive
    pl = pv.Plotter(off_screen=off_screen, window_size=window_size)
    pl.set_background(_BG)
    meshes = build_static_meshes(pv, snap)
    _add_static_scene(pl, meshes)
    _set_arrows(pl, pv, snap, meshes["box_len"], {"arrows": False})
    _set_hud(pl, snap, legend=True)
    if interactive:
        _attach_camera_controls(pl)
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
    """Live loop: build geometry once; only HUD + arrows update on keys."""
    pv = _require_pyvista()
    sim = SequentialEnvironmentSimulator(default_scenario_v2(seed=seed), seed=seed)
    state = {"heater": 0.0, "fan": 0.0, "humidifier": 0.0, "steps": 0}
    flags = {"arrows": False, "ready": False}

    pl = pv.Plotter(window_size=(1200, 860))
    pl.set_background(_BG)
    _attach_camera_controls(pl)

    def action() -> ControlAction:
        return ControlAction(
            heater=state["heater"],
            fan=state["fan"],
            humidifier=state["humidifier"],
        )

    def refresh(*, hard: bool = False) -> None:
        snap = snapshot_from_simulator(sim, action=action())
        if hard or not flags["ready"]:
            # Full rebuild only on start/reset — never clear_actors mid-session.
            for name in list(getattr(pl, "actors", {}) or {}):
                _safe_remove(pl, name)
            # Named removes for text / labels that may not be in actors dict
            for name in (
                "chamber",
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
                "port_label_0",
                "port_label_1",
                "arrow_0",
                "arrow_1",
            ):
                _safe_remove(pl, name)
            meshes = build_static_meshes(pv, snap)
            _add_static_scene(pl, meshes)
            flags["box_len"] = meshes["box_len"]
            flags["ready"] = True
            _set_hud(pl, snap, legend=True)
            _set_arrows(pl, pv, snap, float(flags["box_len"]), flags)
            _set_standard_view(pl, "home")
            return

        # Soft update: params table + fan arrows only
        _set_hud(pl, snap, legend=False)
        _set_arrows(pl, pv, snap, float(flags["box_len"]), flags)
        pl.render()

    def set_cmd(key: str, value: float) -> None:
        state[key] = _clip01(value)
        refresh(hard=False)

    def bump(key: str, delta: float) -> None:
        state[key] = _clip01(state[key] + delta)
        refresh(hard=False)

    def step_once() -> None:
        if state["steps"] >= max_auto_steps:
            return
        sim.step(action(), add_sensor_noise=False)
        state["steps"] += 1
        refresh(hard=False)

    def reset_sim() -> None:
        sim.reset(seed=seed)
        state["steps"] = 0
        state["heater"] = 0.0
        state["fan"] = 0.0
        state["humidifier"] = 0.0
        flags["ready"] = False
        refresh(hard=True)

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

    refresh(hard=True)
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
