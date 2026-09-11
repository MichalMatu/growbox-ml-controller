if(NOT DEFINED GROWBOX_APP_MODE OR GROWBOX_APP_MODE STREQUAL "")
  set(GROWBOX_APP_MODE "$ENV{GROWBOX_APP_MODE}")
endif()
if(GROWBOX_APP_MODE STREQUAL "")
  message(FATAL_ERROR "GROWBOX_APP_MODE was not exported by the project root")
endif()

idf_component_register(
  SRCS
    "main.cpp"
    "demo/protocol/HeapDiagnostics.cpp"
    "climate/ClimateIoAdapters.cpp"
    "climate/ClimateApplication.cpp"
    "climate/ClimateCompositeInput.cpp"
    "climate/ClimateSemanticOutput.cpp"
    "climate/ClimateObservabilityMetrics.cpp"
    "climate/rf433/ClimateRf433EndpointRegistry.cpp"
    "climate/rf433/Rf433OutputTransport.cpp"
    "climate/output/OutputStateStore.cpp"
    "climate/output/OutputPolicyConfig.cpp"
    "climate/output/OutputPersistenceSchema.cpp"
    "climate/output/OutputPersistenceCoordinator.cpp"
    "climate/output/OutputPersistenceStore.cpp"
    "climate/output/OutputNvsBackend.cpp"
    "climate/output/OutputSupervisorLifecycle.cpp"
    "climate/output/OutputLifecycleExecutor.cpp"
    "climate/output/OutputAutomationControl.cpp"
    "climate/output/OutputManualControl.cpp"
    "climate/output/OutputMaintenanceControl.cpp"
    "climate/output/OutputRuntimeLifecycleControl.cpp"
    "climate/output/OutputExecutionProjection.cpp"
    "climate/output/OutputExecutionTelemetry.cpp"
    "climate/output/BinaryActuatorPolicy.cpp"
    "climate/output/OutputSupervisorResolver.cpp"
    "climate/output/OutputSupervisorExecutor.cpp"
    "climate/output/ClimateOutputSupervisorSink.cpp"
    "climate/Stage28dOutputBindings.cpp"
    "climate/Stage28dLampSafety.cpp"
    "climate/Stage28dThermalTestSequence.cpp"
    "climate/runtime/Stage28eBreadcrumbs.cpp"
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

if(GROWBOX_APP_MODE STREQUAL "legacy")
  set(GROWBOX_APP_CLIMATE_V6_FAKE 0)
  set(GROWBOX_APP_CLIMATE_V6_REAL_INPUTS 0)
  target_sources(
    ${COMPONENT_LIB}
    PRIVATE
      "legacy/LegacyRuntime.cpp"
      "demo/DummyEnvironmentSimulator.cpp"
      "demo/SerialJsonProtocol.cpp"
      "demo/protocol/JsonLineWriter.cpp"
      "demo/protocol/ScenarioWireCodec.cpp"
      "demo/protocol/DecisionWireCodec.cpp"
      "demo/protocol/DiagnosticsWireCodec.cpp"
      "demo/protocol/StatusWireCodec.cpp"
  )
elseif(GROWBOX_APP_MODE STREQUAL "climate-v6-fake")
  set(GROWBOX_APP_CLIMATE_V6_FAKE 1)
  set(GROWBOX_APP_CLIMATE_V6_REAL_INPUTS 0)
  target_sources(
    ${COMPONENT_LIB}
    PRIVATE
      "climate/ClimateV6FakeRuntime.cpp"
      "climate/ClimateDeterministicFake.cpp"
      "climate/ClimateDiagnostics.cpp"
      "demo/protocol/JsonLineWriter.cpp"
  )
elseif(GROWBOX_APP_MODE STREQUAL "climate-v6-real-inputs")
  set(GROWBOX_APP_CLIMATE_V6_FAKE 0)
  set(GROWBOX_APP_CLIMATE_V6_REAL_INPUTS 1)
  target_sources(
    ${COMPONENT_LIB}
    PRIVATE
      "climate/ClimateV6RealInputRuntime.cpp"
      "climate/runtime/RealInputRuntimeComposition.cpp"
      "climate/runtime/RealInputRuntimeCoordinator.cpp"
      "climate/runtime/RuntimeCycleState.cpp"
      "climate/runtime/EuropeWarsawTime.cpp"
      "climate/runtime/Stage27ScheduleProfile.cpp"
      "climate/runtime/Stage27ScheduleIntentAdapter.cpp"
      "climate/runtime/Stage27RuntimeAdapters.cpp"
      "climate/runtime/Stage27TelemetryReporter.cpp"
      "climate/runtime/Stage28RfDiagnostics.cpp"
      "climate/runtime/Stage28MaintenanceRfTransport.cpp"
      "climate/runtime/Stage28ServiceConsole.cpp"
      "climate/runtime/ServiceConsoleTextSink.cpp"
      "climate/runtime/Stage28ServiceConsoleOutputCommands.cpp"
      "climate/runtime/Stage28ServiceConsoleStorageCommands.cpp"
      "climate/runtime/Stage28ServiceConsoleSystemCommands.cpp"
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
      "climate/rf433/Rf433RmtFrameSender.cpp"
  )
else()
  message(FATAL_ERROR "Unsupported GROWBOX_APP_MODE: ${GROWBOX_APP_MODE}")
endif()

get_filename_component(GROWBOX_PROJECT_ROOT "${CMAKE_CURRENT_LIST_DIR}/.." ABSOLUTE)
include("${GROWBOX_PROJECT_ROOT}/config/runtime/GrowboxRuntimeConfig.cmake")

set(GROWBOX_GENERATED_INCLUDE_DIR "${CMAKE_CURRENT_BINARY_DIR}/generated")
file(MAKE_DIRECTORY "${GROWBOX_GENERATED_INCLUDE_DIR}/climate/runtime")
configure_file(
  "${CMAKE_CURRENT_LIST_DIR}/climate/runtime/RuntimeBuildConfig.h.in"
  "${GROWBOX_GENERATED_INCLUDE_DIR}/climate/runtime/RuntimeBuildConfig.h"
  @ONLY
)
target_include_directories(${COMPONENT_LIB} PRIVATE "${GROWBOX_GENERATED_INCLUDE_DIR}")

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
    GROWBOX_RF433_REMOTE_CAPTURE_ENABLED=${GROWBOX_RF433_REMOTE_CAPTURE_ENABLED}
    GROWBOX_RF433_TX_GPIO=${GROWBOX_RF433_TX_GPIO}
    GROWBOX_RF433_RX_GPIO=${GROWBOX_RF433_RX_GPIO}
    GROWBOX_STAGE28_SERVICE_CONSOLE_ENABLED=${GROWBOX_STAGE28_SERVICE_CONSOLE_ENABLED}
    GROWBOX_STAGE28_REAL_OUTPUTS_ENABLED=${GROWBOX_STAGE28_REAL_OUTPUTS_ENABLED}
    GROWBOX_STAGE28_THERMAL_TEST_SEQUENCE_ENABLED=${GROWBOX_STAGE28_THERMAL_TEST_SEQUENCE_ENABLED}
    GROWBOX_STAGE28E_LOG_COMPILE_LEVEL=${GROWBOX_STAGE28E_LOG_COMPILE_LEVEL}
    GROWBOX_STAGE28E_BREADCRUMB_RESTART_SELFTEST=${GROWBOX_STAGE28E_BREADCRUMB_RESTART_SELFTEST}
)
