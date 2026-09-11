# Output Execution Architecture Audit

Status: A0 READ-ONLY ARCHITECTURE AUDIT
Updated: 2026-09-08
Repository: `MichalMatu/growbox-ml-controller`
Work branch: `mvp/environment-controller`
Audited source HEAD: `ff769096f24349ba6f31e61ea170176db00725d3`
Parent handoff reference: `430e15e1bc9e2d65ff5a97554339467ef2351c52`

## Scope and constraints

This audit is source-reading only. It does not change production behavior and did not run H v8, flash hardware, open serial, transmit RF, or execute hardware tests.

The work-branch HEAD moved after the handoff reference by exactly one commit:

`ff769096f24349ba6f31e61ea170176db00725d3` — `Correct output architecture persistence assumptions`

That commit changes only `docs/OUTPUT_EXECUTION_ARCHITECTURE.md` (+3/-2). It records two facts already confirmed by the audit: `Stage28RfDiagnostics` auto-smoke is a direct RF path when enabled, and the repository currently has no suitable existing product settings/state store for output policy/state.

The target invariant remains:

> `OutputSupervisor` is the only normal production owner allowed to execute configured physical outputs.

---

# 1. Observed facts from the current code

## 1.1 Current normal climate-to-RF call graph

The normal real-output path is:

```text
runClimateV6RealInputRuntime()
  -> ClimateApplication::tick()
    -> ClimateControlLoop::tick()
      -> ClimateRuntimeController::step()
         ruleRequest()
         -> evaluate()
            -> arbitrate()
            -> safety()
         -> decision.applied
      -> ClimateActuatorAdapter::applyAndReport()
        -> ClimateActuatorAdapter::apply()
          -> SwitchableRoleDriver::apply()
            -> Stage28dBinaryRoleArbiter::apply()
              -> Stage28dBinaryRoleArbiter::applyBinary()   [fan/humidifier]
              -> MappedClimateRoleDriver::apply()
                -> Stage28dRfOutputEndpoint::write()
                  -> Stage28dRfOutputEndpoint::applyBinary()
                    -> DiagnosticsRfTransmitter::transmit()
                      -> Stage28RfDiagnostics::manualTransmit()
                        -> Rf433RmtLoopback::transmitAndReceive()
                          -> rmt_transmit()
                          -> rmt_tx_wait_all_done()
      -> ClimateRuntimeController::reconcileApplied()
```

Files:

- `src/climate/ClimateV6RealInputRuntime.cpp`
- `src/climate/ClimateApplication.cpp`
- `lib/environment_control/src/climate/ClimateControlLoop.cpp`
- `lib/environment_control/src/climate/ClimateRuntimeController.cpp`
- `src/climate/ClimateIoAdapters.cpp`
- `src/climate/Stage28dBinaryRoleArbiter.cpp`
- `src/climate/ClimateSemanticOutput.cpp`
- `src/climate/Stage28dRfOutputEndpoint.cpp`
- `src/climate/runtime/Stage28RfDiagnostics.cpp`
- `src/climate/rf433/Rf433RmtLoopback.cpp`

Important detail: the normal production endpoint does **not** own a dedicated RF transport object. `DiagnosticsRfTransmitter` adapts the production endpoint to `Stage28RfDiagnostics::manualTransmit()`. The same diagnostics object is also exposed to the service console and auto-smoke path.

## 1.2 All output/RF execution paths found

### A. Normal climate path

Described above. Fan and humidifier pass through binary hysteresis/dwell. Other climate roles pass through the arbiter to the mapped driver, although the current Stage28D binding deliberately enables only exhaust fan and humidifier.

### B. Lamp schedule path bypasses the climate driver chain

In the normal branch of `runClimateV6RealInputRuntime()`:

1. RTC and fixed schedule are sampled directly.
2. `LampSafetyController::evaluate()` combines schedule demand with thermal safety.
3. `physical_endpoint.writeScheduledLight(...)` is called directly.

This path bypasses `ClimateApplication`, `ClimateControlLoop`, `ClimateActuatorAdapter`, `Stage28dBinaryRoleArbiter`, and `MappedClimateRoleDriver`.

### C. Startup safe-state path

`forceSafeStateWithRetries()` calls `Stage28dRfOutputEndpoint::initializeSafeState()` up to three times.

`initializeSafeState()` force-sends OFF to:

1. scheduled lamp;
2. exhaust fan;
3. humidifier.

