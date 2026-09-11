# Stage28E Phase B handoff — crash/reset/corruption/lifecycle diagnostics

Updated: 2026-09-06
Work branch: `mvp/environment-controller`
Phase A exit SHA: `384e415eaaec960add2b3b3fe94db5c052ca6497`
Phase B hardware-validated source SHA: `b43516a2adcd320b3da2b4ee9051e442cceb5c93`

## Phase B result

Phase B is complete from the implementation and bounded-runtime perspective. The firmware now leaves enough evidence to distinguish normal/power-on boot, software reset, coredump presence/absence, arbiter/runtime reconstruction, counter regression, heap-integrity failure and loss of runtime heartbeat.

Stage28D AH functional development remains paused. The next stage is Stage28E Phase C: quantitative memory map, stack audit, runtime-object inventory and allocation-path analysis.

## Safety boundary used for all Phase B hardware work

All Phase B device validation used only:

- `board:growbox-s3`
- serial `/dev/cu.usbserial-1130`
- `GROWBOX_STAGE28_REAL_OUTPUTS_ENABLED=0`
- `GROWBOX_STAGE28_THERMAL_TEST_SEQUENCE_ENABLED=0`
- `GROWBOX_RF433_LOOPBACK_ENABLED=0`

`/dev/cu.usbserial-10` was not used.

After the restart diagnostic, the normal firmware was re-flashed with the restart self-test disabled and the final state was proven `fake-locked`. Shelly master remained ON.

## B1 — flash coredump support

The installed SDK contract was verified against ESP-IDF 5.5.4 before editing configuration.

Verified original flash layout:

```csv
# Name, Type, SubType, Offset, Size
nvs,       data, nvs,     0x9000,  0x6000
phy_init,  data, phy,     0xf000,  0x1000
factory,   app, factory,  0x10000, 0x400000
telemetry, data, fat,     0x410000,0x200000
```

The board has 8 MiB flash. The old high end was `0x610000`, leaving `0x1F0000` bytes / 1984 KiB before the end of flash.

Chosen coredump layout/configuration:

- 1 MiB coredump partition at `0x610000..0x710000`
- 960 KiB tail remains free
- flash coredump enabled
- ELF format
- CRC32 checksum
- DRAM capture enabled
- boot-time check enabled
- coredump logs disabled to save internal memory
- no-overwrite enabled
- maximum captured tasks: 16
- dedicated coredump stack: 1792 B

Commits:

- `9e5ae78f4f4dc56426ecfefd5724c9861d810465` — reserve flash for Stage28E core dumps
- `5f7cdab9811fe8df686565516ce326fbb23041ba` — enable Stage28E flash core dumps
- `2cf2a19bb9d1dfe4cfc51d477748d0c1b14332a6` — report coredump state at boot

Boot output now reports:

`stage28e_coredump present=<0|1> valid=<0|1> size=<bytes> get_err=<err> check_err=<err>`

No synthetic panic was induced in Phase B. Bounded runtime evidence showed `present=0`, which is the expected clean state.

## B2 — low-wear RTC breadcrumbs

Commit:

`2c7cf143b7ebf253c29c1fe02148466accb23e95`

The breadcrumb lives in RTC no-init memory, not NVS or the telemetry FAT partition, so regular diagnostic updates create zero flash wear.

The retained structure contains a magic/version/checksum plus:

- write and boot sequence
- previous boot ID/reset reason
- last Stage28E log sequence/uptime/module/level
- last fault sequence/uptime/module/level/code
- last arbiter uptime
- arbiter instance/construction count
- transition/dwell-hold/safety-override/continuity-fault counters

A deterministic checksum protects against invalid RTC contents and partial/inconsistent state. A focused host test specifically mutates the suspected `arbiter_dwell_hold_count` field and proves the checksum rejects the modified state until recalculated.

Important runtime result: an external RTS/EN reset did not preserve RTC no-init state on this hardware path, so that path is not used to prove breadcrumb retention. A bounded software reset using `esp_restart()` did preserve it.

After `esp_restart()`, the next boot produced:

```text
stage28e_breadcrumb previous_valid=1 write_seq=10 boot_seq=1 boot_id=33c2cde5 reset_reason=1 last_log_seq=8 last_log_uptime_ms=52331 last_log_module=1 last_log_level=2 fault_code=0 fault_seq=0 fault_uptime_ms=0 arbiter_instance=1 arbiter_constructions=1 arbiter_transitions=0 arbiter_dwell_holds=0 arbiter_safety_overrides=0 arbiter_continuity_faults=0
```

This is direct evidence that the retained breadcrumb can bridge a software reset and expose the previous boot/runtime state.

