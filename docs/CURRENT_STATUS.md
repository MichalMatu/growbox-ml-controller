# Current controller status

Updated: 2026-09-07
Development branch: `mvp/environment-controller`
Latest handoff: `docs/STAGE28E_PHASE_F_HANDOFF.md`
Stage28E execution guide: `docs/GUIDANCE.md`
Prior Stage28D evidence: `docs/STAGE28D_AH_ARBITER_HANDOFF.md`
Primary roadmap: `docs/PROJECT_ROADMAP.md`
Continuation checklist: `docs/CONTINUATION_PLAN.md`

## Current transition

**Stage27C FROZEN -> Stage28E Phase A COMPLETE -> B COMPLETE -> C COMPLETE -> D COMPLETE -> E COMPLETE -> F COMPLETE -> Phase G NEXT**

Stage28D functional AH work remains paused. The active program remains Stage28E A -> H. Phase G is bounded fake-locked runtime validation followed by a representative soak only after the short gate is clean. Do not return to the final physical AH actuator path before Phase H.

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

Always fetch fresh work-branch HEAD and Local Agent daemon state before editing or queueing work.

## Phase C quantitative baseline

Default/safe firmware baseline before Phase D:

- image: `743369 B`
- `.data`: `20512 B`
- `.bss`: `6672 B`
- DIRAM used: `124771 B / 341760 B`
- DIRAM remaining: `216989 B`
- main runtime compiler frame: `5296 B`
- bounded main HWM: about `7984-8064 B`
- internal free/min/largest: `217444 / 216808 / 176128 B`
- PSRAM free/min/largest: `8363512 / 8363108 / 8257536 B`

The historical approximately 1 KiB internal-RAM condition was not reproduced.

## Phase D completed ownership hardening

D1 `1aee13cb96eaebdf41a937c5622cce61f1a01b88` introduced explicit process-lifetime ownership for telemetry storage and RF diagnostics.

D2 `09340089767cde117d12acc049790a2b93778b8e` introduced explicit process-lifetime ownership for `ClimateRuntimeController`, `LampSafetyController`, and `ThermalTestSequence`.

Result:

- main runtime compiler frame `5296 -> 2032 B` (`-3264 B`, about `61.6%`);
- D2 hardware main HWM `11336 B`;
- D2 internal free/min/largest `213900 / 213264 / 172032 B`;
- image `743477 B`;
- `.bss` `10216 B`;
- host tests `24/24 PASS`;
- no coredump/counter regression/crash/corrupt heap/stack canary;
- Shelly median about `65.5 W`;
- safe final state `fake-locked`.

Phase D intentionally stopped at a `2032 B` compiler frame instead of moving progressively smaller automatic objects.

## Phase E completed measured optimization

Full evidence: `docs/STAGE28E_PHASE_E_HANDOFF.md`.

### E1 — telemetry queue payload to PSRAM

Implementation SHA:

`4a5121abf2a93ba76bfc219575d2b52b8025fb03`

- queue payload `16 x 296 B = 4736 B` uses explicit `MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT`;
- `StaticQueue_t` metadata stays internal;
- fallback remains the original internal `xQueueCreate()` path;
- `CONFIG_SPIRAM_USE_MALLOC` remains disabled;
- host tests `24/24 PASS`;
- hardware marker `queue_psram=1 queue_bytes=4736`;
- internal free/min/largest `218672 / 218140 / 176128 B`;
- gain vs D2 `+4772 / +4876 B` free/min;
- telemetry `12` writes, `0` queue drops, `0` write errors;
- safe final state `fake-locked`.

### E2 — `stage27_store` stack right-sizing

Implementation SHA:

`c2aff0a14bbcca567de4083a284d3522fa52421e`

- stack `7168 -> 6144 B`;
- host tests `24/24 PASS`;
- hardware internal free/min/largest `219568 / 219036 / 176128 B`;
- gain vs E1 `+896 / +896 B` free/min;
- worst observed `stage27_store` HWM `1884 B`, later `1820 B` in E3;
- telemetry `12` writes, `0` drops, `0` write errors;
- safe final state `fake-locked`.

Do not reduce this stack further before longer Phase G evidence.

### E3 — Stage27C main stack right-sizing

Implementation SHA:

`4a8ce18edd8cc90e6300929d2d9f035c4ec49eb5`

