# Current controller status

Updated: 2026-09-07
Development branch: `mvp/environment-controller`
Latest handoff: `docs/STAGE28E_PHASE_D_HANDOFF.md`
Stage28E execution guide: `docs/GUIDANCE.md`
Prior Stage28D evidence: `docs/STAGE28D_AH_ARBITER_HANDOFF.md`
Primary roadmap: `docs/PROJECT_ROADMAP.md`
Continuation checklist: `docs/CONTINUATION_PLAN.md`

## Current transition

**Stage27C FROZEN -> Stage28E Phase A COMPLETE -> B COMPLETE -> C COMPLETE -> D COMPLETE -> Phase E ACTIVE**

Stage28D functional AH work remains paused. The active program remains Stage28E A -> H. Phase E now performs measured memory/allocation/hot-path optimization. Do not return to the final physical AH actuator path before Phase H.

## Phase identities

- Phase A exit SHA: `384e415eaaec960add2b3b3fe94db5c052ca6497`
- Phase B exit SHA: `e0fb5da17879569f791898ba793e1c02b195fab8`
- Phase C exit SHA: `7601f0beb95d27b2bf2360b760355c3c235871a1`
- Phase D implementation SHA: `09340089767cde117d12acc049790a2b93778b8e`
- Phase D evidence: `docs/STAGE28E_PHASE_D_HANDOFF.md`

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

D1 commit:

`1aee13cb96eaebdf41a937c5622cce61f1a01b88`

D1 introduced explicit process-lifetime ownership for telemetry storage and RF diagnostics.

D1 evidence:

- runtime frame `5296 -> 3104 B`
- reduction `2192 B`
- host tests `24/24 PASS`
- image `743541 B`
- `.bss` `9248 B`
- hardware HWM `10256 B`
- internal free/min/largest `214740 / 214208 / 172032 B`
- 10 heartbeats, heap-integrity PASS
- Shelly master ON, median `65.5 W`
- safe final state `fake-locked`

D2 commit:

`09340089767cde117d12acc049790a2b93778b8e`

D2 introduced explicit process-lifetime ownership for `ClimateRuntimeController`, `LampSafetyController`, and `ThermalTestSequence`.

D2 evidence:

- runtime frame `3104 -> 2032 B`
- total reduction from Phase C: `3264 B` (`~61.6%`)
- host tests `24/24 PASS`
- image `743477 B`
- `.bss` `10216 B`
- hardware HWM `11336 B`
- internal free/min/largest `213900 / 213264 / 172032 B`
- PSRAM free/min/largest `8363512 / 8363108 / 8257536 B`
- 11 heartbeats, heap-integrity PASS
- no coredump, arbiter counter regression, crash, corrupt heap, or stack-canary marker
- Shelly master ON, median `65.5 W`
- safe final state `fake-locked`

Phase D intentionally stopped at a `2032 B` main runtime frame rather than moving progressively smaller automatic objects for marginal benefit. No allocator or PSRAM policy was changed in Phase D.

## Verified FreeRTOS/internal-RAM allocation contract

For this ESP-IDF 5.5.4 build:

- ordinary `pvPortMalloc()` uses `MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT`;
- `CONFIG_SPIRAM_USE_CAPS_ALLOC=y`;
- `CONFIG_SPIRAM_USE_MALLOC` is not set;
- `CONFIG_FREERTOS_TASK_CREATE_ALLOW_EXT_MEM=y`.

Therefore ordinary `xTaskCreate()` and `xQueueCreate()` consume internal RAM unless an explicit caps-aware path is selected.

Current telemetry-storage costs:

- `stage27_store` task stack: `7168 B` plus task control allocation;
- `Stage27TelemetrySnapshot`: `296 B`;
- queue depth: `16`;
- queue payload: `4736 B` plus queue metadata/allocator overhead.

## Phase E active goal

Phase E is measured optimization, not broad configuration churn.

First target: telemetry storage allocation placement and stack sizing.

Required order:

1. verify exact ESP-IDF 5.5.4 caps-aware task/queue/static APIs and constraints;
2. decide which storage allocations are safe for PSRAM/external memory;
3. do not move RMT/ISR/DMA-sensitive buffers blindly;
4. do not globally enable `CONFIG_SPIRAM_USE_MALLOC`;
5. preserve task semantics and storage reliability;
6. compare internal free/min/largest, PSRAM usage, stack HWM, firmware size and timing before/after;
7. use bounded fake-locked hardware verification after software PASS.

Potential Phase E targets after telemetry storage:

- reduce transient serialization/string churn only where measured;
- evaluate `stage27_store` stack from real HWM before reducing it;
- review service-console transient frames;
- leave IDF/NimBLE changes evidence-driven only.

## V5 issue remains open but instrumented

The prior Stage28D anomaly remains:

`arbiter_dwell_holds 33 -> 43 -> 1 -> 11`

Phase B-D did not reproduce a same-instance regression. Do not change `Stage28dBinaryRoleArbiter::applyBinary()` based only on old V5 evidence. Phase F will run the focused continuity/regression proof.

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

1. Run one docs-only exact-SHA Phase D exit gate on the fresh work-branch HEAD.
2. Record that SHA as the formal Phase D exit SHA.
3. Start Phase E with a read-only ESP-IDF/API capability audit for telemetry task/queue allocation.
4. Make the smallest measured optimization slice and run host/build/size checks.
5. Run bounded fake-locked hardware only after software PASS.

Do not run the long soak before Phase G and do not return to a real AH actuator transition before Phase H.
