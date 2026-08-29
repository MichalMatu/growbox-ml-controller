# Fresh-context continuation plan

Date: 2026-08-29
Work branch: `mvp/environment-controller`
Control branch: `agent-control`
Primary Stage27 handoff: `docs/STAGE27_NATIVE_IDF_HANDOFF.md`
Software-only Stage26C baseline: `bbf8684d2817f630ddca08837ddc8860a28eb660`

This document is the bootstrap point for a new ChatGPT conversation. Read it together with
`AGENTS.md`, `docs/CURRENT_STATUS.md`, `docs/STAGE27_NATIVE_IDF_HANDOFF.md`,
`docs/HARDWARE_BRINGUP_CHECKLIST.md`, `docs/ARCHITECTURE.md`, and
`docs/ML_DECISION_REPORT.md` before planning new work.

## Product state

The current product path is climate-v6 (`climate-mvp-v1`):

- 44 runtime-observable features;
- 6 semantic ML-controlled outputs: heater, cooler, exhaust fan, humidifier, dehumidifier and CO2 doser;
- bounded research network `44 -> 32 -> 32 -> 6`;
- Rule is the authoritative runtime policy;
- `MlShadow` evaluates ML without controlling hardware;
- `MlActive` is research-only and is not qualified for real growbox actuation;
- deterministic arbitration and safety remain authoritative over every proposal;
- effective actuator state advances only from confirmed/final applied semantic actions.

Completed work includes the ML research/qualification path through Stage16, the climate-v6 runtime,
Python/C++ parity, trace/replay/counterfactual tooling, fail-closed `ClimateControlLoop`, actuator
fault handling, virtual HIL, real ESP-IDF v5.5.4 compilation, and the complete software-only
hardware-neutral preparation through Stage26C.

Do not repeat those stages unless new evidence demonstrates a regression.

## Frozen architecture boundary

Keep the strict IPO/dependency-inversion structure:

```text
INPUT                                  PROCESSING                         OUTPUT

Inside/outside/clock/config         -> ClimateInputAdapter            -> ClimateActuatorAdapter
providers                               |                                  |
      |                                 v                                  v
      v                         ClimateControlLoop                  ClimateRoleDriver
CompositeClimateSnapshotProvider       |
                                        v
                                ClimateRuntimeController
                              Rule / ML shadow / safety
```

Rules:

1. Input providers do not know policy or actuator implementation.
2. Processing knows semantic measurements/targets/capabilities only; it must not know SCD41, BLE,
   DS3231, e-paper, GPIO, PWM, relay or board-specific details.
3. Output drivers know semantic actuator roles and normalized levels only.
4. Fake and real providers use the same interfaces; do not introduce controller-level `if (fake)` branches.
5. `ClimateControlLoop` owns confirmed previous applied actions, OFF recovery and actuator fault state.
6. Hardware adapters may report unavailable/invalid/stale data; existing runtime/safety must remain the fail-closed authority.
7. Keep the six semantic actuator roles stable across hardware backends.

## Completed software stages

### Stage25A — application composition

`ClimateApplication` proves the full
`ClimateSnapshotProvider -> ClimateInputAdapter -> ClimateControlLoop -> ClimateActuatorAdapter -> ClimateRoleDriver`
path with constructor-injected dependencies and no physical hardware coupling.

### Stage25B — reversible runtime boundary

`GROWBOX_APP_MODE` keeps `legacy` as the preserved default and provides `climate-v6-fake` as a separate hardware-neutral runtime path. Both compile in the ESP-IDF v5.5.4 gate.

### Stage25C — deterministic fake runtime

`DeterministicClimateScenarioProvider` produces repeatable scenario data from monotonic time and drives long full-application host coverage.

### Stage25D — diagnostics

Versioned read-only diagnostics observe the exact input snapshot consumed by the controller and the resulting Rule/ML/safety/output evidence without creating a control path.

### Stage25E — fault/soak virtual HIL

Host virtual HIL covers stale, invalid and unavailable inputs, timeout boundaries, capability changes, actuator rejection, fail-safe OFF rejection, fault latch/reset and long deterministic soak behavior.

### Stage26A — composite input seam

Separate inside environment, outside environment, wall clock and schedule/config interfaces feed `CompositeClimateSnapshotProvider`. The climate core remains hardware-neutral.

### Stage26B — semantic output seam

`MappedClimateRoleDriver` maps the six semantic roles to configured endpoint identifiers while preserving deterministic normalized/OFF/rejection semantics.

### Stage26C — pre-hardware readiness gate

