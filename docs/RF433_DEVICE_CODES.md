# RF433 device codes and growbox hardware map

Updated: 2026-09-04
Work branch: `mvp/environment-controller`

This file is the quick human-readable source of truth for learned RF433 ON/OFF identities and the current growbox sensor/actuator topology.

Validated identities that are used by firmware must also be frozen in `src/climate/rf433/Rf433HardwareConfig.h` and covered by host tests. Do not infer a semantic actuator role from a neutral hardware identity.

## Current RF433 devices

| physical device | hardware label | endpoint id | ON code | OFF code | bits | protocol | pulse | validated TX repeat | status |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| not assigned yet | `remote_socket_1` | 1 | 906118656 (`0x36024600`) | 1040336384 (`0x3E024600`) | 32 | 2 | 575 us | 10 | frozen / physically validated |
| lamp | pending | pending | pending | pending | pending | pending | pending | pending | codes needed |
| fan | pending | pending | pending | pending | pending | pending | pending | pending | codes needed |
| humidifier | pending | pending | pending | pending | pending | pending | pending | pending | codes needed |

`remote_socket_1` remains deliberately neutral until its real physical device is explicitly identified.

## Data to record for every learned device

For each device record:

- physical device name;
- neutral hardware label, for example `remote_socket_2`;
- ON decimal code and optional hex form;
- OFF decimal code and optional hex form;
- bit length;
- protocol number;
- pulse length in microseconds;
- ESP transmit repeat count that was physically verified as reliable;
- evidence/commit where the pair was physically checked.

The exact repeat count emitted by an original handheld remote must not be claimed unless it was actually measured. A reliable ESP transmit repeat setting is a separate fact.

## Current growbox sensor topology

| location | sensor/source | role |
| --- | --- | --- |
| inside growbox | TP357 BLE thermometer/hygrometer | inside climate reference |
| outside growbox | Xiaomi BLE thermometer/hygrometer | nearby/outside climate reference |
| inside growbox | sensors connected directly to ESP32 | local growbox measurements |

The exact directly connected ESP32 sensor list remains defined by the active hardware/runtime configuration; this document records their physical placement as inside the growbox.

## Safety/evidence boundary

Recording an RF code does not authorize unattended mains-load control. Local RF TX completion or local self-RX is not physical load-state acknowledgement. Runtime outputs remain fake-locked until the later explicit physical-output gate qualifies semantic role mapping and real actuation.

## Quick paste format for new codes

Use this format when adding a new device:

```text
DEVICE: lamp | fan | humidifier
ON: <decimal or hex>
OFF: <decimal or hex>
BITS: <number>
PROTOCOL: <number>
PULSE_US: <number>
TX_REPEAT: <number or unknown>
```

If only ON/OFF codes are known initially, record those first and leave the remaining fields explicitly unknown until captured/validated.
