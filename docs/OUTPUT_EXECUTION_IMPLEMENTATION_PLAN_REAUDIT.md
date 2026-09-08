# Output Execution Implementation Plan Re-Audit

Status: PASS WITH NORMATIVE AMENDMENTS
Updated: 2026-09-08
Repository: `MichalMatu/growbox-ml-controller`
Work branch: `mvp/environment-controller`
Plan reviewed: `docs/OUTPUT_EXECUTION_IMPLEMENTATION_PLAN.md`
A0 audit: `docs/OUTPUT_EXECUTION_ARCHITECTURE_AUDIT.md`
Production C++ baseline audited: `ff769096f24349ba6f31e61ea170176db00725d3`
A0 audit commit: `d11b6de703421ff678789bdcfcea876fc902733d`
Plan commit: `7f870c99a5b87e3ae9ec2565ba9ffaa6772774e1`

## Result

The implementation plan is feasible against the current source and preserves the requested incremental migration strategy. No production C++ changed between the A0 audit and this re-audit; the only branch delta after A0 is the implementation-plan document itself.

The plan is approved for Local Chat Bridge execution subject to the amendments below. These amendments are normative and override the corresponding shorthand wording in the main implementation plan.

No hardware, serial, flashing, RF transmission, build, or test was executed for this re-audit.

---

## Evidence checked

The re-audit checked the current boundaries that determine whether the proposed sequence is genuinely incremental:

- `ClimateApplication` owns a concrete `ClimateActuatorAdapter` and `ClimateControlLoop`;
- `ClimateActuatorAdapter` implements `ClimateActuatorSink` over a per-role `ClimateRoleDriver`;
- `ClimateControlLoop` owns `previous_applied_`, actuator fault latch, sink execution and fail-safe calls;
- `ClimateRuntimeController::reconcileApplied()` rewinds/updates the effective-action estimator from sink-reported state;
- `Stage28dBinaryRoleArbiter` owns binary dwell/hysteresis state and calls a downstream driver;
- `Stage28dRfOutputEndpoint` owns endpoint command cache and the duplicate exhaust safety force flag;
- `Stage28RfDiagnostics` directly owns `Rf433RmtLoopback` and exposes manual TX/RX plus auto-smoke;
- `runClimateV6RealInputRuntime()` serializes service console, RF diagnostics tick, safety/schedule, climate execution and telemetry in the main task;
- the runtime directly owns startup safe-state, scheduled lamp writes, runtime recovery and Gate6 direct endpoint paths;
- current endpoint identifiers are `ClimateEndpointId` (`uint16_t`) and the physical set is RF socket 1 fan, socket 2 lamp, socket 3 humidifier;
- `nvs_flash` is already an ESP-IDF component dependency, but no product output policy/state schema exists;
- existing Stage28D arbiter and RF endpoint tests are present but are not currently registered in `test/host/CMakeLists.txt`.

---

# Normative amendments

## R-A1 — do not create a second endpoint-ID domain

The current source already defines:

```cpp
using ClimateEndpointId = std::uint16_t;
```

A1.1 must not introduce an unrelated parallel numeric ID that then requires permanent conversion layers.

Preferred migration:

1. move/centralize the primitive endpoint ID into the output contract module;
2. temporarily alias `ClimateEndpointId` to that primitive type, or retain the existing typedef while new output contracts reuse it;
3. preserve current endpoint values exactly;
4. remove the legacy climate-named alias only when downstream migration makes that safe.

This keeps A1 behavior-preserving.

## R-A2 — A2.1 must establish exactly one RMT hardware owner

`Stage28RfDiagnostics` currently contains `Rf433RmtLoopback loopback_` by value. Therefore output transport cannot simply instantiate a second RMT object on the same TX/RX GPIOs.

A2.1 must first establish one low-level RF radio/RMT owner with one initialization lifecycle, then inject/reference that owner from:

- dedicated `Rf433OutputTransport`;
- `Stage28RfDiagnostics`.

Do not let both components independently call `begin()` on competing RMT channel instances.

The main-task serialized call order may remain the initial concurrency contract.

## R-A3 — preserve RF TX semantics while separating diagnostics

Current `Stage28RfDiagnostics::manualTransmit()` invokes loopback transmit/receive but reports success from `tx_completed`.

During A2 separation, do not accidentally redefine transport success as successful self-RX decode or physical load acknowledgement.

