# Growbox ML project roadmap and chat handoff

Updated: 2026-09-06
Repository: `MichalMatu/growbox-ml-controller`
Work branch: `mvp/environment-controller`
Control branch: `agent-control`
Local Agent repository id: `growbox-ml-controller`
Agent binding: `815cf40f-8d2a-4e1f-b7cc-c0f4e37b6cb5`
Latest focused handoff: `docs/STAGE28D_AH_ARBITER_HANDOFF.md`

## Source-of-truth order

For a fresh chat, read:

1. `AGENTS.md`
2. `docs/STAGE28D_AH_ARBITER_HANDOFF.md`
3. `docs/PROJECT_ROADMAP.md`
4. `docs/CURRENT_STATUS.md`
5. `docs/CONTINUATION_PLAN.md`
6. `docs/OBSERVABILITY_AND_INFERENCE_PLAN.md`
7. `docs/SHELLY_POWER_FEEDBACK.md`
8. older stage-specific handoffs only when needed

Then fetch fresh `mvp/environment-controller` HEAD, `agent-control:.agent/status/daemon.json`, and the latest terminal Local Agent result. Never continue from remembered chat state alone.

## Project direction

The project is a native ESP-IDF growbox environmental controller using real sensors, local RF433 actuators, deterministic safety, telemetry/logging and a shadow ML path.

Frozen policy boundary:

- deterministic rule policy is authoritative;
- ML remains shadow/research-only;
- native ESP-IDF only;
- installed firmware returns to fake-locked after every bounded physical qualification;
- real outputs are allowed only inside explicit bounded test/qualification tasks;
- RF TX completion is transport evidence, not physical-load acknowledgement;
- Shelly power is independent electrical evidence;
- environmental response is required before claiming actual airflow/moisture effect;
- unattended real-output operation is not yet authorized.

## Completed platform milestones

### Stage27C - real-input native ESP-IDF baseline - FROZEN

Real SCD41, DS3231 and BLE inputs, storage telemetry and fake-locked output behavior are established.

### Stage28A - RF433 codec/classification - DONE

Native protocol-2 RF433 codec and temporal classification established.

### Stage28B - ESP-IDF RMT TX/RX - DONE

Native RMT transport and loopback qualified.

### Stage28C - physical RF identity - DONE/FROZEN

Frozen devices:

| role/load | ON | OFF | profile |
| --- | ---: | ---: | --- |
| fan / endpoint 1 | 906118656 | 1040336384 | protocol 2, 32 bit, 575 us, repeat 10 |
| lamp / endpoint 2 | 235030016 | 16926208 | protocol 2, 32 bit, 560 us, repeat 10 |
| humidifier / endpoint 3 | 637683200 | 771900928 | protocol 2, 32 bit, 560 us, repeat 10 |

### Gates 1-6 - COMPLETE

The following remain accepted and should not be re-run by default:

- semantic output binding;
- lamp timer and deterministic thermal safety;
- RTC/time/profile/observability;
- exact-SHA read-only hardware smoke;
- physical RF role routing;
- deterministic physical thermal safety.

Thermal safety remains:

- trip `>=28 C`;
- recovery threshold `<=26 C`;
- 10-minute continuous recovery hold;
- safety may immediately force exhaust ON;
- stale/invalid authoritative TP357 temperature fails closed for the lamp path.

## Ventilation identification - COMPLETE

A physical fan OFF -> ON -> OFF experiment established that the fan is effective:

- inside absolute humidity slope about `-0.312 g/m3/min` while fan ON;
- inside CO2 slope about `-3.09 ppm/min`;
- inside-minus-intake AH gradient reduced approximately `3.27 -> 0.96 g/m3`;
- temperature effect was small.

Control principle:

**moisture-exchange decisions use absolute humidity/moisture content, not raw RH alone.**

Outside CO2 is not measured; do not invent outdoor ppm.

## Absolute-humidity ventilation policy - SOFTWARE COMPLETE

The previous roadmap item to replace mixed raw-RH ventilation logic is now complete in the current product lineage.

At the 2026-09-06 handoff, executable HEAD before docs-only updates was:

`dfc6dc86a47ad2158e36bb0d5241b0153dbce387`

Commit: `Refresh climate replay fixture for AH policy`

Parent:

`3e2e195898c45734f459ac9a8f69dad9891ab4eb`

Commit: `Align Python ventilation policy with absolute humidity`

Do not restart that policy implementation from older text.

## Gate 7 - binary/dwell arbitration - REOPENED BY NEWER V5 EVIDENCE

Gate 7 had previously been treated as complete after earlier closed-loop and bounded-soak evidence. That historical evidence remains useful, but it is no longer sufficient to close the runtime path because a newer exact-SHA test produced contradictory evidence.

