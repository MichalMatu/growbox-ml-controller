# Stage28E Guidance — Runtime Diagnostics, Architecture Hardening, and Memory Optimization

## Purpose

This document is the mandatory execution guide for the next development stage of the Growbox ML controller.

Stage28D functional development is intentionally paused. Before returning to AH ventilation / binary-arbiter functional work, the firmware must gain enough observability, crash evidence, memory headroom understanding, and architectural clarity to diagnose failures from evidence rather than inference.

This is not a temporary debugging checklist. The useful parts of the diagnostics architecture are expected to remain part of the product.

## Current starting point

Repository and execution identity:

- repository: `MichalMatu/growbox-ml-controller`
- work branch: `mvp/environment-controller`
- control branch: `agent-control`
- Local Agent binding: `815cf40f-8d2a-4e1f-b7cc-c0f4e37b6cb5`
- correct Growbox serial device: `/dev/cu.usbserial-1130`
- `/dev/cu.usbserial-10` belongs to another project and must never be opened, probed, monitored, reset, or flashed

Safety invariants remain unchanged:

- the rule controller remains authoritative
- ML remains shadow / research only
- thermal safety trip is `>= 28 C`
- thermal recovery requires `<= 26 C` continuously for 10 minutes
- manual RF remains deliberately blocked during `real-bounded`; do not bypass it
- Shelly master must remain ON
- after any hardware diagnostic run, restore the safe fake-locked firmware/state

Stage28D is paused because the V5 AH arbiter run produced evidence inconsistent with a continuously living arbiter instance. The cumulative dwell-hold counter decreased during one run even though normal arbiter code has no reset path for that counter. The leading possibilities include runtime reset/reboot, object reconstruction, memory corruption, power/brownout, watchdog, stack exhaustion, heap pressure, or another system-level fault. Do not assume the arbiter transition algorithm itself is the root cause until the runtime can prove or disprove these possibilities.

The previously discussed observation of approximately 1 KiB free internal DRAM is **not yet accepted as a confirmed measurement**. Stage28E must measure current, minimum-ever, and largest-block values directly under representative runtime load.

## Mandatory execution policy

The phases below are sequential: **A -> B -> C -> D -> E -> F -> G -> H**.

Do not skip a phase because a likely cause appears obvious.

For every phase A-G:

1. Record the starting Git SHA and the intended scope.
2. Make the smallest coherent set of changes for that phase.
3. Run focused tests while editing.
4. Run the phase exit verification defined below.
5. Capture before/after measurements where applicable.
6. Update this document or the appropriate status/handoff document with material findings.
7. Commit the completed phase separately with an English commit message.
8. Record the resulting commit SHA before starting the next phase.
9. If a phase fails its exit criteria, stay in that phase; do not continue forward.

Verification policy:

- use focused/unit/host tests during iteration
- use build and size evidence whenever firmware/configuration changes
- do not repeatedly run the full repository gate after every small edit
- run one appropriate phase-exit gate after each phase
- when Local Agent `efficient-verification-v1` is used, keep exactly one final `full` verification stage per task
- a commit proves publication, not runtime correctness

Hardware policy during Stage28E:

- no AH feature development or uncontrolled actuator experiments
- diagnostic firmware may be run only when a phase explicitly requires runtime evidence
- hardware runs must be bounded and use only `board:growbox-s3`
- use only `/dev/cu.usbserial-1130`
- preserve all thermal/output safety interlocks
- restore safe fake-locked state after every hardware run
- do not run a long soak until Phase G

Refactoring policy:

- instrumentation before optimization
- measurement before moving memory
- preserve behavior while observability is being added
- do not combine broad architecture refactoring with an unresolved functional change
- no blind allocator-threshold changes and no blanket “move everything to PSRAM” changes

---

# Phase A — Observability foundation

## Goal

Create a coherent, low-overhead diagnostics and logging foundation that can identify what the firmware was doing, on which boot, in which subsystem, and with what resource state.

## Required work

### A1. Structured logging facade

Introduce one firmware logging facade instead of ad-hoc formatting in critical paths.

Required log levels:

