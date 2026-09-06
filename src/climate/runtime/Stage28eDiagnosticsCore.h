#pragma once

#include <array>
#include <cstddef>
#include <cstdint>
#include <limits>

namespace growbox::app::climate_io::runtime {

enum class DiagnosticLogLevel : std::uint8_t {
  Error = 0U,
  Warn,
  Info,
  Debug,
  Trace,
};

enum class DiagnosticLogModule : std::uint8_t {
  Sys = 0U,
  Mem,
  Task,
  Ble,
  Sensor,
  Control,
  Ah,
  Arbiter,
  Rf,
  Shelly,
  Storage,
  Telemetry,
  Safety,
  Watchdog,
  Count,
};

constexpr std::size_t diagnosticLogModuleCount() noexcept {
  return static_cast<std::size_t>(DiagnosticLogModule::Count);
}

const char* diagnosticLogLevelName(DiagnosticLogLevel level) noexcept;
const char* diagnosticLogModuleName(DiagnosticLogModule module) noexcept;

class DiagnosticLogFilter final {
public:
  constexpr DiagnosticLogFilter() noexcept {
    for (auto& level : levels_) {
      level = DiagnosticLogLevel::Info;
    }
  }

  constexpr void setLevel(DiagnosticLogModule module, DiagnosticLogLevel level) noexcept {
    const auto index = static_cast<std::size_t>(module);
    if (index < levels_.size()) {
      levels_[index] = level;
    }
  }

  constexpr DiagnosticLogLevel level(DiagnosticLogModule module) const noexcept {
    const auto index = static_cast<std::size_t>(module);
    return index < levels_.size() ? levels_[index] : DiagnosticLogLevel::Error;
  }

  constexpr bool enabled(DiagnosticLogModule module, DiagnosticLogLevel message_level) const noexcept {
    return static_cast<std::uint8_t>(message_level) <= static_cast<std::uint8_t>(level(module));
  }

private:
  std::array<DiagnosticLogLevel, diagnosticLogModuleCount()> levels_{};
};

struct HeapRegionMetrics {
  std::uint32_t total_bytes{0U};
  std::uint32_t free_bytes{0U};
  std::uint32_t minimum_free_bytes{0U};
  std::uint32_t largest_free_block_bytes{0U};
};

struct RuntimeMemoryMetrics {
  HeapRegionMetrics internal{};
  HeapRegionMetrics psram{};
};

enum class StackMarginSeverity : std::uint8_t {
  Unknown = 0U,
  Normal,
  Warning,
  Critical,
};

StackMarginSeverity classifyStackMargin(std::uint32_t high_water_bytes,
                                        std::uint32_t configured_stack_bytes) noexcept;

struct TaskStackMetrics {
  const char* name{nullptr};
  std::int32_t core_id{-1};
  std::uint32_t priority{0U};
  std::uint32_t configured_stack_bytes{0U};
  std::uint32_t high_water_bytes{0U};
  StackMarginSeverity severity{StackMarginSeverity::Unknown};
};

struct TimingAccumulator {
  std::uint64_t sample_count{0U};
  std::uint64_t total_us{0U};
  std::uint64_t max_us{0U};
  std::uint64_t overrun_count{0U};
  std::uint64_t budget_us{0U};

  void observe(std::uint64_t duration_us) noexcept;
};

struct BootIdentity {
  std::uint32_t boot_id{0U};
  std::int32_t reset_reason{0};
  std::uint64_t started_monotonic_us{0U};
  const char* firmware_sha{"unknown"};
};

} // namespace growbox::app::climate_io::runtime
