# Current controller status

Updated: 2026-09-08
Development branch: `mvp/environment-controller`
Latest handoff: `docs/ARCHITECTURE_HANDOFF.md`
Execution architecture design: `docs/OUTPUT_EXECUTION_ARCHITECTURE.md`
Frozen Phase H evidence: `docs/STAGE28E_PHASE_H_HANDOFF.md`
Stage28E guide/history: `docs/GUIDANCE.md`
Prior Stage28D evidence: `docs/STAGE28D_AH_ARBITER_HANDOFF.md`
Primary roadmap: `docs/PROJECT_ROADMAP.md`
Continuation checklist: `docs/CONTINUATION_PLAN.md`

## Current transition

**Stage27C FROZEN -> Stage28E A-G COMPLETE -> H OPEN BUT SUSPENDED -> EXECUTION ARCHITECTURE AUDIT/REFACTOR ACTIVE**

A-G are formally complete. Phase H remains formally open, but all further H v8 testing is intentionally suspended by project decision on 2026-09-08.

The immediate workstream is not another output gate around the old runtime. It is a clean execution architecture with one physical-output owner and explicit separation of:

- climate/control intent;
- schedule/manual intent;
- safety constraints and forced actions;
- lifecycle/output policy;
- binary dwell/hysteresis policy;
- transport;
- command/configuration state;
- telemetry/physical feedback.

Architecture-pause entry baseline:

`157806442161e88edd8038e532e9dff333a19efb`

Formal Phase G exit gate:

`7ddb995d1f6cd190fa110f21f0d8dc0eabc61d26`

Old qualified Phase H production runtime/tooling identity:

`5a4830db9d10e8cb73d4c617b09122f0844ad899`

That identity and the old H v8 preflight remain historical evidence only once production C++ changes for the architecture refactor.

## Phase H frozen state

Phase H is **not PASS** and is **not currently running**.

Latest relevant H facts:

- H v7 was intentionally interrupted after an observer semantic defect was established;
- mandatory recovery and final verification passed;
- the board was documented RF-disabled `fake-locked` afterward;
- observer commit `45065a34ce276ac5cdb7ef8cf0a1ad8a4bae1b0d` accepts `Safe (0)` and `TimerOff (1)` only when `safety_latched=0` and `force_fan=0`;
- H v8 software preflight `20260908-stage28e-h-v8-preflight-v1` passed on `231eed28f64bdbdc4238fd8bce128264027702f2`;
- H v8 hardware execution was never started.

Do not start H v8 during the architecture workstream. The frozen H handoff preserves the detailed historical evidence.

## Active architecture decision

Authoritative design:

`docs/OUTPUT_EXECUTION_ARCHITECTURE.md`

Authoritative continuation handoff:

`docs/ARCHITECTURE_HANDOFF.md`

Core invariant:

> `OutputSupervisor` becomes the only normal production component allowed to execute configured physical outputs.

Target responsibilities:

- `ClimateRuntimeController` / climate decision layer computes `ControlIntent` and does not own RF/lifecycle behavior;
- `SafetyPolicyEngine` computes a `SafetyEnvelope` and never transmits directly;
- schedule and manual sources produce intents;
- `OutputPolicyConfig` defines per-output boot/automation-off/recovery/fault actions and bounded ordering/timing;
- binary actuator policy owns hysteresis/dwell only;
- `OutputSupervisor` resolves mode + intents + safety + policy into an `OutputPlan`;
- RF433 becomes a narrow transport;
- `OutputStateStore` distinguishes desired/resolved/last-commanded/transport-result from actual physical state;
- normal service-console output commands go through the supervisor.

### Automation OFF

Automation OFF is a lifecycle state, not merely a final command filter.

Preferred behavior:

- climate engine may continue calculating in observe-only mode;
- normal control intent is not executed;
- safety remains active;
- configured per-output disable actions decide which sockets receive OFF/ON/no command/schedule/restore behavior and when;
- transport remains unaware of why a command was chosen.

## First task in the next chat

