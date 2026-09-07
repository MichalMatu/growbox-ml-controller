# Current controller status

Updated: 2026-09-07
Development branch: `mvp/environment-controller`
Latest handoff: `docs/STAGE28E_PHASE_H_HANDOFF.md`
Stage28E execution guide: `docs/GUIDANCE.md`
Prior Stage28D evidence: `docs/STAGE28D_AH_ARBITER_HANDOFF.md`
Primary roadmap: `docs/PROJECT_ROADMAP.md`
Continuation checklist: `docs/CONTINUATION_PLAN.md`

## Current transition

**Stage27C FROZEN -> Stage28E A COMPLETE -> B COMPLETE -> C COMPLETE -> D COMPLETE -> E COMPLETE -> F COMPLETE -> G COMPLETE -> H IN PROGRESS**

A-G are formally complete. Phase H is the only remaining Stage28E phase.

Formal Phase G exit gate:

`7ddb995d1f6cd190fa110f21f0d8dc0eabc61d26`

Current Phase H runtime/tooling source SHA:

`5a4830db9d10e8cb73d4c617b09122f0844ad899`

Full current H evidence and the fresh-chat procedure are in `docs/STAGE28E_PHASE_H_HANDOFF.md`.

## Phase H current result

Phase H is **not PASS yet**.

The required evidence remains:

`natural AH/rule request -> binary arbiter OFF->ON -> RF -> physical fan`

H v3 established that the repaired real/RF runtime is stable, but startup lamp safety forced the fan ON before the natural AH request could be observed from a normal OFF prestate.

V3 positive evidence:

- no main-task stack overflow;
- stable real-bounded boot/session;
- RF ready;
- main stack `16384 B`, worst observed free HWM about `2600 B`;
- internal free/min/largest approximately `218592 / 218060 / 176128 B`;
- natural fan request approximately `0.444-0.500`;
- after startup recovery: safety clear;
- physical fan ON;
- arbiter transition count `1`;
- RF TX count `5`, TX errors `0`;
- manual safe recovery PASS;
- final RF-disabled `fake-locked` PASS;
- Shelly master remained ON.

Primary failure reason:

`natural requested_fan>=0.10 not observed in bounded window`

This is expected from the observed sequence: startup `TemperatureUnavailable` safety forced exhaust ON, then the normal AH request was already high when safety cleared.

## RF-enabled main-stack correction

The Stage27C 12 KiB main stack was qualified only in fake-locked builds and overflowed inside the deeper ESP-IDF RMT initialization call path.

Current policy:

- RF disabled/fake build: `CONFIG_ESP_MAIN_TASK_STACK_SIZE=12288`;
- RF enabled build: `CONFIG_ESP_MAIN_TASK_STACK_SIZE=16384`.

Implementation:

- `config/idf/sdkconfig.defaults.stage28rf`
- conditional selection in `scripts/stage27c_crowpanel.sh`

Dual-build verification passed on SHA `5a4830db9d10e8cb73d4c617b09122f0844ad899`.

Do not shrink the RF-enabled main stack based on fake-only evidence.

## Physical setup required for the next H run

Do not intentionally exceed 28 C. Thermal trip `>=28 C` is safety evidence, not AH evidence.

Preferred setup:

1. Xiaomi remains outside/intake.
2. TP357 starts inside with `<=26 C` and preferably daytime RH `<=60%`.
3. Keep the tent open/ventilated during startup-safety recovery.
4. If TP357 was unavailable during an early cycle, hold `<=26 C` continuously for 10 minutes until `safety_latched=0 force_fan=0 safety_reason=0`.
5. Require normal fan OFF before creating the H request.
6. Then close the tent / allow lamp warming while keeping TP357 below 28 C.
7. A useful natural temperature trigger is roughly inside `26-27 C` with Xiaomi/intake around `23-24 C`; alternatively daytime RH above roughly `62%` with materially drier intake can cross the fan ON request threshold.
8. Observe normal minimum-OFF dwell, OFF->ON arbiter transition, RF TX increment with `tx_errors=0`, physical/Shelly evidence.
9. Always restore/prove final `fake-locked`.

Exact request math and startup-safety details are in `docs/STAGE28E_PHASE_H_HANDOFF.md`.

## Safety boundary

Correct Growbox serial device:

`/dev/cu.usbserial-1130`

Never open/probe/flash:

`/dev/cu.usbserial-10`

Standing invariants:

- rule controller authoritative;
- ML shadow/research-only;
- thermal trip `>=28 C`;
- recovery `<=26 C` continuously for 10 minutes;
- manual RF blocked during `real-bounded`;
- Shelly master stays ON;
- after bounded diagnostics restore/prove `fake-locked`;
- serial-open reset is tolerated only before the stabilized post-open baseline.

## Local Agent execution identity

- repository: `MichalMatu/growbox-ml-controller`
- repository id: `growbox-ml-controller`
- agent binding: `815cf40f-8d2a-4e1f-b7cc-c0f4e37b6cb5`
- control branch: `agent-control`
- work branch: `mvp/environment-controller`

Before edits or tasks, read fresh `.agent/status/daemon.json`.

For tasks:

- exact `agent_binding` is mandatory;
- use `resources: []` for software/docs/build work;
- use `resources: ["board:growbox-s3"]` for serial/flash/hardware;
- verify exact SHA explicitly because `expected_head` is not implemented;
- read terminal `.agent/results/<task-id>.json` before reporting PASS.

## Modularity status

Do not refactor production runtime before the pending H physical proof.

After formal H close, start a separate behavior-preserving modularity series. Priority targets:

1. split the `runClimateV6RealInputRuntime()` god-function into bootstrap, scheduler/cycle, output/fail-safe, and telemetry seams;
2. split `Stage28ServiceConsole` into transport/parser plus status, RF, RTC, sensor, and storage command modules.

The detailed proposed seams and verification policy are in `docs/STAGE28E_PHASE_H_HANDOFF.md`.

## Immediate next work

1. Read `docs/STAGE28E_PHASE_H_HANDOFF.md`.
2. Fetch fresh work-branch HEAD and fresh daemon/result evidence.
3. Prepare TP357/Xiaomi so startup safety can recover with a low natural fan request.
4. Run the next bounded H physical attempt without any request injector and without intentionally crossing 28 C.
5. Require normal fan OFF prestate, natural request `>=0.10`, minimum-OFF dwell, normal arbiter OFF->ON, RF/physical/Shelly evidence.
6. Restore/prove `fake-locked`.
7. Only after H formally closes, begin the modularity backlog.
