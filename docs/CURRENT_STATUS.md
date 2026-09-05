# Current controller status

Updated: 2026-09-05
Development branch: `mvp/environment-controller`
Primary roadmap/handoff: `docs/PROJECT_ROADMAP.md`
Observability contract: `docs/OBSERVABILITY_AND_INFERENCE_PLAN.md`
Shelly feedback reference: `docs/SHELLY_POWER_FEEDBACK.md`

## Current transition

**Stage27C FROZEN -> Stage28A DONE -> Stage28B DONE -> Stage28C DONE -> pre-Stage28D golden gate COMPLETE -> Stage28D manual RF path COMPLETE -> Gate 1 semantic binding COMPLETE -> Gate 2 lamp safety COMPLETE -> Gate 3 time/profile/observability NEXT**

Stage27C and the completed RF transport/identity work are not being reopened.

## Current safety state

- Rule policy remains authoritative.
- ML remains shadow/research-only.
- Automatic physical outputs remain fake-locked.
- Manual RF service commands are an explicit bounded diagnostic path.
- Local TX completion / `SelfTx` is not physical socket/load acknowledgement.
- Shelly power feedback is available as an independent supervised physical-state signal.
- No unattended real-output gate is open yet.

## Hardware-qualified identities

Golden pre-Stage28D firmware/source:

`316b58e76de609069ddbf2667fe86f6218fb2143`

This SHA passed the complete software gate and strict 5400-second real-hardware soak with real sensors/RTC/BLE/SD and fake-locked outputs.

Hardware-qualified Stage28D service-console firmware:

`af16aebde8f69d1a1257256c7711e9721c07c9d5`

The service console uses the primary UART driver and provides `help`, `status`, `sensors`, `rf list`, named manual RF ON/OFF commands and bounded `rf rx` capture.

Later documentation-only branch commits must not be described as separately hardware-tested firmware identities.

## Gate 2 lamp thermal safety — COMPLETE

The source contract at:

`11b02749fd5896e47ec01d03bcca333be2dea810`

passed focused verification and the complete software quality gate:

- Python: `479 passed`, `3 skipped`, `9 deselected`;
- host C++: `20/20` passed, including `stage28d_lamp_safety_tests`;
- clang-tidy passed;
- ESP-IDF build/pre-push quality gate passed;
- automatic outputs remained fake-locked and no RF TX was performed by the verification task.

Frozen safety behavior:

- trip at `28.0 C` -> lamp forced OFF;
- fan forced ON when available;
- recovery threshold `<=26.0 C`;
- temperature must remain at/below recovery threshold continuously for `10 min` before latch clear;
- recovery hold resets if temperature rises above `26.0 C`;
- stale/invalid/non-finite authoritative TP357 temperature fails closed for the lamp path;
- schedule OFF always remains lamp OFF.

## RF433 physical validation — COMPLETE

On 2026-09-05 the operator physically observed correct ESP-to-socket ON/OFF behavior for all three current RF loads.

| device | ON decimal | OFF decimal | protocol | qualified TX profile | physical result |
| --- | ---: | ---: | --- | --- | --- |
| lamp | 235030016 | 16926208 | 2 / 32 bit | 560 us, repeat 10 | PASS |
| fan / `remote_socket_1` | 906118656 | 1040336384 | 2 / 32 bit | 575 us, repeat 10 | PASS |
| humidifier | 637683200 | 771900928 | 2 / 32 bit | 560 us, repeat 10 | PASS |

The permanent code/evidence register is `docs/RF433_DEVICE_CODES.md`.

The manual tests ended with OFF commands and automatic runtime outputs remained fake-locked.

## Current RF transport contract

- TX/codec resolution: `100 kHz`;
- RX resolution: `100 kHz`;
- RX minimum signal: `10 us`;
- RX idle/max signal: `20 ms`;
- TX GPIO: `8`;
- RX GPIO: `14`;
- raw RX capacity: `256` symbols;
- self-TX guard: `50 ms`.

