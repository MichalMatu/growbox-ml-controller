# Current controller status

Updated: 2026-09-06
Development branch: `mvp/environment-controller`
Latest handoff: `docs/STAGE28E_PHASE_C_HANDOFF.md`
Stage28E execution guide: `docs/GUIDANCE.md`
Prior Stage28D evidence: `docs/STAGE28D_AH_ARBITER_HANDOFF.md`
Primary roadmap: `docs/PROJECT_ROADMAP.md`
Continuation checklist: `docs/CONTINUATION_PLAN.md`

## Current transition

**Stage27C FROZEN -> Stage28A/B/C DONE -> Gates 1-6 COMPLETE -> Gate 7 previously qualified -> AH policy software COMPLETE -> Gate 7 runtime path REOPENED by V5 evidence -> Stage28E Phase A COMPLETE -> Phase B COMPLETE -> Phase C COMPLETE pending final docs-only exit gate -> Phase D next**

Stage28D functional AH work remains paused. The active program remains Stage28E A -> H. Phase A established observability, Phase B added crash/reset/corruption/lifecycle evidence, and Phase C produced a quantitative memory/stack/allocation baseline. Phase D now hardens ownership/lifetime without changing control semantics.

## Phase identities

Phase A exit SHA:

`384e415eaaec960add2b3b3fe94db5c052ca6497`

Phase B exit SHA:

`e0fb5da17879569f791898ba793e1c02b195fab8`

Phase C measurement source SHA:

`e0fb5da17879569f791898ba793e1c02b195fab8`

Phase C handoff creation commit:

`3215d5d1e3e85e6f9e6fa9e04f238e48c9a621ba`

Always fetch fresh work-branch HEAD and Local Agent daemon state before editing or queueing work.

## Phase C quantitative baseline

Exact default/safe firmware image:

`743369 B`

Static/linker memory:

- Flash Code `.text`: `479570 B`
- Flash Data: `129284 B`
- `.rodata`: `129028 B`
- DIRAM used: `124771 B / 341760 B` (`36.51%`)
- DIRAM remaining: `216989 B`
- DIRAM `.data`: `20512 B`
- DIRAM `.bss`: `6672 B`
- IRAM: `16384 B / 16384 B`
- RTC no-init breadcrumb: `112 B`
- deliberate coredump stack: `1892 B`

There is no evidence of a large hidden application `.bss` consumer.

## Long-lived main-task stack ownership

`runClimateV6RealInputRuntime()` is `[[noreturn]]` and its compiler-reported static frame is:

**`5296 B`**

Important automatic objects retained in that frame for the process lifetime:

- `Stage28RfDiagnostics`: `1288 B`
- `ClimateRuntimeController`: `872 B`
- `Stage27TelemetryLogger`: `848 B`
- `Stage28ServiceConsole`: `208 B`
- `RuntimeTimingMetrics`: `200 B`
- `BleClimateScanner`: `136 B`
- `Stage28dBinaryRoleArbiter`: `136 B`

`Stage28RfDiagnostics` contains fixed RF loopback symbol arrays, so its `1288 B` object cost exists even when RF loopback diagnostics are disabled.

Measured `app_main` HWM was about `8064 B` in Phase B and reached `7984 B` in the Phase C bounded baseline from a configured `16384 B` stack. The stack is not currently critical, but the ownership pattern is quantitatively expensive and is the first Phase D target.

Important transient frames:

- service-console RF receive: `1648 B`
- service-console SD log read: `1184 B`
- telemetry storage `persistSnapshot()`: `1120 B`
- telemetry reporter log formatting: `880 B`
- telemetry reporter record: `592 B`

## FreeRTOS/internal-RAM allocation contract

For this exact ESP-IDF 5.5.4 build:

- ordinary `pvPortMalloc()` uses `MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT`;
- `CONFIG_SPIRAM_USE_CAPS_ALLOC=y`;
- `CONFIG_SPIRAM_USE_MALLOC` is not set;
- `CONFIG_FREERTOS_TASK_CREATE_ALLOW_EXT_MEM=y`.

Therefore ordinary `xTaskCreate()` and `xQueueCreate()` consume internal RAM unless an explicit caps-aware API/path is chosen.

Telemetry storage currently has at least these internal-RAM costs:

- `stage27_store` task stack: `7168 B` plus task control allocation;
- `Stage27TelemetrySnapshot`: `296 B`;
- queue depth: `16`;
- queue payload: **`4736 B`** plus queue metadata/allocator overhead.

Do not globally enable PSRAM malloc or move these blindly. Ownership first belongs to Phase D; measured placement optimization belongs to Phase E.

## Phase C bounded hardware baseline

Task:

`20260906-growbox-stage28e-phase-c-runtime-baseline-v1`

Exact firmware/source SHA:

`e0fb5da17879569f791898ba793e1c02b195fab8`

Safe configuration had real outputs, thermal test, RF loopback and breadcrumb restart self-test all disabled.

Representative runtime metrics through about 118 seconds:

- internal free: `217444 B`
- internal minimum: `216808 B`
- largest internal block: `176128 B`
- PSRAM free: `8363512 B`
- PSRAM minimum: `8363108 B`
- largest PSRAM block: `8257536 B`
- main HWM: `8064 B`, later `7984 B`
- heartbeat count: `14`
- heap-integrity successes: `2`
- no heap-integrity failure/counter regression/crash/canary marker
- Shelly master ON for all read-only samples
- Shelly median power: `65.8 W`
- final state: `fake-locked`

The internal minimum was only `636 B` below the steady current-free value and the largest block remained `176128 B`. The old approximately 1 KiB internal-memory observation was not reproduced in Phase A-C and is not accepted as the current product state.

Long-duration fragmentation/stability proof remains Phase G work.

## V5 issue remains open but instrumented

The prior Stage28D V5 anomaly remains cumulative `arbiter_dwell_holds` decreasing:

`33 -> 43 -> 1 -> 11`

Phase B/C did not reproduce a same-instance regression. The firmware can now distinguish boot/reset, same-boot reconstruction, same-instance regression/corruption, coredump state, heap-integrity failure and liveness loss.

Do not change `Stage28dBinaryRoleArbiter::applyBinary()` based only on the old V5 trace. A-G must pass before the final physical path in Phase H.

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
- manual RF remains blocked during `real-bounded`;
- Shelly master stays ON;
- no unattended real-output mode;
- after bounded diagnostics restore/prove fake-locked safe state.

## Immediate next work

1. Run one docs-only exact-SHA Phase C exit gate on fresh HEAD.
2. Record the passing SHA as formal Phase C exit SHA.
3. Start **Stage28E Phase D — architecture hardening and ownership cleanup**.
4. First Phase D slice: introduce an explicit long-lived runtime owner for the existing object graph so the giant non-returning automatic frame no longer implicitly owns all runtime state.
5. Preserve a single binary-arbiter instance and all Phase B lifecycle/continuity diagnostics.
6. Do not combine the ownership refactor with PSRAM relocation, stack reductions, allocator-threshold changes or AH behavior changes.
7. After each coherent slice run focused host tests, firmware build/size and compiler stack-frame comparison; use bounded fake-locked hardware only when needed to validate lifetime behavior.

Do not run the long soak before Phase G and do not return to a real AH actuator transition before Phase H.
