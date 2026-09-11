# Output Execution Architecture

Status: DESIGN BASELINE — implementation not started
Updated: 2026-09-08
Repository: `MichalMatu/growbox-ml-controller`
Work branch: `mvp/environment-controller`
Architecture-pause entry baseline: `157806442161e88edd8038e532e9dff333a19efb`

## Decision

Stage28E Phase H physical qualification is intentionally suspended before H v8. The project will first correct output-execution ownership and safety architecture. This is a deliberate production-architecture decision, not a workaround for the qualification harness.

No Phase H hardware run, actuator experiment, firmware flashing, or new physical-output qualification is authorized by this document.

The architectural invariant is:

> Exactly one production component owns physical output execution. Climate control, schedules, safety logic, manual commands, recovery logic, and diagnostics may request or constrain output behavior, but they do not transmit to physical outputs directly.

The target owner is `OutputSupervisor`.

## Why the current architecture needs correction

The current implementation has useful pieces but distributes execution authority across several layers:

- `ClimateRuntimeController` and `ClimateControlLoop` produce climate decisions and currently drive an actuator sink.
- `ClimateActuatorAdapter`, `Stage28dBinaryRoleArbiter`, and `MappedClimateRoleDriver` form the normal climate-output path.
- `Stage28dRfOutputEndpoint` combines RF endpoint execution, cached endpoint state, initialization behavior, and a safety-force flag.
- `LampSafetyController` makes lamp/fan safety decisions outside the normal climate decision path.
- service-console RF diagnostics can address RF behavior through a separate operational path.
- `Stage28RfDiagnostics` auto-smoke is another direct RF transmit path when enabled; it must be treated as maintenance/transport diagnostics rather than a production output owner.
- qualification/recovery tooling contains lifecycle output behavior such as fan OFF, humidifier OFF, lamp ON/fake-locked restoration.
- fail-safe semantics are not represented by one common policy: ordinary fail-safe OFF, thermal lamp OFF + fan ON, startup safe-state initialization, and recovery behavior are distinct mechanisms.

This makes output ownership harder to reason about and makes `automation OFF`, safety, recovery, startup, and manual behavior unnecessarily coupled to specific call paths.

## Goals

1. One physical-output owner in production.
2. Clean separation between decision, safety constraints, execution policy, transport, persistence, and telemetry.
3. Keep the climate engine able to calculate in observe-only mode while automation execution is disabled.
4. Make lifecycle output behavior data-driven and configurable per endpoint rather than hard-coded in recovery scripts or scattered branches.
5. Preserve safety authority independently of whether automation is enabled.
6. Make RF transport intentionally dumb: transport sends commands and reports transport results; it does not decide safety or lifecycle behavior.
7. Represent stored state honestly for one-way RF: last commanded state is not physical acknowledgement.
8. Make manual/service-console commands pass through the same execution authority as automatic commands.
9. Allow future transports and feedback mechanisms without rewriting control policy.
10. Enable host-level verification of execution decisions before returning to hardware qualification.

## Non-goals for the first architecture pass

- changing AH thresholds or climate-control semantics;
- changing ML authority; ML remains shadow/research-only;
- intentionally triggering thermal safety on hardware;
- building a generic home-automation framework;
- adding a new transport before RF433 ownership is clean;
- treating RF transmit success as proof that a physical load changed state;
- continuing H v8 with the old production identity after production C++ changes.

## Target data flow

```text
Sensors / targets / schedule
          |
          v
+-------------------------+
| Climate decision engine |
| ControlIntent producer  |
+------------+------------+
             |
             | ControlIntent (observe-only when disabled)
             v
+-------------------------+        +-------------------------+
| SafetyPolicyEngine      |        | Schedule / Manual       |
| constraints only        |        | intent producers        |
+------------+------------+        +------------+------------+
             |                                  |
             +------------------+---------------+
                                v
                    +-------------------------+
                    | OutputSupervisor        |
                    | single execution owner  |
                    | mode + policy + state   |
                    +------------+------------+
                                 | OutputPlan
                                 v
                    +-------------------------+
                    | OutputTransport         |
                    | RF433 adapter initially |
                    +------------+------------+
                                 | TxResult
                    +------------+------------+
                    |                         |
                    v                         v
             OutputStateStore          Telemetry / audit
```

## Core contracts

### `ControlIntent`

Represents what the climate engine would like to do. It is not permission to touch hardware.

Required properties:

- semantic roles, not RF frame knowledge;
- normalized requested levels where appropriate;
- source cycle/sequence and monotonic timestamp;
- valid even while automation execution is disabled so diagnostics can show what the controller would have requested.

### `ScheduleIntent`

Represents schedule-driven behavior such as lamp demand. Schedule production must not transmit directly.

### `ManualIntent`

Represents an operator/service request for a semantic role or endpoint. Manual intent is subject to supervisor mode, safety policy, and authorization. Normal manual device control must not bypass the supervisor.

### `SafetyEnvelope`

Represents constraints and forced actions, not output writes. A safety rule can express, per protected role/endpoint:

- `Allow`;
- `ForceOff`;
- `ForceOn`;
- `Inhibit`;
- reason code;
- latch/recovery state;
- evidence timestamp/age.

Safety evaluation must be testable without a transport.

### `OutputPolicyConfig`

Versioned, validated policy defining lifecycle behavior per endpoint. It includes endpoint-role binding and lifecycle actions. Policy is data; transport code does not own it.

### `OutputPlan`

A complete resolved execution plan produced before transport calls. Each step identifies endpoint, desired command, reason/source, ordering, and any bounded delay.

### `ExecutionReport`

Records what the supervisor resolved and what the transport actually reported. It must distinguish requested, resolved, commanded, transport-success, and physical-observation concepts.

## Supervisor state machine

The public product control may remain simple (`automation ON/OFF`), but execution needs explicit internal states. Initial design target:

```text
BootLocked
   | enable
   v
Arming ------ failure ------> FaultLocked
   | success
   v
Automatic
   | disable
   v
Recovering --- failure -----> FaultLocked
   | success
   v
Disabled
```

`Disabled` does not stop the climate engine from calculating. It stops normal control intent from being executed. Safety remains active.

`FaultLocked` is an execution state, not a claim that every load is physically OFF. The state store must record what commands were attempted and what is unknown.

A later audit may simplify or rename states, but the following distinctions must remain explicit:

- boot/unknown physical state;
- automatic execution enabled;
- automatic execution disabled;
- transition/recovery in progress;
- execution fault requiring containment.

## Resolution precedence

The supervisor resolves output behavior in a documented order. Initial precedence target:

1. non-bypassable hard safety constraints;
2. fault-containment policy;
3. lifecycle transition policy (`Boot`, `AutomationDisabled`, `Recovery`);
4. authorized manual intent;
5. schedule intent;
6. climate control intent;
7. no-command/hold behavior.

The audit must confirm whether schedule and manual precedence need role-specific exceptions. Any exception must be explicit policy, not hidden call ordering.

## Safety architecture

`SafetyPolicyEngine` owns safety decisions. It does not own transport.

The existing thermal lamp behavior is migrated conceptually as:

```text
normal schedule + safe temperature
  -> lamp allowed according to schedule

overtemperature / unusable temperature / invalid safety config
  -> lamp ForceOff
  -> exhaust ForceOn when the protected exhaust path is available
  -> reason + latch/recovery metadata
```

The `OutputSupervisor` consumes this envelope. A binary actuator policy may bypass normal minimum-OFF dwell when processing a safety `ForceOn`, but the bypass is a documented execution rule rather than a safety flag embedded in the RF endpoint.

Ordinary `automation OFF` configuration must not silently disable non-bypassable thermal protection. If later product requirements allow a safety rule to be disabled, that must be a separately validated safety configuration with explicit constraints, not an incidental output-policy option.

## Output lifecycle policy

The supervisor must support explicit per-endpoint actions for lifecycle events. Minimal action set:

```cpp
enum class OutputPolicyAction {
  NoCommand,
  ForceOff,
  ForceOn,
  ApplySchedule,
  RestoreLastCommand,
};
```

Each lifecycle action may include bounded execution metadata such as:

- `order`;
- `delay_ms`;
- whether a command must be retransmitted even when cached last-commanded state matches;
- timeout/failure handling.

Delays must be non-blocking at the supervisor level.

Example product policy, illustrative rather than hard-coded architecture:

| Endpoint role | Boot | Automation OFF | Recovery | Fault |
|---|---|---|---|---|
| Exhaust fan | ForceOff | ForceOff | ForceOff | ForceOff |
| Lamp | ApplySchedule | ApplySchedule | ForceOn | ForceOff |
| Humidifier | ForceOff | ForceOff | ForceOff | ForceOff |