- `ERROR`
- `WARN`
- `INFO`
- `DEBUG`
- `TRACE`

Required logical modules at minimum:

- `SYS`
- `MEM`
- `TASK`
- `BLE`
- `SENSOR`
- `CONTROL`
- `AH`
- `ARBITER`
- `RF`
- `SHELLY`
- `STORAGE`
- `TELEMETRY`
- `SAFETY`
- `WATCHDOG`

Design requirements:

- compile-time inexpensive when disabled
- module-specific level filtering
- no dynamic string construction in hot paths
- prefer constant format strings, enums, POD values, `string_view`, or fixed buffers
- no per-loop heap allocation solely for logging
- support a compact human-readable serial form first; machine-readable event IDs may be added where useful

Every critical log record should be able to include or derive:

- uptime / monotonic time
- boot/session ID
- sequence/event number
- level
- module
- task and core where practical

### A2. Boot/session identity

Add an explicit boot/session identifier visible in diagnostic logs and status output.

At boot capture at minimum:

- firmware SHA / build identity
- `esp_reset_reason()`
- boot/session ID
- startup uptime reference
- relevant previous crash/coredump availability when implemented later

The purpose is to distinguish:

- counter reset caused by reboot
- object reconstruction during the same boot
- memory corruption without reboot

### A3. Memory metrics

Expose at minimum:

Internal memory:

- total where available/useful
- current free bytes
- minimum-ever free bytes
- largest free block

PSRAM:

- total
- current free bytes
- minimum-ever free bytes
- largest free block

Prefer ESP-IDF heap-capability APIs and report capability-specific values rather than ambiguous generic heap numbers.

### A4. Task/stack instrumentation

Create a diagnostic task registry/snapshot that can report, for every important task:

- task name
- core affinity/current core where meaningful
- priority
- configured or known stack size where available
- current high-water mark
- worst observed high-water mark
- units converted explicitly to bytes

Do not assume the FreeRTOS high-water API units without verifying the project’s ESP-IDF/FreeRTOS version.

Define warning thresholds, initially as diagnostics rather than fatal behavior, for example:

- warning below 25% stack margin
- critical diagnostic below 10%

Thresholds may be refined after baseline measurements.

### A5. Loop and subsystem timing

Measure execution cost without materially perturbing runtime.

Candidate metrics:

- sensor update time
- control evaluation time
- AH policy time
- arbiter time
- RF operation time
- telemetry serialization time
- BLE cycle/scan processing time
- main loop duration
- maximum loop duration
- overrun count

Do not add expensive tracing to every iteration if sampled or aggregate counters are sufficient.

## Phase A tests

Focused tests must cover:

- log level/module filtering
- formatting does not allocate dynamically in selected hot-path helpers where testable
- boot/session identity representation
- memory metric helpers on host via abstraction/mocks where practical
- stack watermark conversion/helper behavior
- timing accumulator correctness and overflow/wrap handling

Firmware verification:

- build succeeds
- binary/static memory size is recorded
- no existing control behavior changes in host tests

Bounded hardware diagnostic after software PASS:

- flash diagnostic build safely
- capture boot identity/reset reason
- capture internal/PSRAM free, min-free, largest block
- capture real stack HWM for all registered tasks
- capture timing metrics under normal sensor/BLE/telemetry operation
- do not run AH actuator transition experiments
- restore safe fake-locked state

## Phase A exit criteria

Phase A is complete only when one diagnostic snapshot can answer:

- which boot is running?
- why did it boot/reset according to ESP-IDF?
- how much internal heap is free now, how low has it gone, and what is the largest allocatable block?
- same for PSRAM?
- which task has the lowest stack margin?
- what is the worst observed control-loop latency?

Commit Phase A separately.

---

# Phase B — Crash, reset, corruption, and lifecycle diagnostics

## Goal

Make resets, watchdogs, crashes, object reconstruction, and detectable memory corruption leave durable evidence.

## Required work

### B1. Flash coredump support

Add a coredump partition to the 8 MiB flash layout after verifying exact flash bounds, application size, telemetry partition requirements, alignment, ESP-IDF version, and required coredump partition size.

