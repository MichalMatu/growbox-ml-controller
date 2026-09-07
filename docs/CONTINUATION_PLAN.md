# Fresh-context continuation plan

Updated: 2026-09-07
Work branch: `mvp/environment-controller`
Control branch: `agent-control`
Latest handoff: `docs/STAGE28E_PHASE_H_HANDOFF.md`
Current status: `docs/CURRENT_STATUS.md`
Execution guide: `docs/GUIDANCE.md`

## Read first in a new chat

1. `AGENTS.md`
2. `docs/STAGE28E_PHASE_H_HANDOFF.md`
3. `docs/CURRENT_STATUS.md`
4. this file
5. `docs/GUIDANCE.md`
6. `docs/ESP32_S3_SERIAL_PORT_RESET.md`
7. `docs/STAGE28D_AH_ARBITER_HANDOFF.md`
8. `docs/STAGE28E_PHASE_G_HANDOFF.md` when Phase G evidence details are needed
9. `docs/PROJECT_ROADMAP.md`

Then fetch fresh `mvp/environment-controller` HEAD and fresh `agent-control:.agent/status/daemon.json`. Read the newest relevant `.agent/results/...` before deciding what has passed. Never continue from remembered chat state alone.

## Current transition

**Stage28E A-G COMPLETE -> H IN PROGRESS**

Formal Phase G exit gate:

`7ddb995d1f6cd190fa110f21f0d8dc0eabc61d26`

Qualified current Phase H runtime/tooling source SHA:

`5a4830db9d10e8cb73d4c617b09122f0844ad899`

A later documentation-only HEAD must not be mistaken for a new firmware qualification.

## What H still has to prove

One bounded normal control path:

`natural AH/rule request -> binary arbiter OFF->ON -> RF -> physical fan`

Required evidence:

- exact firmware/source SHA;
- post-serial-open boot/session baseline;
- safety clear;
- normal fan OFF prestate;
- natural request `>=0.10`;
- minimum-OFF dwell/counters;
- one normal OFF->ON arbiter transition;
- RF TX increment and `tx_errors=0`;
- independent physical/Shelly support;
- memory/stack/timing remain acceptable;
- mandatory safe recovery and final RF-disabled `fake-locked`.

Do not add a request injector to force PASS.

## Why H v3 did not pass

The RF/main-stack problem is fixed. V3 ran stably with RF-enabled main stack `16384 B`.

However, startup lamp safety saw TP357 unavailable before the first usable sample, latched safety, and forced exhaust ON. Once safety recovered, the natural AH request was already high (`~0.44-0.50`), so the fan never presented the required normal OFF prestate.

Recovery/final were successful; the board ended `fake-locked`.

## Correct physical preparation

The user is preparing to put sensors in the tent and use the lamp.

Do not intentionally heat to `>=28 C`; that triggers thermal safety and does not count as AH evidence.

For the next attempt:

1. Xiaomi stays outside/intake.
2. TP357 stays in the inside position.
3. During startup keep TP357 `<=26 C` continuously and preferably daytime RH `<=60%`.
4. Keep the tent open/ventilated enough that the normal fan request can fall below the OFF threshold.
5. If startup safety latched, allow the full 10-minute `<=26 C` recovery.
6. Confirm `safety_latched=0 force_fan=0 safety_reason=0` and fan OFF.
7. Then close the tent / allow lamp warming.
8. Prefer a TP357 temperature around `26-27 C` while Xiaomi/intake remains around `23-24 C`; stay below 28 C. A >2 C inside-to-intake difference is sufficient to activate the current temperature-ventilation path and gives a request above the binary ON threshold.
9. Alternatively, daytime TP357 RH around `>=62%` with materially drier Xiaomi intake can produce the fan request.
10. Once request is high, let the existing 120 s minimum-OFF dwell run naturally and capture the normal OFF->ON transition.
11. Run recovery/final fake-locked checks even if primary H fails.

Exact formulas and thresholds are in `docs/STAGE28E_PHASE_H_HANDOFF.md`.

## Local Agent / hybrid workflow

Repository identity:

- repo `MichalMatu/growbox-ml-controller`;
- repo id `growbox-ml-controller`;
- agent binding `815cf40f-8d2a-4e1f-b7cc-c0f4e37b6cb5`;
- control branch `agent-control`;
- work branch `mvp/environment-controller`.

Rules:

- new Chat Bridge conversation gets its own `LA_CHAT`; never invent/copy a chat id as a substitute for the bridge envelope;
- hard repository binding is fail-closed;
- direct GitHub is suitable for bounded exact diffs/docs;
- Local Agent handles Mac commands, local builds/tests, serial/flash/device evidence;
- hybrid flow: direct GitHub commit -> Local Agent exact-SHA read-only verification;
- `resources: []` for software/docs/build;
- `resources: ["board:growbox-s3"]` for hardware;
- exact SHA must be checked in-task; `expected_head` is unsupported;
- task IDs/payloads are immutable;
- follow run/status and read terminal result before PASS;
- use narrow source inspection paths; avoid unbounded repo-wide grep through build/generated assets.

Canonical Local Agent docs are referenced from `AGENTS.md`. This repository-bound conversation must not inspect another repository without explicit Bridge Rebind.

## Modularity after H

Do not change production runtime structure before the H physical proof.

After H closes, begin a separate behavior-preserving extraction series:

- split `runClimateV6RealInputRuntime()` into bootstrap, scheduler/cycle, output/fail-safe, and telemetry responsibilities;
- split `Stage28ServiceConsole` into serial transport/parser and separate status/RF/RTC/sensor/storage command modules.

Use focused host tests after each extraction, one final full software gate, and bounded fake-locked hardware evidence when runtime layout/stack changes materially.

## Recommended fresh-chat instruction

`Continue Stage28E Phase H only. First read AGENTS.md, docs/STAGE28E_PHASE_H_HANDOFF.md, docs/CURRENT_STATUS.md, docs/CONTINUATION_PLAN.md, docs/GUIDANCE.md, docs/ESP32_S3_SERIAL_PORT_RESET.md and docs/STAGE28D_AH_ARBITER_HANDOFF.md. Fresh-check mvp/environment-controller HEAD and agent-control:.agent/status/daemon.json. A-G are formally complete. Qualified H runtime/tooling source SHA is 5a4830db9d10e8cb73d4c617b09122f0844ad899. H v3 fixed the RF stack overflow but failed the AH OFF->ON proof because startup safety forced the fan ON first. Do not intentionally cross 28 C and do not add a request injector. Prepare TP357 <=26 C with low RH/request through startup recovery, obtain safety-clear normal fan OFF, then close the tent/use the lamp while staying below 28 C to create a natural request >=0.10, observe the 120 s OFF dwell, normal arbiter OFF->ON, RF TX with zero errors, physical/Shelly evidence, and final fake-locked recovery. Defer god-object modularization until H is formally complete.`
