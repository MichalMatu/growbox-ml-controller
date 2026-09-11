# Output Execution Implementation Plan

Status: PRE-EXECUTION PLAN — READY FOR LOCAL CHAT BRIDGE AFTER FINAL RE-AUDIT
Updated: 2026-09-08
Repository: `MichalMatu/growbox-ml-controller`
Work branch: `mvp/environment-controller`
Control branch: `agent-control`
Local Agent repository id: `growbox-ml-controller`
Local Agent binding: `815cf40f-8d2a-4e1f-b7cc-c0f4e37b6cb5`
Plan baseline HEAD: `d11b6de703421ff678789bdcfcea876fc902733d`
Architecture: `docs/OUTPUT_EXECUTION_ARCHITECTURE.md`
Audit: `docs/OUTPUT_EXECUTION_ARCHITECTURE_AUDIT.md`

## 1. Purpose

This document turns A1-A13 into small, independently testable, commit-sized steps.

The implementation goal is not a giant rewrite. Each step must preserve a comparable system state, run the narrowest meaningful verification, and commit only after that verification passes. A failed step stops the sequence until the defect is understood and fixed in the same stage.

The final production invariant is:

> `OutputSupervisor` is the only normal production owner allowed to execute configured physical outputs.

The target separation remains:

```text
Climate engine -> ControlIntent
Schedule/manual -> Intent
SafetyPolicyEngine -> SafetyEnvelope
OutputPolicyConfig -> lifecycle policy
BinaryActuatorPolicy -> hysteresis + dwell
OutputSupervisor -> resolve + plan + execute
RF433OutputTransport -> transmission only
OutputStateStore -> command truth, never fabricated physical acknowledgement
```

## 2. Non-negotiable execution constraints

Until A13 reaches the explicit hardware-authorization stop gate:

- do not run H v8;
- do not flash hardware;
- do not open serial;
- do not transmit RF;
- do not run physical-output tests;
- do not touch `/dev/cu.usbserial-1130` during software architecture work;
- never touch `/dev/cu.usbserial-10` under any circumstance;
- old firmware identity `5a4830db9d10e8cb73d4c617b09122f0844ad899` and old H v8 preflight identity `231eed28f64bdbdc4238fd8bce128264027702f2` remain historical evidence only.

When Local Chat Bridge is enabled, every Local Agent task must use:

```json
{
  "agent_binding": "815cf40f-8d2a-4e1f-b7cc-c0f4e37b6cb5",
  "work_branch": "mvp/environment-controller",
  "resources": []
}
```

Do not use named resources. Do not use `machine`.

## 3. Commit and verification discipline

### 3.1 One step = one bounded commit

Default rule:

1. fresh-check exact HEAD;
2. make only the step's bounded change;
3. run the listed focused gate;
4. inspect diff and tree cleanliness;
5. commit with an English commit message;
6. record the resulting SHA;
7. fresh-check branch HEAD before the next step.

A step may remain uncommitted while fixing its own failed focused tests, but unrelated follow-up work must not be folded into it.

### 3.2 Verification levels

- Pure types/contracts: compile + focused host tests.
- Pure policy/state logic: focused host tests.
- ESP-specific wiring: focused host tests for abstractions plus an ESP-IDF compile/build check.
- Runtime composition changes: focused climate/output tests plus ESP-IDF build.
- Persistence: host codec/store tests plus ESP-IDF build.
- Console: parser/guard tests plus ESP-IDF build.
- Full repository/software gate: exactly once, in A12 after the architecture is stable.

Do not run `make check-push` after every commit.

### 3.3 Focused host command pattern

Use the existing host harness where possible:

```bash
cmake -S test/host -B build/host-tests
cmake --build build/host-tests --parallel --target <focused-target>
ctest --test-dir build/host-tests -R '^<focused-test>$' --output-on-failure
```

If an existing Stage28D standalone C++ test is not registered in `test/host/CMakeLists.txt`, register it first rather than relying on an undocumented ad-hoc compiler invocation.

### 3.4 Firmware build checkpoints

Use the current repository's canonical ESP-IDF build scripts and the same real/fake software build profiles used by the latest frozen H preflight as build configuration evidence only. Do not treat the old PASS as qualification of changed C++.

At every ESP-specific checkpoint record:

- exact SHA;
- build profile;
- static DRAM / `.data` / `.bss` deltas where available;
- binary size delta;
- configured main-task stack;
- no hardware started.

The architectural implementation should remain single-task synchronous initially; do not create a new supervisor task unless evidence later proves it necessary.

## 4. Decisions frozen for implementation planning

These decisions are required to keep the sequence deterministic.

### 4.1 Climate safety boundary

Do not move every function named `safety` into `SafetyPolicyEngine`.

The current `ClimateRuntimeController::safety()` remains part of climate-policy request sanitation unless a rule is explicitly reclassified later. The non-bypassable Stage28D lamp/thermal protection is the first `SafetyEnvelope` producer.

