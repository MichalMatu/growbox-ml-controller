# Environment Controller MVP

Status: architecture/design phase  
Branch: `mvp/environment-controller`

## 1. Product goal

Build a small, hardware-independent environment controller for a typical indoor growbox.

The MVP controls the climate from a small semantic configuration:

- target air temperature,
- target relative humidity,
- target CO2 concentration,
- light schedule,
- assignment of available outputs to actuator roles.

The first implementation must not depend on ESP32-S3, OLED, encoder, GPIO, relay boards, MQTT, Shelly, Modbus, or any particular sensor. Those are adapters around the core.

The architecture follows an IPO-style separation:

`inputs -> normalized environment state -> control -> safety/arbitration -> desired actions -> outputs`

No layer should need to know how the layer on the other side is physically implemented.

## 2. MVP boundary

### Included

Semantic measurements:

- air temperature [degC],
- relative humidity [%],
- CO2 [ppm],
- current time / schedule state.

Semantic actuator roles:

- heater,
- cooler,
- circulation/exhaust fan,
- humidifier,
- dehumidifier,
- CO2 doser,
- grow light.

Configuration:

- target temperature,
- target humidity,
- target CO2,
- light ON/OFF schedule,
- hysteresis/deadbands,
- assignment of abstract output endpoints to actuator roles,
- enabled/disabled state for each function.

Controller behavior:

- deterministic rule-based control first,
- safety interlocks independent from the controller policy,
- explicit handling of unavailable/stale/invalid measurements,
- observable reasons for every resulting action.

### Explicitly outside the first MVP

- irrigation,
- soil moisture,
- pot-level control,
- EC,
- pH,
- nutrient tank control,
- PPFD/light intensity control,
- leaf temperature,
- multiple climate zones,
- dosing recipes,
- hardware drivers,
- display/menu implementation,
- ML as the primary controller.

These can be added later without changing the core separation.

## 3. Architectural layers

### A. Input adapters

An input adapter converts any source into semantic measurements.

Possible future sources:

- local sensor,
- BLE,
- MQTT,
- Modbus,
- Nodeflow,
- REST API,
- simulator,
- recorded dataset.

The core never sees source identity.

Example semantic sample:

```text
Measurement {
  kind: AirTemperature
  value: 23.7
  valid: true
  age_ms: 1200
  quality: Good
}
```

### B. EnvironmentState

One normalized snapshot used by control logic.

Conceptually:

```text
EnvironmentState {
  air_temperature
  relative_humidity
  co2
  time
  light_schedule_active
}
```

Each measured value carries validity/freshness separately from its numeric value.

No fake value such as `0` should represent a missing sensor.

### C. User configuration

The configuration describes intent, not hardware.

```text
ClimateTargets {
  temperature_c
  humidity_pct
  co2_ppm
}

LightSchedule {
  enabled
  on_time
  off_time
}
```

Control tuning belongs here too:

```text
ControlTuning {
  temperature_deadband_c
  humidity_deadband_pct
  co2_deadband_ppm
}
```

Defaults must be safe and understandable.

### D. ControlPolicy

The policy consumes only:

- `EnvironmentState`,
- user targets,
- availability/capabilities.

It produces requests, not direct GPIO commands.

```text
ControlRequests {
  heater: 0..1
  cooler: 0..1
  fan: 0..1
  humidifier: 0..1
  dehumidifier: 0..1
  co2_doser: 0..1
  light: 0..1
}
```

For the first MVP the policy is deterministic and rule based.

A future `MlControlPolicy` may implement the same interface.

### E. Safety and arbitration

This layer is mandatory and must remain independent from ML/rules.

Responsibilities include:

- heater and cooler cannot fight each other,
- humidifier and dehumidifier cannot fight each other,
- CO2 dosing is disabled when lights are off,
- CO2 dosing can be inhibited while strong exhaust ventilation is requested,
- actuator maximum run time,
- minimum ON/OFF time where appropriate,
- fail-safe behavior when required measurements are stale or invalid,
- output clamping to supported capability,
- deterministic priority when several control needs request the same shared actuator.

Output of this layer:

```text
DesiredActions
```

Every overridden request should carry a reason, for example:

```text
co2_doser = OFF
reason = CO2_INHIBITED_LIGHTS_OFF
```

This will be useful for OLED, web UI, logs, debugging and training-data analysis.

### F. Output mapping

The controller operates on roles. Output mapping connects roles to abstract output endpoints.

Example:

```text
output_1 -> Light
output_2 -> Fan
output_3 -> Heater
output_4 -> Humidifier
output_5 -> Co2Doser
output_6 -> None
```

An endpoint advertises capability rather than hardware type:

```text
OutputEndpointCapability = Binary | Variable
```

Examples later:

- GPIO relay -> Binary,
- SSR -> Binary or Variable depending on implementation,
- PWM -> Variable,
- Shelly switch -> Binary,
- Modbus VFD -> Variable.

The core does not contain those implementations.

More than one endpoint may eventually be assigned to the same role. The MVP data model should not make that impossible even if the first UI initially restricts it for simplicity.

### G. Output adapters

Output adapters translate `DesiredActions` into physical commands.

Future examples:

- GPIO,
- relay board,
- PWM,
- Shelly RPC,
- MQTT,
- Modbus,
- Nodeflow.

They are outside control logic.

## 4. Rule controller v1

The first controller should deliberately be simple.

### Temperature

Below target minus deadband:

- request heater.

Above target plus deadband:

- request cooler,
- optionally request/increase fan according to configured ventilation strategy.

Inside deadband:

- no heating/cooling request.

### Humidity

Below target minus deadband:

- request humidifier.

Above target plus deadband:

