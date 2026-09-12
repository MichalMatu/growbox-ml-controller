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
  "${PROJECT_ROOT}/src/climate/application/ClimateIoAdapters.cpp"
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
  "${PROJECT_ROOT}/src/climate/application/ClimateApplication.cpp"
  "${PROJECT_ROOT}/src/climate/application/ClimateIoAdapters.cpp"
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
  "${PROJECT_ROOT}/src/climate/application/ClimateApplication.cpp"
  "${PROJECT_ROOT}/src/climate/application/ClimateIoAdapters.cpp"
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
  "${PROJECT_ROOT}/src/climate/application/ClimateApplication.cpp"
  "${PROJECT_ROOT}/src/climate/application/ClimateIoAdapters.cpp"
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
  "${PROJECT_ROOT}/src/climate/application/ClimateCompositeInput.cpp"
  "${PROJECT_ROOT}/src/climate/application/ClimateApplication.cpp"
  "${PROJECT_ROOT}/src/climate/application/ClimateIoAdapters.cpp"
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
  output_execution_contract_tests
  "${PROJECT_ROOT}/test/test_output_execution_contracts/test_main.cpp"
)
target_include_directories(output_execution_contract_tests PRIVATE "${PROJECT_ROOT}/src")
target_compile_features(output_execution_contract_tests PRIVATE cxx_std_17)
target_compile_options(output_execution_contract_tests PRIVATE -Wall -Wextra -Wpedantic)

add_executable(
  output_intents_tests
  "${PROJECT_ROOT}/test/test_output_intents/test_main.cpp"
)
target_include_directories(output_intents_tests PRIVATE "${PROJECT_ROOT}/src")
target_compile_features(output_intents_tests PRIVATE cxx_std_17)
target_compile_options(output_intents_tests PRIVATE -Wall -Wextra -Wpedantic)

add_executable(
  output_types_tests
  "${PROJECT_ROOT}/test/test_output_types/test_main.cpp"
)
target_include_directories(
  output_types_tests
  PRIVATE
    "${PROJECT_ROOT}/src"
    "${PROJECT_ROOT}/lib/environment_control/src"
)
target_compile_features(output_types_tests PRIVATE cxx_std_17)
target_compile_options(output_types_tests PRIVATE -Wall -Wextra -Wpedantic)

add_executable(
  output_supervisor_resolver_tests
  "${PROJECT_ROOT}/test/test_output_supervisor_resolver/test_main.cpp"
  "${PROJECT_ROOT}/src/climate/output/supervisor/OutputSupervisorResolver.cpp"
  "${PROJECT_ROOT}/src/climate/output/policy/BinaryActuatorPolicy.cpp"
  "${PROJECT_ROOT}/src/climate/output/OutputStateStore.cpp"
)
target_include_directories(output_supervisor_resolver_tests PRIVATE "${PROJECT_ROOT}/src")
target_compile_features(output_supervisor_resolver_tests PRIVATE cxx_std_17)
target_compile_options(output_supervisor_resolver_tests PRIVATE -Wall -Wextra -Wpedantic)

add_executable(
  output_supervisor_executor_tests
  "${PROJECT_ROOT}/test/test_output_supervisor_executor/test_main.cpp"
  "${PROJECT_ROOT}/src/climate/output/supervisor/OutputSupervisorExecutor.cpp"
  "${PROJECT_ROOT}/src/climate/output/supervisor/OutputSupervisorResolver.cpp"
  "${PROJECT_ROOT}/src/climate/output/policy/BinaryActuatorPolicy.cpp"
  "${PROJECT_ROOT}/src/climate/output/OutputStateStore.cpp"
)
target_include_directories(output_supervisor_executor_tests PRIVATE "${PROJECT_ROOT}/src")
target_compile_features(output_supervisor_executor_tests PRIVATE cxx_std_17)
target_compile_options(output_supervisor_executor_tests PRIVATE -Wall -Wextra -Wpedantic)