### 4.2 Initial supervisor execution context

`OutputSupervisor` runs synchronously from the existing main control task. Intent producers never call transport. Future cross-task producers must queue/snapshot intents into that owner.

### 4.3 Initial endpoint set

Keep fixed-size storage for the currently validated physical set:

- exhaust fan / RF socket 1;
- scheduled lamp / RF socket 2;
- humidifier / RF socket 3.

Do not add dynamic containers or generic heap allocation to the hot path.

### 4.4 Initial lifecycle defaults

These are conservative initial production defaults unless the operator explicitly changes them before A8 is implemented:

| Endpoint | Boot | Automation OFF | Recovery | Fault |
|---|---|---|---|---|
| Lamp | `ForceOff` | `ApplySchedule` | `ForceOff` | `ForceOff` |
| Exhaust fan | `ForceOff` | `ForceOff` | `ForceOff` | `ForceOff` |
| Humidifier | `ForceOff` | `ForceOff` | `ForceOff` | `ForceOff` |

Hard safety has higher precedence than these lifecycle actions. Therefore a valid non-bypassable thermal `ForceOff` for lamp / `ForceOn` for exhaust can override lifecycle output choices.

`RestoreLastCommand` is supported by the policy model but is not a default action.

Startup command order initially preserves current code order: lamp, exhaust fan, humidifier, with zero configured delay unless a later reviewed policy says otherwise.

### 4.5 One-way RF truth

A completed RF transmission means command transport completed. It never means the socket physically changed state.

Persisted or runtime state must distinguish:

- desired;
- resolved;
- command attempted;
- command completed/failed at transport;
- physical state `Unknown` unless independent feedback exists.

Shelly aggregate power remains evidence/telemetry, not endpoint acknowledgement.

### 4.6 Maintenance diagnostics

Passive RF receive may remain available outside maintenance mode because it does not transmit.

Raw RF transmit is a maintenance capability, not a production output owner. It must require explicit `MaintenanceLocked` mode, a safe entry transition, and an explicit re-arm/exit transition. Hard safety may veto a raw command to a protected configured endpoint.

Auto-smoke TX must not remain an invisible boot-time production bypass.

---

# 5. P0 — execution preflight and focused-test harness

P0 happens only after Local Chat Bridge is enabled.

## P0.1 — fresh execution identity

**Change:** none.

**Check:**

- branch HEAD equals the plan baseline or determine exact docs-only/source delta;
- fresh `agent-control:.agent/status/daemon.json` is idle and binding matches;
- no active task touches this branch;
- worktree is clean;
- `docs/OUTPUT_EXECUTION_ARCHITECTURE_AUDIT.md` remains consistent with current production C++.

**Commit:** none.

**Stop condition:** any production C++ delta after the audit must be audited before A1.

## P0.2 — register missing current Stage28D focused tests in host CMake

**Goal:** make current behavior executable through one repeatable host harness before extracting it.

**Expected scope:** test harness only, especially existing tests such as:

- `test/test_stage28d_binary_role_arbiter/test_main.cpp`;
- `test/test_stage28d_rf_output_endpoint/test_main.cpp`;
- any equivalent current output-binding tests not already registered.

**Focused gate:** build and run only the newly registered existing tests.

**Behavior:** none.

**Commit message:** `Register Stage28 output host tests`

**Exit:** current legacy behavior has repeatable focused host coverage before refactor.

---

# 6. A1 — contracts and fixed-size types

No production wiring changes in A1.

## A1.1 — output primitive types

**Add:** a small output-execution contract header under a dedicated output module, for example `src/climate/output/OutputTypes.h`.

Define only primitive concepts needed by later steps:

- output endpoint identifier;
- binary command state / level representation;
- output source/reason enum;
- supervisor mode enum skeleton;
- transport status/error enum;
- fixed endpoint-capacity constant for the current three endpoints.

Avoid RF frame knowledge and climate-controller classes.

**Focused tests:** type value/validation tests and compile-time size/trivial-copy assertions where useful.

**Commit:** `Add output execution primitive types`

## A1.2 — intent and safety contracts

**Add fixed-size POD contracts:**

- `ControlIntent`;
- `ScheduleIntent`;
- `ManualIntent`;
- `SafetyEnvelope`;
- per-endpoint safety constraint (`Allow`, `ForceOff`, `ForceOn`, `Inhibit`);
- sequence/timestamp/reason metadata.

No transport methods.

**Focused tests:**

- default intent is empty/no-command;
- invalid endpoint cannot become active;
- envelope precedence data is representable without dynamic allocation;
- copy/reset semantics.

**Commit:** `Add output intent and safety contracts`

## A1.3 — plan, transport and report contracts

**Add:**

