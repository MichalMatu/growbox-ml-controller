cmake_minimum_required(VERSION 3.16)
project(environment_control_host_tests LANGUAGES CXX)

set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

get_filename_component(PROJECT_ROOT "${CMAKE_CURRENT_LIST_DIR}/../.." ABSOLUTE)

add_executable(
  environment_control_tests
  "${PROJECT_ROOT}/test/test_environment_controller/test_main.cpp"
  "${PROJECT_ROOT}/lib/environment_control/src/EnvironmentController.cpp"
  "${PROJECT_ROOT}/lib/environment_control/src/EnvironmentTypes.cpp"
  "${PROJECT_ROOT}/lib/environment_control/src/FeatureEncoder.cpp"
  "${PROJECT_ROOT}/lib/environment_control/src/ModelRuntime.cpp"
  "${PROJECT_ROOT}/lib/environment_control/src/SafetySupervisor.cpp"
)

target_include_directories(
  environment_control_tests
  PRIVATE
    "${CMAKE_CURRENT_LIST_DIR}"
    "${PROJECT_ROOT}/lib/environment_control/src"
    "${PROJECT_ROOT}/tests/fixtures"
    "${PROJECT_ROOT}/components/emlearn_runtime/include"
)

target_compile_features(environment_control_tests PRIVATE cxx_std_17)
target_compile_options(environment_control_tests PRIVATE -Wall -Wextra -Wpedantic)

add_executable(
  climate_v6_tests
  "${PROJECT_ROOT}/test/test_climate_v6/test_main.cpp"
  "${PROJECT_ROOT}/lib/environment_control/src/climate/ClimateFeatureEncoder.cpp"
  "${PROJECT_ROOT}/lib/environment_control/src/climate/ClimateRuntimeController.cpp"
  "${PROJECT_ROOT}/lib/environment_control/src/climate/ClimateTrendEstimator.cpp"
)
target_include_directories(climate_v6_tests PRIVATE "${PROJECT_ROOT}/lib/environment_control/src/climate")
target_compile_features(climate_v6_tests PRIVATE cxx_std_17)
target_compile_options(climate_v6_tests PRIVATE -Wall -Wextra -Wpedantic)


add_executable(
  climate_runtime_parity_tests
  "${PROJECT_ROOT}/test/test_climate_runtime_parity/test_main.cpp"
  "${PROJECT_ROOT}/lib/environment_control/src/climate/ClimateFeatureEncoder.cpp"
  "${PROJECT_ROOT}/lib/environment_control/src/climate/ClimateRuntimeController.cpp"
  "${PROJECT_ROOT}/lib/environment_control/src/climate/ClimateTrendEstimator.cpp"
)
target_include_directories(
  climate_runtime_parity_tests
  PRIVATE
    "${PROJECT_ROOT}/lib/environment_control/src/climate"
    "${PROJECT_ROOT}/tests/fixtures"
)
target_compile_features(climate_runtime_parity_tests PRIVATE cxx_std_17)
target_compile_options(climate_runtime_parity_tests PRIVATE -Wall -Wextra -Wpedantic)

add_executable(
  climate_control_loop_tests
  "${PROJECT_ROOT}/test/test_climate_control_loop/test_main.cpp"
  "${PROJECT_ROOT}/lib/environment_control/src/climate/ClimateControlLoop.cpp"
  "${PROJECT_ROOT}/lib/environment_control/src/climate/ClimateFeatureEncoder.cpp"
  "${PROJECT_ROOT}/lib/environment_control/src/climate/ClimateRuntimeController.cpp"
  "${PROJECT_ROOT}/lib/environment_control/src/climate/ClimateTrendEstimator.cpp"
)
target_include_directories(climate_control_loop_tests PRIVATE "${PROJECT_ROOT}/lib/environment_control/src/climate")
target_compile_features(climate_control_loop_tests PRIVATE cxx_std_17)
target_compile_options(climate_control_loop_tests PRIVATE -Wall -Wextra -Wpedantic)

add_executable(
  climate_virtual_hil_tests
  "${PROJECT_ROOT}/test/test_climate_virtual_hil/test_main.cpp"
  "${PROJECT_ROOT}/lib/environment_control/src/climate/ClimateControlLoop.cpp"
  "${PROJECT_ROOT}/lib/environment_control/src/climate/ClimateFeatureEncoder.cpp"
  "${PROJECT_ROOT}/lib/environment_control/src/climate/ClimateRuntimeController.cpp"
  "${PROJECT_ROOT}/lib/environment_control/src/climate/ClimateTrendEstimator.cpp"
)
target_include_directories(climate_virtual_hil_tests PRIVATE "${PROJECT_ROOT}/lib/environment_control/src/climate")
target_compile_features(climate_virtual_hil_tests PRIVATE cxx_std_17)
target_compile_options(climate_virtual_hil_tests PRIVATE -Wall -Wextra -Wpedantic)


