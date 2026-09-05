# Fresh-context continuation plan

Updated: 2026-09-05
Work branch: `mvp/environment-controller`
Control branch: `agent-control`
Primary roadmap/handoff: `docs/PROJECT_ROADMAP.md`
Observability contract: `docs/OBSERVABILITY_AND_INFERENCE_PLAN.md`
Shelly power feedback: `docs/SHELLY_POWER_FEEDBACK.md`

## Read first in a new chat

1. `AGENTS.md`
2. `docs/PROJECT_ROADMAP.md`
3. `docs/CURRENT_STATUS.md`
4. this file
5. `docs/OBSERVABILITY_AND_INFERENCE_PLAN.md` when working on physical feedback, ventilation-effect learning, telemetry or ML features
6. stage-specific evidence only when needed

Then fetch fresh `mvp/environment-controller` HEAD and `agent-control:.agent/status/daemon.json`. Never continue from remembered chat state alone.

## Current transition

**Stage27C FROZEN -> Stage28A DONE -> Stage28B DONE -> Stage28C DONE -> pre-Stage28D golden gate COMPLETE -> Stage28D manual RF path COMPLETE -> Gate 1 semantic binding COMPLETE -> Gate 2 lamp safety COMPLETE -> Gate 3 time/profile/observability NEXT**

The service-console firmware `af16aebde8f69d1a1257256c7711e9721c07c9d5` is hardware-qualified for the current manual diagnostic path.

On 2026-09-05 the operator physically confirmed correct ON/OFF response for all three RF loads:

- lamp: `235030016` / `16926208`, 560 us, repeat 10;
- fan: `906118656` / `1040336384`, 575 us, repeat 10;
- humidifier: `637683200` / `771900928`, 560 us, repeat 10.

Do not redo these manual RF identity tests unless new evidence invalidates them.

Gate 2 source contract at `11b02749fd5896e47ec01d03bcca333be2dea810` passed focused tests and the complete software quality gate. The safety controller uses configurable `28.0 C` trip, `26.0 C` recovery threshold and a continuous `10 min` recovery hold. Stale/invalid authoritative temperature fails closed for the lamp path and the fan is forced on when available. Automatic runtime outputs remain fake-locked.

## Current locked boundary

- rule policy authoritative;
- ML shadow/research-only;
- automatic physical outputs fake-locked;
- no unattended real-output control authorized yet;
- manual RF is only an explicit bounded operator-present diagnostic;
- local RF TX completion is transport evidence, not physical load acknowledgement;
- Shelly power feedback may be used as independent supervised physical-state evidence.

## Architecture decision for current loads

- fan RF endpoint -> semantic role `ExhaustFan`;
- humidifier RF endpoint -> semantic role `Humidifier`;
- lamp stays under the lighting schedule/timer for normal operation.

Lamp safety is a separate higher-priority layer:

`schedule/timer -> requested lamp state -> thermal safety override -> physical output`

The current Climate-v6 model receives `schedule.light_level` and the simulator accounts for lamp heat, but lamp is not one of the six ML outputs. Do not add a seventh ML output merely to complete the next hardware gate.

## Shelly physical feedback now available

Shelly Plug S Gen3 is reachable from the Local Agent host at `192.168.0.16` and measures total growbox-strip active power, voltage, current and energy.

Two supervised one-device-at-a-time calibrations now exist. The second used a full `20 s` settling interval after every RF ON and OFF command and nine samples per settled state.

Current observed power contributions:

- lamp: approximately `97.0-97.1 W`;
- exhaust fan: approximately `2.8-3.2 W`;
- humidifier: approximately `15.4-15.7 W`;
- all-three-controlled-loads-OFF baseline: approximately `2.2 W` in the current wiring.

The 20-second repeat ended at the same `2.2 W` baseline with lamp/fan/humidifier OFF and Shelly master ON.

Do not freeze ultra-tight thresholds yet. Continue collecting settled signatures, especially for the low-power fan. Use calibrated ranges plus baseline stability and voltage context.

## Existing-sensor observability track

The project should extract maximum information from hardware already present before adding more sensors. `docs/OBSERVABILITY_AND_INFERENCE_PLAN.md` is the durable contract.

Immediate derived/logged quantities should include:

