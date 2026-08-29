# Stage27A native input feasibility freeze

Date: 2026-08-29
Work branch: `mvp/environment-controller`
Baseline before this freeze: `f7481cde3ecdab88d49be70b9b49042b56694ac2`

This document closes Stage27A. Stage25/26 remain closed and are not reopened here.

## Decision

Use a plain ESP32-S3 DevKitC-class board for the first Stage27 real-input bring-up. Keep CrowPanel 2.9-inch support deferred. The firmware remains 100% native ESP-IDF v5.5.4; Arduino-ESP32 is not permitted as a component or runtime dependency.

All physical outputs remain fake/locked during Stage27B/C.

## KEEP / ADAPT / REIMPLEMENT / DEFER / DROP

| Decision | Item | Frozen result |
| --- | --- | --- |
| KEEP | Existing climate-neutral ports and `CompositeClimateSnapshotProvider` | Real devices stay behind `InsideEnvironmentSource`, `OutsideEnvironmentSource`, and `ClimateClockSource`. |
| KEEP | Stage26 output safety boundary | No physical actuator driver is enabled in Stage27B. |
| ADAPT | Sensirion SCD4x embedded driver | Vendor the current `Sensirion/embedded-i2c-scd4x` C driver and implement only its platform HAL using ESP-IDF I2C. SCD41 address is `0x62`. Do not use the deprecated `Sensirion/embedded-scd` or Arduino wrapper. |
| ADAPT | ESP-IDF NimBLE | Use ESP-IDF's built-in NimBLE host/controller and passive GAP discovery. No NimBLE-Arduino/Arduino BLE layer. |
| ADAPT | LiteGraph BLE semantics/tests | Reuse only framework-independent BTHome v2 packet semantics and captured fixture shape. LiteGraph's current host fixture uses service data UUID `0xFCD2`, temperature object `0x02`, humidity object `0x03`, and a stable configured MAC. |
| REIMPLEMENT | BLE outside path | Native scanner -> advertisement extraction -> pure BTHome v2 decoder -> freshness/identity state -> `OutsideEnvironmentSource`. |
| REIMPLEMENT | DS3231 | Small native ESP-IDF I2C register driver for address `0x68`; availability and trusted validity remain distinct. Status register `0x0F` OSF bit 7 invalidates wall-clock time. |
| ADAPT | CrowPanel metadata | Board/pin/schematic knowledge may be referenced from Elecrow and `esp32s3_LiteGraph`, without importing its Arduino/GxEPD2 runtime. |
| DEFER | CrowPanel e-paper/buttons | Not required for input correctness. Revisit only after Stage27 input validation. |
| DROP | Arduino component, `Wire`, GxEPD2, Arduino BLE libraries | Must not enter the dependency graph. |
| DROP | LiteGraph renderer/UI/store and MatrixHub application runtime | Not needed for this controller. |

## Source audit

### Elecrow CrowPanel 2.9-inch

Official sources audited:

- Elecrow wiki: `https://www.elecrow.com/wiki/CrowPanel_ESP32_E-paper_2.9-inch_HMI_Display.html`
- Elecrow product page: `https://www.elecrow.com/crowpanel-esp32-2-9-e-paper-hmi-display-with-128-296-resolution-black-white-color-driven-by-spi-interface.html`
- Elecrow user manual: `https://www.elecrow.com/download/product/DIE01021S/User_Manual_for_ESP32_E-Paper_HMI_Display.pdf`

Confirmed common facts: ESP32-S3-WROOM-1-N8R8, 8 MB flash, 8 MB PSRAM, 128x296 e-paper, SPI, exposed GPIO and buttons.

The current official material is internally inconsistent about the 2.9-inch e-paper controller: the wiki names UC8253 while the product page/manual name SSD1680Z. Vendor demo material is Arduino-centric even though the wiki specification mentions ESP-IDF. The existing LiteGraph implementation also relies on Arduino/GxEPD2. Native display support is therefore disproportionate Stage27 risk and is deferred.

