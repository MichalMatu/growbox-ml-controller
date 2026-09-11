# Stage27C CrowPanel physical bring-up

Date: 2026-08-31
Updated: 2026-09-03
Work branch: `mvp/environment-controller`

This document freezes the physical Stage27C configuration for the user's actual Elecrow CrowPanel ESP32-S3 2.9-inch HAT setup. E-paper and front-panel UI remain intentionally deferred. Physical actuator outputs remain fake/locked.

> **Final status:** Stage27C points 1-7 are closed for the requested scope. The exact final firmware-under-test, seven accepted long-soak chunks, point-6 host validation and closure decision are frozen in `docs/STAGE27C_FINAL_EVIDENCE.md`. `docs/STAGE27C_PRE_SOAK_HANDOFF.md` and `docs/STAGE27C_CONTINUATION_HANDOFF.md` are historical handoffs and must not be used to resume the completed soak.

## Board and bus

- board: Elecrow CrowPanel ESP32-S3 2.9-inch e-paper HMI;
- module class: N8R8, 8 MB flash + 8 MB octal PSRAM;
- shared primary I2C: SDA GPIO21, SCL GPIO38;
- SCD41 address: `0x62`;
- DS3231 address: `0x68`;
- SD SPI: MOSI GPIO40, MISO GPIO13, SCLK GPIO39, CS GPIO10, power GPIO42;
- current verified CH340 serial path: `/dev/cu.usbserial-1130` (rediscover before future use; the path is not guaranteed stable);
- e-paper: not initialized by Stage27C climate bring-up;
- physical growbox outputs: not enabled.

The Stage27C build uses `config/idf/sdkconfig.defaults.n8r8` plus the existing Stage27 native BLE overlay and stores its generated sdkconfig inside the dedicated build directory so stale root sdkconfig state cannot override the requested configuration.

## Physical sensors

| Sensor | Identity/location | Stage27C role |
| --- | --- | --- |
| TP357 | BLE MAC `F7:5F:8D:0F:76:20`, physically inside growbox | primary inside temperature/RH source |
| Xiaomi LYWSD03MMC + PVVX/BTHome | BLE MAC `A4:C1:38:4F:24:CD`, physically on/near growbox | nearby ambient temperature/RH source exposed through the existing outside/ambient fields |
| SCD41 | I2C, physically near window | CO2 source for the controller plus local window-area temperature/RH diagnostics |
| DS3231 | I2C on HAT | trusted wall-clock source |

Do not calculate calibration offsets between these sensors because they are intentionally placed in different physical locations.

## Bring-up command

```bash
bash scripts/stage27c_crowpanel.sh build
bash scripts/stage27c_crowpanel.sh flash
bash scripts/stage27c_crowpanel.sh monitor
```

`PORT=/dev/cu...` may be supplied when automatic serial-port detection is ambiguous.

The Stage27C helper configures both exact BLE identities:
`GROWBOX_BLE_TP357_MAC=F7:5F:8D:0F:76:20` and
`GROWBOX_BLE_XIAOMI_MAC=A4:C1:38:4F:24:CD`.
One shared native NimBLE scanner routes advertisements by exact MAC; there is no strongest-RSSI sensor selection.

The helper now defaults `GROWBOX_SD_CMD0_PRECONDITION=0`. The native no-shim path passed the physical A/B gate. The compatibility precondition remains available as an explicit override if future hardware evidence requires it.

## Completed physical input gates

Points 1-4 were originally closed on source HEAD `a1a05a91a6928f672a8f4f43963f979fefa7d79d` (`Wire Stage27C dual BLE runtime`).

1. CrowPanel N8R8 build uses GPIO21/GPIO38 for the shared I2C bus, 8 MB flash, 8 MB octal PSRAM, no e-paper initialization and fake/locked physical outputs.
2. Physical I2C bring-up established SCD41 at `0x62` and DS3231 at `0x68`. SCD41 MCU-only-reset recovery stops an inherited periodic session before starting a fresh one. Runtime evidence shows `scd41_available=1`, `scd41_sample=1`, `rtc_available=1` and `rtc_trusted=1`.
3. TP357 manufacturer data was validated from the real exact-MAC device. The native decoder/router tracks packet-seen separately from valid-measurement freshness, and the shared scanner concurrently tracks TP357 and Xiaomi by exact MAC.
4. Hardware gate `20260831-growbox-stage27c-dual-ble-hardware-gate-v2` passed a 90-second live capture. The final simultaneous line reported TP357 `23.90 C / 74.00 %RH` with `packet_ms=1154994`, `valid_ms=1154994`, and Xiaomi `25.06 C / 55.07 %RH` with `packet_ms=1155251`, `valid_ms=1154244`. The same line reported `scd41_sample=1`, `rtc_available=1`, `rtc_trusted=1`, `ble_scanning=1` and `outputs=fake-locked`; no panic or watchdog evidence was present.