Requirements:

- verify the exact ESP-IDF coredump configuration symbols from the installed SDK; do not guess them
- prefer flash coredump
- prefer ELF format if supported and practical for useful post-mortem analysis
- verify checksum support
- evaluate DRAM capture support and limitations
- do not assume PSRAM content will be captured
- make coredump presence/status queryable from the service console or boot diagnostics

The previous partition table had no coredump partition, so historical crashes from that layout cannot be assumed recoverable.

### B2. Persistent crash breadcrumbs

Persist a minimal crash/reset breadcrumb set in an appropriate durable mechanism, keeping writes bounded.

Candidate fields:

- boot/session ID
- last event sequence
- last critical subsystem heartbeat
- last controller state
- last arbiter state
- last safety state
- last memory low-water snapshot
- last task/loop timing alarm

Do not introduce high-frequency flash wear.

### B3. Object lifecycle tracking

For critical long-lived state objects, add debug-build lifecycle evidence:

- instance ID
- constructor count
- optional destructor count
- creation timestamp/boot ID

Initial target objects should include at least the Stage28D binary arbiter and any runtime owner whose reconstruction would recreate it.

A second arbiter construction in one boot must become visible immediately.

### B4. State integrity sentinels

For selected critical state structures in diagnostic/heavy-diagnostic builds, evaluate guard/magic values or equivalent invariants that detect overwrite/corruption.

Requirements:

- cheap enough not to destabilize production logic
- assertions/logging must report the affected object and boot/session
- no undefined behavior introduced by the diagnostic itself

### B5. Heap integrity checks

Introduce optional heavy-diagnostic heap-integrity checks at carefully selected boundaries, such as:

- before/after BLE processing
- before/after telemetry serialization
- before/after storage writes
- around suspicious allocation-heavy operations

Do not run full heap validation every control-loop iteration.

### B6. Watchdog/heartbeat diagnostics

Add subsystem heartbeats/ages where they materially help distinguish deadlock, starvation, and long blocking work.

At minimum consider:

- sensor runtime
- control runtime
- BLE runtime
- telemetry runtime
- RF/output runtime

## Phase B tests

- validate partition layout and flash bounds
- build diagnostic and release profiles
- test lifecycle counters/instance IDs
- test state-integrity detection helper without corrupting real runtime state
- test heartbeat age/timeout calculations
- verify coredump tooling against a controlled synthetic crash only if it can be done safely and bounded

Hardware verification, if a controlled crash test is used:

- it must not energize outputs unexpectedly
- confirm coredump is written
- confirm it can be read/decoded using the exact built ELF
- restore safe firmware/state afterward

## Phase B exit criteria

After an intentional diagnostic reset/crash, the system must provide enough evidence to distinguish at least:

- normal boot
- software reset
- watchdog/crash reset when reported by platform
- coredump present/absent
- arbiter/runtime object reconstructed in the same boot vs after a new boot

Commit Phase B separately.

---

# Phase C — Memory map, stack audit, and resource baseline

## Goal

Build a quantitative map of where DRAM, PSRAM, task stack, static storage, and large runtime objects are consumed before changing architecture.

## Required work

### C1. Static/linker memory audit

Collect and record:

- `.data`
- `.bss`
- IRAM usage
- flash text/rodata
- static DRAM contributors where map-file tooling permits
- overall firmware size

Keep a machine-readable or reproducible report if practical.

### C2. Runtime object inventory

Create an inventory of long-lived and large objects, including at minimum:

- type/object name
- `sizeof`
- owner
- lifetime
- current storage location: stack/static/internal heap/PSRAM
- whether it requires INTERNAL/DMA capability
- whether moving it is safe and beneficial

Pay special attention to objects created as locals inside the non-returning climate runtime function. Such objects are semantically local but can occupy `app_main` stack for the lifetime of the firmware.

### C3. Stack frame/code-depth audit

Inspect critical call paths for:

- large local arrays/structures
- accidental copies of large objects
- deep nested calls
- recursive code
- large temporary formatting buffers
- exception-like error paths that create extra stack pressure

