# Stage28E OutputSupervisor Phase H Qualification

Status: A13.1 SOFTWARE CONTRACT
Updated: 2026-09-09
Repository: `MichalMatu/growbox-ml-controller`
Work branch: `mvp/environment-controller`
A12 software-qualified executable SHA: `1c59f3cfa239abbfbae721247d01d65a39d4bdfc`
Historical H v8: frozen; do not execute
Hardware authorization: NOT GRANTED

## 1. Purpose

This document replaces the historical Phase H v8 observer contract for the OutputSupervisor architecture.

The qualification goal is to prove one natural fan OFF->ON transition through the production execution chain without treating one-way RF transmission as physical acknowledgement:

```text
natural climate ControlIntent
-> OutputSupervisor resolution
-> BinaryActuatorPolicy eligibility
-> OutputPlan fan ON command
-> Rf433OutputTransport TxResult
-> independent Shelly aggregate-power support
-> environmental response support
```

`OutputSupervisor` remains the only normal production owner allowed to execute configured physical outputs.

## 2. Qualified software identity

Only this exact executable source identity is qualified by A12.2:

`1c59f3cfa239abbfbae721247d01d65a39d4bdfc`

Terminal A12.2 evidence:

`20260909-output-a12-2-final-full-software-gate-v8`

A later docs/tooling commit does not change this executable identity. Any production-source change after this identity requires new software qualification before hardware H can resume.

## 3. Telemetry contract

The observer consumes `growbox-log-v3` records with output telemetry version `out_v=2` / `out.v=2`.

The compact output object fields are:

- `m`: `SupervisorMode`;
- `ta`: transport active;
- `la`: lifecycle execution active;
- `le`: lifecycle event;
- `ae`: automation requested;
- `sl`: safety latched;
- `sr`: aggregate safety reason;
- `ep`: fixed endpoint telemetry arrays.

For each endpoint array, the observer uses these positions:

| Index | Meaning |
|---:|---|
| 0 | endpoint id |
| 1 | control intent active |
| 2 | control intent level |
| 3 | schedule intent active |
| 5 | manual intent active |
| 7 | safety constraint active |
| 10 | selected |
| 11 | selected level |
| 12 | selected source |
| 13 | selected reason |
| 14 | resolved |
| 15 | resolved binary state |
| 16 | held by dwell |
| 17 | safety override |
| 18 | inhibited |
| 19 | command attempt known |
| 20 | attempted this cycle |
| 21 | attempted binary state |
| 22 | attempt source |
| 23 | attempt reason |
| 24 | transport status |
| 25 | transport error |
| 26 | last command known |
| 27 | last commanded binary state |
| 28 | last command source |
| 29 | last command reason |
| 30 | physical state |
| 31 | physical state independently supported |

Current fixed endpoint identities are:

- `1`: exhaust fan / RF socket 1;
- `2`: scheduled lamp / RF socket 2;
- `3`: humidifier / RF socket 3.

Important enum values used by the replay contract:

- `SupervisorMode::Automatic = 2`;
- `SupervisorMode::MaintenanceLocked = 6`;
- `OutputSource::Climate = 1`;
- `OutputReason::ClimateDecision = 1`;
- `BinaryOutputState::Off = 0`, `On = 1`;
- `TransportStatus::Completed = 1`, `Failed = 2`;
- `TransportError::None = 0`;
- `PhysicalOutputState::Unknown = 0`.

## 4. Normal fan transition acceptance contract

The counted fan transition must satisfy all of the following.

### 4.1 Session identity

- session schema is `growbox-log-v3`;
- session advertises output telemetry v2;
- session firmware identity equals the A12-qualified SHA exactly.

### 4.2 Supervisor state

For the baseline and counted transition:

- supervisor mode is `Automatic`;
- automation is requested;
- `MaintenanceLocked` is not active;
- lifecycle execution is not active during the counted normal transition.

### 4.3 Clean OFF baseline

Before the counted transition, fan endpoint 1 must show:

- no active hard-safety constraint/override/inhibit;
- no manual intent;
- resolved state OFF;
- last-commanded state known and OFF;
- no transport error.

Independent physical fan-OFF support for the eventual hardware run is established separately by the Shelly power baseline; command state alone is not physical acknowledgement.

### 4.4 Natural climate fan ON transition

The counted transition must show:

