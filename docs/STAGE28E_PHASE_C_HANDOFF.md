# Stage28E Phase C handoff — memory map, stack audit, and resource baseline

Updated: 2026-09-06
Work branch: `mvp/environment-controller`
Phase B exit SHA: `e0fb5da17879569f791898ba793e1c02b195fab8`
Phase C measurement source SHA: `e0fb5da17879569f791898ba793e1c02b195fab8`

## Phase C result

Phase C is complete from the measurement/resource-baseline perspective. No broad memory optimization or ownership refactor was performed in this phase.

The previously suspected approximately 1 KiB internal-RAM condition was **not reproduced**. The bounded representative runtime remained near 217 KiB current free internal RAM with a minimum near 216.8 KiB and a 176 KiB largest free block while BLE, sensors, telemetry, storage, service-console status sampling, heartbeat, and periodic heap-integrity checks were active.

The evidence instead identifies two concrete architectural/resource costs that Phase D/E can address from measurement rather than guesswork:

1. `runClimateV6RealInputRuntime()` is `[[noreturn]]` and owns a 5296-byte compiler-reported static stack frame containing long-lived runtime objects for the entire process lifetime.
2. the telemetry storage path uses ordinary FreeRTOS dynamic allocation, which this exact ESP-IDF build maps to internal RAM; its task stack is 7168 bytes and its 16-entry telemetry queue contains 4736 bytes of payload before queue metadata/allocator overhead.

Stage28D functional AH work remains paused. Phase D is next and must harden ownership/lifetime without changing controller semantics.

## C1 — static/linker memory baseline

Exact safe/default firmware build at the Phase C source SHA:

- total image: `743369 B`
- Flash Code / `.text`: `479570 B`
- Flash Data: `129284 B`
- `.rodata`: `129028 B`
- DIRAM used: `124771 B / 341760 B` (`36.51%`)
- DIRAM remaining: `216989 B`
- DIRAM `.text`: `97587 B`
- DIRAM `.data`: `20512 B`
- DIRAM `.bss`: `6672 B`
- IRAM: `16384 B / 16384 B`
- IRAM `.text`: `15356 B`
- vectors: `1028 B`
- RTC slow used: `144 B`, including Stage28E RTC no-init breadcrumb storage

ELF section rows confirmed:

- `.dram0.data` = `0x5020` = `20512 B`
- `.dram0.bss` = `0x1a10` = `6672 B`
- `.iram0.text` = `0x1b92f`
- `.flash.text` = `0x75152`
- `.flash.rodata` = `0x1f804`
- `.rtc_noinit` = `0x70` = `112 B`

There is no evidence of a large application-owned hidden `.bss` consumer. The largest static symbols are mainly ESP-IDF/FreeRTOS/BLE platform data. Notable entries include:

- FreeRTOS interrupt stack `port_IntStack`: `4192 B`
- Stage28E coredump stack `s_coredump_stack`: `1892 B`
- FreeRTOS ready lists: `500 B`
- Stage28E RTC breadcrumb: `112 B`

The coredump stack is a deliberate Phase B diagnostic cost and should not be removed blindly.

## C2 — long-lived runtime object inventory

`runClimateV6RealInputRuntime()` is `[[noreturn]]`. Objects declared as local automatic variables before its infinite loop therefore remain resident on the `app_main` task stack for the life of the firmware.

Compiler/toolchain `sizeof` measurements for important objects:

| Object/type | Size | Current owner/storage | Lifetime / note |
| --- | ---: | --- | --- |
| `Stage28RfDiagnostics` | `1288 B` | automatic in non-returning runtime | process lifetime; contains RF loopback buffers even when loopback is disabled |
| `ClimateRuntimeController` | `872 B` | automatic in non-returning runtime | process lifetime |
| `Stage27TelemetryLogger` | `848 B` | automatic in non-returning runtime | process lifetime; also owns dynamic queue/task handles |
| `Stage28ServiceConsole` | `208 B` | automatic in non-returning runtime | process lifetime |
| `RuntimeTimingMetrics` | `200 B` | automatic in non-returning runtime | process lifetime |
| `BleClimateScanner` | `136 B` | automatic in non-returning runtime | process lifetime; NimBLE/library state is separate |
| `Stage28dBinaryRoleArbiter` | `136 B` | automatic in non-returning runtime | process lifetime; Phase B lifecycle identity protects reconstruction diagnosis |
| `Stage28dRfOutputEndpoint` | `80 B` | automatic in non-returning runtime | process lifetime |
| `ClimateApplication` | `56 B` | automatic in non-returning runtime | references controller/input/output owners |
| `Ds3231ClockSource` | `56 B` | automatic in non-returning runtime | process lifetime |
| `LampSafetyController` | `48 B` | automatic in non-returning runtime | process lifetime |
| `Scd41InsideSource` | `48 B` | automatic in non-returning runtime | process lifetime |
| `ThermalTestSequence` | `40 B` | automatic in non-returning runtime | process lifetime |
| `MappedClimateRoleDriver` | `36 B` | automatic in non-returning runtime | process lifetime |
| `Stage27TelemetryReporter` | `36 B` | automatic in non-returning runtime | process lifetime |

