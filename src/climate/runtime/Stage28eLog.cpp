#include "climate/runtime/Stage28eLog.h"

#include <esp_log.h>
#include <esp_timer.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>

#include <array>
#include <atomic>
#include <cstdarg>
#include <cstdio>

namespace growbox::app::climate_io::runtime {
namespace {

constexpr char kTag[] = "g28";
constexpr std::size_t kMessageBytes = 320U;

class AtomicModuleFilter final {
public:
  AtomicModuleFilter() noexcept {
    for (auto& level : levels_) {
      level.store(static_cast<std::uint8_t>(DiagnosticLogLevel::Info), std::memory_order_relaxed);
    }
  }

  void set(DiagnosticLogModule module, DiagnosticLogLevel level) noexcept {
    const std::size_t index = static_cast<std::size_t>(module);
    if (index < levels_.size()) {
      levels_[index].store(static_cast<std::uint8_t>(level), std::memory_order_relaxed);
    }
  }

  DiagnosticLogLevel get(DiagnosticLogModule module) const noexcept {
    const std::size_t index = static_cast<std::size_t>(module);
    if (index >= levels_.size()) {
      return DiagnosticLogLevel::Error;
    }
    return static_cast<DiagnosticLogLevel>(levels_[index].load(std::memory_order_relaxed));
  }

  bool enabled(DiagnosticLogModule module, DiagnosticLogLevel message_level) const noexcept {
    return static_cast<std::uint8_t>(message_level) <= static_cast<std::uint8_t>(get(module));
  }

private:
  std::array<std::atomic<std::uint8_t>, diagnosticLogModuleCount()> levels_{};
};

AtomicModuleFilter g_filter;
std::atomic<std::uint32_t> g_boot_id{0U};
std::atomic<std::uint32_t> g_sequence{0U};

esp_log_level_t toEspLogLevel(DiagnosticLogLevel level) noexcept {
  switch (level) {
  case DiagnosticLogLevel::Error:
    return ESP_LOG_ERROR;
  case DiagnosticLogLevel::Warn:
    return ESP_LOG_WARN;
  case DiagnosticLogLevel::Info:
    return ESP_LOG_INFO;
  case DiagnosticLogLevel::Debug:
    return ESP_LOG_DEBUG;
  case DiagnosticLogLevel::Trace:
    return ESP_LOG_VERBOSE;
  }
  return ESP_LOG_ERROR;
}

} // namespace

void configureStage28eLogging(const BootIdentity& boot) noexcept {
  g_boot_id.store(boot.boot_id, std::memory_order_relaxed);
  g_sequence.store(0U, std::memory_order_relaxed);
}

void setStage28eLogLevel(DiagnosticLogModule module, DiagnosticLogLevel level) noexcept {
  g_filter.set(module, level);
}

DiagnosticLogLevel stage28eLogLevel(DiagnosticLogModule module) noexcept {
  return g_filter.get(module);
}

void stage28eLogWrite(DiagnosticLogModule module, DiagnosticLogLevel level,
                      const char* format, ...) noexcept {
  if (format == nullptr || !g_filter.enabled(module, level)) {
    return;
  }

  std::array<char, kMessageBytes> message{};
  va_list arguments;
  va_start(arguments, format);
  const int formatted = std::vsnprintf(message.data(), message.size(), format, arguments);
  va_end(arguments);
  if (formatted < 0) {
    return;
  }
  message.back() = '\0';

  const std::int64_t monotonic_us = esp_timer_get_time();
  const std::uint64_t uptime_ms = monotonic_us > 0 ? static_cast<std::uint64_t>(monotonic_us) / 1000U : 0U;
  const std::uint32_t sequence = g_sequence.fetch_add(1U, std::memory_order_relaxed) + 1U;
  const char* task_name = pcTaskGetName(nullptr);
  const BaseType_t core_id = xPortGetCoreID();

  esp_log_write(toEspLogLevel(level), kTag,
                "u=%llu b=%08lx s=%lu %s/%s %s/c%ld %s",
                static_cast<unsigned long long>(uptime_ms),
                static_cast<unsigned long>(g_boot_id.load(std::memory_order_relaxed)),
                static_cast<unsigned long>(sequence), diagnosticLogLevelName(level),
                diagnosticLogModuleName(module), task_name != nullptr ? task_name : "?",
                static_cast<long>(core_id), message.data());
}

} // namespace growbox::app::climate_io::runtime
