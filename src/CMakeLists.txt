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
    "climate/application/ClimateIoAdapters.cpp"
    "climate/application/ClimateApplication.cpp"
    "climate/application/ClimateCompositeInput.cpp"
    "climate/application/ClimateSemanticOutput.cpp"
    "climate/ClimateObservabilityMetrics.cpp"
    "climate/rf433/ClimateRf433EndpointRegistry.cpp"
    "climate/rf433/Rf433OutputTransport.cpp"
    "climate/output/OutputStateStore.cpp"
    "climate/output/policy/OutputPolicyConfig.cpp"
    "climate/output/persistence/OutputPersistenceSchema.cpp"
    "climate/output/persistence/OutputPersistenceCoordinator.cpp"
    "climate/output/persistence/OutputPersistenceStore.cpp"
    "climate/output/persistence/OutputNvsBackend.cpp"
    "climate/output/lifecycle/OutputSupervisorLifecycle.cpp"
    "climate/output/lifecycle/OutputLifecycleExecutor.cpp"
    "climate/output/control/OutputAutomationControl.cpp"
    "climate/output/control/OutputManualControl.cpp"
    "climate/output/control/OutputMaintenanceControl.cpp"
    "climate/output/lifecycle/OutputRuntimeLifecycleControl.cpp"
    "climate/output/OutputExecutionProjection.cpp"
    "climate/output/OutputExecutionTelemetry.cpp"
    "climate/output/policy/BinaryActuatorPolicy.cpp"
    "climate/output/supervisor/OutputSupervisorResolver.cpp"
    "climate/output/supervisor/OutputSupervisorExecutor.cpp"
    "climate/output/supervisor/ClimateOutputSupervisorSink.cpp"
    "climate/Stage28dOutputBindings.cpp"
    "climate/Stage28dLampSafety.cpp"
    "climate/runtime/diagnostics/Stage28eBreadcrumbs.cpp"
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
      "climate/runtime/core/RealInputRuntimeComposition.cpp"
      "climate/runtime/core/RealInputRuntimeCoordinator.cpp"
      "climate/runtime/core/RuntimeOutputTransport.cpp"
      "climate/runtime/telemetry/RuntimeOutputTelemetryLog.cpp"
      "climate/runtime/core/RuntimeCycleState.cpp"
      "climate/runtime/schedule/EuropeWarsawTime.cpp"
      "climate/runtime/schedule/Stage27ScheduleProfile.cpp"
      "climate/runtime/schedule/Stage27ScheduleIntentAdapter.cpp"
      "climate/runtime/Stage27RuntimeAdapters.cpp"
      "climate/runtime/telemetry/Stage27TelemetryReporter.cpp"
      "climate/runtime/diagnostics/Stage28RfDiagnostics.cpp"
      "climate/runtime/Stage28MaintenanceRfTransport.cpp"
      "climate/runtime/console/Stage28ServiceConsole.cpp"
      "climate/runtime/console/ServiceConsoleTextSink.cpp"
      "climate/runtime/console/Stage28ServiceConsoleOutputCommands.cpp"
      "climate/runtime/console/Stage28ServiceConsoleStorageCommands.cpp"
      "climate/runtime/console/Stage28ServiceConsoleSystemCommands.cpp"
      "climate/runtime/console/Stage28ServiceConsoleCommand.cpp"
      "climate/runtime/console/Stage28ServiceConsoleRouter.cpp"
      "climate/runtime/diagnostics/Stage28eLog.cpp"
      "climate/telemetry/Stage27LogFormat.cpp"
      "climate/storage/Stage27TelemetryLogger.cpp"
      "climate/storage/Stage27FileDurability.cpp"
      "climate/storage/Stage27SdStorageBackend.cpp"
      "climate/storage/Stage27FlashStorageBackend.cpp"
      "climate/storage/crowpanel/CrowPanelSdPrecondition.cpp"
      "climate/input/ble/BthomeV2Decoder.cpp"
      "climate/input/ble/Tp357Decoder.cpp"
      "climate/input/ble/BleClimateState.cpp"
      "climate/input/ble/BleClimateScanner.cpp"
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

# Keep only switches that are intentionally consumed by the preprocessor. Runtime values are
# available exclusively through the generated RuntimeBuildConfig.h typed interface.
target_compile_definitions(
  ${COMPONENT_LIB}
  PRIVATE
    GROWBOX_APP_CLIMATE_V6_FAKE=${GROWBOX_APP_CLIMATE_V6_FAKE}
    GROWBOX_APP_CLIMATE_V6_REAL_INPUTS=${GROWBOX_APP_CLIMATE_V6_REAL_INPUTS}
    GROWBOX_STAGE28E_LOG_COMPILE_LEVEL=${GROWBOX_STAGE28E_LOG_COMPILE_LEVEL}
    GROWBOX_STAGE28E_BREADCRUMB_RESTART_SELFTEST=${GROWBOX_STAGE28E_BREADCRUMB_RESTART_SELFTEST}
)