add_executable(
  climate_io_adapter_tests
  "${PROJECT_ROOT}/test/test_climate_io_adapters/test_main.cpp"
  "${PROJECT_ROOT}/src/climate/ClimateIoAdapters.cpp"
)
target_include_directories(
  climate_io_adapter_tests
  PRIVATE
    "${PROJECT_ROOT}/src"
    "${PROJECT_ROOT}/lib/environment_control/src"
)
target_compile_features(climate_io_adapter_tests PRIVATE cxx_std_17)
target_compile_options(climate_io_adapter_tests PRIVATE -Wall -Wextra -Wpedantic)


add_executable(
  climate_application_composition_tests
  "${PROJECT_ROOT}/test/test_climate_application_composition/test_main.cpp"
  "${PROJECT_ROOT}/src/climate/ClimateApplication.cpp"
  "${PROJECT_ROOT}/src/climate/ClimateIoAdapters.cpp"
  "${PROJECT_ROOT}/lib/environment_control/src/climate/ClimateControlLoop.cpp"
  "${PROJECT_ROOT}/lib/environment_control/src/climate/ClimateFeatureEncoder.cpp"
  "${PROJECT_ROOT}/lib/environment_control/src/climate/ClimateRuntimeController.cpp"
  "${PROJECT_ROOT}/lib/environment_control/src/climate/ClimateTrendEstimator.cpp"
)
target_include_directories(
  climate_application_composition_tests
  PRIVATE
    "${PROJECT_ROOT}/src"
    "${PROJECT_ROOT}/lib/environment_control/src"
)
target_compile_features(climate_application_composition_tests PRIVATE cxx_std_17)
target_compile_options(climate_application_composition_tests PRIVATE -Wall -Wextra -Wpedantic)


add_executable(
  climate_deterministic_fake_runtime_tests
  "${PROJECT_ROOT}/test/test_climate_deterministic_fake_runtime/test_main.cpp"
  "${PROJECT_ROOT}/src/climate/ClimateApplication.cpp"
  "${PROJECT_ROOT}/src/climate/ClimateIoAdapters.cpp"
  "${PROJECT_ROOT}/src/climate/ClimateDeterministicFake.cpp"
  "${PROJECT_ROOT}/lib/environment_control/src/climate/ClimateControlLoop.cpp"
  "${PROJECT_ROOT}/lib/environment_control/src/climate/ClimateFeatureEncoder.cpp"
  "${PROJECT_ROOT}/lib/environment_control/src/climate/ClimateRuntimeController.cpp"
  "${PROJECT_ROOT}/lib/environment_control/src/climate/ClimateTrendEstimator.cpp"
)
target_include_directories(
  climate_deterministic_fake_runtime_tests
  PRIVATE
    "${PROJECT_ROOT}/src"
    "${PROJECT_ROOT}/lib/environment_control/src"
)
target_compile_features(climate_deterministic_fake_runtime_tests PRIVATE cxx_std_17)
target_compile_options(climate_deterministic_fake_runtime_tests PRIVATE -Wall -Wextra -Wpedantic)


add_executable(
  climate_diagnostics_tests
  "${PROJECT_ROOT}/test/test_climate_diagnostics/test_main.cpp"
  "${PROJECT_ROOT}/src/climate/ClimateDiagnostics.cpp"
)
target_include_directories(
  climate_diagnostics_tests
  PRIVATE
    "${PROJECT_ROOT}/src"
    "${PROJECT_ROOT}/lib/environment_control/src"
)
target_compile_features(climate_diagnostics_tests PRIVATE cxx_std_17)
target_compile_options(climate_diagnostics_tests PRIVATE -Wall -Wextra -Wpedantic)


