# Fresh-context continuation plan

Updated: 2026-09-06
Work branch: `mvp/environment-controller`
Control branch: `agent-control`
Latest handoff: `docs/STAGE28E_PHASE_C_HANDOFF.md`
Stage28E execution guide: `docs/GUIDANCE.md`
Prior Stage28D evidence: `docs/STAGE28D_AH_ARBITER_HANDOFF.md`
Current status: `docs/CURRENT_STATUS.md`
Primary roadmap: `docs/PROJECT_ROADMAP.md`

## Read first in a new chat

1. `AGENTS.md`
2. `docs/GUIDANCE.md`
3. `docs/STAGE28E_PHASE_C_HANDOFF.md`
4. `docs/PROJECT_ROADMAP.md`
5. `docs/CURRENT_STATUS.md`
6. this file
7. `docs/STAGE28E_PHASE_B_HANDOFF.md` when Phase B reset/lifecycle detail is needed
8. `docs/STAGE28E_PHASE_A_HANDOFF.md` when the original observability baseline is needed
9. `docs/STAGE28D_AH_ARBITER_HANDOFF.md` when historical V5 details are needed
10. `docs/OBSERVABILITY_AND_INFERENCE_PLAN.md` when changing ventilation, inference, telemetry or ML behavior
11. `docs/SHELLY_POWER_FEEDBACK.md` when changing physical-state supervision

Then fetch fresh `mvp/environment-controller` HEAD, fresh `agent-control:.agent/status/daemon.json`, and the newest Local Agent result. Never continue from remembered chat state alone.

## Current transition

**Stage27C FROZEN -> Stage28A/B/C DONE -> Gates 1-6 COMPLETE -> Gate 7 previously qualified -> AH policy software COMPLETE -> Gate 7 runtime path REOPENED by V5 -> Stage28E Phase A COMPLETE -> Phase B COMPLETE -> Phase C COMPLETE pending exact-SHA docs gate -> Phase D next**

Stage28D functional AH work stays paused until A-G pass. The final physical `AH/rule request -> binary arbiter -> RF -> physical fan` path belongs to Stage28E Phase H.

## Phase identities

Phase A exit SHA:

`384e415eaaec960add2b3b3fe94db5c052ca6497`

Phase B exit SHA:

`e0fb5da17879569f791898ba793e1c02b195fab8`

Phase C measurement source SHA:

`e0fb5da17879569f791898ba793e1c02b195fab8`

Phase C complete evidence:

`docs/STAGE28E_PHASE_C_HANDOFF.md`

## Phase C decisive findings

Static/default firmware baseline:

- image `743369 B`
- `.data` `20512 B`
- `.bss` `6672 B`
- DIRAM used `124771 B / 341760 B`
- DIRAM remaining `216989 B`
- coredump stack `1892 B`

No large hidden application `.bss` consumer was found.

The main runtime ownership pattern is quantitatively significant:

- `runClimateV6RealInputRuntime()` is `[[noreturn]]`;
- compiler static frame: **`5296 B`**;
- `Stage28RfDiagnostics`: `1288 B`;
- `ClimateRuntimeController`: `872 B`;
- `Stage27TelemetryLogger`: `848 B`;
- these and many smaller objects remain resident on `app_main` stack for the firmware lifetime.

Important transient frames:

- service-console RF receive `1648 B`;
- service-console SD read `1184 B`;
- telemetry storage persist `1120 B`;
- telemetry log formatting `880 B`.

Exact ESP-IDF 5.5.4 FreeRTOS allocation contract:

- ordinary `pvPortMalloc()` is `MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT`;
- `CONFIG_SPIRAM_USE_MALLOC` is not set;
- `CONFIG_SPIRAM_USE_CAPS_ALLOC=y`;
- external-memory task creation is available only through explicit caps-aware paths.

Telemetry storage therefore has explicit internal-RAM costs:

- `stage27_store` stack `7168 B` plus task metadata;
- `Stage27TelemetrySnapshot` `296 B`;
- 16-entry queue payload **`4736 B`** plus queue overhead.

Do not globally enable PSRAM malloc or blindly move the queue/task. Phase D first clarifies ownership; Phase E handles measured placement optimization.

## Phase C bounded runtime baseline

Task:

`20260906-growbox-stage28e-phase-c-runtime-baseline-v1`

Exact SHA:

`e0fb5da17879569f791898ba793e1c02b195fab8`

Safe fake-locked evidence through about 118 seconds:

- internal free `217444 B`;
- internal minimum `216808 B`;
- largest internal block `176128 B`;
- PSRAM free `8363512 B`;
- PSRAM minimum `8363108 B`;
- largest PSRAM block `8257536 B`;
- main HWM `8064 B`, later `7984 B`;
- 14 heartbeats;
- two heap-integrity successes;
- no corruption/crash/counter-regression marker;
- Shelly master ON, median `65.8 W`;
- final marker `STAGE28E_C_SAFE_FAKE_LOCKED_PASS`.

The historical approximately 1 KiB internal-free observation was not reproduced in A-C. It is not the current accepted product baseline. Long-duration stability/fragmentation proof remains Phase G.

## V5 issue remains the functional problem to explain

Prior decisive Stage28D task:

`20260906-growbox-ah-arbiter-clean-v5`

Unexpected cumulative dwell-hold trace:

`33 -> 43 -> 1 -> 11`

Phase B/C did not reproduce the regression. Diagnostics now distinguish reset, same-boot reconstruction, same-instance counter regression, coredump state, heap corruption and liveness failure.

Do not change `applyBinary()` from the historical trace alone.

## Serial and hardware invariants

Growbox/CrowPanel serial:

`/dev/cu.usbserial-1130`

Never touch:

`/dev/cu.usbserial-10`

For Local Agent tasks:

- every task must contain exactly `"agent_binding": "815cf40f-8d2a-4e1f-b7cc-c0f4e37b6cb5"`;
- use `resources: []` for software/docs/build work;
- use `resources: ["board:growbox-s3"]` for serial/flashing/device work;
- check fresh daemon state before editing the same branch or queueing hardware access.

Safety boundary:

- rule controller authoritative;
- ML shadow/research-only;
- thermal trip `>=28 C`;
- recovery `<=26 C` continuously for 10 minutes;
- manual RF blocked during `real-bounded`;
- Shelly master ON;
- no unattended real-output operation;
- restore/prove fake-locked after bounded diagnostics.

## Immediate next work

### 1. Close Phase C formally

Run one docs-only exact-SHA Local Agent gate on fresh work-branch HEAD. Verify:

- exact local and remote SHA;
- clean work tree and `git diff --check`;
- `docs/STAGE28E_PHASE_C_HANDOFF.md` exists;
- the handoff records image `743369 B`, frame `5296 B`, telemetry queue payload `4736 B`, current/min/largest runtime memory and safe fake-locked result;
- `docs/CURRENT_STATUS.md` and this file point to Phase D next;
- no build, flash or device action.

Record the passing SHA as formal Phase C exit SHA.

### 2. Start Phase D — ownership hardening

First coherent slice:

1. introduce an explicit long-lived owner for the current runtime object graph;
2. remove the implicit lifetime coupling created by many automatic objects in the `[[noreturn]]` runtime function;
3. preserve exactly one `Stage28dBinaryRoleArbiter` instance and all Phase B lifecycle/continuity diagnostics;
4. do **not** change control/safety semantics, PSRAM placement, queue/task allocation policy or AH behavior in the same slice;
5. run focused host tests, firmware build/size and `-fstack-usage` comparison;
6. only after software PASS, use a bounded fake-locked runtime check if ownership/lifetime behavior needs hardware proof.

Target architecture direction remains:

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

This is a direction, not a requirement for a giant rewrite. Move one coherent responsibility at a time.

Do not reduce stacks or move FreeRTOS allocations to PSRAM until Phase E and only from measured evidence.

## Recommended fresh-chat instruction

`Read AGENTS.md, docs/GUIDANCE.md, docs/STAGE28E_PHASE_C_HANDOFF.md, docs/CURRENT_STATUS.md and docs/CONTINUATION_PLAN.md. Fetch fresh mvp/environment-controller HEAD plus Local Agent daemon/result first. Treat Phase C as complete only if its docs-only exact-SHA gate passed. Then continue Stage28E Phase D with a small ownership/lifetime refactor that preserves controller/arbiter/safety semantics; do not combine it with PSRAM relocation or Stage28D AH physical testing.`
