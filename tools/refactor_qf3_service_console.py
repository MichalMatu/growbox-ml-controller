#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CPP = ROOT / "src/climate/runtime/Stage28ServiceConsole.cpp"
HDR = ROOT / "src/climate/runtime/Stage28ServiceConsole.h"
text = CPP.read_text()


def extract_method(name: str) -> str:
    marker = f"Stage28ServiceConsole::{name}"
    pos = text.index(marker)
    line_start = text.rfind("\n", 0, pos) + 1
    brace = text.index("{", pos)
    depth = 0
    i = brace
    in_str = False
    in_char = False
    esc = False
    line_comment = False
    block_comment = False
    while i < len(text):
        c = text[i]
        n = text[i + 1] if i + 1 < len(text) else ""
        if line_comment:
            if c == "\n":
                line_comment = False
            i += 1
            continue
        if block_comment:
            if c == "*" and n == "/":
                block_comment = False
                i += 2
                continue
            i += 1
            continue
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
            i += 1
            continue
        if in_char:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == "'":
                in_char = False
            i += 1
            continue
        if c == "/" and n == "/":
            line_comment = True
            i += 2
            continue
        if c == "/" and n == "*":
            block_comment = True
            i += 2
            continue
        if c == '"':
            in_str = True
        elif c == "'":
            in_char = True
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return text[line_start : i + 1]
        i += 1
    raise RuntimeError(name)


def transform(method: str, target: str) -> str:
    out = method.replace("Stage28ServiceConsole::", f"{target}::")
    out = out.replace("writeFormatted(", "sink_.writeFormatted(")
    out = out.replace("writeText(", "sink_.writeText(")
    return out

output_methods = "\n\n".join(
    transform(extract_method(name), "Stage28ServiceConsoleOutputCommands")
    for name in (
        "printAutomationStatus",
        "handleAutomationRequest",
        "printMaintenanceStatus",
        "handleMaintenanceRequest",
        "handleMaintenanceRaw",
        "handleManualOutput",
    )
)
output_methods = output_methods.replace(
    "void Stage28ServiceConsoleOutputCommands::printAutomationStatus() noexcept",
    "void Stage28ServiceConsoleOutputCommands::printAutomationStatus() noexcept",
)

status_method = transform(extract_method("printStatus"), "Stage28ServiceConsoleSystemCommands")
old_status = '''  if (config_.automation_control != nullptr) {\n    printAutomationStatus();\n  }\n  if (config_.maintenance_control != nullptr) {\n    printMaintenanceStatus();\n  }\n'''
assert old_status in status_method
status_method = status_method.replace(old_status, "  status_contributor_.printStatusDetails();\n")
system_methods = "\n\n".join(
    [status_method]
    + [
        transform(extract_method(name), "Stage28ServiceConsoleSystemCommands")
        for name in ("printSensors", "printRfList", "handleRfReceive", "handleRtcSetUnix")
    ]
)
storage_methods = "\n\n".join(
    transform(extract_method(name), "Stage28ServiceConsoleStorageCommands")
    for name in ("printSdLogStatus", "printSdLogList", "handleSdLogRead", "handleSdLogSelfTest")
)

sink_h = r'''#pragma once

#include <cstdarg>

namespace growbox::app::climate_io::runtime {

class ServiceConsoleTextSink {
public:
  virtual ~ServiceConsoleTextSink() = default;
  virtual void writeText(const char* text) noexcept = 0;
  void writeFormatted(const char* format, ...) noexcept;
};

class ServiceConsoleStatusContributor {
public:
  virtual ~ServiceConsoleStatusContributor() = default;
  virtual void printStatusDetails() noexcept = 0;
};

} // namespace growbox::app::climate_io::runtime
'''
sink_cpp = r'''#include "climate/runtime/ServiceConsoleTextSink.h"

#include <array>
#include <cstdio>

namespace growbox::app::climate_io::runtime {

void ServiceConsoleTextSink::writeFormatted(const char* format, ...) noexcept {
  if (format == nullptr) {
    return;
  }
  std::array<char, 640U> buffer{};
  va_list arguments;
  va_start(arguments, format);
  const int written = std::vsnprintf(buffer.data(), buffer.size(), format, arguments);
  va_end(arguments);
  if (written <= 0) {
    return;
  }
  buffer.back() = '\0';
  writeText(buffer.data());
}

} // namespace growbox::app::climate_io::runtime
'''