`scripts/check_pre_hardware_readiness.sh`, host/schema/static tests and both ESP-IDF v5.5.4 app modes close the software-only gate. Passing Stage26C is not physical hardware evidence.

## Stage27 framework decision — frozen

The first real hardware implementation must be **100% native ESP-IDF v5.5.4**.

Do not:

- add Arduino-ESP32 as a component;
- migrate to PlatformIO/Arduino;
- preserve the CrowPanel screen by introducing an Arduino compatibility layer.

Preferred platform:

- Elecrow CrowPanel 2.9-inch e-paper ESP32-S3 used in `MichalMatu/esp32s3_LiteGraph`, together with the user's custom HAT, if the exact board/display/buttons have a clean maintainable native ESP-IDF path.

Fallback:

- plain inexpensive ESP32-S3 devboard;
- optional cheap display + rotary encoder later.

Display/buttons are not MVP blockers. If native CrowPanel support is disproportionately difficult, simplify the hardware instead of mixing frameworks.

The detailed decision gate is in `docs/STAGE27_NATIVE_IDF_HANDOFF.md`.

## Stage27 input direction — frozen at product level

Target real inputs:

- inside: Sensirion SCD41 — temperature, RH, CO2;
- outside: BLE temperature/RH sensor — exact model/protocol must be selected by the native source audit;
- wall clock: DS3231 with backup battery.

Preferred implementation shape:

- native ESP-IDF I2C with one explicit bus owner for SCD41 + DS3231 when wiring allows;
- native ESP-IDF NimBLE for scanning;
- protocol decoder separated from BLE scanner and climate-source adaptation;
- real inputs feed the existing `CompositeClimateSnapshotProvider` interfaces;
- all physical outputs remain fake/locked during first input bring-up;
- Rule remains authoritative; ML remains `MlShadow` only.

## Donor/reference repositories

Do not treat these as framework dependencies. Use them to recover proven behavior, pin maps,
protocol parsing, real packet fixtures, register details and hardware assumptions.

- `MichalMatu/esp32s3_LiteGraph`, reference branch `main`, observed handoff SHA
  `d9ac2e96812e5ce0a188016994a89bdd9b9edfaf`;
- `MichalMatu/MatrixHub`, reference branch `develop`, observed handoff SHA
  `fd5df96c768cdaab647d3589775e1e838e2d2db3`.

LiteGraph is particularly important because it already works on the user's real CrowPanel/HAT setup,
but it is Arduino/PlatformIO-based. Reuse pure logic/behavior only when appropriate; do not copy
Arduino runtime ownership into growbox.

## Immediate next stage: Stage27A native feasibility/source audit

The next chat must research before implementing.

Required audit:

1. identify the exact CrowPanel 2.9 ESP32-S3/e-paper revision/controller used by LiteGraph;
2. inspect official Elecrow schematic, pin map, power/init requirements, buttons, PSRAM/flash setup and native ESP-IDF examples for that exact model or directly compatible controller;
3. select a maintained native ESP-IDF SCD41/SCD4x driver compatible with IDF 5.5.4;
4. select/implement native DS3231 access with oscillator-stop/lost-power validity handling;
5. select native ESP-IDF NimBLE and the exact BLE outside sensor/protocol/decoder;
6. compare LiteGraph/MatrixHub to identify proven behavior and reusable framework-independent pieces;
7. explicitly classify each subsystem as KEEP / ADAPT / REIMPLEMENT / DEFER / DROP;
8. decide CrowPanel vs bare ESP32-S3 before starting the real input implementation.

Do not assume that because an Arduino implementation exists it should be ported. Prefer official/native ESP-IDF components when they are good enough.

## Stage27 implementation sequence after the audit

### Stage27B — real input bundle + fake outputs

Implement all selected native input backends through the existing seams:

- SCD41 inside source;
- BLE outside source;
- DS3231 clock source;
- native platform/bus ownership;
- diagnostic visibility;
- fake/locked outputs.

Host-test pure packet/measurement/freshness logic where possible and run the real ESP-IDF v5.5.4 gate.

### Stage27C — physical input validation

On the user's real device verify:

- detected part/sensor identity;
- plausible measurements;
- age/freshness progression;
- SCD41 disconnect/error behavior;
- BLE absence/malformed/foreign packet behavior;
- DS3231 untrusted-time/lost-power behavior;
- no panic/reset loop;
- fail-closed controller behavior with outputs still fake.

### Later Stage27 output work

Only after input validation:

