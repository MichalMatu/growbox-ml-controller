# Hardware Bring-up Checklist

Status: Stage26C software readiness gate. Physical hardware work starts only in Stage27.

Passing Stage26C is software evidence only; it is not hardware validation.

## Frozen software boundary before hardware work

The controller architecture is ready for concrete hardware adapters without changing the climate
core:

- `CompositeClimateSnapshotProvider` aggregates hardware-neutral inside, outside, clock and
  schedule/config sources into the existing `ClimateInputSnapshot`;
- `ClimateApplication` keeps the strict input -> processing -> output composition;
- `MappedClimateRoleDriver` maps six stable semantic actuator roles to normalized endpoint writes;
- `ClimateControlLoop` remains the owner of confirmed applied state, OFF recovery and actuator fault
  latching;
- diagnostics observe the exact consumed input and resulting runtime/output evidence without feeding
  control state;
- Rule remains authoritative. `MlActive` is not qualified for real actuation.

## Manual freeze required before Stage27

Do not implement physical drivers until each item below is resolved deliberately.

- SCD41 driver/library: UNRESOLVED — freeze the ESP-IDF-compatible library/driver, I2C controller,
  address handling, pins, sampling cadence and error/freshness mapping. The SCD41 sensor itself is
  already the planned inside T/RH/CO2 device.
- outside BLE sensor/model: UNRESOLVED — freeze the exact sensor, advertisement format/decoder, BLE
  stack, scan cadence, reconnect/absence behavior and freshness/age mapping.
- RTC part: UNRESOLVED — freeze the backed-up RTC part, library/driver, bus/address/pins, backup-power
  implementation and synchronization policy. Candidate class remains DS3231 or PCF8563; neither is
  selected by Stage26C.
- physical actuator backend/pins: UNRESOLVED — freeze relay/MOSFET/PWM or other endpoint technology,
  endpoint-to-role mapping, pins, active polarity, electrical ratings and physical safe-OFF behavior.
- power/ground/protection: UNRESOLVED — confirm common ground, supply headroom, inductive-load
  protection where applicable and safe power-up/power-loss states before connecting loads.

Record the selected values in repository documentation before adding each concrete backend. Do not
hide these choices inside driver code.

## Stage27 bring-up order

1. Connect and implement real inputs while keeping all outputs fake.
2. Verify SCD41, outside BLE and RTC availability, measurement validity, age/freshness and schedule
   transitions through diagnostics before any physical load can be energized.
3. Exercise invalid, stale and unavailable real-input cases and confirm the existing fail-closed
   behavior matches host/HIL evidence.
4. Add the physical output endpoint beneath `MappedClimateRoleDriver`, initially in Rule mode only.
5. Bring up one semantic actuator role at a time and verify endpoint mapping, normalized level,
   explicit OFF, rejection handling, fail-safe OFF and the actuator fault latch.
6. Verify that rejected physical writes never advance confirmed/effective applied state.
7. Run ML only as `MlShadow` while collecting real traces. Do not enable `MlActive` from simulator or
   fake-runtime evidence.
8. Re-qualify active ML from real data before considering real actuation authority.

## Evidence required during physical bring-up

For every real input/output backend, retain evidence for:

- exact source revision and hardware configuration;
- detected device/part identity where available;
- bounded startup and diagnostics logs;
- normal readings/writes plus stale/unavailable/rejection cases;
- confirmed safe OFF behavior;
- no panic/reset loop during the bounded validation window;
- Rule-authoritative operation before any ML shadow collection.

A successful ESP-IDF build, host test or fake-runtime run is not a substitute for these physical
checks.