Use compiler/map/static-analysis support where available; combine it with real HWM measurements from Phase A.

### C4. Allocation-path audit

Classify allocations by capability and lifetime:

- internal-only
- DMA/internal
- generic `malloc/new`
- explicit PSRAM
- library-managed Wi-Fi/BLE allocations
- transient serialization allocations

The board already enables PSRAM and configures generic allocator preference for larger allocations, but this only affects eligible dynamic allocations. It does **not** automatically move task stacks, globals/statics, or automatic/local stack objects to PSRAM.

### C5. Fragmentation and peak-load measurement

Measure memory during representative operations:

- boot
- idle
- BLE activity
- sensor refresh
- telemetry serialization/write
- service-console diagnostics
- normal control loop

Record current, minimum-ever, and largest-block values.

## Phase C tests

Phase C may be mostly measurement/tooling, but all analysis scripts/helpers must have deterministic tests where appropriate.

Required evidence:

- build size/map baseline
- task stack HWM table
- runtime internal/PSRAM baseline table
- large-object inventory
- identified top memory-risk items ranked by evidence

## Phase C exit criteria

No broad memory optimization starts until the project can answer:

- what consumes static DRAM?
- what consumes long-lived stack?
- what consumes internal heap?
- which allocations are PSRAM-eligible?
- which task has the least real margin?
- whether the suspected ~1 KiB internal-free condition is real, transient, minimum-ever, or incorrect

Commit Phase C separately, including the baseline report/documentation.

---

# Phase D — Architecture hardening and ownership cleanup

## Goal

Reduce “god object” behavior, unclear ownership, hidden lifetime coupling, and permanent stack residency without changing control semantics.

## Required work

Refactor only from evidence gathered in A-C.

Target architecture direction:

```text
SystemRuntime
  SensorRuntime
  ControlRuntime
    RuleController
    AhController
    BinaryArbiter
  OutputRuntime
    RfOutput
    ShellyFeedback
  SafetyRuntime
  DiagnosticsRuntime
  TelemetryRuntime
```

This is a direction, not a requirement to force exactly these classes if a simpler design is better.

Required principles:

- explicit ownership
- explicit lifetime
- no hidden reconstruction of long-lived control state
- clear separation of sensing, decision, safety, output, telemetry, and diagnostics
- avoid one non-returning function owning many large automatic objects on one task stack
- use RAII where it improves correctness without hiding critical embedded lifetimes
- keep safety and rule-controller authority intact
- keep hardware interfaces testable behind narrow abstractions

Move one coherent responsibility at a time. Do not perform a giant rewrite.

## Phase D tests

After each coherent refactor chunk:

- focused unit/host tests
- no behavior changes to existing controller/arbiter semantics
- build and size comparison

Phase exit verification:

- full relevant host/software gate
- compare stack HWM/static DRAM/runtime heap to Phase C baseline
- bounded runtime check only if needed to validate ownership/lifetime behavior

## Phase D exit criteria

- long-lived objects have clear owners
- critical state cannot be silently recreated by routine control-flow re-entry
- large automatic objects on persistent stacks are eliminated or explicitly justified
- tests demonstrate unchanged control behavior
- memory/stack metrics are no worse without documented reason

Commit Phase D separately.

---

# Phase E — Memory, allocation, and hot-path optimization

## Goal

Recover robust internal-memory and stack margin using measured, low-risk changes.

## Required work

### E1. Selective PSRAM placement

Move only proven PSRAM-eligible data, such as large non-DMA buffers, caches, history, telemetry buffers, or other non-time-critical storage.

Use explicit capability-aware allocation when it gives stronger guarantees than generic allocator preference.

Do not blindly move:

- ISR data
- DMA buffers
- task stacks without platform-supported design and evidence
- internal-only synchronization/runtime structures
- latency-critical tiny objects where PSRAM adds complexity for no gain

### E2. Remove heap churn from hot paths

Audit and reduce:

- `std::string` construction
- Arduino `String` churn if present in critical paths
- `std::stringstream`
- repeated JSON object construction
- temporary vectors/containers
- repeated allocation/free patterns
- large local `snprintf` buffers

