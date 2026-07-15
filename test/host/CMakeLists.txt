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

if(UNIX)
  target_link_libraries(environment_control_tests PRIVATE m)
endif()

enable_testing()
add_test(NAME environment_control_tests COMMAND environment_control_tests)
