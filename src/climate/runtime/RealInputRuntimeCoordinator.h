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
