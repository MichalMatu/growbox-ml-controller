"""Software-only parser and replay contract for OutputSupervisor Phase H qualification."""

from __future__ import annotations

import argparse
import json
import statistics
from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path
from typing import Any

QUALIFIED_SHA = "02208d23f403bca3540dbbd652eb55703a044833"
FAN_ENDPOINT = 1
OUTPUT_TELEMETRY_VERSION = 2
LOG_SCHEMA = "growbox-log-v3"


class SupervisorMode(IntEnum):
    BOOT_LOCKED = 0
    ARMING = 1
    AUTOMATIC = 2
    RECOVERING = 3
    DISABLED = 4
    FAULT_LOCKED = 5
    MAINTENANCE_LOCKED = 6


class OutputSource(IntEnum):
    NONE = 0
    CLIMATE = 1
    SCHEDULE = 2
    MANUAL = 3
    SAFETY = 4
    LIFECYCLE = 5
    MAINTENANCE = 6


class OutputReason(IntEnum):
    NONE = 0
    CLIMATE_DECISION = 1
    SCHEDULE_REQUEST = 2
    MANUAL_REQUEST = 3
    THERMAL_SAFETY = 4
    LIFECYCLE_POLICY = 5
    FAULT_CONTAINMENT = 6
    MAINTENANCE_REQUEST = 7


class TransportStatus(IntEnum):
    NOT_ATTEMPTED = 0
    COMPLETED = 1
    FAILED = 2


class TransportError(IntEnum):
    NONE = 0
    INVALID_ENDPOINT = 1
    INVALID_COMMAND = 2
    UNAVAILABLE = 3
    BUSY = 4
    IO_FAILURE = 5


class BinaryOutputState(IntEnum):
    OFF = 0
    ON = 1


class PhysicalOutputState(IntEnum):
    UNKNOWN = 0
    OFF = 1
    ON = 2


class QualificationContractError(ValueError):
    """Raised when replay evidence violates the OutputSupervisor H contract."""


@dataclass(frozen=True)
class EndpointTelemetry:
    endpoint: int
    control_active: bool
    control_level: float
    schedule_active: bool
    manual_active: bool
    safety_active: bool
    selected: bool
    selected_level: float
    selected_source: int
    selected_reason: int
    resolved: bool
    resolved_state: int
    held_by_dwell: bool
    safety_override: bool
    inhibited: bool
    attempt_known: bool
    attempted_this_cycle: bool
    attempt_state: int
    attempt_source: int
    attempt_reason: int
    transport_status: int
    transport_error: int
    last_command_known: bool
    last_command_state: int
    last_command_source: int
    last_command_reason: int
    physical_state: int
    physical_independent: bool


@dataclass(frozen=True)
class OutputSnapshot:
    uptime_ms: int
    mode: int
    transport_active: bool
    lifecycle_active: bool
    automation_requested: bool
    safety_latched: bool
    endpoints: tuple[EndpointTelemetry, ...]

    def endpoint(self, endpoint_id: int) -> EndpointTelemetry:
        matches = [endpoint for endpoint in self.endpoints if endpoint.endpoint == endpoint_id]
        if len(matches) != 1:
            raise QualificationContractError(
                f"expected exactly one endpoint {endpoint_id}, found {len(matches)}"
            )
        return matches[0]


@dataclass(frozen=True)
class QualificationReplayResult:
    qualified_sha: str
    baseline_uptime_ms: int
    transition_uptime_ms: int
    power_before_median_w: float
    power_after_median_w: float
    power_delta_w: float


def _bool(value: Any) -> bool:
    return bool(int(value))


def _endpoint_from_array(values: list[Any]) -> EndpointTelemetry:
    if len(values) != 32:
        raise QualificationContractError(
            f"telemetry v2 endpoint array must contain 32 fields, got {len(values)}"
        )
    endpoint = EndpointTelemetry(
        endpoint=int(values[0]),
        control_active=_bool(values[1]),
        control_level=float(values[2]),
        schedule_active=_bool(values[3]),
        manual_active=_bool(values[5]),
        safety_active=_bool(values[7]),
        selected=_bool(values[10]),
        selected_level=float(values[11]),
        selected_source=int(values[12]),
        selected_reason=int(values[13]),
        resolved=_bool(values[14]),
        resolved_state=int(values[15]),
        held_by_dwell=_bool(values[16]),
        safety_override=_bool(values[17]),
        inhibited=_bool(values[18]),
        attempt_known=_bool(values[19]),
        attempted_this_cycle=_bool(values[20]),
        attempt_state=int(values[21]),
        attempt_source=int(values[22]),
        attempt_reason=int(values[23]),
        transport_status=int(values[24]),
        transport_error=int(values[25]),
        last_command_known=_bool(values[26]),
        last_command_state=int(values[27]),
        last_command_source=int(values[28]),
        last_command_reason=int(values[29]),
        physical_state=int(values[30]),
        physical_independent=_bool(values[31]),
    )
    if not endpoint.physical_independent and endpoint.physical_state != PhysicalOutputState.UNKNOWN:
        raise QualificationContractError(
            f"endpoint {endpoint.endpoint} claims physical state without independent evidence"
        )
    return endpoint