- `OutputCommand`;
- fixed-capacity `OutputPlan`;
- `TxResult`;
- per-step execution result;
- `ExecutionReport`;
- `ExecutedControlProjection` name reserved for later climate reconciliation.

The report must make partial execution representable. Do not collapse plan execution to one boolean internally.

**Focused tests:**

- ordered plan construction;
- capacity failure is explicit/fail-closed;
- transport failure is distinct from physical state;
- empty plan/report semantics.

**Commit:** `Add output plan and execution report contracts`

**A1 exit:** contracts compile and are host-tested; no production call graph changed.

---

# 7. A2 — dedicated RF433 transport

Goal: production output execution no longer depends on `Stage28RfDiagnostics::manualTransmit()`.

## A2.1 — separate low-level RF radio ownership from diagnostics policy

Refactor the current RMT object ownership so one low-level RF433 radio/driver can be injected into both output transport and diagnostics without constructing two RMT channel owners on the same GPIOs.

Keep current transmit/receive behavior callable during this step.

**Do not:** change endpoint mapping, threshold decisions, schedule, safety, or startup policy.

**Focused tests:** RF protocol/registry tests plus host compile tests for injected interfaces.

**Firmware check:** real-input ESP-IDF build only, no hardware.

**Commit:** `Separate RF433 radio ownership from diagnostics`

## A2.2 — add `Rf433OutputTransport`

Add a narrow production transport implementing the output transport contract.

Responsibilities:

- accept validated endpoint command;
- resolve endpoint to current frozen RF hardware binding;
- perform the transmission attempt through the low-level radio;
- return `TxResult`;
- never decide automation, safety, schedule, dwell, recovery, or physical state.

For this compatibility step, preserve current success semantics: a completed TX is transport success; do not require physical acknowledgement.

**Focused tests:**

- fan/lamp/humidifier ON/OFF select exact frozen frames;
- invalid endpoint fails before transmit;
- low-level failure maps to `TxResult` without changing state elsewhere.

**Commit:** `Add dedicated RF433 output transport`

## A2.3 — migrate legacy RF endpoint to the dedicated transport

Change `Stage28dRfOutputEndpoint` so it uses `OutputTransport` / `Rf433OutputTransport` instead of `RfCommandTransmitter -> Stage28RfDiagnostics::manualTransmit()`.

Keep the endpoint's current cache temporarily; A3 will mirror/migrate it.

**Focused gates:**

- legacy endpoint tests unchanged in meaning;
- RF frame-selection tests;
- real-input firmware build.

**Commit:** `Route legacy output endpoint through RF433 transport`

**A2 exit:** normal automatic output transport no longer calls the diagnostics component.

---

# 8. A3 — honest `OutputStateStore`

## A3.1 — in-memory state-store core

Add fixed-size `OutputStateStore` with one entry per configured endpoint.

Minimum runtime fields:

- desired command/value;
- resolved command/value;
- last command attempted;
- last command attempt sequence/timestamp;
- last transport result;
- last successful transport command if useful;
- physical observation status, default `Unknown`;
- optional independent-feedback metadata kept separate from transport.

No NVS yet.

**Focused tests:**

- desired/resolved update does not imply command attempted;
- failed transmit preserves uncertainty;
- successful TX records command truth but physical remains unknown;
- reset/boot begins physical unknown.

**Commit:** `Add honest output command state store`

## A3.2 — shadow-mirror legacy endpoint execution into the store

Inject/store command-state events from the legacy endpoint/transport path while retaining the old endpoint cache for behavior comparison.

Add focused comparison tests proving legacy endpoint cache and state-store last-commanded projection agree for successful TX sequences and disagree correctly on failures/unknown physical state.

Do not change runtime telemetry naming yet.

**Commit:** `Mirror legacy output execution into state store`

**A3 exit:** one honest state model exists and is populated, though legacy caches still remain temporarily.

---

# 9. A4 — transport-free `BinaryActuatorPolicy`

## A4.1 — extract pure binary resolution state machine

Create `BinaryActuatorPolicy` without downstream driver references.

It owns only:

- ON threshold;
- OFF threshold;
- minimum ON/OFF dwell;
- known binary resolved state;
- last change time;
- dwell/transition counters if retained;
- explicit override input for safety/lifecycle resolution.

Its output is a resolution result such as:

- target state;
- whether a command is required;
- held-by-dwell flag;
- override/bypass reason.

It does not transmit.

**Focused tests:** port the complete useful Stage28D arbiter behavior, including:

- V5 43 -> 44 continuity sequence;
- exact dwell boundary;
- fan hysteresis;
- humidifier longer dwell;
- failed transport does not advance policy state (through explicit commit/ack API rather than hidden downstream failure);
- emergency/lifecycle force-off bypass;
- thermal force-on minimum-OFF bypass behavior.

**Commit:** `Extract transport-free binary actuator policy`

