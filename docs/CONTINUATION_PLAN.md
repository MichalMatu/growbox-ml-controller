# Fresh-context continuation plan

Updated: 2026-09-06
Work branch: `mvp/environment-controller`
Control branch: `agent-control`
Latest handoff: `docs/STAGE28E_PHASE_B_HANDOFF.md`
Stage28E execution guide: `docs/GUIDANCE.md`
Prior Stage28D evidence: `docs/STAGE28D_AH_ARBITER_HANDOFF.md`
Current status: `docs/CURRENT_STATUS.md`
Primary roadmap: `docs/PROJECT_ROADMAP.md`

## Read first in a new chat

1. `AGENTS.md`
2. `docs/GUIDANCE.md`
3. `docs/STAGE28E_PHASE_B_HANDOFF.md`
4. `docs/PROJECT_ROADMAP.md`
5. `docs/CURRENT_STATUS.md`
6. this file
7. `docs/STAGE28E_PHASE_A_HANDOFF.md` when Phase A baseline detail is needed
8. `docs/STAGE28D_AH_ARBITER_HANDOFF.md` when historical V5 details are needed
9. `docs/OBSERVABILITY_AND_INFERENCE_PLAN.md` when changing ventilation, inference, telemetry or ML behavior
10. `docs/SHELLY_POWER_FEEDBACK.md` when changing physical-state supervision

Then fetch fresh `mvp/environment-controller` HEAD, fresh `agent-control:.agent/status/daemon.json`, and the newest Local Agent result. Never continue from remembered chat state alone.

## Current transition

**Stage27C FROZEN -> Stage28A/B/C DONE -> Gates 1-6 COMPLETE -> Gate 7 previously qualified -> AH policy software COMPLETE -> Gate 7 runtime path REOPENED by V5 -> Stage28E Phase A COMPLETE -> Phase B COMPLETE pending final docs-only exit gate -> Phase C next**

Stage28D functional AH work stays paused until A-G pass. The final physical `AH/rule request -> binary arbiter -> RF -> physical fan` path belongs to Stage28E Phase H.

## Phase A identity

Phase A exit SHA:

`384e415eaaec960add2b3b3fe94db5c052ca6497`

Phase A established boot/session identity, structured logging, internal/PSRAM metrics, task-stack snapshots and runtime timing evidence. Its bounded hardware run did not reproduce the historical approximately 1 KiB internal-memory crisis.

Full evidence:

`docs/STAGE28E_PHASE_A_HANDOFF.md`

## Phase B identity and evidence

Phase B hardware-validated source SHA:

`b43516a2adcd320b3da2b4ee9051e442cceb5c93`

Complete evidence:

`docs/STAGE28E_PHASE_B_HANDOFF.md`

Phase B added:

- flash coredump partition/configuration and boot status;
- RTC no-init checksum-protected crash/reset breadcrumbs;
- runtime/arbiter lifecycle instance and construction identity;
- same-instance cumulative counter regression detection;
- corrected stack-HWM telemetry units;
- periodic heartbeat;
- periodic heap-integrity checks;
- bounded compile-time software-restart self-test, disabled in normal firmware.

Final hardware task:

`20260906-growbox-stage28e-phase-b-hardware-diag-v3`

Key result across the bounded `esp_restart()`:

- post-reset reason `3` / `ESP_RST_SW`;
- previous breadcrumb `previous_valid=1`;
- previous arbiter instance/construction `1/1`;
- previous continuity faults `0`;
- 14 heartbeats;
- two successful heap-integrity checks;
- no coredump or corruption/crash markers;
- outputs `fake-locked`;
- Shelly master ON, median power `65.5 W`.

After the diagnostic the same source SHA was rebuilt/flashed with restart self-test `0`. Final normal-firmware status remained `fake-locked`, `rf_ready=0`, main HWM about `8064 B`, internal RAM free/min/largest `217444 / 216824 / 176128 B`, Shelly ON at median `65.5 W`.

## V5 issue remains the functional problem to explain

