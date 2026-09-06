# Fresh-context continuation plan

Updated: 2026-09-06
Work branch: `mvp/environment-controller`
Control branch: `agent-control`
Latest handoff: `docs/STAGE28D_AH_ARBITER_HANDOFF.md`
Primary roadmap: `docs/PROJECT_ROADMAP.md`
Current status: `docs/CURRENT_STATUS.md`
Observability contract: `docs/OBSERVABILITY_AND_INFERENCE_PLAN.md`
Shelly power feedback: `docs/SHELLY_POWER_FEEDBACK.md`

## Read first in a new chat

1. `AGENTS.md`
2. `docs/STAGE28D_AH_ARBITER_HANDOFF.md`
3. `docs/PROJECT_ROADMAP.md`
4. `docs/CURRENT_STATUS.md`
5. this file
6. `docs/OBSERVABILITY_AND_INFERENCE_PLAN.md` when changing ventilation, inference, telemetry or ML behavior
7. `docs/SHELLY_POWER_FEEDBACK.md` when changing physical-state supervision

Then fetch fresh `mvp/environment-controller` HEAD, `agent-control:.agent/status/daemon.json`, and the newest terminal Local Agent result. Never continue from remembered chat state alone.

## Current transition

**Stage27C FROZEN -> Stage28A/B/C DONE -> Gates 1-6 COMPLETE -> Gate 7 previously qualified -> AH policy software COMPLETE -> Gate 7 runtime path REOPENED by V5 evidence -> diagnose before more hardware**

The older statement that the next work is to implement moisture-aware ventilation is stale. The absolute-humidity policy is already present at the current product lineage.

At the 2026-09-06 handoff, the product HEAD before docs-only handoff commits was:

`dfc6dc86a47ad2158e36bb0d5241b0153dbce387`

with parent:

`3e2e195898c45734f459ac9a8f69dad9891ab4eb`

Always fetch the fresh work HEAD because documentation commits may now be above that executable identity.

## Latest hardware evidence

Task:

`20260906-growbox-ah-arbiter-clean-v5`

Read:

`.agent/results/20260906-growbox-ah-arbiter-clean-v5.json`

V5 observed a non-safety AH-driven exhaust request at or above the fan ON threshold after the expected minimum-OFF window while the fan remained OFF.

Representative state:

- `requested_fan=0.111`;
- `fan=0`;
- `applied_fan=0.0`;
- `safety=0`;
- `force=0`;
- `safety_reason=0`;
- `arbiter_transitions=0`;
- `tx_errors=0`;
- inside AH about `15.10 g/m3`;
- intake AH about `11.69 g/m3`;
- AH gap about `3.41 g/m3`;
- Shelly about `61.7 W`.

Terminal failure:

`AHV2_PRIMARY_ERROR type=RuntimeError detail=sustained req_fan>=0.10 after min-OFF expiry but fan did not transition ON`

This is now the highest-priority control-path issue.

## Important diagnostic clue

V5 telemetry showed cumulative `arbiter_dwell_holds` values:

`33 -> 43 -> 1 -> 11`

The decrease from 43 to 1 strongly suggests a runtime/arbiter reset or reinitialization and must be investigated before blaming `applyBinary()` directly.

Check:

- board/runtime reset evidence;
- arbiter reconstruction/reinitialization;
- repeated `synchronizeSafeOff()` or `forceSafeOff()` paths;
- monotonic-time discontinuities;
- applied-state reconciliation;
- whether the controller continues calling the exhaust output path after producing the request.

## Latest confirmed recovery state

V5 cleanup passed:

`AHV2_RECOVERY_PASS sha=dfc6dc86a47ad2158e36bb0d5241b0153dbce387 outputs=fake-locked lamp=on fan=off humidifier=off shelly_master=on power_w=61.700 port=/dev/cu.usbserial-1130`

Last confirmed hardware state:

- outputs fake-locked;
- lamp ON;
- fan OFF;
- humidifier OFF;
- Shelly master ON.

## Serial-port invariant

Growbox port:

`/dev/cu.usbserial-1130`

Never touch `/dev/cu.usbserial-10`; it belongs to another project.

## Completed evidence not to repeat by default

- physical RF role identities and ON/OFF routing;
- physical fan efficacy;
- deterministic 28 C thermal trip and 10-minute recovery qualification;
- ventilation identification experiment;
- long 30-minute soak.

The physical fan previously produced approximately:

- AH slope `-0.312 g/m3/min` while ON;
- CO2 slope `-3.09 ppm/min`;
- AH-gradient reduction about `3.27 -> 0.96 g/m3`.

Therefore the current problem is not whether the fan itself works.

## Immediate next work

1. Fetch fresh work HEAD and daemon status.
2. Confirm no active task before editing/queueing.
3. Read V5 terminal result completely.
4. Diagnose the `dwell_holds 43 -> 1` reset/reinitialization clue from source and telemetry.
5. Trace all paths that can reset/reconcile binary actuator state or dwell timing.
6. Add a focused regression reproducing the V5 sequence.
7. Make the smallest evidence-backed product fix.
8. Run focused tests.
9. Run exactly one final full software quality gate once the fix is stable.
10. Only after software PASS run a short bounded exact-SHA hardware confirmation of:

   `AH request -> dwell expiry -> arbiter transition -> RF -> physical fan ON`

11. Use Shelly as independent electrical evidence.
12. End with verified fake-lock recovery and normal RTC/storage restoration.

## Locked safety/policy boundary

- native ESP-IDF only;
- deterministic rule policy authoritative;
- ML shadow/research-only;
- thermal trip `>=28 C`;
- recovery threshold `<=26 C` held continuously for 10 minutes;
- thermal safety may force exhaust immediately;
- no heater/cooler/dehumidifier/CO2 doser;
- real outputs only in explicit bounded tests;
- Shelly master remains ON;
- manual RF TX remains blocked while automatic outputs are real-bounded;
- no unattended real-output operation yet.

## Local Agent / Chat Bridge essentials

Every Growbox task must contain exactly:

`"agent_binding": "815cf40f-8d2a-4e1f-b7cc-c0f4e37b6cb5"`

Use `resources: []` for software/docs/build and `resources: ["board:growbox-s3"]` for USB/serial/flashing/hardware.

Task IDs and payloads are immutable. A retry uses a new ID.

Recommended fresh-chat instruction:

`Continue Growbox from docs/STAGE28D_AH_ARBITER_HANDOFF.md and docs/CONTINUATION_PLAN.md. Fetch fresh work HEAD and Local Agent daemon/result evidence first. V5 reopened the Gate 7 runtime path: diagnose the arbiter_dwell_holds 43 -> 1 discontinuity and state/reset paths before any more hardware testing.`