output_h = r'''#pragma once

#include "climate/runtime/ServiceConsoleTextSink.h"
#include "climate/runtime/Stage28ServiceConsoleCommand.h"

#include <cstdint>

namespace growbox::app::output {
class OutputAutomationControl;
class OutputManualControl;
class OutputMaintenanceControl;
} // namespace growbox::app::output

namespace growbox::app::climate_io::runtime {

class Stage28ServiceConsoleOutputCommands final : public ServiceConsoleStatusContributor {
public:
  struct Config {
    const bool* real_outputs_active{nullptr};
    ::growbox::app::output::OutputAutomationControl* automation_control{nullptr};
    ::growbox::app::output::OutputManualControl* manual_control{nullptr};
    ::growbox::app::output::OutputMaintenanceControl* maintenance_control{nullptr};
  };

  Stage28ServiceConsoleOutputCommands(Config config, ServiceConsoleTextSink& sink) noexcept
      : config_(config), sink_(sink) {}

  bool handle(const ServiceConsoleCommand& command, std::uint64_t now_ms) noexcept;
  void printStatusDetails() noexcept override;

private:
  bool realOutputsActive() const noexcept;
  const char* outputModeName() const noexcept;
  void printAutomationStatus() noexcept;
  void handleAutomationRequest(bool enabled) noexcept;
  void printMaintenanceStatus() noexcept;
  void handleMaintenanceRequest(bool enter) noexcept;
  void handleMaintenanceRaw(const ServiceConsoleCommand& command, std::uint64_t now_ms) noexcept;
  void handleManualOutput(const ServiceConsoleCommand& command, std::uint64_t now_ms) noexcept;

  Config config_{};
  ServiceConsoleTextSink& sink_;
};

} // namespace growbox::app::climate_io::runtime
'''

output_cpp = f'''#include "climate/runtime/Stage28ServiceConsoleOutputCommands.h"\n\n#include "climate/output/OutputAutomationControl.h"\n#include "climate/output/OutputMaintenanceControl.h"\n#include "climate/output/OutputManualControl.h"\n\nnamespace growbox::app::climate_io::runtime {{\nnamespace {{\n\nconst char* supervisorModeName(::growbox::app::output::SupervisorMode mode) noexcept {{\n  using ::growbox::app::output::SupervisorMode;\n  switch (mode) {{\n  case SupervisorMode::BootLocked: return "boot-locked";\n  case SupervisorMode::Arming: return "arming";\n  case SupervisorMode::Automatic: return "automatic";\n  case SupervisorMode::Recovering: return "recovering";\n  case SupervisorMode::Disabled: return "disabled";\n  case SupervisorMode::FaultLocked: return "fault-locked";\n  case SupervisorMode::MaintenanceLocked: return "maintenance-locked";\n  }}\n  return "unknown";\n}}\n\n}} // namespace\n\nbool Stage28ServiceConsoleOutputCommands::realOutputsActive() const noexcept {{\n  return config_.real_outputs_active != nullptr && *config_.real_outputs_active;\n}}\n\nconst char* Stage28ServiceConsoleOutputCommands::outputModeName() const noexcept {{\n  return realOutputsActive() ? "real-bounded" : "fake-locked";\n}}\n\nbool Stage28ServiceConsoleOutputCommands::handle(const ServiceConsoleCommand& command,\n                                                  std::uint64_t now_ms) noexcept {{\n  switch (command.kind) {{\n  case ServiceConsoleCommandKind::ManualOutput: handleManualOutput(command, now_ms); return true;\n  case ServiceConsoleCommandKind::AutomationStatus: printAutomationStatus(); return true;\n  case ServiceConsoleCommandKind::AutomationEnable: handleAutomationRequest(true); return true;\n  case ServiceConsoleCommandKind::AutomationDisable: handleAutomationRequest(false); return true;\n  case ServiceConsoleCommandKind::MaintenanceStatus: printMaintenanceStatus(); return true;\n  case ServiceConsoleCommandKind::MaintenanceEnter: handleMaintenanceRequest(true); return true;\n  case ServiceConsoleCommandKind::MaintenanceExit: handleMaintenanceRequest(false); return true;\n  case ServiceConsoleCommandKind::MaintenanceRawOutput: handleMaintenanceRaw(command, now_ms); return true;\n  default: return false;\n  }}\n}}\n\nvoid Stage28ServiceConsoleOutputCommands::printStatusDetails() noexcept {{\n  if (config_.automation_control != nullptr) {{\n    printAutomationStatus();\n  }}\n  if (config_.maintenance_control != nullptr) {{\n    printMaintenanceStatus();\n  }}\n}}\n\n{output_methods}\n\n}} // namespace growbox::app::climate_io::runtime\n'''