Only after that succeeds does the runtime mark real outputs ready and call `Stage28dBinaryRoleArbiter::synchronizeSafeOff()` to align the arbiter's logical fan/humidifier state with the commanded startup state.

### D. Climate-loop fail-safe path

`ClimateControlLoop::tick()` owns its own fail-safe execution:

- if the normal `applyAndReport()` fails, it calls `ClimateActuatorSink::applyFailSafeOff()`;
- `ClimateActuatorAdapter::applyFailSafeOff()` calls `forceSafeOff()` for all six climate roles;
- the real chain reaches `Stage28dBinaryRoleArbiter::forceSafeOff()` and then `MappedClimateRoleDriver::forceSafeOff()` / endpoint `forceOff()`.

If fail-safe OFF itself fails, `ClimateControlLoop` latches `actuator_fault_latched_` and retries fail-safe OFF on subsequent ticks.

### E. Runtime-level fault recovery path

After `ClimateApplication::tick()`, `runClimateV6RealInputRuntime()` independently checks `!loop_result.command_applied`. When real outputs are still enabled, it again calls `forceSafeStateWithRetries(physical_endpoint, now_ms)`, then calls `output_driver.disableReal()` and sets `real_output_ready=false`.

Therefore output-failure recovery currently has **two execution owners**:

1. `ClimateControlLoop`/actuator sink;
2. runtime composition code calling the RF endpoint directly.

### F. Lamp-fault recovery path

If direct scheduled-lamp execution fails, `runClimateV6RealInputRuntime()` directly calls `forceSafeStateWithRetries()`, disables the real driver, and clears `real_output_ready`.

### G. Gate6 thermal-test production-code path

When `GROWBOX_STAGE28_THERMAL_TEST_SEQUENCE_ENABLED != 0`, the runtime directly calls:

- `physical_endpoint.writeScheduledLight(...)`;
- `physical_endpoint.write(kExhaustFanEndpoint, ...)`;
- `physical_endpoint.write(kHumidifierEndpoint, 0.0F, ...)`.

It also calls direct safe-state recovery on failure/completion.

This is compile-time qualification/test behavior in production C++ and is a direct endpoint bypass.

### H. Service-console RF path

`Stage28ServiceConsole::handleRfTransmit()` resolves a physical RF device and directly calls:

`Stage28RfDiagnostics::manualTransmit(frame, evidence)`.

It is blocked while `realOutputsActive()` is true, but it is allowed when automatic outputs are `fake-locked`, provided RF diagnostics are ready. Therefore `fake-locked` does **not** mean that no code can transmit configured output RF frames; it only locks the automatic climate driver path.

The console correctly reports `physical_state=unconfirmed`.

### I. RF auto-smoke path

`Stage28RfDiagnostics::tick()` calls `runSmoke()` when `config_.auto_smoke` is enabled. `runSmoke()` directly calls `Rf433RmtLoopback::transmitAndReceive()`.

This is another direct RF transmit path independent of the output endpoint and climate chain.

### J. Low-level physical transmitter

Within the audited real-input runtime, the actual ESP-IDF RMT write is centralized in:

`Rf433RmtLoopback::transmitAndReceive()` -> `rmt_transmit()`.

However, multiple higher-level owners can reach that transport.

No additional production RF transmitter call site was found by the repository-wide read-only scan for the current real-input path. Qualification/recovery scripts remain external tooling and can cause output actions through the service-console interface, but they are not firmware output owners.

## 1.3 Output-state caches and sources of truth

There is no single output state owner.

### `ClimateControlLoop::previous_applied_`

File: `lib/environment_control/src/climate/ClimateControlLoop.{h,cpp}`.

- copied into `ClimateControllerInput::previous` before each controller step;
- updated only after successful `applyAndReport()` and `reconcileApplied()`;
- cleared on normal apply failure and on reset;
- describes the last driver-reported applied projection, not physical acknowledgement.

### `ClimateRuntimeController::effective_estimator_`

Files:

- `lib/environment_control/src/climate/ClimateRuntimeController.cpp`
- `lib/environment_control/src/climate/ClimateActuatorStateEstimator.h`

The controller first advances the effective-action estimator from `decision.applied` **before** output execution. After successful driver execution, `reconcileApplied()` restores `decision.effective_before` and advances again using driver-reported `confirmed_applied`.

Thus the estimator currently participates in both decision calculation and post-execution reconciliation.

### `Stage28dBinaryRoleArbiter` binary state

The arbiter owns separate `BinaryState` for exhaust and humidifier:

- `known`;
- `on`;
- `last_change_ms`.

