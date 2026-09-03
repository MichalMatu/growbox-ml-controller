# Stage27C final evidence

Date: 2026-09-03
Repository: `MichalMatu/growbox-ml-controller`
Work branch: `mvp/environment-controller`

## Final status

Stage27C is complete for the requested CrowPanel real-input validation scope.

Frozen scope at closure:

- native ESP-IDF v5.5.4 only;
- Elecrow CrowPanel ESP32-S3 N8R8;
- SCD41 + DS3231 on shared native I2C;
- TP357 + Xiaomi/PVVX/BTHome on one native NimBLE scanner using exact MAC identities;
- TP357 is primary inside T/RH;
- SCD41 is controller CO2 plus local/window T/RH diagnostics;
- Xiaomi is nearby ambient T/RH through the neutral `outside_*` channel;
- Rule remains authoritative;
- ML remains shadow-only;
- physical outputs remain fake/locked;
- e-paper/front-panel UI remains out of scope.

The exact firmware flashed and physically validated throughout the final soak is:

`a5726b89e94b9ac628249b780d6548a692c3fd2c` — `Disable Stage27C CMD0 precondition by default`

No firmware reflash or reset was introduced during the accepted final soak sequence. Later test/documentation commits are not firmware-under-test identities and must not be presented as if they were physically soaked.

## Pre-soak qualification

The final firmware passed the strict SD-primary qualification task:

`20260903-growbox-stage27c-final-sd-primary-v1`

Terminal marker: `STAGE27C_FINAL_SD_PRIMARY_OK`.

Key terminal evidence:

- strict `--require-sd` capture: 300 s;
- records: 30;
- `last_sd_records_written=34`;
- `min_heap_internal=231780`;
- `min_stack_free=10884`;
- SD mount/write errors: 0;
- queue drops/skipped records: 0;
- resets: 0;
- serial disconnects: 0.

The storage fallback/recovery and CMD0 gates also passed before the final soak:

- `20260903-growbox-stage27c-sd-primary-smoke-v2`;
- `20260903-growbox-stage27c-flash-fallback-v3`;
- `20260903-growbox-stage27c-flash-to-sd-recovery-v1`;
- `20260903-growbox-stage27c-cmd0-native-ab-v1`.

CI for firmware SHA `a5726b89e94b9ac628249b780d6548a692c3fd2c` passed:

- `CI` run `33714883003`;
- `Stage27C Storage Gate` run `33714883009`.

## Point 5: accepted final long soak

Acceptance used seven immutable bounded 5400-second strict SD-primary windows. The accepted windows total 37,800 seconds, or 10.5 hours of active soak capture, on one continuously-running firmware/MCU uptime sequence. Task boundaries and planner wake gaps are not counted as active capture time. Uptime continuity was required between accepted chunks and no reflash/reset was performed.

| Accepted chunk | Task | First uptime ms | Last uptime ms | Records | Last SD records written |
| --- | --- | ---: | ---: | ---: | ---: |
| 01 | `20260903-growbox-stage27c-final-long-soak-chunk01-v1` | 1,507,679 | 6,900,079 | 527 | 786 |
| 02 | `20260903-growbox-stage27c-final-long-soak-chunk02-v1` | 7,156,379 | 12,548,779 | 527 | 1,428 |
| 03 | `20260903-growbox-stage27c-final-long-soak-chunk03-v1` | 13,194,629 | 18,587,029 | 527 | 2,116 |
| 04 | `20260903-growbox-stage27c-final-long-soak-chunk04-v1` | 18,689,549 | 24,071,699 | 526 | 2,740 |
| 05 | `20260903-growbox-stage27c-final-long-soak-chunk05-v2` | 41,981,429 | 47,373,829 | 527 | 5,392 |
| 06 | `20260903-growbox-stage27c-final-long-soak-chunk06-v1` | 47,568,609 | 52,961,009 | 527 | 6,027 |
| 07 | `20260903-growbox-stage27c-final-long-soak-chunk07-v1` | 53,627,369 | 59,019,769 | 527 | 6,717 |

All seven accepted tasks ended terminal `done` with exit code 0 and strict parser PASS.

Across the accepted final sequence:

- exact firmware SHA remained `a5726b89e94b9ac628249b780d6548a692c3fd2c`;
- resets: 0;
- serial disconnects: 0;
- parser errors in accepted chunks: 0;
- SD mount errors: 0;
- SD write errors: 0;
- SD queue drops: 0;
- SD skipped records: 0;
- SD unmounted records: 0;
- BLE scan errors: 0;
- BLE advertisement lock drops: 0;
- BLE-not-scanning records: 0;
- SCD41 read errors: 0;
- SCD41 invalid measurements: 0;
- RTC read errors: 0;
- RTC untrusted records: 0;
- unexpected firmware SHA records: 0;
- bad output records: 0;
- non-zero I/O status records: 0;
- counter regressions: 0.

