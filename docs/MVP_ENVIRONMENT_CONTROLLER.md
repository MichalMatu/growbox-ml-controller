# Environment Controller MVP

Status: architecture/design phase — MVP v1 flow and I/O frozen  
Branch: `mvp/environment-controller`

## 1. Product goal

Build a hardware-independent environment controller for a typical indoor growbox.

Hardware choices do not define the core. ESP32-S3, OLED, encoder, GPIO, relay boards, BLE, MQTT, Shelly, Modbus and sensor models are future adapters.

## 2. Frozen MVP v1 architecture

The core follows IPO separation:

```text
INPUT
semantic environment values
        |
        v
PROCESSING
ControlPolicy
        |
        v
Safety + Arbitration
        |
        v
OUTPUT
semantic device-role commands
```

Rules:

- inputs describe values, never hardware sources;
- processing never directly controls GPIO or a specific device;
- outputs describe device roles, never physical endpoints;
- hardware adapters exist only outside the core;
- `SafetySupervisor` remains independent from the control policy;
- the first policy is rule based; ML may later replace only `ControlPolicy`.

## 3. Frozen INPUT contract

Required semantic inputs:

- `air_temperature_c`
- `relative_humidity_pct`
- `co2_ppm`
- `time_of_day`
- `light_schedule_active`

Optional semantic inputs:

- `outside_temperature_c`
- `outside_humidity_pct`

Every measured value must carry measurement state separately from its numeric value:

- `valid`
- freshness / `age_ms`

A missing or invalid measurement must never be represented by a fake numeric value such as zero.

The core does not know whether a value came from I2C, BLE, MQTT, Modbus, Nodeflow, REST, a simulator or a recorded dataset.

## 4. Frozen user configuration

Targets:

- `target_temperature_c`
- `target_humidity_pct`
- `target_co2_ppm`

Light schedule:

- `light_on_time`
- `light_off_time`

Control tuning:

- `temperature_deadband_c`
- `humidity_deadband_pct`
- `co2_deadband_ppm`

Capabilities/configuration also describe which functions are available and which abstract endpoints are assigned to which output roles.

## 5. Frozen OUTPUT roles

MVP v1 device roles:

- `heater`
- `cooler`
- `exhaust_fan`
- `circulation_fan`
- `humidifier`
- `dehumidifier`
- `co2_doser`
- `light`

Internal commands use normalized values:

```text
0.0 = off / minimum
1.0 = full request
```

This applies even when the physical device is binary. The output adapter decides how a normalized command maps to relay ON/OFF, PWM, VFD, Shelly, Modbus or another implementation.

Conceptually:

```text
ControlRequests {
  heater: 0..1
  cooler: 0..1
  exhaust_fan: 0..1
  circulation_fan: 0..1
  humidifier: 0..1
  dehumidifier: 0..1
  co2_doser: 0..1
  light: 0..1
}
```

## 6. Output binding

The core controls roles. A separate mapping connects roles to abstract output endpoints.

Example:

```text
Endpoint A -> Light
Endpoint B -> ExhaustFan
Endpoint C -> Heater
Endpoint D -> Humidifier
Endpoint E -> Co2Doser
Endpoint F -> None
```

Only an adapter knows what an endpoint physically is.

Examples later:

- GPIO relay
- SSR
- PWM
- Shelly
- Modbus VFD
- MQTT-controlled output

## 7. Processing

Phase 1 policy:

```text
RuleControlPolicy
```

Future policy:

```text
MlControlPolicy
```

Both implement the same logical contract:

```text
EnvironmentState + ControllerConfig
              -> ControlPolicy
              -> ControlRequests
```

ML is therefore a processing strategy, not the architecture of the whole product.

## 8. Safety and arbitration

Safety is authoritative and remains outside ML/rule policy.

Minimum responsibilities:

- heater and cooler cannot fight each other;
- humidifier and dehumidifier cannot fight each other;
- CO2 dosing is disabled with lights off;
- CO2 dosing is disabled for invalid/stale CO2 measurement;
- CO2 dosing may be inhibited during strong exhaust ventilation;
- stale/invalid required measurements produce safe behavior;
- actuator commands are clamped to available capability;
- minimum ON/OFF time and maximum run time can be enforced where needed;
- shared demands are resolved deterministically.

The system should expose reasons for overrides and resulting actions.

## 9. Fan behavior

`exhaust_fan` and `circulation_fan` are separate roles.

`exhaust_fan` may be requested for several reasons:

- temperature removal;
- humidity removal;
- baseline air exchange;
- safety.

Individual loops do not directly own the exhaust fan. They produce demands and arbitration combines them into the final request.

`circulation_fan` is an independent role for internal air movement and does not automatically imply outside-air exchange.

## 10. Missing capability behavior

Missing hardware is not itself an error.

Examples:

- temperature measurement available, heater absent -> monitor only / use other available strategies;
- humidity measurement absent, humidifier present -> no automatic humidification;
- CO2 measurement absent -> automatic CO2 dosing disabled;
- CO2 measurement available, doser absent -> monitor only;
- cooler absent -> cooling may use exhaust if available and allowed.

Availability is explicit and never inferred from numeric measurements.

## 11. Configuration and status model

Conceptually:

```text
ControllerConfig
├── targets
├── light_schedule
├── control_tuning
├── enabled_functions
├── output_bindings
└── safety_limits
```

The core publishes status independently of any UI:

```text
ControllerStatus
├── environment
├── targets
├── requested_actions
├── final_safe_actions
├── output_bindings
├── active_interlocks
└── reasons / diagnostics
```

OLED, web UI, app or API are only views/editors of this model.

## 12. MVP v1 boundary

Included:

- temperature control;
- humidity control;
- CO2 control;
- light schedule;
- exhaust and circulation fan roles;
- hardware-independent input/output mapping;
- rule policy;
- safety/arbitration;
- status/reason reporting.

Not included yet:

- irrigation;
- soil moisture;
- EC;
- pH;
- nutrient tank control;
- PPFD;
- leaf temperature;
- multiple climate zones;
- hardware drivers;
- OLED/menu implementation;
- final ML model.

## 13. Implementation order

1. Finish behavioral decisions for the frozen contract: exact safety rules, deadbands, priorities and schedule semantics.
2. Define small hardware-independent domain types.
3. Implement deterministic reference controller and SafetySupervisor.
4. Adapt the existing simulator to the new `EnvironmentState` / output contract.
5. Run the complete loop on desktop: `simulator -> controller -> simulator`.
6. Define stable JSON configuration/status representation.
7. Adapt existing dashboards as needed.
8. Add embedded/hardware adapters only after the core is stable.
9. Add ML policy later using the same I/O contract.

## 14. Decisions intentionally postponed

Do not choose yet:

- exact ESP32 board;
- display or encoder;
- sensor models;
- GPIO/relay/SSR hardware;
- MQTT/BLE/Modbus details;
- final UI layout;
- final ML architecture.

Those choices must adapt to this contract, not define it.
