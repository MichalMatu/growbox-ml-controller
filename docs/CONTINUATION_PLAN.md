# Fresh-context continuation plan

Updated: 2026-09-08
Work branch: `mvp/environment-controller`
Control branch: `agent-control`
Latest handoff: `docs/ARCHITECTURE_HANDOFF.md`
Execution architecture design: `docs/OUTPUT_EXECUTION_ARCHITECTURE.md`
Current status: `docs/CURRENT_STATUS.md`
Frozen Phase H evidence: `docs/STAGE28E_PHASE_H_HANDOFF.md`

## Read first in a new chat

1. `AGENTS.md`
2. `docs/ARCHITECTURE_HANDOFF.md`
3. `docs/OUTPUT_EXECUTION_ARCHITECTURE.md`
4. `docs/CURRENT_STATUS.md`
5. this file
6. `docs/GUIDANCE.md`
7. `docs/STAGE28E_PHASE_H_HANDOFF.md` for frozen H evidence
8. `docs/STAGE28D_AH_ARBITER_HANDOFF.md` for prior arbiter context
9. `docs/PROJECT_ROADMAP.md`
10. `docs/ESP32_S3_SERIAL_PORT_RESET.md` before any future serial/hardware work

Then fetch fresh `mvp/environment-controller` HEAD and fresh `agent-control:.agent/status/daemon.json`. Read relevant terminal `.agent/results/...` before deciding what has passed. Never continue from remembered chat state alone.

## Current transition

**Stage28E A-G COMPLETE -> H OPEN BUT SUSPENDED -> EXECUTION ARCHITECTURE AUDIT/REFACTOR ACTIVE**

Architecture-pause entry baseline:

`157806442161e88edd8038e532e9dff333a19efb`

Formal Phase G exit gate:

`7ddb995d1f6cd190fa110f21f0d8dc0eabc61d26`

Old qualified production identity:

`5a4830db9d10e8cb73d4c617b09122f0844ad899`

H v8 software preflight `20260908-stage28e-h-v8-preflight-v1` passed on `231eed28f64bdbdc4238fd8bce128264027702f2`, but H v8 hardware execution was never started.

That preflight is frozen historical evidence. It must not be reused to qualify production C++ changed by the architecture workstream.

## Explicit project decision

Do **not** continue H v8 now.

The previous sequencing decision — preserve the current production binary until H PASS and refactor afterward — is superseded by the 2026-09-08 project decision. We intentionally stop physical qualification first and correct the product architecture.

The target is not a final output kill switch. The target is modular ownership:

```text
climate/schedule/manual intent
            +
      safety envelope
            |
            v
     OutputSupervisor
   mode + policy + state
            |
       OutputPlan
            |
            v
      RF433 Transport
```

`OutputSupervisor` must become the only normal production owner that can execute configured physical outputs.

## Architecture requirements

Read the full design in `docs/OUTPUT_EXECUTION_ARCHITECTURE.md`.

Minimum required separation:

- climate engine computes `ControlIntent`;
- climate engine may continue observe-only calculation when automation is OFF;
- safety computes non-bypassable constraints/forced actions and does not transmit;
- schedule/manual sources produce intents and do not transmit;
- per-output lifecycle policy defines boot/automation-off/recovery/fault actions;
- lifecycle actions can define bounded ordering/timing and ON/OFF/no-command/schedule/restore behavior;
- binary hysteresis/dwell is an execution policy independent of RF and temperature evaluation;
- RF433 transport sends validated commands and reports transport results only;
- persisted state distinguishes last commanded/transport result from actual physical state;
- normal service-console output commands must pass through the supervisor;
- raw transport diagnostics, if retained, require an explicit maintenance guard and cannot become a second invisible production owner.

## First new-chat task: architecture audit

Start with a read-only/source-reading audit. No production behavior patch first.

Create:

`docs/OUTPUT_EXECUTION_ARCHITECTURE_AUDIT.md`

The audit must identify, with exact file/symbol evidence:

1. normal controller-to-output call graph;
2. every direct and indirect RF/output writer;
3. every output-state cache/owner;
4. every thermal safety / fail-safe path;
5. boot, disable, recovery, and fault output actions;
6. schedule/lamp path;
7. service-console/manual output path;
8. endpoint-role mapping ownership and validation;
9. persistence/settings mechanisms already present;
10. control/safety/console/RF task and concurrency context;
11. `reconcileApplied` and previous-applied semantics;
12. tests coupled to current actuator/driver structure;
13. memory/stack impact expected from the new supervisor/policy objects.

Distinguish observed source facts from design proposals. If the source disproves an assumption in the architecture design, update the design before implementing behavior.

## Planned implementation after the audit

Use small coherent commits:

1. contracts/types (`ControlIntent`, `SafetyEnvelope`, plan/report/config types);
2. dumb RF transport split;
3. safety-envelope adaptation;
4. `OutputSupervisor` state machine + resolver + lifecycle policy;
5. binary actuator policy integration without hardware ownership;
6. climate decision/execution split and correct applied-state reconciliation;
7. versioned policy + honest command-state persistence using an existing suitable store;
8. service-console migration and maintenance diagnostics separation;
9. removal of legacy duplicate state/safety/output ownership;
10. invariant enforcement: one normal production output owner;
11. focused host tests during each behavior-changing step;
12. one full software gate after the architecture stabilizes;
13. new firmware identity and new H qualification plan before any hardware execution.

Do not perform a giant rewrite.

## Frozen Phase H evidence

The detailed H history remains in `docs/STAGE28E_PHASE_H_HANDOFF.md`.

Relevant frozen facts:

- H v7 primary was intentionally interrupted after the TimerOff observer defect was understood;
- recovery and final fake-locked verification passed;
- TimerOff-aware observer commit is `45065a34ce276ac5cdb7ef8cf0a1ad8a4bae1b0d`;
- H v8 preflight passed but hardware did not start;
- the existing observer/recovery scripts are retained but are not authorized to run during the architecture audit/refactor.

The eventual H path remains conceptually useful, but the exact expected execution chain must be rewritten against the new supervisor architecture before physical qualification resumes.

## Test and hardware policy

For the current handoff session:

- no tests;
- no builds;
- no serial;
- no flash;
- no RF commands;
- no hardware qualification.

In the next chat:

- audit first without hardware;
- once implementation begins, focused host tests are expected for coherent changes;
- one full software gate only after stabilization;
- no physical H continuation without a new exact firmware identity, reviewed plan, and explicit operator authorization.

## Safety boundaries

- correct serial: `/dev/cu.usbserial-1130`;
- never touch `/dev/cu.usbserial-10`;
- tent remains closed unless the operator explicitly changes that requirement;
- deterministic rule controller remains authoritative;
- ML remains shadow/research-only;
- thermal trip remains `>=28 C`;
- thermal recovery remains `<=26 C` continuously for 10 minutes;
- ordinary automation-off configuration must not silently disable non-bypassable thermal protection;
- Shelly master remains ON for future bounded qualification;
- future output recovery semantics must be owned by firmware execution policy, not only qualification scripts.

## Local Agent contract

Every Local Agent task must use:

- exact `agent_binding`: `815cf40f-8d2a-4e1f-b7cc-c0f4e37b6cb5`;
- explicit `resources: []`;
- `work_branch: mvp/environment-controller` when working on this MVP branch;
- no named resources or `machine`;
- explicit SHA verification when source identity matters;
- terminal `.agent/results/<task-id>.json` evidence before reporting PASS.

Any future hardware task must detect and verify `/dev/cu.usbserial-1130` internally and explicitly refuse `/dev/cu.usbserial-10`.

## Recommended fresh-chat instruction

`Continue only MichalMatu/growbox-ml-controller on mvp/environment-controller with Local Agent binding 815cf40f-8d2a-4e1f-b7cc-c0f4e37b6cb5. Read AGENTS.md, docs/ARCHITECTURE_HANDOFF.md, docs/OUTPUT_EXECUTION_ARCHITECTURE.md, docs/CURRENT_STATUS.md and docs/CONTINUATION_PLAN.md first, then fresh-check work HEAD and agent-control daemon/result state. Stage28E A-G are complete; H remains open but is intentionally suspended before H v8. Do not start H v8, flash hardware or run physical-output tests. Start with a read-only audit of the actual execution architecture: enumerate every RF/output writer, output-state owner, safety/fail-safe path, boot/disable/recovery/fault action, schedule/manual path, endpoint mapping, persistence mechanism, task context and reconcileApplied/previous-state coupling. Write the evidence-backed audit to docs/OUTPUT_EXECUTION_ARCHITECTURE_AUDIT.md and reconcile it with docs/OUTPUT_EXECUTION_ARCHITECTURE.md before changing behavior. The target is one OutputSupervisor as the only normal production physical-output owner, SafetyPolicyEngine producing constraints, per-output lifecycle OutputPolicy, honest StateStore semantics and a dumb RF433 Transport. Automation OFF should stop execution of normal control intent while allowing the climate engine to keep calculating observe-only; safety remains active. After audit, implement in small commits with focused host tests, one full software gate only after stabilization, and create a new firmware identity/qualification plan before any hardware H continuation. Every Local Agent task uses resources: []; future hardware tasks must verify /dev/cu.usbserial-1130 internally and never touch /dev/cu.usbserial-10.`