Start with a **read-only execution-architecture audit**. Do not patch production behavior first.

The audit must identify exact files/symbols for:

1. every normal and diagnostic RF/output write path;
2. every output-state owner/cache;
3. thermal safety and all fail-safe paths;
4. boot, automation-disable, recovery, and fault output behavior;
5. schedule/lamp path;
6. service-console/manual RF path;
7. endpoint-role mapping and validation;
8. existing configuration/state persistence mechanisms;
9. task/thread ownership and reentrancy assumptions;
10. `reconcileApplied` / previous-applied coupling;
11. host tests coupled to the present actuator-driver chain;
12. expected stack/DRAM effect of the supervisor/policy split.

Write the result to:

`docs/OUTPUT_EXECUTION_ARCHITECTURE_AUDIT.md`

Only after the audit is reconciled with the design should implementation begin.

## Planned migration sequence

1. audit only;
2. contracts/types;
3. split dumb RF transport from endpoint state/policy;
4. adapt thermal safety to a `SafetyEnvelope`;
5. introduce `OutputSupervisor` + lifecycle state machine/policy;
6. integrate binary hysteresis/dwell under execution policy;
7. split climate decision production from physical execution/reconciliation;
8. add versioned output policy and honest persisted command state using the existing suitable store;
9. route normal service-console output commands through the supervisor;
10. remove duplicated state/safety/output ownership and enforce the one-owner invariant;
11. focused host tests during implementation, then one full software gate after stabilization;
12. only then create a new production firmware identity and new bounded physical qualification plan.

Do not combine this into one large rewrite.

## Test / hardware status

For the current handoff session:

- tests are paused;
- no builds are requested;
- no serial access;
- no flashing;
- no RF transmission;
- no hardware qualification.

In the next architecture session, start with code-reading/audit only. Focused host tests resume when behavior-changing implementation begins. One full software gate is deferred until the architecture stabilizes.

## Safety boundary

Correct Growbox serial device:

`/dev/cu.usbserial-1130`

Never open/probe/flash:

`/dev/cu.usbserial-10`

Standing invariants:

- tent remains closed unless the operator explicitly changes that requirement later;
- deterministic rule controller remains authoritative;
- ML remains shadow/research-only;
- thermal trip remains `>=28 C`;
- thermal recovery remains `<=26 C` continuously for 10 minutes;
- manual RF remains blocked during the old `real-bounded` qualification mode and must not be reintroduced as an unguarded production bypass;
- Shelly master stays ON during any future bounded qualification;
- future hardware tasks must restore/prove an explicitly defined safe state;
- old H observer/recovery tooling is historical until reviewed against the new execution architecture.

## Local Agent execution identity

- repository: `MichalMatu/growbox-ml-controller`;
- repository id: `growbox-ml-controller`;
- agent binding: `815cf40f-8d2a-4e1f-b7cc-c0f4e37b6cb5`;
- control branch: `agent-control`;
- work branch: `mvp/environment-controller`.

For every Local Agent task:

- exact `agent_binding` is mandatory;
- use `resources: []` for every repository task, including software, builds, serial, flash and hardware;
- do not declare named resources or `machine`;
- verify exact SHA in-task whenever source identity matters;
- verify the exact device/port inside any future hardware task;
- read terminal `.agent/results/<task-id>.json` before reporting PASS.

## Immediate next work

1. Fresh-check work-branch HEAD and Local Agent status in the new chat.
2. Read `docs/ARCHITECTURE_HANDOFF.md` and `docs/OUTPUT_EXECUTION_ARCHITECTURE.md` before the older H handoff.
3. Perform the read-only architecture audit and create `docs/OUTPUT_EXECUTION_ARCHITECTURE_AUDIT.md`.
4. Correct the design document if the audit disproves an assumption.
5. Then implement the modular execution architecture in small coherent commits.
6. Do not start H v8 or any physical-output test until the architecture has a new software qualification, new exact firmware identity, reviewed qualification plan, and explicit operator authorization.
