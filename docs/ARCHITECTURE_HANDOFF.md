# Execution Architecture Handoff

Updated: 2026-09-08
Repository: `MichalMatu/growbox-ml-controller`
Work branch: `mvp/environment-controller`
Control branch: `agent-control`
Local Agent binding: `815cf40f-8d2a-4e1f-b7cc-c0f4e37b6cb5`
Architecture-pause entry baseline: `157806442161e88edd8038e532e9dff333a19efb`
Authoritative design: `docs/OUTPUT_EXECUTION_ARCHITECTURE.md`

## Current project decision

Stage28E A-G are complete. Phase H remains open, but all further H v8 testing is intentionally suspended. The immediate workstream is a code-architecture audit and refactor of output execution, safety integration, lifecycle policy, state ownership, and transport separation.

The current session stops at documentation/handoff. It does not run tests, builds, flashing, serial access, RF transmission, or hardware qualification.

The next chat must start with a repository audit before changing production behavior.

## Why H is suspended

The current code has multiple execution/safety concepts spread across the climate actuator chain, thermal safety, RF endpoint, service-console diagnostics, startup safe-state logic, and recovery tooling. Continuing H would qualify an architecture that the project has now explicitly decided to restructure.

The goal is not to hide outputs behind a final ON/OFF gate. The goal is to create one modular execution authority where:

- the climate engine computes intent;
- safety computes constraints;
- lifecycle/output policy decides startup/disable/recovery/fault actions;
- `OutputSupervisor` resolves the final plan;
- transport only transmits;
- state/persistence records command truth without pretending one-way RF is acknowledged.

## Frozen H evidence

Do not delete or rewrite the existing H evidence. It remains useful historical qualification data.

Key frozen facts:

- formal Phase G exit: `7ddb995d1f6cd190fa110f21f0d8dc0eabc61d26`;
- old qualified production identity: `5a4830db9d10e8cb73d4c617b09122f0844ad899`;
- TimerOff-aware observer commit: `45065a34ce276ac5cdb7ef8cf0a1ad8a4bae1b0d`;
- H v8 software preflight: `20260908-stage28e-h-v8-preflight-v1` PASS on `231eed28f64bdbdc4238fd8bce128264027702f2`;
- H v8 hardware run was never started;
- last documented bounded hardware recovery/final verification left the board RF-disabled `fake-locked`;
- tent remains closed;
- correct Growbox serial port is `/dev/cu.usbserial-1130`;
- `/dev/cu.usbserial-10` must never be touched.

Once production C++ changes, the old H v8 preflight is no longer a qualification of the new firmware.

## Read order in the next chat

1. `AGENTS.md`
2. `docs/ARCHITECTURE_HANDOFF.md`
3. `docs/OUTPUT_EXECUTION_ARCHITECTURE.md`
4. `docs/CURRENT_STATUS.md`
5. `docs/CONTINUATION_PLAN.md`
6. `docs/GUIDANCE.md`
7. `docs/STAGE28E_PHASE_H_HANDOFF.md` for frozen H evidence
8. `docs/STAGE28D_AH_ARBITER_HANDOFF.md` for prior arbiter context
9. `docs/PROJECT_ROADMAP.md`

Then fetch the fresh work-branch HEAD and fresh `agent-control:.agent/status/daemon.json`. Do not continue from remembered chat state alone.

## First task in the next chat — read-only architecture audit

Before proposing production patches, inspect the actual current source and produce an evidence-backed audit. At minimum trace:

1. normal climate decision -> actuator -> endpoint -> RF call graph;
2. all direct and indirect RF/output write entry points;
3. every output-state cache and owner;
4. thermal safety, fail-safe, startup, recovery, and fault paths;
5. schedule/lamp path;
6. service-console/manual RF path;
7. endpoint-role mapping and configuration validation;
8. existing settings/persistence mechanisms suitable for output policy;
9. task/thread ownership and reentrancy assumptions;
10. `reconcileApplied` / previous-applied semantics;
11. current host tests tied to the driver chain;
12. memory/stack consequences of moving ownership into one supervisor.

Write the audit to:

`docs/OUTPUT_EXECUTION_ARCHITECTURE_AUDIT.md`

The audit may correct the design document where repository evidence disproves an assumption. It must distinguish observed facts from proposed architecture.

## Target architecture

The working target is:

```text
ControlIntent + ScheduleIntent + ManualIntent
                    |
SafetyPolicyEngine -> SafetyEnvelope
                    |
                    v
             OutputSupervisor
          mode + policy + state
                    |
              OutputPlan
                    |
                    v
             OutputTransport
                    |
              RF433 initially
```

Supporting components:

- `BinaryActuatorPolicy` for hysteresis/dwell;
- versioned `OutputPolicyConfig`;
- `OutputStateStore` with honest commanded-vs-physical semantics;
- optional future `OutputFeedbackProvider`;
- telemetry that distinguishes requested/resolved/commanded/observed state.

## Required invariant

After migration, no normal production code outside the execution module may directly transmit a configured output command.

Safety is not a second output owner. It provides a non-bypassable envelope to the supervisor.

The service console is not a second output owner. Normal output commands become supervisor requests. Any low-level transport diagnostic must be isolated behind an explicit maintenance guard.

## Automation OFF semantics

Disabling automation does not have to stop the control engine. The preferred design keeps climate calculation running for observe-only telemetry while the supervisor ignores normal control intent.

The disable transition executes configured per-output lifecycle actions. The policy must be able to specify, per endpoint, actions such as:

- no command;
- force OFF;
- force ON;
- apply schedule;
- restore last command;
- ordered/bounded delayed execution.

Safety remains active while automation is disabled.

## Test and hardware policy during architecture work

For the remainder of this session: tests are paused.

In the next chat:

- start with a read-only/code-reading audit;
- do not run H v8;
- do not flash or access hardware for the audit;
- once architecture implementation starts, use focused host tests for each coherent change;
- run one full software gate only after the architecture stabilizes;
- do not resume physical H qualification until a new exact firmware identity and new qualification plan exist.

## Local Agent contract

Every Local Agent task must include exactly:

`"agent_binding": "815cf40f-8d2a-4e1f-b7cc-c0f4e37b6cb5"`

Use `resources: []` for every repository task, including builds/tests and any future hardware work. Verify the exact device/port inside a future hardware task.

Do not declare named resources or `machine`.

## Stop conditions for the architecture refactor

Stop and reassess rather than patch around the problem if:

- two production paths still own the same physical output;
- safety must call transport directly to function;
- transport must know global automation/safety policy;
- persisted command state is being treated as physical acknowledgement;
- a refactor silently changes AH thresholds or climate-control semantics;
- a large rewrite prevents behavior comparison with the current implementation;
- the architecture requires hardware testing before its software contracts can be verified.

## Resume conditions for Phase H

Do not resume H merely because the old observer is ready. Resume physical qualification only after:

1. architecture audit is complete;
2. migration is complete enough that one output owner invariant is true;
3. focused tests cover supervisor mode, safety precedence, lifecycle policy, dwell behavior, transport failure, and persistence semantics;
4. one full software gate passes;
5. production firmware identity is recorded;
6. the H test plan is reviewed against the new execution architecture;
7. the operator explicitly authorizes hardware qualification.
