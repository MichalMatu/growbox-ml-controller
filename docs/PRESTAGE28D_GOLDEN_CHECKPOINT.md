# Pre-Stage28D golden checkpoint

Date: 2026-09-04
Status: COMPLETE
Stage28D: NOT STARTED
Golden firmware/source checkpoint: `316b58e76de609069ddbf2667fe86f6218fb2143`

## Software gate

Task `20260904-growbox-prestage-format-gate-v2` passed on the exact checkpoint SHA. The gate included pre-commit, Python regressions, host C++/CTest, clang-tidy, ESP-IDF quality-gate build, exact CrowPanel build, zero unknown Kconfig-symbol warnings and a clean worktree.

Terminal marker:

`PRESTAGE_FORMAT_GATE_READY commit=316b58e76de609069ddbf2667fe86f6218fb2143 parent=484a7dfa262165fc3e61716cc162a49d61a2ee8a precommit=pass quality_gate=pass crowpanel_build=pass unknown_kconfig_warnings=0 cmake_parallel=2`

## Hardware soak

Task `20260904-growbox-prestage-golden-hardware-soak-v1` built and flashed the exact checkpoint SHA and ran a strict 5400-second real-hardware soak with SCD41, DS3231 RTC, both BLE climate inputs and SD telemetry active.

Observed evidence:

- 526 records;
- zero resets, serial disconnects, parse errors, unexpected-SHA records and strict violations;
- max SCD41 age 4050 ms, TP357 age 3052 ms, Xiaomi age 11962 ms;
- zero BLE scan errors, BLE lock drops, RTC read errors, RTC untrusted records, SCD41 read errors and SCD41 invalid records;
- minimum internal heap 226200 B and largest internal block 184320 B;
- minimum PSRAM free 8368044 B and largest PSRAM block 8257536 B;
- minimum free stack 9292 B;
- SD telemetry advanced by 612 records with zero mount/write/queue/skip errors;
- outputs remained `fake-locked`;
- RF automatic transmit was disabled and no RF433 TX lifecycle was observed in the raw soak logs.

Terminal markers:

`PRESTAGE_GOLDEN_SOAK_SUMMARY records=526 uptime_first=10939 uptime_last=5393079 heap_internal_first=226328 heap_internal_last=226200 heap_psram_first=8368044 heap_psram_last=8368044 min_stack_free=9292 sd_delta=612`

`PRESTAGE_GOLDEN_HARDWARE_SOAK_PASS sha=316b58e76de609069ddbf2667fe86f6218fb2143 duration_s=5400 outputs=fake-locked rf_auto_tx=0`

## Boundary

The historical Stage28C known-pair physical recheck remains tied to `2cb4b8dffb0835460a9e9ba920d9bd888c99d992`. The exact post-hardening firmware qualified by this golden gate is `316b58e76de609069ddbf2667fe86f6218fb2143`.

A later documentation-only commit may advance repository HEAD without becoming a separately hardware-soaked firmware SHA. Stage28D is intentionally not started by this checkpoint.