Do not restore the older Stage28B receive settings without new physical evidence.

## Shelly power feedback — AVAILABLE AND CALIBRATED

A Shelly Plug S Gen3 is reachable from the Local Agent host at:

`192.168.0.16`

It exposes relay state plus active power, voltage, current, accumulated energy and internal temperature through local RPC. It is currently useful as an independent measurement upstream of the growbox power strip and as a separately gated emergency master switch.

Two supervised RF/power calibrations were completed. The second waited `20 s` after every ON and OFF transition and used nine Shelly samples per settled state.

Current observed settled signatures:

- all controlled loads OFF baseline: about `2.2 W`;
- lamp contribution: about `97.0-97.1 W`;
- exhaust-fan contribution: about `2.8-3.2 W`;
- humidifier contribution: about `15.4-15.7 W`.

The 20-second repeat ended at `2.2 W` baseline with lamp OFF, fan OFF, humidifier OFF and Shelly master ON.

Use these as reference centers/ranges, not exact production constants. Continue collecting settled signatures and voltage context, especially for the low-power fan.

The feedback contract is:

`requested state -> RF TX -> settle -> Shelly power delta -> physical-state confidence/anomaly`

Shelly does not replace environmental confirmation: electrical fan power does not itself prove airflow, humidifier power does not prove mist output, and lamp electrical power does not directly prove optical output. Combine electrical and environmental response when possible.

## Stage28 reference test rig — sensor placement

The following physical arrangement is the frozen reference layout for the current mint growbox tests. Keep sensor positions stable during qualification and data collection unless a later experiment explicitly records a topology change.

| sensor | physical placement | authoritative role | secondary role |
| --- | --- | --- | --- |
| TP357 BLE thermo/hygrometer | inside the growbox, slightly above the leaf canopy | primary inside temperature and relative humidity | primary thermal-safety temperature source |
| SCD41 | inside the growbox, approximately at pot height | primary inside CO2 | backup/diagnostic temperature and relative humidity |
| Xiaomi BLE thermo/hygrometer | outside the growbox, next to the air intake | incoming/outside temperature and relative humidity | ventilation-effectiveness context |
| DS3231 | controller installation | UTC RTC/timebase | Europe/Warsaw lighting schedule source after conversion |

SCD41 installation note: the sensor is soldered to the HAT through approximately 5 cm leads, and the HAT itself is physically spaced from the ESP32-S3. Conductive heat transfer from the ESP32 into the SCD41 is therefore expected to be small in this test rig. Even so, SCD41 temperature/RH remain diagnostic/backup values rather than the authoritative inside T/RH source; TP357 remains authoritative for those channels.

This topology intentionally gives the controller three different pieces of environmental context: growbox canopy conditions, growbox CO2/pot-height conditions, and the temperature/RH of the air available at the intake.

## Current mint control baseline

The current software-safety baseline for the mint test rig is:

- exhaust fan is a binary actuator only: `OFF` or `ON`; no PWM/duty-cycle control is assumed;
- TP357 inside temperature is the primary thermal-safety measurement;
- lamp thermal cutoff: `28.0 C` -> force lamp OFF regardless of the lighting timer and request exhaust fan ON;
- recovery: `<=26.0 C` continuously for `10 min` before lamp safety latch clears;
- nominal relative-humidity target: about `60% RH`, with an initial normal band of approximately `55-65% RH`;
- high humidity around `70% RH` and above should be treated as a ventilation/dehumidification condition only when intake-air conditions or learned fan response indicate ventilation is beneficial;
- normal light request remains schedule-driven and independent from the six Climate-v6 ML outputs;
- SCD41 CO2 is a real ventilation input, but there is no CO2 dosing/enrichment hardware.

Automatic physical outputs remain fake-locked until the corresponding software and supervised hardware gates pass.

## Ventilation-effect inference — important control/learning principle