Initial dedicated transport success remains:

> the requested RF TX completed according to the local transport.

Self-RX evidence belongs to diagnostics. A later internal cleanup may remove unnecessary receive work from production TX only after focused software behavior/timing review.

## R-A4 — split A6.3 into two commit-sized steps

`ClimateApplication` currently hard-wires:

```text
ClimateInputAdapter
ClimateActuatorAdapter
ClimateControlLoop
```

and its public constructor accepts a `ClimateRoleDriver`, not a `ClimateActuatorSink`.

Therefore A6.3 must be executed as:

### A6.3a — add a sink injection/composition seam

Add a behavior-preserving construction path that allows `ClimateControlLoop` to receive an externally owned `ClimateActuatorSink` while retaining the existing constructor/path for compatibility tests.

Focused gate: existing application composition + control-loop tests.

Suggested commit: `Allow climate application actuator sink injection`

### A6.3b — add the supervisor-backed climate sink

Implement the compatibility sink/bridge over `OutputSupervisor` and prove it returns execution projection rather than physical confirmation.

Focused gate: new supervisor sink tests + existing control-loop tests.

Suggested commit: `Bridge climate sink to output supervisor`

Only then perform A6.4 runtime wiring.

## R-A5 — A6.4 must deactivate both legacy safety-force copies on the active path

The current thermal force is copied into both:

- `Stage28dBinaryRoleArbiter::safety_force_exhaust_`;
- `Stage28dRfOutputEndpoint::safety_force_exhaust_`.

Once normal execution is supervisor-owned, the active production path must not keep either flag as an independent safety decision owner.

Legacy objects may remain temporarily for comparison, but if they are still constructed they must be inactive with respect to normal output execution. `SafetyEnvelope` is the active safety input to the supervisor.

## R-A6 — split A7 previous-state migration into two steps

`ClimateControlLoop` currently owns `previous_applied_` internally and writes it into `ClimateControllerInput::previous` before every controller step. Removing it in one commit would unnecessarily mix API change, state ownership change and controller reconciliation.

Execute instead:

### A7.3a — external execution-feedback seam

Add a way for the climate decision/control composition to consume an externally supplied previous execution projection while preserving the existing internal path as a compatibility wrapper.

Focused gate: control-loop, runtime parity and virtual-HIL tests.

Suggested commit: `Allow external climate execution feedback`

### A7.3b — switch production to supervisor-owned previous projection

Wire the supervisor execution report/state projection into the next climate cycle, then remove/retire `previous_applied_` as production ownership.

Focused gate: control-loop, application composition, fault soak and runtime parity.

Suggested commit: `Use supervisor projection as climate previous state`

## R-A7 — P0.2 is required, not optional

The source contains host-friendly standalone tests for:

- `Stage28dBinaryRoleArbiter`;
- `Stage28dRfOutputEndpoint`;

but the current `test/host/CMakeLists.txt` does not register them.

P0.2 should register these existing tests before A2/A4 so legacy extraction behavior has a repeatable CMake/CTest gate.

This is test-harness-only and does not change production behavior.

## R-A8 — lifecycle policy and binary policy must use propose/commit semantics

A pure `BinaryActuatorPolicy` cannot update `last_change_ms` merely because it resolved a target. Current legacy behavior advances state only after the downstream call succeeds.

The extracted policy therefore needs an explicit two-phase contract or equivalent:

```text
resolve/propose -> OutputPlan
transport result -> commit accepted transition
```

A failed transport attempt must not advance binary ON/OFF state or dwell clock.

This applies to A4 and becomes a supervisor invariant in A6.

## R-A9 — `OutputStateStore` and binary policy state are distinct

Do not merge these merely because both contain ON/OFF-like data.

- `BinaryActuatorPolicy` state = deterministic hysteresis/dwell resolution state.
- `OutputStateStore` = desired/resolved/command-attempt/transport-result/physical-unknown truth.

They may be correlated by supervisor execution reports, but neither replaces the other.

## R-A10 — current main-loop serialization is suitable for the first supervisor

No new FreeRTOS supervisor task is required by current source structure.

Service-console polling, diagnostics tick, safety/schedule evaluation, climate execution and telemetry already run sequentially from the main runtime loop. The RF RMT callback interaction is internal ISR/semaphore behavior.

The initial supervisor should remain synchronous in that task. This avoids new stack/queue/concurrency risk during migration.

