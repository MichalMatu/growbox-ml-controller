"""Tracking deviations, inject, and foresight rollouts."""

from __future__ import annotations

from tools.ml.deviations import (
    compute_deviations,
    deviations_from_decision,
    deviations_from_simulator,
)
from tools.ml.foresight import foresight, inject_state
from tools.ml.simulator import ControlAction, SequentialEnvironmentSimulator, default_scenario_v2


def test_compute_deviations_signs():
    report = compute_deviations(
        sensors={"air_temperature_c": 28.0, "air_humidity_pct": 50.0, "co2_ppm": 700.0},
        targets={"air_temperature_c": 25.0, "air_humidity_pct": 65.0, "co2_ppm": 850.0},
    )
    by = report.by_key()
    assert by["air_temperature_c"].error == 3.0
    assert by["air_humidity_pct"].error == -15.0
    assert by["co2_ppm"].error == -150.0
    assert report.rms_normalized > 0.0


def test_deviations_from_decision_ndjson_shape():
    record = {
        "type": "decision",
        "sensors": {"air_temperature_c": 21.0, "air_humidity_pct": 55.0, "co2_ppm": 900.0},
        "targets": {"air_temperature_c": 25.0, "air_humidity_pct": 65.0, "co2_ppm": 850.0},
        "validity": {"air_temperature_c": True},
    }
    report = deviations_from_decision(record)
    assert report.by_key()["air_temperature_c"].error == -4.0


def test_inject_and_foresight_heater_moves_temperature():
    sim = SequentialEnvironmentSimulator(default_scenario_v2(seed=7), seed=7)
    inject_state(sim, {"air_temperature_c": 18.0})
    before = deviations_from_simulator(sim)
    assert before.by_key()["air_temperature_c"].error is not None
    assert before.by_key()["air_temperature_c"].error < 0

    result = foresight(sim, ControlAction(heater=1.0), steps=8)
    assert len(result.steps) == 8
    # Caller sim unchanged
    assert sim.state.air_temperature_c == 18.0
    final_t = result.steps[-1].state.air_temperature_c
    assert final_t > 18.0
    # Error toward target should improve or at least warm up
    assert result.steps[-1].deviations.by_key()["air_temperature_c"].reading == final_t


def test_inject_pot_moisture():
    sim = SequentialEnvironmentSimulator(default_scenario_v2(seed=3), seed=3)
    inject_state(sim, {}, pot_overrides={0: {"soil_moisture_pct": 30.0}})
    assert sim.state.pots[0].soil_moisture_pct == 30.0
