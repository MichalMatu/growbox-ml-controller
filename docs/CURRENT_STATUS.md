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

## Sensor topology

- TP357 BLE thermo/hygrometer: inside growbox;
- Xiaomi BLE thermo/hygrometer: outside growbox;
- SCD41 and other directly connected ESP32 sensors: inside/controller installation;
- DS3231 provides RTC.

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