The decisive prior Stage28D task remains:

`20260906-growbox-ah-arbiter-clean-v5`

V5 showed a non-safety fan request above the ON threshold while the fan remained OFF after the expected dwell window. The strongest clue remains cumulative `arbiter_dwell_holds` decreasing:

`33 -> 43 -> 1 -> 11`

Phase B did not reproduce such a regression in the bounded diagnostic run. It did make future occurrences diagnosable as boot/reset, same-boot reconstruction, same-instance regression/corruption or another platform fault.

Do not jump directly to changing `applyBinary()`.

## Serial and hardware invariants

Growbox/CrowPanel serial:

`/dev/cu.usbserial-1130`

Never touch:

`/dev/cu.usbserial-10`

For Local Agent tasks:

- every task must contain exactly `"agent_binding": "815cf40f-8d2a-4e1f-b7cc-c0f4e37b6cb5"`;
- use `resources: []` for software/docs/build work;
- use `resources: ["board:growbox-s3"]` for serial/flashing/device work;
- check fresh daemon state before editing the same branch or queueing hardware access.

Safety boundary:

- rule controller authoritative;
- ML shadow/research-only;
- thermal trip `>=28 C`;
- recovery `<=26 C` continuously for 10 minutes;
- manual RF blocked during `real-bounded`;
- Shelly master ON;
- no unattended real-output operation;
- restore/prove fake-locked after bounded diagnostics.

## Immediate next work

### 1. Close Phase B formally

Run one docs-only exact-SHA Local Agent gate on the fresh work-branch HEAD. It should verify:

- exact local and remote SHA;
- clean work tree;
- `git diff --check`;
- `docs/STAGE28E_PHASE_B_HANDOFF.md` exists and references source SHA `b43516a2adcd320b3da2b4ee9051e442cceb5c93`;
- the handoff records `previous_valid=1`, `reset_reason=3`, 14 heartbeats, two heap-integrity successes and safe normal-firmware restore;
- `docs/CURRENT_STATUS.md` points to Phase C next;
- this continuation file points to the Phase B handoff;
- no build, flash or device action is performed.

Record the passing SHA as the formal Phase B exit SHA.

### 2. Start Phase C read-only

Phase C is **memory map, stack audit and resource baseline**. Do not optimize first.

Collect reproducible evidence for:

1. `.data`, `.bss`, IRAM, flash text/rodata and largest static DRAM contributors where tooling permits;
2. firmware image/static-size baseline;
3. every important long-lived/large object: type, `sizeof`, owner, lifetime and storage location;
4. large locals in the non-returning climate runtime function, because they remain on `app_main` stack for the firmware lifetime;
5. stack frames, large local arrays, accidental copies and deep call paths;
6. allocation classes: internal-only, DMA/internal, generic `malloc/new`, explicit PSRAM and library-owned Wi-Fi/BLE allocations;
7. representative runtime memory during boot, BLE, sensors, telemetry/storage, service-console diagnostics and normal control operation;
8. current/minimum/largest-block values for internal RAM and PSRAM.

Rank the top memory-risk items by measured evidence.

Do not change allocator thresholds, move objects to PSRAM or refactor ownership until the audit explains where memory is actually consumed.

The historical approximately 1 KiB internal-free observation remains unconfirmed. Phase C must classify it as real/current, transient, minimum-ever, fragmentation-related, stale-build evidence or incorrect measurement.

## Recommended fresh-chat instruction

`Read AGENTS.md, docs/GUIDANCE.md, docs/STAGE28E_PHASE_B_HANDOFF.md, docs/CURRENT_STATUS.md and docs/CONTINUATION_PLAN.md. Fetch fresh mvp/environment-controller HEAD and Local Agent daemon/result evidence first. Treat Phase B as complete only if its docs-only exact-SHA exit gate passed. Then continue with Stage28E Phase C read-only memory/resource audit; do not optimize or return to Stage28D AH physical testing until the sequential Stage28E gates permit it.`
