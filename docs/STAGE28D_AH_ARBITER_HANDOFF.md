# Stage28D AH / binary-arbiter handoff

Updated: 2026-09-06
Repository: `MichalMatu/growbox-ml-controller`
Work branch: `mvp/environment-controller`
Control branch: `agent-control`
Agent binding: `815cf40f-8d2a-4e1f-b7cc-c0f4e37b6cb5`

This is the latest fresh-chat handoff and overrides older statements that Gate 7 binary/dwell arbitration is fully closed. Read it together with `AGENTS.md`, `docs/PROJECT_ROADMAP.md`, `docs/CURRENT_STATUS.md`, and `docs/CONTINUATION_PLAN.md`.

## Fresh source identity

At handoff time the product branch HEAD was:

`dfc6dc86a47ad2158e36bb0d5241b0153dbce387`

Commit: `Refresh climate replay fixture for AH policy`

Parent:

`3e2e195898c45734f459ac9a8f69dad9891ab4eb`

Commit: `Align Python ventilation policy with absolute humidity`

The absolute-humidity ventilation policy software slice and its replay fixture are already present at this HEAD. Do not restart that implementation slice from the older roadmap text.

Always fetch fresh branch HEAD before continuing.

## Local Agent contract

Hard binding is immutable for this repository:

`"agent_binding": "815cf40f-8d2a-4e1f-b7cc-c0f4e37b6cb5"`

Use:

- `resources: []` for software-only work;
- `resources: ["board:growbox-s3"]` for serial, flashing or hardware work.

Before editing or queueing a task, read fresh `agent-control:.agent/status/daemon.json` and ensure there is no active task touching the same branch/resource.

At handoff the worker was idle and on Local Agent 4.18.4, but the next chat must fetch fresh daemon evidence rather than trusting this remembered version.

## Serial-port invariant

Correct Growbox/CrowPanel port:

`/dev/cu.usbserial-1130`

`/dev/cu.usbserial-10` belongs to another project.

Never open, probe, monitor, flash or otherwise touch `/dev/cu.usbserial-10` for Growbox work.

## Safety state after the latest physical test

Latest recovery marker from task `20260906-growbox-ah-arbiter-clean-v5`:

`AHV2_RECOVERY_PASS sha=dfc6dc86a47ad2158e36bb0d5241b0153dbce387 outputs=fake-locked lamp=on fan=off humidifier=off shelly_master=on power_w=61.700 port=/dev/cu.usbserial-1130`

Therefore the last confirmed hardware state was:

- exact SHA `dfc6dc86...`;
- outputs `fake-locked`;
- lamp ON;
- fan OFF;
- humidifier OFF;
- Shelly master ON;
- about 61.7 W total power.

Do not claim a later hardware state without fresh evidence.

## What is already proven and should not be repeated by default

- Native ESP-IDF sensor/runtime baseline is established.
- TP357, Xiaomi intake sensor, SCD41 and DS3231 paths are working.
- RF433 identities for lamp, fan and humidifier are frozen and physically verified.
- The physical fan works and changes the environment.
- Ventilation identification previously measured approximately:
  - inside AH slope while fan ON: `-0.312 g/m3/min`;
  - inside CO2 slope while fan ON: `-3.09 ppm/min`;
  - AH gradient reduction approximately `3.27 -> 0.96 g/m3`.
- Thermal safety behavior is already physically qualified:
  - trip `>=28 C`;
  - recovery threshold `<=26 C`;
  - continuous recovery hold 10 minutes;
  - thermal safety may immediately force exhaust ON.
- Rule policy remains authoritative.
- ML remains shadow/research-only.
- Do not repeat the long Gate 6 thermal sequence unless safety code changes.
- Do not repeat a 30-minute soak without a new specific hypothesis.

## Startup-safety finding

`LampSafetyReason` mapping on `dfc6dc86...` is:

- 0 Safe
- 1 TimerOff
- 2 TemperatureUnavailable
- 3 OverTemperature
- 4 RecoveryHold
- 5 InvalidConfig

A fresh boot may enter `TemperatureUnavailable` before the first authoritative BLE TP357 sample, then hold `RecoveryHold` for 10 minutes if the temperature is already below the recovery threshold. This can force fan ON and lamp OFF at startup.

However, startup safety is not guaranteed to appear on every test boot: if a fresh TP357 sample is available early enough, the runtime may start directly in `safety=0` / `force=0`.

Physical harnesses must accept both legal startup cases.

## V2-V4 harness lessons

Earlier AH/arbiter hardware tests V2-V4 failed for harness reasons, not product reasons:

- V2 required both BLE sensors immediately after flash and failed during the normal BLE startup gap.
- V3 tolerated missing sensors only while safety was active, but still required TP357 and Xiaomi in the same service-console sample after safety cleared.
- V4 correctly accumulated asynchronous BLE samples, but incorrectly required observing `RecoveryHold`; that boot started directly safe.

V4 produced useful non-safety evidence before the harness failure:

- `safety=0`, `force=0`;
- lamp ON, fan OFF;
- `requested_fan=0.611`;
- `arbiter_dwell_holds=21`;
- `arbiter_transitions=0`;
- `tx_errors=0`;
- Shelly about 61.7 W.

## Latest decisive test: V5

Task:

`20260906-growbox-ah-arbiter-clean-v5`

Read the exact terminal result first:

`.agent/results/20260906-growbox-ah-arbiter-clean-v5.json`

V5 fixed the known harness defects and accepted either startup RecoveryHold or a direct-safe startup.

Key observed non-safety samples included:

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

The harness recorded the request above the fan ON threshold after the expected minimum-OFF window and terminated with:

`AHV2_PRIMARY_ERROR type=RuntimeError detail=sustained req_fan>=0.10 after min-OFF expiry but fan did not transition ON`

This is strong evidence of a real runtime/control-path defect or state-reset defect and must not be dismissed as the previous BLE/startup harness issue without new evidence.

## Important additional clue from V5

The cumulative telemetry field `arbiter_dwell_holds` was observed across successive AH-window samples as:

`33 -> 43 -> 1 -> 11`

A cumulative counter should not normally decrease inside one uninterrupted runtime instance.

Therefore do **not** jump directly to the conclusion that `Stage28dBinaryRoleArbiter::applyBinary()` itself is wrong. First determine whether the runtime, board, arbiter object or telemetry state was reset/reinitialized between those samples.

Primary diagnostic hypotheses now include:

1. board/runtime reset or restart during the V5 window;
2. arbiter object/state being recreated or synchronized/reset unexpectedly;
3. monotonic-time discontinuity or incorrect timestamp propagation;
4. a repeated safe-off/reconciliation path resetting the OFF dwell clock;
5. the controller/application no longer invoking the exhaust apply path as expected after the request is generated;
6. only after excluding the above, a defect in `applyBinary()` dwell/threshold logic itself.

Treat these as hypotheses, not conclusions.

## Code inspection starting point

Inspect exact `dfc6dc86...` versions of:

- `src/climate/Stage28dBinaryRoleArbiter.cpp`
- `src/climate/Stage28dBinaryRoleArbiter.h`
- `src/climate/ClimateV6RealInputRuntime.cpp`
- `src/climate/ClimateApplication.*`
- runtime controller/output reconciliation code reached by the exhaust request
- RF endpoint safe-state paths
- telemetry/reset-reason reporting

Current arbiter defaults:

- fan ON threshold `0.10`;
- fan OFF threshold `0.03`;
- fan minimum ON `120000 ms`;
- fan minimum OFF `120000 ms`;
- humidifier minimum ON/OFF `180000 ms`.

`Stage28dBinaryRoleArbiter::synchronizeSafeOff(monotonic_ms)` truthfully starts fan/humidifier known OFF after the physical endpoint has been initialized safe.

`applyBinary()` should transition an OFF fan ON after `min_off_ms` when the normalized request remains at or above `on_threshold`, unless another valid path resets the state/timer or prevents the apply call.

## Immediate next work

Do not start with another hardware run.

1. Fetch fresh product HEAD and daemon status.
2. Read V5 terminal result completely.
3. Audit reset/reinitialization evidence first, especially the `dwell_holds 43 -> 1` discontinuity.
4. Trace every path that can:
   - call `forceSafeOff()`;
   - call `synchronizeSafeOff()`;
   - recreate/reinitialize the arbiter;
   - restart the runtime/controller;
   - reset/reconcile applied actuator state;
   - change monotonic timing assumptions.
5. Add a focused host/runtime regression that reproduces the exact V5 request/dwell/state sequence, including protection against unintended state reset.
6. Make the smallest product fix supported by evidence.
7. Run focused tests.
8. Run exactly one final full software quality gate after the fix is stable.
9. Only then perform a short bounded exact-SHA hardware confirmation of:

   `AH request -> dwell expiry -> arbiter transition -> RF -> physical fan ON`

10. Use independent Shelly power evidence and zero RF TX errors.
11. Finish with safe exact-SHA fake-lock recovery and restore normal RTC/storage.

## Physical-output rules

- Shelly master stays ON.
- Lamp may be switched ON/OFF when a bounded test requires it.
- Manual service-console RF TX is intentionally blocked while automatic outputs are `real-bounded`; do not bypass this safety rule.
- Every physical run must be bounded and fail closed.
- Always inspect the recovery marker before reporting a hardware test complete.

## Fresh-chat instruction

A new chat should begin with:

`Read AGENTS.md, docs/STAGE28D_AH_ARBITER_HANDOFF.md, docs/PROJECT_ROADMAP.md, docs/CURRENT_STATUS.md and docs/CONTINUATION_PLAN.md. Fetch fresh mvp/environment-controller HEAD and agent-control daemon/result evidence. Treat V5 as the newest control-path evidence, with special attention to the arbiter_dwell_holds 43 -> 1 discontinuity. Diagnose reset/reinitialization before running more hardware.`