It also owns transition/dwell/safety-override counters and `safety_force_exhaust_`.

This state is execution-policy state, not physical acknowledgement.

### `Stage28dRfOutputEndpoint::states_`

The endpoint owns three cached states:

- `known`;
- `on`;
- `changed_ms`.

They are updated when `transmitter_.transmit(frame)` returns success. In the current adapter, success means RF TX completed. It is not proof that the remote socket changed state.

The endpoint cache is therefore **last successfully commanded transport state**, despite current telemetry names such as `fan_known/fan_on` looking more physical than that truth allows.

### `real_output_ready` / `SwitchableRoleDriver::real_enabled_`

`runClimateV6RealInputRuntime()` owns `real_output_ready`; `SwitchableRoleDriver` owns a separate `real_enabled_` copy initialized from it. Fault paths normally update both, but the duplication is an ownership smell.

### Safety state

`LampSafetyController` owns:

- `thermal_latched_`;
- `recovery_running_`;
- `recovery_started_ms_`.

Safety force state is then duplicated into both:

- `Stage28dBinaryRoleArbiter::safety_force_exhaust_`;
- `Stage28dRfOutputEndpoint::safety_force_exhaust_`.

### Diagnostics/telemetry projections

`physicalOutputSnapshot()` and `stage28d_output` logs read endpoint caches and label them as lamp/fan/humidifier state. These are useful command-state observations but must not become the target `physical_state` unless independent feedback exists.

## 1.4 Safety and fail-safe mechanisms are currently split

There are at least three distinct safety concepts.

### Climate policy safety inside `ClimateRuntimeController`

The private `safety()` function mutates the climate request before it becomes `decision.applied`. Examples include:

- unusable required temperature/RH -> zero request;
- very high temperature -> heater/humidifier/CO2 off, cooler/exhaust potentially full on;
- very low temperature -> cooler/exhaust off, heater potentially full on;
- very high RH -> humidifier off, dehumidifier potentially full on;
- high CO2 -> CO2 dosing off, exhaust potentially full on.

This is part of climate decision evaluation and is separate from Stage28D lamp thermal safety.

### `LampSafetyController`

This is the product thermal lamp protection:

- invalid config -> lamp OFF + exhaust forced ON when available;
- unavailable/stale TP357 temperature -> lamp OFF + exhaust forced ON;
- trip -> thermal latch;
- recovery below threshold for configured hold -> unlatch;
- while latched -> lamp OFF + exhaust ON;
- otherwise lamp follows schedule.

The controller itself does not transmit, but the runtime immediately translates its result into direct endpoint writes and force flags, so the current safety path has execution authority through composition code.

### `ClimateControlLoop` fail-safe OFF

This is actuator-I/O failure containment. It tries to force all climate roles OFF and can latch an actuator fault.

It is semantically different from lamp thermal safety, which intentionally requires exhaust ON.

The target architecture must preserve these distinctions while giving only the supervisor transport ownership.

## 1.5 Startup and safe initialization

Current real-output startup is fail-closed in a useful way:

1. RF diagnostics/transport must be ready.
2. hard-coded output bindings must validate.
3. `Stage28dRfOutputEndpoint` is enabled only if real outputs were compile-time requested and prerequisites pass.
4. startup explicitly transmits OFF to lamp, fan, humidifier using `initializeSafeState()`.
5. if that fails after retries, automatic outputs remain fake-locked.
6. after success, arbiter fan/humidifier state is synchronized as known OFF at the current monotonic time.

The target policy must preserve explicit boot commands but move their choice/order/retry semantics into `OutputPolicyConfig` + `OutputSupervisor`.

## 1.6 Automation enable/disable in the current firmware

The current real-input runtime does **not** have the target runtime Automation ON/OFF state machine.

Existing mechanisms are different:

- `GROWBOX_STAGE28_REAL_OUTPUTS_ENABLED` is a compile-time build option;
- `real_output_ready` is a runtime readiness/fault boolean;
- `SwitchableRoleDriver::disableReal()` is a one-way switch used by fault/qualification cleanup paths;
- there is no normal re-enable transition in this runtime without reconstructing/rebooting the runtime;
- the climate engine itself continues only because the normal loop remains active after the real driver is disabled and the switchable driver then routes to the fake driver.

Therefore target Automation OFF lifecycle semantics are a **new explicit execution-mode contract**, not simply a rename of an existing user-facing automation switch.

## 1.7 Recovery and fault handling

Current fault handling is distributed:

