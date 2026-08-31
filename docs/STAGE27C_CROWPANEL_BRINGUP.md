# Stage27C CrowPanel physical bring-up

Date: 2026-08-31
Work branch: `mvp/environment-controller`

This document freezes the first physical Stage27C configuration for the user's actual Elecrow CrowPanel ESP32-S3 2.9-inch HAT setup. E-paper and front-panel UI remain intentionally deferred. Physical actuator outputs remain fake/locked.

## Board and bus

- board: Elecrow CrowPanel ESP32-S3 2.9-inch e-paper HMI;
- module class: N8R8, 8 MB flash + 8 MB octal PSRAM;
- shared primary I2C: SDA GPIO21, SCL GPIO38;
- SCD41 address: `0x62`;
- DS3231 address: `0x68`;
- e-paper: not initialized by Stage27C climate bring-up;
- physical growbox outputs: not enabled.

The Stage27C build uses `config/idf/sdkconfig.defaults.n8r8` plus the existing Stage27 native BLE overlay and stores its generated sdkconfig inside the dedicated build directory so stale root sdkconfig state cannot override the requested configuration.

## Physical sensors

| Sensor | Identity/location | Stage27C role |
| --- | --- | --- |
| TP357 | BLE MAC `F7:5F:8D:0F:76:20`, physically inside growbox | intended primary inside temperature/RH source after the dual-BLE Stage27C adaptation |
| Xiaomi LYWSD03MMC + PVVX/BTHome | BLE MAC `A4:C1:38:4F:24:CD`, physically on/near growbox | ambient BLE temperature/RH source |
| SCD41 | I2C, physically near window | CO2 + local window-area temperature/RH diagnostic source |
| DS3231 | I2C on HAT | trusted wall-clock source |

Do not calculate calibration offsets between these sensors during the overnight test because they are intentionally placed in different physical locations.

## Bring-up command

```bash
bash scripts/stage27c_crowpanel.sh build
bash scripts/stage27c_crowpanel.sh flash
bash scripts/stage27c_crowpanel.sh monitor
```

`PORT=/dev/cu...` may be supplied when automatic serial-port detection is ambiguous.

Until the TP357 path is adapted into the native runtime, the Stage27C helper defaults `GROWBOX_BLE_OUTSIDE_MAC` to the Xiaomi BTHome sensor so the existing Stage27B BLE path can be physically validated first.

## Ordered validation

1. Build CrowPanel N8R8 firmware with I2C GPIO21/38 and fake/locked outputs.
2. Flash and verify SCD41 + DS3231 discovery and plausible live readings.
3. Adapt the proven LiteGraph TP357 manufacturer-data decoder into a pure native decoder and scan both configured BLE MACs concurrently.
4. Map TP357 as the primary inside T/RH source while retaining SCD41 CO2 and its own local T/RH diagnostics; Xiaomi remains the ambient BLE source.
5. Run a long unattended input soak with bounded diagnostics, uptime/heap/freshness/error counters and no e-paper work.
6. Perform only safe software-observable fault tests that do not require physical manipulation while unattended.
7. Freeze terminal evidence and update Stage27C status. Physical output work remains out of scope.
