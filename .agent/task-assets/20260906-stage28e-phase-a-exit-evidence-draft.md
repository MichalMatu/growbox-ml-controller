# Stage28E Phase A exit evidence draft

Status: **draft only — do not mark Phase A complete until the pending hardware confirmation is resolved and the work-branch docs/exit gate are published.**

Repository: `MichalMatu/growbox-ml-controller`
Work branch: `mvp/environment-controller`
Agent binding: `815cf40f-8d2a-4e1f-b7cc-c0f4e37b6cb5`
Correct board resource: `board:growbox-s3`
Correct serial port: `/dev/cu.usbserial-1130`
Forbidden unrelated port: `/dev/cu.usbserial-10`

## Starting point

Phase A original starting executable lineage:

- `2218ad30401222537cb568541d80bc07adc2c0eb` — `Require Stage28E guidance during bootstrap`

Baseline CrowPanel N8R8 image and static memory:

- image: `726061 B`
- Flash Code `.text`: `467426 B`
- Flash Data: `126308 B`
- DIRAM used: `119759 B` (`35.04%`), `222001 B` remaining
- `.data`: `19240 B`
- `.bss`: `3848 B`
- IRAM: `16384 B` used
- RTC SLOW: `32 B`
- RTC FAST: `24 B`

The baseline disproved the idea that static DIRAM itself was near a ~1 KiB limit; runtime heap/stack evidence was required.

## Phase A implementation evidence

### A1 diagnostics core

Published source commits:

- `e349fa26c4bb5b4caffba5022db9d4adeefa5cf2` — Add Stage28E diagnostics core types
- `5dc7c598525b3a7d2030cc54b25a7030c13d757f` — Implement Stage28E diagnostics core
- `17ad185cf80b5e6f2e1aadd29a40aa0ea2259fad` — Test Stage28E diagnostics core
- `f43a34feea2aa77c101d0a6583eb5b831d08ef87` — Make Stage28E diagnostics core header-only
- `1d5ec2999668fa93eab417fd45b80731dba2914e` — Remove redundant diagnostics core source

Core provides fixed-size/no-dynamic-allocation representations for log levels/modules, heap metrics, stack metrics/severity, boot identity and timing accumulators.

### A2/A3 boot identity and memory metrics

Published work-branch commits include:

- `78056fc...` — Expose Stage28E boot and heap metrics
- `85b594d546bbd3f8886c432f90f26c2e79eda0b1` — Log Stage28E boot identity

A2/A3 image: `727417 B`, delta vs baseline `+1356 B`; DIRAM delta `+48 B`.

Runtime status exposes firmware SHA, boot ID, reset reason, uptime, output mode, and internal/PSRAM total/free/min-ever/largest-block metrics.

### A4 task/stack diagnostics

Published commits:

- `0d48f80a...` — Enable Stage28E task snapshot support
- `1376601b...` — Expose telemetry task stack size
- `b338a709...` — Reuse telemetry task stack constant
- `c284b811e8973f8d1628f1eab8e2a641be49d4dc` — Report Stage28E task stack diagnostics

Exact ESP-IDF contract findings:

- `uxTaskGetStackHighWaterMark()` reports bytes on this installed ESP-IDF/FreeRTOS port.
- CrowPanel non-SMP `TaskStatus_t` has no `xCoreID`; implementation correctly uses `xTaskGetCoreID(task.xHandle)`.
- task snapshot transient allocation is in PSRAM and freed after status generation.
- warning threshold is `<25%`; critical threshold is `<10%`.

A4 image: `728829 B`.

### A5 runtime timing

Published work-branch timing lineage completed at:

- `c055bb2d0568b3b826e2ec92b755051dfea3d258`

Timing metrics cover service console, RF tick, control cycle, telemetry and active loop, using `esp_timer_get_time()` and fixed accumulators without per-loop dynamic allocation.

A5 image: `729809 B`.

### A1 logging facade completion

Published facade commits:

- `66fb4ca37c7d68804f1f4cd2b7c3a10e708a68d2` — Add Stage28E logging facade
- `fa93e860accde09d9a8c87830285dd3911e2500b` — Implement Stage28E logging facade
- `2eaa33efde0b27184733d1dd94d8c8197406f248` — Wire Stage28E logging facade
- `3058625be2f35c121afcf82549d5c73068839ecd` — Use Stage28E boot logging facade

Exact published gate `20260906-growbox-stage28e-phase-a1-log-facade-published-v1` passed:

- work/origin exact `3058625be2f35c121afcf82549d5c73068839ecd`
- deterministic payload-vs-published blobs matched
- standalone diagnostics core tests passed
- host suite `24/24` passed
- safe CrowPanel N8R8 build passed
- `idf.py size` passed
- `git diff --check` and clean-tree checks passed

Final Phase-A source image before docs: `730821 B`.

Growth:

- vs baseline `726061 B`: `+4760 B`
- facade alone vs A5 `729809 B`: `+1012 B`