- no aggregate safety latch;
- no fan safety constraint, safety override or inhibit;
- no manual intent;
- active fan climate control intent with positive requested level;
- selected source `Climate` and reason `ClimateDecision`;
- resolved fan state ON;
- `held_by_dwell=0` for the counted command cycle;
- command attempt known and attempted this cycle;
- attempted state ON;
- attempt source `Climate`, reason `ClimateDecision`;
- transport status `Completed`;
- transport error `None`;
- last-commanded state known and ON with climate source/reason;
- transport active for the counted command.

A command transmitted because of `Safety`, `Manual`, `Lifecycle` or `Maintenance` is not a valid normal-control Phase H transition.

### 4.5 Global transport cleanliness

No configured endpoint may report an unexpected transport error or `Failed` transport status during the analyzed proof window.

## 5. Honest physical-state semantics

One-way RF transport success means only that the transmit operation completed.

The observer must reject telemetry that claims a physical ON/OFF state while `physical_independent=0`.

Without an independent feedback provider, the firmware physical state remains `Unknown`. Shelly aggregate power is external supporting evidence and must not be written back as per-endpoint RF acknowledgement.

## 6. Independent supporting evidence

The future bounded hardware observer must collect independent evidence around the counted fan transition.

### 6.1 Shelly power support

Requirements:

- Shelly master remains ON;
- at least three stable power samples exist before the counted transition;
- at least three power samples exist after the counted transition;
- lamp state does not change across the proof window;
- humidifier state does not change across the proof window;
- post-transition median power minus pre-transition median power meets a reviewed positive minimum threshold.

The threshold is an explicit qualification parameter, not a hidden constant. It must be reviewed before hardware authorization.

### 6.2 Environmental response support

A bounded post-transition environmental window must provide supporting evidence consistent with increased exhaust airflow. The exact acceptance metric/window must be frozen before the hardware task is authorized and must not weaken thermal safety.

Environmental response is supporting physical evidence, not a substitute for the supervisor/transport telemetry chain.

## 7. Recovery and final state

The eventual physical H task must make recovery/final-state execution supervisor-owned.

The qualification wrapper must:

- execute a bounded supervisor lifecycle/recovery transition;
- reject unexpected transport failures;
- restore/prove the reviewed safe final state;
- never use raw RF TX as recovery outside `MaintenanceLocked`;
- preserve hard thermal safety throughout recovery.

Historical H v8 recovery commands are not automatically valid for this architecture and must not be reused without review.

## 8. A13.1 software tooling

`tools/output_supervisor_h.py` is the software-only replay implementation of this contract.

It:

- parses committed/captured `growbox-log-v3` NDJSON records;
- verifies the exact A12 firmware identity;
- validates the OutputSupervisor-owned natural fan transition;
- rejects safety/manual/maintenance ownership;
- rejects transport errors;
- rejects fabricated physical acknowledgement;
- validates independent-evidence metadata supplied as JSON;
- never opens serial;
- never probes USB;
- never accesses Shelly/network hardware;
- never flashes;
- never transmits RF.

Focused tests live in `tests/test_output_supervisor_h.py`.

## 9. A13.2 software-only preflight

A13.2 must run on the Mac through Local Agent with:

```json
{
  "agent_binding": "815cf40f-8d2a-4e1f-b7cc-c0f4e37b6cb5",
  "work_branch": "mvp/environment-controller",
  "resources": []
}
```

The preflight must verify:

1. current branch ancestry contains exact A12-qualified executable SHA;
2. no production C/C++ source changed after the qualified SHA unless a new A12 full qualification exists;
3. the replay tool and focused tests pass;
4. a positive synthetic replay produces the expected PASS marker;
5. negative cases reject wrong SHA, manual/safety ownership, transport errors and fabricated physical acknowledgement;
6. repository formatting/lint for the new A13.1 files passes;
7. no serial, USB, flash, network hardware or RF command is executed;
8. final marker includes `hardware_started=0`.

A13.2 is not hardware qualification.

## 10. Mandatory stop

After A13.2 PASS, stop and wait for explicit operator authorization.

Do not tell the operator to connect the ESP32 before that explicit authorization step.

When hardware is later explicitly authorized, only this Growbox serial port may be used:

`/dev/cu.usbserial-1130`

Never touch:

`/dev/cu.usbserial-10`