add_executable(
  output_execution_projection_tests
  "${PROJECT_ROOT}/test/test_output_execution_projection/test_main.cpp"
  "${PROJECT_ROOT}/src/climate/output/OutputExecutionProjection.cpp"
  "${PROJECT_ROOT}/src/climate/output/OutputStateStore.cpp"
)
target_include_directories(output_execution_projection_tests PRIVATE "${PROJECT_ROOT}/src")
target_compile_features(output_execution_projection_tests PRIVATE cxx_std_17)
target_compile_options(output_execution_projection_tests PRIVATE -Wall -Wextra -Wpedantic)

add_executable(
  climate_output_supervisor_sink_tests
  "${PROJECT_ROOT}/test/test_climate_output_supervisor_sink/test_main.cpp"
  "${PROJECT_ROOT}/src/climate/output/supervisor/ClimateOutputSupervisorSink.cpp"
  "${PROJECT_ROOT}/src/climate/output/OutputExecutionProjection.cpp"
  "${PROJECT_ROOT}/src/climate/output/supervisor/OutputSupervisorExecutor.cpp"
  "${PROJECT_ROOT}/src/climate/output/supervisor/OutputSupervisorResolver.cpp"
  "${PROJECT_ROOT}/src/climate/output/policy/BinaryActuatorPolicy.cpp"
  "${PROJECT_ROOT}/src/climate/output/OutputStateStore.cpp"
  "${PROJECT_ROOT}/src/climate/application/ClimateSemanticOutput.cpp"
)
target_include_directories(
  climate_output_supervisor_sink_tests
  PRIVATE
    "${PROJECT_ROOT}/src"
    "${PROJECT_ROOT}/lib/environment_control/src"
)
target_compile_features(climate_output_supervisor_sink_tests PRIVATE cxx_std_17)
target_compile_options(climate_output_supervisor_sink_tests PRIVATE -Wall -Wextra -Wpedantic)

add_executable(
  output_policy_config_tests
  "${PROJECT_ROOT}/test/test_output_policy_config/test_main.cpp"
  "${PROJECT_ROOT}/src/climate/output/policy/OutputPolicyConfig.cpp"
)
target_include_directories(output_policy_config_tests PRIVATE "${PROJECT_ROOT}/src")
target_compile_features(output_policy_config_tests PRIVATE cxx_std_17)
target_compile_options(output_policy_config_tests PRIVATE -Wall -Wextra -Wpedantic)

add_executable(
  output_execution_telemetry_tests
  "${PROJECT_ROOT}/test/test_output_execution_telemetry/test_main.cpp"
  "${PROJECT_ROOT}/src/climate/output/OutputExecutionTelemetry.cpp"
  "${PROJECT_ROOT}/src/climate/output/OutputStateStore.cpp"
)
target_include_directories(output_execution_telemetry_tests PRIVATE "${PROJECT_ROOT}/src")
target_compile_features(output_execution_telemetry_tests PRIVATE cxx_std_17)
target_compile_options(output_execution_telemetry_tests PRIVATE -Wall -Wextra -Wpedantic)

add_executable(
  output_persistence_schema_tests
  "${PROJECT_ROOT}/test/test_output_persistence_schema/test_main.cpp"
  "${PROJECT_ROOT}/src/climate/output/persistence/OutputPersistenceSchema.cpp"
  "${PROJECT_ROOT}/src/climate/output/policy/OutputPolicyConfig.cpp"
)
target_include_directories(output_persistence_schema_tests PRIVATE "${PROJECT_ROOT}/src")
target_compile_features(output_persistence_schema_tests PRIVATE cxx_std_17)
target_compile_options(output_persistence_schema_tests PRIVATE -Wall -Wextra -Wpedantic)

