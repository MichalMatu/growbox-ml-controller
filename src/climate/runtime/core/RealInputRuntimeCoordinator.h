#pragma once

#include "climate/runtime/core/RuntimeCycleState.h"

#include <cstdint>

namespace growbox::app::output {
class OutputAutomationControl;
class OutputLifecycleExecutor;
class OutputMaintenanceControl;
class OutputManualControl;
class OutputPersistenceCoordinator;
class OutputRuntimeLifecycleControl;
class OutputStateStore;
class OutputSupervisorLifecycle;
} // namespace growbox::app::output

namespace growbox::app::climate_io {
class ClimateApplication;
class ClimateOutputSupervisorSink;

namespace native {
class BleClimateScanner;
class Ds3231ClockSource;
} // namespace native

namespace stage28d {
class LampSafetyController;
} // namespace stage28d

namespace runtime {
class RfDiagnostics;
class RuntimeOutputTransport;
class Stage28ServiceConsole;
class TelemetryReporter;
struct RuntimeExecutionStatus;
struct RuntimeTimingMetrics;

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
  RfDiagnostics& rf_diagnostics;
  TelemetryReporter& telemetry_reporter;
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

} // namespace runtime
} // namespace growbox::app::climate_io
