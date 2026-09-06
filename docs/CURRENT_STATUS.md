# Current controller status

Updated: 2026-09-06
Development branch: `mvp/environment-controller`
Latest handoff: `docs/STAGE28E_PHASE_B_HANDOFF.md`
Stage28E execution guide: `docs/GUIDANCE.md`
Prior Stage28D evidence: `docs/STAGE28D_AH_ARBITER_HANDOFF.md`
Primary roadmap: `docs/PROJECT_ROADMAP.md`
Continuation checklist: `docs/CONTINUATION_PLAN.md`

## Current transition

**Stage27C FROZEN -> Stage28A/B/C DONE -> Gates 1-6 COMPLETE -> Gate 7 previously qualified -> AH policy software COMPLETE -> Gate 7 runtime path REOPENED by V5 evidence -> Stage28E Phase A COMPLETE -> Phase B COMPLETE pending final docs-only exit gate -> Phase C next**

Stage28D functional work remains intentionally paused. The active program remains Stage28E A -> H. Phase A established low-overhead observability; Phase B added reset/crash/corruption/lifecycle evidence. Phase C now performs a quantitative memory/resource audit before any broad optimization or architecture change.

## Phase identities

Phase A exit SHA:

`384e415eaaec960add2b3b3fe94db5c052ca6497`

Phase B hardware-validated source SHA:

`b43516a2adcd320b3da2b4ee9051e442cceb5c93`

Phase B evidence handoff creation commit:

`d1df3bdca7eaf0683609c816c875bba326f05f97`

Always fetch fresh work-branch HEAD and Local Agent daemon state before editing or queueing work.

## Phase B completed capability

The firmware now provides:

- 1 MiB flash coredump partition with ELF/CRC32/DRAM capture configuration;
- boot-time coredump presence/validity/size reporting;
- low-wear RTC no-init breadcrumbs with magic/version/checksum;
- retained previous boot/log/fault/arbiter counters across software reset;
- runtime entry count and arbiter instance/construction identity;
- same-instance cumulative counter regression detection with explicit uint32 wrap handling;
- corrected stack-HWM telemetry units for ESP-IDF 5.5.4;
- periodic runtime heartbeat at the existing telemetry cadence;
- periodic `heap_caps_check_integrity_all(false)` at roughly one-minute cadence;
- diagnostic-only compile-time breadcrumb restart self-test, disabled by default.

Key Phase B commits include:

- `9e5ae78f4f4dc56426ecfefd5724c9861d810465` — coredump partition
- `5f7cdab9811fe8df686565516ce326fbb23041ba` — coredump configuration
- `2cf2a19bb9d1dfe4cfc51d477748d0c1b14332a6` — coredump boot marker
- `c2627fe9cc0bca3352c2fa1f6c40b9075d28b3bb` — lifecycle identity
- `1caf8557eecbec06dccf658ced65c285bf6c032b` — arbiter counter continuity sentinel
- `d75e904f59d2a00b4648b1498a6157351c903ea8` — stack-HWM unit correction
- `2d15ff26769103be7ebf461d4891c2d7c0116d2e` — heartbeat and heap integrity
- `2c7cf143b7ebf253c29c1fe02148466accb23e95` — RTC breadcrumbs
- `528357397c38dbfbb82af1f09df907cf8bc7b651` — bounded restart self-test
- `b43516a2adcd320b3da2b4ee9051e442cceb5c93` — explicit build option plumbing for restart self-test

## Phase B bounded hardware evidence

Final task:

`20260906-growbox-stage28e-phase-b-hardware-diag-v3`

Exact source SHA:

`b43516a2adcd320b3da2b4ee9051e442cceb5c93`

The diagnostic build was fake-locked with real RF outputs disabled. It performed one bounded `esp_restart()` after a successful periodic heap-integrity check.

Evidence after the software reset:

- reset reason `3` / `ESP_RST_SW`;
- retained breadcrumb `previous_valid=1`;
- previous breadcrumb boot sequence `1`;
- previous arbiter instance `1` and construction count `1`;
- previous arbiter continuity faults `0`;
- 14 heartbeats observed across the two boot instances;
- two successful heap-integrity checks;
- no coredump present;
- no `heap_integrity_failed`;
- no `arbiter_counter_regression`;
- no Guru Meditation / corrupt heap / stack-canary marker;
- post-reset main HWM about `8064 B`;
- internal RAM: free `217188 B`, minimum `216656 B`, largest `176128 B`;
- PSRAM free `8363512 B`, minimum `8363512 B`, largest `8257536 B`;
- outputs `fake-locked`;
- Shelly master ON;
- Shelly median power `65.5 W`.

The most important retained line was:

```text
stage28e_breadcrumb previous_valid=1 write_seq=10 boot_seq=1 boot_id=33c2cde5 reset_reason=1 last_log_seq=8 last_log_uptime_ms=52331 last_log_module=1 last_log_level=2 fault_code=0 fault_seq=0 fault_uptime_ms=0 arbiter_instance=1 arbiter_constructions=1 arbiter_transitions=0 arbiter_dwell_holds=0 arbiter_safety_overrides=0 arbiter_continuity_faults=0
```

This proves the breadcrumb can preserve prior runtime/arbiter state across the software-reset path that Phase B needs to diagnose.

## Normal-firmware restore proof

After the diagnostic run, the board was rebuilt and flashed from the same source SHA with:

`GROWBOX_STAGE28E_BREADCRUMB_RESTART_SELFTEST=0`

The restore build was checked not to contain the restart-self-test marker.

Final status:

- firmware SHA `b43516a2adcd320b3da2b4ee9051e442cceb5c93`;
- reset reason `1` after flash/hardware reboot;
- outputs `fake-locked`;
- `rf_ready=0`;
- internal RAM free/min/largest `217444 / 216824 / 176128 B`;
- main HWM `8064 B`;
- Shelly master ON;
- Shelly median power `65.5 W`.

Final task markers:

- `STAGE28E_B_HW_V3_RUNTIME_PASS`
- `STAGE28E_B_HW_V3_SAFE_FAKE_LOCKED_PASS`
- `STAGE28E_B_HARDWARE_DIAG_V3_PASS`

## Firmware-size evidence

Useful progression:

- original Phase A baseline: `726061 B`
- Phase A diagnostic implementation: `730821 B`
- B1 coredump + boot marker: `739537 B`
- lifecycle build: `739893 B`
- counter sentinel build: `740285 B`
- heartbeat/heap-integrity build: `741265 B`
- RTC breadcrumb build: `743369 B`
- diagnostic restart-self-test build: `743773 B`

The restart self-test is compile-time disabled in the normal firmware.

## V5 issue remains open but is now diagnosable

The decisive Stage28D functional evidence remains V5:

`20260906-growbox-ah-arbiter-clean-v5`

The unexplained cumulative dwell-hold decrease remains:

`33 -> 43 -> 1 -> 11`

Phase B did not reproduce a same-instance counter regression. The firmware can now distinguish:

- new boot/reset;
- same-boot arbiter/runtime reconstruction;
- same-instance cumulative counter regression;
- prior state retained across a software reset;
- heap-integrity failure;
- missing runtime heartbeat;
- coredump presence/absence.

Do not change `Stage28dBinaryRoleArbiter::applyBinary()` based only on the old V5 trace. Phase C-G must complete before returning to the final physical actuator path in Phase H.

## Latest safety boundary

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

1. Run one docs-only exact-SHA Phase B exit gate on the fresh work-branch HEAD.
2. Record that SHA as the formal Phase B exit SHA.
3. Start **Stage28E Phase C — memory map, stack audit and resource baseline**.
4. Phase C starts read-only: collect linker/static memory evidence and inventory long-lived runtime objects before changing architecture or allocator policy.
5. Quantify `.data`, `.bss`, IRAM, flash text/rodata, static DRAM contributors, task HWM, large objects, storage location and allocation capability.
6. Pay special attention to large locals inside the non-returning climate runtime function because they remain resident on `app_main` stack.
7. Classify generic `malloc/new`, explicit PSRAM, internal/DMA and library-owned allocations.
8. Decide from measured evidence whether the historical approximately 1 KiB internal-free observation was real, transient, minimum-ever, fragmentation-related or incorrect.

Do not run a long soak before Phase G and do not return to a real AH actuator transition before Phase H.