- dew point, absolute humidity and air VPD from valid T/RH;
- inside-versus-intake temperature and moisture gradients;
- robust `dT/dt`, `dAbsoluteHumidity/dt`, `dCO2/dt` trends;
- actuator transition timestamps and context;
- Shelly power deltas and physical-state confidence;
- clean fan OFF -> ON -> OFF response windows;
- lamp thermal response and humidifier moisture response when other actuators are stable;
- sensor freshness/confidence and confounder flags.

The later ventilation-effect model should learn observed fan effects rather than blindly ventilating. Normal fan control should ask whether exchange is predicted to improve the state, except for hard thermal safety which remains unconditional.

## First incomplete gate — Gate 3

Gate 3 should complete the time/control-profile foundations before real automatic outputs are enabled.

### 3A — RTC and local schedule

1. store UTC in DS3231;
2. add a bounded service-console RTC set/write path with immediate readback;
3. add deterministic Europe/Warsaw CET/CEST conversion, including DST transition tests;
4. run the lighting schedule from local Europe/Warsaw time, target `06:00-22:00` local;
5. keep trusted/untrusted RTC semantics explicit.

### 3B — actual hardware capability contract

Correct runtime capabilities to match physical hardware:

- heater: false;
- cooler: false;
- exhaust fan: true;
- humidifier: true;
- dehumidifier: false;
- CO2 doser: false.

SCD41 CO2 is a real ventilation input, not a dosing/enrichment capability. Inspect the semantics of `targets.co2_enabled`; do not enable a nonexistent CO2 doser merely to make CO2 influence ventilation.

### 3C — observability plumbing while outputs remain fake-locked

Add or prepare deterministic telemetry/features for the measurements described in `docs/OBSERVABILITY_AND_INFERENCE_PLAN.md`. At minimum preserve enough synchronized data to calculate:

- inside/intake moisture gradient;
- environmental slopes before and after fan transitions;
- physical actuator-state evidence from Shelly during supervised host-side/hardware tests;
- confidence/invalid/ambiguous states.

Do not block RTC/safety qualification on a large ML implementation. A clean logging/derived-metric layer is sufficient first; adaptive models remain later work.

### Gate 3 verification

Run focused host tests for time conversion, schedule boundaries, capability contract and new pure derived-metric helpers, then exactly one final full quality gate. No real automatic RF TX in this software gate.

## Next hardware session after Gate 3 software qualification

When the software slice passes its focused/full build gate:

1. flash the exact qualified firmware and verify SHA, sensors, RTC, RF readiness and `outputs=fake-locked` before actuation;
2. set/read back DS3231 UTC and verify Europe/Warsaw local schedule interpretation;
3. run one bounded physical role-routing test per endpoint, each ending OFF;
4. use Shelly power signatures as independent physical feedback in addition to RF TX evidence;
5. test the lamp thermal override using deterministic injected/simulated over-temperature rather than deliberately overheating the growbox;
6. physically verify lamp forced OFF and fan forced ON under that injected condition;
7. verify `26 C` / 10-minute recovery hysteresis behavior;
8. collect bounded fan OFF -> ON -> OFF T/RH/CO2 response data with Xiaomi intake context to establish the first ventilation-effect observations;
9. run a short supervised real-sensor closed-loop session;
10. only after all supervised gates pass, propose a separate unattended real-output soak for explicit operator approval.

## Local Agent / Chat Bridge essentials

Hard binding for every Growbox task:

`"agent_binding": "815cf40f-8d2a-4e1f-b7cc-c0f4e37b6cb5"`

Use `resources: []` for software/docs/build and `resources: ["board:growbox-s3"]` for USB/serial/flashing/hardware. Task IDs and payloads are immutable. `agent-control` holds task/run/result/status state; product/source changes belong on `mvp/environment-controller`.

Chat Bridge only transports wakeups and pins repository identity. Local Agent deterministically executes queued tasks. ChatGPT remains the planner and must inspect terminal result evidence before claiming completion.

Recommended first message in the fresh chat:

`Continue Growbox from docs/PROJECT_ROADMAP.md and docs/CONTINUATION_PLAN.md. Verify fresh work-branch HEAD and Local Agent daemon first. Start from the first incomplete gate. Keep real automatic outputs fake-locked until the roadmap reaches a supervised hardware gate.`