storage_h = r'''#pragma once

#include "climate/runtime/ServiceConsoleTextSink.h"
#include "climate/runtime/Stage28ServiceConsoleCommand.h"

namespace growbox::app::climate_io::storage {
class Stage27TelemetryLogger;
}

namespace growbox::app::climate_io::runtime {

class Stage28ServiceConsoleStorageCommands final {
public:
  Stage28ServiceConsoleStorageCommands(const storage::Stage27TelemetryLogger* storage_logger,
                                       ServiceConsoleTextSink& sink) noexcept
      : storage_logger_(storage_logger), sink_(sink) {}

  bool handle(const ServiceConsoleCommand& command) noexcept;

private:
  void printSdLogStatus() noexcept;
  void printSdLogList() noexcept;
  void handleSdLogRead(const ServiceConsoleCommand& command) noexcept;
  void handleSdLogSelfTest() noexcept;

  const storage::Stage27TelemetryLogger* storage_logger_{nullptr};
  ServiceConsoleTextSink& sink_;
};

} // namespace growbox::app::climate_io::runtime
'''
storage_methods = storage_methods.replace("config_.storage_logger", "storage_logger_")
storage_cpp = f'''#include "climate/runtime/Stage28ServiceConsoleStorageCommands.h"\n\n#include "climate/storage/Stage27FileDurability.h"\n#include "climate/storage/Stage27TelemetryLogger.h"\n\n#include <array>\n#include <cerrno>\n#include <cstdio>\n#include <cstring>\n#include <dirent.h>\n#include <sys/stat.h>\n#include <unistd.h>\n#include <mbedtls/base64.h>\n\nnamespace growbox::app::climate_io::runtime {{\nnamespace {{\nconstexpr char kSdLogDirectory[] = "/sdcard/GBLOG";\nconstexpr char kSdSelfTestPath[] = "/sdcard/GBLOG/STEST.TMP";\nconstexpr std::size_t kSdReadMaxBytes = 384U;\n\nbool isLogFilename(const char* name) noexcept {{\n  if (name == nullptr || std::strlen(name) != 11U || name[8] != '.' ||\n      (name[9] != 'J' && name[9] != 'j') || (name[10] != 'L' && name[10] != 'l'))\n    return false;\n  for (std::size_t i = 0U; i < 8U; ++i) {{\n    const char c = name[i];\n    if (!((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f') || (c >= 'A' && c <= 'F')))\n      return false;\n  }}\n  return true;\n}}\n\nstd::uint32_t crc32(const std::uint8_t* data, std::size_t length) noexcept {{\n  std::uint32_t crc = 0xFFFFFFFFU;\n  for (std::size_t i = 0U; i < length; ++i) {{\n    crc ^= data[i];\n    for (unsigned bit = 0U; bit < 8U; ++bit)\n      crc = (crc >> 1U) ^ ((crc & 1U) != 0U ? 0xEDB88320U : 0U);\n  }}\n  return crc ^ 0xFFFFFFFFU;\n}}\n}} // namespace\n\nbool Stage28ServiceConsoleStorageCommands::handle(const ServiceConsoleCommand& command) noexcept {{\n  switch (command.kind) {{\n  case ServiceConsoleCommandKind::SdLogStatus: printSdLogStatus(); return true;\n  case ServiceConsoleCommandKind::SdLogList: printSdLogList(); return true;\n  case ServiceConsoleCommandKind::SdLogRead: handleSdLogRead(command); return true;\n  case ServiceConsoleCommandKind::SdLogSelfTest: handleSdLogSelfTest(); return true;\n  default: return false;\n  }}\n}}\n\n{storage_methods}\n\n}} // namespace growbox::app::climate_io::runtime\n'''