## B3 — lifecycle identity

Commit:

`c2627fe9cc0bca3352c2fa1f6c40b9075d28b3bb`

The binary arbiter now has:

- process-local monotonic `instance_id`
- atomic construction count
- constructor diagnostics

The runtime entry path logs:

`stage28e_runtime_lifecycle entry_count=<n> mode=<mode>`

The arbiter constructor logs:

`arbiter_construct instance_id=<n> construction_count=<n>`

This separates:

- a new boot
- same-boot runtime re-entry/reconstruction
- corrupted cumulative counters on an unchanged instance

Focused/full host and firmware gates passed. The host suite completed 24/24 tests.

## B4 — arbiter counter continuity sentinel

Commit:

`1caf8557eecbec06dccf658ced65c285bf6c032b`

The arbiter now compares cumulative transition, dwell-hold and safety-override counters against the previous snapshot for the same instance.

A decrease that is not a valid uint32 wrap increments the continuity-fault counter and logs:

`arbiter_counter_regression instance_id=...`

The wrap policy is explicit: a small modulo delta across `UINT32_MAX -> 0` is accepted and does not raise a false alarm.

This directly targets the Stage28D V5 anomaly where cumulative dwell-hold evidence appeared to drop from values such as `43 -> 1`.

The sentinel is diagnostic only and does not alter requested/applied control behavior.

## HWM units correction discovered during Phase B

Commit:

`d75e904f59d2a00b4648b1498a6157351c903ea8`

Phase A had verified that this ESP-IDF 5.5.4 target reports `uxTaskGetStackHighWaterMark()` in bytes. The old telemetry code multiplied the value by `sizeof(StackType_t)`, effectively scaling it by four.

`soak_v=2 stack_free` now reports the real byte value. Bounded hardware evidence after the fix showed a plausible main-task value around `8064 B` rather than an inflated value.

## B5/B6 — heap integrity and heartbeat

Commit:

`2d15ff26769103be7ebf461d4891c2d7c0116d2e`

No new task or timer was added. Diagnostics piggyback on the existing roughly 10-second telemetry cadence:

- heartbeat on every report
- `heap_caps_check_integrity_all(false)` every six reports, roughly once per minute

Healthy messages:

- `heartbeat seq=... uptime_ms=... internal_free=... internal_min=...`
- `heap_integrity_ok check=... uptime_ms=... internal_free=... internal_largest=...`

Failure is diagnostic only and is also retained by the RTC breadcrumb through the Stage28E ERROR log path.

## Bounded hardware validation

Final task:

`20260906-growbox-stage28e-phase-b-hardware-diag-v3`

Exact source SHA:

`b43516a2adcd320b3da2b4ee9051e442cceb5c93`

A compile-time restart self-test was used only in the diagnostic build. It is controlled by:

`GROWBOX_STAGE28E_BREADCRUMB_RESTART_SELFTEST`

Normal/default value is `0`. The diagnostic build used `1` and waits for the first successful periodic heap-integrity check before calling one `esp_restart()`. A software-reset guard prevents a restart loop.

The build plumbing for this explicit CMake option was completed at `b43516a2adcd320b3da2b4ee9051e442cceb5c93`.

Diagnostic image with restart self-test enabled:

`743773 B`

Final Phase B runtime evidence across the software reset:

```text
STAGE28E_B_HW_V3_BREADCRUMB stage28e_breadcrumb previous_valid=1 write_seq=10 boot_seq=1 boot_id=33c2cde5 reset_reason=1 last_log_seq=8 last_log_uptime_ms=52331 last_log_module=1 last_log_level=2 fault_code=0 fault_seq=0 fault_uptime_ms=0 arbiter_instance=1 arbiter_constructions=1 arbiter_transitions=0 arbiter_dwell_holds=0 arbiter_safety_overrides=0 arbiter_continuity_faults=0
STAGE28E_B_HW_V3_HEARTBEATS 14 HEAP_OK 2
STAGE28E_B_HW_V3_STATUS status firmware_sha=b43516a2adcd320b3da2b4ee9051e442cceb5c93 boot_id=cd155bb3 reset_reason=3 uptime_ms=61619 outputs=fake-locked rf_ready=0 internal_total=337132 internal_free=217188 internal_min=216656 internal_largest=176128 psram_total=8388608 psram_free=8363512 psram_min=8363512 psram_largest=8257536 free_internal=217188 free_psram=8363512 stack_high_water=8064 current_task_stack_hwm_bytes=8064 task_total=9 task_captured=9 task_snapshot_psram=1 hwm_semantics=min_free_since_create
STAGE28E_B_HW_V3_SHELLY output_all_on=1 median_apower_w=65.50 samples=[65.4, 65.5, 65.5, 65.5, 65.5]
STAGE28E_B_HW_V3_RUNTIME_PASS
```