These values are evidence of independent sensor operation only. Do not calculate or apply cross-sensor temperature/RH offsets because the sensors are physically located in different places.

## Completed Stage27C pre-soak storage qualification

Final firmware-under-test SHA:

`a5726b89e94b9ac628249b780d6548a692c3fd2c` — `Disable Stage27C CMD0 precondition by default`

The following bounded physical gates are complete:

1. SD-primary smoke: `20260903-growbox-stage27c-sd-primary-smoke-v2` passed on firmware `0cbd181f46661423d1983ad1805f11d6fecc5128`.
2. Flash fallback with the SD card physically absent: `20260903-growbox-stage27c-flash-fallback-v3` passed. The expected cold-start sequence is one initial diagnostic row with `storage_backend=none`, followed by stable `storage_backend=flash`; fallback activation was `1`, write/drop/skip errors were zero, and records advanced.
3. Live flash-to-SD recovery after hot insertion without reset: `20260903-growbox-stage27c-flash-to-sd-recovery-v1` passed with `sd_recoveries=1`, retained `fallbacks=1`, stable SD after recovery, records `24 -> 43`, no reset/disconnect, and zero storage write/drop/skip errors.
4. CMD0 A/B: `20260903-growbox-stage27c-cmd0-native-ab-v1` built/flashed with `GROWBOX_SD_CMD0_PRECONDITION=0` and passed strict SD-required hardware validation. Therefore the helper default was changed from `1` to `0`.
5. Final default-config SD-primary gate: `20260903-growbox-stage27c-final-sd-primary-v1` built/flashed exact firmware `a5726b89e94b9ac628249b780d6548a692c3fd2c` and passed a 300-second strict `--require-sd` soak. Terminal marker: `STAGE27C_FINAL_SD_PRIMARY_OK` with `records=30`, `last_sd_records_written=34`, `min_heap_internal=231780`, and `min_stack_free=10884`. SD mount/write errors, queue drops, skipped records, resets and serial disconnects were all zero.

CI for final firmware SHA `a5726b89e94b9ac628249b780d6548a692c3fd2c` also passed:

- GitHub Actions `CI`, run `33714883003`: success;
- GitHub Actions `Stage27C Storage Gate`, run `33714883009`: success.

The device remains Rule-authoritative, ML shadow-only, and outputs fake/locked. No e-paper work was added.

## Completed final long soak and fault/freshness closure

The final firmware completed seven accepted strict 5400-second SD-primary soak chunks, totaling 37,800 seconds (10.5 hours) of active capture on one preserved MCU uptime sequence. All accepted chunks had zero resets, zero serial disconnects, zero parser errors, zero SD mount/write/drop/skip failures, zero SCD41 read/invalid errors, clean BLE scanning/freshness diagnostics, trusted RTC, fake/locked outputs and the exact firmware SHA throughout.

The final accepted chunk ended at `last_uptime_ms=59019769` with `last_sd_records_written=6717`, `min_heap_internal=231588`, `min_heap_psram=8368044`, and `min_stack_free=10708`.

Point 6 then audited existing fault/freshness tests and added only the missing end-to-end stale-valid-sample assertion. `20260903-growbox-stage27c-point6-host-validation-v2` passed the complete portable host suite `17/17` and the targeted Stage27C subset `3/3`.

Full task IDs, per-chunk uptime/SD counters, the rejected chunk-05 capture attempt, memory trend, point-6 test evidence and the exact closure boundary are recorded in `docs/STAGE27C_FINAL_EVIDENCE.md`.

## Closure boundary

Stage27C is complete. Do not resume or extend its soak loop.

Future work must open a new explicit goal if it changes any of the following boundaries:

- e-paper/front-panel UI;
- physical actuators/relays;
- Rule-authoritative / ML-shadow-only policy;
- sensor identities or physical role mapping;
- final firmware/runtime behavior in a way that invalidates the frozen evidence.

Documentation/test-only HEAD changes after closure do not change the physically soaked firmware identity `a5726b89e94b9ac628249b780d6548a692c3fd2c`.
