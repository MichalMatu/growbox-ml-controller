# MVP Hardware Sensor Set

Status: provisional hardware set for the standalone growbox controller.

The controller core remains hardware-independent. This document records the first practical sensor/system set intended for the embedded MVP.

## Planned sensors and required system hardware

### Inside growbox

`SCD41`

Provides:

- `air_temperature_c`
- `relative_humidity_pct`
- `co2_ppm`

For the first hardware MVP, these readings are sufficient as the primary inside-air measurements. No additional SHT45-class temperature/RH sensor is required.

### Outside growbox

BLE temperature/humidity sensor.

Provides:

- `outside_temperature_c`
- `outside_humidity_pct`

The exact BLE sensor model is intentionally not frozen yet.

### Real-time clock — required onboard hardware

A hardware RTC with backup power is mandatory for the embedded MVP and should be soldered onto the controller hardware/PCB.

Provides:

- persistent `current_time`
- reliable DAY/NIGHT profile switching
- light schedule operation after restart
- schedule operation without Wi-Fi or Internet access

The exact RTC part is not frozen yet. The implementation should use a low-cost RTC with battery/supercapacitor backup. Candidate parts include DS3231-class or PCF8563-class devices.

Network time may be used to synchronize the RTC when available, but the controller must not depend on network connectivity for normal scheduling.

## Resulting MVP measurement/system set

```text
INSIDE
SCD41
  air temperature
  relative humidity
  CO2

OUTSIDE
BLE sensor
  outside temperature
  outside humidity

SYSTEM
hardware RTC + backup power
  current time
  DAY/NIGHT schedule continuity

DERIVED
  air VPD
  outside VPD when outside T/RH are valid
```

## Must be soldered / provided on the controller

- ESP32-S3
- SCD41
- hardware RTC with backup power

The BLE outside sensor remains external and wireless.

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