add_executable(
  climate_fault_soak_tests
  "${PROJECT_ROOT}/test/test_climate_fault_soak/test_main.cpp"
  "${PROJECT_ROOT}/src/climate/ClimateApplication.cpp"
  "${PROJECT_ROOT}/src/climate/ClimateIoAdapters.cpp"
  "${PROJECT_ROOT}/lib/environment_control/src/climate/ClimateControlLoop.cpp"
  "${PROJECT_ROOT}/lib/environment_control/src/climate/ClimateFeatureEncoder.cpp"
  "${PROJECT_ROOT}/lib/environment_control/src/climate/ClimateRuntimeController.cpp"
  "${PROJECT_ROOT}/lib/environment_control/src/climate/ClimateTrendEstimator.cpp"
)
target_include_directories(
  climate_fault_soak_tests
  PRIVATE
    "${PROJECT_ROOT}/src"
    "${PROJECT_ROOT}/lib/environment_control/src"
)
target_compile_features(climate_fault_soak_tests PRIVATE cxx_std_17)
target_compile_options(climate_fault_soak_tests PRIVATE -Wall -Wextra -Wpedantic)


add_executable(
  climate_composite_input_tests
  "${PROJECT_ROOT}/test/test_climate_composite_input/test_main.cpp"
  "${PROJECT_ROOT}/src/climate/ClimateCompositeInput.cpp"
  "${PROJECT_ROOT}/src/climate/ClimateApplication.cpp"
  "${PROJECT_ROOT}/src/climate/ClimateIoAdapters.cpp"
  "${PROJECT_ROOT}/lib/environment_control/src/climate/ClimateControlLoop.cpp"
  "${PROJECT_ROOT}/lib/environment_control/src/climate/ClimateFeatureEncoder.cpp"
  "${PROJECT_ROOT}/lib/environment_control/src/climate/ClimateRuntimeController.cpp"
  "${PROJECT_ROOT}/lib/environment_control/src/climate/ClimateTrendEstimator.cpp"
)
target_include_directories(
  climate_composite_input_tests
  PRIVATE
    "${PROJECT_ROOT}/src"
    "${PROJECT_ROOT}/lib/environment_control/src"
)
target_compile_features(climate_composite_input_tests PRIVATE cxx_std_17)
target_compile_options(climate_composite_input_tests PRIVATE -Wall -Wextra -Wpedantic)


add_executable(
  climate_semantic_output_tests
  "${PROJECT_ROOT}/test/test_climate_semantic_output/test_main.cpp"
  "${PROJECT_ROOT}/src/climate/ClimateIoAdapters.cpp"
  "${PROJECT_ROOT}/src/climate/ClimateSemanticOutput.cpp"
)
target_include_directories(
  climate_semantic_output_tests
  PRIVATE
    "${PROJECT_ROOT}/src"
    "${PROJECT_ROOT}/lib/environment_control/src"
)
target_compile_features(climate_semantic_output_tests PRIVATE cxx_std_17)
target_compile_options(climate_semantic_output_tests PRIVATE -Wall -Wextra -Wpedantic)

add_executable(
  tp357_decoder_tests
  "${PROJECT_ROOT}/test/test_tp357_decoder/test_main.cpp"
  "${PROJECT_ROOT}/src/climate/native/Tp357Decoder.cpp"
)
target_include_directories(tp357_decoder_tests PRIVATE "${PROJECT_ROOT}/src")
target_compile_features(tp357_decoder_tests PRIVATE cxx_std_17)
target_compile_options(tp357_decoder_tests PRIVATE -Wall -Wextra -Wpedantic)

add_executable(
  stage27_telemetry_tests
  "${PROJECT_ROOT}/test/test_stage27_telemetry/test_main.cpp"
  "${PROJECT_ROOT}/src/climate/telemetry/Stage27LogFormat.cpp"
)
target_include_directories(stage27_telemetry_tests PRIVATE "${PROJECT_ROOT}/src")
target_compile_features(stage27_telemetry_tests PRIVATE cxx_std_17)
target_compile_options(stage27_telemetry_tests PRIVATE -Wall -Wextra -Wpedantic)

add_executable(
  ble_climate_state_tests
  "${PROJECT_ROOT}/test/test_ble_climate_state/test_main.cpp"
  "${PROJECT_ROOT}/src/climate/native/BleClimateState.cpp"
  "${PROJECT_ROOT}/src/climate/native/BthomeV2Decoder.cpp"
  "${PROJECT_ROOT}/src/climate/native/Tp357Decoder.cpp"
)
target_include_directories(ble_climate_state_tests PRIVATE "${PROJECT_ROOT}/src")
target_compile_features(ble_climate_state_tests PRIVATE cxx_std_17)
target_compile_options(ble_climate_state_tests PRIVATE -Wall -Wextra -Wpedantic)