- `ClimateControlLoop`: normal apply failure -> fail-safe OFF; latch only when fail-safe OFF fails; reset runtime estimator/trends and previous-applied state.
- `runClimateV6RealInputRuntime`: any failed application command while real driver remains enabled -> direct endpoint safe-state retries -> disable real outputs.
- scheduled-lamp failure -> same direct runtime-level recovery.
- thermal-test failure/completion -> same direct runtime-level recovery.
- service-console manual TX failure only reports evidence; it is not integrated with automatic fault state.
- RF endpoint caches are not updated on failed transmit, which is correct, but there is no global execution fault object/state store.

A successful safe-off attempt is still only a successful RF command attempt. The current code cannot prove the physical load is OFF.

## 1.8 Lamp schedule path

The schedule is currently generated by `FixedStage27ScheduleConfigSource::resolve()` using Europe/Warsaw local time and `buildMintScheduleProfile()`.

The composite input also carries the schedule into the climate controller, but physical lamp execution is separate: the runtime samples RTC/schedule again, feeds scheduled light level to `LampSafetyController`, and writes the lamp endpoint directly.

This creates two schedule projections in one cycle and keeps lamp execution outside the normal actuator chain.

Target treatment: one `ScheduleIntent` source and one supervisor resolution path.

## 1.9 Endpoint-role mapping

Current mapping is split across two layers.

### Semantic climate mapping

`makeClimateSemanticOutputConfig()` binds:

- `ExhaustFan` -> `kExhaustFanEndpoint`;
- `Humidifier` -> `kHumidifierEndpoint`.

Heater, cooler, dehumidifier, and CO2 doser must remain cleanly disabled.

`validateClimateSemanticOutputConfig()` rejects enabled unmapped roles and duplicate endpoint assignments.

### Hardware RF registry validation

`validateOutputBindings()` separately proves:

- exhaust endpoint -> RF remote socket 1;
- scheduled light endpoint -> RF remote socket 2;
- humidifier endpoint -> RF remote socket 3;
- the scheduled light endpoint is not accidentally routed as a climate role.

This validation is strong but static/hard-coded. The target versioned `OutputPolicyConfig` should absorb endpoint-role binding while retaining equivalent validation and uniqueness rules.

## 1.10 Persistent settings/state mechanisms currently present

The design document correction at `ff769096...` is consistent with source evidence.

### NVS

NVS is initialized by BLE platform code (`BleClimateScanner` and older BLE source code) as an ESP-IDF/NimBLE prerequisite. There is no current product output-policy/state schema built on NVS.

### RTC no-init breadcrumbs

`Stage28eBreadcrumbs.cpp` stores diagnostic reset/crash breadcrumbs in `RTC_NOINIT_ATTR`. This is diagnostic continuity storage, not durable product configuration and not suitable as the output policy/state store.

### Stage27 telemetry storage

`Stage27TelemetryLogger` provides queued append-only telemetry to SD with optional flash fallback. It creates a separate `stage27_store` task and is designed for log records, not mutable settings/state.

Conclusion: there is no suitable existing product settings store to reuse today. A6 may introduce exactly one versioned store, with NVS the natural first candidate, while keeping telemetry storage separate.

## 1.11 Task/thread ownership and concurrency/reentrancy

### Main control execution

`app_main()` calls `runClimateV6RealInputRuntime()` directly. The function is non-returning and its main loop executes, sequentially in the main task:

1. service console poll;
2. RF diagnostics tick;
3. lamp safety/schedule + climate control/output execution;
4. telemetry snapshot submission;
5. delay.

Normal console TX, auto-smoke tick, schedule output, climate output, and runtime recovery therefore do not execute concurrently with each other in this explicit main-loop code; they are serialized by call order.

### RMT ISR interaction

`Rf433RmtLoopback` registers an RMT RX callback. The ISR writes RX count/overflow state and gives a semaphore; the main task waits/consumes it. This is an intentional ISR/task interaction.

The RF object itself has no general mutex protecting simultaneous callers. The current main-loop serialization is therefore an implicit safety property. A future supervisor/console design must not assume the transport is reentrant.

### Telemetry storage task

`Stage27TelemetryLogger::begin()` creates a separate FreeRTOS task `stage27_store` and a queue. Shared status counters are atomic. Output execution does not happen from that task.

### BLE/runtime platform tasks

NimBLE and ESP-IDF platform tasks exist outside this composition. BLE state uses atomics/internal synchronization. No audited BLE callback directly owns configured RF output execution.

