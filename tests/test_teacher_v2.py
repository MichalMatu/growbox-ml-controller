from __future__ import annotations

from dataclasses import replace

import pytest

from tools.ml.generate_dataset_v2 import random_scenario_v2
from tools.ml.simulator_v2 import (
    ControlAction,
    HeaterCapabilities,
    PumpCapabilities,
    SequentialEnvironmentSimulatorV2,
    ZoneConfig,
    default_scenario_v2,
)
from tools.ml.teacher_v2 import (
    CostConfig,
    RolloutTeacherV2,
    build_candidates,
    irrigation_levels_for_zone,
)


@pytest.fixture
def scenario_v2():
    return default_scenario_v2(seed=17)


def test_build_candidates_scales_with_active_zones(scenario_v2):
    one_zone = SequentialEnvironmentSimulatorV2(scenario_v2)
    assert len(build_candidates(one_zone)) == 320

    two_zone_scenario = replace(
        scenario_v2,
        zones=(
            ZoneConfig(available=True, soil_moisture_valid=True, irrigation=PumpCapabilities(True)),
            ZoneConfig(available=True, soil_moisture_valid=True, irrigation=PumpCapabilities(True)),
            ZoneConfig(),
            ZoneConfig(),
        ),
    )
    two_zone = SequentialEnvironmentSimulatorV2(two_zone_scenario)
    assert len(build_candidates(two_zone)) == 640

    zero_zone = SequentialEnvironmentSimulatorV2(
        replace(scenario_v2, zones=(ZoneConfig(), ZoneConfig(), ZoneConfig(), ZoneConfig()))
    )
    assert len(build_candidates(zero_zone)) == 160


def test_zero_cost_tie_selects_first_candidate(scenario_v2):
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
    result = RolloutTeacherV2(cost=zero, horizon_steps=1).choose(
        SequentialEnvironmentSimulatorV2(scenario_v2)
    )
    assert result.candidate_index == 0
    assert result.action == ControlAction()


def test_teacher_is_deterministic_and_does_not_advance_source(scenario_v2):
    simulator = SequentialEnvironmentSimulatorV2(scenario_v2)
    before_temp = simulator.state.air_temperature_c
    teacher = RolloutTeacherV2(horizon_steps=2)
    first = teacher.choose(simulator)
    second = teacher.choose(simulator)
    assert first == second
    assert simulator.state.air_temperature_c == before_temp
    assert simulator.elapsed_s == 0.0


def test_teacher_never_selects_unavailable_outputs(scenario_v2):
    unavailable = replace(
        scenario_v2.actuators,
        heater=HeaterCapabilities(False, 0.0, 0.0),
        fan=replace(scenario_v2.actuators.fan, available=False, max_airflow_m3_h=0.0),
        humidifier=replace(scenario_v2.actuators.humidifier, available=False, max_output_g_h=0.0),
        dehumidifier=replace(scenario_v2.actuators.dehumidifier, available=False),
        cooler=replace(scenario_v2.actuators.cooler, available=False),
        co2_doser=replace(scenario_v2.actuators.co2_doser, available=False),
    )
    zones = tuple(
        replace(zone, irrigation=replace(zone.irrigation, available=False))
        for zone in scenario_v2.zones
    )
    simulator = SequentialEnvironmentSimulatorV2(
        replace(scenario_v2, actuators=unavailable, zones=zones)
    )
    result = RolloutTeacherV2(horizon_steps=2).choose(simulator)
    assert result.action == ControlAction()


def test_irrigation_blocked_when_soil_at_target(scenario_v2):
    simulator = SequentialEnvironmentSimulatorV2(scenario_v2)
    zone = simulator.scenario.zones[0]
    simulator.state.zones[0].soil_moisture_pct = zone.target_soil_moisture_pct
    assert irrigation_levels_for_zone(simulator, 0) == (0.0,)


def test_irrigation_interval_violation_has_explicit_cost(scenario_v2):
    simulator = SequentialEnvironmentSimulatorV2(scenario_v2)
    simulator.step(ControlAction(irrigation_zone_1=1.0), add_sensor_noise=False)
    teacher = RolloutTeacherV2(horizon_steps=1)
    irrigation = teacher.evaluate(simulator, ControlAction(irrigation_zone_1=1.0))
    idle = teacher.evaluate(simulator, ControlAction())
    assert irrigation > idle


def test_random_scenario_supports_zero_to_four_active_zones():
    counts = {
        len(random_scenario_v2(index, 9000 + index).active_zone_indices()) for index in range(40)
    }
    assert counts == {0, 1, 2, 3, 4}
