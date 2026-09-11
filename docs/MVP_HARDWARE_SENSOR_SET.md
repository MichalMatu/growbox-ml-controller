# MVP Hardware Sensor Set

Status: Stage27 hardware direction frozen at product level; exact native driver/component choices remain subject to the Stage27A source audit.

The controller core remains hardware-independent. This document records the first practical sensor/system set intended for the embedded MVP.

## Framework constraint

The first hardware MVP must remain **100% native ESP-IDF v5.5.4**.

- Do not add Arduino-ESP32 as a component.
- Do not migrate the project to PlatformIO/Arduino.
- Existing Arduino/PlatformIO projects may be used as reference sources for proven hardware behavior, pin maps, protocol parsing and pure logic only.
- If the preferred CrowPanel board requires a substantial Arduino-only stack, use a plain ESP32-S3 devboard instead.

See `docs/STAGE27_NATIVE_IDF_HANDOFF.md` for the complete platform decision gate.

## Planned sensors and required system hardware

### Inside growbox — FROZEN PART

`SCD41`

Provides:

- `air_temperature_c`
- `relative_humidity_pct`
- `co2_ppm`

For the first hardware MVP, these readings are sufficient as the primary inside-air measurements. No additional SHT45-class temperature/RH sensor is required.

The exact SCD4x/SCD41 native ESP-IDF driver/component is selected during Stage27A. Failed reads must remain unavailable/invalid rather than becoming synthetic values, and only an accepted valid measurement may refresh climate freshness.

### Outside growbox — FUNCTION FROZEN, MODEL/PROTOCOL PENDING AUDIT

BLE temperature/humidity sensor.

Provides:

- `outside_temperature_c`
- `outside_humidity_pct`

The implementation uses native ESP-IDF NimBLE. The exact outside sensor/model and advertisement protocol are selected during Stage27A. Existing Xiaomi/PVVX/BTHome-compatible code in the user's donor repositories is a strong source of protocol behavior and test fixtures.

The configured sensor must be selected deterministically by a stable identity; an arbitrary strongest compatible nearby sensor must not become the controller input. Packet-seen time and last-valid-measurement time are separate diagnostics/semantics.

### Real-time clock — FROZEN PART

`DS3231` with backup battery is the selected hardware RTC for the first embedded MVP.

Provides:

- persistent `current_time`
- reliable DAY/NIGHT profile switching
- light schedule operation after restart
- schedule operation without Wi-Fi or Internet access

The exact native ESP-IDF DS3231 component/driver is selected during Stage27A. The implementation must expose trusted validity separately from mere bus availability/readability. Oscillator-stop/lost-power/untrusted time must not be accepted as a valid schedule time until intentionally set/synchronized.

Network time may be used to synchronize the RTC when available, but the controller must not depend on network connectivity for normal scheduling.

## Resulting MVP measurement/system set

```text
INSIDE
SCD41
  air temperature
  relative humidity
  CO2

OUTSIDE
BLE sensor via native ESP-IDF NimBLE
  outside temperature
  outside humidity

SYSTEM
DS3231 + backup battery
  current time
  DAY/NIGHT schedule continuity

DERIVED
  air VPD
  outside VPD when outside T/RH are valid
```

## Board/platform direction

Preferred first board is the Elecrow CrowPanel 2.9-inch e-paper ESP32-S3 already used with the user's LiteGraph/custom-HAT hardware, but only if Stage27A confirms a clean native ESP-IDF path for the exact board/display/buttons.

Fallback is a plain inexpensive ESP32-S3 devboard. E-paper/buttons are useful but optional; a cheap display and rotary encoder may be added later.

Sensors/control correctness outrank preserving the CrowPanel UI.

## Must be provided on or connected to the controller

- ESP32-S3 platform selected by Stage27A;
- SCD41;
- DS3231 with backup power.

The BLE outside sensor remains external and wireless.

SCD41 and DS3231 should preferably share one explicitly owned native ESP-IDF I2C bus when the selected board/HAT wiring permits it.

## Not planned for the first hardware MVP

- SHT45 or another duplicate inside T/RH sensor
- leaf-temperature sensor (contact NTC or IR)
- leaf humidity sensor
- leaf VPD
- PPFD sensor
- soil moisture
- EC/pH

Leaf temperature was intentionally removed from MVP v1 to keep the hardware, simulator and ML training dataset simpler. It can be reconsidered later only if it provides measurable value.

Expansion remains possible later without changing the semantic controller contract.

## Integration order

Do not couple the climate core directly to a sensor library. Concrete hardware remains behind `src/climate/ClimateIoAdapters.*` and the composite input seam.

1. Stage27A: audit official/native sources; decide CrowPanel vs bare ESP32-S3; freeze native SCD41 driver, BLE sensor/protocol, DS3231 driver and bus/pin assumptions.
2. Stage27B: implement the complete real SCD41 + BLE + DS3231 input bundle while physical outputs remain fake/locked.
3. Stage27C: physically validate validity/freshness/unavailable/lost-time behavior and diagnostics.
4. Only after real-input validation, map physical output endpoints to semantic actuator roles and bring them up one role at a time in Rule mode.
5. Use `MlShadow` for real trace collection; do not enable active ML until it is re-qualified from real data.

No board/soldering choice changes the 44-feature/6-output climate-v6 semantic contract.