Prefer where appropriate:

- constant format strings
- enums/event IDs
- `constexpr`
- `string_view`
- POD telemetry records
- fixed-capacity buffers with explicit bounds
- preallocated/reused serializers

### E3. Stack right-sizing

Do not reduce stack sizes from configuration guesses.

Use measured HWM plus a deliberate safety margin. Increase stacks that are dangerously low; reduce only clearly oversized stacks when recovered DRAM is useful and the workload has been exercised sufficiently.

### E4. BLE/Wi-Fi/library allocation review

Inspect the exact ESP-IDF/NimBLE configuration and identify supported PSRAM/internal-memory options rather than guessing symbols.

### E5. Fragmentation reduction

Prefer stable long-lived allocation patterns. Avoid introducing pools unless evidence shows they solve a real fragmentation/latency problem.

## Phase E tests

For each optimization:

- focused behavior tests
- build
- before/after static size where relevant
- before/after internal free/min/largest block
- before/after PSRAM metrics
- before/after stack HWM
- before/after loop timing for hot-path changes

Regressions in latency or reliability must be treated as failures even if free memory improves.

## Phase E exit criteria

Define final numeric acceptance thresholds from Phase C evidence. At minimum, the result must show a materially safer internal-memory/stack margin than the pre-optimization baseline, without control-behavior regression.

Commit Phase E separately.

---

# Phase F — Diagnostic validation and regression hardening

## Goal

Prove that the new observability and optimized architecture accurately report known fault classes and remain useful under representative load.

## Required work

Create targeted regression tests for the Stage28D symptom family.

At minimum include a V5-inspired arbiter continuity regression:

- synchronize safe OFF
- exercise below-threshold and `~0.111` requests around minimum-OFF dwell
- verify cumulative dwell-hold count is monotonically non-decreasing for one arbiter instance
- after required dwell expiry, verify an eligible `0.111` request can transition ON in pure arbiter logic

The purpose is to prove that the observed V5 counter decrease cannot arise from normal continuous execution of the current counter semantics.

Also validate:

- boot/session change is visible across reset
- lifecycle instance IDs behave as expected
- stack/memory alarms trigger correctly in synthetic tests
- diagnostic logging does not create material heap churn
- release build can compile diagnostics down to intended cost

## Phase F tests

- focused regression suite
- host tests
- build all relevant diagnostic/release profiles
- static analysis/formatting gates used by the repository
- one final full software quality gate for the Stage28E implementation

If the full gate finds a defect and source changes, rerun the affected focused gate and then rerun the final full gate.

## Phase F exit criteria

- full software gate passes
- no unresolved instrumentation defects
- no known diagnostics-induced instability
- baseline/after comparison documented

Commit Phase F separately.

---

# Phase G — Bounded runtime validation and soak

## Goal

Validate the hardened firmware on real hardware before resuming AH functional work.

## Required work

Start with short bounded runtime checks using safe fake-locked outputs.

Validate:

- stable boot/session ID
- reset reason remains expected
- no unexplained object reconstruction
- no heap-integrity errors
- no stack warning/critical events
- internal heap minimum and largest-block remain within accepted margins
- PSRAM remains healthy
- loop timing remains bounded
- BLE/sensors/telemetry continue operating
- no unexpected coredump appears

Only after short checks pass, run the planned diagnostic soak of sufficient duration to exercise the normal workload. The duration should be chosen from evidence, not automatically inherited from older soak plans.

During the soak, preserve periodic low-overhead summaries rather than TRACE flooding.

If a reset occurs:

1. stop treating the run as a normal pass
2. collect reset reason
3. collect coredump before overwriting evidence
4. collect boot/session transition
5. inspect last breadcrumbs/memory/task state
6. return to the earliest relevant phase rather than continuing to H

## Phase G exit criteria

- no unexplained reset/reinitialization during the agreed representative runtime window
- memory minima and largest-block values remain above accepted thresholds
- stacks retain accepted margin
- no runaway fragmentation trend
- no diagnostics-induced timing failure
- coredump path has been demonstrated usable or explicitly documented if no crash occurred

