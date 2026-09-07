# Fresh-context continuation plan

Updated: 2026-09-07
Work branch: `mvp/environment-controller`
Control branch: `agent-control`
Latest handoff: `docs/STAGE28E_PHASE_F_HANDOFF.md`
Stage28E execution guide: `docs/GUIDANCE.md`
Prior Stage28D evidence: `docs/STAGE28D_AH_ARBITER_HANDOFF.md`
Current status: `docs/CURRENT_STATUS.md`
Primary roadmap: `docs/PROJECT_ROADMAP.md`

## Read first in a new chat

1. `AGENTS.md`
2. `docs/GUIDANCE.md`
3. `docs/STAGE28E_PHASE_F_HANDOFF.md`
4. `docs/PROJECT_ROADMAP.md`
5. `docs/CURRENT_STATUS.md`
6. this file
7. `docs/STAGE28E_PHASE_E_HANDOFF.md` for measured memory optimization evidence
8. `docs/STAGE28E_PHASE_D_HANDOFF.md` for ownership-hardening evidence
9. `docs/STAGE28E_PHASE_C_HANDOFF.md` for the original memory baseline
10. `docs/STAGE28E_PHASE_B_HANDOFF.md` for reset/lifecycle diagnostics
11. `docs/STAGE28D_AH_ARBITER_HANDOFF.md` for historical V5 details
12. `docs/OBSERVABILITY_AND_INFERENCE_PLAN.md` when changing ventilation/inference/telemetry/ML behavior
13. `docs/SHELLY_POWER_FEEDBACK.md` when changing physical-state supervision

Then fetch fresh `mvp/environment-controller` HEAD, fresh `agent-control:.agent/status/daemon.json`, and the newest Local Agent result. Never continue from remembered chat state alone.

## Current transition

**Stage27C FROZEN -> Stage28E A COMPLETE -> B COMPLETE -> C COMPLETE -> D COMPLETE -> E COMPLETE -> F COMPLETE -> Phase G NEXT**

Stage28D functional AH work stays paused until A-G pass. Final physical `AH/rule request -> binary arbiter -> RF -> physical fan` verification belongs to Phase H.

## Phase identities

- Phase A exit SHA: `384e415eaaec960add2b3b3fe94db5c052ca6497`
- Phase B exit SHA: `e0fb5da17879569f791898ba793e1c02b195fab8`
- Phase C exit SHA: `7601f0beb95d27b2bf2360b760355c3c235871a1`
- Phase D implementation SHA: `09340089767cde117d12acc049790a2b93778b8e`
- Phase D formal docs exit SHA: `5e750b972eeff4ac8c9149ef6ea708f703d2d755`
- Phase E implementation head: `4a8ce18edd8cc90e6300929d2d9f035c4ec49eb5`
- Phase E formal docs exit SHA: `0d4325f08033a38e4fd3769c38b1572e344a27ff`
- Phase E evidence: `docs/STAGE28E_PHASE_E_HANDOFF.md`
- Phase F implementation SHA: `d88c77d8eab5013a6f94baf60e1404f5b030efdc`
- Phase F evidence: `docs/STAGE28E_PHASE_F_HANDOFF.md`

## Phase E retained runtime baseline

Phase E final bounded hardware evidence remains the reference for Phase G:

- image `743641 B`;
- internal free/min/largest `223792 / 223260 / 180224 B`;
- main configured stack `12288 B`, worst observed HWM `7240 B` free;
- `stage27_store` configured stack `6144 B`, worst observed HWM `1820 B` free;
- telemetry queue payload `4736 B` on explicit PSRAM path;
- telemetry `12` writes, `0` queue drops, `0` write errors;
- 11 heartbeats and heap-integrity PASS;
- Shelly master ON, median `65.5 W`;
- safe final state `fake-locked`;
- no coredump, counter regression, crash, corrupt heap or stack-canary marker.

Do not shrink either stack further before Phase G long-runtime evidence.

## Phase F decisive result

Phase F implementation SHA:

`d88c77d8eab5013a6f94baf60e1404f5b030efdc`

Only `test/test_stage28d_binary_role_arbiter/test_main.cpp` changed. Production `Stage28dBinaryRoleArbiter.{h,cpp}` remained unchanged from Phase E.

The deterministic single-instance V5 proof establishes:

- `0.099` below threshold remains OFF with zero dwell holds;
- 43 `0.111` calls inside minimum-OFF dwell increment cumulative holds exactly `0 -> 43` on one stable instance;
- `43 -> 1` is classified by the existing helper as a regression, while legitimate `uint32_t` wrap remains accepted;
- `0.111` at `119999 ms` remains OFF and advances `43 -> 44`;
- `0.111` at exactly `120000 ms` produces one OFF -> ON transition;
- dwell history remains `44` after the transition;
- continuity fault count remains `0`.

