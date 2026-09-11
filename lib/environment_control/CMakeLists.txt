if(NOT DEFINED GROWBOX_APP_MODE OR GROWBOX_APP_MODE STREQUAL "")
  set(GROWBOX_APP_MODE "$ENV{GROWBOX_APP_MODE}")
endif()
if(GROWBOX_APP_MODE STREQUAL "")
  message(FATAL_ERROR "GROWBOX_APP_MODE was not exported by the project root")
endif()

set(GROWBOX_ENVIRONMENT_CONTROL_SRCS
  "src/climate/ClimateControlLoop.cpp"
  "src/climate/ClimateFeatureEncoder.cpp"
  "src/climate/ClimateRuntimeController.cpp"
  "src/climate/ClimateTrendEstimator.cpp"
)

if(GROWBOX_APP_MODE STREQUAL "legacy")
  list(APPEND GROWBOX_ENVIRONMENT_CONTROL_SRCS
    "src/EnvironmentController.cpp"
    "src/EnvironmentTypes.cpp"
    "src/FeatureEncoder.cpp"
    "src/ModelRuntime.cpp"
    "src/SafetySupervisor.cpp"
  )
elseif(NOT GROWBOX_APP_MODE STREQUAL "climate-v6-fake" AND
       NOT GROWBOX_APP_MODE STREQUAL "climate-v6-real-inputs")
  message(FATAL_ERROR "Unsupported GROWBOX_APP_MODE in environment_control: ${GROWBOX_APP_MODE}")
endif()

idf_component_register(
  SRCS ${GROWBOX_ENVIRONMENT_CONTROL_SRCS}
  INCLUDE_DIRS
    "src"
  REQUIRES
    emlearn_runtime
)

target_compile_features(${COMPONENT_LIB} PUBLIC cxx_std_17)
target_compile_options(${COMPONENT_LIB} PRIVATE -Wall -Wextra -Wpedantic)
