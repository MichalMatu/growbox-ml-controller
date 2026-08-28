idf_component_register(
  SRCS
    "src/EnvironmentController.cpp"
    "src/EnvironmentTypes.cpp"
    "src/FeatureEncoder.cpp"
    "src/ModelRuntime.cpp"
    "src/SafetySupervisor.cpp"
    "src/climate/ClimateControlLoop.cpp"
    "src/climate/ClimateFeatureEncoder.cpp"
    "src/climate/ClimateRuntimeController.cpp"
    "src/climate/ClimateTrendEstimator.cpp"
  INCLUDE_DIRS
    "src"
  REQUIRES
    emlearn_runtime
)

target_compile_features(${COMPONENT_LIB} PUBLIC cxx_std_17)
target_compile_options(${COMPONENT_LIB} PRIVATE -Wall -Wextra -Wpedantic)
