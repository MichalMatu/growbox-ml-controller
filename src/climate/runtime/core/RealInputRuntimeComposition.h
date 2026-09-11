#pragma once

#include "climate/Stage28dLampSafety.h"
#include "climate/application/ClimateSemanticOutput.h"
#include "climate/output/BinaryActuatorPolicy.h"
#include "climate/output/ClimateOutputSupervisorSink.h"
#include "climate/output/OutputAutomationControl.h"
#include "climate/output/OutputMaintenanceControl.h"
#include "climate/output/OutputManualControl.h"
#include "climate/output/OutputStateStore.h"
#include "climate/output/OutputSupervisorExecutor.h"
#include "climate/output/OutputSupervisorResolver.h"
#include "climate/output/lifecycle/OutputLifecycleExecutor.h"
#include "climate/output/lifecycle/OutputRuntimeLifecycleControl.h"
#include "climate/output/lifecycle/OutputSupervisorLifecycle.h"
#include "climate/output/persistence/OutputNvsBackend.h"
#include "climate/output/persistence/OutputPersistenceCoordinator.h"
#include "climate/output/persistence/OutputPersistenceStore.h"
#include "climate/rf433/Rf433OutputTransport.h"
#include "climate/rf433/Rf433RmtFrameSender.h"
#include "climate/rf433/Rf433RmtLoopback.h"
#include "climate/runtime/Stage27RuntimeAdapters.h"
#include "climate/runtime/Stage28MaintenanceRfTransport.h"
#include "climate/runtime/core/RuntimeOutputTransport.h"
#include "climate/runtime/diagnostics/Stage28RfDiagnostics.h"
#include "climate/storage/Stage27TelemetryLogger.h"

namespace growbox::app::climate_io::runtime {

class RuntimeIoOwner final {
public:
  RuntimeIoOwner() noexcept;

  RuntimeIoOwner(const RuntimeIoOwner&) = delete;
  RuntimeIoOwner& operator=(const RuntimeIoOwner&) = delete;

  const storage::Stage27TelemetryLogger::Config& storageConfig() const noexcept {
    return storage_config_;
  }

  storage::Stage27TelemetryLogger& storageLogger() noexcept {
    return storage_logger_;
  }

  bool beginRf() noexcept;

  Stage28RfDiagnostics& rfDiagnostics() noexcept {
    return rf_diagnostics_;
  }

  rf433::Rf433OutputTransport& rfOutputTransport() noexcept {
    return rf_output_transport_;
  }

private:
  storage::Stage27TelemetryLogger::Config storage_config_{};
  storage::Stage27TelemetryLogger storage_logger_;
  Stage28RfDiagnosticsConfig rf_diagnostics_config_{};
  rf433::Rf433RmtLoopback rf_radio_;
  Stage28RfDiagnostics rf_diagnostics_;
  rf433::Rf433RmtFrameSender rf_frame_sender_;
  rf433::Rf433OutputTransport rf_output_transport_;
};

const output::OutputPolicyConfig& safeOutputPolicy() noexcept;

class RuntimePersistenceOwner final {
public:
  RuntimePersistenceOwner() noexcept;

  RuntimePersistenceOwner(const RuntimePersistenceOwner&) = delete;
  RuntimePersistenceOwner& operator=(const RuntimePersistenceOwner&) = delete;

  void initialize() noexcept;

  bool stateStoreReady() const noexcept {
    return state_store_ready_;
  }

  const output::OutputPersistenceCoordinatorInitResult& initResult() const noexcept {
    return init_result_;
  }

  bool valid() const noexcept {
    return persistence_.valid();
  }

  const output::OutputPolicyConfig& policy() const noexcept;

  output::OutputStateStore& stateStore() noexcept {
    return state_store_;
  }

  output::OutputPersistenceCoordinator& persistence() noexcept {
    return persistence_;
  }

private:
  output::OutputStateStore state_store_{};
  output::OutputNvsBackend nvs_backend_{};
  output::OutputPersistenceStore persistence_store_;
  output::OutputPersistenceCoordinator persistence_;
  output::OutputPersistenceCoordinatorInitResult init_result_{};
  bool state_store_ready_{false};
};

class RuntimeOutputOwner final {
public:
  RuntimeOutputOwner(output::OutputTransport& real_transport,
                     RuntimeExecutionStatus& execution_status, Stage28RfDiagnostics& diagnostics,
                     const output::OutputPolicyConfig& policy,
                     output::OutputStateStore& state_store) noexcept;

  RuntimeOutputOwner(const RuntimeOutputOwner&) = delete;
  RuntimeOutputOwner& operator=(const RuntimeOutputOwner&) = delete;

  bool valid() const noexcept {
    return valid_;
  }

  bool bindingsValid() const noexcept {
    return bindings_valid_;
  }

  RuntimeOutputTransport& transport() noexcept {
    return supervisor_transport_;
  }

  output::OutputSupervisorLifecycle& lifecycle() noexcept {
    return output_lifecycle_;
  }

  output::OutputLifecycleExecutor& lifecycleExecutor() noexcept {
    return lifecycle_executor_;
  }

  output::OutputRuntimeLifecycleControl& runtimeLifecycle() noexcept {
    return runtime_lifecycle_;
  }

  output::OutputAutomationControl& automationControl() noexcept {
    return automation_control_;
  }

  output::OutputManualControl& manualControl() noexcept {
    return manual_control_;
  }

  output::OutputMaintenanceControl& maintenanceControl() noexcept {
    return maintenance_control_;
  }

  ClimateOutputSupervisorSink& supervisorSink() noexcept {
    return supervisor_sink_;
  }

private:
  output::OutputPolicyConfig policy_{};
  ClimateSemanticOutputConfig semantic_output_config_{};
  output::BinaryActuatorPolicy exhaust_policy_;
  output::BinaryActuatorPolicy humidifier_policy_;
  output::OutputSupervisorResolverConfig supervisor_config_{};
  RuntimeOutputTransport supervisor_transport_;
  output::OutputSupervisorLifecycle output_lifecycle_;
  output::OutputLifecycleExecutor lifecycle_executor_;
  output::OutputRuntimeLifecycleControl runtime_lifecycle_;
  output::OutputAutomationControl automation_control_;
  output::OutputManualControl manual_control_;
  Stage28MaintenanceRfTransport maintenance_rf_transport_;
  output::OutputMaintenanceControl maintenance_control_;
  output::OutputSupervisorResolver supervisor_resolver_;
  output::OutputSupervisorExecutor supervisor_executor_;
  ClimateOutputSupervisorSink supervisor_sink_;
  bool bindings_valid_{false};
  bool valid_{false};
};

class RuntimeControlOwner final {
public:
  RuntimeControlOwner() noexcept;

  RuntimeControlOwner(const RuntimeControlOwner&) = delete;
  RuntimeControlOwner& operator=(const RuntimeControlOwner&) = delete;

  ::growbox::climate::ClimateRuntimeController& runtimeController() noexcept {
    return runtime_controller_;
  }

  stage28d::LampSafetyController& lampSafety() noexcept {
    return lamp_safety_;
  }

private:
  ::growbox::climate::ClimateRuntimeController runtime_controller_;
  stage28d::LampSafetyController lamp_safety_;
};

} // namespace growbox::app::climate_io::runtime
