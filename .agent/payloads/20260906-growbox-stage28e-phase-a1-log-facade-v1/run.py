from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text()
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"expected one match in {path}, got {count}")
    p.write_text(text.replace(old, new, 1))

header = r'''#pragma once

#include "climate/runtime/Stage28eDiagnosticsCore.h"

#include <cstdint>

#ifndef GROWBOX_STAGE28E_LOG_COMPILE_LEVEL
#define GROWBOX_STAGE28E_LOG_COMPILE_LEVEL 2
#endif

static_assert(GROWBOX_STAGE28E_LOG_COMPILE_LEVEL >= 0 && GROWBOX_STAGE28E_LOG_COMPILE_LEVEL <= 4,
              "GROWBOX_STAGE28E_LOG_COMPILE_LEVEL must be 0..4");

namespace growbox::app::climate_io::runtime {

void configureStage28eLogging(const BootIdentity& boot) noexcept;
void setStage28eLogLevel(DiagnosticLogModule module, DiagnosticLogLevel level) noexcept;
DiagnosticLogLevel stage28eLogLevel(DiagnosticLogModule module) noexcept;
void stage28eLogWrite(DiagnosticLogModule module, DiagnosticLogLevel level,
                      const char* format, ...) noexcept;

} // namespace growbox::app::climate_io::runtime

#if GROWBOX_STAGE28E_LOG_COMPILE_LEVEL >= 0
#define GROWBOX_STAGE28E_LOG_ERROR(module, ...) \
  do { ::growbox::app::climate_io::runtime::stage28eLogWrite( \
      (module), ::growbox::app::climate_io::runtime::DiagnosticLogLevel::Error, __VA_ARGS__); } while (0)
#else
#define GROWBOX_STAGE28E_LOG_ERROR(module, ...) do { } while (0)
#endif

#if GROWBOX_STAGE28E_LOG_COMPILE_LEVEL >= 1
#define GROWBOX_STAGE28E_LOG_WARN(module, ...) \
  do { ::growbox::app::climate_io::runtime::stage28eLogWrite( \
      (module), ::growbox::app::climate_io::runtime::DiagnosticLogLevel::Warn, __VA_ARGS__); } while (0)
#else
#define GROWBOX_STAGE28E_LOG_WARN(module, ...) do { } while (0)
#endif

#if GROWBOX_STAGE28E_LOG_COMPILE_LEVEL >= 2
#define GROWBOX_STAGE28E_LOG_INFO(module, ...) \
  do { ::growbox::app::climate_io::runtime::stage28eLogWrite( \
      (module), ::growbox::app::climate_io::runtime::DiagnosticLogLevel::Info, __VA_ARGS__); } while (0)
#else
#define GROWBOX_STAGE28E_LOG_INFO(module, ...) do { } while (0)
#endif

#if GROWBOX_STAGE28E_LOG_COMPILE_LEVEL >= 3
#define GROWBOX_STAGE28E_LOG_DEBUG(module, ...) \
  do { ::growbox::app::climate_io::runtime::stage28eLogWrite( \
      (module), ::growbox::app::climate_io::runtime::DiagnosticLogLevel::Debug, __VA_ARGS__); } while (0)
#else
#define GROWBOX_STAGE28E_LOG_DEBUG(module, ...) do { } while (0)
#endif

#if GROWBOX_STAGE28E_LOG_COMPILE_LEVEL >= 4
#define GROWBOX_STAGE28E_LOG_TRACE(module, ...) \
  do { ::growbox::app::climate_io::runtime::stage28eLogWrite( \
      (module), ::growbox::app::climate_io::runtime::DiagnosticLogLevel::Trace, __VA_ARGS__); } while (0)
#else
#define GROWBOX_STAGE28E_LOG_TRACE(module, ...) do { } while (0)
#endif
'''
Path("src/climate/runtime/Stage28eLog.h").write_text(header)

source = r'''#include "climate/runtime/Stage28eLog.h"

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
'''
Path("src/climate/runtime/Stage28eLog.cpp").write_text(source)

replace_once(
    "src/CMakeLists.txt",
    '      "climate/runtime/Stage28ServiceConsoleCommand.cpp"\n',
    '      "climate/runtime/Stage28ServiceConsoleCommand.cpp"\n'
    '      "climate/runtime/Stage28eLog.cpp"\n',
)
replace_once(
    "src/CMakeLists.txt",
    'set(GROWBOX_STAGE28_THERMAL_TEST_SEQUENCE_ENABLED "0" CACHE STRING "Enable bounded Gate6 thermal test sequence")\n',
    'set(GROWBOX_STAGE28_THERMAL_TEST_SEQUENCE_ENABLED "0" CACHE STRING "Enable bounded Gate6 thermal test sequence")\n'
    'set(GROWBOX_STAGE28E_LOG_COMPILE_LEVEL "2" CACHE STRING "Stage28E diagnostic compile-time log level 0=ERROR..4=TRACE")\n',
)
replace_once(
    "src/CMakeLists.txt",
    '    GROWBOX_STAGE28_THERMAL_TEST_SEQUENCE_ENABLED=${GROWBOX_STAGE28_THERMAL_TEST_SEQUENCE_ENABLED}\n',
    '    GROWBOX_STAGE28_THERMAL_TEST_SEQUENCE_ENABLED=${GROWBOX_STAGE28_THERMAL_TEST_SEQUENCE_ENABLED}\n'
    '    GROWBOX_STAGE28E_LOG_COMPILE_LEVEL=${GROWBOX_STAGE28E_LOG_COMPILE_LEVEL}\n',
)

replace_once(
    "src/climate/ClimateV6RealInputRuntime.cpp",
    '#include "climate/runtime/Stage28ServiceConsole.h"\n',
    '#include "climate/runtime/Stage28ServiceConsole.h"\n'
    '#include "climate/runtime/Stage28eLog.h"\n',
)
replace_once(
    "src/climate/ClimateV6RealInputRuntime.cpp",
    '  const esp_reset_reason_t reset_reason =\n'
    '      static_cast<esp_reset_reason_t>(boot_identity.reset_reason);\n',
    '  const esp_reset_reason_t reset_reason =\n'
    '      static_cast<esp_reset_reason_t>(boot_identity.reset_reason);\n'
    '  runtime::configureStage28eLogging(boot_identity);\n',
)
replace_once(
    "src/climate/ClimateV6RealInputRuntime.cpp",
    '  ESP_LOGI(kTag,\n'
    '           "Stage27 soak boot: firmware_sha=%s boot_id=%08lx reset_reason=%d started_us=%llu",\n'
    '           boot_identity.firmware_sha, static_cast<unsigned long>(boot_identity.boot_id),\n'
    '           static_cast<int>(reset_reason),\n'
    '           static_cast<unsigned long long>(boot_identity.started_monotonic_us));\n',
    '  GROWBOX_STAGE28E_LOG_INFO(\n'
    '      runtime::DiagnosticLogModule::Sys,\n'
    '      "boot firmware_sha=%s reset_reason=%d started_us=%llu outputs=%s",\n'
    '      boot_identity.firmware_sha, static_cast<int>(reset_reason),\n'
    '      static_cast<unsigned long long>(boot_identity.started_monotonic_us),\n'
    '      real_output_ready ? "real-bounded" : "fake-locked");\n',
)
