# Fresh-context continuation plan

Date: 2026-08-29
Work branch: `mvp/environment-controller`
Control branch: `agent-control`
Stage24A published baseline before this handoff: `6106d00f202fbaa4e4acd2e8fc93a6d94e6228b4`

This document is the bootstrap point for a new ChatGPT conversation. Read it together with
`AGENTS.md`, `docs/CURRENT_STATUS.md`, `docs/ARCHITECTURE.md`, and
`docs/ML_DECISION_REPORT.md` before planning new work.

## Product state

The current product path is climate-v6 (`climate-mvp-v1`):

- 44 runtime-observable features;
- 6 ML-controlled semantic outputs: heater, cooler, exhaust fan, humidifier,
  dehumidifier, CO2 doser;
- bounded research network `44 -> 32 -> 32 -> 6`;
- Rule is the authoritative runtime policy;
- `MlShadow` evaluates ML without controlling hardware;
- `MlActive` is research-only and is not qualified for real growbox actuation;
- deterministic arbitration and safety remain authoritative over every proposal;
- effective actuator state advances only from confirmed/final applied semantic actions.

Already completed:

- Sequence Teacher qualification and ML research freeze through Stage16;
- effective-actuator observability;
- Python runtime modes and C++ runtime core;
- Python/C++ parity;
- trace schema, NDJSON recording, deterministic replay and counterfactual ML;
- `ClimateControlLoop` with fail-closed input handling and actuator fault latch;
- multi-step virtual HIL;
- climate-v6 sources compiled in the real ESP-IDF ESP32-S3 firmware build;
- ESP-IDF migration to v5.5.4 locally and in CI;
- Stage24A hardware-neutral I/O seam plus documentation refresh.

Stage24A added application-side interfaces in `src/climate/ClimateIoAdapters.*`:

- `ClimateInputSnapshot`;
- `ClimateSnapshotProvider`;
- `ClimateInputAdapter`;
- `ClimateActuatorRole`;
- `ClimateRoleDriver`;
- `ClimateActuatorAdapter`.

The preserved legacy `src/main.cpp` still runs the old simulator/serial `EnvironmentController`.
Do not silently replace it until the climate-v6 application composition path has been proven.

## Architecture decision: strict IPO and dependency inversion

Keep the system deliberately modular:

```text
INPUT                                  PROCESSING                         OUTPUT

Measurement/config/time providers  -> ClimateInputAdapter            -> ClimateActuatorAdapter
               |                         |                                  |
               v                         v                                  v
      ClimateInputSnapshot       ClimateControlLoop                  ClimateRoleDriver
                                     |
                                     v
                             ClimateRuntimeController
                           Rule / ML shadow / safety
```

Rules:

1. Input providers know nothing about Processing or actuator implementation.
2. Processing knows only semantic measurements, targets, capabilities and semantic actuator
   requests. It must not know SCD41, BLE, RTC, GPIO, PWM, Shelly, MQTT, Modbus or similar details.
3. Output drivers know only semantic actuator roles and normalized levels. They must not know ML,
   Rule policy or sensor sources.
4. Fake providers and fake role drivers implement the same interfaces as future real hardware.
   There must be no special `if (fake)` path inside the controller.
5. Confirmed applied state is feedback, not a violation of IPO. `ClimateControlLoop` owns confirmed
   previous applied actions and resets runtime state after rejected commands. Do not let hardware
   adapters duplicate or invent that state.
6. A provider may fail or return invalid/stale measurements; the runtime/safety path must fail
   closed exactly as it does in existing tests.
7. Keep semantic roles stable so hardware backends can later be swapped independently.

This architecture must permit combinations such as:

- fake sensors + fake actuators;
- replayed measurements + fake actuators;
- real SCD41 + fake actuators;
- real sensors + Rule-authoritative real actuators + ML shadow;
- different physical output backends without controller changes.

## Stage25A completed — strict IPO composition with fake providers

Stage25A proves the complete application-level path without physical hardware:

`ClimateSnapshotProvider -> ClimateInputAdapter -> ClimateControlLoop -> ClimateActuatorAdapter -> ClimateRoleDriver`

`ClimateApplication` is only the constructor-injected composition root. It adds no policy, hardware knowledge or duplicate runtime state. Fake providers/drivers live in host tests and use the same public interfaces intended for future real hardware. Multi-tick coverage includes nominal Rule control, changing/stale/invalid/unavailable measurements, ML shadow isolation, rejection -> OFF recovery, double-failure latch/reset, confirmed applied feedback and all six semantic role mappings. The legacy `src/main.cpp` remains unchanged and no SCD41/BLE/RTC/GPIO dependency is introduced.

## Following stages

### Stage25B completed — explicit reversible application runtime boundary

`GROWBOX_APP_MODE` now defaults to `legacy`. The optional `climate-v6-fake` mode runs the proven
`ClimateApplication` path with a fixed fake snapshot provider and an accept-all fake role driver.
It reports application/policy/input/output identity over JSON serial status and has no GPIO or
physical actuator dependency. The ESP-IDF v5.5.4 gate compiles both modes.