## A4.2 — make `Stage28dBinaryRoleArbiter` a compatibility adapter over policy

Keep public behavior temporarily, but delegate its state decisions to `BinaryActuatorPolicy`.

The adapter performs the old downstream call and commits policy transition only when downstream transport accepts it.

**Focused gate:** old arbiter tests + new policy tests.

**Commit:** `Delegate legacy binary arbiter to policy`

## A4.3 — remove duplicated binary algorithm state from the legacy adapter

After parity is proven, ensure the legacy wrapper is not carrying a second hysteresis/dwell state machine.

Keep legacy counters/lifecycle diagnostics only if still required and source them from the policy.

**Focused gate:** Stage28D arbiter tests and lifecycle counter continuity tests.

**Commit:** `Remove duplicate binary arbiter state`

**A4 exit:** binary policy is independently testable and transport-free.

---

# 10. A5 — `SafetyEnvelope` and `ScheduleIntent`

## A5.1 — single schedule-intent producer

Add a schedule adapter that converts the existing `FixedStage27ScheduleConfigSource` light schedule into `ScheduleIntent`.

Do not change the schedule profile or Europe/Warsaw time behavior.

Eliminate duplicate schedule interpretation in tests first; production direct lamp write remains until supervisor wiring.

**Focused tests:** existing schedule profile + new intent conversion.

**Commit:** `Add scheduled-light output intent`

## A5.2 — adapt lamp thermal safety to `SafetyEnvelope`

Preserve `LampSafetyController` thresholds/latch/recovery state machine exactly.

Add a narrow adapter or revised output contract that yields:

- lamp `ForceOff` when required;
- exhaust `ForceOn` when required/available;
- reason;
- latch/recovery metadata;
- evidence timestamp/age.

It must not know RF transport.

**Focused gate:** every existing lamp safety test plus new envelope mapping tests.

**Commit:** `Expose lamp thermal safety as safety envelope`

## A5.3 — shadow-compare current direct safety/schedule result against intents

Before rewiring production execution, compute the new `ScheduleIntent + SafetyEnvelope` result beside the old path and assert/diagnose parity in host composition tests.

No extra RF call and no hardware.

**Focused tests:** day/night schedule, TimerOff, TemperatureUnavailable, OverTemperature, RecoveryHold, InvalidConfig.

**Commit:** `Verify schedule and safety intent parity`

**A5 exit:** schedule and hard thermal safety can feed a supervisor without transport ownership.

---

# 11. A6 — `OutputSupervisor` compatibility mode

This is the first major ownership migration. Keep behavior comparable to the legacy path.

## A6.1 — pure resolver

Add `OutputSupervisor` resolution core with no real transport wiring.

Inputs:

- `ControlIntent`;
- `ScheduleIntent`;
- `ManualIntent` placeholder;
- `SafetyEnvelope`;
- current mode;
- output policy/config;
- `BinaryActuatorPolicy` state;
- `OutputStateStore`.

Initial compatibility mode resolves only currently active automatic behavior.

Document precedence in code/tests:

1. hard safety;
2. fault/lifecycle when active;
3. manual;
4. schedule;
5. climate;
6. hold/no-command.

**Focused tests:** resolver only, no transport.

**Commit:** `Add output supervisor resolver`

## A6.2 — executor and structured partial-failure reporting

Add synchronous plan execution using a fake transport in host tests.

Requirements:

- execute plan steps in deterministic order;
- update state store after each attempted step;
- produce `ExecutionReport` for partial success/failure;
- never fabricate OFF after a failed command;
- do not advance binary transition state until the relevant command succeeds.

**Focused tests:** first/middle/last step failure, no-op dedupe, repeated command, transport error.

**Commit:** `Execute output plans with deterministic reports`

## A6.3 — compatibility climate sink/bridge

Create a temporary bridge so the existing `ClimateControlLoop` can hand the complete climate request to the supervisor without reintroducing per-role direct transport writes.

The bridge must return supervisor-resolved execution projection, not physical confirmation.

Keep legacy adapters available only for comparison/tests.

**Focused tests:** climate control-loop/application composition using fake supervisor transport.

**Commit:** `Bridge climate loop to output supervisor`

## A6.4 — route normal climate and lamp schedule through supervisor

In `runClimateV6RealInputRuntime()`:

- produce schedule intent;
- produce thermal safety envelope;
- set these on the supervisor cycle input;
- execute normal climate + lamp through the supervisor;
- remove direct normal `writeScheduledLight()` call;
- stop copying thermal force state into the RF endpoint;
- keep startup and exceptional recovery direct for the moment if needed for controlled migration; they are removed in A11.

This commit changes production C++ behavior ownership, so run:

- supervisor focused tests;
- climate composition/control-loop focused tests;
- lamp safety tests;
- binary policy tests;
- RF endpoint/transport focused tests;
- real-input ESP-IDF build.