### SCD41

Official current source:

- `https://github.com/Sensirion/embedded-i2c-scd4x`

The old `Sensirion/embedded-scd` repository is explicitly deprecated in favor of `embedded-i2c-scd4x`. The current driver provides SCD41 support at address `0x62`, CRC/protocol handling and a replaceable `sensirion_i2c_hal` layer. Stage27B will adapt this driver with an ESP-IDF HAL rather than reimplementing the SCD4x protocol.

Required semantics: failed reads do not become zeros; only accepted measurements refresh freshness; temperature, RH and CO2 validity are preserved.

### DS3231

Official source:

- Analog Devices DS3231 data sheet: `https://www.analog.com/media/en/technical-documentation/data-sheets/ds3231.pdf`

The required subset is small enough to own locally. Read time/date registers and status register `0x0F`. OSF bit 7 means oscillator stopped/was stopped and the time must be treated as untrusted. A readable date is not sufficient for `valid=true`.

### BLE / BTHome v2

Official/current sources:

- ESP-IDF ESP32-S3 BLE/NimBLE documentation and `examples/bluetooth/nimble/blecent`
- BTHome v2 format: `https://bthome.io/format/`

Use passive ESP-IDF NimBLE scanning. Freeze the outside protocol to unencrypted BTHome v2 (`0xFCD2`) as emitted by PVVX-compatible Xiaomi LYWSD03MMC-class thermometers. Select exactly one configured BLE MAC; never select by RSSI/nearest device.

The first decoder scope is deliberately narrow: BTHome v2 device-info byte plus battery `0x01` (optional diagnostics), temperature `0x02` (signed LE, 0.01 C), and humidity `0x03` (unsigned LE, 0.01%). Encrypted packets are unsupported for the first MVP and must fail decoding without refreshing climate freshness.

Keep `last_packet_seen` separate from `last_valid_measurement`; malformed, partial, encrypted, wrong-device or battery-only packets never refresh temperature/RH freshness.

## Donor comparison frozen at current heads

- `MichalMatu/esp32s3_LiteGraph/main`: `58a1b86219e2be28ce88b02845f51b2bdf3666a8`
  - useful: CrowPanel pin/hardware knowledge, BTHome v2 fixture/identity/freshness semantics;
  - not reusable: Arduino/GxEPD2/Arduino BLE ownership or large application/UI layers.
- `MichalMatu/MatrixHub/develop`: `fd5df96c768cdaab647d3589775e1e838e2d2db3`
  - current code search contains no BTHome, NimBLE, SCD41 or DS3231 implementation worth porting for Stage27.

## Native Stage27B architecture

Use one explicit ESP-IDF I2C bus owner shared by SCD41 (`0x62`) and DS3231 (`0x68`). The DevKitC-class default wiring assumption is SDA GPIO8 and SCL GPIO9, configurable at build time and requiring physical confirmation before Stage27C.

The production composition is:

`shared I2C -> SCD41 inside source`

`ESP-IDF NimBLE -> BTHome decoder/state -> BLE outside source`

`shared I2C -> DS3231 clock source`

`inside + outside + clock + existing schedule/config source -> CompositeClimateSnapshotProvider -> ClimateApplication -> fake/locked role driver`

## Stage27B acceptance gates

- native ESP-IDF v5.5.4 build passes;
- no Arduino component/API/dependency;
- SCD41, BLE and DS3231 production classes compile and are wired through the neutral interfaces;
- one I2C bus owner is shared by SCD41 and DS3231;
- BTHome decoder/freshness/identity logic has host tests including the LiteGraph-compatible packet fixture;
- DS3231 BCD/range/OSF semantics have host-testable coverage;
- real-input runtime cannot energize physical outputs;
- hardware absence fails closed without converting failures into plausible measurements.