### Architectural concurrency requirement

The target supervisor should have one documented execution context. If intents arrive from multiple contexts in the future, they should be queued/snapshotted into the supervisor rather than letting callers invoke transport directly. Transport calls should remain serialized.

## 1.12 `reconcileApplied`, `previous_applied`, and effective-action estimator

Current semantics are tightly coupled to the driver chain.

1. `ClimateRuntimeController::step()` computes `decision.applied` and immediately advances `effective_estimator_` from it.
2. `ClimateControlLoop` asks the actuator sink to execute/report.
3. `ClimateActuatorAdapter::applyAndReport()` first applies all roles, then obtains each driver's `appliedLevel()`.
4. `Stage28dBinaryRoleArbiter::appliedLevel()` converts fan/humidifier to held binary state when known, so dwell holds can be reflected as 0/1 rather than the requested analog level.
5. On success, `reconcileApplied()` restores the estimator to `effective_before` and advances it using `confirmed_applied`.
6. `previous_applied_` is then copied from the reconciled `decision.applied`.

This is useful behavior: future controller context reflects the execution-policy projection rather than raw requested level.

But the name `confirmed_applied` is too strong for one-way RF. It means **driver-resolved/accepted command projection**, not confirmed physical state.

Target placement:

- `OutputSupervisor` owns resolved/commanded execution truth;
- climate receives an `ExecutedControlProjection` (or similarly explicit name) derived from supervisor execution reports;
- `previous_applied_` should no longer be owned by a transport-driving `ClimateControlLoop`;
- effective-action estimation can remain with the climate engine, but reconciliation must use supervisor-reported execution truth, never endpoint-cache-as-physical-state.

## 1.13 Partial-application behavior

`ClimateActuatorAdapter::apply()` iterates all six roles and continues after an individual failure. Therefore one output may have transmitted successfully before a later role fails, after which the whole operation returns false.

`applyFailSafeOff()` likewise attempts every role even when one force-off fails.

`Stage28dRfOutputEndpoint::initializeSafeState()` also attempts all three safe-state outputs and returns aggregate success.

This is intentional best-effort behavior in some recovery contexts, but there is no explicit transaction/plan/report describing which steps succeeded. The target `OutputPlan` + `ExecutionReport` should make partial execution deterministic and observable instead of reducing it to one boolean.

## 1.14 Tests coupled to the current chain

The read-only repository scan found direct coupling in at least:

- `test/test_climate_control_loop/test_main.cpp`;
- `test/test_climate_io_adapters/test_main.cpp`;
- `test/test_climate_application_composition/test_main.cpp`;
- `test/test_climate_semantic_output/test_main.cpp`;
- `test/test_stage28d_binary_role_arbiter/test_main.cpp`;
- `test/test_stage28d_rf_output_endpoint/test_main.cpp`;
- `test/test_stage28d_lamp_safety/test_main.cpp`;
- `test/test_climate_fault_soak/test_main.cpp`;
- `test/test_climate_virtual_hil/test_main.cpp`;
- `test/test_climate_runtime_parity/test_main.cpp`;
- `test/test_climate_v6/test_main.cpp`;
- `tests/test_climate_replay.py` and related climate trace/runtime tests.

Migration must preserve useful semantic tests while moving tests from implementation-chain assumptions to contracts: intent, policy resolution, dwell, safety precedence, transport result, and reconciliation.

No tests were run during this A0 audit by design.

## 1.15 DRAM and stack impact

Current relevant facts:

- `runClimateV6RealInputRuntime()` is non-returning, so ordinary local objects live for the lifetime of the main task stack.
- Stage28E already moved `RuntimeIoOwner` and `RuntimeControlOwner` to static storage, reducing persistent main-stack residency for their members.
- RF-enabled historical qualification uses a larger main-task stack (16 KiB) than fake RF-disabled builds (12 KiB), and that evidence must not be invalidated casually.
- `Stage27TelemetryLogger` allocates its queue storage preferentially from PSRAM and runs persistence on its own task.
- the current endpoint/arbiter/safety state objects are small fixed-size structures; the major architectural risk is not those few bytes but adding duplicated policy/state objects or large transient plans to the main stack.

Target implementation guidance:

