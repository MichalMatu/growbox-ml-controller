# Growbox ML project roadmap and chat handoff

Updated: 2026-09-11
Repository: `MichalMatu/growbox-ml-controller`
Work branch: `mvp/environment-controller`
Control branch: `agent-control`
Local Agent binding: `815cf40f-8d2a-4e1f-b7cc-c0f4e37b6cb5`
Current continuation: `docs/CONTINUATION_PLAN.md`
Current execution handoff: `docs/ARCHITECTURE_HANDOFF.md`

## Source-of-truth order

For a fresh chat, read:

1. `AGENTS.md`
2. `docs/CURRENT_STATUS.md`
3. `docs/ARCHITECTURE_HANDOFF.md`
4. `docs/CONTINUATION_PLAN.md`
5. this roadmap

Older Stage27/Stage28 handoffs and `docs/GUIDANCE.md` are historical evidence unless a task specifically needs that context.

## Project direction

The project is a native ESP-IDF growbox environmental controller using real sensors, local RF433 actuators, deterministic safety, telemetry/logging, and a shadow ML path.

Current direction after Physical H PASS: improve product behavior and usability with small/medium, evidence-backed changes rather than extending the completed qualification workstream.

## Completed platform milestones

- Stage27C real-input native ESP-IDF baseline: FROZEN.
- Stage28A RF433 codec/classification: DONE.
- Stage28B ESP-IDF RMT TX/RX: DONE.
- Stage28C physical RF identity: DONE/FROZEN.
- absolute-humidity ventilation policy: DONE.
- Stage28E diagnostics/architecture hardening A-G: DONE.
- Output execution architecture A1-A12: DONE.
- A13 OutputSupervisor qualification tooling/preflight: DONE.
- Physical H: PASS.

Qualified production executable identity:

`02208d23f403bca3540dbbd652eb55703a044833`

Physical H evidence:

`20260910-output-supervisor-physical-h-v3` PASS

The physical H run proved the production chain from natural climate intent through OutputSupervisor/RF transport to independent Shelly power evidence and environmental response, then restored the supervisor-owned safe final state.

## Frozen physical identities

| role/load | ON | OFF | profile |
| --- | ---: | ---: | --- |
| fan / endpoint 1 | 906118656 | 1040336384 | protocol 2, 32 bit, 575 us, repeat 10 |
| lamp / endpoint 2 | 235030016 | 16926208 | protocol 2, 32 bit, 560 us, repeat 10 |
| humidifier / endpoint 3 | 637683200 | 771900928 | protocol 2, 32 bit, 560 us, repeat 10 |

Canonical Shelly host: `192.168.0.16`.

## Architecture invariant

`OutputSupervisor` is the only normal production owner allowed to execute configured physical outputs.

Standing rules:

- climate/schedule/manual produce intents;
- safety produces non-bypassable constraints/forced actions;
- binary policy owns hysteresis/dwell rather than transport;
- RF433 transport is policy-free;
- one-way RF completion is not physical acknowledgement;
- raw RF is maintenance-only through explicit `MaintenanceLocked` handling;
- deterministic rule control remains authoritative;
- ML remains shadow/research-only.

## Current product roadmap

The next chat should audit current source and rank the following opportunities rather than blindly implementing all of them.

### 1. Controller quality

Review temperature/humidity interaction, absolute-humidity ventilation usefulness, targets, deadband/hysteresis, dwell, binary thresholds, and whether the controller is unnecessarily conservative or aggressive in real growbox conditions.

Prefer offline replay/simulation before hardware experimentation.

### 2. Configuration and operator UX

Reduce friction in configuring sensors, targets, actuators, schedules and growbox parameters. Preserve clear validation and bounded embedded resource cost.

### 3. Logging/history/plots

Improve the ability to answer why the controller made a decision and how the environment responded. Prefer compact telemetry and offline analysis over expensive firmware-side visualization/processing.

### 4. ML shadow/research

Improve feature logging, labels, deterministic-vs-ML comparison, replay datasets and evaluation metrics. ML must remain observe-only until separately justified and qualified.

### 5. Additional devices

Add sensors/actuators only where a concrete use case justifies code, RAM, UI and verification cost. Avoid feature accumulation for its own sake.

## Selection rule for the next implementation

Choose the first change by:

1. practical growbox value;
2. low/controlled safety risk;
3. clean architectural ownership;
4. modest ESP32-S3 RAM/CPU/flash cost;
5. ability to verify mostly in software/sandbox;
6. small coherent diff over broad rewrites.

The expected first deliverable is a source-backed shortlist of 3-5 changes with value/cost/risk/resource/test estimates and one recommended first implementation.

## Work-mode roadmap

- use sandbox/container first for analysis, replay, simulation, statistics and compute-heavy experiments;
- use direct GitHub for bounded edits when exact diff + CI/focused checks are sufficient;
- use Local Agent for Mac-specific builds/toolchains, local network, serial/USB/flash and physical devices;
- do not use Local Agent merely as general compute when sandbox can do the work;
- never invoke local Codex from Local Agent;
- every Local Agent task uses the exact repository binding, explicit `work_branch: mvp/environment-controller`, and `resources: []`.

## Hardware boundaries

Correct Growbox port: `/dev/cu.usbserial-1130`.

Never touch `/dev/cu.usbserial-10`.

Do not use `/dev/cu.usbserial-1120` without separate authorization.

Shelly: `192.168.0.16`; do not scan for substitutes unless the operator explicitly changes the address.

## Qualification policy going forward

A12/A13/Physical H are complete for the qualified executable identity. Do not rerun them by default after docs/UI/unrelated work.

If a later production-source change materially modifies the qualified execution/safety/output path, determine the minimum required requalification from the actual diff and preserve the historical H evidence. Historical H v8 remains frozen and must not be run.
