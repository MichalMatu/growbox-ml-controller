# Fresh-context continuation plan

Updated: 2026-09-07
Work branch: `mvp/environment-controller`
Control branch: `agent-control`
Latest handoff: `docs/STAGE28E_PHASE_E_HANDOFF.md`
Stage28E execution guide: `docs/GUIDANCE.md`
Prior Stage28D evidence: `docs/STAGE28D_AH_ARBITER_HANDOFF.md`
Current status: `docs/CURRENT_STATUS.md`
Primary roadmap: `docs/PROJECT_ROADMAP.md`

## Read first in a new chat

1. `AGENTS.md`
2. `docs/GUIDANCE.md`
3. `docs/STAGE28E_PHASE_E_HANDOFF.md`
4. `docs/PROJECT_ROADMAP.md`
5. `docs/CURRENT_STATUS.md`
6. this file
7. `docs/STAGE28E_PHASE_D_HANDOFF.md` for ownership-hardening evidence
8. `docs/STAGE28E_PHASE_C_HANDOFF.md` for the original memory baseline
9. `docs/STAGE28E_PHASE_B_HANDOFF.md` for reset/lifecycle diagnostics
10. `docs/STAGE28D_AH_ARBITER_HANDOFF.md` for historical V5 details
11. `docs/OBSERVABILITY_AND_INFERENCE_PLAN.md` when changing ventilation/inference/telemetry/ML behavior
12. `docs/SHELLY_POWER_FEEDBACK.md` when changing physical-state supervision

Then fetch fresh `mvp/environment-controller` HEAD, fresh `agent-control:.agent/status/daemon.json`, and the newest Local Agent result. Never continue from remembered chat state alone.

## Current transition

**Stage27C FROZEN -> Stage28E A COMPLETE -> B COMPLETE -> C COMPLETE -> D COMPLETE -> E COMPLETE -> Phase F NEXT**

Stage28D functional AH work stays paused until A-G pass. Final physical `AH/rule request -> binary arbiter -> RF -> physical fan` verification belongs to Phase H.

## Phase identities

- Phase A exit SHA: `384e415eaaec960add2b3b3fe94db5c052ca6497`
- Phase B exit SHA: `e0fb5da17879569f791898ba793e1c02b195fab8`
- Phase C exit SHA: `7601f0beb95d27b2bf2360b760355c3c235871a1`
- Phase D implementation SHA: `09340089767cde117d12acc049790a2b93778b8e`
- Phase D formal docs exit SHA: `5e750b972eeff4ac8c9149ef6ea708f703d2d755`
- Phase E implementation head: `4a8ce18edd8cc90e6300929d2d9f035c4ec49eb5`
- Phase E complete evidence: `docs/STAGE28E_PHASE_E_HANDOFF.md`

## Phase E decisive result

Phase E recovered internal-RAM headroom with three bounded, measured changes and no control/AH/RF/safety semantic change.

E1 (`4a5121abf2a93ba76bfc219575d2b52b8025fb03`):

- moved only the `4736 B` telemetry queue payload to PSRAM using `MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT`;
- kept queue control metadata internal;
- preserved the previous internal `xQueueCreate()` path as allocation fallback;
- kept global `CONFIG_SPIRAM_USE_MALLOC` disabled;
- host `24/24 PASS`;
- hardware `queue_psram=1 queue_bytes=4736`;
- internal free/min/largest `218672 / 218140 / 176128 B`;
- gain vs D2 `+4772 / +4876 B` free/min;
- storage `12` writes, `0` queue drops, `0` write errors;
- safe final state `fake-locked`.

E2 (`c2aff0a14bbcca567de4083a284d3522fa52421e`):

- right-sized `stage27_store` stack `7168 -> 6144 B`;
- host `24/24 PASS`;
- internal free/min/largest `219568 / 219036 / 176128 B`;
- gain vs E1 `+896 / +896 B`;
- worst observed storage-task HWM `1884 B`, later `1820 B` in E3;
- storage `12` writes, `0` drops, `0` errors;
- safe final state `fake-locked`.

Do not shrink `stage27_store` further before Phase G long-runtime evidence.

E3 (`4a8ce18edd8cc90e6300929d2d9f035c4ec49eb5`):

- changed only the Stage27C main-task overlay from `16384 -> 12288 B`; base project default remains `16384 B`;
- generated Stage27C sdkconfig proves the override;
- host `24/24 PASS`;
- image `743641 B`;
- internal free/min/largest `223792 / 223260 / 180224 B`;
- gain vs E2 `+4224 / +4224 B`;
- cumulative gain vs D2 `+9892 B free`, `+9996 B min`, `+8192 B largest block`;
- main worst observed HWM `7240 B` free;
- storage-task worst HWM `1820 B` free;
- 11 heartbeats and heap-integrity PASS;
- Shelly master ON, median `65.5 W`;
- storage `12` writes, `0` drops, `0` errors;
- safe final state `fake-locked`.