- keep `ControlIntent`, `SafetyEnvelope`, endpoint state, plan/report entries as fixed-size POD/enum-heavy structures;
- size arrays to the small validated endpoint count rather than using heap containers;
- avoid `std::string`, maps, function wrappers, or per-tick allocation in the supervisor hot path;
- keep durable configuration compact and versioned;
- prefer a long-lived statically owned supervisor/state store if measurements show persistent stack pressure;
- avoid copying large telemetry/config structures through multiple layers;
- preserve one-task synchronous resolution initially so no additional supervisor task/stack is needed unless evidence later justifies it.

A separate build/size/stack measurement belongs to implementation verification, not this read-only audit.

---

# 2. Architectural problems

## P1. Physical execution has multiple owners

Current physical execution can be initiated by:

- normal climate chain;
- direct scheduled-lamp path;
- startup safe-state code;
- runtime fault recovery;
- ClimateControlLoop fail-safe;
- thermal-test path;
- service-console manual RF;
- RF auto-smoke.

The low-level RMT function is shared, but ownership is not centralized.

## P2. Safety is duplicated into execution layers

The lamp safety decision is copied into both the binary arbiter and RF endpoint as `safety_force_exhaust_`. Safety policy therefore leaks into multiple execution layers.

## P3. Lamp schedule is a separate physical-output owner

Lamp schedule/safety directly writes the endpoint rather than expressing an intent/constraint to the same resolver used by climate outputs.

## P4. Fault recovery is duplicated

`ClimateControlLoop` executes fail-safe OFF, then runtime code may independently perform endpoint-level safe-state retries and disable real outputs.

## P5. State semantics overclaim certainty

Endpoint `known/on` means a TX-completed command cache, not known physical state. Telemetry names do not consistently expose that uncertainty.

## P6. The RF diagnostics component is also the production transport

The normal endpoint calls `Stage28RfDiagnostics::manualTransmit()`. The same object serves production transport, manual console commands, passive receive, and auto-smoke. This makes maintenance and production authority difficult to isolate.

## P7. `fake-locked` is not a global RF lock

Manual console RF can transmit while automatic outputs are fake-locked. Auto-smoke can also transmit when enabled. The mode name is therefore narrower than its apparent safety meaning.

## P8. No explicit Automation OFF lifecycle state exists

Compile-time real-output enable and one-way `disableReal()` are not the target runtime policy state. Boot/disable/recovery/fault behavior cannot currently be configured per endpoint.

## P9. Boolean application results hide partial execution

Several layers can partially execute a sequence and return one aggregate false. Recovery cannot reason from a structured per-step execution report.

## P10. Decision/execution reconciliation is tied to the current actuator chain

`confirmed_applied`, `previous_applied_`, and the effective estimator rely on downstream driver behavior. They must survive migration without treating RF TX completion as physical confirmation.

## P11. There are two safety families that must not be conflated

Climate policy safety inside `ClimateRuntimeController` and hard lamp thermal safety solve different problems. A refactor that blindly moves every function named `safety` into one class could change climate semantics.

## P12. Main-loop serialization is implicit, not contractual

Current transport safety partly depends on service console, diagnostics, schedule, climate, and recovery being called sequentially from one task. The new architecture should make single-writer serialization explicit.

---

# 3. Reconciliation with `docs/OUTPUT_EXECUTION_ARCHITECTURE.md`

The design is directionally consistent with the audited code.

The latest `ff769096...` documentation-only delta already corrected the two material source assumptions discovered before this full audit:

1. RF auto-smoke is a direct transmit path.
2. There is no suitable existing product output configuration/state store to reuse today.

Additional facts that implementation must explicitly preserve:

- current runtime Automation OFF does not exist as a normal runtime lifecycle API; it must be introduced rather than inferred from `disableReal()`;
- climate-policy `safety()` inside `ClimateRuntimeController` is separate from hard thermal `LampSafetyController` safety;
- production RF currently reaches the same `Stage28RfDiagnostics` object used by manual/auto-smoke diagnostics;
- `fake-locked` does not block every RF transmit path;
- current fail-safe and endpoint initialization are best-effort multi-step operations with possible partial success.

None of these facts requires changing the core target invariant or target diagrams. They refine migration requirements rather than invalidate the design baseline. No further edit to `OUTPUT_EXECUTION_ARCHITECTURE.md` is required before A1.

---

# 4. Proposed target structure

