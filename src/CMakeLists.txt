idf_component_register(
  SRCS
    "main.cpp"
    "climate/ClimateIoAdapters.cpp"
    "climate/ClimateApplication.cpp"
    "climate/ClimateCompositeInput.cpp"
    "climate/ClimateSemanticOutput.cpp"
    "climate/ClimateObservabilityMetrics.cpp"
    "climate/rf433/ClimateRf433EndpointRegistry.cpp"
    "climate/Stage28dOutputBindings.cpp"
    "climate/Stage28dLampSafety.cpp"
    "climate/Stage28dBinaryRoleArbiter.cpp"
    "climate/Stage28dRfOutputEndpoint.cpp"
    "climate/Stage28dThermalTestSequence.cpp"
    "climate/ClimateDeterministicFake.cpp"
    "climate/ClimateDiagnostics.cpp"
    "climate/ClimateV6FakeRuntime.cpp"
    "demo/DummyEnvironmentSimulator.cpp"
    "demo/SerialJsonProtocol.cpp"
    "demo/protocol/JsonLineWriter.cpp"
    "demo/protocol/ScenarioWireCodec.cpp"
    "demo/protocol/DecisionWireCodec.cpp"
    "demo/protocol/DiagnosticsWireCodec.cpp"
    "demo/protocol/HeapDiagnostics.cpp"
    "demo/protocol/StatusWireCodec.cpp"
  INCLUDE_DIRS
    "."
    "demo"
  REQUIRES
    environment_control
    esp_driver_usb_serial_jtag
    esp_timer
    heap
    json
    bt
    esp_driver_i2c
    esp_driver_gpio
    esp_driver_rmt
    esp_driver_uart
    nvs_flash
    sensirion_scd4x
    fatfs
    sdmmc
    esp_driver_spi
    esp_driver_sdspi
    wear_levelling
    mbedtls
    espcoredump
)

target_compile_features(${COMPONENT_LIB} PUBLIC cxx_std_17)
target_compile_options(${COMPONENT_LIB} PRIVATE -Wall -Wextra -Wpedantic)

set(GROWBOX_APP_MODE "legacy" CACHE STRING "Growbox application runtime")
set_property(
  CACHE GROWBOX_APP_MODE
  PROPERTY STRINGS "legacy" "climate-v6-fake" "climate-v6-real-inputs"
)
if(GROWBOX_APP_MODE STREQUAL "legacy")
  set(GROWBOX_APP_CLIMATE_V6_FAKE 0)
  set(GROWBOX_APP_CLIMATE_V6_REAL_INPUTS 0)
elseif(GROWBOX_APP_MODE STREQUAL "climate-v6-fake")
  set(GROWBOX_APP_CLIMATE_V6_FAKE 1)
  set(GROWBOX_APP_CLIMATE_V6_REAL_INPUTS 0)
elseif(GROWBOX_APP_MODE STREQUAL "climate-v6-real-inputs")
  set(GROWBOX_APP_CLIMATE_V6_FAKE 0)
  set(GROWBOX_APP_CLIMATE_V6_REAL_INPUTS 1)
  target_sources(
    ${COMPONENT_LIB}
    PRIVATE
      "climate/ClimateV6RealInputRuntime.cpp"
      "climate/runtime/EuropeWarsawTime.cpp"
      "climate/runtime/Stage27ScheduleProfile.cpp"
      "climate/runtime/Stage27RuntimeAdapters.cpp"
      "climate/runtime/Stage27TelemetryReporter.cpp"
      "climate/runtime/Stage28RfDiagnostics.cpp"
      "climate/runtime/Stage28ServiceConsole.cpp"
      "climate/runtime/Stage28ServiceConsoleCommand.cpp"
      "climate/runtime/Stage28eLog.cpp"
      "climate/telemetry/Stage27LogFormat.cpp"
      "climate/storage/Stage27TelemetryLogger.cpp"
      "climate/storage/Stage27FileDurability.cpp"
      "climate/storage/Stage27SdStorageBackend.cpp"
      "climate/storage/Stage27FlashStorageBackend.cpp"
      "climate/storage/crowpanel/CrowPanelSdPrecondition.cpp"
      "climate/native/BthomeV2Decoder.cpp"
      "climate/native/Tp357Decoder.cpp"
      "climate/native/BleClimateState.cpp"
      "climate/native/BleClimateScanner.cpp"
      "climate/native/Ds3231Codec.cpp"
      "climate/native/NativeI2cBus.cpp"
      "climate/native/Scd41InsideSource.cpp"
      "climate/native/Ds3231ClockSource.cpp"
      "climate/rf433/Rf433ProtocolCodec.cpp"
      "climate/rf433/Rf433RmtLoopback.cpp"
  )
