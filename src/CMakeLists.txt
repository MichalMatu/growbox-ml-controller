idf_component_register(
  SRCS
    "main.cpp"
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

if(NOT DEFINED GROWBOX_BOARD_PROFILE)
  set(GROWBOX_BOARD_PROFILE "esp32s3-devkitc1-n16r8")
endif()
target_compile_definitions(
  ${COMPONENT_LIB}
  PRIVATE GROWBOX_BOARD_PROFILE="${GROWBOX_BOARD_PROFILE}"
)