Final chunk 07 terminal summary:

- `first_uptime_ms=53627369`;
- `last_uptime_ms=59019769`;
- `records=527`;
- `last_sd_records_written=6717`;
- `max_scd_age_ms=4050`;
- `max_tp_age_ms=4300`;
- `max_xiaomi_age_ms=7958`;
- `min_heap_internal=231588`;
- `min_heap_internal_largest=188416`;
- `min_heap_psram=8368044`;
- `min_heap_psram_largest=8257536`;
- `min_stack_free=10708`;
- `violations=[]`.

The memory minima were stable across the later accepted chunks and did not show a progressive leak trend.

### Rejected chunk 05 attempt

`20260903-growbox-stage27c-final-long-soak-chunk05-v1` is not accepted soak evidence because its strict parser reported one malformed captured NDJSON line.

Follow-up diagnostics isolated one corrupted UART/CH340 capture line surrounded by valid lines. The firmware emits the complete soak record in one `ESP_LOGI(...)`, and the malformed capture contained glued/dropped field bytes. The strict parser was not weakened. The chunk was rerun unchanged as immutable `...chunk05-v2`, which passed with zero parse errors and preserved MCU uptime continuity.

## Point 6: safe software-observable fault/freshness validation

The point-6 audit first inspected existing host coverage instead of duplicating tests.

Existing coverage already proves:

- wrong BLE MAC is ignored and cannot alter the target TP357 counters/freshness;
- malformed exact TP357 packets increment rejected diagnostics without refreshing last valid measurement time;
- encrypted/unsupported exact Xiaomi/BTHome frames are rejected without refreshing last valid measurement time;
- BTHome encrypted and malformed payload decode semantics;
- DS3231 OSF/lost-power semantics make decoded time untrusted/invalid;
- clock availability and valid/trusted context are treated separately by the composite input path.

One missing end-to-end host assertion was added in test-only code: `test/test_stage27_fault_freshness/test_main.cpp`. It proves that malformed exact TP357 traffic can update packet-seen diagnostics but cannot keep an old valid measurement fresh; once the valid sample exceeds the 30-second freshness timeout, the Rule controller produces all-off output.

Point-6 test registration HEAD before final documentation was:

`2d2af78cd62c83b9438b45964cf4b1565abe2868` — `Register Stage27C point 6 host tests`

Terminal validation task:

`20260903-growbox-stage27c-point6-host-validation-v2`

passed with:

- full portable host suite: `17/17` tests passed;
- targeted Stage27C subset: `3/3` tests passed, including `ble_climate_state_tests`, `stage27_native_inputs_tests`, and `stage27_fault_freshness_tests`.

The preceding `...host-validation-v1` ended only because the Local Agent software-only 1024 MB task limit was exceeded during highly parallel compilation (`command_memory_limit`, peak RSS about 1483.75 MB). The same source was rerun with machine exclusivity and a 4096 MB task limit; v2 passed. This was an executor resource-limit event, not a product/test failure.

SCD41 hardware-facing read-error/data-ready paths do not have a portable host seam. Source inspection confirms that ready/read failures increment `read_error_count_` and return the cached measurement without updating `last_measurement_ms_`; invalid readings increment `invalid_measurement_count_` and likewise do not refresh the cached timestamp. The final physical soak simultaneously showed zero SCD41 read/invalid errors and bounded SCD41 age. No production refactor was introduced merely to manufacture an artificial host seam after the final firmware soak.

## Point 7: closure decision

Stage27C points 1-7 are closed for the requested scope.

The final acceptance combines:

1. physical CrowPanel/I2C/BLE bring-up and exact sensor identity routing;
2. storage primary/fallback/recovery/CMD0 qualification;
3. final strict SD-primary gate on firmware `a5726b89e94b9ac628249b780d6548a692c3fd2c`;
4. seven accepted 90-minute strict soak windows totaling 10.5 hours of active capture with MCU uptime continuity and zero resets;
5. safe software-observable fault/freshness host validation;
6. explicit separation of firmware-under-test identity from later test/documentation HEADs.

No e-paper/front-panel validation and no physical actuator/relay validation are claimed. Those remain outside Stage27C and require a new explicit goal.

Do not reopen Stage27C solely because the repository documentation HEAD advances after this file. Reopen only if firmware/runtime behavior changes in a way that invalidates this evidence or if a new explicit hardware goal expands the scope.

## Frozen milestone

The tested and reviewed Stage27C closure is frozen by the annotated Git tag `stage27c-validated-2026-09-03`. The tag identifies the repository closure state; the exact physically soaked firmware remains `a5726b89e94b9ac628249b780d6548a692c3fd2c`.