Local Agent task `20260907-growbox-stage28e-phase-f-arbiter-continuity-gate-v1` passed focused C++17 proof, exact-SHA checks, production-file identity checks, full existing host suite `24/24`, and clean-tree checks.

Interpretation: the historical V5 same-instance-style `43 -> 1` drop cannot be produced by normal continuous execution of the current arbiter semantics. Future reproduction is lifecycle/runtime evidence until proven otherwise.

## Formal Phase F exit gate

Before entering Phase G, run one final exact-SHA software exit gate on the Phase F docs HEAD.

It must:

1. verify work HEAD and origin match the exact docs SHA;
2. prove production arbiter code is unchanged from Phase E exit `0d4325f08033a38e4fd3769c38b1572e344a27ff`;
3. rerun the focused V5 continuity proof;
4. run the full host suite;
5. build the safe Stage27C firmware profile with all real-output/selftest flags disabled;
6. confirm generated Stage27C main stack remains `12288 B` and telemetry storage stack remains `6144 B`;
7. finish with clean worktree / `git diff --check`.

Record the passing docs SHA as formal Phase F exit SHA.

## Phase G — bounded runtime validation and soak

After the formal Phase F exit gate passes, start Phase G with a short bounded hardware run using safe fake-locked outputs.

### G1 short bounded gate

Use only resource `board:growbox-s3` and only `/dev/cu.usbserial-1130`.

Build/flash exact Phase F exit SHA with:

- `GROWBOX_STAGE28_REAL_OUTPUTS_ENABLED=0`
- `GROWBOX_STAGE28_THERMAL_TEST_SEQUENCE_ENABLED=0`
- `GROWBOX_RF433_LOOPBACK_ENABLED=0`
- `GROWBOX_STAGE28E_BREADCRUMB_RESTART_SELFTEST=0`

Capture and require:

1. exact firmware SHA;
2. stable boot/session ID and expected reset reason;
3. stable arbiter instance ID / construction count with no unexplained reconstruction;
4. cumulative arbiter counters never decrease on the same instance except legitimate wrap;
5. continuity fault count remains zero;
6. no coredump, Guru Meditation, corrupt heap, stack canary, watchdog, or heap-integrity failure;
7. internal free/min/largest block stay close to the Phase E reference and do not collapse;
8. PSRAM remains healthy;
9. main stack and `stage27_store` HWM retain accepted margin;
10. loop timing remains bounded;
11. BLE/sensor telemetry remains live;
12. telemetry storage continues with zero queue drops and zero write errors;
13. Shelly master remains ON;
14. final outputs remain `fake-locked`.

If G1 fails, stay in Phase G and preserve evidence. Do not start the long soak.

### G2 representative soak

Only after G1 passes, choose a representative duration from current runtime evidence and run the longer diagnostic soak.

Use low-overhead periodic summaries, not TRACE flooding. Preserve evidence immediately on any reset/session change, coredump, heap-integrity fault, counter regression, stack warning/critical event, watchdog, or unexplained object reconstruction.

Do not use a clean reboot to erase evidence before it is captured.

## Phase H after G

Only after Phase G passes, run the bounded physical E2E path:

`AH/rule request -> binary arbiter -> RF -> physical fan`

Capture request, arbiter pre-state/dwell/boot+instance, transition, RF result, physical/Shelly evidence, memory/stack/safety, then restore `fake-locked`.

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

1. Fetch fresh daemon and exact work-branch HEAD after these Phase F docs commits.
2. Queue the formal exact-SHA Phase F software exit gate; do not duplicate it if already present.
3. If PASS, record the final Phase F exit SHA and enter Phase G.
4. Queue one short bounded fake-locked G1 hardware run first.
5. Only after G1 PASS, plan and run the representative G2 soak.

## Recommended fresh-chat instruction

`Read AGENTS.md, docs/GUIDANCE.md, docs/STAGE28E_PHASE_F_HANDOFF.md, docs/CURRENT_STATUS.md and docs/CONTINUATION_PLAN.md. Fetch fresh mvp/environment-controller HEAD and Local Agent daemon/result first. Treat Phase F as complete only if its final exact-SHA software exit gate passed. Then continue Stage28E Phase G with a short bounded fake-locked hardware runtime before any long soak; preserve lifecycle/counter/coredump/heap/stack evidence on failure, use only /dev/cu.usbserial-1130, and do not run the physical AH actuator path before Phase H.`
