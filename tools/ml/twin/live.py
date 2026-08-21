"""Snapshot render, rollout, and interactive live twin loop."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from ..profile import default_profile, load_profile, profile_to_scenario
from ..simulator import (
    ControlAction,
    SequentialEnvironmentSimulator,
)
from .camera import attach_camera_controls, bind_camera_keys, set_standard_view
from .config import (
    MENU_SECTIONS,
    ConfigEditor,
    apply_editor_to_simulator,
    bump_growbox_config,
    flat_from_profile,
    move_cursor,
    needs_geometry_rebuild,
    read_growbox_config,
    toggle_flag_at_cursor,
)
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

_LOG = logging.getLogger(__name__)


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
    profile_path: str | Path | None = None,
) -> TwinSnapshot:
    if profile_path is not None:
        profile = load_profile(profile_path)
    else:
        profile = default_profile(profile_id="rollout-default", title="Rollout default")
    scenario = profile_to_scenario(profile, seed=seed)
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
    profile_path: str | Path | None = None,
) -> None:
    """Live loop: geometry once; fan toggles arrows; ``p`` edits growbox config."""
    pv = require_pyvista()
    try:
        pv.global_theme.multi_samples = 0
    except Exception:
        pass
    if profile_path is not None:
        profile = load_profile(profile_path)
    else:
        profile = default_profile(profile_id="live-default", title="Live twin default")
    sim = SequentialEnvironmentSimulator(profile_to_scenario(profile, seed=seed), seed=seed)
    state = {
        "heater": 0.0,
        "fan": 0.0,
        "humidifier": 0.0,
        "steps": 0,
        "playing": False,
    }
    cache: dict[str, Any] = {"arrow_ready": False, "ready": False}
    # Auto-play period (ms between sim steps of timestep_s each)
    play_interval_ms = 120
    editor = ConfigEditor(
        active=False,
        level="root",
        section="chamber",
        menu_cursor=0,
        cursor=0,
        profile=profile,
        values=flat_from_profile(profile),
    )

    win = (1200, 860)
    pl = pv.Plotter(window_size=win)
    configure_plotter(pl)
    # Do not enable_trackball_style here — VTK warns "no current renderer"
    # until actors exist. Enabled after the first hard refresh below.

    def action() -> ControlAction:
        return ControlAction(
            heater=state["heater"],
            fan=state["fan"],
            humidifier=state["humidifier"],
        )

    def refresh(*, hard: bool = False, legend: bool | None = None) -> None:
        force_mono_render(pl)
        snap = snapshot_from_simulator(sim, action=action())
        show_legend = True if legend is None else legend
        if hard or not cache.get("ready"):
            # Full rebuild only on start/reset/geometry config — never clear_actors mid-session.
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
            cache["pot_label_texts"] = None
            set_hud(
                pl,
                snap,
                legend=True,
                config_editor=editor,
                playing=bool(state["playing"]),
                steps=int(state["steps"]),
                max_steps=max_auto_steps,
            )
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
        set_pot_labels(pl, pot_labels, cache=cache)
        set_hud(
            pl,
            snap,
            legend=show_legend,
            config_editor=editor,
            playing=bool(state["playing"]),
            steps=int(state["steps"]),
            max_steps=max_auto_steps,
        )
        set_arrows_visible(pl, snap.action.fan > 0.02, cache)
        force_mono_render(pl)
        pl.render()

    def set_cmd(key: str, value: float) -> None:
        if editor.active:
            return
        # Always kill stereo first — VTK may still fire default '3' stereo toggle.
        force_mono_render(pl)
        state[key] = _clip01(value)
        refresh(hard=False)
        force_mono_render(pl)

    def bump(key: str, delta: float) -> None:
        if editor.active:
            return
        force_mono_render(pl)
        state[key] = _clip01(state[key] + delta)
        refresh(hard=False)
        force_mono_render(pl)

    def step_once(*, from_timer: bool = False) -> None:
        if editor.active:
            return
        if state["steps"] >= max_auto_steps:
            state["playing"] = False
            if not from_timer:
                refresh(hard=False)
            return
        force_mono_render(pl)
        sim.step(action(), add_sensor_noise=False)
        state["steps"] += 1
        if state["steps"] >= max_auto_steps:
            state["playing"] = False
        refresh(hard=False)

    def set_playing(running: bool) -> None:
        state["playing"] = bool(running) and not editor.active
        if state["steps"] >= max_auto_steps:
            state["playing"] = False
        refresh(hard=False)

    def toggle_play() -> None:
        """space: play / pause (media-player style)."""
        if editor.active:
            return
        set_playing(not state["playing"])

    def reset_sim() -> None:
        if editor.active:
            return
        force_mono_render(pl)
        state["playing"] = False
        # Keep current hardware scenario; only reset process state / commands.
        sim.reset(seed=seed)
        state["steps"] = 0
        state["heater"] = 0.0
        state["fan"] = 0.0
        state["humidifier"] = 0.0
        cache["ready"] = False
        cache["pot_label_texts"] = None
        editor.profile = None
        editor.values = read_growbox_config(sim)
        refresh(hard=True)

    def toggle_config() -> None:
        """p always exits fully if open; otherwise opens root menu."""
        force_mono_render(pl)
        if editor.active:
            editor.close()
            refresh(hard=False, legend=True)
        else:
            # Pause while editing hardware — avoids mid-menu steps.
            state["playing"] = False
            editor.open_root(sim)
            refresh(hard=False, legend=True)
        force_mono_render(pl)

    def config_back() -> None:
        if not editor.active:
            return
        try:
            force_mono_render(pl)
            editor.back()
            refresh(hard=False, legend=True)
            force_mono_render(pl)
        except Exception:
            _LOG.exception("config_back failed")
            force_mono_render(pl)

    def config_move(delta: int) -> None:
        if not editor.active:
            return
        try:
            force_mono_render(pl)
            editor.ensure_values(sim)
            if editor.level == "root":
                editor.menu_cursor = move_cursor(
                    editor.menu_cursor, delta, n_items=len(MENU_SECTIONS)
                )
            else:
                editor.cursor = move_cursor(editor.cursor, delta, n_items=len(editor.rows()))
            refresh(hard=False, legend=True)
            force_mono_render(pl)
        except Exception:
            _LOG.exception("config_move failed")
            force_mono_render(pl)

    def _apply_editor_and_refresh() -> None:
        changed = apply_editor_to_simulator(sim, editor)
        hard = needs_geometry_rebuild(changed)
        if hard:
            cache["ready"] = False
        refresh(hard=hard, legend=True)

    def config_enter() -> None:
        if not editor.active:
            return
        try:
            force_mono_render(pl)
            if editor.level == "root":
                editor.enter_section()
                refresh(hard=False, legend=True)
            elif editor.is_flag_at_cursor():
                toggle_flag_at_cursor(editor)
                _apply_editor_and_refresh()
            force_mono_render(pl)
        except Exception:
            _LOG.exception("config_enter failed")
            force_mono_render(pl)

    def config_bump(direction: int, *, coarse: bool = False) -> None:
        if not editor.active or editor.level != "section":
            return
        try:
            force_mono_render(pl)
            if editor.is_flag_at_cursor():
                toggle_flag_at_cursor(editor)
                _apply_editor_and_refresh()
            else:
                cfg = editor.ensure_values(sim)
                editor.values = bump_growbox_config(
                    cfg,
                    editor.cursor,
                    direction=direction,
                    coarse=coarse,
                    section=editor.section,
                )
                _apply_editor_and_refresh()
            force_mono_render(pl)
        except Exception:
            _LOG.exception("config_bump failed")
            force_mono_render(pl)

    # One clear + one full bind (camera keys must be re-added after clear).
    clear_vtk_default_keys(pl)
    bind_camera_keys(pl)

    def space_key() -> None:
        if editor.active and editor.level == "section" and editor.is_flag_at_cursor():
            config_enter()
        elif editor.active:
            return
        else:
            toggle_play()

    def step_key() -> None:
        if editor.active:
            return
        # Manual step always advances once; does not force play.
        step_once(from_timer=False)

    def on_play_timer(_step: int = 0) -> None:
        if not state["playing"] or editor.active:
            return
        step_once(from_timer=True)

    pl.add_key_event("s", step_key)
    pl.add_key_event("S", step_key)
    pl.add_key_event("space", space_key)
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

    # Configurator: root menu → sections (keyboard only).
    pl.add_key_event("p", toggle_config)
    pl.add_key_event("P", toggle_config)
    pl.add_key_event("Escape", config_back)
    pl.add_key_event("j", lambda: config_move(1))
    pl.add_key_event("k", lambda: config_move(-1))
    pl.add_key_event("Down", lambda: config_move(1))
    pl.add_key_event("Up", lambda: config_move(-1))
    pl.add_key_event("Return", config_enter)
    pl.add_key_event("KP_Enter", config_enter)
    pl.add_key_event("minus", lambda: config_bump(-1))
    pl.add_key_event(
        "equal",
        lambda: (config_enter() if editor.active and editor.level == "root" else config_bump(1)),
    )
    pl.add_key_event("-", lambda: config_bump(-1))
    pl.add_key_event(
        "=",
        lambda: (config_enter() if editor.active and editor.level == "root" else config_bump(1)),
    )
    pl.add_key_event("plus", lambda: config_bump(1))
    pl.add_key_event("bracketleft", lambda: config_bump(-1, coarse=True))
    pl.add_key_event("bracketright", lambda: config_bump(1, coarse=True))
    pl.add_key_event("[", lambda: config_bump(-1, coarse=True))
    pl.add_key_event("]", lambda: config_bump(1, coarse=True))
    pl.add_key_event("Left", lambda: config_bump(-1))
    pl.add_key_event(
        "Right",
        lambda: (config_enter() if editor.active and editor.level == "root" else config_bump(1)),
    )

    refresh(hard=True)
    # Trackball only after meshes/renderer exist (avoids vtkInteractorStyle WARN).
    try:
        pl.enable_trackball_style()
        ren = getattr(pl, "renderer", None)
        iren = getattr(pl, "iren", None)
        style = getattr(iren, "style", None) if iren is not None else None
        if ren is not None and style is not None and hasattr(style, "SetDefaultRenderer"):
            style.SetDefaultRenderer(ren)
    except Exception:
        _LOG.debug("enable_trackball_style deferred setup failed", exc_info=True)

    # Repeating timer for play mode (callback no-ops while paused).
    try:
        pl.add_timer_event(
            max_steps=max(1, int(max_auto_steps) * 50),
            duration=int(play_interval_ms),
            callback=on_play_timer,
        )
    except Exception:
        _LOG.exception("add_timer_event failed — play mode unavailable")

    force_mono_render(pl)
    pl.show()