The generated build config is INFO default/max with dynamic ESP log level control. Stage28E facade therefore uses its own compile-time gate and module filter and writes through `esp_log_write`; DEBUG/TRACE are structurally available but compile out by default at Stage28E INFO level.

## Bounded hardware diagnostic evidence

Task: `20260906-growbox-stage28e-phase-a-hardware-diag-v1`
Firmware: exact `3058625be2f35c121afcf82549d5c73068839ecd`
Port: only `/dev/cu.usbserial-1130`
Build/runtime safety configuration:

- `GROWBOX_STAGE28_REAL_OUTPUTS_ENABLED=0`
- `GROWBOX_STAGE28_THERMAL_TEST_SEQUENCE_ENABLED=0`
- `GROWBOX_RF433_LOOPBACK_ENABLED=0`
- output state confirmed `fake-locked`

Useful complete snapshot:

- `boot_id=30b159d6`
- `reset_reason=1`
- `uptime_ms=35869`
- internal total `341620 B`
- internal free `221648 B`
- internal minimum-ever free `221028 B`
- internal largest block `180224 B`
- PSRAM total `8388608 B`
- PSRAM free `8363512 B`
- PSRAM minimum-ever free `8363108 B`
- PSRAM largest block `8257536 B`
- main stack HWM `8140/16384 B` (~49.7%, normal)
- stage27_store stack HWM from complete line `2908/7168 B` (~40.6%, normal)
- nimble_host stack HWM `1688/4096 B` (~41.2%, normal)
- esp_timer stack HWM `3348/3584 B` (~93.4%, normal)
- loop samples `34`
- loop max `194320 us`
- loop budget `1000000 us`
- loop overruns `0`
- control max `21607 us`
- RF max `9 us`
- telemetry max `183523 us`
- service-console max observed `35779 us`

A serial capture ended with a truncated task line showing `hwm_bytes=29`; this was not a real 29-byte HWM. An immediately preceding complete task line in the same hardware run showed `stage27_store ... hwm_bytes=2908 ... severity=normal`. The truncation was caused by the harness reading a partial UART buffer.

No Phase-A stop condition was observed in the complete snapshot: no critical known task stack, no loop overrun, no unsafe internal heap, no largest-block collapse, and outputs remained fake-locked.

## Pending confirmation / infrastructure blocker

Confirmation task v1 (`20260906-growbox-stage28e-phase-a-hardware-confirm-v1`) failed because the parser stopped on an earlier service-console prompt/menu before the requested status block. This was a harness/parser failure, not a firmware failure.

Confirmation v2 (`20260906-growbox-stage28e-phase-a-hardware-confirm-v2`) is queued with:

- exact required `agent_binding`
- `resources: ["board:growbox-s3"]`
- only `/dev/cu.usbserial-1130`
- no flash/write to firmware
- three fixed-time-window status snapshots
- stable boot-ID/reset-reason requirement
- complete known-task stack margin requirement >=25%
- zero loop-overrun requirement

However Local Agent `daemon.json` became stale while still reporting v1 as running. Last observed stale state:

- daemon `4.18.4`
- worker PID `76300`
- `state=running`
- `current_task_id=20260906-growbox-stage28e-phase-a-hardware-confirm-v1`
- active resource `board:growbox-s3`
- `updated_at=2026-09-06T07:22:50.722145+00:00`

The v1 result had already been committed as failed at `2026-09-06T07:23:10Z`, proving the published daemon status was stale. No supported recovery control file exists in this repository; `.agent/daemon/` contains only `.gitkeep`. Do not fabricate a restart/cancel mechanism and do not access the board concurrently.

## Phase A exit interpretation

The first complete bounded hardware snapshot already answers the formal Phase A diagnostic questions:

1. Which boot? `boot_id=30b159d6`, firmware `3058625b...`.
2. Why reset? ESP-IDF `reset_reason=1`.
3. Internal heap now/min/largest? `221648 / 221028 / 180224 B`.
4. PSRAM now/min/largest? `8363512 / 8363108 / 8257536 B`.
5. Lowest known configured-task margin in the complete captured set? `stage27_store`, `2908/7168 B`, ~40.6%, normal.
6. Worst observed active-loop latency? `194320 us` with `0` overruns against a `1 s` budget.

This evidence strongly rejects the earlier unverified ~1 KiB internal-free concern for this representative bounded runtime window.

Still required before declaring Phase A closed:

- resolve/complete the queued confirmation or explicitly disposition it after Local Agent worker recovery;
- update work-branch `docs/GUIDANCE.md`, `docs/CURRENT_STATUS.md`, and `docs/STAGE28D_AH_ARBITER_HANDOFF.md` with material Phase-A findings;
- make the separate English Phase-A documentation/exit commit;
- run the final exact-SHA Phase-A exit gate on the resulting work-branch SHA;
- record the resulting Phase-A SHA;
- only then start Phase B.