def parse_output_snapshot(record: dict[str, Any]) -> OutputSnapshot:
    if record.get("t") != "s":
        raise QualificationContractError("qualification transition records must be sample records")
    output = record.get("out")
    if not isinstance(output, dict):
        raise QualificationContractError("sample record is missing output telemetry")
    if int(output.get("v", -1)) != OUTPUT_TELEMETRY_VERSION:
        raise QualificationContractError("output telemetry version is not v2")
    raw_endpoints = output.get("ep")
    if not isinstance(raw_endpoints, list):
        raise QualificationContractError("output telemetry endpoint list is missing")
    endpoints = tuple(_endpoint_from_array(values) for values in raw_endpoints)
    return OutputSnapshot(
        uptime_ms=int(record["u"]),
        mode=int(output["m"]),
        transport_active=_bool(output["ta"]),
        lifecycle_active=_bool(output["la"]),
        automation_requested=_bool(output["ae"]),
        safety_latched=_bool(output["sl"]),
        endpoints=endpoints,
    )


def validate_session_record(record: dict[str, Any]) -> None:
    if record.get("t") != "session":
        raise QualificationContractError("first record must be a session record")
    if record.get("schema") != LOG_SCHEMA:
        raise QualificationContractError(f"unexpected log schema: {record.get('schema')!r}")
    if int(record.get("out_v", -1)) != OUTPUT_TELEMETRY_VERSION:
        raise QualificationContractError("session does not advertise output telemetry v2")
    if record.get("fw") != QUALIFIED_SHA:
        raise QualificationContractError(
            f"firmware identity mismatch: {record.get('fw')!r} != {QUALIFIED_SHA}"
        )


def _assert_snapshot_normal(snapshot: OutputSnapshot) -> None:
    if snapshot.mode == SupervisorMode.MAINTENANCE_LOCKED:
        raise QualificationContractError("MaintenanceLocked is forbidden in normal H proof")
    if snapshot.mode != SupervisorMode.AUTOMATIC:
        raise QualificationContractError(f"supervisor mode is not Automatic: {snapshot.mode}")
    if not snapshot.automation_requested:
        raise QualificationContractError("automation is not requested")
    if snapshot.lifecycle_active:
        raise QualificationContractError("lifecycle execution is active during normal proof")


def _assert_transport_clean(snapshot: OutputSnapshot) -> None:
    for endpoint in snapshot.endpoints:
        if endpoint.transport_error != TransportError.NONE:
            raise QualificationContractError(
                f"endpoint {endpoint.endpoint} transport_error={endpoint.transport_error}"
            )
        if endpoint.transport_status == TransportStatus.FAILED:
            raise QualificationContractError(
                f"endpoint {endpoint.endpoint} transport status is Failed"
            )


def _is_clean_fan_off_baseline(snapshot: OutputSnapshot) -> bool:
    fan = snapshot.endpoint(FAN_ENDPOINT)
    return (
        not snapshot.safety_latched
        and not fan.manual_active
        and not fan.safety_active
        and not fan.safety_override
        and not fan.inhibited
        and fan.resolved
        and fan.resolved_state == BinaryOutputState.OFF
        and fan.last_command_known
        and fan.last_command_state == BinaryOutputState.OFF
    )


def _assert_natural_fan_on_transition(snapshot: OutputSnapshot) -> None:
    fan = snapshot.endpoint(FAN_ENDPOINT)
    if snapshot.safety_latched or fan.safety_active or fan.safety_override or fan.inhibited:
        raise QualificationContractError(
            "hard safety caused or inhibited the counted fan transition"
        )
    if fan.manual_active:
        raise QualificationContractError("manual intent is active during counted fan transition")
    if not fan.control_active or fan.control_level <= 0.0:
        raise QualificationContractError("fan transition has no active natural climate intent")
    if not fan.selected or fan.selected_source != OutputSource.CLIMATE:
        raise QualificationContractError("fan selection is not climate-owned")
    if fan.selected_reason != OutputReason.CLIMATE_DECISION:
        raise QualificationContractError("fan selection reason is not ClimateDecision")
    if not fan.resolved or fan.resolved_state != BinaryOutputState.ON:
        raise QualificationContractError("fan did not resolve ON")
    if fan.held_by_dwell:
        raise QualificationContractError("counted fan transition is still held by dwell")
    if not fan.attempt_known or not fan.attempted_this_cycle:
        raise QualificationContractError("no OutputSupervisor command attempt in counted cycle")
    if fan.attempt_state != BinaryOutputState.ON:
        raise QualificationContractError("counted command attempt is not fan ON")
    if fan.attempt_source != OutputSource.CLIMATE:
        raise QualificationContractError("counted command attempt is not climate-sourced")
    if fan.attempt_reason != OutputReason.CLIMATE_DECISION:
        raise QualificationContractError("counted command attempt reason is not ClimateDecision")
    if fan.transport_status != TransportStatus.COMPLETED:
        raise QualificationContractError("fan RF transport did not complete")
    if fan.transport_error != TransportError.NONE:
        raise QualificationContractError("fan RF transport reported an error")
    if not fan.last_command_known or fan.last_command_state != BinaryOutputState.ON:
        raise QualificationContractError("last commanded fan state is not ON")
    if fan.last_command_source != OutputSource.CLIMATE:
        raise QualificationContractError("last commanded fan source is not climate")
    if fan.last_command_reason != OutputReason.CLIMATE_DECISION:
        raise QualificationContractError("last commanded fan reason is not ClimateDecision")
    if not snapshot.transport_active:
        raise QualificationContractError("transport is not active for counted command attempt")


