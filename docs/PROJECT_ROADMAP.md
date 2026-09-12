# Growbox ML project roadmap

Updated: 2026-09-12
Repository: `MichalMatu/growbox-ml-controller`
Primary development branch after cleanup: `main`
Control branch: `agent-control`
Current status: `docs/CURRENT_STATUS.md`

## Source-of-truth order

For fresh context, read:

1. `AGENTS.md`
2. `docs/FRESH_CHAT_BOOTSTRAP.md`
3. `docs/CURRENT_STATUS.md`
4. `docs/ARCHITECTURE.md`
5. this roadmap
6. `docs/CONTINUATION_PLAN.md`

Stage27/Stage28 handoffs, qualification documents and older audit plans are historical evidence unless a task specifically needs them.

## Current project direction

The project is a native ESP-IDF ESP32-S3 growbox controller using real sensors, deterministic rule control, local RF433 actuators, durable telemetry and an ML shadow/research path.

The architecture-cleanup workstream is finished. Do not start another broad refactor by default. New work should improve actual growbox behavior or operator value while preserving the current ownership and safety boundaries.

Latest code-bearing release-hardening and bounded hardware qualification identity: `e03763d019af405087a5fa9c6713a7165d2e623f`. It passed local guards/tests/clang-tidy/ESP-IDF builds, GitHub CI #865, Sandbox Pack #63 and `20260912-final-main-hardware-qualification-v1`.

Historical full Physical H qualification remains evidence for executable `02208d23f403bca3540dbbd652eb55703a044833`; the 2026-09-12 bounded qualification above is the current safe real-input/fake-locked evidence and must not be mislabeled as the historical full Physical H run.

## Completed platform milestones

- climate-v6 deterministic controller and schema: DONE;
- Stage27C native real-input ESP-IDF baseline: FROZEN;
- Stage28A-C RF433 protocol/transport/physical identity: DONE/FROZEN;
- absolute-humidity ventilation policy: DONE;
- Stage28E diagnostics/architecture hardening A-G: DONE;
- OutputSupervisor execution architecture A1-A13: DONE;
- historical Physical H qualification: DONE for its exact historical executable;
- quality-freeze runtime/config/service-console/legacy refactor: DONE;
- post-refactor debt burn and compact software verification: DONE.

## Architecture invariants

- `OutputSupervisor` is the only normal configured physical-output owner;
- climate/schedule/manual produce intents, not direct RF writes;
- safety is non-bypassable;
- `BinaryActuatorPolicy` owns hysteresis/dwell;
- RF transport is policy-free;
- unavailable transport reports `NotAttempted/Unavailable` and cannot manufacture execution truth;
- one-way RF completion is not physical acknowledgement;
- raw RF is maintenance-only through `MaintenanceLocked`;
- production control authority is deterministic Rule;
- ML is shadow/research-only;
- runtime/build configuration defaults have one CMake/profile source of truth.

## Active product roadmap

### Next selected bounded task

Start with **Controller behavior quality**: build a baseline from current real telemetry/replay, quantify temperature/humidity and absolute-humidity ventilation behavior, and select exactly one tuning candidate. Record baseline metrics and acceptance criteria before implementation so the change is evidence-backed and reversible.

### 1. Controller behavior quality

Use replay/simulation and real telemetry to improve temperature/humidity interaction, absolute-humidity ventilation decisions, targets, deadbands, hysteresis and dwell. Prefer evidence-backed tuning over adding complexity.

### 2. Configuration and operator UX

Reduce friction in configuring sensors, targets, schedules, outputs and growbox parameters. Keep validation explicit and resource cost bounded for ESP32-S3.

### 3. Logging, history and explainability

Make it easier to answer: what did the controller observe, why did it choose an action, what was actually attempted, and how did the environment respond? Prefer compact device telemetry plus offline analysis.

### 4. ML shadow/research quality

Improve feature logging, labels, replay datasets and deterministic-vs-ML comparison metrics. ML remains observe-only in production until separately justified and qualified.

### 5. Useful device expansion

Add sensors/actuators only when a concrete growbox use case justifies code, RAM, UI and verification cost. Do not accumulate integrations for their own sake.

### 6. Release/qualification discipline

Use focused software verification during normal development. Run physical qualification only for a release/candidate where a fresh hardware-qualified executable identity is actually required or when changes materially affect output/safety/hardware behavior.

## Selection rule

Rank prospective work by:

1. practical growbox value;
2. safety risk;
3. architectural ownership clarity;
4. ESP32-S3 RAM/CPU/flash cost;
5. software-verification coverage;
6. implementation size and reversibility.

Prefer one small coherent improvement over another cross-cutting rewrite.

## Repository/work-mode roadmap

- `main` is the normal development branch after cleanup;
- `agent-control` is infrastructure/control state and is not a product-development branch;
- `gh-pages` is retained for publishing;
- sandbox/container first for analysis, replay, simulation and statistics;
- direct GitHub for bounded code/config/docs edits;
- Local Agent for Mac-local builds/toolchains, local network, USB/serial/flash and devices;
- never invoke local Codex from Local Agent.

Every Local Agent task uses the exact repository binding, `work_branch: main`, and `resources: []`.

## Hardware boundaries

Growbox port: `/dev/cu.usbserial-1130`.

Never touch `/dev/cu.usbserial-10`.

Do not use `/dev/cu.usbserial-1120` without separate authorization.

Canonical Shelly host: `192.168.0.16`.