**Commit:** `Route normal outputs through output supervisor`

**A6 exit:** all normal automatic climate and schedule output execution is supervisor-owned. Remaining direct paths are explicit migration debt: startup/recovery/qualification/maintenance diagnostics.

---

# 12. A7 — climate execution reconciliation migration

## A7.1 — make execution projection terminology honest

Replace `confirmed_applied` terminology across the supervisor-facing path with `ExecutedControlProjection` / `resolved_executed` or equivalent naming that cannot imply physical acknowledgement.

Add conversion from `ExecutionReport` to semantic climate role projection.

**Focused tests:** dwell hold projects held binary state; failed command does not report newly executed state.

**Commit:** `Add honest climate execution projection`

## A7.2 — replace `reconcileApplied()` with supervisor-report reconciliation

Refactor `ClimateRuntimeController` so effective-action reconciliation consumes the supervisor execution projection while preserving the current estimator algorithm:

- restore `effective_before`;
- update using the executed/resolved projection;
- no RF state assumption.

Keep a compatibility wrapper only if needed for a short migration window.

**Focused gates:** `climate_v6_tests`, runtime parity, virtual HIL/control-loop tests.

**Commit:** `Reconcile climate estimator from execution reports`

## A7.3 — remove driver `appliedLevel()` as execution truth and migrate previous-action ownership

Stop deriving climate previous state from downstream driver caches.

The supervisor/state/report boundary becomes the source of previous executed control projection for the next climate cycle.

`previous_applied_` must either be removed or renamed/re-homed so it no longer looks like physically confirmed actuator state.

**Focused gates:** control loop, application composition, fault soak, runtime parity.

**Commit:** `Move climate previous state to supervisor projection`

**A7 exit:** climate decision calculation and physical execution ownership are separated; estimator continuity is preserved using supervisor execution truth.

---

# 13. A8 — lifecycle state machine and Automation OFF

## A8.1 — versioned `OutputPolicyConfig` in memory

Add validated in-memory policy for:

- endpoint-role binding;
- Boot;
- AutomationOff;
- Recovery;
- Fault;
- action (`NoCommand`, `ForceOff`, `ForceOn`, `ApplySchedule`, `RestoreLastCommand`);
- order;
- bounded delay;
- retransmit policy;
- retry/containment limits.

Move current hard-coded output binding validation rules into/behind this validated configuration without weakening duplicate/unmapped checks.

**Focused tests:** invalid duplicate endpoint, invalid scheduled-light/climate mapping, invalid order/delay/action, safe defaults.

**Commit:** `Add validated output lifecycle policy`

## A8.2 — lifecycle state machine

Implement explicit supervisor states, at minimum:

```text
BootLocked
Arming
Automatic
Recovering
Disabled
FaultLocked
MaintenanceLocked   // full behavior activated in A10
```

Add legal transition tests and fail-closed illegal transition handling.

Automation OFF must not stop climate calculation; it suppresses execution of normal `ControlIntent` while keeping the latest intent observable.

Safety remains evaluated in `Disabled`.

**Focused tests:** enable, disable, failed arming, fault, recovery, re-enable.

**Commit:** `Add output supervisor lifecycle state machine`

## A8.3 — ordered non-blocking lifecycle plan execution

Add lifecycle transition plans using `order`, `delay_ms`, and bounded retry metadata.

No blocking sleeps inside supervisor resolution/execution. Represent pending transition steps with due time and advance them from the existing main-loop tick.

**Focused tests:**

- ordered zero-delay sequence;
- delayed step is not executed early;
- deadline/wrap-safe monotonic handling;
- partial failure -> configured containment/FaultLocked;
- no unbounded retry.

**Commit:** `Execute lifecycle output policy non-blockingly`

## A8.4 — runtime Automation OFF/ON integration

Add a narrow product/runtime API used by service/control surfaces to request automation mode transitions.

During `Disabled`:

- climate engine continues to calculate and publish `ControlIntent`;
- normal climate intent is not executed;
- configured AutomationOff actions are executed once per transition/policy requirement;
- schedule action works when configured;
- safety envelope remains active and higher priority.

**Focused tests:** all five AutomationOff actions, safety precedence, observe-only climate telemetry, re-enable/arming.

**Firmware check:** real-input ESP-IDF build.

**Commit:** `Add configurable automation off behavior`

**A8 exit:** lifecycle behavior is a first-class supervisor policy, not compile-time/fake-driver behavior.

---

# 14. A9 — NVS persistence for policy and command state

## A9.1 — versioned durable schema and codec

Add host-testable serialization/validation for `OutputPolicyConfig` and the minimal durable command-state needed for `RestoreLastCommand`.

Requirements:

- explicit schema version;
- fail-closed decode;
- invalid/corrupt/unknown version -> safe defaults, never fabricated physical state;
- fixed-size bounded payload;
- no telemetry-log format reuse.

