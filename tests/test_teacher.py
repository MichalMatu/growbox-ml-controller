from __future__ import annotations

from dataclasses import replace

from tools.ml.simulator import (
    ActuatorCapabilities,
    ControlAction,
    FanCapabilities,
    HeaterCapabilities,
    HumidifierCapabilities,
    PumpCapabilities,
    SequentialEnvironmentSimulator,
)
from tools.ml.teacher import FIXED_CANDIDATES, CostConfig, RolloutTeacher


def test_candidate_set_and_tie_order_are_fixed():
    assert len(FIXED_CANDIDATES) == 40
    assert FIXED_CANDIDATES[0] == ControlAction()
    assert FIXED_CANDIDATES[-1] == ControlAction(1.0, 1.0, 1.0, 1.0)


def test_zero_cost_tie_selects_first_candidate(scenario):
    zero = CostConfig(
        temperature_error=0.0,
        humidity_error=0.0,
        co2_error=0.0,
        soil_moisture_error=0.0,
        energy=0.0,
        water=0.0,
        switching=0.0,
        constraint_violation=0.0,
        unreachable_target=0.0,
        terminal_multiplier=0.0,
    )
    result = RolloutTeacher(cost=zero, horizon_steps=1).choose(
        SequentialEnvironmentSimulator(scenario)
    )
    assert result.candidate_index == 0
    assert result.action == ControlAction()


def test_teacher_is_deterministic_and_does_not_advance_source(scenario):
    simulator = SequentialEnvironmentSimulator(scenario)
    before = simulator.state.as_dict()
    teacher = RolloutTeacher(horizon_steps=2)
    first = teacher.choose(simulator)
    second = teacher.choose(simulator)
    assert first == second
    assert simulator.state.as_dict() == before
    assert simulator.elapsed_s == 0.0


def test_teacher_never_selects_unavailable_outputs(scenario):
    unavailable = ActuatorCapabilities(
        heater=HeaterCapabilities(False, 0.0, 0.0, "binary"),
        fan=FanCapabilities(False, 0.0, 0.2),
        humidifier=HumidifierCapabilities(False, 0.0),
        irrigation_pump=PumpCapabilities(False, 0.0, 0.0, 300.0),
    )
    simulator = SequentialEnvironmentSimulator(replace(scenario, actuators=unavailable))
    result = RolloutTeacher(horizon_steps=2).choose(simulator)
    assert result.action == ControlAction()


def test_irrigation_interval_violation_has_explicit_cost(scenario):
    simulator = SequentialEnvironmentSimulator(scenario)
    simulator.step(ControlAction(irrigation=1.0), add_sensor_noise=False)
    teacher = RolloutTeacher(horizon_steps=1)
    irrigation = teacher.evaluate(simulator, ControlAction(irrigation=1.0))
    idle = teacher.evaluate(simulator, ControlAction())
    assert irrigation > idle
