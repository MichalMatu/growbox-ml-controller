"""Lumped-model twin scene geometry and exchange field (no PyVista required)."""

from __future__ import annotations

import numpy as np

from tools.ml.simulator import ControlAction, SequentialEnvironmentSimulator, default_scenario_v2
from tools.ml.twin_scene import (
    box_from_volume,
    exchange_field,
    pot_centers,
    pot_layout_positions,
    pot_radius_height,
    snapshot_from_simulator,
)


def test_box_volume_matches_product():
    box = box_from_volume(0.8)
    sx, sy, sz = box.size_xyz
    assert abs(sx * sy * sz - 0.8) < 1e-6
    assert box.bounds[4] == 0.0  # floor at z=0


def test_pot_centers_four_on_floor():
    box = box_from_volume(1.0)
    centers = pot_centers(box, 4)
    assert len(centers) == 4
    assert all(c[2] == 0.0 for c in centers)


def test_single_active_pot_is_centered():
    box = box_from_volume(0.8)
    layout = pot_layout_positions(box, (True, False, False, False))
    assert len(layout) == 1
    _idx, x, y, z = layout[0]
    assert abs(x) < 1e-9 and abs(y) < 1e-9 and abs(z) < 1e-9


def test_pot_is_stocky_not_thin_tube():
    box = box_from_volume(0.8)
    radius, height = pot_radius_height(box)
    # Diameter should be >= height (bowl/pot proportions)
    assert 2.0 * radius >= height * 0.95
    assert height / (2.0 * radius) < 1.15


def test_fan_drives_inlet_outlet_arrows_not_walls():
    box = box_from_volume(0.8)
    idle = exchange_field(
        box,
        fan_command=0.0,
        air_leak_rate_ach=0.25,
        fan_max_airflow_m3_h=90.0,
        outside_temperature_c=10.0,
        outside_humidity_pct=40.0,
        air_temperature_c=28.0,
        air_humidity_pct=70.0,
    )
    windy = exchange_field(
        box,
        fan_command=1.0,
        air_leak_rate_ach=0.25,
        fan_max_airflow_m3_h=90.0,
        outside_temperature_c=10.0,
        outside_humidity_pct=40.0,
        air_temperature_c=28.0,
        air_humidity_pct=70.0,
    )
    # Sealed walls: no glyphs when fan is off; fan ON → exactly two small port arrows
    assert idle.points.shape[0] == 0
    assert windy.fan_ach_proxy > idle.fan_ach_proxy
    assert windy.points.shape[0] == 2
    assert float(np.mean(windy.magnitudes)) > 0.02
    assert float(np.max(windy.magnitudes)) < 0.5 * box.size_xyz[0]
    assert windy.labels == ("inlet", "outlet_fan")
    assert "leak" not in windy.labels


def test_snapshot_from_simulator_smoke():
    sim = SequentialEnvironmentSimulator(default_scenario_v2(seed=2), seed=2)
    sim.step(ControlAction(fan=0.5, heater=0.2), add_sensor_noise=False)
    snap = snapshot_from_simulator(sim)
    assert snap.elapsed_s > 0
    assert len(snap.pot_moisture) == 4
    assert snap.exchange.points.ndim == 2
    assert "T=" in snap.title()
    table = snap.params_table()
    assert "parameters" in table
    assert "air T" in table
    assert "out T" in table
    assert "heater" in table
    assert "┌" in table and "└" in table


def test_scene_labels_larger_than_hud_font():
    """In-chamber labels must stay readable vs compact HUD tables."""
    from tools.ml import twin_view

    assert twin_view._SCENE_LABEL_FONT_SIZE > twin_view._FONT_SIZE
    assert twin_view._pot_label_text(0, 42.4) == "P1 θ=42%"
