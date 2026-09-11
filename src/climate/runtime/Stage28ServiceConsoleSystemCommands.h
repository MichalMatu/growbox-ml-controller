#pragma once

#include "climate/runtime/ServiceConsoleTextSink.h"
#include "climate/runtime/Stage28ServiceConsoleCommand.h"
#include "climate/runtime/Stage28eDiagnosticsCore.h"

#include <cstdint>

namespace growbox::app::climate_io::native {
class BleClimateScanner;
class Scd41InsideSource;
class Ds3231ClockSource;
}
namespace growbox::app::climate_io::runtime {
class Stage28RfDiagnostics;

class Stage28ServiceConsoleSystemCommands final {
public:
  struct Config {
    const char* firmware_sha{"unknown"};
    const bool* real_outputs_active{nullptr};
    const RuntimeTimingMetrics* timing_metrics{nullptr};
  };

  Stage28ServiceConsoleSystemCommands(Config config, native::BleClimateScanner& ble,
                                      native::Scd41InsideSource& scd41,
                                      native::Ds3231ClockSource& clock,
                                      Stage28RfDiagnostics& rf_diagnostics,
                                      ServiceConsoleTextSink& sink,
                                      ServiceConsoleStatusContributor& status_contributor) noexcept
      : config_(config), ble_(ble), scd41_(scd41), clock_(clock),
        rf_diagnostics_(rf_diagnostics), sink_(sink), status_contributor_(status_contributor) {}

  bool handle(const ServiceConsoleCommand& command, std::uint64_t now_ms) noexcept;

private:
  bool realOutputsActive() const noexcept;
  const char* outputModeName() const noexcept;
  void printStatus(std::uint64_t now_ms) noexcept;
  void printSensors(std::uint64_t now_ms) noexcept;
  void printRfList() noexcept;
  void handleRfReceive(const ServiceConsoleCommand& command) noexcept;
  void handleRtcSetUnix(const ServiceConsoleCommand& command, std::uint64_t now_ms) noexcept;

  Config config_{};
  native::BleClimateScanner& ble_;
  native::Scd41InsideSource& scd41_;
  native::Ds3231ClockSource& clock_;
  Stage28RfDiagnostics& rf_diagnostics_;
  ServiceConsoleTextSink& sink_;
  ServiceConsoleStatusContributor& status_contributor_;
};

} // namespace growbox::app::climate_io::runtime
