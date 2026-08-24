# MVP Hardware Sensor Set

Status: provisional hardware set for the standalone growbox controller.

The controller core remains hardware-independent. This document records the first practical sensor set intended for the embedded MVP.

## Planned sensors

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

### Leaf temperature

Low-cost contact temperature sensor using a small NTC thermistor mounted in a lightweight leaf clip.

Provides:

- `leaf_temperature_c`

The sensor should contact the leaf gently and add as little thermal mass and shading as practical. It measures leaf temperature only; no separate humidity sensor is attached to the leaf.

When a valid leaf temperature is available, the controller can calculate `leaf_vpd_kpa` from leaf temperature plus ambient RH. If the leaf sensor is missing, stale or invalid, control falls back to air VPD calculated from SCD41 air temperature and RH.

## Resulting MVP measurement set

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

PLANT
NTC leaf clip
  leaf temperature

DERIVED
  air VPD
  leaf VPD when leaf temperature is valid
  outside VPD when outside T/RH are valid
```

## Not planned for the first hardware MVP

- SHT45 or another duplicate inside T/RH sensor
- IR leaf-temperature sensor
- leaf humidity sensor
- PPFD sensor
- soil moisture
- EC/pH

Expansion remains possible later without changing the semantic controller contract.