add_executable(
  output_persistence_coordinator_tests
  "${PROJECT_ROOT}/test/test_output_persistence_coordinator/test_main.cpp"
  "${PROJECT_ROOT}/src/climate/output/persistence/OutputPersistenceCoordinator.cpp"
  "${PROJECT_ROOT}/src/climate/output/persistence/OutputPersistenceStore.cpp"
  "${PROJECT_ROOT}/src/climate/output/persistence/OutputPersistenceSchema.cpp"
  "${PROJECT_ROOT}/src/climate/output/policy/OutputPolicyConfig.cpp"
  "${PROJECT_ROOT}/src/climate/output/OutputStateStore.cpp"
  "${PROJECT_ROOT}/src/climate/output/lifecycle/OutputLifecycleExecutor.cpp"
  "${PROJECT_ROOT}/src/climate/output/lifecycle/OutputSupervisorLifecycle.cpp"
  "${PROJECT_ROOT}/src/climate/output/policy/BinaryActuatorPolicy.cpp"
)
target_include_directories(output_persistence_coordinator_tests PRIVATE "${PROJECT_ROOT}/src")
target_compile_features(output_persistence_coordinator_tests PRIVATE cxx_std_17)
target_compile_options(output_persistence_coordinator_tests PRIVATE -Wall -Wextra -Wpedantic)

add_executable(
  output_persistence_store_tests
  "${PROJECT_ROOT}/test/test_output_persistence_store/test_main.cpp"
  "${PROJECT_ROOT}/src/climate/output/persistence/OutputPersistenceStore.cpp"
  "${PROJECT_ROOT}/src/climate/output/persistence/OutputPersistenceSchema.cpp"
  "${PROJECT_ROOT}/src/climate/output/policy/OutputPolicyConfig.cpp"
)
target_include_directories(output_persistence_store_tests PRIVATE "${PROJECT_ROOT}/src")
target_compile_features(output_persistence_store_tests PRIVATE cxx_std_17)
target_compile_options(output_persistence_store_tests PRIVATE -Wall -Wextra -Wpedantic)

add_executable(
  output_supervisor_lifecycle_tests
  "${PROJECT_ROOT}/test/test_output_supervisor_lifecycle/test_main.cpp"
  "${PROJECT_ROOT}/src/climate/output/lifecycle/OutputSupervisorLifecycle.cpp"
  "${PROJECT_ROOT}/src/climate/output/policy/OutputPolicyConfig.cpp"
)
target_include_directories(output_supervisor_lifecycle_tests PRIVATE "${PROJECT_ROOT}/src")
target_compile_features(output_supervisor_lifecycle_tests PRIVATE cxx_std_17)
target_compile_options(output_supervisor_lifecycle_tests PRIVATE -Wall -Wextra -Wpedantic)

add_executable(
  output_lifecycle_executor_tests
  "${PROJECT_ROOT}/test/test_output_lifecycle_executor/test_main.cpp"
  "${PROJECT_ROOT}/src/climate/output/lifecycle/OutputLifecycleExecutor.cpp"
  "${PROJECT_ROOT}/src/climate/output/lifecycle/OutputSupervisorLifecycle.cpp"
  "${PROJECT_ROOT}/src/climate/output/policy/OutputPolicyConfig.cpp"
  "${PROJECT_ROOT}/src/climate/output/OutputStateStore.cpp"
  "${PROJECT_ROOT}/src/climate/output/policy/BinaryActuatorPolicy.cpp"
)
target_include_directories(output_lifecycle_executor_tests PRIVATE "${PROJECT_ROOT}/src")
target_compile_features(output_lifecycle_executor_tests PRIVATE cxx_std_17)
target_compile_options(output_lifecycle_executor_tests PRIVATE -Wall -Wextra -Wpedantic)

add_executable(
  output_runtime_lifecycle_control_tests
  "${PROJECT_ROOT}/test/test_output_runtime_lifecycle_control/test_main.cpp"
  "${PROJECT_ROOT}/src/climate/output/lifecycle/OutputRuntimeLifecycleControl.cpp"
  "${PROJECT_ROOT}/src/climate/output/lifecycle/OutputLifecycleExecutor.cpp"
  "${PROJECT_ROOT}/src/climate/output/lifecycle/OutputSupervisorLifecycle.cpp"
  "${PROJECT_ROOT}/src/climate/output/supervisor/OutputSupervisorResolver.cpp"
  "${PROJECT_ROOT}/src/climate/output/policy/OutputPolicyConfig.cpp"
  "${PROJECT_ROOT}/src/climate/output/OutputStateStore.cpp"
  "${PROJECT_ROOT}/src/climate/output/policy/BinaryActuatorPolicy.cpp"
)
target_include_directories(output_runtime_lifecycle_control_tests PRIVATE "${PROJECT_ROOT}/src")
target_compile_features(output_runtime_lifecycle_control_tests PRIVATE cxx_std_17)
target_compile_options(output_runtime_lifecycle_control_tests PRIVATE -Wall -Wextra -Wpedantic)

