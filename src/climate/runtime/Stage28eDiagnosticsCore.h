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

inline const char* diagnosticLogLevelName(DiagnosticLogLevel level) noexcept {
  switch (level) {
  case DiagnosticLogLevel::Error:
    return "ERROR";
  case DiagnosticLogLevel::Warn:
    return "WARN";
  case DiagnosticLogLevel::Info:
    return "INFO";
  case DiagnosticLogLevel::Debug:
    return "DEBUG";
  case DiagnosticLogLevel::Trace:
    return "TRACE";
  }
  return "ERROR";
}

inline const char* diagnosticLogModuleName(DiagnosticLogModule module) noexcept {
  switch (module) {
  case DiagnosticLogModule::Sys:
    return "SYS";
  case DiagnosticLogModule::Mem:
    return "MEM";
  case DiagnosticLogModule::Task:
    return "TASK";
  case DiagnosticLogModule::Ble:
    return "BLE";
  case DiagnosticLogModule::Sensor:
    return "SENSOR";
  case DiagnosticLogModule::Control:
    return "CONTROL";
  case DiagnosticLogModule::Ah:
    return "AH";
  case DiagnosticLogModule::Arbiter:
    return "ARBITER";
  case DiagnosticLogModule::Rf:
    return "RF";
  case DiagnosticLogModule::Shelly:
    return "SHELLY";
  case DiagnosticLogModule::Storage:
    return "STORAGE";
  case DiagnosticLogModule::Telemetry:
    return "TELEMETRY";
  case DiagnosticLogModule::Safety:
    return "SAFETY";
  case DiagnosticLogModule::Watchdog:
    return "WATCHDOG";
  case DiagnosticLogModule::Count:
    break;
  }
  return "SYS";
}

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

inline StackMarginSeverity classifyStackMargin(std::uint32_t high_water_bytes,
                                               std::uint32_t configured_stack_bytes) noexcept {
  if (configured_stack_bytes == 0U || high_water_bytes > configured_stack_bytes) {
    return StackMarginSeverity::Unknown;
  }

  const std::uint64_t scaled = static_cast<std::uint64_t>(high_water_bytes) * 100U;
  const std::uint64_t critical_threshold = static_cast<std::uint64_t>(configured_stack_bytes) * 10U;
  const std::uint64_t warning_threshold = static_cast<std::uint64_t>(configured_stack_bytes) * 25U;

  if (scaled < critical_threshold) {
    return StackMarginSeverity::Critical;
  }
  if (scaled < warning_threshold) {
    return StackMarginSeverity::Warning;
  }
  return StackMarginSeverity::Normal;
}

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

  void observe(std::uint64_t duration_us) noexcept {
    const auto max_value = std::numeric_limits<std::uint64_t>::max();
    sample_count = sample_count == max_value ? max_value : sample_count + 1U;
    total_us = duration_us > (max_value - total_us) ? max_value : total_us + duration_us;
    if (duration_us > max_us) {
      max_us = duration_us;
    }
    if (budget_us != 0U && duration_us > budget_us) {
      overrun_count = overrun_count == max_value ? max_value : overrun_count + 1U;
    }
  }
};

struct BootIdentity {
  std::uint32_t boot_id{0U};
  std::int32_t reset_reason{0};
  std::uint64_t started_monotonic_us{0U};
  const char* firmware_sha{"unknown"};
};

} // namespace growbox::app::climate_io::runtime