The largest individual automatic object is `Stage28RfDiagnostics`. It contains `Rf433RmtLoopback`, which owns fixed TX/RX symbol arrays as object members, so its `1288 B` cost exists even when `GROWBOX_RF433_LOOPBACK_ENABLED=0`.

## C3 — compiler stack audit

Using the exact target compiler flags plus `-fstack-usage`:

- `runClimateV6RealInputRuntime()` static frame: **`5296 B`**
- `Stage28ServiceConsole::handleRfReceive(...)`: `1648 B`
- `Stage28ServiceConsole::handleSdLogRead(...)`: `1184 B`
- `Stage27TelemetryLogger::persistSnapshot(...)`: `1120 B`
- `Stage27TelemetryReporter::logRecord(...)`: `880 B`
- `Stage28ServiceConsole` additional large handler observed: `720 B`
- `Stage27TelemetryLogger::ensureActiveSession(...)`: `592 B`
- `Stage27TelemetryReporter::record(...)`: `592 B`
- `Stage27TelemetryLogger::taskLoop()`: `336 B`
- `Stage28ServiceConsole::printStatus(...)`: `208 B`

Runtime hardware evidence in Phase B/C showed `app_main` HWM around `8064 B`, later `7984 B`, from a configured `16384 B` stack. This remains safe but confirms that the 5296-byte persistent owner frame consumes a material fraction of the main task stack before transient call depth is considered.

`stage27_store` uses a configured `7168 B` stack. Phase A measured approximately `2908 B` HWM, about 40.6% remaining. Its largest audited local frame is `persistSnapshot()` at `1120 B`.

## C4 — allocation-path audit

Application-level explicit dynamic allocation is limited and generally intentional:

- service-console task snapshots use `heap_caps_malloc(..., MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT)` and are freed after use;
- serial JSON line storage prefers explicit PSRAM and has an internal fallback;
- telemetry storage creates a FreeRTOS queue via `xQueueCreate()` and a task via ordinary `xTaskCreate()`.

Exact ESP-IDF 5.5.4 allocation contract for the current build:

- `pvPortMalloc()` uses `heap_caps_malloc(size, MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT)`;
- `CONFIG_SPIRAM_USE_CAPS_ALLOC=y`;
- `CONFIG_SPIRAM_USE_MALLOC` is **not set**;
- `CONFIG_SPIRAM_TRY_ALLOCATE_WIFI_LWIP=y`;
- `CONFIG_FREERTOS_TASK_CREATE_ALLOW_EXT_MEM=y`.

Therefore ordinary FreeRTOS dynamic objects do **not** automatically move to PSRAM in this build. External-memory-capable FreeRTOS APIs exist, but they must be selected explicitly and only after Phase D clarifies ownership and Phase E proves the move is safe.

Telemetry allocation details:

- `sizeof(Stage27TelemetrySnapshot) = 296 B`
- queue depth = `16`
- queue payload alone = **`4736 B`**, plus queue control/allocator overhead
- storage task stack = **`7168 B`** plus task control allocation

Both ordinary `xQueueCreate()` storage and ordinary `xTaskCreate()` allocations consume internal RAM under the verified IDF contract above.

## C5 — bounded representative runtime baseline

Final task:

`20260906-growbox-stage28e-phase-c-runtime-baseline-v1`

Exact firmware/source SHA:

`e0fb5da17879569f791898ba793e1c02b195fab8`

Safety configuration:

- `GROWBOX_STAGE28_REAL_OUTPUTS_ENABLED=0`
- `GROWBOX_STAGE28_THERMAL_TEST_SEQUENCE_ENABLED=0`
- `GROWBOX_RF433_LOOPBACK_ENABLED=0`
- `GROWBOX_STAGE28E_BREADCRUMB_RESTART_SELFTEST=0`
- only `/dev/cu.usbserial-1130`
- no RF transmit or real-output transition