add_executable(
  output_automation_control_tests
  "${PROJECT_ROOT}/test/test_output_automation_control/test_main.cpp"
  "${PROJECT_ROOT}/src/climate/output/control/OutputAutomationControl.cpp"
  "${PROJECT_ROOT}/src/climate/output/lifecycle/OutputLifecycleExecutor.cpp"
  "${PROJECT_ROOT}/src/climate/output/lifecycle/OutputSupervisorLifecycle.cpp"
  "${PROJECT_ROOT}/src/climate/output/supervisor/OutputSupervisorResolver.cpp"
  "${PROJECT_ROOT}/src/climate/output/policy/OutputPolicyConfig.cpp"
  "${PROJECT_ROOT}/src/climate/output/OutputStateStore.cpp"
  "${PROJECT_ROOT}/src/climate/output/policy/BinaryActuatorPolicy.cpp"
)
target_include_directories(output_automation_control_tests PRIVATE "${PROJECT_ROOT}/src")
target_compile_features(output_automation_control_tests PRIVATE cxx_std_17)
target_compile_options(output_automation_control_tests PRIVATE -Wall -Wextra -Wpedantic)

add_executable(
  output_manual_control_tests
  "${PROJECT_ROOT}/test/test_output_manual_control/test_main.cpp"
  "${PROJECT_ROOT}/src/climate/output/control/OutputManualControl.cpp"
  "${PROJECT_ROOT}/src/climate/output/lifecycle/OutputSupervisorLifecycle.cpp"
  "${PROJECT_ROOT}/src/climate/output/policy/OutputPolicyConfig.cpp"
)
target_include_directories(output_manual_control_tests PRIVATE "${PROJECT_ROOT}/src")
target_compile_features(output_manual_control_tests PRIVATE cxx_std_17)
target_compile_options(output_manual_control_tests PRIVATE -Wall -Wextra -Wpedantic)

add_executable(
  output_maintenance_control_tests
  "${PROJECT_ROOT}/test/test_output_maintenance_control/test_main.cpp"
  "${PROJECT_ROOT}/src/climate/output/control/OutputMaintenanceControl.cpp"
  "${PROJECT_ROOT}/src/climate/output/control/OutputAutomationControl.cpp"
  "${PROJECT_ROOT}/src/climate/output/lifecycle/OutputLifecycleExecutor.cpp"
  "${PROJECT_ROOT}/src/climate/output/lifecycle/OutputSupervisorLifecycle.cpp"
  "${PROJECT_ROOT}/src/climate/output/policy/OutputPolicyConfig.cpp"
  "${PROJECT_ROOT}/src/climate/output/OutputStateStore.cpp"
  "${PROJECT_ROOT}/src/climate/output/policy/BinaryActuatorPolicy.cpp"
)
target_include_directories(output_maintenance_control_tests PRIVATE "${PROJECT_ROOT}/src")
target_compile_features(output_maintenance_control_tests PRIVATE cxx_std_17)
target_compile_options(output_maintenance_control_tests PRIVATE -Wall -Wextra -Wpedantic)

add_executable(
  climate_semantic_output_tests
  "${PROJECT_ROOT}/test/test_climate_semantic_output/test_main.cpp"
  "${PROJECT_ROOT}/src/climate/application/ClimateIoAdapters.cpp"
  "${PROJECT_ROOT}/src/climate/application/ClimateSemanticOutput.cpp"
  "${PROJECT_ROOT}/src/climate/rf433/ClimateRf433EndpointRegistry.cpp"
  "${PROJECT_ROOT}/src/climate/output/policy/OutputPolicyConfig.cpp"
  "${PROJECT_ROOT}/src/climate/OutputBindings.cpp"
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
  stage28d_binary_role_arbiter_tests
  "${PROJECT_ROOT}/test/test_stage28d_binary_role_arbiter/test_main.cpp"
  "${PROJECT_ROOT}/src/climate/compatibility/stage28d/Stage28dBinaryRoleArbiter.cpp"
  "${PROJECT_ROOT}/src/climate/output/policy/BinaryActuatorPolicy.cpp"
)
target_include_directories(stage28d_binary_role_arbiter_tests PRIVATE "${PROJECT_ROOT}/src" "${PROJECT_ROOT}/lib/environment_control/src")
target_compile_features(stage28d_binary_role_arbiter_tests PRIVATE cxx_std_17)
target_compile_options(stage28d_binary_role_arbiter_tests PRIVATE -Wall -Wextra -Wpedantic)

