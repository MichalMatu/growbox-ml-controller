#pragma once

#include "climate/ClimateApplication.h"
#include "climate/Stage28dLampSafety.h"
#include "climate/native/BleClimateScanner.h"
#include "climate/native/Ds3231ClockSource.h"
#include "climate/runtime/RealInputRuntimeComposition.h"
#include "climate/runtime/RuntimeCycleState.h"
#include "climate/runtime/Stage27TelemetryReporter.h"
#include "climate/runtime/Stage28ServiceConsole.h"
#include "climate/runtime/Stage28ePlatformDiagnostics.h"

#include <cstdint>

namespace growbox::app::climate_io::runtime {

struct RealInputRuntimeServices final {
  native::BleClimateScanner& ble;
  native::Ds3231ClockSource& clock;
  stage28d::LampSafetyController& lamp_safety;
  ClimateApplication& application;
  RuntimeExecutionStatus& execution_status;
  RuntimeOutputTransport& supervisor_transport;
  output::OutputSupervisorLifecycle& output_lifecycle;
  output::OutputLifecycleExecutor& lifecycle_executor;
  output::OutputRuntimeLifecycleControl& runtime_lifecycle;
  output::OutputAutomationControl& automation_control;
  output::OutputManualControl& manual_control;
  output::OutputMaintenanceControl& maintenance_control;
  ClimateOutputSupervisorSink& supervisor_sink;
  output::OutputPersistenceCoordinator& output_persistence;
  output::OutputStateStore& output_state_store;
  Stage28ServiceConsole& service_console;
  Stage28RfDiagnostics& rf_diagnostics;
  Stage27TelemetryReporter& telemetry_reporter;
  RuntimeTimingMetrics& runtime_timing;
  bool output_bindings_valid{false};
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