else()
  message(FATAL_ERROR "Unsupported GROWBOX_APP_MODE: ${GROWBOX_APP_MODE}")
endif()

if(NOT DEFINED GROWBOX_BOARD_PROFILE)
  set(GROWBOX_BOARD_PROFILE "esp32s3-devkitc1-n16r8")
endif()
set(GROWBOX_I2C_SDA_GPIO "8" CACHE STRING "Stage27 shared I2C SDA GPIO")
set(GROWBOX_I2C_SCL_GPIO "9" CACHE STRING "Stage27 shared I2C SCL GPIO")
set(GROWBOX_BLE_TP357_MAC "" CACHE STRING "Stage27 TP357 inside sensor MAC")
set(GROWBOX_BLE_XIAOMI_MAC "" CACHE STRING "Stage27 Xiaomi nearby BTHome sensor MAC")
set(GROWBOX_FIRMWARE_GIT_SHA "unknown" CACHE STRING "Exact Git SHA embedded in Stage27 firmware")
set(GROWBOX_STAGE27_SD_ENABLED "0" CACHE STRING "Enable Stage27 SD telemetry backend")
set(GROWBOX_STAGE27_FLASH_FALLBACK_ENABLED "0" CACHE STRING "Enable Stage27 internal-flash telemetry fallback")
set(GROWBOX_SD_CMD0_PRECONDITION "0" CACHE STRING "Enable CrowPanel SD CMD0 compatibility precondition")
set(GROWBOX_SD_MOSI_GPIO "40" CACHE STRING "Stage27 SD SPI MOSI GPIO")
set(GROWBOX_SD_MISO_GPIO "13" CACHE STRING "Stage27 SD SPI MISO GPIO")
set(GROWBOX_SD_SCLK_GPIO "39" CACHE STRING "Stage27 SD SPI clock GPIO")
set(GROWBOX_SD_CS_GPIO "10" CACHE STRING "Stage27 SD SPI chip-select GPIO")
set(GROWBOX_SD_POWER_GPIO "-1" CACHE STRING "Stage27 SD power-enable GPIO")
set(GROWBOX_RF433_LOOPBACK_ENABLED "0" CACHE STRING "Enable Stage28 RF433 loopback transport")
set(GROWBOX_RF433_LOOPBACK_AUTO_SMOKE "0" CACHE STRING "Run one Stage28 RF433 boot loopback smoke")
set(GROWBOX_RF433_REMOTE_CAPTURE_ENABLED "0" CACHE STRING "Enable Stage28C passive remote capture diagnostics")
set(GROWBOX_RF433_LOOPBACK_SMOKE_CODE "0xA55A" CACHE STRING "Stage28 RF433 loopback smoke code")
set(GROWBOX_RF433_LOOPBACK_SMOKE_BITS "16" CACHE STRING "Stage28 RF433 loopback smoke bit length")
set(GROWBOX_RF433_LOOPBACK_SMOKE_PROTOCOL "1" CACHE STRING "Stage28 RF433 loopback smoke protocol")
set(GROWBOX_RF433_LOOPBACK_SMOKE_REPEAT "3" CACHE STRING "Stage28 RF433 loopback smoke repeat count")
set(GROWBOX_RF433_LOOPBACK_SMOKE_PULSE_US "0" CACHE STRING "Stage28 RF433 loopback smoke pulse length; 0 uses protocol default")
set(GROWBOX_RF433_TX_GPIO "8" CACHE STRING "Stage28 RF433 TX GPIO")
set(GROWBOX_RF433_RX_GPIO "14" CACHE STRING "Stage28 RF433 RX GPIO")
set(GROWBOX_STAGE28_SERVICE_CONSOLE_ENABLED "1" CACHE STRING "Enable Stage28 primary-serial service console")
set(GROWBOX_STAGE28_REAL_OUTPUTS_ENABLED "0" CACHE STRING "Enable bounded Stage28 real RF outputs")
set(GROWBOX_STAGE28_THERMAL_TEST_SEQUENCE_ENABLED "0" CACHE STRING "Enable bounded Gate6 thermal test sequence")
set(GROWBOX_STAGE28E_LOG_COMPILE_LEVEL "2" CACHE STRING "Stage28E diagnostic compile-time log level 0=ERROR..4=TRACE")