add_executable(
  stage28d_rf_output_endpoint_tests
  "${PROJECT_ROOT}/test/test_stage28d_rf_output_endpoint/test_main.cpp"
  "${PROJECT_ROOT}/src/climate/compatibility/stage28d/Stage28dRfOutputEndpoint.cpp"
  "${PROJECT_ROOT}/src/climate/output/OutputStateStore.cpp"
)
target_include_directories(stage28d_rf_output_endpoint_tests PRIVATE "${PROJECT_ROOT}/src" "${PROJECT_ROOT}/lib/environment_control/src")
target_compile_features(stage28d_rf_output_endpoint_tests PRIVATE cxx_std_17)
target_compile_options(stage28d_rf_output_endpoint_tests PRIVATE -Wall -Wextra -Wpedantic)

add_executable(
  stage28d_lamp_safety_tests
  "${PROJECT_ROOT}/test/test_stage28d_lamp_safety/test_main.cpp"
  "${PROJECT_ROOT}/src/climate/LampSafety.cpp"
)
target_include_directories(
  stage28d_lamp_safety_tests
  PRIVATE
    "${PROJECT_ROOT}/src"
    "${PROJECT_ROOT}/lib/environment_control/src"
)
target_compile_features(stage28d_lamp_safety_tests PRIVATE cxx_std_17)
target_compile_options(stage28d_lamp_safety_tests PRIVATE -Wall -Wextra -Wpedantic)

add_executable(
  climate_observability_metrics_tests
  "${PROJECT_ROOT}/test/test_climate_observability_metrics/test_main.cpp"
  "${PROJECT_ROOT}/src/climate/ClimateObservabilityMetrics.cpp"
)
target_include_directories(climate_observability_metrics_tests PRIVATE "${PROJECT_ROOT}/src")
target_compile_features(climate_observability_metrics_tests PRIVATE cxx_std_17)
target_compile_options(climate_observability_metrics_tests PRIVATE -Wall -Wextra -Wpedantic)

add_executable(
  europe_warsaw_time_tests
  "${PROJECT_ROOT}/test/test_europe_warsaw_time/test_main.cpp"
  "${PROJECT_ROOT}/src/climate/runtime/schedule/EuropeWarsawTime.cpp"
)
target_include_directories(europe_warsaw_time_tests PRIVATE "${PROJECT_ROOT}/src")
target_compile_features(europe_warsaw_time_tests PRIVATE cxx_std_17)
target_compile_options(europe_warsaw_time_tests PRIVATE -Wall -Wextra -Wpedantic)

add_executable(
  stage27_schedule_profile_tests
  "${PROJECT_ROOT}/test/test_stage27_schedule_profile/test_main.cpp"
  "${PROJECT_ROOT}/src/climate/runtime/schedule/Stage27ScheduleProfile.cpp"
  "${PROJECT_ROOT}/src/climate/runtime/schedule/EuropeWarsawTime.cpp"
)
target_include_directories(
  stage27_schedule_profile_tests
  PRIVATE
    "${PROJECT_ROOT}/src"
    "${PROJECT_ROOT}/lib/environment_control/src"
)
target_compile_features(stage27_schedule_profile_tests PRIVATE cxx_std_17)
target_compile_options(stage27_schedule_profile_tests PRIVATE -Wall -Wextra -Wpedantic)

