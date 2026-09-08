# Execution Architecture Handoff

Updated: 2026-09-09
Repository: `MichalMatu/growbox-ml-controller`
Work branch: `mvp/environment-controller`
Control branch: `agent-control`
Local Agent binding: `815cf40f-8d2a-4e1f-b7cc-c0f4e37b6cb5`
Authoritative design: `docs/OUTPUT_EXECUTION_ARCHITECTURE.md`
Implementation plan: `docs/OUTPUT_EXECUTION_IMPLEMENTATION_PLAN.md`

## Current state

The OutputSupervisor migration is software-stabilized through A12.2.

Software-qualified executable SHA:

`1c59f3cfa239abbfbae721247d01d65a39d4bdfc`

Terminal full-gate evidence:

`20260909-output-a12-2-final-full-software-gate-v8`

The final full gate passed Python software tests, all 49 host C++ tests, lint/format/schema/pre-push checks, fake-output and real-output software-only firmware builds, RF-enabled main-stack evidence, and the output/RF ownership invariant. It recorded `main_stack=16384`, `runtime_frame=32`, `firmware_bin=771888`, and `hardware_started=0`.

The current branch may contain later documentation/tooling commits. Those later commits do not replace the exact A12-qualified executable identity unless production source is changed and requalified.

## Required architecture invariant

> `OutputSupervisor` is the only normal production owner allowed to execute configured physical outputs.

The qualified architecture establishes:

- climate, schedule and normal manual paths produce intents;
- safety produces constraints/forced actions through `SafetyEnvelope` and does not transmit;
- `OutputSupervisor` resolves normal execution;
- `BinaryActuatorPolicy` owns binary hysteresis/dwell only;
- `Rf433OutputTransport` performs transport only;
- `OutputStateStore` records command truth without fabricating physical acknowledgement;
- raw RF TX is a maintenance capability available only through explicit `MaintenanceLocked` handling;
- the repository ownership guard must reject any new hidden configured-output writer.

## Historical H evidence

Do not delete or rewrite historical H evidence, but do not execute the old H v8 workflow.

Historical facts retained for reference:

- formal Phase G exit: `7ddb995d1f6cd190fa110f21f0d8dc0eabc61d26`;
- old pre-architecture production identity: `5a4830db9d10e8cb73d4c617b09122f0844ad899`;
- old TimerOff-aware observer commit: `45065a34ce276ac5cdb7ef8cf0a1ad8a4bae1b0d`;
- old H v8 software preflight: `20260908-stage28e-h-v8-preflight-v1` PASS on `231eed28f64bdbdc4238fd8bce128264027702f2`;
- old H v8 hardware execution never started.

Those identities and tools are historical only because they predate the OutputSupervisor architecture.

## A13.1 — new OutputSupervisor H qualification contract

A13.1 is the active task.

Create a new qualification plan/tool contract for the A12-qualified identity. It must not reuse the historical H v8 observer as-is.

The normal transition proof must follow the new architecture:

```text
natural climate ControlIntent
-> OutputSupervisor input/resolution
-> BinaryActuatorPolicy eligibility
-> OutputPlan command
-> RF433OutputTransport TxResult
-> independent Shelly aggregate-power support
-> environmental response support
```

The observer contract must consume telemetry v2 and distinguish:

- supervisor mode;
- automation request state;
- control/schedule/manual intent activity;
- safety envelope and safety reason;
- selected source/reason;
- resolved command and dwell hold;
- command attempted this cycle;
- attempted command source/reason;
- transport status/error;
- last-commanded state;
- physical observation state and whether it is independently supported.

A valid normal-control qualification transition must prove at minimum:

1. exact production identity is `1c59f3cfa239abbfbae721247d01d65a39d4bdfc`;
2. supervisor mode is `Automatic`;
3. `MaintenanceLocked` is not active;
4. the fan control intent is natural climate intent, not injected test/manual intent;
5. no active hard-safety override caused the counted normal transition;
6. the fan target becomes eligible through binary policy rather than bypassing dwell/hysteresis accounting;
7. an OutputSupervisor-owned command attempt is observed for the fan endpoint;
8. `TxResult` is `Completed` with no transport error;
9. one-way RF TX is treated only as transport completion, not physical acknowledgement;
10. independent Shelly total-power evidence is temporally compatible with the fan transition and is not confounded by lamp/humidifier state changes;
11. post-transition environmental evidence is collected as supporting evidence;
12. no unexpected transport errors occur during the bounded proof;
13. recovery/final safe state is supervisor-owned.

A13.1 is documentation/tooling only. It must not open serial, flash, transmit RF, or touch hardware.

## A13.2 — software-only H preflight

After A13.1 is committed, run a new software-only preflight against the exact A12-qualified executable identity and the new H tooling.

The preflight may:

- parse/replay committed telemetry fixtures;
- exercise observer state transitions with synthetic records;
- run focused Python/tool tests;
- compile/build the exact qualified source identity if needed for identity evidence.

It must not:

- open serial;
- probe USB;
- flash;
- transmit RF;
- access Shelly or other physical hardware;
- run the historical H v8 observer;
- start physical qualification.

The terminal result must include `hardware_started=0`.

## Mandatory stop after A13.2

After A13.2 PASS, stop before hardware.

Do not begin physical H until the operator explicitly authorizes it.

Only after that explicit authorization may a future hardware task use:

`/dev/cu.usbserial-1130`

Never touch:

`/dev/cu.usbserial-10`

Any future hardware task must verify the correct port internally, explicitly reject the forbidden port, use `resources: []`, verify the exact qualified firmware identity, remain bounded, preserve all safety invariants, and restore/prove the defined safe final state.

## Safety invariants

- deterministic rule controller remains authoritative;
- ML remains shadow/research-only;
- thermal trip remains `>=28 C`;
- thermal recovery remains `<=26 C` continuously for 10 minutes;
- safety remains active while automation is disabled;
- one-way RF never implies physical acknowledgement;
- Shelly master remains ON during future bounded qualification;
- no raw RF TX outside `MaintenanceLocked`;
- no hidden output owner outside `OutputSupervisor`.

## Local Agent contract

Every Local Agent task must contain exactly:

```json
{
  "agent_binding": "815cf40f-8d2a-4e1f-b7cc-c0f4e37b6cb5",
  "work_branch": "mvp/environment-controller",
  "resources": []
}
```

Do not declare named resources or `machine`. Verify exact SHA in-task whenever source identity matters and read terminal `.agent/results/<task-id>.json` before reporting PASS.