Architecture under investigation:

`rule request -> Stage28dBinaryRoleArbiter -> confirmed actual applied -> RF endpoint -> telemetry`

Default arbiter settings remain:

- exhaust ON threshold `0.10`;
- exhaust OFF threshold `0.03`;
- exhaust min ON/OFF `120 s`;
- humidifier min ON/OFF `180 s`;
- thermal safety may bypass exhaust min-OFF for immediate ON;
- emergency safe OFF bypasses dwell;
- failed RF transition must not advance arbiter state.

### Latest V5 evidence

Task:

`20260906-growbox-ah-arbiter-clean-v5`

Read:

`.agent/results/20260906-growbox-ah-arbiter-clean-v5.json`

Representative non-safety state:

- `requested_fan=0.111`;
- `fan=0`;
- `applied_fan=0.0`;
- `safety=0`;
- `force=0`;
- `safety_reason=0`;
- `arbiter_transitions=0`;
- `tx_errors=0`;
- AH gap about `3.41 g/m3`;
- Shelly about `61.7 W`.

Terminal result:

`AHV2_PRIMARY_ERROR type=RuntimeError detail=sustained req_fan>=0.10 after min-OFF expiry but fan did not transition ON`

This is current priority evidence.

### Strong reset/reinitialization clue

Across successive V5 AH-window samples the cumulative `arbiter_dwell_holds` values were:

`33 -> 43 -> 1 -> 11`

Because a cumulative counter should not decrease inside one uninterrupted runtime, the first diagnosis must investigate reset/reinitialization rather than immediately blaming the threshold comparison itself.

Primary hypotheses:

- board/runtime reboot;
- arbiter recreation/reinitialization;
- repeated `synchronizeSafeOff()` / safe-off state reset;
- monotonic-time discontinuity;
- reconciliation path resetting OFF dwell timing;
- controller output path ceasing/restarting after generating a fan request;
- only after excluding these, a direct `applyBinary()` defect.

## Latest confirmed hardware cleanup

V5 recovery passed:

`AHV2_RECOVERY_PASS sha=dfc6dc86a47ad2158e36bb0d5241b0153dbce387 outputs=fake-locked lamp=on fan=off humidifier=off shelly_master=on power_w=61.700 port=/dev/cu.usbserial-1130`

Last confirmed state:

- outputs fake-locked;
- lamp ON;
- fan OFF;
- humidifier OFF;
- Shelly master ON.

## Serial-port invariant

Correct Growbox port:

`/dev/cu.usbserial-1130`

Never use `/dev/cu.usbserial-10`; it belongs to another project.

## Current highest-priority roadmap item

### Stage28D runtime-state / arbiter defect diagnosis

1. Fetch fresh work HEAD and Local Agent daemon/result evidence.
2. Read V5 result completely.
3. Diagnose the `arbiter_dwell_holds 43 -> 1` discontinuity.
4. Trace all state-reset/reconciliation/time paths around the binary arbiter.
5. Add a focused regression that reproduces the V5 sequence.
6. Make the smallest evidence-backed fix.
7. Run focused tests.
8. Run exactly one final full software quality gate after the fix stabilizes.
9. Only after software PASS run a short bounded exact-SHA hardware confirmation:

   `AH request -> dwell expiry -> arbiter transition -> RF -> physical fan ON`

10. Verify independently with Shelly power evidence and zero RF TX errors.
11. Finish with verified safe fake-lock recovery and restore normal RTC/storage.

Do not start with another long physical soak.

## Local Agent / Chat Bridge contract

Every Growbox task must contain exactly:

`"agent_binding": "815cf40f-8d2a-4e1f-b7cc-c0f4e37b6cb5"`

Use:

- `resources: []` for software/docs/build;
- `resources: ["board:growbox-s3"]` for USB/serial/flashing/hardware.

Task IDs and payloads are immutable. Retry with a new ID. Product/source changes belong on the work branch; `agent-control` is execution/control evidence only.

## Fresh-chat bootstrap

A fresh chat should:

1. honor the exact Bridge binding envelope;
2. read `AGENTS.md` and `docs/STAGE28D_AH_ARBITER_HANDOFF.md` first;
3. read this roadmap, `CURRENT_STATUS` and `CONTINUATION_PLAN`;
4. fetch fresh work HEAD and daemon/result evidence;
5. treat the AH policy as already implemented;
6. treat V5 as newer evidence reopening the Gate 7 runtime path;
7. diagnose reset/reinitialization before more hardware testing;
8. keep ML shadow-only and all safety invariants unchanged.
