#pragma once

#include "climate/Stage28dLampSafety.h"
#include "climate/application/ClimateApplication.h"
#include "climate/native/BleClimateScanner.h"
#include "climate/native/Ds3231ClockSource.h"
#include "climate/output/ClimateOutputSupervisorSink.h"
#include "climate/output/OutputAutomationControl.h"
#include "climate/output/OutputLifecycleExecutor.h"
#include "climate/output/OutputMaintenanceControl.h"
#include "climate/output/OutputManualControl.h"
#include "climate/output/OutputPersistenceCoordinator.h"
#include "climate/output/OutputRuntimeLifecycleControl.h"
#include "climate/output/OutputStateStore.h"
#include "climate/output/OutputSupervisorLifecycle.h"
#include "climate/runtime/Stage27TelemetryReporter.h"
#include "climate/runtime/Stage28RfDiagnostics.h"
#include "climate/runtime/Stage28ePlatformDiagnostics.h"
#include "climate/runtime/console/Stage28ServiceConsole.h"
#include "climate/runtime/core/RuntimeCycleState.h"
#include "climate/runtime/core/RuntimeOutputTransport.h"

#include <cstdint>

namespace growbox::app::climate_io::runtime {

struct RealInputRuntimeInputServices final {
  native::BleClimateScanner& ble;
  native::Ds3231ClockSource& clock;
};

struct RealInputRuntimeOutputServices final {
  stage28d::LampSafetyController& lamp_safety;
  RuntimeExecutionStatus& execution_status;
  RuntimeOutputTransport& transport;
  output::OutputSupervisorLifecycle& lifecycle;
  output::OutputLifecycleExecutor& lifecycle_executor;
  output::OutputRuntimeLifecycleControl& runtime_lifecycle;
  output::OutputAutomationControl& automation_control;
  output::OutputManualControl& manual_control;
  output::OutputMaintenanceControl& maintenance_control;
  ClimateOutputSupervisorSink& supervisor_sink;
  output::OutputPersistenceCoordinator& persistence;
  output::OutputStateStore& state_store;
  bool bindings_valid{false};
};

struct RealInputRuntimeSupportServices final {
  Stage28ServiceConsole& service_console;
  Stage28RfDiagnostics& rf_diagnostics;
  Stage27TelemetryReporter& telemetry_reporter;
  RuntimeTimingMetrics& timing;
};

struct RealInputRuntimeServices final {
  RealInputRuntimeInputServices inputs;
  ClimateApplication& application;
  RealInputRuntimeOutputServices outputs;
  RealInputRuntimeSupportServices support;
};

class RealInputRuntimeCoordinator final {
public:
  explicit RealInputRuntimeCoordinator(RealInputRuntimeServices services) noexcept
      : services_(services) {}

  void tick(std::uint64_t loop_started_us) noexcept;

private:
  RealInputRuntimeServices services_;
  RuntimeCycleState cycle_state_{};
};

} // namespace growbox::app::climate_io::runtime