add_executable(
  stage27_native_inputs_tests
  "${PROJECT_ROOT}/test/test_stage27_native_inputs/test_main.cpp"
  "${PROJECT_ROOT}/src/climate/native/BthomeV2Decoder.cpp"
  "${PROJECT_ROOT}/src/climate/native/Ds3231Codec.cpp"
)
target_include_directories(stage27_native_inputs_tests PRIVATE "${PROJECT_ROOT}/src")
target_compile_features(stage27_native_inputs_tests PRIVATE cxx_std_17)
target_compile_options(stage27_native_inputs_tests PRIVATE -Wall -Wextra -Wpedantic)

add_executable(
  stage27_fault_freshness_tests
  "${PROJECT_ROOT}/test/test_stage27_fault_freshness/test_main.cpp"
  "${PROJECT_ROOT}/src/climate/native/BleClimateState.cpp"
  "${PROJECT_ROOT}/src/climate/native/BthomeV2Decoder.cpp"
  "${PROJECT_ROOT}/src/climate/native/Tp357Decoder.cpp"
  "${PROJECT_ROOT}/lib/environment_control/src/climate/ClimateFeatureEncoder.cpp"
  "${PROJECT_ROOT}/lib/environment_control/src/climate/ClimateRuntimeController.cpp"
  "${PROJECT_ROOT}/lib/environment_control/src/climate/ClimateTrendEstimator.cpp"
)
target_include_directories(
  stage27_fault_freshness_tests
  PRIVATE
    "${PROJECT_ROOT}/src"
    "${PROJECT_ROOT}/lib/environment_control/src/climate"
)
target_compile_features(stage27_fault_freshness_tests PRIVATE cxx_std_17)
target_compile_options(stage27_fault_freshness_tests PRIVATE -Wall -Wextra -Wpedantic)

if(UNIX)
  target_link_libraries(environment_control_tests PRIVATE m)
  target_link_libraries(climate_v6_tests PRIVATE m)
  target_link_libraries(climate_runtime_parity_tests PRIVATE m)
  target_link_libraries(climate_control_loop_tests PRIVATE m)
  target_link_libraries(climate_virtual_hil_tests PRIVATE m)
  target_link_libraries(climate_io_adapter_tests PRIVATE m)
  target_link_libraries(climate_application_composition_tests PRIVATE m)
  target_link_libraries(climate_deterministic_fake_runtime_tests PRIVATE m)
  target_link_libraries(climate_fault_soak_tests PRIVATE m)
  target_link_libraries(climate_diagnostics_tests PRIVATE m)
  target_link_libraries(climate_composite_input_tests PRIVATE m)
  target_link_libraries(climate_semantic_output_tests PRIVATE m)
  target_link_libraries(stage27_telemetry_tests PRIVATE m)
  target_link_libraries(stage27_fault_freshness_tests PRIVATE m)
endif()

enable_testing()
add_test(NAME environment_control_tests COMMAND environment_control_tests)
add_test(NAME climate_v6_tests COMMAND climate_v6_tests)
add_test(NAME climate_runtime_parity_tests COMMAND climate_runtime_parity_tests)
add_test(NAME climate_control_loop_tests COMMAND climate_control_loop_tests)
add_test(NAME climate_virtual_hil_tests COMMAND climate_virtual_hil_tests)
add_test(NAME climate_io_adapter_tests COMMAND climate_io_adapter_tests)
add_test(NAME climate_application_composition_tests COMMAND climate_application_composition_tests)
add_test(NAME climate_deterministic_fake_runtime_tests COMMAND climate_deterministic_fake_runtime_tests)
add_test(NAME climate_fault_soak_tests COMMAND climate_fault_soak_tests)
add_test(NAME climate_diagnostics_tests COMMAND climate_diagnostics_tests)
add_test(NAME climate_composite_input_tests COMMAND climate_composite_input_tests)
add_test(NAME climate_semantic_output_tests COMMAND climate_semantic_output_tests)
add_test(NAME tp357_decoder_tests COMMAND tp357_decoder_tests)
add_test(NAME stage27_telemetry_tests COMMAND stage27_telemetry_tests)
add_test(NAME ble_climate_state_tests COMMAND ble_climate_state_tests)
add_test(NAME stage27_native_inputs_tests COMMAND stage27_native_inputs_tests)
add_test(NAME stage27_fault_freshness_tests COMMAND stage27_fault_freshness_tests)