Commit Phase G separately with the validated runtime baseline/status update.

---

# Phase H — Controlled return to Stage28D AH/arbiter work

## Goal

Resume the original functional issue only after the platform can explain failures reliably.

## Entry conditions

Phases A-G must all be complete with recorded commits and passing exit criteria.

## First AH task after hardening

Do not immediately run a long soak.

First perform one short, bounded hardware confirmation of the complete path:

`AH/rule request -> binary arbiter -> RF -> physical fan`

Required evidence:

- requested fan value
- arbiter pre-state
- dwell elapsed / dwell decision
- arbiter instance ID and boot/session ID
- transition decision
- RF send result
- physical/Shelly evidence of fan ON where available
- memory and stack snapshot near the transition
- no safety override unless intentionally triggered

After the confirmation, restore safe fake-locked firmware/state.

If the problem reproduces, use the new diagnostics and coredump/breadcrumb evidence before changing functional code.

## Phase H completion

Only after the bounded functional path is understood should normal Stage28D continuation resume.

---

# Required profiles

Maintain three conceptual build/logging profiles where practical:

## `release`

- minimal production logging
- persistent essential boot/reset/safety evidence
- low runtime overhead

## `diagnostic`

- memory metrics
- task/stack metrics
- lifecycle IDs
- timing summaries
- module-level DEBUG as needed

## `heavy-diagnostic`

- TRACE where targeted
- heap integrity checks
- state sentinels/assertions
- additional lifecycle/corruption diagnostics

Heavy diagnostics must not become the default production configuration.

---

# Phase tracking table

Update this table as work progresses.

| Phase | Status | Start SHA | Result commit | Key evidence / notes |
|---|---|---|---|---|
| A — Observability foundation | NOT STARTED | — | — | — |
| B — Crash/reset/corruption diagnostics | NOT STARTED | — | — | — |
| C — Memory/stack/resource baseline | NOT STARTED | — | — | — |
| D — Architecture hardening | NOT STARTED | — | — | — |
| E — Memory/hot-path optimization | NOT STARTED | — | — | — |
| F — Regression hardening/full software gate | NOT STARTED | — | — | — |
| G — Bounded runtime validation/soak | NOT STARTED | — | — | — |
| H — Return to AH/arbiter functional work | BLOCKED ON A-G | — | — | — |

Allowed status values:

- `NOT STARTED`
- `IN PROGRESS`
- `BLOCKED`
- `PASS`
- `FAIL`

---

# Required evidence log per phase

At the end of each phase, record at minimum:

```text
phase:
start_sha:
result_commit:
focused_tests:
phase_exit_gate:
firmware_build:
flash_size:
static_dram:
internal_free_current:
internal_free_min:
internal_largest_block:
psram_free_current:
psram_free_min:
psram_largest_block:
lowest_stack_hwm_task:
lowest_stack_hwm_bytes:
max_loop_us:
hardware_run_used:
hardware_restored_safe:
open_findings:
```

Fields that do not apply to a documentation-only or software-only phase may be marked `N/A`, but must not be silently omitted when they are expected evidence for that phase.

---

# Stop conditions

Stop forward progression and investigate when any of the following occurs:

- unexplained boot/session change
- cumulative counter decreases within the same proven object instance without documented wrap semantics
- coredump/crash appears unexpectedly
- stack enters critical margin
- internal heap minimum approaches an unsafe margin
- largest internal free block collapses despite apparently adequate total free memory
- heap integrity check fails
- control-loop timing becomes unbounded or watchdog-relevant
- safety behavior changes
- Shelly/output state cannot be restored to the known safe condition

Do not mask these signals by immediately increasing stack, lowering logging, changing allocator thresholds, or moving random objects to PSRAM. Preserve the evidence first.

# Definition of success for Stage28E

Stage28E is successful when the firmware can provide evidence for **why** it reset or reconstructed state, has measured and acceptable memory/stack margins, has clear runtime ownership, avoids unnecessary hot-path allocation/string churn, and survives representative runtime validation without unexplained state loss.

Only then resume normal AH/arbiter functional development.