add_executable(
  stage27_schedule_intent_tests
  "${PROJECT_ROOT}/test/test_stage27_schedule_intent/test_main.cpp"
  "${PROJECT_ROOT}/src/climate/runtime/schedule/Stage27ScheduleIntentAdapter.cpp"
  "${PROJECT_ROOT}/src/climate/runtime/schedule/Stage27ScheduleProfile.cpp"
  "${PROJECT_ROOT}/src/climate/runtime/schedule/EuropeWarsawTime.cpp"
)
target_include_directories(
  stage27_schedule_intent_tests
  PRIVATE
    "${PROJECT_ROOT}/src"
    "${PROJECT_ROOT}/lib/environment_control/src"
)
target_compile_features(stage27_schedule_intent_tests PRIVATE cxx_std_17)
target_compile_options(stage27_schedule_intent_tests PRIVATE -Wall -Wextra -Wpedantic)

add_executable(
  stage28d_output_intent_parity_tests
  "${PROJECT_ROOT}/test/test_stage28d_output_intent_parity/test_main.cpp"
  "${PROJECT_ROOT}/src/climate/runtime/schedule/Stage27ScheduleIntentAdapter.cpp"
  "${PROJECT_ROOT}/src/climate/runtime/schedule/Stage27ScheduleProfile.cpp"
  "${PROJECT_ROOT}/src/climate/runtime/schedule/EuropeWarsawTime.cpp"
  "${PROJECT_ROOT}/src/climate/LampSafety.cpp"
)
target_include_directories(
  stage28d_output_intent_parity_tests
  PRIVATE
    "${PROJECT_ROOT}/src"
    "${PROJECT_ROOT}/lib/environment_control/src"
)
target_compile_features(stage28d_output_intent_parity_tests PRIVATE cxx_std_17)
target_compile_options(stage28d_output_intent_parity_tests PRIVATE -Wall -Wextra -Wpedantic)

add_executable(
  tp357_decoder_tests
  "${PROJECT_ROOT}/test/test_tp357_decoder/test_main.cpp"
  "${PROJECT_ROOT}/src/climate/input/ble/Tp357Decoder.cpp"
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
  "${PROJECT_ROOT}/src/climate/input/ble/BleClimateState.cpp"
  "${PROJECT_ROOT}/src/climate/input/ble/BthomeV2Decoder.cpp"
  "${PROJECT_ROOT}/src/climate/input/ble/Tp357Decoder.cpp"
)
target_include_directories(ble_climate_state_tests PRIVATE "${PROJECT_ROOT}/src")
target_compile_features(ble_climate_state_tests PRIVATE cxx_std_17)
target_compile_options(ble_climate_state_tests PRIVATE -Wall -Wextra -Wpedantic)

add_executable(
  stage27_native_inputs_tests
  "${PROJECT_ROOT}/test/test_stage27_native_inputs/test_main.cpp"
  "${PROJECT_ROOT}/src/climate/input/ble/BthomeV2Decoder.cpp"
  "${PROJECT_ROOT}/src/climate/input/rtc/Ds3231Codec.cpp"
)
target_include_directories(stage27_native_inputs_tests PRIVATE "${PROJECT_ROOT}/src")
target_compile_features(stage27_native_inputs_tests PRIVATE cxx_std_17)
target_compile_options(stage27_native_inputs_tests PRIVATE -Wall -Wextra -Wpedantic)

