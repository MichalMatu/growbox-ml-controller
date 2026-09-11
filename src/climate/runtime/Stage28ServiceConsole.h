#pragma once

#include "climate/runtime/ServiceConsoleTextSink.h"
#include "climate/runtime/Stage28ServiceConsoleOutputCommands.h"
#include "climate/runtime/Stage28ServiceConsoleStorageCommands.h"
#include "climate/runtime/Stage28ServiceConsoleSystemCommands.h"
#include "climate/runtime/Stage28eDiagnosticsCore.h"

#include <array>
#include <cstddef>
#include <cstdint>

namespace growbox::app::climate_io::storage {
class Stage27TelemetryLogger;
}
namespace growbox::app::output {
class OutputAutomationControl;
class OutputManualControl;
class OutputMaintenanceControl;
} // namespace growbox::app::output
namespace growbox::app::climate_io::native {
class BleClimateScanner;
class Scd41InsideSource;
class Ds3231ClockSource;
} // namespace growbox::app::climate_io::native
namespace growbox::app::climate_io::runtime {
class Stage28RfDiagnostics;

class Stage28ServiceConsole final : public ServiceConsoleTextSink {
public:
  struct Config {
    bool enabled{true};
    const char* firmware_sha{"unknown"};
    const bool* real_outputs_active{nullptr};
    const storage::Stage27TelemetryLogger* storage_logger{nullptr};
    const RuntimeTimingMetrics* timing_metrics{nullptr};
    ::growbox::app::output::OutputAutomationControl* automation_control{nullptr};
    ::growbox::app::output::OutputManualControl* manual_control{nullptr};
    ::growbox::app::output::OutputMaintenanceControl* maintenance_control{nullptr};
  };

  Stage28ServiceConsole(Config config, native::BleClimateScanner& ble,
                        native::Scd41InsideSource& scd41, native::Ds3231ClockSource& clock,
                        Stage28RfDiagnostics& rf_diagnostics) noexcept;
  bool begin() noexcept;
  void poll(std::uint64_t now_ms) noexcept;
  bool ready() const noexcept {
    return ready_;
  }

private:
  static constexpr std::size_t kMaximumLineBytes = 160U;
  void processLine(std::uint64_t now_ms) noexcept;
  void printHelp() noexcept;
  void writeText(const char* text) noexcept override;
  void printPrompt() noexcept;
  bool realOutputsActive() const noexcept;
  const char* outputModeName() const noexcept;

  bool enabled_{true};
  const bool* real_outputs_active_{nullptr};
  Stage28ServiceConsoleOutputCommands output_commands_;
  Stage28ServiceConsoleStorageCommands storage_commands_;
  Stage28ServiceConsoleSystemCommands system_commands_;
  std::array<char, kMaximumLineBytes + 1U> line_{};
  std::size_t length_{0U};
  bool discarding_{false};
  bool ready_{false};
};

} // namespace growbox::app::climate_io::runtime
