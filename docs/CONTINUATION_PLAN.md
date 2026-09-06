# Fresh-context continuation plan

Updated: 2026-09-07
Work branch: `mvp/environment-controller`
Control branch: `agent-control`
Latest handoff: `docs/STAGE28E_PHASE_D_HANDOFF.md`
Stage28E execution guide: `docs/GUIDANCE.md`
Prior Stage28D evidence: `docs/STAGE28D_AH_ARBITER_HANDOFF.md`
Current status: `docs/CURRENT_STATUS.md`
Primary roadmap: `docs/PROJECT_ROADMAP.md`

## Read first in a new chat

1. `AGENTS.md`
2. `docs/GUIDANCE.md`
3. `docs/STAGE28E_PHASE_D_HANDOFF.md`
4. `docs/PROJECT_ROADMAP.md`
5. `docs/CURRENT_STATUS.md`
6. this file
7. `docs/STAGE28E_PHASE_C_HANDOFF.md` for the memory baseline
8. `docs/STAGE28E_PHASE_B_HANDOFF.md` for reset/lifecycle diagnostics
9. `docs/STAGE28D_AH_ARBITER_HANDOFF.md` for historical V5 details
10. `docs/OBSERVABILITY_AND_INFERENCE_PLAN.md` when changing ventilation/inference/telemetry/ML behavior
11. `docs/SHELLY_POWER_FEEDBACK.md` when changing physical-state supervision

Then fetch fresh `mvp/environment-controller` HEAD, fresh `agent-control:.agent/status/daemon.json`, and the newest Local Agent result. Never continue from remembered chat state alone.

## Current transition

**Stage27C FROZEN -> Stage28E A COMPLETE -> B COMPLETE -> C COMPLETE -> D COMPLETE -> Phase E ACTIVE**

Stage28D functional AH work stays paused until A-G pass. Final physical `AH/rule request -> binary arbiter -> RF -> physical fan` verification belongs to Phase H.

## Phase identities

- Phase A exit SHA: `384e415eaaec960add2b3b3fe94db5c052ca6497`
- Phase B exit SHA: `e0fb5da17879569f791898ba793e1c02b195fab8`
- Phase C exit SHA: `7601f0beb95d27b2bf2360b760355c3c235871a1`
- Phase D implementation SHA: `09340089767cde117d12acc049790a2b93778b8e`
- Phase D complete evidence: `docs/STAGE28E_PHASE_D_HANDOFF.md`

## Phase D decisive result

Phase C identified a `5296 B` compiler-reported frame in the non-returning main runtime function.

D1 (`1aee13cb96eaebdf41a937c5622cce61f1a01b88`):

- introduced `RuntimeIoOwner` for telemetry storage + RF diagnostics;
- frame `5296 -> 3104 B`;
- host `24/24 PASS`;
- hardware HWM `10256 B`;
- internal free/min/largest `214740 / 214208 / 172032 B`;
- safe final state `fake-locked`.

D2 (`09340089767cde117d12acc049790a2b93778b8e`):

- introduced `RuntimeControlOwner` for controller/safety/thermal sequence;
- frame `3104 -> 2032 B`;
- total reduction `3264 B` (`~61.6%`);
- host `24/24 PASS`;
- image `743477 B`;
- `.bss` `10216 B`;
- hardware HWM `11336 B`;
- internal free/min/largest `213900 / 213264 / 172032 B`;
- PSRAM free/min/largest `8363512 / 8363108 / 8257536 B`;
- 11 heartbeats, heap-integrity PASS;
- Shelly master ON, median `65.5 W`;
- no coredump/counter regression/crash/corrupt heap/stack canary;
- safe final state `fake-locked`.

Phase D did not change allocator placement or control/AH/RF/safety semantics.

## Phase E — measured optimization

Start with telemetry storage because Phase C quantified a concrete internal-RAM cost.

Current exact facts:

- ordinary `pvPortMalloc()` uses `MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT` in this ESP-IDF 5.5.4 build;
- `CONFIG_SPIRAM_USE_CAPS_ALLOC=y`;
- `CONFIG_SPIRAM_USE_MALLOC` is not set;
- `CONFIG_FREERTOS_TASK_CREATE_ALLOW_EXT_MEM=y`;
- storage task stack is `7168 B` via ordinary `xTaskCreate()`;
- queue depth is `16`;
- `sizeof(Stage27TelemetrySnapshot) = 296 B`;
- queue payload alone is `4736 B` via ordinary `xQueueCreate()`.

### First Phase E slice

1. Read exact installed ESP-IDF 5.5.4 task/queue/static/caps API contracts; do not guess names or support.
2. Determine whether queue storage and/or task stack can be placed in external RAM safely.
3. Preserve queue semantics, logger lifetime, storage reliability and task priority.
4. Do not globally enable `CONFIG_SPIRAM_USE_MALLOC`.
5. Do not move ISR/DMA/RMT-sensitive buffers blindly.
6. Do not reduce `stage27_store` stack until real HWM and worst audited local frames justify the new size.
7. Make one coherent measured change at a time.
8. After each slice compare:
   - internal current/min/largest block;
   - PSRAM current/min/largest block;
   - task HWM;
   - firmware image/static memory;
   - storage queue drops/errors and write behavior;
   - loop/timing diagnostics.
9. Run host/build/size first; bounded fake-locked hardware only after software PASS.

### Later Phase E candidates

Only if measured evidence supports them:

- lower `stage27_store` stack from its current `7168 B` based on real HWM + frame margin;
- reduce telemetry/JSON/string transient churn;
- review service-console transient frames (`1648 B` RF receive, `1184 B` SD read);
- evaluate exact NimBLE/IDF allocation configuration only with before/after measurements.

## Phase F after E

Run the focused binary-arbiter continuity/regression proof. It must demonstrate that a continuous single instance cannot produce the historical cumulative drop `43 -> 1`; test dwell monotonicity and transition eligibility around the 120 s minimum-OFF boundary.

Do not modify `applyBinary()` merely to make the old V5 trace disappear.

## Phase G after F

Run bounded fake-locked runtime first, then the long-duration soak only after short stability is clean. Preserve evidence on any reset, coredump, heap-integrity fault, counter regression, stack alarm, watchdog, or unexplained boot/session change.

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

1. Run docs-only exact-SHA Phase D exit gate on fresh HEAD.
2. Record that passing SHA as formal Phase D exit SHA.
3. Start Phase E with a read-only ESP-IDF 5.5.4 caps-aware allocation/API audit for telemetry storage.
4. Implement the smallest measured storage-memory optimization slice.
5. Verify software first, hardware second.

## Recommended fresh-chat instruction

`Read AGENTS.md, docs/GUIDANCE.md, docs/STAGE28E_PHASE_D_HANDOFF.md, docs/CURRENT_STATUS.md and docs/CONTINUATION_PLAN.md. Fetch fresh mvp/environment-controller HEAD and Local Agent daemon/result first. Treat Phase D as complete only if its exact-SHA docs gate passed. Then continue Stage28E Phase E with measured telemetry-storage allocation optimization; do not globally enable PSRAM malloc, change AH behavior, or run the final physical actuator path before Phase H.`