add_executable(
  stage27_fault_freshness_tests
  "${PROJECT_ROOT}/test/test_stage27_fault_freshness/test_main.cpp"
  "${PROJECT_ROOT}/src/climate/input/ble/BleClimateState.cpp"
  "${PROJECT_ROOT}/src/climate/input/ble/BthomeV2Decoder.cpp"
  "${PROJECT_ROOT}/src/climate/input/ble/Tp357Decoder.cpp"
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

add_executable(
  stage27_file_durability_tests
  "${PROJECT_ROOT}/test/test_stage27_file_durability/test_main.cpp"
  "${PROJECT_ROOT}/src/climate/storage/Stage27FileDurability.cpp"
)
target_include_directories(stage27_file_durability_tests PRIVATE "${PROJECT_ROOT}/src")
target_compile_features(stage27_file_durability_tests PRIVATE cxx_std_17)
target_compile_options(stage27_file_durability_tests PRIVATE -Wall -Wextra -Wpedantic)

add_executable(
  stage28_service_console_tests
  "${PROJECT_ROOT}/test/test_stage28_service_console/test_main.cpp"
  "${PROJECT_ROOT}/src/climate/runtime/console/Stage28ServiceConsoleCommand.cpp"
  "${PROJECT_ROOT}/src/climate/runtime/console/Stage28ServiceConsoleRouter.cpp"
)
target_include_directories(stage28_service_console_tests PRIVATE "${PROJECT_ROOT}/src")
target_compile_features(stage28_service_console_tests PRIVATE cxx_std_17)
target_compile_options(stage28_service_console_tests PRIVATE -Wall -Wextra -Wpedantic)

add_executable(
  rf433_protocol_tests
  "${PROJECT_ROOT}/test/test_rf433_protocol/test_main.cpp"
  "${PROJECT_ROOT}/src/climate/rf433/Rf433ProtocolCodec.cpp"
)
target_include_directories(rf433_protocol_tests PRIVATE "${PROJECT_ROOT}/src")
target_compile_features(rf433_protocol_tests PRIVATE cxx_std_17)
target_compile_options(rf433_protocol_tests PRIVATE -Wall -Wextra -Wpedantic)

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
  target_link_libraries(stage28d_binary_role_arbiter_tests PRIVATE m)
  target_link_libraries(stage28d_rf_output_endpoint_tests PRIVATE m)
  target_link_libraries(stage28d_lamp_safety_tests PRIVATE m)
  target_link_libraries(climate_observability_metrics_tests PRIVATE m)
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
add_test(NAME output_execution_contract_tests COMMAND output_execution_contract_tests)
add_test(NAME output_intents_tests COMMAND output_intents_tests)
add_test(NAME output_types_tests COMMAND output_types_tests)
add_test(NAME output_supervisor_resolver_tests COMMAND output_supervisor_resolver_tests)
add_test(NAME output_supervisor_executor_tests COMMAND output_supervisor_executor_tests)
add_test(NAME output_execution_projection_tests COMMAND output_execution_projection_tests)
add_test(NAME output_execution_telemetry_tests COMMAND output_execution_telemetry_tests)
add_test(NAME climate_output_supervisor_sink_tests COMMAND climate_output_supervisor_sink_tests)
add_test(NAME output_policy_config_tests COMMAND output_policy_config_tests)
add_test(NAME output_persistence_schema_tests COMMAND output_persistence_schema_tests)
add_test(NAME output_persistence_coordinator_tests COMMAND output_persistence_coordinator_tests)
add_test(NAME output_persistence_store_tests COMMAND output_persistence_store_tests)
add_test(NAME output_supervisor_lifecycle_tests COMMAND output_supervisor_lifecycle_tests)
add_test(NAME output_lifecycle_executor_tests COMMAND output_lifecycle_executor_tests)
add_test(NAME output_runtime_lifecycle_control_tests COMMAND output_runtime_lifecycle_control_tests)
add_test(NAME output_automation_control_tests COMMAND output_automation_control_tests)
add_test(NAME output_manual_control_tests COMMAND output_manual_control_tests)
add_test(NAME output_maintenance_control_tests COMMAND output_maintenance_control_tests)
add_test(NAME climate_semantic_output_tests COMMAND climate_semantic_output_tests)
add_test(NAME stage28d_binary_role_arbiter_tests COMMAND stage28d_binary_role_arbiter_tests)
add_test(NAME stage28d_rf_output_endpoint_tests COMMAND stage28d_rf_output_endpoint_tests)
add_test(NAME stage28d_lamp_safety_tests COMMAND stage28d_lamp_safety_tests)
add_test(NAME climate_observability_metrics_tests COMMAND climate_observability_metrics_tests)
add_test(NAME europe_warsaw_time_tests COMMAND europe_warsaw_time_tests)
add_test(NAME stage27_schedule_profile_tests COMMAND stage27_schedule_profile_tests)
add_test(NAME stage27_schedule_intent_tests COMMAND stage27_schedule_intent_tests)
add_test(NAME stage28d_output_intent_parity_tests COMMAND stage28d_output_intent_parity_tests)
add_test(NAME tp357_decoder_tests COMMAND tp357_decoder_tests)
add_test(NAME stage27_telemetry_tests COMMAND stage27_telemetry_tests)
add_test(NAME ble_climate_state_tests COMMAND ble_climate_state_tests)
add_test(NAME stage27_native_inputs_tests COMMAND stage27_native_inputs_tests)
add_test(NAME stage27_fault_freshness_tests COMMAND stage27_fault_freshness_tests)
add_test(NAME stage27_file_durability_tests COMMAND stage27_file_durability_tests)
add_test(NAME stage28_service_console_tests COMMAND stage28_service_console_tests)
add_test(NAME rf433_protocol_tests COMMAND rf433_protocol_tests)

add_executable(
  rf433_output_transport_tests
  "${PROJECT_ROOT}/test/test_rf433_output_transport/test_main.cpp"
  "${PROJECT_ROOT}/src/climate/rf433/Rf433OutputTransport.cpp"
  "${PROJECT_ROOT}/src/climate/rf433/ClimateRf433EndpointRegistry.cpp"
)
target_include_directories(
  rf433_output_transport_tests
  PRIVATE
    "${PROJECT_ROOT}/src"
    "${PROJECT_ROOT}/lib/environment_control/src"
)
target_compile_features(rf433_output_transport_tests PRIVATE cxx_std_17)
target_compile_options(rf433_output_transport_tests PRIVATE -Wall -Wextra -Wpedantic)
add_test(NAME rf433_output_transport_tests COMMAND rf433_output_transport_tests)

add_executable(
  output_state_store_tests
  "${PROJECT_ROOT}/test/test_output_state_store/test_main.cpp"
  "${PROJECT_ROOT}/src/climate/output/OutputStateStore.cpp"
)
target_include_directories(output_state_store_tests PRIVATE "${PROJECT_ROOT}/src")
target_compile_features(output_state_store_tests PRIVATE cxx_std_17)
target_compile_options(output_state_store_tests PRIVATE -Wall -Wextra -Wpedantic)
add_test(NAME output_state_store_tests COMMAND output_state_store_tests)

add_executable(
  binary_actuator_policy_tests
  "${PROJECT_ROOT}/test/test_binary_actuator_policy/test_main.cpp"
  "${PROJECT_ROOT}/src/climate/output/policy/BinaryActuatorPolicy.cpp"
)
target_include_directories(binary_actuator_policy_tests PRIVATE "${PROJECT_ROOT}/src")
target_compile_features(binary_actuator_policy_tests PRIVATE cxx_std_17)
target_compile_options(binary_actuator_policy_tests PRIVATE -Wall -Wextra -Wpedantic)
add_test(NAME binary_actuator_policy_tests COMMAND binary_actuator_policy_tests)


add_executable(
  runtime_cycle_state_tests
  "${PROJECT_ROOT}/test/test_runtime_cycle_state/test_main.cpp"
  "${PROJECT_ROOT}/src/climate/runtime/core/RuntimeCycleState.cpp"
)
target_include_directories(runtime_cycle_state_tests PRIVATE "${PROJECT_ROOT}/src")
target_compile_features(runtime_cycle_state_tests PRIVATE cxx_std_17)
target_compile_options(runtime_cycle_state_tests PRIVATE -Wall -Wextra -Wpedantic)
add_test(NAME runtime_cycle_state_tests COMMAND runtime_cycle_state_tests)


add_executable(
  service_console_text_sink_tests
  "${PROJECT_ROOT}/test/test_service_console_text_sink/test_main.cpp"
  "${PROJECT_ROOT}/src/climate/runtime/console/ServiceConsoleTextSink.cpp"
)
target_include_directories(service_console_text_sink_tests PRIVATE "${PROJECT_ROOT}/src")
target_compile_features(service_console_text_sink_tests PRIVATE cxx_std_17)
target_compile_options(service_console_text_sink_tests PRIVATE -Wall -Wextra -Wpedantic)
add_test(NAME service_console_text_sink_tests COMMAND service_console_text_sink_tests)
