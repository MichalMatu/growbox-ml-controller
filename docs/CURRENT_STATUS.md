# Current controller status

Updated: 2026-09-07
Development branch: `mvp/environment-controller`
Latest handoff: `docs/STAGE28E_PHASE_E_HANDOFF.md`
Stage28E execution guide: `docs/GUIDANCE.md`
Prior Stage28D evidence: `docs/STAGE28D_AH_ARBITER_HANDOFF.md`
Primary roadmap: `docs/PROJECT_ROADMAP.md`
Continuation checklist: `docs/CONTINUATION_PLAN.md`

## Current transition

**Stage27C FROZEN -> Stage28E Phase A COMPLETE -> B COMPLETE -> C COMPLETE -> D COMPLETE -> E COMPLETE -> Phase F NEXT**

Stage28D functional AH work remains paused. The active program remains Stage28E A -> H. Phase F is the focused binary-arbiter continuity/regression proof. Do not return to the final physical AH actuator path before Phase H.

## Phase identities

- Phase A exit SHA: `384e415eaaec960add2b3b3fe94db5c052ca6497`
- Phase B exit SHA: `e0fb5da17879569f791898ba793e1c02b195fab8`
- Phase C exit SHA: `7601f0beb95d27b2bf2360b760355c3c235871a1`
- Phase D implementation SHA: `09340089767cde117d12acc049790a2b93778b8e`
- Phase D formal docs exit SHA: `5e750b972eeff4ac8c9149ef6ea708f703d2d755`
- Phase E implementation head: `4a8ce18edd8cc90e6300929d2d9f035c4ec49eb5`
- Phase E evidence: `docs/STAGE28E_PHASE_E_HANDOFF.md`

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

## Phase F next goal

Phase F must prove the Stage28D/V5 arbiter behavior from synthetic, single-instance evidence rather than inference.

Required proof:

1. use one known binary-arbiter instance with lifecycle/boot identity visible;
2. hold requests below threshold and around minimum-OFF dwell;
3. prove cumulative dwell-hold counters remain monotonic within one instance except allowed integer wrap;
4. prove the historical same-instance-style `43 -> 1` drop cannot arise from normal `applyBinary()` execution;
5. after the full `120 s` minimum-OFF dwell, prove an eligible `0.111` request can transition ON;
6. keep physical outputs `fake-locked`;
7. do not change `applyBinary()` merely to fit historical V5 logs.

Long runtime soak remains Phase G. Final physical `AH/rule request -> binary arbiter -> RF -> physical fan` remains Phase H.

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

1. Run one docs-only exact-SHA Phase E exit gate on the fresh work-branch HEAD.
2. Record that SHA as the formal Phase E exit SHA.
3. Enter Phase F only after that gate passes.
4. Build the focused synthetic arbiter continuity/regression diagnostic with no physical actuator output.
5. Run focused host proof first, then only the bounded fake-locked runtime evidence required by Phase F.

Do not run the long soak before Phase G and do not return to a real AH actuator transition before Phase H.