def find_natural_fan_transition(
    records: list[dict[str, Any]],
) -> tuple[OutputSnapshot, OutputSnapshot]:
    if not records:
        raise QualificationContractError("no telemetry records supplied")
    validate_session_record(records[0])
    baseline: OutputSnapshot | None = None
    for record in records[1:]:
        if record.get("t") != "s":
            continue
        snapshot = parse_output_snapshot(record)
        _assert_snapshot_normal(snapshot)
        _assert_transport_clean(snapshot)
        if baseline is None:
            if _is_clean_fan_off_baseline(snapshot):
                baseline = snapshot
            continue
        if snapshot.uptime_ms <= baseline.uptime_ms:
            raise QualificationContractError("telemetry uptime did not advance after baseline")
        fan = snapshot.endpoint(FAN_ENDPOINT)
        if fan.attempted_this_cycle and fan.attempt_state == BinaryOutputState.ON:
            _assert_natural_fan_on_transition(snapshot)
            return baseline, snapshot
    raise QualificationContractError("no qualifying natural fan OFF->ON transition found")


def validate_independent_evidence(evidence: dict[str, Any]) -> tuple[float, float, float]:
    if evidence.get("shelly_master_on") is not True:
        raise QualificationContractError("Shelly master must remain ON")
    if evidence.get("lamp_state_changed") is not False:
        raise QualificationContractError("lamp state changed during Shelly fan proof window")
    if evidence.get("humidifier_state_changed") is not False:
        raise QualificationContractError("humidifier state changed during Shelly fan proof window")
    before = [float(value) for value in evidence.get("power_before_w", [])]
    after = [float(value) for value in evidence.get("power_after_w", [])]
    if len(before) < 3 or len(after) < 3:
        raise QualificationContractError(
            "at least three Shelly samples are required before and after"
        )
    minimum_delta = float(evidence.get("minimum_power_delta_w", 0.0))
    if minimum_delta <= 0.0:
        raise QualificationContractError("minimum_power_delta_w must be positive")
    before_median = float(statistics.median(before))
    after_median = float(statistics.median(after))
    delta = after_median - before_median
    if delta < minimum_delta:
        raise QualificationContractError(
            f"Shelly power delta {delta:.3f} W is below {minimum_delta:.3f} W"
        )
    if evidence.get("environmental_response_supported") is not True:
        raise QualificationContractError("environmental response evidence is missing")
    return before_median, after_median, delta


def replay_qualification(
    records: list[dict[str, Any]], evidence: dict[str, Any]
) -> QualificationReplayResult:
    baseline, transition = find_natural_fan_transition(records)
    before_median, after_median, delta = validate_independent_evidence(evidence)
    return QualificationReplayResult(
        qualified_sha=QUALIFIED_SHA,
        baseline_uptime_ms=baseline.uptime_ms,
        transition_uptime_ms=transition.uptime_ms,
        power_before_median_w=before_median,
        power_after_median_w=after_median,
        power_delta_w=delta,
    )


def load_ndjson(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text().splitlines(), start=1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise QualificationContractError(f"invalid NDJSON line {line_number}: {exc}") from exc
        if not isinstance(payload, dict):
            raise QualificationContractError(f"NDJSON line {line_number} is not an object")
        records.append(payload)
    return records


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--telemetry", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()
    records = load_ndjson(args.telemetry)
    evidence = json.loads(args.evidence.read_text())
    if not isinstance(evidence, dict):
        raise QualificationContractError("evidence JSON must be an object")
    result = replay_qualification(records, evidence)
    print(
        "OUTPUT_SUPERVISOR_H_REPLAY_PASS "
        f"sha={result.qualified_sha} "
        f"baseline_uptime_ms={result.baseline_uptime_ms} "
        f"transition_uptime_ms={result.transition_uptime_ms} "
        f"power_delta_w={result.power_delta_w:.3f} hardware_started=0"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
