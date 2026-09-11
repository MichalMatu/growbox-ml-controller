cmake_minimum_required(VERSION 3.16)

set(IDF_TARGET "esp32s3" CACHE STRING "ESP-IDF target")

set(GROWBOX_APP_MODE "legacy" CACHE STRING "Growbox application runtime")
set_property(
  CACHE GROWBOX_APP_MODE
  PROPERTY STRINGS "legacy" "climate-v6-fake" "climate-v6-real-inputs"
)
set(GROWBOX_VALID_APP_MODES "legacy" "climate-v6-fake" "climate-v6-real-inputs")
if(NOT GROWBOX_APP_MODE IN_LIST GROWBOX_VALID_APP_MODES)
  message(FATAL_ERROR "Unsupported GROWBOX_APP_MODE: ${GROWBOX_APP_MODE}")
endif()
set(ENV{GROWBOX_APP_MODE} "${GROWBOX_APP_MODE}")
set(EXTRA_COMPONENT_DIRS
    "${CMAKE_CURRENT_LIST_DIR}/src"
    "${CMAKE_CURRENT_LIST_DIR}/lib/environment_control")

include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(growbox_ml_controller)
