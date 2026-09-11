cmake_minimum_required(VERSION 3.16)
project(runtime_output_transport_tests LANGUAGES CXX)

get_filename_component(PROJECT_ROOT "${CMAKE_CURRENT_LIST_DIR}/../.." ABSOLUTE)

add_executable(
  runtime_output_transport_tests
  "${CMAKE_CURRENT_LIST_DIR}/test_main.cpp"
  "${PROJECT_ROOT}/src/climate/runtime/RuntimeOutputTransport.cpp"
)
target_include_directories(runtime_output_transport_tests PRIVATE "${PROJECT_ROOT}/src")
target_compile_features(runtime_output_transport_tests PRIVATE cxx_std_17)
target_compile_options(runtime_output_transport_tests PRIVATE -Wall -Wextra -Wpedantic)
