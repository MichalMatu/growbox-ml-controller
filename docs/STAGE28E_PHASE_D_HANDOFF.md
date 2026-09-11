# Stage28E Phase D handoff — architecture hardening and ownership cleanup

Updated: 2026-09-07
Work branch: `mvp/environment-controller`
Phase C exit SHA: `7601f0beb95d27b2bf2360b760355c3c235871a1`
Phase D implementation SHA: `09340089767cde117d12acc049790a2b93778b8e`

## Phase D result

Phase D is complete. The ownership/lifetime cleanup reduced the persistent compiler-reported stack frame of `runClimateV6RealInputRuntime()` without changing controller, AH, arbiter, RF, or safety semantics.

The work was deliberately split into two small slices:

1. D1 introduced `RuntimeIoOwner` for long-lived telemetry storage and RF diagnostics.
2. D2 introduced `RuntimeControlOwner` for long-lived control and safety state (`ClimateRuntimeController`, `LampSafetyController`, and `ThermalTestSequence`).

No PSRAM placement, stack-size reduction, allocator policy change, threshold change, RF behavior change, or AH behavior change was performed in Phase D.

## Before / after ownership evidence

Phase C baseline:

- `runClimateV6RealInputRuntime()` static frame: `5296 B`
- main task HWM in bounded runtime: about `7984-8064 B`
- `.bss`: `6672 B`

After D1 (`1aee13cb96eaebdf41a937c5622cce61f1a01b88`):

- runtime frame: `3104 B`
- reduction from Phase C: `2192 B`
- host tests: `24/24 PASS`
- firmware image: `743541 B`
- `.bss`: `9248 B`
- bounded hardware HWM: `10256 B`
- bounded hardware internal free/min/largest: `214740 / 214208 / 172032 B`
- 10 heartbeats, one successful heap-integrity check
- Shelly master ON, median `65.5 W`
- final safe state: `fake-locked`

After D2 (`09340089767cde117d12acc049790a2b93778b8e`):

- runtime frame: `2032 B`
- reduction from D1: `1072 B`
- total reduction from Phase C: `3264 B` (`~61.6%`)
- host tests: `24/24 PASS`
- firmware image: `743477 B`
- `.bss`: `10216 B`
- bounded hardware HWM: `11336 B`
- bounded hardware internal free/min/largest: `213900 / 213264 / 172032 B`
- PSRAM free/min/largest: `8363512 / 8363108 / 8257536 B`
- 11 heartbeats, one successful heap-integrity check
- Shelly master ON, median `65.5 W`
- no coredump, heap-integrity failure, arbiter counter regression, Guru Meditation, corrupt heap, or stack-canary marker
- final safe state: `fake-locked`

## Interpretation

The stack gain is visible both statically and at runtime:

- compiler frame improved `5296 -> 3104 -> 2032 B`;
- measured main-task free stack/HWM improved from about `8.0 KiB` in Phase C to `11.336 KiB` after D2.

The corresponding `.bss` growth is expected in Phase D because long-lived ownership was made explicit using static process-lifetime owners. This phase was not intended to reduce total internal DRAM usage yet. Moving proven PSRAM-eligible storage or changing FreeRTOS allocation belongs to Phase E.

The D2 internal-heap values remain healthy and flat. The slight reduction versus Phase C is explained by the explicit static ownership shift and does not indicate fragmentation or runtime leak; the largest internal free block remained `172032 B`.

## Why Phase D stops here

At `2032 B`, the non-returning runtime frame no longer contains the large ownership concentration identified by Phase C. Additional movement of smaller automatic objects would increase refactor surface while providing comparatively little architectural benefit.

The remaining high-value memory target is now clearly Phase E work, especially telemetry storage allocations that are still internal-RAM-backed under the verified ESP-IDF 5.5.4 allocator contract.

## Phase D exit assessment

Phase D exit criteria are satisfied:

- long-lived I/O and control/safety state have explicit owners;
- critical runtime state is not recreated by ordinary loop control flow;
- the largest persistent automatic objects were removed from the non-returning main frame;
- controller/arbiter behavior stayed unchanged in 24/24 host tests;
- firmware builds remained valid;
- bounded hardware runs showed stable heap, improved stack margin, valid heartbeat/integrity diagnostics, and safe output state.

Phase D therefore passes. Phase E is next.

## Phase E next

Start with measured allocation targets, not global configuration changes.

First target: telemetry storage.

Current proven costs:

- storage task stack: `7168 B` via ordinary `xTaskCreate()`;
- `Stage27TelemetrySnapshot`: `296 B`;
- queue depth: `16`;
- queue payload alone: `4736 B` via ordinary `xQueueCreate()`;
- current ESP-IDF build maps ordinary FreeRTOS allocation to internal RAM.

Phase E should first verify exact ESP-IDF caps-aware APIs and memory-capability constraints, then move only storage proven safe for external RAM. Do not enable blanket `CONFIG_SPIRAM_USE_MALLOC`, do not reduce task stacks without HWM evidence, and do not move ISR/DMA-sensitive RMT buffers blindly.

Stage28D AH physical testing remains paused until Phase H.