The exhaust fan must not be treated as a generic periodic actuator. Outside of hard safety overrides, it should be requested only when the controller predicts that exchanging air will improve the current state.

The reference sensor topology supports this directly:

- TP357 gives authoritative inside temperature/RH near the canopy;
- Xiaomi gives intake-air temperature/RH immediately outside the growbox;
- SCD41 gives inside CO2, while outside CO2 is not measured directly.

For temperature and humidity the controller can compare inside values with intake values before ventilation and then measure the actual response after `fan ON`. Prefer absolute-humidity/moisture-content comparison over raw RH because RH changes strongly with temperature.

For CO2, fan response provides indirect information about effective outside/intake CO2. If inside CO2 rises after a controlled `fan OFF -> fan ON` transition, incoming air is effectively supplying more CO2 than the current growbox state; if it falls, incoming air is effectively lower in CO2. Initially record the observable `delta CO2/min` effect rather than a falsely precise outside-CO2 concentration.

Use baseline OFF slopes and compare them with ON slopes so ongoing plant uptake/respiration is partially separated from the fan effect:

`fan_effect ~= slope_ON - slope_OFF_baseline`

The durable detailed contract is `docs/OBSERVABILITY_AND_INFERENCE_PLAN.md`.

## Existing-sensor observability plan

Before adding hardware, extract more information from sensors already installed. Record/derive at least:

- dew point;
- absolute humidity;
- air VPD;
- inside/intake temperature and moisture gradients;
- robust `dT/dt`, `dAbsoluteHumidity/dt`, `dCO2/dt` slopes;
- response delays/time constants after actuator transitions;
- lamp thermal contribution;
- humidifier moisture contribution;
- fan cooling/drying/CO2-exchange effects;
- Shelly power signatures and physical-state confidence;
- sensor freshness, disagreement and confounder flags.

Later useful quantities include time-to-target, time-to-safety-limit, actuator degradation and energy used per useful climate correction. These are strong ML features because they describe measured plant/environment/hardware response rather than only controller requests.

Hard deterministic safety remains higher priority than every learned/inferred effect.

## Frozen actuator semantics

- `remote_socket_1` / endpoint 1 -> `ExhaustFan`;
- `remote_socket_3` / endpoint 3 -> `Humidifier`;
- `remote_socket_2` / endpoint 2 -> dedicated scheduled-light path, not a normal Climate-v6 ML output.

The Gate 1 validator fails closed for missing, duplicate, unknown, stale or scheduled-light-as-climate bindings. Automatic runtime outputs remain fake-locked.

The lamp is a special layered actuator:

`schedule/timer -> requested lamp state -> thermal safety override -> physical lamp output`

Climate-v6 already consumes `schedule.light_level`, and the simulator includes lamp heat. The current six-output ML contract does not include a lamp output. The near-term design therefore keeps normal lamp control under schedule/timer while allowing an independent safety layer to force it OFF under over-temperature conditions.

## Immediate next work — Gate 3

Use `docs/CONTINUATION_PLAN.md` for the detailed order. The immediate software work is:

1. DS3231 stores UTC and gains bounded set/write/readback support;
2. deterministic Europe/Warsaw CET/CEST conversion with DST boundary tests;
3. lighting schedule `06:00-22:00` local Wroclaw time;
4. runtime hardware capabilities corrected to the actual fan/humidifier-only climate actuators, with no heater/cooler/dehumidifier/CO2 doser;
5. SCD41 CO2 integrated as ventilation context without inventing dosing hardware;
6. begin pure derived-metric/observability plumbing while outputs remain fake-locked;
7. focused tests followed by exactly one full quality gate;
8. only after software qualification: exact-SHA flash/read-only hardware smoke, Shelly-assisted physical confirmation, deterministic thermal-safety test, bounded ventilation-effect capture and short supervised closed loop.

Do not skip directly from successful manual RF commands or Shelly calibration to unattended automatic control.
