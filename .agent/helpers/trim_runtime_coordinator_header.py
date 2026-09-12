from pathlib import Path

header = Path('src/climate/runtime/core/RealInputRuntimeCoordinator.h')
cpp = Path('src/climate/runtime/core/RealInputRuntimeCoordinator.cpp')

new_header = r'''#pragma once

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
'''

current_header = header.read_text()
assert '#include "climate/application/ClimateApplication.h"' in current_header
assert current_header.count('#include ') >= 19
header.write_text(new_header)

current_cpp = cpp.read_text()
old_prefix = '''#include "climate/runtime/core/RealInputRuntimeCoordinator.h"\n\n#include "climate/output/OutputBindings.h"\n#include "climate/output/OutputExecutionTelemetry.h"\n#include "climate/runtime/schedule/ScheduleIntentAdapter.h"\n#include "climate/runtime/telemetry/RuntimeOutputTelemetryLog.h"\n'''
new_prefix = '''#include "climate/runtime/core/RealInputRuntimeCoordinator.h"\n\n#include "climate/application/ClimateApplication.h"\n#include "climate/input/ble/BleClimateScanner.h"\n#include "climate/input/rtc/Ds3231ClockSource.h"\n#include "climate/output/LampSafety.h"\n#include "climate/output/OutputBindings.h"\n#include "climate/output/OutputExecutionTelemetry.h"\n#include "climate/output/OutputStateStore.h"\n#include "climate/output/control/OutputAutomationControl.h"\n#include "climate/output/control/OutputMaintenanceControl.h"\n#include "climate/output/control/OutputManualControl.h"\n#include "climate/output/lifecycle/OutputLifecycleExecutor.h"\n#include "climate/output/lifecycle/OutputRuntimeLifecycleControl.h"\n#include "climate/output/lifecycle/OutputSupervisorLifecycle.h"\n#include "climate/output/persistence/OutputPersistenceCoordinator.h"\n#include "climate/output/supervisor/ClimateOutputSupervisorSink.h"\n#include "climate/runtime/console/Stage28ServiceConsole.h"\n#include "climate/runtime/core/RuntimeOutputTransport.h"\n#include "climate/runtime/diagnostics/RfDiagnostics.h"\n#include "climate/runtime/diagnostics/Stage28eDiagnosticsCore.h"\n#include "climate/runtime/schedule/ScheduleIntentAdapter.h"\n#include "climate/runtime/telemetry/RuntimeOutputTelemetryLog.h"\n#include "climate/runtime/telemetry/TelemetryReporter.h"\n'''
assert old_prefix in current_cpp
cpp.write_text(current_cpp.replace(old_prefix, new_prefix, 1))
