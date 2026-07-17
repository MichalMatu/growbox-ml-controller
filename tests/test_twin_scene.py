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


def test_pot_mesh_scales_with_physical_volume():
    box = box_from_volume(0.8)
    r_small, h_small = pot_radius_height(box, pot_volume_l=6.0)
    r_ref, h_ref = pot_radius_height(box, pot_volume_l=12.0)
    r_big, h_big = pot_radius_height(box, pot_volume_l=24.0)
    assert r_small < r_ref < r_big
    assert h_small < h_ref < h_big


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


def test_growbox_config_section_complete_and_apply():
    """Full growbox section: env parameters + active pot count."""
    from tools.ml.twin.config import (
        GEOMETRY_KEYS,
        GROWBOX_FIELDS,
        apply_growbox_config,
        bump_growbox_config,
        config_table,
        needs_geometry_rebuild,
        read_growbox_config,
    )

    keys = {f.key for f in GROWBOX_FIELDS}
    # Chamber + expanded pot physical/irrigation template
    assert {
        "growbox_volume_m3",
        "thermal_mass_j_per_k",
        "heat_loss_w_per_k",
        "air_leak_rate_ach",
        "active_pots",
        "pot_volume_l",
        "substrate_water_capacity_ml",
        "transpiration_factor",
        "irrigation_flow_ml_s",
        "irrigation_maximum_pulse_s",
        "irrigation_minimum_interval_s",
        "heat_mat_max_power_w",
    }.issubset(keys)

    sim = SequentialEnvironmentSimulator(default_scenario_v2(seed=0), seed=0)
    before = read_growbox_config(sim)
    assert before.active_pots == 1
    assert before.growbox_volume_m3 == 0.8
    assert before.pot_volume_l == 12.0

    base = read_growbox_config(sim)
    cfg = (
        base.with_value("growbox_volume_m3", 1.2)
        .with_value("thermal_mass_j_per_k", 40_000.0)
        .with_value("heat_loss_w_per_k", 9.0)
        .with_value("air_leak_rate_ach", 0.5)
        .with_value("active_pots", 3)
        .with_value("pot_volume_l", 18.0)
        .with_value("substrate_water_capacity_ml", 4500.0)
    )
    changed = apply_growbox_config(sim, cfg)
    assert "growbox_volume_m3" in changed
    assert "active_pots" in changed
    assert "pot_volume_l" in changed
    assert needs_geometry_rebuild(changed)
    assert GEOMETRY_KEYS == frozenset({"growbox_volume_m3", "active_pots", "pot_volume_l"})

    after = read_growbox_config(sim)
    assert after.growbox_volume_m3 == 1.2
    assert after.thermal_mass_j_per_k == 40_000.0
    assert after.heat_loss_w_per_k == 9.0
    assert after.air_leak_rate_ach == 0.5
    assert after.active_pots == 3
    assert after.pot_volume_l == 18.0
    assert after.substrate_water_capacity_ml == 4500.0
    assert [p.available for p in sim.scenario.pots] == [True, True, True, False]
    assert all(p.cultivation.pot_volume_l == 18.0 for p in sim.scenario.pots if p.available)

    # Bump chamber volume field (index 0) by one fine step
    bumped = bump_growbox_config(after, 0, direction=1, coarse=False, section="chamber")
    assert bumped.growbox_volume_m3 == 1.3

    pot_bumped = bump_growbox_config(after, 1, direction=1, coarse=False, section="pots")
    assert pot_bumped.pot_volume_l == 19.0
    assert pot_bumped.substrate_water_capacity_ml > after.substrate_water_capacity_ml

    table = config_table(after, cursor=0, section="chamber")
    assert "config:Chamber" in table
    assert ">volume" in table
    assert "1.20 m3" in table
    pots_table = config_table(after, cursor=0, section="pots")
    assert "active pots" in pots_table
    assert "pot volume" in pots_table
    assert "pot water cap" in pots_table