target_compile_definitions(
  ${COMPONENT_LIB}
  PRIVATE
    GROWBOX_BOARD_PROFILE="${GROWBOX_BOARD_PROFILE}"
    GROWBOX_APP_CLIMATE_V6_FAKE=${GROWBOX_APP_CLIMATE_V6_FAKE}
    GROWBOX_APP_CLIMATE_V6_REAL_INPUTS=${GROWBOX_APP_CLIMATE_V6_REAL_INPUTS}
    GROWBOX_I2C_SDA_GPIO=${GROWBOX_I2C_SDA_GPIO}
    GROWBOX_I2C_SCL_GPIO=${GROWBOX_I2C_SCL_GPIO}
    GROWBOX_BLE_TP357_MAC="${GROWBOX_BLE_TP357_MAC}"
    GROWBOX_BLE_XIAOMI_MAC="${GROWBOX_BLE_XIAOMI_MAC}"
    GROWBOX_FIRMWARE_GIT_SHA="${GROWBOX_FIRMWARE_GIT_SHA}"
    GROWBOX_STAGE27_SD_ENABLED=${GROWBOX_STAGE27_SD_ENABLED}
    GROWBOX_STAGE27_FLASH_FALLBACK_ENABLED=${GROWBOX_STAGE27_FLASH_FALLBACK_ENABLED}
    GROWBOX_SD_CMD0_PRECONDITION=${GROWBOX_SD_CMD0_PRECONDITION}
    GROWBOX_SD_MOSI_GPIO=${GROWBOX_SD_MOSI_GPIO}
    GROWBOX_SD_MISO_GPIO=${GROWBOX_SD_MISO_GPIO}
    GROWBOX_SD_SCLK_GPIO=${GROWBOX_SD_SCLK_GPIO}
    GROWBOX_SD_CS_GPIO=${GROWBOX_SD_CS_GPIO}
    GROWBOX_SD_POWER_GPIO=${GROWBOX_SD_POWER_GPIO}
    GROWBOX_RF433_LOOPBACK_ENABLED=${GROWBOX_RF433_LOOPBACK_ENABLED}
    GROWBOX_RF433_LOOPBACK_AUTO_SMOKE=${GROWBOX_RF433_LOOPBACK_AUTO_SMOKE}
    GROWBOX_RF433_REMOTE_CAPTURE_ENABLED=${GROWBOX_RF433_REMOTE_CAPTURE_ENABLED}
    GROWBOX_RF433_LOOPBACK_SMOKE_CODE=${GROWBOX_RF433_LOOPBACK_SMOKE_CODE}
    GROWBOX_RF433_LOOPBACK_SMOKE_BITS=${GROWBOX_RF433_LOOPBACK_SMOKE_BITS}
    GROWBOX_RF433_LOOPBACK_SMOKE_PROTOCOL=${GROWBOX_RF433_LOOPBACK_SMOKE_PROTOCOL}
    GROWBOX_RF433_LOOPBACK_SMOKE_REPEAT=${GROWBOX_RF433_LOOPBACK_SMOKE_REPEAT}
    GROWBOX_RF433_LOOPBACK_SMOKE_PULSE_US=${GROWBOX_RF433_LOOPBACK_SMOKE_PULSE_US}
    GROWBOX_RF433_TX_GPIO=${GROWBOX_RF433_TX_GPIO}
    GROWBOX_RF433_RX_GPIO=${GROWBOX_RF433_RX_GPIO}
    GROWBOX_STAGE28_SERVICE_CONSOLE_ENABLED=${GROWBOX_STAGE28_SERVICE_CONSOLE_ENABLED}
    GROWBOX_STAGE28_REAL_OUTPUTS_ENABLED=${GROWBOX_STAGE28_REAL_OUTPUTS_ENABLED}
    GROWBOX_STAGE28_THERMAL_TEST_SEQUENCE_ENABLED=${GROWBOX_STAGE28_THERMAL_TEST_SEQUENCE_ENABLED}
    GROWBOX_STAGE28E_LOG_COMPILE_LEVEL=${GROWBOX_STAGE28E_LOG_COMPILE_LEVEL}
)