```text
ClimateRuntimeController
  -> ControlIntent

Schedule source
  -> ScheduleIntent

Service/manual API
  -> ManualIntent

Climate input-safety sanitation (where semantics belong to climate policy)
  -> ControlIntent

Lamp thermal safety and future hard output protections
  -> SafetyPolicyEngine
  -> SafetyEnvelope

OutputPolicyConfig
  -> endpoint binding
  -> Boot / AutomationOff / Recovery / Fault policy
  -> order + bounded delay/retry semantics

                        +-------------------+
ControlIntent ---------->|                   |
ScheduleIntent ---------->| OutputSupervisor |----> OutputPlan
ManualIntent ------------>| single writer     |          |
SafetyEnvelope ---------->| mode/policy/state |          v
Lifecycle event --------->|                   |    RF433OutputTransport
                        +-------------------+          |
                                  |                    v
                                  +------------> TxResult
                                  |
                                  v
                           OutputStateStore
                     desired / resolved /
                     last-command-attempt /
                     transport-result /
                     physical=Unknown unless
                     independent feedback exists
```

`BinaryActuatorPolicy` is a deterministic supervisor dependency used during resolution. It owns threshold/dwell state but never transport, endpoint mapping, thermal evaluation, or global mode.

The initial supervisor should execute synchronously in the existing main control task. Intent producers must not call transport. This preserves current serialization and avoids adding a new FreeRTOS task/stack during the first migration.

---

# 5. Migration map of current classes

| Current component | Observed responsibility today | Target treatment |
|---|---|---|
| `ClimateRuntimeController` | climate decision, climate-policy safety, trend/effective estimator | keep decision engine; emit `ControlIntent`; retain only safety rules that are intrinsic climate-policy semantics; reconcile from supervisor execution projection |
| `ClimateControlLoop` | sampling, decision, physical apply, fail-safe execution, previous-applied, fault latch | split; remove transport/fail-safe ownership; eventually become decision-cycle orchestration or retire |
| `ClimateActuatorAdapter` | six-role apply, aggregate bool, applied projection, fail-safe OFF | transitional intent adapter, then retire |
| `SwitchableRoleDriver` | fake-vs-real routing and one-way disable | replace with supervisor mode; retire |
| `Stage28dBinaryRoleArbiter` | binary hysteresis/dwell, output calls, safety force, command-state projection | extract `BinaryActuatorPolicy`; remove downstream driver and safety transport flag |
| `MappedClimateRoleDriver` | role -> endpoint mapping and endpoint calls | move mapping into validated `OutputPolicyConfig`; retire |
| `Stage28dRfOutputEndpoint` | endpoint thresholding, lamp special case, safety force, cache, RF frame lookup, TX | split into RF433 transport + supervisor/state-store responsibilities; retire monolith |
| `DiagnosticsRfTransmitter` | production adapter into diagnostics manual TX API | replace with dedicated RF433 output transport |
| `Stage28RfDiagnostics` | RMT ownership, manual TX/RX, passive capture, auto-smoke | separate transport mechanics from diagnostics; low-level diagnostics only under maintenance guard |
| `LampSafetyController` | thermal latch/recovery + schedule-lamp effective decision + force fan | preserve thermal state machine; adapt to `SafetyEnvelope`; schedule demand becomes separate `ScheduleIntent` |
| `Stage28ServiceConsole` | UART/parser/diagnostics + direct RF manual path | normal configured-output commands -> `ManualIntent`; raw RF only under explicit maintenance mode |
| `RuntimeControlOwner` | static lifetime owner for controller/safety/test sequence | evolve into composition owner for supervisor/policy/state where appropriate |
| `runClimateV6RealInputRuntime()` | composition root plus direct schedule/output/recovery policy | reduce to composition + cycle orchestration; no physical-output policy |
| `Stage27TelemetryLogger` | async append-only telemetry | keep separate; consume supervisor execution telemetry, not become settings store |
| H/recovery scripts | bounded qualification/recovery via console/tooling | keep historical; rewrite qualification against supervisor after software migration |

---

# 6. Decisions still required

1. **Climate-policy safety boundary:** decide rule-by-rule which `ClimateRuntimeController::safety()` behaviors remain intrinsic control-intent sanitation and which, if any, must become non-bypassable `SafetyEnvelope` rules. Do not move them solely because they are named safety.
2. **Maintenance mode:** define the exact guard for raw RF diagnostics. Minimum requirement: explicit maintenance mode, normal supervisor automatic execution blocked, state uncertainty recorded, and a deliberate exit/re-arm procedure. Thermal safety implications must be explicit.
3. **Automation OFF API:** define the operator/API transition into `Disabled`; current firmware has no equivalent normal runtime state.
4. **Lifecycle default policy:** choose exact Boot/AutomationOff/Recovery/Fault actions per lamp, exhaust, humidifier before A4/A6. The architecture document's table is illustrative only.
5. **RestoreLastCommand semantics:** decide whether restore means re-transmit last commanded state unconditionally or conditionally; it can never mean restore known physical state.
6. **Retry/fault policy:** define bounded retries and containment for partial plans and transport failure.
7. **Execution projection naming:** replace `confirmed_applied` with terminology that cannot be read as physical acknowledgement.
8. **Independent feedback:** Shelly aggregate power remains telemetry/evidence, not endpoint acknowledgement unless a future explicit feedback provider can attribute the load safely.

