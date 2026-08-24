# Environment Controller MVP

Status: architecture/design phase — MVP v1 flow and I/O frozen  
Branch: `mvp/environment-controller`

## 1. Product goal

Build a standalone, hardware-independent environment controller for a typical indoor growbox.

This project owns its own control model, simulation/training path, runtime contract and future embedded implementation. It is not an extension, plugin, ML node or control layer for `esp32s3_LiteGraph`.

Hardware choices do not define the core. ESP32-S3, OLED, encoder, GPIO, relay boards, BLE, MQTT, Shelly, Modbus and sensor models are future adapters.

## 2. Frozen MVP v1 architecture

The core follows IPO separation:

```text
MEASUREMENTS + SYSTEM TIME + CONFIGURATION
                    |
                    v
             EnvironmentState
                    |
                    v
PROCESSING
ControlPolicy
                    |
                    v
ARBITRATION
                    |
                    v
SAFETY SUPERVISOR
                    |
                    v
OUTPUT
semantic device-role commands
```

Rules:

- measurements describe semantic values, never hardware sources;
- current time is system context, not a sensor input;
- schedule state is derived from current time and configuration;
- VPD is derived inside the core from temperature and relative humidity;
- processing never directly controls GPIO or a specific device;
- outputs describe device roles, never physical endpoints;
- hardware adapters exist only outside the core;
- `SafetySupervisor` remains independent from the control policy;
- the first policy is rule based; ML may later replace only `ControlPolicy` inside this standalone project.

## 3. Frozen INPUT contract

Required semantic measurements:

- `air_temperature_c`
- `relative_humidity_pct`

Optional semantic measurements:

- `co2_ppm`
- `outside_temperature_c`
- `outside_humidity_pct`
- `leaf_temperature_c`

Every measured value must carry measurement state separately from its numeric value:

- `valid`
- freshness / `age_ms`

System context:

- `current_time`

Derived environment values:

- `air_vpd_kpa`
- `leaf_vpd_kpa` when `leaf_temperature_c` is valid
- optionally `outside_vpd_kpa` when outside temperature and humidity are valid

`light_schedule_active` is not an input. It is derived from `current_time` and `light_schedule`.

For MVP v1, VPD control must work without a leaf-temperature sensor. When `leaf_temperature_c` is unavailable, the controller uses air VPD calculated from air temperature and relative humidity. When a valid leaf temperature is available, the controller may use leaf VPD for more accurate plant-level control.

CO2 is optional. A basic growbox controller must remain fully functional for temperature, humidity/VPD, ventilation and lighting without a CO2 sensor.

A missing or invalid measurement must never be represented by a fake numeric value such as zero.

The core does not know whether a value came from I2C, BLE, MQTT, Modbus, REST, a simulator or a recorded dataset.

## 4. Frozen user configuration

Light schedule:

- `light_on_time`
- `light_off_time`

Day targets:

- `day_temperature_c`
- `day_humidity_pct`
- `day_vpd_kpa`
- `day_humidity_control_mode = RH | VPD`
- `day_co2_enabled`
- `day_co2_ppm` when CO2 control is enabled
- `day_light_level = 0..1`

Night targets:

- `night_temperature_c`
- `night_humidity_pct`
- `night_vpd_kpa`
- `night_humidity_control_mode = RH | VPD`
- `night_co2_enabled = false` by default
- `night_co2_ppm` only when explicitly enabled
- `night_light_level = 0.0` by default

The active target profile is derived from current time and the light schedule.

RH and VPD are coupled quantities, so the controller must not independently regulate both at the same time. Each DAY/NIGHT profile selects one humidity-control mode:

```text
RH mode  -> relative_humidity_pct is the controlled humidity target
VPD mode -> VPD is the controlled humidity target
```

The non-selected value remains calculated and visible for monitoring, diagnostics and future ML use.

Temperature always remains an independent target. A correct VPD does not make an incorrect air temperature acceptable.

Control tuning:

- `temperature_deadband_c`
- `humidity_deadband_pct`
- `vpd_deadband_kpa`
- `co2_deadband_ppm`
- `minimum_ventilation`

Safety limits:

- `max_temperature_c`
- `min_temperature_c`
- `max_humidity_pct`
- `max_co2_ppm`
- `max_co2_dosing_time`
- `sensor_timeout`
- actuator-specific minimum ON/OFF times where required

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
0.0 = off / minimum request
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

Each bound actuator may also declare configurable operating limits:

```text
ActuatorLimits {
  min_level: 0..1
  max_level: 0..1
}
```

Examples:

- exhaust fan may idle at `0.20` and ramp up to `1.00`;
- a dimmable light may be limited to `0.70`;
- a binary relay may still expose `0.0/1.0` after adapter conversion.

The controller requests semantic intensity. The adapter decides how that request is physically represented.

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

Future policy inside this project:

```text
MlControlPolicy
```

