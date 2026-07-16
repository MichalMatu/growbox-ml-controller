cmake_minimum_required(VERSION 3.16)

set(IDF_TARGET "esp32s3" CACHE STRING "ESP-IDF target")
set(EXTRA_COMPONENT_DIRS
    "${CMAKE_CURRENT_LIST_DIR}/src"
    "${CMAKE_CURRENT_LIST_DIR}/lib/environment_control")

include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(growbox_ml_controller)
