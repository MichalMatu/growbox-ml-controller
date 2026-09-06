#include "climate/runtime/Stage28eDiagnosticsCore.h"

namespace growbox::app::climate_io::runtime {

namespace {

constexpr std::uint64_t saturatingAdd(std::uint64_t left, std::uint64_t right) noexcept {
  return right > (std::numeric_limits<std::uint64_t>::max() - left)
             ? std::numeric_limits<std::uint64_t>::max()
             : left + right;
}

} // namespace

const char* diagnosticLogLevelName(DiagnosticLogLevel level) noexcept {
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

const char* diagnosticLogModuleName(DiagnosticLogModule module) noexcept {
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

StackMarginSeverity classifyStackMargin(std::uint32_t high_water_bytes,
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

void TimingAccumulator::observe(std::uint64_t duration_us) noexcept {
  sample_count = saturatingAdd(sample_count, 1U);
  total_us = saturatingAdd(total_us, duration_us);
  if (duration_us > max_us) {
    max_us = duration_us;
  }
  if (budget_us != 0U && duration_us > budget_us) {
    overrun_count = saturatingAdd(overrun_count, 1U);
  }
}

} // namespace growbox::app::climate_io::runtime