**Focused tests:** round-trip, corrupt payload, unknown version, truncated payload, safe default migration.

**Commit:** `Add versioned output policy persistence schema`

## A9.2 — one NVS-backed output configuration/state store

Add a thin ESP-IDF NVS adapter behind an interface that has a host fake.

Use one namespace/store for output policy/state. Do not create a second settings backend.

NVS initialization already exists for platform/BLE; reuse platform initialization correctly rather than erasing NVS from output code.

**Focused tests:** fake backend read/write/error behavior.

**Firmware check:** real-input build.

**Commit:** `Add NVS output policy store`

## A9.3 — integrate bounded persistence into supervisor

Persist only meaningful transitions:

- policy changes;
- last-commanded binary state changes needed by restore semantics;
- relevant lifecycle mode/config checkpoints if required.

Do not write each control tick.

`RestoreLastCommand` means reissue the last stored command according to policy; it never means restore a known physical state.

**Focused tests:** write-count bounds, power-cycle fake reload, failed TX does not persist a false new commanded state, restore retransmit semantics.

**Commit:** `Persist output policy and command state safely`

**A9 exit:** durable configuration/state semantics are versioned, bounded, and honest.

---

# 15. A10 — service console and maintenance mode

## A10.1 — route normal manual output commands through `ManualIntent`

Add/adjust service-console commands for normal configured endpoint control so they submit `ManualIntent` to the supervisor.

Normal manual commands are subject to:

- supervisor mode;
- hard safety;
- endpoint policy/authorization;
- state/report telemetry.

**Focused tests:** command parser + supervisor manual precedence/denial cases.

**Commit:** `Route service output commands through supervisor`

## A10.2 — explicit maintenance lock for raw RF TX

Implement `MaintenanceLocked` entry/exit guard.

Entry must:

- stop normal automatic/manual execution;
- complete configured safe-entry lifecycle actions;
- record physical state uncertainty;
- expose mode explicitly.

Raw RF TX is permitted only after successful maintenance entry and may be vetoed by non-bypassable safety for a protected configured endpoint.

Exit must re-arm through supervisor policy; it must not silently flip a boolean back to automatic.

**Focused tests:** denied outside maintenance, entry failure, raw TX allowed only after safe entry, hard-safety veto, exit/re-arm.

**Commit:** `Guard raw RF diagnostics with maintenance mode`

## A10.3 — remove auto-smoke transmit bypass

Change `Stage28RfDiagnostics` so:

- passive receive remains diagnostics-only;
- auto-smoke TX cannot fire invisibly from the ordinary production main loop;
- any TX smoke is explicitly maintenance-scoped or a software-only test fixture;
- normal production transport never calls the diagnostics object.

**Focused tests:** diagnostics state/guard tests and output ownership static test draft.

**Firmware check:** real-input build.

**Commit:** `Isolate RF smoke diagnostics from production outputs`

**A10 exit:** service/diagnostic TX is either supervisor-owned normal manual control or explicitly maintenance-guarded raw transport testing.

---

# 16. A11 — remove legacy owners and enforce the invariant

## A11.1 — migrate startup, recovery and fault execution to supervisor

Replace direct `forceSafeStateWithRetries()` / endpoint writes in runtime startup, output fault handling, and recovery with supervisor lifecycle transitions/plans.

The supervisor becomes the authority for:

- boot safe initialization;
- arming;
- output fault containment;
- recovery;
- disabling execution.

**Focused tests:** boot plan, failed boot command, recovery partial failure, fault containment, safety precedence.

**Firmware check:** real-input build.

**Commit:** `Move startup and recovery outputs to supervisor`

## A11.2 — remove legacy endpoint/driver policy ownership

Remove or reduce obsolete components once no production caller needs them:

- `Stage28dRfOutputEndpoint` state/policy ownership;
- endpoint `safety_force_exhaust_`;
- `MappedClimateRoleDriver` production use;
- `Stage28dBinaryRoleArbiter` production use after policy extraction;
- `SwitchableRoleDriver` fake/real execution ownership;
- `ClimateActuatorAdapter` production execution role if no longer needed.

Keep compatibility test shims only when they still prove migration behavior; remove them when redundant.

**Focused tests:** supervisor/policy/climate composition.

**Commit:** `Remove legacy output execution owners`

## A11.3 — honest output telemetry v2

Replace ambiguous physical-looking fields with explicit telemetry concepts:

- requested/control intent;
- schedule intent;
- safety envelope/reason;
- supervisor mode;
- lifecycle action;
- binary/dwell resolution;
- command attempted;
- transport result;
- last commanded state;
- physical observation = unknown/confidence unless independent feedback exists.

Historical H parsers remain frozen; do not preserve misleading field names solely for old qualification tooling.

**Focused tests:** telemetry serialization/format tests and observer fixture updates only for software parsing.