system_h = r'''#pragma once

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
'''
system_cpp = f'''#include "climate/runtime/Stage28ServiceConsoleSystemCommands.h"\n\n#include "climate/native/BleClimateScanner.h"\n#include "climate/native/Ds3231ClockSource.h"\n#include "climate/native/Scd41InsideSource.h"\n#include "climate/rf433/Rf433HardwareConfig.h"\n#include "climate/runtime/EuropeWarsawTime.h"\n#include "climate/runtime/Stage28RfDiagnostics.h"\n#include "climate/runtime/Stage28ePlatformDiagnostics.h"\n#include "climate/storage/Stage27TelemetryLogger.h"\n\n#include <array>\n#include <cstring>\n#include <esp_heap_caps.h>\n#include <freertos/FreeRTOS.h>\n#include <freertos/idf_additions.h>\n#include <freertos/task.h>\n#include <sdkconfig.h>\n\nnamespace growbox::app::climate_io::runtime {{\nnamespace {{\nstruct KnownRfDevice {{ ServiceConsoleRfDevice id; const char* physical_name; const rf433::RemoteSocketHardwareConfig* hardware; const char* tx_status; }};\nconstexpr std::array<KnownRfDevice, 3U> kKnownRfDevices{{{{\n    {{ServiceConsoleRfDevice::Lamp, "lamp", &rf433::kRemoteSocket2, "physically validated; Shelly signature about +97W"}},\n    {{ServiceConsoleRfDevice::Fan, "fan", &rf433::kRemoteSocket1, "physically validated; Shelly signature about +2.9W"}},\n    {{ServiceConsoleRfDevice::Humidifier, "humidifier", &rf433::kRemoteSocket3, "physically validated; Shelly signature about +15.7W"}},\n}}}};\n\nstd::uint32_t knownConfiguredTaskStackBytes(const char* name) noexcept {{\n  if (name == nullptr) return 0U;\n  if (std::strcmp(name, "main") == 0) return static_cast<std::uint32_t>(CONFIG_ESP_MAIN_TASK_STACK_SIZE);\n  if (std::strcmp(name, "stage27_store") == 0) return storage::Stage27TelemetryLogger::taskStackBytes();\n#if defined(CONFIG_ESP_TIMER_TASK_STACK_SIZE)\n  if (std::strcmp(name, "esp_timer") == 0) return static_cast<std::uint32_t>(CONFIG_ESP_TIMER_TASK_STACK_SIZE);\n#endif\n#if defined(CONFIG_ESP_SYSTEM_EVENT_TASK_STACK_SIZE)\n  if (std::strcmp(name, "sys_evt") == 0) return static_cast<std::uint32_t>(CONFIG_ESP_SYSTEM_EVENT_TASK_STACK_SIZE);\n#endif\n#if defined(CONFIG_BT_NIMBLE_HOST_TASK_STACK_SIZE)\n  if (std::strcmp(name, "nimble_host") == 0) return static_cast<std::uint32_t>(CONFIG_BT_NIMBLE_HOST_TASK_STACK_SIZE);\n#endif\n  return 0U;\n}}\n\nconst char* stackMarginSeverityName(StackMarginSeverity severity) noexcept {{\n  switch (severity) {{\n  case StackMarginSeverity::Normal: return "normal";\n  case StackMarginSeverity::Warning: return "warning";\n  case StackMarginSeverity::Critical: return "critical";\n  case StackMarginSeverity::Unknown: break;\n  }}\n  return "unknown";\n}}\n}} // namespace\n\nbool Stage28ServiceConsoleSystemCommands::realOutputsActive() const noexcept {{\n  return config_.real_outputs_active != nullptr && *config_.real_outputs_active;\n}}\nconst char* Stage28ServiceConsoleSystemCommands::outputModeName() const noexcept {{\n  return realOutputsActive() ? "real-bounded" : "fake-locked";\n}}\n\nbool Stage28ServiceConsoleSystemCommands::handle(const ServiceConsoleCommand& command, std::uint64_t now_ms) noexcept {{\n  switch (command.kind) {{\n  case ServiceConsoleCommandKind::Status: printStatus(now_ms); return true;\n  case ServiceConsoleCommandKind::Sensors: printSensors(now_ms); return true;\n  case ServiceConsoleCommandKind::RfList: printRfList(); return true;\n  case ServiceConsoleCommandKind::RfReceive: handleRfReceive(command); return true;\n  case ServiceConsoleCommandKind::RtcSetUnix: handleRtcSetUnix(command, now_ms); return true;\n  default: return false;\n  }}\n}}\n\n{system_methods}\n\n}} // namespace growbox::app::climate_io::runtime\n'''

