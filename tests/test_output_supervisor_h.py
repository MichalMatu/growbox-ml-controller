from __future__ import annotations

import copy

import pytest

from tools.output_supervisor_h import (
    QUALIFIED_SHA,
    QualificationContractError,
    replay_qualification,
)


def endpoint(endpoint_id: int) -> list[object]:
    return [
        endpoint_id,
        0,
        0.0,
        0,
        0.0,
        0,
        0.0,
        0,
        0,
        0,
        0,
        0.0,
        0,
        0,
        1,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        1,
        0,
        5,
        6,
        0,
        0,
    ]


def baseline_fan() -> list[object]:
    fan = endpoint(1)
    fan[1] = 1
    fan[2] = 0.0
    fan[10] = 1
    fan[11] = 0.0
    fan[12] = 1
    fan[13] = 1
    fan[14] = 1
    fan[15] = 0
    fan[26] = 1
    fan[27] = 0
    fan[28] = 1
    fan[29] = 1
    return fan


def transition_fan() -> list[object]:
    fan = endpoint(1)
    fan[1] = 1
    fan[2] = 0.75
    fan[10] = 1
    fan[11] = 0.75
    fan[12] = 1
    fan[13] = 1
    fan[14] = 1
    fan[15] = 1
    fan[19] = 1
    fan[20] = 1
    fan[21] = 1
    fan[22] = 1
    fan[23] = 1
    fan[24] = 1
    fan[25] = 0
    fan[26] = 1
    fan[27] = 1
    fan[28] = 1
    fan[29] = 1
    return fan


def sample(uptime_ms: int, fan: list[object], *, transport_active: int) -> dict[str, object]:
    return {
        "t": "s",
        "v": 3,
        "u": uptime_ms,
        "out": {
            "v": 2,
            "m": 2,
            "ta": transport_active,
            "la": 0,
            "le": 0,
            "ae": 1,
            "sl": 0,
            "sr": 0,
            "ep": [fan, endpoint(2), endpoint(3)],
        },
    }


def records() -> list[dict[str, object]]:
    return [
        {
            "t": "session",
            "schema": "growbox-log-v3",
            "out_v": 2,
            "fw": QUALIFIED_SHA,
        },
        sample(10_000, baseline_fan(), transport_active=0),
        sample(20_000, transition_fan(), transport_active=1),
    ]


def evidence() -> dict[str, object]:
    return {
        "shelly_master_on": True,
        "power_before_w": [12.0, 12.1, 11.9, 12.0],
        "power_after_w": [20.0, 20.2, 19.9, 20.1],
        "minimum_power_delta_w": 5.0,
        "lamp_state_changed": False,
        "humidifier_state_changed": False,
        "environmental_response_supported": True,
    }


def test_replay_accepts_natural_supervisor_owned_transition() -> None:
    result = replay_qualification(records(), evidence())
    assert result.qualified_sha == QUALIFIED_SHA
    assert result.baseline_uptime_ms == 10_000
    assert result.transition_uptime_ms == 20_000
    assert result.power_delta_w == pytest.approx(8.05)


def test_replay_accepts_transition_sampled_after_command_cycle() -> None:
    fixture = records()
    transition = fixture[2]["out"]["ep"][0]
    transition[20] = 0
    result = replay_qualification(fixture, evidence())
    assert result.transition_uptime_ms == 20_000


def test_replay_rejects_sampled_transition_without_attempt_truth() -> None:
    fixture = records()
    transition = fixture[2]["out"]["ep"][0]
    transition[19] = 0
    transition[20] = 0
    with pytest.raises(
        QualificationContractError, match="no recorded OutputSupervisor command attempt"
    ):
        replay_qualification(fixture, evidence())


def test_replay_rejects_wrong_firmware_identity() -> None:
    fixture = records()
    fixture[0]["fw"] = "deadbeef"
    with pytest.raises(QualificationContractError, match="firmware identity mismatch"):
        replay_qualification(fixture, evidence())


def test_replay_rejects_manual_transition() -> None:
    fixture = records()
    transition = fixture[2]["out"]["ep"][0]
    transition[5] = 1
    with pytest.raises(QualificationContractError, match="manual intent"):
        replay_qualification(fixture, evidence())


def test_replay_rejects_safety_caused_transition() -> None:
    fixture = records()
    transition = fixture[2]["out"]["ep"][0]
    transition[7] = 1
    transition[17] = 1
    with pytest.raises(QualificationContractError, match="hard safety"):
        replay_qualification(fixture, evidence())


def test_replay_rejects_fabricated_physical_acknowledgement() -> None:
    fixture = records()
    transition = fixture[2]["out"]["ep"][0]
    transition[30] = 2
    transition[31] = 0
    with pytest.raises(QualificationContractError, match="claims physical state"):
        replay_qualification(fixture, evidence())


def test_replay_rejects_unexpected_transport_error_on_other_endpoint() -> None:
    fixture = copy.deepcopy(records())
    lamp = fixture[2]["out"]["ep"][1]
    lamp[24] = 2
    lamp[25] = 5
    with pytest.raises(QualificationContractError, match="transport_error"):
        replay_qualification(fixture, evidence())


def test_replay_rejects_confounded_shelly_evidence() -> None:
    fixture_evidence = evidence()
    fixture_evidence["lamp_state_changed"] = True
    with pytest.raises(QualificationContractError, match="lamp state changed"):
        replay_qualification(records(), fixture_evidence)