- only Stage27C overlay changes main stack `16384 -> 12288 B`;
- base project default stays `16384 B`;
- generated Stage27C sdkconfig confirms `CONFIG_ESP_MAIN_TASK_STACK_SIZE=12288`;
- host tests `24/24 PASS`;
- image `743641 B`;
- hardware internal free/min/largest `223792 / 223260 / 180224 B`;
- gain vs E2 `+4224 / +4224 B` free/min;
- cumulative gain vs D2 `+9892 B free`, `+9996 B min`, `+8192 B largest block`;
- main worst observed HWM `7240 B` free;
- `stage27_store` worst HWM `1820 B` free;
- telemetry `12` writes, `0` drops, `0` write errors;
- 11 heartbeats and heap-integrity PASS;
- Shelly median `65.5 W`;
- safe final state `fake-locked`.

Phase E stops here. Further stack cuts have diminishing value and should wait for Phase G long-runtime evidence.

## Verified allocation policy

For this ESP-IDF 5.5.4 Stage27C build:

- `CONFIG_SPIRAM_USE_CAPS_ALLOC=y`;
- `CONFIG_SPIRAM_USE_MALLOC` is not set;
- `CONFIG_FREERTOS_TASK_CREATE_ALLOW_EXT_MEM=y`;
- broad allocator policy was not changed;
- RMT/ISR/DMA-sensitive buffers were not moved to PSRAM.

## Phase F completed arbiter continuity proof

Full evidence: `docs/STAGE28E_PHASE_F_HANDOFF.md`.

Implementation SHA:

`d88c77d8eab5013a6f94baf60e1404f5b030efdc`

Phase F changed only `test/test_stage28d_binary_role_arbiter/test_main.cpp`. Production `Stage28dBinaryRoleArbiter.{h,cpp}` remained unchanged from the Phase E exit SHA.

Deterministic single-instance result:

- synchronized safe OFF at `0 ms`;
- request `0.099` stays OFF with zero dwell holds;
- 43 requests at `0.111` inside minimum-OFF dwell advance the same instance's cumulative dwell counter exactly `0 -> 43`;
- the existing regression helper classifies `43 -> 1` as a regression;
- request `0.111` at `119999 ms` stays OFF and advances `43 -> 44`;
- request `0.111` at exactly `120000 ms` performs one OFF -> ON transition;
- dwell history remains `44` after transition;
- continuity faults remain `0`;
- next same-state call remains monotonic.

Local Agent gate `20260907-growbox-stage28e-phase-f-arbiter-continuity-gate-v1` passed:

- exact SHA verification PASS;
- focused C++17 proof PASS;
- existing host tests `24/24 PASS`;
- clean worktree / `git diff --check` PASS.

Conclusion: the historical V5 same-instance-style dwell counter drop `43 -> 1` cannot arise from normal continuous execution of the current arbiter semantics except legitimate integer wrap. A future recurrence must be treated as lifecycle/runtime evidence until proven otherwise.

## Phase G next goal

Start with one short, bounded fake-locked hardware runtime. Do not begin the long soak until the short gate is clean.

Required short-run evidence:

1. exact firmware SHA, boot/session ID and expected reset reason;
2. stable arbiter instance/construction count with no unexplained reconstruction;
3. no `arbiter_counter_regression` or continuity fault;
4. no coredump, crash, corrupt heap, stack warning/critical event or watchdog marker;
5. internal free/min/largest block remains within accepted Phase E margins;
6. PSRAM remains healthy;
7. main and `stage27_store` HWM retain adequate margin;
8. BLE/sensors/telemetry remain active with zero queue drops/write errors;
9. loop timing remains bounded;
10. Shelly master stays ON and final state is `fake-locked`.

Only after the short bounded run passes should Phase G queue a representative longer diagnostic soak. Any reset/session change or integrity fault preserves evidence and stops forward progress.

Final physical `AH/rule request -> binary arbiter -> RF -> physical fan` remains Phase H.

## Safety boundary

Correct Growbox serial device:

`/dev/cu.usbserial-1130`

Never open, probe, monitor, reset or flash:

`/dev/cu.usbserial-10`

Standing invariants:

- rule controller authoritative;
- ML shadow/research-only;
- thermal trip `>=28 C`;
- recovery `<=26 C` continuously for 10 minutes;
- manual RF blocked during `real-bounded`;
- Shelly master stays ON;
- no unattended real-output mode;
- after bounded diagnostics restore/prove `fake-locked` safe state.

## Immediate next work

1. Run one formal exact-SHA Phase F software exit gate on the fresh work-branch docs HEAD.
2. The gate must re-run the focused arbiter proof, full host suite and Stage27C firmware build while proving production arbiter code is unchanged from Phase E.
3. Record the passing docs SHA as the formal Phase F exit SHA.
4. Enter Phase G only after that gate passes.
5. Run one short bounded fake-locked hardware validation before any longer soak.

Do not run the long soak before the short Phase G gate passes and do not return to a real AH actuator transition before Phase H.