Representative status samples:

| Uptime | Internal free | Internal minimum | Largest internal block | PSRAM free | PSRAM minimum | Largest PSRAM block | main HWM |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| ~38 s | `217444 B` | `216808 B` | `176128 B` | `8363512 B` | `8363108 B` | `8257536 B` | `8064 B` |
| ~74 s | `217444 B` | `216808 B` | `176128 B` | `8363512 B` | `8363108 B` | `8257536 B` | `8064 B` |
| ~118 s | `217444 B` | `216808 B` | `176128 B` | `8363512 B` | `8363108 B` | `8257536 B` | `7984 B` |

Additional evidence:

- 14 runtime heartbeats
- two successful periodic heap-integrity checks
- no heap-integrity failure
- no arbiter counter regression
- no Guru Meditation / corrupt heap / stack-canary marker
- BLE/sensors/telemetry/storage remained active
- Shelly master ON for all five read-only samples
- Shelly median active power: `65.8 W`
- final task marker: `STAGE28E_C_SAFE_FAKE_LOCKED_PASS`

The internal minimum remained only `636 B` below the steady current-free value in these samples, and the largest free block remained `176128 B`. There is no evidence here of severe fragmentation or a transient collapse toward 1 KiB.

## Interpretation of the historical ~1 KiB observation

Phase A-C evidence does not reproduce an approximately 1 KiB current-free or minimum-free internal heap state.

The present evidence supports these possibilities more strongly than a current product-wide DRAM exhaustion problem:

- the old observation came from a materially different build/configuration;
- it was a different metric or unit;
- it represented a short historical/transient state not present now;
- it came from another runtime path/configuration.

Phase G still must provide longer-duration stability evidence. Do not claim long-term absence of fragmentation from the two-minute Phase C baseline alone.

## Ranked Phase D/E targets from evidence

1. **Ownership/lifetime of the 5296-byte non-returning runtime frame.** Phase D should introduce explicit runtime ownership so large long-lived objects are not implicitly tied to one giant automatic frame.
2. **`Stage28RfDiagnostics` 1288-byte always-resident object.** Its fixed RF buffers exist even when RF loopback diagnostics are disabled; Phase D should clarify optional ownership/lifetime before Phase E decides placement or lazy construction.
3. **Telemetry storage task + queue internal-RAM cost.** At least 7168 B stack + 4736 B queue payload are explicitly internal under the current IDF contract. Phase D should isolate ownership; Phase E may evaluate external-memory-capable allocation only if hardware/library constraints permit it.
4. **Large service-console transient frames.** RF receive and SD read handlers use 1648 B and 1184 B frames. They are not continuously resident beyond call depth, but should be considered when sizing main stack after ownership cleanup.
5. **Storage serialization frame.** `persistSnapshot()` uses 1120 B on `stage27_store`; use real HWM before reducing that task stack.

Do not start by reducing stack sizes or globally enabling `CONFIG_SPIRAM_USE_MALLOC`.

## Phase C exit assessment

Phase C can now answer the required questions:

- static DRAM consumers are quantified; `.data` is 20512 B and `.bss` is 6672 B with no hidden application-sized global block;
- long-lived stack ownership is quantified; the non-returning main runtime frame is 5296 B;
- the largest long-lived automatic objects are identified and measured;
- ordinary FreeRTOS allocation is proven internal-RAM-backed in this exact build;
- the telemetry queue/task internal costs are quantified;
- important transient stack frames are measured;
- representative current/minimum/largest-block runtime memory is stable and far from 1 KiB;
- the lowest known task margins remain observable from Phase A-C HWM measurements.

Phase C therefore passes its measurement/baseline criteria. Phase D is next.

## Phase D next

Refactor one coherent ownership boundary at a time. Preserve all control and safety semantics.

Recommended first slice:

1. introduce an explicit long-lived runtime owner for the current `runClimateV6RealInputRuntime()` object graph;
2. keep the arbiter a single owned instance with Phase B identity/continuity diagnostics intact;
3. move construction/lifetime out of the giant non-returning automatic frame without yet changing allocator placement;
4. verify host behavior, firmware size, compiler stack frame and bounded fake-locked runtime before additional architecture slices.

Do not combine this with PSRAM relocation or AH behavior changes. Those belong to later evidence-backed slices/Phase E.