---

# 7. Proposed small-commit sequence

The design sequence is valid; the audit recommends the following concrete cut points.

### A0 — audit documentation

This document only. No production behavior change.

### A1 — execution contracts/types

Add fixed-size host-testable types only:

- `ControlIntent`;
- `ScheduleIntent`;
- `ManualIntent`;
- `SafetyEnvelope`;
- `OutputCommand` / `OutputPlan`;
- `TxResult`;
- `ExecutionReport`;
- endpoint/mode/reason enums.

No production wiring change.

### A2 — dedicated RF433 transport extraction

Extract frame lookup + RMT transmit contract from `Stage28RfDiagnostics`/endpoint without changing call order or output decisions. Keep the legacy endpoint temporarily using the new transport. Focused host tests prove identical frame selection/result semantics.

### A3 — command-state model

Introduce an in-memory `OutputStateStore` with explicit `desired/resolved/last_commanded/transport_result/physical_unknown` semantics. Initially mirror existing endpoint behavior; no lifecycle policy yet.

### A4 — binary policy extraction

Turn `Stage28dBinaryRoleArbiter` hysteresis/dwell state machine into transport-free `BinaryActuatorPolicy`. Preserve thresholds, dwell, held-state projection, and safety/lifecycle bypass semantics in focused tests.

### A5 — safety envelope split

Adapt `LampSafetyController` so thermal protection emits constraints/forced actions. Split schedule demand into `ScheduleIntent`. Remove endpoint-level duplicate `safety_force_exhaust_` only when the supervisor path can preserve behavior.

### A6 — minimal `OutputSupervisor` in compatibility mode

Introduce one synchronous supervisor execution path and route existing normal climate + lamp schedule through it while reproducing current startup/automatic behavior. Initially keep lifecycle configuration equivalent to current hard-coded policy.

### A7 — climate reconciliation migration

Make climate emit `ControlIntent`. Move `previous_applied_`/execution projection boundary so `reconcileApplied()` consumes supervisor execution reports. Preserve effective estimator behavior with focused tests.

### A8 — lifecycle state machine + policy

Add Boot/Automatic/Recovering/Disabled/FaultLocked and per-endpoint lifecycle actions. This is where normal Automation OFF behavior becomes explicit. Keep safety active in Disabled.

### A9 — persistence/configuration

Add one versioned NVS-backed output policy/state store if no suitable product store has appeared. Persist only bounded meaningful transitions; never claim physical acknowledgement.

### A10 — console/maintenance migration

Route normal configured-output console commands through supervisor `ManualIntent`. Put raw RF transport diagnostics behind explicit maintenance guard. Remove `fake-locked` ambiguity.

### A11 — legacy-owner removal/invariant enforcement

Delete direct scheduled-lamp writes, runtime direct recovery output ownership, legacy driver chain pieces, endpoint safety flags, and other bypasses once replacements are proven. Add compile/link/test enforcement where practical that only the output execution module can reach configured-output transport.

### A12 — software qualification

Focused host tests accompany behavior-changing commits. After architecture stabilizes, run exactly one full software gate and record the exact new firmware identity.

### A13 — new H qualification plan

Only after explicit operator authorization: rewrite H against `OutputSupervisor`, then use `/dev/cu.usbserial-1130` only. Never touch `/dev/cu.usbserial-10`.

---

# 8. Audit conclusion

The core architecture problem is confirmed by source: the project already has a mostly linear normal climate chain, but physical-output authority is distributed around it. Lamp schedule, safety translation, startup, fail-safe, runtime recovery, service-console RF, auto-smoke, and thermal qualification can all reach physical execution outside a single owner.

The target `OutputSupervisor` architecture is therefore justified and should be implemented incrementally. The safest first implementation move is not a giant controller rewrite: define contracts, separate the RF transport, make command state honest, extract binary policy, then introduce the supervisor while preserving current behavior at each cut point.

No hardware qualification from the old architecture should be treated as qualification of production C++ after these changes.