Key interpretation:

- `reset_reason=3` after the bounded restart proves an ESP software reset path
- previous breadcrumb validates across that reset
- previous arbiter instance/construction count is visible
- previous continuity-fault count is zero
- 14 heartbeats were observed across the two boot instances
- two heap-integrity successes were observed
- no coredump was present
- no heap-integrity failure, arbiter regression, Guru Meditation, corrupt-heap or stack-canary marker was observed
- main task HWM was about `8064 B`
- internal heap remained around `217188 B` free, `216656 B` minimum, `176128 B` largest block in this run
- PSRAM remained healthy
- outputs stayed `fake-locked`
- Shelly master stayed ON; median active power was `65.5 W`

## Normal-firmware restore proof

The final command rebuilt and flashed the same source SHA with:

`GROWBOX_STAGE28E_BREADCRUMB_RESTART_SELFTEST=0`

The normal restore build was verified not to contain the restart-self-test marker.

Final board status:

```text
status firmware_sha=b43516a2adcd320b3da2b4ee9051e442cceb5c93 boot_id=001a5795 reset_reason=1 uptime_ms=29659 outputs=fake-locked rf_ready=0 internal_total=337388 internal_free=217444 internal_min=216824 internal_largest=176128 psram_total=8388608 psram_free=8363512 psram_min=8363512 psram_largest=8257536 free_internal=217444 free_psram=8363512 stack_high_water=8064 current_task_stack_hwm_bytes=8064 task_total=9 task_captured=9 task_snapshot_psram=1 hwm_semantics=min_free_since_create
```

Shelly restore proof:

```text
output_all_on=1 median_apower_w=65.50 samples=[65.5, 65.5, 65.5, 65.6, 65.6]
```

Final task markers:

- `STAGE28E_B_HW_V3_SAFE_FAKE_LOCKED_PASS`
- `STAGE28E_B_HARDWARE_DIAG_V3_PASS`

## Firmware-size progression

Useful checkpoints:

- original Phase A baseline: `726061 B`
- Phase A diagnostic implementation: `730821 B`
- B1 coredump build after boot marker: `739537 B`
- lifecycle build: `739893 B`
- counter sentinel build: `740285 B`
- heartbeat/heap-integrity build: `741265 B`
- RTC breadcrumb gate build: `743369 B`
- diagnostic restart-self-test build: `743773 B`

The restart self-test is compile-time disabled in the normal firmware and is not a permanent runtime action.

## Phase B exit assessment

Phase B exit questions can now be answered from evidence:

- normal/power-on boot: `esp_reset_reason()` and boot/session ID
- software reset: `ESP_RST_SW` / reset reason 3 demonstrated on hardware
- crash/watchdog reset when reported by the platform: reset-reason framework and coredump partition are in place
- coredump present/absent: boot marker reports presence, validity and size
- same-boot object reconstruction: runtime entry count + arbiter instance/construction count
- counter corruption/regression on the same instance: explicit continuity sentinel
- prior state across software reset: validated RTC breadcrumb
- heap corruption: periodic heap-integrity checks plus retained diagnostic error breadcrumb
- runtime liveness: periodic heartbeat sequence

No evidence in the Phase B bounded run reproduced the Stage28D V5 cumulative-counter regression.

Phase B therefore passes its bounded implementation/runtime criteria. Long-duration stability remains intentionally deferred to Phase G.

## Phase C next

Start Phase C read-only and quantitative. Do not optimize memory yet.

Required first evidence:

1. exact current source SHA after Phase B closing docs/gate;
2. linker/static memory map: `.data`, `.bss`, IRAM, flash text/rodata and largest static DRAM contributors where tooling permits;
3. runtime object inventory with `sizeof`, owner, lifetime and storage class;
4. explicit audit of long-lived locals in the non-returning climate runtime function, because they occupy `app_main` stack for the process lifetime;
5. allocation classification: INTERNAL/DMA, generic malloc/new, explicit PSRAM and library-owned allocations;
6. stack-depth/local-buffer/copy audit using Phase A/B HWM evidence;
7. representative boot/BLE/sensor/telemetry/service-console memory samples including free/min/largest-block values.

The suspected approximately 1 KiB internal-memory crisis is still not reproduced. Phase C must determine quantitatively whether it was an old build, transient/minimum value, wrong metric/units, fragmentation event or another condition.

Do not return to the real AH actuator path before A-G pass and Phase H explicitly begins.