**Commit:** `Report honest output execution telemetry`

## A11.4 — static ownership enforcement

Add a repository test, for example `tests/test_output_execution_ownership.py`, that scans production paths and fails if configured-output transport calls appear outside an allowlist owned by the output transport/maintenance module.

At minimum guard direct uses of:

- `rmt_transmit` for configured output transport;
- raw output transport send calls;
- legacy endpoint write/force calls if removed;
- `Stage28RfDiagnostics::manualTransmit` from normal production paths.

Prefer architecture/module visibility to static grep where possible, but keep the test as regression evidence.

**Focused test:** the ownership test itself plus output supervisor suite.

**Commit:** `Enforce single production output owner`

## A11.5 — composition-root and memory/stack cleanup

Reduce `runClimateV6RealInputRuntime()` to composition/orchestration after direct policy ownership is gone.

Keep long-lived supervisor/state/policy objects off accidental permanent main-stack growth, using static/runtime-owner storage if measurements justify it.

Run software-only size/stack build comparison against the pre-refactor software baseline.

Do not shrink the RF-enabled main-task stack merely because source structure improved.

**Commit:** `Finalize output runtime composition ownership`

**A11 exit criteria:**

- no normal production configured-output execution outside `OutputSupervisor`;
- safety does not transmit;
- schedule does not transmit;
- climate does not transmit;
- normal service-console control does not transmit directly;
- raw TX exists only behind maintenance guard;
- transport contains no global automation/safety/lifecycle policy;
- state never claims one-way RF physical acknowledgement.

---

# 17. A12 — software stabilization and one full gate

## A12.1 — focused stabilization sweep

Before the full gate, run only the combined focused suites most directly affected:

- output contract/types;
- RF transport;
- output state store;
- binary policy;
- lamp safety/safety envelope;
- schedule intent;
- supervisor resolver/executor/lifecycle;
- climate reconciliation/parity;
- persistence codec/fake/NVS abstraction;
- console/maintenance guard;
- ownership static guard;
- telemetry format.

Fix any failures with small commits, rerunning the affected focused suite only.

Do not run the full gate until these are stable.

## A12.2 — exactly one final software gate

Run one final Local Agent task using `efficient-verification-v1` with focused prerequisite stages and exactly one last `full` verification stage.

The final software gate must include the repository's canonical full software quality checks plus required ESP-IDF production profiles. At minimum establish:

- exact clean SHA;
- all Python tests;
- all host C++ tests;
- lint/format/schema/pre-push quality checks;
- fake-output firmware build;
- real-output firmware build without hardware access;
- static memory/firmware-size report;
- configured main-stack evidence for RF-enabled build;
- ownership static invariant PASS;
- no hardware started marker.

If the full gate reveals a defect and source changes, rerun the affected focused gate first and then run a new final full gate for the new SHA. The previously failed full attempt is retained as evidence; only the final passing SHA becomes the software-qualified architecture identity.

After PASS record the exact new production firmware identity in current status/handoff docs.

**Commit:** documentation/status commit only after the executable SHA is already fixed and passed.

**A12 exit:** one exact production C++ identity has a passing full software gate under the new architecture.

---

# 18. A13 — new Phase H qualification definition, not automatic hardware execution

## A13.1 — rewrite H plan/observer contract for `OutputSupervisor`

Create a new H qualification handoff/plan that proves the new chain, for example:

```text
natural climate ControlIntent
-> OutputSupervisor resolution
-> BinaryActuatorPolicy eligibility
-> OutputPlan fan OFF->ON command
-> RF433OutputTransport TxResult
-> independent Shelly power support
-> environmental response evidence
```

The observer must consume new honest telemetry fields and distinguish requested/resolved/commanded/physical-evidence concepts.

It must also verify:

- supervisor mode is correct;
- no maintenance mode active;
- hard safety did not cause the counted normal transition;
- exact production SHA equals A12 qualified identity;
- zero unexpected transport errors;
- recovery/final state is supervisor-owned.

This is documentation/tooling only.

**Commit:** `Define OutputSupervisor hardware qualification`

## A13.2 — software-only H preflight

Run a new software-only preflight for the exact A12 firmware identity and new H tooling.

It may build and replay fixtures. It must not:

- open serial;
- flash;
- transmit RF;
- touch hardware.

Record `hardware_started=0`.

**Commit:** tooling/docs only if fixes are needed; otherwise result evidence only.

## A13.3 — mandatory stop for explicit operator authorization

After A13.2 PASS, stop.

Do not begin physical H until the operator explicitly authorizes it.

Any future hardware task must:

- use only `/dev/cu.usbserial-1130`;
- explicitly reject `/dev/cu.usbserial-10`;
- use `resources: []`;
- verify exact firmware SHA before physical execution;
- preserve all safety invariants;
- be bounded;
- restore/prove the defined safe final state.

