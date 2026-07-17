"""Lumped-model twin scene geometry and exchange field (no PyVista required)."""

from __future__ import annotations

import numpy as np

from tools.ml.simulator import ControlAction, SequentialEnvironmentSimulator, default_scenario_v2
from tools.ml.twin_scene import (
    box_from_volume,
    exchange_field,
    humidity_opacity,
    pot_centers,
    snapshot_from_simulator,
    soil_moisture_to_rgb,
    temperature_to_rgb,
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


def test_fan_increases_exchange_magnitudes():
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
    assert windy.fan_ach_proxy > idle.fan_ach_proxy
    assert float(np.mean(windy.magnitudes)) > float(np.mean(idle.magnitudes))
    assert idle.points.shape[0] == windy.points.shape[0]
    assert idle.vectors.shape == idle.points.shape


def test_snapshot_from_simulator_smoke():
    sim = SequentialEnvironmentSimulator(default_scenario_v2(seed=2), seed=2)
    sim.step(ControlAction(fan=0.5, heater=0.2), add_sensor_noise=False)
    snap = snapshot_from_simulator(sim)
    assert snap.elapsed_s > 0
    assert len(snap.pot_moisture) == 4
    assert snap.exchange.points.ndim == 2
    assert "T=" in snap.title()


def test_color_maps_monotonic():
    cold = temperature_to_rgb(12.0)
    hot = temperature_to_rgb(32.0)
    assert hot[0] >= cold[0]
    assert humidity_opacity(80.0) > humidity_opacity(20.0)
    wet = soil_moisture_to_rgb(90.0)
    dry = soil_moisture_to_rgb(10.0)
    assert wet[2] >= dry[2]