Both implement the same logical contract:

```text
EnvironmentState + ControllerConfig
              -> ControlPolicy
              -> ControlRequests
```

ML is therefore a processing strategy inside the standalone growbox controller, not an extension of another automation runtime.

The rule controller may use either RH or calculated VPD for humidity-related decisions according to the active DAY/NIGHT profile.

## 8. Safety and arbitration

Safety is authoritative and remains outside ML/rule policy.

Minimum responsibilities:

- heater and cooler cannot fight each other;
- humidifier and dehumidifier cannot fight each other;
- CO2 dosing is disabled when CO2 control is not configured;
- CO2 dosing is disabled with lights off unless explicitly supported later;
- CO2 dosing is disabled for missing, invalid or stale CO2 measurement;
- CO2 dosing may be inhibited during strong exhaust ventilation;
- stale/invalid required measurements produce safe behavior;
- VPD control is unavailable when temperature or humidity is invalid/stale;
- leaf-VPD control falls back to air VPD if leaf temperature is unavailable or stale;
- actuator commands are clamped to configured min/max capability;
- minimum ON/OFF time and maximum run time can be enforced where needed;
- shared demands are resolved deterministically;
- configured hard safety limits override controller requests.

The system should expose reasons for overrides and resulting actions.

## 9. Fan behavior

`exhaust_fan` and `circulation_fan` are separate roles.

`exhaust_fan` may be requested for several reasons:

- temperature removal;
- humidity/VPD correction;
- baseline air exchange;
- safety.

Individual loops do not directly own the exhaust fan. They produce demands and arbitration combines them into the final request.

`minimum_ventilation` together with actuator `min_level` allows a typical growbox configuration where the exhaust fan runs continuously at a low baseline and increases only when climate control requires it.

`circulation_fan` is an independent role for internal air movement and does not automatically imply outside-air exchange.

## 10. Missing capability behavior

Missing hardware is not itself an error.

Examples:

- temperature measurement available, heater absent -> monitor only / use other available strategies;
- humidity measurement absent, humidifier present -> no automatic RH or VPD control;
- temperature or humidity invalid -> calculated VPD invalid;
- leaf temperature absent -> use air VPD;
- CO2 measurement absent -> temperature/RH/VPD/light control continues normally and automatic CO2 dosing stays disabled;
- CO2 measurement available, doser absent -> monitor only;
- cooler absent -> cooling may use exhaust if available and allowed.

Availability is explicit and never inferred from numeric measurements.

## 11. Configuration and status model

Conceptually:

```text
ControllerConfig
├── light_schedule
├── day_targets
├── night_targets
├── humidity_control_mode
├── control_tuning
├── enabled_functions
├── output_bindings
├── actuator_limits
└── safety_limits
```

The core publishes status independently of any UI:

```text
ControllerStatus
├── environment
│   ├── temperature
│   ├── relative_humidity
│   ├── air_vpd
│   ├── leaf_temperature [optional]
│   ├── leaf_vpd [optional]
│   └── co2 [optional]
├── current_time
├── active_profile (DAY/NIGHT)
├── active_targets
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
- humidity control by RH or calculated VPD;
- air VPD calculation and monitoring;
- optional leaf temperature and leaf-VPD calculation;
- optional CO2 monitoring/control;
- day/night targets;
- light schedule and normalized light level;
- exhaust and circulation fan roles;
- configurable actuator min/max levels;
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
- multiple climate zones;
- hardware drivers;
- OLED/menu implementation;
- final ML model;
- LiteGraph/Nodeflow integration or an ML node for `esp32s3_LiteGraph`.

## 13. Implementation order

1. Finish behavioral decisions for the frozen contract: exact safety rules, deadbands, priorities, RH/VPD mode behavior, actuator min/max semantics and schedule semantics.
2. Define small hardware-independent domain types.
3. Implement deterministic reference controller and SafetySupervisor.
4. Adapt the existing simulator to the new `EnvironmentState` / output contract.
5. Run the complete loop on desktop: `simulator -> controller -> simulator`.
6. Define stable JSON configuration/status representation.
7. Adapt existing dashboards as needed.
8. Add standalone embedded/hardware adapters only after the core is stable.
9. Train and benchmark `MlControlPolicy` inside this project against the deterministic reference controller.

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

## 15. Project boundary

`growbox-ml-controller` and `esp32s3_LiteGraph` remain separate projects.

For this MVP:

- no ML node is added to LiteGraph;
- no LiteGraph graph analysis is required by the growbox controller;
- no shared runtime or control loop is introduced;
- no dependency on Nodeflow contracts is allowed in the controller core;
- any future interoperability, if ever useful, must happen through a generic external adapter/API and must not couple either project's internal architecture.

This boundary is intentional: the growbox project must be able to prove or disprove the value of ML on its own, with its own simulator, benchmark and observable controller behavior.