The actual safe defaults must be reviewed during the architecture audit before implementation.

This directly supports the product requirement that disabling automation can choose **which sockets receive OFF/ON/no command and when**.

## Binary actuator policy

Current binary hysteresis/dwell behavior is valuable but should become an execution-policy component instead of a downstream driver with hardware knowledge.

Target responsibilities:

- normalized-level thresholding;
- ON/OFF hysteresis;
- minimum ON/OFF dwell;
- held-state reporting;
- explicit override semantics for safety/lifecycle actions.

It must not:

- transmit RF;
- own endpoint mapping;
- evaluate temperature safety;
- persist configuration;
- decide global automation mode.

## Transport contract

Initial transport is RF433. Target interface is intentionally narrow, conceptually:

```cpp
TxResult send(const OutputCommand& command) noexcept;
```

Transport responsibilities:

- map a validated endpoint command to the configured RF frame/hardware operation;
- attempt transmission;
- report deterministic transport result/counters.

Transport must not:

- decide lamp/fan safety;
- decide automation enable/disable;
- perform recovery policy;
- own dwell/hysteresis;
- claim physical acknowledgement for one-way RF.

`Stage28dRfOutputEndpoint` should therefore be split rather than expanded.

## State and persistence

There are two different kinds of state and they must not be conflated.

### Durable configuration

Versioned `OutputPolicyConfig` and endpoint-role bindings are durable configuration. The A0 audit found no existing product configuration/state store suitable for this data: project code initializes NVS for platform/BLE use, RTC no-init storage is diagnostic-only, and Stage27 SD/flash storage is append-only telemetry rather than a settings store. A6 may therefore introduce exactly one versioned output configuration/state store (NVS is the natural first candidate) instead of repurposing telemetry storage. If a suitable product configuration store is added elsewhere before A6, reuse it rather than creating a second one.

### Runtime / command state

For one-way RF, the state model must distinguish at least:

- desired/resolved state;
- last command attempted;
- last transport result;
- last command timestamp/sequence;
- physical state `Unknown` unless independent evidence exists.

Persisting `last_commanded=ON` must never be represented as `physical_state=ON`.

At boot, physical state begins unknown. Boot policy decides whether to resend an explicit state, apply schedule, restore the last command, or issue no command.

Flash/NVS writes must be bounded to meaningful transitions; do not write every control tick.

## Optional physical feedback

Physical feedback is separate from transport acknowledgement. A future `OutputFeedbackProvider` may provide endpoint-specific or aggregate evidence. Current Shelly total-power evidence is useful but can be confounded by multiple loads, so it must not silently become endpoint acknowledgement.

## Failure semantics

A transport failure must not be converted into a fabricated OFF state. The supervisor should:

1. record the failed command and uncertainty;
2. apply the configured containment/retry policy;
3. enter `FaultLocked` when execution truth cannot be maintained;
4. preserve safety evaluation;
5. expose the fault through telemetry/service status.

Whether a retry is appropriate depends on the command, transport, and lifecycle event and must be bounded.

## Service console and diagnostics

Normal service-console commands for configured outputs must become requests to `OutputSupervisor`.

Low-level RF diagnostics may remain only as an explicitly separate maintenance/transport-test capability. The architecture audit must decide its exact guard, but it may not be an invisible second production owner of the same outputs. A likely requirement is a dedicated maintenance-locked mode with normal automatic execution disabled and safety implications made explicit.

## Telemetry contract

For each execution cycle/transition, diagnostics should be able to distinguish:

- controller-requested level;
- schedule request;
- manual request;
- safety envelope/reason;
- supervisor mode;
- policy action;
- binary/dwell resolution;
- final output command;
- transport result;
- last-commanded state;
- physical observation/confidence if available.

This avoids using one field such as `fan_on` to mean requested, commanded, cached, and physically confirmed state.

## Migration map from current classes