console_h = r'''#pragma once

#include "climate/runtime/ServiceConsoleTextSink.h"
#include "climate/runtime/Stage28ServiceConsoleOutputCommands.h"
#include "climate/runtime/Stage28ServiceConsoleStorageCommands.h"
#include "climate/runtime/Stage28ServiceConsoleSystemCommands.h"
#include "climate/runtime/Stage28eDiagnosticsCore.h"

#include <array>
#include <cstddef>
#include <cstdint>

namespace growbox::app::climate_io::storage { class Stage27TelemetryLogger; }
namespace growbox::app::output {
class OutputAutomationControl;
class OutputManualControl;
class OutputMaintenanceControl;
}
namespace growbox::app::climate_io::native {
class BleClimateScanner;
class Scd41InsideSource;
class Ds3231ClockSource;
}
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
  bool ready() const noexcept { return ready_; }

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
'''

begin_method = extract_method("begin")
poll_method = extract_method("poll")
help_method = extract_method("printHelp")
write_method = extract_method("writeText")
prompt_method = extract_method("printPrompt")
begin_method = begin_method.replace("config_.enabled", "enabled_")
# inherited writeFormatted stays callable as before
process_method = r'''void Stage28ServiceConsole::processLine(std::uint64_t now_ms) noexcept {
  const ServiceConsoleCommand command = parseServiceConsoleCommand(line_.data());
  if (command.kind == ServiceConsoleCommandKind::None) {
    return;
  }
  if (command.kind == ServiceConsoleCommandKind::Help) {
    printHelp();
    return;
  }
  if (output_commands_.handle(command, now_ms) || storage_commands_.handle(command) ||
      system_commands_.handle(command, now_ms)) {
    return;
  }
  writeText("error: unknown/invalid command; type 'help'\r\n");
}
'''
constructor = r'''Stage28ServiceConsole::Stage28ServiceConsole(Config config, native::BleClimateScanner& ble,
                                             native::Scd41InsideSource& scd41,
                                             native::Ds3231ClockSource& clock,
                                             Stage28RfDiagnostics& rf_diagnostics) noexcept
    : enabled_(config.enabled), real_outputs_active_(config.real_outputs_active),
      output_commands_({config.real_outputs_active, config.automation_control, config.manual_control,
                        config.maintenance_control}, *this),
      storage_commands_(config.storage_logger, *this),
      system_commands_({config.firmware_sha, config.real_outputs_active, config.timing_metrics}, ble,
                       scd41, clock, rf_diagnostics, *this, output_commands_) {}
'''
console_cpp = f'''#include "climate/runtime/Stage28ServiceConsole.h"\n\n#include <driver/uart.h>\n#include <sdkconfig.h>\n#include <array>\n#include <cstring>\n\nnamespace growbox::app::climate_io::runtime {{\nnamespace {{\n#if !defined(CONFIG_ESP_CONSOLE_UART_NUM)\n#error "Stage28 service console requires an ESP-IDF UART primary console"\n#endif\nconstexpr uart_port_t kServiceConsoleUart = static_cast<uart_port_t>(CONFIG_ESP_CONSOLE_UART_NUM);\nconstexpr int kServiceConsoleRxBufferBytes = 1024;\nconstexpr int kServiceConsoleTxBufferBytes = 2048;\n}} // namespace\n\n{constructor}\n\nbool Stage28ServiceConsole::realOutputsActive() const noexcept {{\n  return real_outputs_active_ != nullptr && *real_outputs_active_;\n}}\nconst char* Stage28ServiceConsole::outputModeName() const noexcept {{\n  return realOutputsActive() ? "real-bounded" : "fake-locked";\n}}\n\n{begin_method}\n\n{poll_method}\n\n{process_method}\n\n{help_method}\n\n{write_method}\n\n{prompt_method}\n\n}} // namespace growbox::app::climate_io::runtime\n'''

