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
    bt
    esp_driver_i2c
    esp_driver_gpio
    nvs_flash
    sensirion_scd4x
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
      "climate/native/BthomeV2Decoder.cpp"
      "climate/native/Tp357Decoder.cpp"
      "climate/native/BleClimateState.cpp"
      "climate/native/BleClimateScanner.cpp"
      "climate/native/Ds3231Codec.cpp"
      "climate/native/NativeI2cBus.cpp"
      "climate/native/Scd41InsideSource.cpp"
      "climate/native/Ds3231ClockSource.cpp"
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
)