| Current component | Target treatment |
|---|---|
| `ClimateRuntimeController` | Retain as climate decision engine; no RF/lifecycle ownership |
| `ClimateControlLoop` | Audit/split so decision production is separable from execution; physical fail-safe ownership moves to supervisor |
| `ClimateActuatorAdapter` | Reduce to intent translation or retire after decision/execution split |
| `Stage28dBinaryRoleArbiter` | Extract/rename as binary actuator policy; remove transport and embedded safety ownership |
| `MappedClimateRoleDriver` | Absorb mapping into validated output configuration/resolution or retire |
| `Stage28dRfOutputEndpoint` | Split into RF433 transport plus supervisor-owned command state |
| `LampSafetyController` | Preserve safety logic, adapt output to `SafetyEnvelope`; no output writes |
| `Stage28ServiceConsole` | Route normal output commands through supervisor; separate maintenance diagnostics |
| `ClimateV6RealInputRuntime` | Become a composition root/orchestrator with narrow module ownership, not a policy owner |
| H/recovery scripts | Remain qualification tooling; product lifecycle behavior moves into firmware policy |

## Implementation sequence after audit

The first new-chat task is an audit, not a rewrite. After the audit is accepted, use small coherent commits:

1. **A0 — execution-ownership audit**: enumerate every path capable of changing an output, state owners, safety paths, persistence, schedule/manual paths, and failure semantics. No behavior change.
2. **A1 — contracts/types**: add narrow intent/envelope/plan/report types and host tests without changing production execution.
3. **A2 — RF transport split**: extract dumb transport from endpoint state/policy while preserving behavior.
4. **A3 — safety envelope**: adapt thermal safety to produce constraints; remove direct transport knowledge from safety.
5. **A4 — OutputSupervisor core**: introduce mode/state machine, resolver, lifecycle policy, binary actuator policy integration, and deterministic execution reports.
6. **A5 — climate integration**: make climate decisions feed `ControlIntent`; reconcile confirmed executed control projection without giving the climate loop transport ownership.
7. **A6 — persistence/configuration**: add versioned output policy and honest command-state persistence in exactly one suitable store; reuse an existing product configuration store only if one exists by then.
8. **A7 — console/diagnostics migration**: remove normal direct output bypasses; separate maintenance transport diagnostics.
9. **A8 — legacy removal and invariant enforcement**: remove duplicated safety/output state and prove one production output owner.
10. **A9 — software qualification**: focused tests during each change, then one full software gate after the architecture stabilizes.
11. **A10 — new hardware qualification**: only after explicit authorization; create a fresh qualification identity and plan. The old H v8 preflight does not qualify changed production C++.

Do not combine these into one giant rewrite.

## Architecture audit checklist

The next chat must inspect the repository and answer, with exact file/symbol evidence:

- every function/class that can directly or indirectly send RF/output commands;
- every owner/copy of output state;
- every safety override and fail-safe path;
- all startup, disable, recovery, and fault output actions;
- all schedule-driven output paths;
- all manual/service-console output paths;
- endpoint-role mapping ownership and validation;
- persistence mechanism(s) already used for settings/state;
- concurrency/task context of control, safety, service console, and RF execution;
- where `reconcileApplied` and previous-action state should live after the split;
- all tests coupled to the current actuator-driver chain;
- whether any raw RF diagnostic path must remain and under which maintenance guard;
- whether current telemetry distinguishes requested/resolved/commanded/observed states;
- expected memory/stack impact of the new supervisor and policy objects.

The audit should produce `docs/OUTPUT_EXECUTION_ARCHITECTURE_AUDIT.md` before production behavior is changed.

## Acceptance criteria before hardware qualification resumes

- exactly one normal production owner can execute configured outputs;
- safety is represented as constraints/forced policy, not a second transport path;
- automation OFF has explicit per-output lifecycle policy and timing;
- climate engine can continue observe-only computation while execution is disabled;
- startup/recovery/fault behavior is explicit and testable;
- binary dwell/hysteresis is isolated from RF and safety evaluation;
- RF transport is free of product safety/mode policy;
- persisted state does not overclaim physical truth;
- service-console normal output commands cannot bypass the supervisor;
- host tests cover precedence, state transitions, lifecycle policy, transport failures, safety override behavior, and persistence semantics;
- one full software gate passes on the final architecture;
- a new exact firmware identity is recorded before any renewed physical qualification.

## Impact on Stage28E Phase H

H remains formally open but suspended. H v8 was prepared and never started. Its software preflight and older qualified production identity remain historical evidence only.

Once production C++ changes for this architecture, do not describe `5a4830db9d10e8cb73d4c617b09122f0844ad899` or H v8 preflight `231eed28f64bdbdc4238fd8bce128264027702f2` as qualifying the new firmware. A fresh software qualification and a new bounded physical plan are required.

The existing H observer/scripts should be retained unless the architecture audit identifies a clear obsolete assumption. Do not run them during the architecture audit.
