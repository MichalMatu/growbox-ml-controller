idf_component_register(
  SRCS
    "main.cpp"
    "climate/ClimateIoAdapters.cpp"
    "climate/ClimateApplication.cpp"
    "climate/ClimateCompositeInput.cpp"
    "climate/ClimateSemanticOutput.cpp"
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
)

target_compile_features(${COMPONENT_LIB} PUBLIC cxx_std_17)
target_compile_options(${COMPONENT_LIB} PRIVATE -Wall -Wextra -Wpedantic)

set(GROWBOX_APP_MODE "legacy" CACHE STRING "Growbox application runtime")
set_property(CACHE GROWBOX_APP_MODE PROPERTY STRINGS "legacy" "climate-v6-fake")
if(GROWBOX_APP_MODE STREQUAL "legacy")
  set(GROWBOX_APP_CLIMATE_V6_FAKE 0)
elseif(GROWBOX_APP_MODE STREQUAL "climate-v6-fake")
  set(GROWBOX_APP_CLIMATE_V6_FAKE 1)
else()
  message(FATAL_ERROR "Unsupported GROWBOX_APP_MODE: ${GROWBOX_APP_MODE}")
endif()

if(NOT DEFINED GROWBOX_BOARD_PROFILE)
  set(GROWBOX_BOARD_PROFILE "esp32s3-devkitc1-n16r8")
endif()
target_compile_definitions(
  ${COMPONENT_LIB}
  PRIVATE
    GROWBOX_BOARD_PROFILE="${GROWBOX_BOARD_PROFILE}"
    GROWBOX_APP_CLIMATE_V6_FAKE=${GROWBOX_APP_CLIMATE_V6_FAKE}
)
