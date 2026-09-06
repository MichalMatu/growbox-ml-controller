# Stage28E Phase A handoff — observability foundation

Updated: 2026-09-06
Repository: `MichalMatu/growbox-ml-controller`
Work branch: `mvp/environment-controller`
Control branch: `agent-control`
Agent binding: `815cf40f-8d2a-4e1f-b7cc-c0f4e37b6cb5`

This handoff closes Stage28E Phase A and supersedes the older Stage28D-only immediate-next-work instructions for the current development sequence. Stage28D functional work remains paused until Stage28E A-G completes.

## Phase A identity

Phase A started from:

`2218ad30401222537cb568541d80bc07adc2c0eb`

The bounded hardware diagnostic firmware was built from and verified at:

`3058625be2f35c121afcf82549d5c73068839ecd`

The Phase A implementation adds diagnostics only; it does not intentionally change controller, AH, arbiter, RF, or safety semantics.

## What Phase A implemented

### Structured logging

The Stage28E logging facade provides:

- levels `ERROR`, `WARN`, `INFO`, `DEBUG`, `TRACE`;
- modules `SYS`, `MEM`, `TASK`, `BLE`, `SENSOR`, `CONTROL`, `AH`, `ARBITER`, `RF`, `SHELLY`, `STORAGE`, `TELEMETRY`, `SAFETY`, `WATCHDOG`;
- compile-time gating with default compiled level `INFO`;
- module-specific runtime filtering;
- fixed-size formatting buffers and no intentional per-loop heap allocation;
- compact records carrying uptime, boot ID, sequence, level/module, task and core where available.

The generated ESP-IDF configuration has maximum normal ESP log level `INFO`. DEBUG/TRACE remain structurally available through the Stage28E facade but are compile-gated by default; do not claim ordinary ESP-IDF runtime DEBUG/TRACE output without separately verifying the selected build configuration.

### Boot/session identity

Runtime diagnostics expose:

- firmware SHA;
- boot/session ID;
- `esp_reset_reason()`;
- uptime.

This allows later phases to distinguish reboot from same-boot object reconstruction or state corruption.

### Memory metrics

Runtime diagnostics expose capability-specific metrics for internal RAM and PSRAM:

- total;
- current free;
- minimum-ever free;
- largest free block.

### Task/stack diagnostics

The task snapshot reports task name, core, priority, configured stack where known, current/worst high-water mark and severity.

Important verified ESP-IDF contract for this build:

- FreeRTOS high-water marks are reported in **bytes**, not words;
- non-SMP `TaskStatus_t` does not provide `xCoreID`; use `xTaskGetCoreID(task.xHandle)`;
- warning threshold is below 25% remaining stack;
- critical threshold is below 10%.

The task-status array is transiently allocated in PSRAM for the diagnostic snapshot and released afterward.

### Timing diagnostics

Aggregate timing is recorded for service-console work, RF tick, control cycle, telemetry and active loop work, including maximum duration and loop-overrun count. The normal loop budget used by the Phase A diagnostic is 1 second.

## Software/build evidence

Original Phase A baseline image:

- firmware image: `726061 B`;
- DIRAM: `119759 B` used, `222001 B` remaining of `341760 B`;
- IRAM: `16384 B` used;
- Flash Code `.text`: `467426 B`;
- Flash Data: `126308 B`.

Final Phase A diagnostic image at `3058625...`:

- firmware image: `730821 B`.

Net image increase versus the original baseline:

- `+4760 B`.

Focused host verification and the full CrowPanel N8R8 firmware build passed during Phase A development.

## Bounded hardware diagnostic — PASS

Task:

`20260906-growbox-stage28e-phase-a-hardware-diag-v1`

The diagnostic was run only on:

- resource `board:growbox-s3`;
- serial `/dev/cu.usbserial-1130`.

`/dev/cu.usbserial-10` belongs to another project and must never be opened, probed, monitored, reset or flashed by Growbox work.

The firmware was fake-locked with real outputs disabled. No AH actuator transition experiment was performed.

Representative captured snapshot:

```text
firmware_sha=3058625be2f35c121afcf82549d5c73068839ecd
boot_id=30b159d6
reset_reason=1
uptime_ms=35869
outputs=fake-locked
rf_ready=0
internal_total=341620
internal_free=221648
internal_min=221028
internal_largest=180224
psram_total=8388608
psram_free=8363512
psram_min=8363108
psram_largest=8257536
stack_high_water=8140
current_task_stack_hwm_bytes=8140
task_total=9
task_captured=9
task_snapshot_psram=1
```

Timing evidence:

```text
loop_samples=34
loop_max_us=194320
loop_overruns=0
loop_budget_us=1000000
control_samples=34
control_max_us=21607
rf_samples=34
rf_max_us=9
telemetry_samples=4
telemetry_max_us=183523
console_samples=34
console_max_us=35779
```

Known configured-stack margins from the same run:

- `main`: configured `16384 B`, HWM `8140 B`, normal;
- `stage27_store`: configured `7168 B`, HWM `2908 B`, normal;
- `esp_timer`: configured `3584 B`, HWM `3348 B`, normal;
- `nimble_host`: configured `4096 B`, HWM `1688 B`, normal.

Among tasks with a known configured size, `stage27_store` had the lowest percentage margin, about 40.6%. `nimble_host` had the lowest raw HWM but still about 41.2% margin. No known task was in warning or critical range.

A diagnostic capture once ended mid-UART-line and displayed `stage27_store hwm_bytes=29`. That value is invalid truncation evidence. A complete earlier line in the same run reported `2908 B`; never use `29 B` as a real HWM measurement.

## Phase A exit questions — answered

1. **Which boot is running?**  
   The bounded diagnostic identified boot `30b159d6` and firmware `3058625...`.

2. **Why did it boot/reset?**  
   `reset_reason=1`, corresponding to the expected power-on reset after the diagnostic flash/reboot, with no crash/reset evidence in the bounded run.

3. **Internal heap now/min/largest?**  
   Current `221648 B`, minimum-ever `221028 B`, largest free block `180224 B`.

4. **PSRAM now/min/largest?**  
   Current `8363512 B`, minimum-ever `8363108 B`, largest free block `8257536 B`.

5. **Lowest-stack task?**  
   For tasks with known configured sizes, `stage27_store` had the lowest percentage margin at about 40.6%; all known tasks remained above the 25% warning threshold.

6. **Worst observed loop latency?**  
   `194320 us` with a `1000000 us` budget and `0` overruns.

## Interpretation

The previously suspected approximately 1 KiB internal-memory crisis is **not reproduced** by the bounded Phase A measurement. The diagnostic run shows substantial current, minimum-ever and largest-block internal-memory headroom under active BLE/sensor/telemetry operation.

This does not yet prove long-duration fragmentation cannot occur. Phase C must still map static/stack/heap ownership and representative allocation paths, while Phase G will provide bounded runtime/soak evidence.

The V5 `arbiter_dwell_holds 43 -> 1` discontinuity remains unresolved. Phase A supplies the observability needed to investigate it; it does not claim a root cause.

## Hardware confirmation harness notes

Two additional read-only hardware confirmation attempts were intentionally not used as product-failure evidence:

- `20260906-growbox-stage28e-phase-a-hardware-confirm-v1` failed because the parser stopped on an earlier/stale prompt before a complete requested status response;
- `20260906-growbox-stage28e-phase-a-hardware-confirm-v2` ran after Local Agent recovery and again failed because its fixed 5-second collection window did not contain a complete line beginning with `status `.

For v2, command 1 passed and proved:

- local HEAD exactly `3058625...`;
- remote work branch exactly `3058625...`;
- clean work tree;
- `/dev/cu.usbserial-1130` present.

The v2 UART tail contained normal runtime/startup output and `outputs=fake-locked`; no crash, coredump, unsafe transition or stack/memory alarm was reported. Because the original bounded diagnostic already produced a complete valid snapshot satisfying all Phase A exit questions, a third identical confirmation harness is not required to close Phase A.

## Latest safe state

The bounded Phase A diagnostic verified the firmware in fake-locked mode with no real-output AH transition. The standing safety boundary remains:

- fake-locked after diagnostics;
- lamp ON when restoring the normal safe physical baseline;
- fan OFF;
- humidifier OFF;
- Shelly master ON;
- real-output experiments only when explicitly bounded by a later phase.

## Stage28E next phase

Proceed to **Phase B — crash, reset, corruption, and lifecycle diagnostics** only after the Phase A docs-only exit gate passes on the exact Phase A closing SHA.

Phase B should start with a read-only Local Agent inspection of the installed ESP-IDF coredump symbols and the exact 8 MiB partition-table bounds before changing configuration.

Known current partition layout to verify, not blindly edit:

```csv
nvs,       data, nvs,     0x9000,  0x6000
phy_init,  data, phy,     0xf000,  0x1000
factory,   app, factory,  0x10000, 0x400000
telemetry, data, fat,     0x410000,0x200000
```

Phase B then covers flash coredump support, bounded crash breadcrumbs, lifecycle/instance IDs for critical runtime objects, state sentinels, targeted heap-integrity checks and subsystem heartbeats.
