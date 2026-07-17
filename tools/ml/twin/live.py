"""Snapshot render, rollout, and interactive live twin loop."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..simulator import (
    ControlAction,
    SequentialEnvironmentSimulator,
    default_scenario_v2,
)
from .camera import attach_camera_controls, bind_camera_keys, set_standard_view
from .hud import set_hud
from .meshes import (
    add_static_scene,
    build_static_meshes,
    ensure_arrow_actors,
    pot_label_text,
    set_arrows_visible,
    set_pot_labels,
)
from .plotter import (
    clear_vtk_default_keys,
    configure_plotter,
    force_mono_render,
    require_pyvista,
    safe_remove,
)
from .scene import TwinSnapshot, snapshot_from_simulator


def _clip01(value: float) -> float:
    return min(1.0, max(0.0, float(value)))


def render_snapshot(
    snap: TwinSnapshot,
    *,
    screenshot: Path | None = None,
    interactive: bool = False,
    window_size: tuple[int, int] = (1100, 800),
) -> None:
    pv = require_pyvista()
    try:
        pv.global_theme.multi_samples = 0
    except Exception:
        pass
    off_screen = screenshot is not None and not interactive
    pl = pv.Plotter(off_screen=off_screen, window_size=window_size)
    configure_plotter(pl)
    meshes = build_static_meshes(pv, snap)
    add_static_scene(pl, meshes)
    cache: dict[str, Any] = {
        "inlet_c": meshes["inlet_c"],
        "outlet_c": meshes["outlet_c"],
    }
    ensure_arrow_actors(pl, pv, snap, meshes["box_len"], cache)
    set_arrows_visible(pl, snap.action.fan > 0.02, cache)
    set_hud(pl, snap, legend=True)
    if interactive:
        attach_camera_controls(pl, window_size)
    set_standard_view(pl, "home")
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
    pv = require_pyvista()
    try:
        pv.global_theme.multi_samples = 0
    except Exception:
        pass
    sim = SequentialEnvironmentSimulator(default_scenario_v2(seed=seed), seed=seed)
    state = {"heater": 0.0, "fan": 0.0, "humidifier": 0.0, "steps": 0}
    cache: dict[str, Any] = {"arrow_ready": False, "ready": False}

    win = (1200, 860)
    pl = pv.Plotter(window_size=win)
    configure_plotter(pl)
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
        force_mono_render(pl)
        snap = snapshot_from_simulator(sim, action=action())
        if hard or not cache.get("ready"):
            # Full rebuild only on start/reset — never clear_actors mid-session.
            for name in list(getattr(pl, "actors", {}) or {}):
                safe_remove(pl, name)
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
                "pot_label_2",
                "pot_label_3",
                "port_label_0",
                "port_label_1",
                "arrow_0",
                "arrow_1",
            ):
                safe_remove(pl, name)
            meshes = build_static_meshes(pv, snap)
            add_static_scene(pl, meshes)
            cache["box_len"] = meshes["box_len"]
            cache["inlet_c"] = meshes["inlet_c"]
            cache["outlet_c"] = meshes["outlet_c"]
            # Positions fixed; text rebuilt on soft refresh when moisture changes
            cache["pot_label_positions"] = [pos for pos, _label in meshes["pot_labels"]]
            cache["pot_label_indices"] = list(meshes["pot_label_indices"])
            cache["arrow_ready"] = False
            cache["ready"] = True
            ensure_arrow_actors(pl, pv, snap, float(cache["box_len"]), cache)
            set_arrows_visible(pl, snap.action.fan > 0.02, cache)
            set_hud(pl, snap, legend=True)
            set_standard_view(pl, "home")
            force_mono_render(pl)
            return

        # Soft update: HUD + pot moisture labels + arrow visibility (no mesh rebuild)
        pot_labels = [
            (pos, pot_label_text(index, snap.pot_moisture[index]))
            for pos, index in zip(
                cache.get("pot_label_positions", []),
                cache.get("pot_label_indices", []),
                strict=False,
            )
            if 0 <= index < len(snap.pot_moisture)
        ]
        set_pot_labels(pl, pot_labels)
        set_hud(pl, snap, legend=False)
        set_arrows_visible(pl, snap.action.fan > 0.02, cache)
        force_mono_render(pl)
        pl.render()

    def set_cmd(key: str, value: float) -> None:
        # Always kill stereo first — VTK may still fire default '3' stereo toggle.
        force_mono_render(pl)
        state[key] = _clip01(value)
        refresh(hard=False)
        force_mono_render(pl)

    def bump(key: str, delta: float) -> None:
        force_mono_render(pl)
        state[key] = _clip01(state[key] + delta)
        refresh(hard=False)
        force_mono_render(pl)

    def step_once() -> None:
        if state["steps"] >= max_auto_steps:
            return
        force_mono_render(pl)
        sim.step(action(), add_sensor_noise=False)
        state["steps"] += 1
        refresh(hard=False)

    def reset_sim() -> None:
        force_mono_render(pl)
        sim.reset(seed=seed)
        state["steps"] = 0
        state["heater"] = 0.0
        state["fan"] = 0.0
        state["humidifier"] = 0.0
        cache["ready"] = False
        refresh(hard=True)

    # One clear + one full bind (camera keys must be re-added after clear).
    clear_vtk_default_keys(pl)
    bind_camera_keys(pl)
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
    pl.add_key_event("m", lambda: (force_mono_render(pl), pl.render()))

    refresh(hard=True)
    force_mono_render(pl)
    pl.show()
