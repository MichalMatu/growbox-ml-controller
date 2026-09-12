#include "climate/runtime/console/Stage28ServiceConsole.h"

#include "climate/runtime/console/Stage28ServiceConsoleRouter.h"

#include <array>
#include <cstring>
#include <driver/uart.h>
#include <sdkconfig.h>

namespace growbox::app::climate_io::runtime {
namespace {
#if !defined(CONFIG_ESP_CONSOLE_UART_NUM)
#error "Stage28 service console requires an ESP-IDF UART primary console"
#endif
constexpr uart_port_t kServiceConsoleUart = static_cast<uart_port_t>(CONFIG_ESP_CONSOLE_UART_NUM);
constexpr int kServiceConsoleRxBufferBytes = 1024;
constexpr int kServiceConsoleTxBufferBytes = 2048;
} // namespace

Stage28ServiceConsole::Stage28ServiceConsole(Config config, native::BleClimateScanner& ble,
                                             native::Scd41InsideSource& scd41,
                                             native::Ds3231ClockSource& clock,
                                             RfDiagnostics& rf_diagnostics) noexcept
    : enabled_(config.enabled), real_outputs_active_(config.real_outputs_active),
      output_commands_({config.real_outputs_active, config.automation_control,
                        config.manual_control, config.maintenance_control},
                       *this),
      storage_commands_(config.storage_logger, *this),
      system_commands_({config.firmware_sha, config.real_outputs_active, config.timing_metrics},
                       ble, scd41, clock, rf_diagnostics, *this, output_commands_) {}

bool Stage28ServiceConsole::realOutputsActive() const noexcept {
  return real_outputs_active_ != nullptr && *real_outputs_active_;
}
const char* Stage28ServiceConsole::outputModeName() const noexcept {
  return realOutputsActive() ? "real-bounded" : "fake-locked";
}

bool Stage28ServiceConsole::begin() noexcept {
  if (!enabled_) {
    return false;
  }

  if (!uart_is_driver_installed(kServiceConsoleUart)) {
    const esp_err_t install_result =
        uart_driver_install(kServiceConsoleUart, kServiceConsoleRxBufferBytes,
                            kServiceConsoleTxBufferBytes, 0, nullptr, 0);
    if (install_result != ESP_OK) {
      return false;
    }
  }
  if (uart_flush_input(kServiceConsoleUart) != ESP_OK) {
    return false;
  }

  ready_ = true;
  writeText("\r\n=== Growbox service console ===\r\n");
  writeFormatted("Automatic output mode: %s.\r\n", outputModeName());
  printHelp();
  printPrompt();
  return true;
}

void Stage28ServiceConsole::poll(std::uint64_t now_ms) noexcept {
  if (!ready_) {
    return;
  }

  std::array<std::uint8_t, 96U> buffer{};
  const int received = uart_read_bytes(kServiceConsoleUart, buffer.data(), buffer.size(), 0U);
  if (received <= 0) {
    return;
  }

  for (int index = 0; index < received; ++index) {
    const char character = static_cast<char>(buffer[index]);
    if (character == '\r') {
      continue;
    }
    if (character == '\b' || character == 0x7F) {
      if (!discarding_ && length_ > 0U) {
        --length_;
        writeText("\b \b");
      }
      continue;
    }
    if (character == '\n') {
      writeText("\r\n");
      if (discarding_) {
        writeText("error: command line too long\r\n");
      } else if (length_ > 0U) {
        line_[length_] = '\0';
        processLine(now_ms);
      }
      length_ = 0U;
      discarding_ = false;
      printPrompt();
      continue;
    }
    if (discarding_) {
      continue;
    }
    if (length_ >= kMaximumLineBytes) {
      discarding_ = true;
      length_ = 0U;
      continue;
    }
    if (character >= 0x20 && character <= 0x7E) {
      line_[length_++] = character;
      char echo[2]{character, '\0'};
      writeText(echo);
    }
  }
}

void Stage28ServiceConsole::processLine(std::uint64_t now_ms) noexcept {
  const ServiceConsoleCommand command = parseServiceConsoleCommand(line_.data());
  const ServiceConsoleCommandDomain domain = serviceConsoleCommandDomain(command.kind);
  switch (domain) {
  case ServiceConsoleCommandDomain::None:
    return;
  case ServiceConsoleCommandDomain::Builtin:
    if (command.kind == ServiceConsoleCommandKind::Help) {
      printHelp();
      return;
    }
    break;
  case ServiceConsoleCommandDomain::Output:
    if (output_commands_.handle(command, now_ms)) {
      return;
    }
    break;
  case ServiceConsoleCommandDomain::Storage:
    if (storage_commands_.handle(command)) {
      return;
    }
    break;
  case ServiceConsoleCommandDomain::System:
    if (system_commands_.handle(command, now_ms)) {
      return;
    }
    break;
  case ServiceConsoleCommandDomain::Invalid:
    break;
  }
  writeText("error: unknown/invalid command; type 'help'\r\n");
}

void Stage28ServiceConsole::printHelp() noexcept {
  writeText("\r\nCommands:\r\n");
  writeText("  0 | help | ?                     show this menu\r\n");
  writeText("  1 | status                       firmware/runtime/heap/RF status\r\n");
  writeText("  2 | sensors                      SCD41, TP357, Xiaomi and RTC snapshot\r\n");
  writeText("  3 | rf | rf list                 list known RF433 devices/codes\r\n");
  writeText("  automation [status]              show automation lifecycle state\r\n");
  writeText("  automation on|off                request high-level automation mode\r\n");
  writeText("  maintenance [status]             show maintenance lock state\r\n");
  writeText("  maintenance enter|exit           safe enter / explicit re-arm exit\r\n");
  writeText("  rtc set-unix <epoch>             set DS3231 from UTC Unix seconds\r\n");
  writeText("  output lamp on|off               supervised manual lamp command\r\n");
  writeText("  output fan on|off                supervised manual fan command\r\n");
  writeText("  output humidifier on|off         supervised manual humidifier command\r\n");
  writeText("  rf <device> on|off               compatibility alias for output command\r\n");
  writeText("  rf raw <device> on|off           maintenance-only raw RF diagnostic TX\r\n");
  writeText("  rf rx [50..5000]                 capture/decode one RF frame\r\n");
  writeText("  sdlog status                     SD logger status/counters\r\n");
  writeText("  sdlog list                       list GBLOG/*.JL with sizes\r\n");
  writeText("  sdlog read <file.JL> <off> <n>  read 1..384 bytes as Base64 + CRC32\r\n");
  writeText("  sdlog selftest                   durable write/read/delete SD probe\r\n");
  writeText("RTC stores UTC; lighting schedule converts UTC to Europe/Warsaw.\r\n");
  writeText("Configured manual outputs are supervisor-owned and mode/safety constrained.\r\n");
  writeText("Manual output completion is command truth, not physical load acknowledgement.\r\n");
  writeText("Raw RF TX requires MaintenanceLocked and is vetoed by conflicting hard safety.\r\n");
}

void Stage28ServiceConsole::writeText(const char* text) noexcept {
  if (!ready_ || text == nullptr) {
    return;
  }
  const std::size_t length = std::strlen(text);
  std::size_t offset = 0U;
  while (offset < length) {
    const int written = uart_write_bytes(kServiceConsoleUart, text + offset, length - offset);
    if (written <= 0) {
      break;
    }
    offset += static_cast<std::size_t>(written);
  }
}

void Stage28ServiceConsole::printPrompt() noexcept {
  writeText("growbox> ");
}

} // namespace growbox::app::climate_io::runtime