- add physical endpoint backend beneath `MappedClimateRoleDriver`;
- keep Rule authoritative;
- bring up one semantic role at a time;
- verify explicit OFF, rejection, fail-safe OFF, fault latch and confirmed applied state;
- collect real traces with ML only in `MlShadow`;
- re-qualify ML before any active ML authority.

## Local Agent operating mode

Canonical executor rules remain in:

- `MichalMatu/local-agent/docs/AUTONOMOUS_CHAT_LOOP.md`;
- `MichalMatu/local-agent/docs/OPERATIONS.md`.

Repository settings:

- repository: `MichalMatu/growbox-ml-controller`;
- work branch: `mvp/environment-controller`;
- control branch: `agent-control`;
- daemon release observed at handoff: 4.10.2;
- execution model: multi-repository worker;
- global execution concurrency: one task.

Core rules:

- always inspect fresh daemon status before planning/queueing;
- never queue another task while one is active;
- task ids/payloads are immutable; every continuation/recovery uses a new unique id;
- terminal result for the exact task/digest outranks live run/status;
- `expected_head` is not implemented — assert the expected source SHA explicitly;
- source publication and physical flashing are separate gates;
- use `workflow_policy: efficient-verification-v1` for non-trivial staged code work;
- one final full verification stage only, after focused verification;
- real-growbox/manual hardware actions are never inferred from simulator/build success.

### Updated hybrid GitHub + local-agent workflow

The planner may now edit the **work branch directly through GitHub** when that is more efficient,
then use local-agent for real local synchronization, compilation and testing.

Use direct GitHub writes mainly for:

- docs/handoff changes;
- small isolated source/config changes with an exact obvious replacement;
- changes that would be needlessly cumbersome to encode as a local-agent patch.

Before any direct source write:

1. fetch fresh daemon status and require no conflicting active task;
2. fetch current work-branch HEAD;
3. write only to the work/source branch, not product code to `agent-control`;
4. record the returned commit SHA.

For code/build/config changes, that GitHub commit is not yet "working" evidence. Queue a new local-agent verification task that explicitly checks/synchronizes to the intended SHA, then runs the impact-appropriate focused tests/build and final full gate when warranted.

Prefer local-agent to perform the edit itself when the change spans many files, benefits from local tooling/refactoring, or needs tight edit/build/test iteration.

Never let a direct GitHub write race with a local-agent task that may publish to the same work branch.

Full project-specific details and examples are in `docs/STAGE27_NATIVE_IDF_HANDOFF.md`.

## ESP-IDF v5.5.4 verification environment

On the user's Mac the established ESP-IDF checkout is `~/esp/esp-idf` and the exact active tag must be `v5.5.4`.

Local Agent tasks run from a repository virtualenv, so ESP-IDF installation/export may require unsetting `VIRTUAL_ENV`, `CONDA_PREFIX`, and `PYTHONHOME`. When installing tools, use the sanitized PATH documented previously. The repository's `scripts/idf_gate_build.sh` is the actual firmware build gate.

## First actions in a fresh chat

1. Read this file, `AGENTS.md` and `docs/STAGE27_NATIVE_IDF_HANDOFF.md`.
2. Fetch fresh `agent-control:.agent/status/daemon.json`.
3. If a task is/was active, inspect its exact run/result before doing anything else.
4. Fetch the current remote HEAD of `mvp/environment-controller`; do not assume the SHA recorded in this handoff is still latest.
5. Read `docs/CURRENT_STATUS.md`, `docs/HARDWARE_BRINGUP_CHECKLIST.md` and `src/climate/ClimateIoAdapters.h` at the current HEAD.
6. Do **not** queue Stage25A/25B/25C/25D/25E/26A/26B/26C — those are complete.
7. Perform the Stage27A native ESP-IDF source/feasibility audit first.
8. Use current official/vendor/component sources because hardware/framework support may have changed.
9. Return a concrete KEEP / ADAPT / REIMPLEMENT / DEFER / DROP result and decide CrowPanel vs bare ESP32-S3.
10. Freeze the exact native selections in repository docs, then implement the real input bundle with fake outputs.

## Planner behavior expected by the user

- communicate in Polish;
- code, commit messages, Local Agent task JSON and repository documentation should be English;
- be concise but exact about task id, attempt/result and commit SHA;
- act autonomously where repository evidence is sufficient;
- do not ask the user to repeat facts already stored in the repository/context;
- do not queue concurrent tasks;
- prefer concrete implementation progress over repeatedly re-auditing completed stages;
- use ESP32-S3 PSRAM sensibly where useful rather than imposing artificial DRAM scarcity;
- keep the project 100% native ESP-IDF even if that means dropping CrowPanel/e-paper for the first MVP.