for content in (output_cpp, storage_cpp, system_cpp):
    assert "Stage28ServiceConsole::" not in content

(ROOT / "src/climate/runtime/ServiceConsoleTextSink.h").write_text(sink_h)
(ROOT / "src/climate/runtime/ServiceConsoleTextSink.cpp").write_text(sink_cpp)
(ROOT / "src/climate/runtime/Stage28ServiceConsoleOutputCommands.h").write_text(output_h)
(ROOT / "src/climate/runtime/Stage28ServiceConsoleOutputCommands.cpp").write_text(output_cpp)
(ROOT / "src/climate/runtime/Stage28ServiceConsoleStorageCommands.h").write_text(storage_h)
(ROOT / "src/climate/runtime/Stage28ServiceConsoleStorageCommands.cpp").write_text(storage_cpp)
(ROOT / "src/climate/runtime/Stage28ServiceConsoleSystemCommands.h").write_text(system_h)
(ROOT / "src/climate/runtime/Stage28ServiceConsoleSystemCommands.cpp").write_text(system_cpp)
HDR.write_text(console_h)
CPP.write_text(console_cpp)

# Integrate production sources.
cmake = ROOT / "src/CMakeLists.txt"
cm = cmake.read_text()
needle = '      "climate/runtime/Stage28ServiceConsole.cpp"\n'
assert cm.count(needle) == 1
extra = needle + '      "climate/runtime/ServiceConsoleTextSink.cpp"\n      "climate/runtime/Stage28ServiceConsoleOutputCommands.cpp"\n      "climate/runtime/Stage28ServiceConsoleStorageCommands.cpp"\n      "climate/runtime/Stage28ServiceConsoleSystemCommands.cpp"\n'
cmake.write_text(cm.replace(needle, extra, 1))

# Architecture guard: router must remain transport/framing only.
guard = ROOT / "scripts/check_service_console_boundaries.py"
guard.write_text(r'''#!/usr/bin/env python3
from pathlib import Path
import sys
root = Path(__file__).resolve().parents[1]
router = (root / "src/climate/runtime/Stage28ServiceConsole.cpp").read_text()
forbidden = (
    "OutputAutomationControl.h", "OutputMaintenanceControl.h", "OutputManualControl.h",
    "Stage27TelemetryLogger.h", "Stage27FileDurability.h", "Rf433HardwareConfig.h",
    "printSdLogStatus", "handleSdLogRead", "handleManualOutput", "handleRtcSetUnix",
    "printSensors", "printRfList", "handleRfReceive",
)
errors = [item for item in forbidden if item in router]
required = (
    "output_commands_.handle", "storage_commands_.handle", "system_commands_.handle",
    "uart_read_bytes", "uart_write_bytes",
)
errors += [f"missing:{item}" for item in required if item not in router]
if errors:
    print("SERVICE_CONSOLE_BOUNDARY_FAIL " + ",".join(errors), file=sys.stderr)
    raise SystemExit(1)
print("SERVICE_CONSOLE_BOUNDARY_PASS")
''')

qg = ROOT / "scripts/quality_gate_push.sh"
q = qg.read_text()
needle = 'echo "==> runtime configuration SSOT"\n"$PY" "${ROOT}/scripts/check_runtime_config_ssot.py"\n'
assert q.count(needle) == 1
qg.write_text(q.replace(needle, needle + '\necho "==> service console boundaries"\n"$PY" "${ROOT}/scripts/check_service_console_boundaries.py"\n', 1))