Phase E stops here. Further stack cuts are intentionally deferred.

## Phase F — focused binary-arbiter continuity/regression proof

Phase F must resolve the Stage28D V5 anomaly from deterministic evidence before any longer soak or physical AH actuator path.

Historical symptom:

`arbiter_dwell_holds 33 -> 43 -> 1 -> 11`

Normal same-instance cumulative state has no ordinary reset path. Phase B-E diagnostics did not reproduce such a regression.

### Required Phase F proof

1. Use a single known `Stage28dBinaryRoleArbiter` instance with lifecycle identity captured.
2. Use synthetic inputs; keep physical outputs fake-locked.
3. Exercise request below threshold and a request around `0.111` while minimum-OFF dwell is active.
4. Verify dwell-hold cumulative counters remain monotonic within one instance except explicit `uint32_t` wrap handling.
5. Verify a historical-style same-instance `43 -> 1` drop is impossible through normal `applyBinary()` execution.
6. Hold the same instance through the full `120 s` minimum-OFF dwell.
7. Prove an eligible `0.111` request transitions ON after dwell eligibility.
8. Capture boot ID, arbiter instance ID, construction count, transition count, dwell-hold count and continuity-fault count around the proof.
9. Avoid log/heap churn in the diagnostic; use bounded synthetic events and existing structured diagnostics.
10. Do not modify `applyBinary()` merely to make the historical V5 trace disappear.

### Phase F verification order

1. record fresh start SHA and exact diagnostic scope;
2. add the smallest pure/focused arbiter diagnostic or test harness needed;
3. run focused host tests first;
4. run the existing host suite/build gate if firmware changes;
5. use bounded fake-locked runtime evidence only if required to prove lifecycle integration;
6. update handoff/status with the result;
7. run one formal exact-SHA Phase F exit gate before Phase G.

## Phase G after F

Run bounded fake-locked runtime first, then the long-duration soak only after short stability is clean. Preserve evidence on any reset, coredump, heap-integrity fault, counter regression, stack alarm, watchdog, or unexplained boot/session change.

Do not shrink stacks further simply because a short Phase F run is clean; Phase G is the runtime evidence needed for that decision.

## Phase H after G

Only after A-G pass, run bounded physical E2E:

`AH/rule request -> binary arbiter -> RF -> physical fan`

Capture request, arbiter state/dwell/identity, transition, RF result, physical/Shelly evidence, memory/stack/safety, then restore `fake-locked`.

## Serial and hardware invariants

Growbox/CrowPanel serial:

`/dev/cu.usbserial-1130`

Never touch:

`/dev/cu.usbserial-10`

For every Local Agent task:

- include exactly `"agent_binding": "815cf40f-8d2a-4e1f-b7cc-c0f4e37b6cb5"`;
- use `resources: []` for software/docs/build work;
- use `resources: ["board:growbox-s3"]` only for device work;
- check fresh daemon state before editing/queueing hardware work.

Safety boundary:

- rule controller authoritative;
- ML shadow/research-only;
- thermal trip `>=28 C`;
- recovery `<=26 C` continuously for 10 minutes;
- manual RF blocked during `real-bounded`;
- Shelly master ON;
- no unattended real-output operation;
- restore/prove `fake-locked` after bounded diagnostics.

## Immediate next work

1. Run docs-only exact-SHA Phase E exit gate on fresh HEAD.
2. Record the passing docs SHA as formal Phase E exit SHA.
3. Start Phase F with a read-only inspection of the current arbiter tests/harness and exact V5-relevant semantics.
4. Add the smallest deterministic single-instance synthetic regression proof.
5. Run focused host proof first; no physical outputs.

## Recommended fresh-chat instruction

`Read AGENTS.md, docs/GUIDANCE.md, docs/STAGE28E_PHASE_E_HANDOFF.md, docs/CURRENT_STATUS.md and docs/CONTINUATION_PLAN.md. Fetch fresh mvp/environment-controller HEAD and Local Agent daemon/result first. Treat Phase E as complete only if its exact-SHA docs gate passed. Then continue Stage28E Phase F with the focused single-instance binary-arbiter continuity/regression proof; keep outputs fake-locked, do not alter applyBinary() merely to fit V5, do not run the long soak before Phase G, and do not run the physical AH actuator path before Phase H.`