---

# 19. Per-step stop conditions

Stop the current stage rather than patching around the problem if any of the following occurs:

- two production components still need to own the same physical output to make the step work;
- safety must call transport directly;
- transport needs automation/safety/lifecycle knowledge;
- a command cache must be relabeled as physical state to preserve tests;
- climate thresholds/AH semantics change unintentionally;
- a step requires a new FreeRTOS task solely to make ownership work;
- a persistence design would write each control tick;
- `RestoreLastCommand` is implemented as physical acknowledgement;
- a raw RF diagnostic can run outside explicit maintenance guard;
- the change cannot be compared against legacy behavior with focused tests;
- hardware appears necessary before the software contract can be proven.

---

# 20. Required re-audits during execution

## R1 — after A2

Confirm normal production RF no longer traverses `Stage28RfDiagnostics::manualTransmit()`.

## R2 — after A6

Trace normal climate + lamp schedule call graph and prove both enter `OutputSupervisor` before transport.

## R3 — after A8

Trace Automation OFF, Boot, Recovery and Fault policies. Prove Disabled still evaluates climate observe-only and safety remains active.

## R4 — after A10

Trace every service-console and diagnostics RF path. Prove normal manual goes supervisor and raw TX requires MaintenanceLocked.

## R5 — final architecture re-audit after A11

Repeat the A0 repository-wide source scan and update `docs/OUTPUT_EXECUTION_ARCHITECTURE_AUDIT.md` or create a final migration audit.

Required proof:

1. every direct/indirect configured-output writer is enumerated;
2. exactly one normal owner reaches production transport;
3. all state caches are documented and none overclaims physical certainty;
4. safety/fail-safe/startup/recovery/fault/schedule/manual paths are supervisor-resolved;
5. endpoint-role mapping has one validated policy owner;
6. persistence has exactly one product output store;
7. main-task serialization/reentrancy assumptions are explicit;
8. climate reconciliation uses execution reports;
9. legacy tests were either migrated or deliberately retained as compatibility evidence;
10. DRAM/stack/size deltas are recorded;
11. no hidden RF/output bypass remains.

A12 full software qualification may start only after R5 is PASS.

---

# 21. Planned commit sequence summary

```text
P0.2  Register Stage28 output host tests

A1.1  Add output execution primitive types
A1.2  Add output intent and safety contracts
A1.3  Add output plan and execution report contracts

A2.1  Separate RF433 radio ownership from diagnostics
A2.2  Add dedicated RF433 output transport
A2.3  Route legacy output endpoint through RF433 transport

A3.1  Add honest output command state store
A3.2  Mirror legacy output execution into state store

A4.1  Extract transport-free binary actuator policy
A4.2  Delegate legacy binary arbiter to policy
A4.3  Remove duplicate binary arbiter state

A5.1  Add scheduled-light output intent
A5.2  Expose lamp thermal safety as safety envelope
A5.3  Verify schedule and safety intent parity

A6.1  Add output supervisor resolver
A6.2  Execute output plans with deterministic reports
A6.3  Bridge climate loop to output supervisor
A6.4  Route normal outputs through output supervisor

A7.1  Add honest climate execution projection
A7.2  Reconcile climate estimator from execution reports
A7.3  Move climate previous state to supervisor projection

A8.1  Add validated output lifecycle policy
A8.2  Add output supervisor lifecycle state machine
A8.3  Execute lifecycle output policy non-blockingly
A8.4  Add configurable automation off behavior

A9.1  Add versioned output policy persistence schema
A9.2  Add NVS output policy store
A9.3  Persist output policy and command state safely

A10.1 Route service output commands through supervisor
A10.2 Guard raw RF diagnostics with maintenance mode
A10.3 Isolate RF smoke diagnostics from production outputs

A11.1 Move startup and recovery outputs to supervisor
A11.2 Remove legacy output execution owners
A11.3 Report honest output execution telemetry
A11.4 Enforce single production output owner
A11.5 Finalize output runtime composition ownership

A12.x Focused fixes only if required
A12    Record qualified OutputSupervisor software identity

A13.1 Define OutputSupervisor hardware qualification
A13.2 New software-only H preflight
A13.3 STOP for explicit hardware authorization
```

This is intentionally many small commits. Adjacent steps should not be squashed during execution because their separate focused-gate evidence is valuable for regression diagnosis.

---

# 22. Pre-execution acceptance criteria

The plan is ready for Local Chat Bridge execution only if a final read-only re-audit confirms:

- current branch still matches the A0 code assumptions;
- the dependency order above is feasible with current class boundaries;
- existing host tests cover the legacy behaviors that will be extracted;
- no plan step assumes a settings store that does not exist;
- no step requires hardware before A13;
- the plan preserves one final full software gate after stabilization;
- every future Local Agent task can use `resources: []` and the exact repository binding.
