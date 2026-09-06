# Current controller status

Updated: 2026-09-06
Development branch: `mvp/environment-controller`
Latest handoff: `docs/STAGE28D_AH_ARBITER_HANDOFF.md`
Primary roadmap: `docs/PROJECT_ROADMAP.md`
Continuation checklist: `docs/CONTINUATION_PLAN.md`
Observability contract: `docs/OBSERVABILITY_AND_INFERENCE_PLAN.md`
Shelly feedback reference: `docs/SHELLY_POWER_FEEDBACK.md`

## Current transition

**Stage27C FROZEN -> Stage28A/B/C DONE -> Gates 1-6 COMPLETE -> Gate 7 previously qualified -> absolute-humidity ventilation software COMPLETE -> Gate 7 runtime path REOPENED by V5 evidence**

The current priority is no longer implementing moisture-aware ventilation. That slice is already present. The immediate task is to diagnose why a valid non-safety fan request did not produce a binary transition after the expected dwell window.

## Current source identity

At the 2026-09-06 handoff, the executable product HEAD before docs-only handoff updates was:

`dfc6dc86a47ad2158e36bb0d5241b0153dbce387`

Commit: `Refresh climate replay fixture for AH policy`

Parent:

`3e2e195898c45734f459ac9a8f69dad9891ab4eb`

Commit: `Align Python ventilation policy with absolute humidity`

Always fetch the fresh work-branch HEAD before making changes because documentation commits may now be above this executable identity.

## Latest physical control-path evidence

Task:

`20260906-growbox-ah-arbiter-clean-v5`

Exact terminal result:

`.agent/results/20260906-growbox-ah-arbiter-clean-v5.json`

Representative V5 non-safety state:

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
- TP357 about `26.0 C / 62%`;
- Xiaomi about `24.46 C / 52.35%`;
- Shelly about `61.7 W`.

The test terminated with:

`AHV2_PRIMARY_ERROR type=RuntimeError detail=sustained req_fan>=0.10 after min-OFF expiry but fan did not transition ON`

This is currently treated as strong evidence of a real runtime/control-path defect or unintended state reset. It is not classified as the earlier BLE/startup harness problem.

## Critical V5 clue: arbiter state appears to reset

Successive V5 samples reported cumulative `arbiter_dwell_holds` values:

`33 -> 43 -> 1 -> 11`

A cumulative counter should not decrease in one uninterrupted runtime instance.

Therefore the next diagnosis must first investigate:

- board/runtime reboot or restart;
- arbiter object/state recreation;
- repeated `synchronizeSafeOff()` or `forceSafeOff()` behavior;
- monotonic-time discontinuity;
- controller/applied-state reconciliation resetting the OFF dwell clock;
- missing subsequent exhaust apply calls.

Do not assume `Stage28dBinaryRoleArbiter::applyBinary()` itself is the root cause until these reset/reinitialization paths are excluded.

## Latest safe hardware state

V5 recovery passed:

`AHV2_RECOVERY_PASS sha=dfc6dc86a47ad2158e36bb0d5241b0153dbce387 outputs=fake-locked lamp=on fan=off humidifier=off shelly_master=on power_w=61.700 port=/dev/cu.usbserial-1130`

Last confirmed state:

- exact executable SHA `dfc6dc86...`;
- outputs fake-locked;
- lamp ON;
- fan OFF;
- humidifier OFF;
- Shelly master ON.

## Serial-port invariant

Correct Growbox/CrowPanel serial port:

`/dev/cu.usbserial-1130`

Never open, probe, monitor, flash or otherwise touch:

`/dev/cu.usbserial-10`

That port belongs to another project.

## Completed platform and physical evidence

### Native input/runtime baseline

- ESP-IDF native implementation remains the product direction.
- TP357 BLE, Xiaomi intake BLE, SCD41 and DS3231 paths are established.
- Rule controller remains authoritative.
- ML remains shadow/research-only.

### RF role routing

Frozen physical identities remain:

- fan / endpoint 1: ON `906118656`, OFF `1040336384`, protocol 2, 32 bit, 575 us, repeat 10;
- lamp / endpoint 2: ON `235030016`, OFF `16926208`, protocol 2, 32 bit, 560 us, repeat 10;
- humidifier / endpoint 3: ON `637683200`, OFF `771900928`, protocol 2, 32 bit, 560 us, repeat 10.

These role mappings have already been physically verified.

### Thermal safety

Do not repeat the long deterministic thermal sequence unless safety code changes.

Frozen behavior:

- trip `>=28.0 C`;
- lamp forced OFF on trip;
- exhaust may be forced ON immediately;
- recovery threshold `<=26.0 C`;
- continuous recovery hold 10 minutes;
- stale/invalid authoritative TP357 temperature fails closed for the lamp path.

### Ventilation efficacy

A previous physical fan OFF -> ON -> OFF experiment established approximately:

- inside AH slope while fan ON: `-0.312 g/m3/min`;
- inside CO2 slope while fan ON: `-3.09 ppm/min`;
- AH gradient reduction: `3.27 -> 0.96 g/m3`.

The current issue is therefore not whether the physical fan itself works.

## Binary arbiter architecture under investigation

Control chain:

`rule request -> Stage28dBinaryRoleArbiter -> confirmed actual applied -> RF endpoint -> telemetry`

Default settings:

- exhaust ON threshold `0.10`;
- exhaust OFF threshold `0.03`;
- exhaust min ON/OFF `120 s`;
- humidifier min ON/OFF `180 s`;
- thermal safety may bypass fan min-OFF to force immediate ON;
- emergency safe OFF bypasses dwell;
- failed RF transitions must not advance internal state.

This architecture was previously qualified, but V5 is newer contradictory runtime evidence and reopens the path until diagnosed.

## Immediate next work

1. Fetch fresh work HEAD and Local Agent daemon status.
2. Confirm no active task.
3. Read V5 terminal result completely.
4. Trace runtime reset/reinitialization and all binary-state reset paths.
5. Inspect exact source around:
   - `Stage28dBinaryRoleArbiter`;
   - `ClimateV6RealInputRuntime`;
   - application/controller output dispatch;
   - safe-off and state-reconciliation paths;
   - reset-reason/telemetry reporting.
6. Add a focused regression reproducing the V5 request/dwell sequence and protecting against unintended state reset.
7. Make the smallest evidence-backed fix.
8. Run focused tests.
9. Run exactly one final full software gate after the fix is stable.
10. Only then perform a short bounded exact-SHA physical confirmation of:

   `AH request -> dwell expiry -> arbiter transition -> RF -> physical fan ON`

11. Use Shelly as independent electrical evidence.
12. End with verified fake-lock recovery and normal RTC/storage restoration.

## Locked policy and safety boundary

- native ESP-IDF only;
- rule controller authoritative;
- ML shadow/research-only;
- no heater/cooler/dehumidifier/CO2 doser;
- real outputs only in explicit bounded tests;
- Shelly master stays ON;
- lamp may be switched as required by a bounded test;
- manual RF remains blocked while automatic outputs are real-bounded;
- no unattended real-output mode yet;
- do not repeat long completed physical gates without a new code change or explicit hypothesis.