## R-A11 — A9 NVS store must never own platform NVS initialization/erase policy

The project already initializes NVS in BLE/platform code. The output persistence layer may open/use its own NVS namespace, but it must not independently call destructive platform recovery such as `nvs_flash_erase()`.

If NVS platform initialization needs centralization, make that a separate platform-ownership refactor rather than hiding it inside output persistence.

## R-A12 — A10 raw RF maintenance must share the single low-level radio safely

After A2 there is one low-level RF radio owner. Maintenance diagnostics and normal output transport therefore share a non-reentrant hardware object under the main-task serialization contract.

`MaintenanceLocked` must ensure normal supervisor output execution is quiescent before raw TX begins.

Passive RX may remain diagnostics-only outside maintenance if it cannot conflict with an active TX operation; otherwise the supervisor/diagnostics scheduling must serialize it explicitly.

## R-A13 — final ownership guard needs a narrow allowlist

The A11 static ownership regression should not simply ban every `rmt_transmit` string repository-wide because transport implementation and tests legitimately need it.

The allowlist should be narrow and explicit, e.g.:

- RF low-level transport implementation;
- dedicated test fixtures;
- explicitly maintenance-only module if raw transport calls live there.

Normal runtime, climate, safety, schedule and service-console production modules must not appear on the allowlist.

---

# Re-audited executable sequence

The final sequence is:

```text
P0.1 fresh identity/status
P0.2 register legacy Stage28D focused tests

A1.1 primitives / endpoint-ID centralization
A1.2 intents + SafetyEnvelope
A1.3 OutputPlan / TxResult / ExecutionReport

A2.1 one shared low-level RF radio owner
A2.2 dedicated RF433OutputTransport
A2.3 legacy endpoint -> dedicated transport

A3.1 OutputStateStore
A3.2 shadow mirror legacy command state

A4.1 pure BinaryActuatorPolicy propose/commit
A4.2 legacy arbiter delegates to policy
A4.3 remove duplicate arbiter algorithm state

A5.1 ScheduleIntent
A5.2 lamp thermal SafetyEnvelope
A5.3 parity tests

A6.1 supervisor resolver
A6.2 plan executor + partial reports
A6.3a ClimateApplication/sink injection seam
A6.3b supervisor-backed climate sink
A6.4 normal climate + lamp -> supervisor; legacy safety-force copies inactive

A7.1 honest execution projection
A7.2 reconcile estimator from supervisor reports
A7.3a external previous-execution feedback seam
A7.3b production previous state -> supervisor projection

A8.1 validated lifecycle policy
A8.2 lifecycle state machine
A8.3 non-blocking ordered/delayed lifecycle plans
A8.4 Automation OFF/ON runtime behavior

A9.1 durable schema/codec
A9.2 NVS namespace adapter
A9.3 bounded persistence integration

A10.1 normal manual -> ManualIntent
A10.2 MaintenanceLocked raw TX guard
A10.3 remove auto-smoke production bypass

A11.1 startup/recovery/fault -> supervisor
A11.2 remove legacy output owners
A11.3 honest telemetry v2
A11.4 static ownership invariant
A11.5 composition + memory/stack cleanup

R5 final architecture re-audit

A12.1 focused stabilization
A12.2 one final full software gate / exact new firmware identity

A13.1 new OutputSupervisor H plan
A13.2 software-only H preflight
A13.3 STOP for explicit hardware authorization
```

---

# Final PASS rationale

The order is dependency-correct against the current code:

- existing legacy tests can be made repeatable before extraction;
- transport can be separated before state/policy ownership moves;
- state store can shadow legacy behavior before becoming authoritative;
- binary policy can be proven independently before supervisor integration;
- schedule and hard safety can become data contracts before direct writes are removed;
- the application needs only a small injection seam before the supervisor becomes its sink;
- climate estimator reconciliation can move after supervisor execution reports exist;
- lifecycle/Automation OFF can be introduced only after the supervisor owns normal execution;
- NVS persistence is deferred until the runtime model is stable;
- console/maintenance migration occurs after lifecycle states exist;
- startup/recovery bypasses are removed only after supervisor lifecycle handling exists;
- the single-owner invariant is re-audited before the only full software gate;
- hardware remains completely deferred until a new exact software-qualified identity and new H plan exist.

No blocker was found that requires a giant rewrite or hardware access.

**FINAL RE-AUDIT: PASS.**
