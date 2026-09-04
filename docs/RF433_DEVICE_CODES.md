# RF433 device codes and growbox hardware map

Updated: 2026-09-04
Work branch: `mvp/environment-controller`

This file is the quick human-readable source of truth for learned RF433 ON/OFF identities and the current growbox sensor/actuator topology.

Validated identities that are used by firmware must also be frozen in `src/climate/rf433/Rf433HardwareConfig.h` and covered by host tests. Captured values and physically validated ESP transmit settings are separate evidence and must not be silently collapsed.

## Current RF433 devices

| physical device | hardware label | endpoint id | ON code | OFF code | bits | protocol | captured pulse | requested TX repeat | physical TX status |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| fan | `remote_socket_1` | 1 | 906118656 (`0x36024600`) | 1040336384 (`0x3E024600`) | 32 | 2 | 560 us | 10 | already physically validated with 575 us / repeat 10 |
| lamp | `remote_socket_2` | pending | 235030016 (`0x0E024600`) | 16926208 (`0x01024600`) | 32 | 2 | 560 us | 10 | capture recorded; ESP -> socket validation pending |
| humidifier | `remote_socket_3` | pending | 637683200 (`0x26024600`) | 771900928 (`0x2E024600`) | 32 | 2 | 560 us | 10 | capture recorded; ESP -> socket validation pending |

The operator explicitly identified the previously frozen `remote_socket_1` pair as the fan on 2026-09-04.

### Fan pulse evidence note

The newly supplied/captured fan pulse is `560 us`. The earlier Stage28C physical ESP transmit qualification for the same ON/OFF pair used `575 us` with repeat `10` and was reliable. Keep both facts until the next bounded physical socket test decides whether the common `560 us` profile is also reliable. Do not rewrite historical Stage28C evidence.

## Compact code list

```text
LAMP / remote_socket_2
ON:  235030016  (0x0E024600)
OFF: 16926208   (0x01024600)
BITS: 32
PROTOCOL: 2
CAPTURED_PULSE_US: 560
TX_REPEAT: 10
STATUS: pending physical ESP -> socket validation

FAN / remote_socket_1
ON:  906118656  (0x36024600)
OFF: 1040336384 (0x3E024600)
BITS: 32
PROTOCOL: 2
CAPTURED_PULSE_US: 560
PHYSICALLY_VALIDATED_TX_PULSE_US: 575
TX_REPEAT: 10
STATUS: ON/OFF pair and 575 us / repeat 10 physically validated in Stage28C

HUMIDIFIER / remote_socket_3
ON:  637683200  (0x26024600)
OFF: 771900928  (0x2E024600)
BITS: 32
PROTOCOL: 2
CAPTURED_PULSE_US: 560
TX_REPEAT: 10
STATUS: pending physical ESP -> socket validation
```

## Serial service commands

The real-input firmware includes a bounded primary-serial service console. The captured lamp and humidifier profiles are now also frozen in `Rf433HardwareConfig.h` for manual diagnostics, but their physical socket validation is still pending. The fan keeps the already-qualified `575 us / repeat 10` transmit profile.

Useful commands:

```text
help
status
sensors
rf list
rf lamp on
rf lamp off
rf fan on
rf fan off
rf humidifier on
rf humidifier off
rf rx 1000
```

Named RF transmit commands are accepted only when the RF diagnostics transport is ready. They are explicit operator service actions and do not unlock the automatic climate-output path. A `manual_rf_tx` line proves local transmit lifecycle only; physical device observation remains the acceptance criterion.

## Data to record for every learned device

For each device record:

- physical device name;
- neutral hardware label;
- ON decimal code and hex form;
- OFF decimal code and hex form;
- bit length;
- protocol number;
- captured pulse length in microseconds;
- requested/configured ESP transmit repeat count;
- separately, the exact pulse/repeat combination that was physically verified as reliable;
- evidence/commit where the pair was physically checked.

The exact repeat count emitted by an original handheld remote must not be claimed unless it was actually measured. A requested or reliable ESP transmit repeat setting is a separate fact.

## Current growbox sensor topology

| location | sensor/source | role |
| --- | --- | --- |
| inside growbox | TP357 BLE thermometer/hygrometer | inside climate reference |
| outside growbox | Xiaomi BLE thermometer/hygrometer | nearby/outside climate reference |
| inside growbox | sensors connected directly to ESP32 | local growbox measurements |

The exact directly connected ESP32 sensor list remains defined by the active hardware/runtime configuration; this document records their physical placement as inside the growbox.

## Next physical validation

The next hardware step is a bounded manual ON/OFF test of each socket/device from the ESP32:

1. lamp: verify ON and OFF;
2. fan: recheck ON and OFF and compare 560 us against the already qualified 575 us profile;
3. humidifier: verify ON and OFF.

Physical observation of the actual lamp/fan/humidifier state is the acceptance criterion. Local TX completion or `SelfTx` reception alone is not sufficient.

## Safety/evidence boundary

Recording an RF code does not authorize unattended mains-load control. Local RF TX completion or local self-RX is not physical load-state acknowledgement. Runtime outputs remain fake-locked until the later explicit physical-output gate qualifies semantic role mapping and real actuation.
