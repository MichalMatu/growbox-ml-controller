#pragma once

#include "climate/native/BleClimateScanner.h"
#include "climate/native/Ds3231ClockSource.h"
#include "climate/native/Scd41InsideSource.h"
#include "climate/runtime/Stage28RfDiagnostics.h"
#include "climate/runtime/Stage28ServiceConsoleCommand.h"

#include <array>
#include <cstddef>
#include <cstdint>

namespace growbox::app::climate_io::runtime {

class Stage28ServiceConsole final {
public:
  struct Config {
    bool enabled{true};
    const char* firmware_sha{"unknown"};
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
  void printStatus(std::uint64_t now_ms) noexcept;
  void printSensors(std::uint64_t now_ms) noexcept;
  void printRfList() noexcept;
  void handleRfTransmit(const ServiceConsoleCommand& command) noexcept;
  void handleRfReceive(const ServiceConsoleCommand& command) noexcept;
  void writeText(const char* text) noexcept;
  void writeFormatted(const char* format, ...) noexcept;
  void printPrompt() noexcept;

  Config config_{};
  native::BleClimateScanner& ble_;
  native::Scd41InsideSource& scd41_;
  native::Ds3231ClockSource& clock_;
  Stage28RfDiagnostics& rf_diagnostics_;
  std::array<char, kMaximumLineBytes + 1U> line_{};
  std::size_t length_{0U};
  bool discarding_{false};
  bool ready_{false};
};

} // namespace growbox::app::climate_io::runtime
