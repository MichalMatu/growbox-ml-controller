# Current controller status

Updated: 2026-09-05
Development branch: `mvp/environment-controller`
Primary roadmap/handoff: `docs/PROJECT_ROADMAP.md`

## Current transition

**Stage27C FROZEN -> Stage28A DONE -> Stage28B DONE -> Stage28C DONE -> pre-Stage28D golden gate COMPLETE -> Stage28D manual RF path COMPLETE -> Gate 1 semantic binding COMPLETE -> Gate 2 lamp safety NEXT**

Stage27C and the completed RF transport/identity work are not being reopened.

## Current safety state

- Rule policy remains authoritative.
- ML remains shadow/research-only.
- Automatic physical outputs remain fake-locked.
- Manual RF service commands are an explicit operator-present diagnostic path only.
- Local TX completion / `SelfTx` is not physical socket/load acknowledgement.
- No unattended real-output gate is open yet.

## Hardware-qualified identities

Golden pre-Stage28D firmware/source:

`316b58e76de609069ddbf2667fe86f6218fb2143`

This SHA passed the complete software gate and strict 5400-second real-hardware soak with real sensors/RTC/BLE/SD and fake-locked outputs.

Hardware-qualified Stage28D service-console firmware:

`af16aebde8f69d1a1257256c7711e9721c07c9d5`

The service console uses the primary UART driver and provides `help`, `status`, `sensors`, `rf list`, named manual RF ON/OFF commands and bounded `rf rx` capture.

Later documentation-only branch commits must not be described as separately hardware-tested firmware identities.

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

## Stage28 reference test rig — sensor placement

The following physical arrangement is the frozen reference layout for the current mint growbox tests. Keep sensor positions stable during qualification and data collection unless a later experiment explicitly records a topology change.

| sensor | physical placement | authoritative role | secondary role |
| --- | --- | --- | --- |
| TP357 BLE thermo/hygrometer | inside the growbox, slightly above the leaf canopy | primary inside temperature and relative humidity | primary thermal-safety temperature source |
| SCD41 | inside the growbox, approximately at pot height | primary inside CO2 | backup/diagnostic temperature and relative humidity |
| Xiaomi BLE thermo/hygrometer | outside the growbox, next to the air intake | incoming/outside temperature and relative humidity | ventilation-effectiveness context |
| DS3231 | controller installation | RTC/timebase | lighting schedule time source |

SCD41 installation note: the sensor is soldered to the HAT through approximately 5 cm leads, and the HAT itself is physically spaced from the ESP32-S3. Conductive heat transfer from the ESP32 into the SCD41 is therefore expected to be small in this test rig. Even so, SCD41 temperature/RH remain diagnostic/backup values rather than the authoritative inside T/RH source; TP357 remains authoritative for those channels.

This topology intentionally gives the controller three different pieces of environmental context: growbox canopy conditions, growbox CO2/pot-height conditions, and the temperature/RH of the air available at the intake.

## Current mint control baseline

The current software-safety baseline for the mint test rig is:

- exhaust fan is a binary actuator only: `OFF` or `ON`; no PWM/duty-cycle control is assumed;
- TP357 inside temperature is the primary thermal-safety measurement;
- lamp thermal cutoff: `28.0 °C` -> force lamp OFF regardless of the lighting timer and request exhaust fan ON;
- nominal relative-humidity target: about `60% RH`, with an initial normal band of approximately `55-65% RH`;
- high humidity around `70% RH` and above should be treated as a ventilation/dehumidification condition, subject to intake-air conditions and later arbitration rules;
- normal light request remains schedule-driven and independent from the six Climate-v6 ML outputs.

The recovery threshold/hysteresis hold duration for the 28 °C lamp cutoff must remain explicit configuration in Gate 2 rather than being hidden in the RF driver. Automatic physical outputs remain fake-locked until the corresponding software and supervised hardware gates pass.

## Frozen actuator semantics

- `remote_socket_1` / endpoint 1 -> `ExhaustFan`;
- `remote_socket_3` / endpoint 3 -> `Humidifier`;
- `remote_socket_2` / endpoint 2 -> dedicated scheduled-light path, not a normal Climate-v6 ML output.

The Gate 1 validator fails closed for missing, duplicate, unknown, stale or scheduled-light-as-climate bindings. Automatic runtime outputs remain fake-locked.

The lamp is a special layered actuator:

`schedule/timer -> requested lamp state -> thermal safety override -> physical lamp output`

Climate-v6 already consumes `schedule.light_level`, and the simulator includes lamp heat. The current six-output ML contract does not include a lamp output. The near-term design therefore keeps normal lamp control under schedule/timer while allowing an independent safety layer to force it OFF under over-temperature conditions.

## Immediate next work

Use `docs/PROJECT_ROADMAP.md` as the canonical plan. The next ordered gates are:

1. software-only lamp timer + over-temperature safety override with hysteresis;
2. focused tests/build while physical outputs remain fake-locked;
3. exact-SHA flash/read-only smoke;
4. operator-present physical role-routing validation;
5. supervised thermal-safety validation using deterministic temperature injection rather than deliberately overheating the growbox;
6. short supervised closed-loop run;
7. only then consider a separately authorized unattended real-output soak.

Do not skip directly from successful manual RF commands to unattended automatic control.
