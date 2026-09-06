# Current controller status

Updated: 2026-09-06
Development branch: `mvp/environment-controller`
Latest handoff: `docs/STAGE28E_PHASE_A_HANDOFF.md`
Stage28E execution guide: `docs/GUIDANCE.md`
Prior Stage28D evidence: `docs/STAGE28D_AH_ARBITER_HANDOFF.md`
Primary roadmap: `docs/PROJECT_ROADMAP.md`
Continuation checklist: `docs/CONTINUATION_PLAN.md`

## Current transition

**Stage27C FROZEN -> Stage28A/B/C DONE -> Gates 1-6 COMPLETE -> Gate 7 previously qualified -> AH policy software COMPLETE -> Gate 7 runtime path REOPENED by V5 evidence -> Stage28E Phase A observability COMPLETE pending docs-only exit gate -> Phase B next**

Stage28D functional work remains intentionally paused. The current program is Stage28E A -> H, with Phase A providing the observability foundation needed to diagnose the V5 runtime discontinuity from evidence rather than inference.

## Current Phase A source identity

Phase A implementation/hardware diagnostic executable:

`3058625be2f35c121afcf82549d5c73068839ecd`

Phase A starting point:

`2218ad30401222537cb568541d80bc07adc2c0eb`

The first Phase A closing documentation commit is:

`32b664a0fcebc1ecbc5863ca07d3200e3d4603ef`

Always fetch fresh work-branch HEAD before editing because additional Phase A documentation commits and the final docs-only exit gate may be above this SHA.

## Phase A completed capability

The firmware now exposes:

- structured Stage28E logging with fixed buffers, compile-time gating and module filters;
- firmware SHA, boot/session ID, reset reason and uptime;
- internal RAM total/current/minimum/largest-block metrics;
- PSRAM total/current/minimum/largest-block metrics;
- task/core/priority/configured-stack/HWM/severity snapshots;
- aggregate service-console, RF, control, telemetry and main-loop timing with overrun count.

Verified ESP-IDF contract for this build:

- stack HWM values are bytes, not words;
- non-SMP task core lookup uses `xTaskGetCoreID(task.xHandle)`;
- warning threshold is below 25% remaining configured stack;
- critical threshold is below 10%.

## Phase A bounded hardware evidence

Task:

`20260906-growbox-stage28e-phase-a-hardware-diag-v1`

Exact diagnostic firmware:

`3058625be2f35c121afcf82549d5c73068839ecd`

Representative safe snapshot:

- boot ID `30b159d6`;
- reset reason `1` / expected power-on reset after flash/reboot;
- outputs `fake-locked`;
- internal RAM: total `341620 B`, free `221648 B`, minimum `221028 B`, largest block `180224 B`;
- PSRAM: total `8388608 B`, free `8363512 B`, minimum `8363108 B`, largest block `8257536 B`;
- main stack: `8140 B` HWM of `16384 B` configured;
- `stage27_store`: `2908 B` HWM of `7168 B`, about 40.6% margin;
- `nimble_host`: `1688 B` HWM of `4096 B`, about 41.2% margin;
- no known stack warning/critical state;
- worst active loop `194320 us` against a `1000000 us` budget;
- loop overruns `0`;
- control max `21607 us`;
- telemetry max `183523 us`.

The earlier suspected approximately 1 KiB internal-memory crisis was **not reproduced** in this bounded representative run. Phase C must still audit static/stack/heap ownership and fragmentation; Phase G will provide longer runtime evidence.

A UART capture once ended mid-line and displayed `stage27_store hwm_bytes=29`. That value is invalid truncation evidence; the complete line reported `2908 B`.

## Hardware-confirm v1/v2 interpretation

Two extra read-only confirmation attempts failed at the UART parser/harness layer, not on a product assertion.

`hardware-confirm-v2` ran successfully after Local Agent recovery. Its first command proved exact local and remote work SHA `3058625...`, a clean tree and presence of `/dev/cu.usbserial-1130`. The second command failed because a fixed 5-second capture window did not contain a complete line beginning with `status `. The tail contained normal startup/runtime text and `outputs=fake-locked`.

Because the original bounded diagnostic already produced a complete valid snapshot answering every Phase A exit question, a third identical confirmation attempt is not required.

See `docs/STAGE28E_PHASE_A_HANDOFF.md` for the complete Phase A evidence and exit rationale.

## Firmware-size evidence

Original Phase A baseline image:

`726061 B`

Final Phase A diagnostic image at `3058625...`:

`730821 B`

Net increase:

`+4760 B`

The original baseline also had `119759 B` DIRAM used and `222001 B` remaining of `341760 B`.

## V5 issue remains open

The latest decisive Stage28D functional evidence remains V5:

`20260906-growbox-ah-arbiter-clean-v5`

Representative non-safety state included:

- `requested_fan=0.111`;
- fan/applied fan OFF;
- safety/force/reason all zero;
- `arbiter_transitions=0`;
- `tx_errors=0`;
- inside AH about `15.10 g/m3`;
- intake AH about `11.69 g/m3`;
- AH gap about `3.41 g/m3`;
- Shelly about `61.7 W`.

The important discontinuity remains cumulative `arbiter_dwell_holds` decreasing within the apparent run:

`33 -> 43 -> 1 -> 11`

Do not assume `Stage28dBinaryRoleArbiter::applyBinary()` is the root cause. Stage28E must distinguish reset, object reconstruction, corruption, timing discontinuity, lifecycle/state reconciliation and execution-environment causes before returning to the final physical Gate 7 confirmation.

## Latest safety boundary

Correct Growbox serial device:

`/dev/cu.usbserial-1130`

Never open, probe, monitor, reset or flash:

`/dev/cu.usbserial-10`

That port belongs to another project.

Standing policy/safety invariants:

- native ESP-IDF direction;
- deterministic rule controller authoritative;
- ML shadow/research-only;
- thermal trip `>=28 C`;
- recovery `<=26 C` continuously for 10 minutes;
- manual RF remains blocked during `real-bounded`;
- Shelly master stays ON;
- no unattended real-output mode;
- after bounded diagnostics restore/prove fake-locked safe state.

Previously qualified physical state to restore when applicable:

- lamp ON;
- fan OFF;
- humidifier OFF;
- Shelly master ON;
- about `61.7 W`.

## Immediate next work

1. Complete the Phase A docs-only exact-SHA exit gate.
2. Record the resulting Phase A exit SHA.
3. Start **Stage28E Phase B — crash, reset, corruption, and lifecycle diagnostics**.
4. First Phase B action must be read-only: inspect the exact installed ESP-IDF coredump configuration symbols and verify the current 8 MiB flash/partition bounds before editing configuration.
5. Then implement Phase B in small evidence-backed slices: coredump support, low-wear breadcrumbs, lifecycle/instance IDs, state sentinels, targeted heap-integrity checks and subsystem heartbeats.

Do not return to a real AH actuator transition until A-G pass and Phase H explicitly starts the bounded end-to-end path.