### Stage25C completed — deterministic fake runtime

`DeterministicClimateScenarioProvider` is a hardware-neutral `ClimateSnapshotProvider` whose output
is a pure function of monotonic time. A 240-tick cycle changes inside/outside T/RH/CO2, day/night
targets, light schedule and actuator capabilities. The embedded `climate-v6-fake` runtime uses it,
and host coverage runs 1,200 ticks through the full `ClimateApplication` path. Sensor faults and
actuator rejection are deliberately deferred to Stage25E rather than mixed into the nominal fake.

### Stage25D — climate-v6 observability and diagnostics

Expose versioned diagnostics for measurement value/validity/age, targets, schedule, capabilities,
Rule proposal, ML shadow proposal, final safe request, confirmed applied state, I/O/runtime status
and actuator-fault latch state. Keep diagnostics observational; they must not become a control path.

### Stage25E — fault-injection and soak virtual HIL

Extend virtual HIL with repeated stale/invalid/unavailable inputs, timeout boundaries, recovery,
capability changes, actuator rejection, OFF rejection, latch/reset and long deterministic runs.
Prove again that rejected commands never become confirmed/effective applied state.

### Stage26A — hardware-ready composite input layer

Introduce hardware-neutral component interfaces for inside environment, outside environment and
clock/schedule/config sources, then aggregate them into one `ClimateInputSnapshot`. Implement and
test only fake component sources at this stage. Do not select sensor libraries or buses yet.

### Stage26B — hardware-ready semantic output layer

Introduce configuration/mapping beneath `ClimateRoleDriver` for the six stable semantic actuator
roles. Keep endpoint implementations fake and normalized; test disabled capabilities, OFF,
partial rejection and deterministic role mapping. Do not add GPIO/PWM/relay/Shelly code yet.

### Stage26C — pre-hardware readiness gate

Run the complete host/schema/static/ESP-IDF gate, audit the climate-v6 fake path end to end and add
a hardware bring-up checklist. The checklist must leave unresolved BLE/RTC/pin/library choices
explicit for manual freeze before physical work.

### Stage27 — hardware bring-up

Bring up real hardware in this order:

1. real inputs + fake outputs;
2. validate freshness/age/error behavior and traces;
3. real outputs in Rule mode;
4. verify readback/confirmed applied behavior and fail-safe OFF;
5. run ML only as `MlShadow` while collecting real traces;
6. do not enable active ML until it is re-qualified from real data.

## Local Agent operating mode

The Local Agent is a deterministic executor. The chat/planner designs the exact bounded task; the
agent executes it and publishes evidence.

Canonical repository settings:

- repository: `MichalMatu/growbox-ml-controller`;
- work branch: `mvp/environment-controller`;
- control branch: `agent-control`;
- daemon release: 4.10.2 at handoff time;
- global execution concurrency: one task;
- never queue another task while one is active;
- never assume queued means started or success;
- task JSON files are immutable; recovery always uses a new task id;
- failed source-edit attempts may dirty the local workspace, so recovery begins by resetting to the
  exact remote work-branch HEAD;
- use `workflow_policy: efficient-verification-v1` for source work;
- use structured `steps` and `verify_steps`;
- require exactly one final full verification stage;
- explicitly assert the expected `git rev-parse HEAD`; `expected_head` is not implemented;
- evidence priority: result/run evidence, then daemon status, then remote branch/source;
- no real-growbox autonomous deployment;
- simulator/fake PASS is not hardware readiness.

For ESP-IDF v5.5.4 verification on the user's Mac:

- canonical checkout: `~/esp/esp-idf`;
- exact active tag must be `v5.5.4`;
- Local Agent tasks run from a repository virtualenv, so ESP-IDF installation/export may require
  unsetting `VIRTUAL_ENV`, `CONDA_PREFIX`, and `PYTHONHOME`;
- use a sanitized PATH when installing ESP-IDF tools:
  `/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin`;
- if the ESP-IDF Python environment was removed during cleanup, recreate it with the v5.5.4
  `install.sh esp32s3` before sourcing `export.sh`;
- then run the repository's `scripts/idf_gate_build.sh` as the actual firmware gate.

## First actions in a fresh chat

1. Read this file and `AGENTS.md`.
2. Fetch `agent-control:.agent/status/daemon.json`.
3. Fetch the latest result named by `last_task_id` if relevant.
4. Fetch the current remote HEAD of `mvp/environment-controller`.
5. Read `docs/CURRENT_STATUS.md` and `src/climate/ClimateIoAdapters.h` at that exact HEAD.
6. If daemon is idle and no newer unpublished work exists, plan/queue exactly one Stage25A task.
7. Do not repeat completed ML research unless new evidence justifies reopening it.

## Planner behavior expected by the user

- communicate in Polish;
- task/commit/code/document content executed by Local Agent should be English;
- be concise but exact about task id, attempt/result and commit SHA;
- act autonomously where repository evidence is sufficient;
- do not ask the user to repeat facts already stored in the repository/context;
- do not queue concurrent tasks;
- focus on concrete next implementation work rather than repeatedly re-auditing completed stages.