- request dehumidifier,
- fan may also be requested when ventilation is allowed to help.

### CO2

If:

- CO2 measurement is valid,
- lights are active,
- CO2 is below target minus deadband,
- safety permits dosing,

then request CO2 dosing.

Otherwise do not dose.

### Light

Light request is derived directly from the schedule in the MVP.

Manual override can be added later but must have explicit timeout/priority semantics rather than silently bypassing safety.

## 5. Shared actuator problem

This must be designed now because a fan can serve several purposes:

- normal air exchange,
- heat removal,
- humidity removal,
- CO2 management.

Therefore climate loops should not directly switch the fan.

Instead they emit named demands, for example:

```text
fan_demands {
  baseline_ventilation
  temperature
  humidity
  safety
}
```

An arbitrator combines them into one final fan request, initially using a simple maximum/priority rule.

This avoids coupling temperature logic to humidity logic and leaves room for ML later.

## 6. Missing sensor behavior

A capability may exist without a measurement and a measurement may exist without an actuator.

Examples:

- temperature sensor present, heater absent -> monitor only,
- humidity sensor absent, humidifier present -> humidifier must not run automatically,
- CO2 sensor absent -> automatic CO2 dosing must be disabled,
- CO2 sensor present, doser absent -> monitor only,
- cooler absent -> high-temperature policy may use fan only if configured/safe.

The system should expose capability/availability explicitly instead of inferring it from numeric values.

## 7. Configuration model

The eventual UI (OLED, web, app, etc.) edits one configuration model.

Conceptual sections:

```text
ControllerConfig
├── targets
├── light_schedule
├── control_tuning
├── enabled_functions
├── output_bindings
└── safety_limits
```

UI is therefore an editor/view of configuration and status, not part of control logic.

The same configuration should be loadable from JSON for simulator/development use and from persistent storage on an embedded target later.

## 8. Status model

The core should publish a complete status snapshot suitable for any UI.

Conceptually:

```text
ControllerStatus
├── environment
├── target values
├── requested actions
├── final/safe actions
├── output bindings
├── active interlocks
└── diagnostics/reasons
```

An OLED can show a small subset; the web UI can show everything. Neither requires controller-specific special cases.

## 9. ML integration point

ML is deliberately not part of MVP phase 1.

The architectural seam is:

```text
EnvironmentState + ControllerConfig
               |
               v
          ControlPolicy
               |
               v
        ControlRequests
```

Initially:

```text
ControlPolicy = RuleControlPolicy
```

Later:

```text
ControlPolicy = MlControlPolicy
```

Safety, arbitration, output mapping and hardware adapters remain unchanged.

The existing simulator/training engine is retained and can later generate data for the new smaller semantic contract.

## 10. Proposed implementation phases

### Phase 0 — freeze the MVP behavior

Before implementation, agree on:

- exact semantic inputs,
- exact actuator roles,
- interaction/priority rules,
- missing-sensor behavior,
- default deadbands,
- CO2 safety behavior,
- fan arbitration,
- schedule semantics,
- configuration persistence semantics.

Deliverable: this document becomes an agreed behavior specification.

### Phase 1 — small domain contract

Create hardware-independent types for:

- measurements,
- `EnvironmentState`,
- `ControllerConfig`,
- `OutputRole`,
- output capabilities/bindings,
- `ControlRequests`,
- `DesiredActions`,
- status/reason codes.

No ESP32 code and no UI code yet.

### Phase 2 — deterministic reference controller

Implement:

- schedule,
- temperature rule,
- humidity rule,
- CO2 rule,
- fan demands/arbitration,
- safety supervisor.

The same core should be executable against synthetic states on a desktop.

### Phase 3 — connect the existing simulator

Adapt the current simulator to feed the new MVP `EnvironmentState` and accept `DesiredActions`.

This becomes the first complete closed-loop environment without hardware.

Goal:

```text
simulator -> MVP controller -> simulator
```

At this point behavior can be tuned and visualized with the existing tooling.

### Phase 4 — configuration and status interfaces

Define stable JSON serialization for:

- configuration,
- state/status,
- output binding.

Both existing dashboards may then be adapted incrementally without coupling them to hardware.

### Phase 5 — embedded adapter

Only after the core behavior is stable:

- ESP32-S3 runtime,
- persistent settings,
- clock,
- local sensor adapters,
- output adapters.

### Phase 6 — local UI

OLED + encoder becomes one UI adapter over the same configuration/status API.

It is not required for controller correctness.

### Phase 7 — ML policy

Use the simulator and/or recorded real data to train a model against the new semantic contract.

ML should initially replace only `RuleControlPolicy`; SafetySupervisor remains authoritative.

## 11. MVP success criteria

The MVP foundation is successful when a desktop simulation can configure something like:

```text
Target temperature: 24 C
Target humidity:    60 %
Target CO2:         900 ppm
Lights:             06:00 -> 00:00

Outputs:
1 Light
2 Fan
3 Heater
4 Humidifier
5 CO2
```

and the controller can run closed-loop against the simulator while:

- never depending on physical GPIO/sensor identity,
- clearly showing why each actuator is ON/OFF,
- failing safely when measurements disappear,
- allowing a different input/output adapter without changing control logic,
- allowing `RuleControlPolicy` to be replaced by ML later.

## 12. Decisions intentionally postponed

Do not decide these until the behavioral contract is stable:

- exact ESP32 board,
- display model,
- encoder model,
- sensor models,
- number/type of GPIO expanders,
- relay/SSR board,
- MQTT topic layout,
- BLE protocol,
- enclosure/UI layout,
- final ML architecture.

Those choices must adapt to the controller contract, not define it.
