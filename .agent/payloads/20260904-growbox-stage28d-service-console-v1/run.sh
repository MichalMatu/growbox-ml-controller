#!/usr/bin/env bash
set -euo pipefail

EXPECTED=0d6936023a216dd0122bb550e9832c0296ecbb72
BRANCH=mvp/environment-controller

git fetch -q origin "$BRANCH"
git reset --hard "$EXPECTED"
test "$(git rev-parse HEAD)" = "$EXPECTED"
test "$(git rev-parse origin/$BRANCH)" = "$EXPECTED"
test -z "$(git status --porcelain)"

cat > src/climate/runtime/Stage28ServiceConsoleCommand.h <<'EOF'
#pragma once

#include <cstdint>

namespace growbox::app::climate_io::runtime {

enum class ServiceConsoleCommandKind : std::uint8_t {
  None = 0U,
  Help,
  Status,
  Sensors,
  RfList,
  RfTransmit,
  RfReceive,
  Invalid,
};

enum class ServiceConsoleRfDevice : std::uint8_t {
  Lamp = 0U,
  Fan,
  Humidifier,
};

enum class ServiceConsoleRfState : std::uint8_t {
  Off = 0U,
  On,
};

struct ServiceConsoleCommand {
  ServiceConsoleCommandKind kind{ServiceConsoleCommandKind::None};
  ServiceConsoleRfDevice device{ServiceConsoleRfDevice::Lamp};
  ServiceConsoleRfState state{ServiceConsoleRfState::Off};
  std::uint32_t timeout_ms{1000U};
};

ServiceConsoleCommand parseServiceConsoleCommand(const char* line) noexcept;
const char* serviceConsoleRfDeviceName(ServiceConsoleRfDevice device) noexcept;
const char* serviceConsoleRfStateName(ServiceConsoleRfState state) noexcept;

} // namespace growbox::app::climate_io::runtime
EOF

cat > src/climate/runtime/Stage28ServiceConsoleCommand.cpp <<'EOF'
#include "climate/runtime/Stage28ServiceConsoleCommand.h"

#include <array>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <string_view>

namespace growbox::app::climate_io::runtime {
namespace {

constexpr std::uint32_t kDefaultRxTimeoutMs = 1000U;
constexpr std::uint32_t kMinimumRxTimeoutMs = 50U;
constexpr std::uint32_t kMaximumRxTimeoutMs = 5000U;

char lowerAscii(char value) noexcept {
  return value >= 'A' && value <= 'Z' ? static_cast<char>(value - 'A' + 'a') : value;
}

bool equalsIgnoreCase(std::string_view left, std::string_view right) noexcept {
  if (left.size() != right.size()) {
    return false;
  }
  for (std::size_t index = 0U; index < left.size(); ++index) {
    if (lowerAscii(left[index]) != lowerAscii(right[index])) {
      return false;
    }
  }
  return true;
}

bool isSpace(char value) noexcept {
  return value == ' ' || value == '\t';
}

std::size_t splitTokens(std::string_view line,
                        std::array<std::string_view, 4U>& tokens) noexcept {
  std::size_t count = 0U;
  std::size_t cursor = 0U;
  while (cursor < line.size()) {
    while (cursor < line.size() && isSpace(line[cursor])) {
      ++cursor;
    }
    if (cursor >= line.size()) {
      break;
    }
    const std::size_t start = cursor;
    while (cursor < line.size() && !isSpace(line[cursor])) {
      ++cursor;
    }
    if (count >= tokens.size()) {
      return tokens.size() + 1U;
    }
    tokens[count++] = line.substr(start, cursor - start);
  }
  return count;
}

bool parseUnsigned(std::string_view token, std::uint32_t& output) noexcept {
  if (token.empty()) {
    return false;
  }
  std::uint64_t value = 0U;
  for (const char character : token) {
    if (character < '0' || character > '9') {
      return false;
    }
    value = value * 10U + static_cast<std::uint64_t>(character - '0');
    if (value > std::numeric_limits<std::uint32_t>::max()) {
      return false;
    }
  }
  output = static_cast<std::uint32_t>(value);
  return true;
}

bool parseDevice(std::string_view token, ServiceConsoleRfDevice& device) noexcept {
  if (equalsIgnoreCase(token, "lamp")) {
    device = ServiceConsoleRfDevice::Lamp;
    return true;
  }
  if (equalsIgnoreCase(token, "fan")) {
    device = ServiceConsoleRfDevice::Fan;
    return true;
  }
  if (equalsIgnoreCase(token, "humidifier")) {
    device = ServiceConsoleRfDevice::Humidifier;
    return true;
  }
  return false;
}

bool parseState(std::string_view token, ServiceConsoleRfState& state) noexcept {
  if (equalsIgnoreCase(token, "on")) {
    state = ServiceConsoleRfState::On;
    return true;
  }
  if (equalsIgnoreCase(token, "off")) {
    state = ServiceConsoleRfState::Off;
    return true;
  }
  return false;
}

ServiceConsoleCommand invalidCommand() noexcept {
  ServiceConsoleCommand command{};
  command.kind = ServiceConsoleCommandKind::Invalid;
  return command;
}

} // namespace

ServiceConsoleCommand parseServiceConsoleCommand(const char* line) noexcept {
  if (line == nullptr) {
    return invalidCommand();
  }

  const std::string_view input(line);
  std::array<std::string_view, 4U> tokens{};
  const std::size_t count = splitTokens(input, tokens);
  if (count == 0U) {
    return {};
  }
  if (count > tokens.size()) {
    return invalidCommand();
  }

  ServiceConsoleCommand command{};
  if (count == 1U) {
    if (equalsIgnoreCase(tokens[0], "help") || equalsIgnoreCase(tokens[0], "menu") ||
        tokens[0] == "?" || tokens[0] == "0") {
      command.kind = ServiceConsoleCommandKind::Help;
      return command;
    }
    if (equalsIgnoreCase(tokens[0], "status") || tokens[0] == "1") {
      command.kind = ServiceConsoleCommandKind::Status;
      return command;
    }
    if (equalsIgnoreCase(tokens[0], "sensors") || tokens[0] == "2") {
      command.kind = ServiceConsoleCommandKind::Sensors;
      return command;
    }
    if (equalsIgnoreCase(tokens[0], "rf") || tokens[0] == "3") {
      command.kind = ServiceConsoleCommandKind::RfList;
      return command;
    }
    return invalidCommand();
  }

  if (!equalsIgnoreCase(tokens[0], "rf")) {
    return invalidCommand();
  }

  if (count == 2U && equalsIgnoreCase(tokens[1], "list")) {
    command.kind = ServiceConsoleCommandKind::RfList;
    return command;
  }

  if (equalsIgnoreCase(tokens[1], "rx")) {
    if (count == 2U) {
      command.kind = ServiceConsoleCommandKind::RfReceive;
      command.timeout_ms = kDefaultRxTimeoutMs;
      return command;
    }
    if (count == 3U) {
      std::uint32_t timeout_ms = 0U;
      if (!parseUnsigned(tokens[2], timeout_ms) || timeout_ms < kMinimumRxTimeoutMs ||
          timeout_ms > kMaximumRxTimeoutMs) {
        return invalidCommand();
      }
      command.kind = ServiceConsoleCommandKind::RfReceive;
      command.timeout_ms = timeout_ms;
      return command;
    }
    return invalidCommand();
  }

  if (count == 3U && parseDevice(tokens[1], command.device) &&
      parseState(tokens[2], command.state)) {
    command.kind = ServiceConsoleCommandKind::RfTransmit;
    return command;
  }

  return invalidCommand();
}

const char* serviceConsoleRfDeviceName(ServiceConsoleRfDevice device) noexcept {
  switch (device) {
  case ServiceConsoleRfDevice::Lamp:
    return "lamp";
  case ServiceConsoleRfDevice::Fan:
    return "fan";
  case ServiceConsoleRfDevice::Humidifier:
    return "humidifier";
  }
  return "unknown";
}

const char* serviceConsoleRfStateName(ServiceConsoleRfState state) noexcept {
  return state == ServiceConsoleRfState::On ? "on" : "off";
}

} // namespace growbox::app::climate_io::runtime
EOF

cat > src/climate/runtime/Stage28ServiceConsole.h <<'EOF'
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
EOF

cat > src/climate/runtime/Stage28ServiceConsole.cpp <<'EOF'
#include "climate/runtime/Stage28ServiceConsole.h"

#include "climate/rf433/Rf433HardwareConfig.h"

#include <driver/usb_serial_jtag.h>
#include <esp_heap_caps.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>

#include <array>
#include <cstdarg>
#include <cstdio>
#include <cstring>

namespace growbox::app::climate_io::runtime {
namespace {

struct KnownRfDevice {
  ServiceConsoleRfDevice id;
  const char* physical_name;
  const rf433::RemoteSocketHardwareConfig* hardware;
  const char* tx_status;
};

constexpr std::array<KnownRfDevice, 3U> kKnownRfDevices{{
    {ServiceConsoleRfDevice::Lamp, "lamp", &rf433::kRemoteSocket2,
     "captured-profile; physical socket validation pending"},
    {ServiceConsoleRfDevice::Fan, "fan", &rf433::kRemoteSocket1,
     "physically validated at 575us/repeat10"},
    {ServiceConsoleRfDevice::Humidifier, "humidifier", &rf433::kRemoteSocket3,
     "captured-profile; physical socket validation pending"},
}};

const KnownRfDevice* findKnownDevice(ServiceConsoleRfDevice id) noexcept {
  for (const KnownRfDevice& device : kKnownRfDevices) {
    if (device.id == id) {
      return &device;
    }
  }
  return nullptr;
}

void printMeasuredValue(Stage28ServiceConsole& console, const char* name,
                        const ::growbox::climate::MeasuredValue& value) noexcept;

} // namespace

Stage28ServiceConsole::Stage28ServiceConsole(Config config, native::BleClimateScanner& ble,
                                             native::Scd41InsideSource& scd41,
                                             native::Ds3231ClockSource& clock,
                                             Stage28RfDiagnostics& rf_diagnostics) noexcept
    : config_(config), ble_(ble), scd41_(scd41), clock_(clock),
      rf_diagnostics_(rf_diagnostics) {}

bool Stage28ServiceConsole::begin() noexcept {
  if (!config_.enabled) {
    return false;
  }

  if (!usb_serial_jtag_is_driver_installed()) {
    usb_serial_jtag_driver_config_t driver_config = USB_SERIAL_JTAG_DRIVER_CONFIG_DEFAULT();
    driver_config.tx_buffer_size = 4096U;
    driver_config.rx_buffer_size = 4096U;
    if (usb_serial_jtag_driver_install(&driver_config) != ESP_OK) {
      return false;
    }
  }

  std::uint8_t discard[128]{};
  while (usb_serial_jtag_read_bytes(discard, sizeof(discard), 0U) > 0) {
  }

  ready_ = true;
  writeText("\r\n=== Growbox service console ===\r\n");
  writeText("Manual service commands only. Automatic climate outputs remain fake-locked.\r\n");
  printHelp();
  printPrompt();
  return true;
}

void Stage28ServiceConsole::poll(std::uint64_t now_ms) noexcept {
  if (!ready_) {
    return;
  }

  std::uint8_t buffer[96]{};
  const int received = usb_serial_jtag_read_bytes(buffer, sizeof(buffer), 0U);
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
  switch (command.kind) {
  case ServiceConsoleCommandKind::None:
    return;
  case ServiceConsoleCommandKind::Help:
    printHelp();
    return;
  case ServiceConsoleCommandKind::Status:
    printStatus(now_ms);
    return;
  case ServiceConsoleCommandKind::Sensors:
    printSensors(now_ms);
    return;
  case ServiceConsoleCommandKind::RfList:
    printRfList();
    return;
  case ServiceConsoleCommandKind::RfTransmit:
    handleRfTransmit(command);
    return;
  case ServiceConsoleCommandKind::RfReceive:
    handleRfReceive(command);
    return;
  case ServiceConsoleCommandKind::Invalid:
    writeText("error: unknown/invalid command; type 'help'\r\n");
    return;
  }
}

void Stage28ServiceConsole::printHelp() noexcept {
  writeText("\r\nCommands:\r\n");
  writeText("  0 | help | ?                     show this menu\r\n");
  writeText("  1 | status                       firmware/runtime/heap/RF status\r\n");
  writeText("  2 | sensors                      SCD41, TP357, Xiaomi and RTC snapshot\r\n");
  writeText("  3 | rf | rf list                 list known RF433 devices/codes\r\n");
  writeText("  rf lamp on|off                   manual lamp socket transmit\r\n");
  writeText("  rf fan on|off                    manual fan socket transmit\r\n");
  writeText("  rf humidifier on|off             manual humidifier socket transmit\r\n");
  writeText("  rf rx [50..5000]                 capture/decode one RF frame\r\n");
  writeText("RF transmit commands require the RF diagnostics transport to be enabled.\r\n");
  writeText("Manual TX is not physical load-state acknowledgement.\r\n");
}

void Stage28ServiceConsole::printStatus(std::uint64_t now_ms) noexcept {
  const std::uint32_t free_internal =
      static_cast<std::uint32_t>(heap_caps_get_free_size(MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT));
  const std::uint32_t free_psram =
      static_cast<std::uint32_t>(heap_caps_get_free_size(MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT));
  const UBaseType_t stack_watermark = uxTaskGetStackHighWaterMark(nullptr);
  writeFormatted("status firmware_sha=%s uptime_ms=%llu outputs=fake-locked rf_ready=%d "
                 "free_internal=%lu free_psram=%lu stack_high_water=%lu\r\n",
                 config_.firmware_sha != nullptr ? config_.firmware_sha : "unknown",
                 static_cast<unsigned long long>(now_ms), rf_diagnostics_.ready(),
                 static_cast<unsigned long>(free_internal), static_cast<unsigned long>(free_psram),
                 static_cast<unsigned long>(stack_watermark));
}

void Stage28ServiceConsole::printSensors(std::uint64_t now_ms) noexcept {
  InsideEnvironmentSnapshot scd{};
  const bool scd_sampled = scd41_.sample(now_ms, scd);
  native::BleClimateReading tp357{};
  const bool tp357_sampled = ble_.sampleTp357(now_ms, tp357);
  native::BleClimateReading xiaomi{};
  const bool xiaomi_sampled = ble_.sampleXiaomi(now_ms, xiaomi);
  ClimateWallClockSnapshot rtc{};
  const bool rtc_sampled = clock_.sample(now_ms, rtc);

  writeText("sensors:\r\n");
  if (scd_sampled) {
    writeFormatted("  scd41 temp_c=%.2f rh_pct=%.2f co2_ppm=%.0f age_ms=%llu available=%d "
                   "reads=%lu errors=%lu invalid=%lu\r\n",
                   static_cast<double>(scd.air_temperature_c.value),
                   static_cast<double>(scd.relative_humidity_pct.value),
                   static_cast<double>(scd.co2_ppm.value),
                   static_cast<unsigned long long>(scd.air_temperature_c.age_ms), scd41_.available(),
                   static_cast<unsigned long>(scd41_.successfulMeasurementCount()),
                   static_cast<unsigned long>(scd41_.readErrorCount()),
                   static_cast<unsigned long>(scd41_.invalidMeasurementCount()));
  } else {
    writeFormatted("  scd41 valid=0 available=%d reads=%lu errors=%lu invalid=%lu\r\n",
                   scd41_.available(),
                   static_cast<unsigned long>(scd41_.successfulMeasurementCount()),
                   static_cast<unsigned long>(scd41_.readErrorCount()),
                   static_cast<unsigned long>(scd41_.invalidMeasurementCount()));
  }

  if (tp357_sampled) {
    writeFormatted("  tp357 temp_c=%.2f rh_pct=%.2f age_ms=%llu battery_pct=%u battery_valid=%d "
                   "packets=%lu accepted=%lu rejected=%lu\r\n",
                   static_cast<double>(tp357.temperature_c),
                   static_cast<double>(tp357.relative_humidity_pct),
                   static_cast<unsigned long long>(tp357.age_ms), tp357.battery_pct,
                   tp357.has_battery, static_cast<unsigned long>(ble_.tp357PacketCount()),
                   static_cast<unsigned long>(ble_.tp357AcceptedCount()),
                   static_cast<unsigned long>(ble_.tp357RejectedCount()));
  } else {
    writeFormatted("  tp357 valid=0 packets=%lu accepted=%lu rejected=%lu\r\n",
                   static_cast<unsigned long>(ble_.tp357PacketCount()),
                   static_cast<unsigned long>(ble_.tp357AcceptedCount()),
                   static_cast<unsigned long>(ble_.tp357RejectedCount()));
  }

  if (xiaomi_sampled) {
    writeFormatted("  xiaomi temp_c=%.2f rh_pct=%.2f age_ms=%llu battery_pct=%u battery_valid=%d "
                   "packets=%lu accepted=%lu rejected=%lu\r\n",
                   static_cast<double>(xiaomi.temperature_c),
                   static_cast<double>(xiaomi.relative_humidity_pct),
                   static_cast<unsigned long long>(xiaomi.age_ms), xiaomi.battery_pct,
                   xiaomi.has_battery, static_cast<unsigned long>(ble_.xiaomiPacketCount()),
                   static_cast<unsigned long>(ble_.xiaomiAcceptedCount()),
                   static_cast<unsigned long>(ble_.xiaomiRejectedCount()));
  } else {
    writeFormatted("  xiaomi valid=0 packets=%lu accepted=%lu rejected=%lu\r\n",
                   static_cast<unsigned long>(ble_.xiaomiPacketCount()),
                   static_cast<unsigned long>(ble_.xiaomiAcceptedCount()),
                   static_cast<unsigned long>(ble_.xiaomiRejectedCount()));
  }

  writeFormatted("  rtc sampled=%d available=%d trusted=%d unix_time_s=%llu reads=%lu errors=%lu "
                 "untrusted=%lu\r\n",
                 rtc_sampled, clock_.available(), rtc.valid && clock_.trusted(),
                 static_cast<unsigned long long>(rtc.unix_time_s),
                 static_cast<unsigned long>(clock_.successfulReadCount()),
                 static_cast<unsigned long>(clock_.readErrorCount()),
                 static_cast<unsigned long>(clock_.untrustedReadCount()));
}

void Stage28ServiceConsole::printRfList() noexcept {
  writeFormatted("rf transport_ready=%d automatic_outputs=fake-locked\r\n",
                 rf_diagnostics_.ready());
  for (const KnownRfDevice& device : kKnownRfDevices) {
    writeFormatted("  %s label=%s on=%lu/0x%08lX off=%lu/0x%08lX bits=%u protocol=%u "
                   "pulse_us=%u repeat=%u status=%s\r\n",
                   device.physical_name, device.hardware->label,
                   static_cast<unsigned long>(device.hardware->on.key.code),
                   static_cast<unsigned long>(device.hardware->on.key.code),
                   static_cast<unsigned long>(device.hardware->off.key.code),
                   static_cast<unsigned long>(device.hardware->off.key.code),
                   device.hardware->on.key.bit_length, device.hardware->on.key.protocol,
                   device.hardware->on.pulse_us, device.hardware->on.repeat, device.tx_status);
  }
}

void Stage28ServiceConsole::handleRfTransmit(const ServiceConsoleCommand& command) noexcept {
  const KnownRfDevice* device = findKnownDevice(command.device);
  if (device == nullptr) {
    writeText("error: RF device not found\r\n");
    return;
  }
  if (!rf_diagnostics_.ready()) {
    writeText("error: RF transport is not ready; enable GROWBOX_RF433_LOOPBACK_ENABLED\r\n");
    return;
  }

  const rf433::FrameConfig& frame =
      command.state == ServiceConsoleRfState::On ? device->hardware->on : device->hardware->off;
  rf433::LoopbackEvidence evidence{};
  const bool tx_completed = rf_diagnostics_.manualTransmit(frame, evidence);
  writeFormatted("manual_rf_tx device=%s state=%s code=%lu bits=%u protocol=%u pulse_us=%u "
                 "repeat=%u tx_queued=%d tx_started=%d tx_completed=%d self_rx_captured=%d "
                 "self_rx_decode_status=%u self_rx_classification=%u physical_state=unconfirmed\r\n",
                 serviceConsoleRfDeviceName(command.device),
                 serviceConsoleRfStateName(command.state), static_cast<unsigned long>(frame.key.code),
                 frame.key.bit_length, frame.key.protocol, frame.pulse_us, frame.repeat,
                 evidence.tx_queued, evidence.tx_started, tx_completed && evidence.tx_completed,
                 evidence.rx_captured, static_cast<unsigned>(evidence.decoded.status),
                 static_cast<unsigned>(evidence.classification));
}

void Stage28ServiceConsole::handleRfReceive(const ServiceConsoleCommand& command) noexcept {
  if (!rf_diagnostics_.ready()) {
    writeText("error: RF transport is not ready; enable GROWBOX_RF433_LOOPBACK_ENABLED\r\n");
    return;
  }
  rf433::ReceiveEvidence evidence{};
  const bool captured = rf_diagnostics_.manualReceive(command.timeout_ms, evidence);
  if (!captured) {
    writeFormatted("rf_rx captured=0 timeout_ms=%lu\r\n",
                   static_cast<unsigned long>(command.timeout_ms));
    return;
  }
  writeFormatted("rf_rx captured=%d timeout_ms=%lu symbols=%u overflow=%d decode_status=%u "
                 "code=%lu bits=%u protocol=%u estimated_pulse_us=%u observed_repeats=%u\r\n",
                 evidence.rx_captured, static_cast<unsigned long>(command.timeout_ms),
                 static_cast<unsigned>(evidence.symbol_count), evidence.overflow,
                 static_cast<unsigned>(evidence.decoded.status),
                 static_cast<unsigned long>(evidence.decoded.frame.code),
                 evidence.decoded.frame.bit_length, evidence.decoded.frame.protocol,
                 evidence.decoded.estimated_pulse_us, evidence.decoded.observed_repeats);
}

void Stage28ServiceConsole::writeText(const char* text) noexcept {
  if (!ready_ || text == nullptr) {
    return;
  }
  static_cast<void>(usb_serial_jtag_write_bytes(text, std::strlen(text), pdMS_TO_TICKS(50)));
}

void Stage28ServiceConsole::writeFormatted(const char* format, ...) noexcept {
  if (!ready_ || format == nullptr) {
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

void Stage28ServiceConsole::printPrompt() noexcept {
  writeText("growbox> ");
}

} // namespace growbox::app::climate_io::runtime
EOF

mkdir -p test/test_stage28_service_console
cat > test/test_stage28_service_console/test_main.cpp <<'EOF'
#include "climate/runtime/Stage28ServiceConsoleCommand.h"

#include <cassert>

using namespace growbox::app::climate_io::runtime;

namespace {

void testReadOnlyMenuCommands() {
  assert(parseServiceConsoleCommand("help").kind == ServiceConsoleCommandKind::Help);
  assert(parseServiceConsoleCommand("?").kind == ServiceConsoleCommandKind::Help);
  assert(parseServiceConsoleCommand("0").kind == ServiceConsoleCommandKind::Help);
  assert(parseServiceConsoleCommand("status").kind == ServiceConsoleCommandKind::Status);
  assert(parseServiceConsoleCommand("1").kind == ServiceConsoleCommandKind::Status);
  assert(parseServiceConsoleCommand("sensors").kind == ServiceConsoleCommandKind::Sensors);
  assert(parseServiceConsoleCommand("2").kind == ServiceConsoleCommandKind::Sensors);
  assert(parseServiceConsoleCommand("rf").kind == ServiceConsoleCommandKind::RfList);
  assert(parseServiceConsoleCommand("rf list").kind == ServiceConsoleCommandKind::RfList);
  assert(parseServiceConsoleCommand("3").kind == ServiceConsoleCommandKind::RfList);
}

void testNamedRfTransmitCommands() {
  const auto lamp = parseServiceConsoleCommand("rf lamp on");
  assert(lamp.kind == ServiceConsoleCommandKind::RfTransmit);
  assert(lamp.device == ServiceConsoleRfDevice::Lamp);
  assert(lamp.state == ServiceConsoleRfState::On);

  const auto fan = parseServiceConsoleCommand("RF FAN OFF");
  assert(fan.kind == ServiceConsoleCommandKind::RfTransmit);
  assert(fan.device == ServiceConsoleRfDevice::Fan);
  assert(fan.state == ServiceConsoleRfState::Off);

  const auto humidifier = parseServiceConsoleCommand("  rf   humidifier   on  ");
  assert(humidifier.kind == ServiceConsoleCommandKind::RfTransmit);
  assert(humidifier.device == ServiceConsoleRfDevice::Humidifier);
  assert(humidifier.state == ServiceConsoleRfState::On);
}

void testRfReceiveTimeoutBounds() {
  const auto default_rx = parseServiceConsoleCommand("rf rx");
  assert(default_rx.kind == ServiceConsoleCommandKind::RfReceive);
  assert(default_rx.timeout_ms == 1000U);

  const auto bounded_rx = parseServiceConsoleCommand("rf rx 2500");
  assert(bounded_rx.kind == ServiceConsoleCommandKind::RfReceive);
  assert(bounded_rx.timeout_ms == 2500U);

  assert(parseServiceConsoleCommand("rf rx 49").kind == ServiceConsoleCommandKind::Invalid);
  assert(parseServiceConsoleCommand("rf rx 5001").kind == ServiceConsoleCommandKind::Invalid);
  assert(parseServiceConsoleCommand("rf rx nope").kind == ServiceConsoleCommandKind::Invalid);
}

void testInvalidCommandsFailClosed() {
  assert(parseServiceConsoleCommand(nullptr).kind == ServiceConsoleCommandKind::Invalid);
  assert(parseServiceConsoleCommand("").kind == ServiceConsoleCommandKind::None);
  assert(parseServiceConsoleCommand("rf lamp maybe").kind == ServiceConsoleCommandKind::Invalid);
  assert(parseServiceConsoleCommand("rf unknown on").kind == ServiceConsoleCommandKind::Invalid);
  assert(parseServiceConsoleCommand("fan on").kind == ServiceConsoleCommandKind::Invalid);
  assert(parseServiceConsoleCommand("rf lamp on extra").kind == ServiceConsoleCommandKind::Invalid);
}

} // namespace

int main() {
  testReadOnlyMenuCommands();
  testNamedRfTransmitCommands();
  testRfReceiveTimeoutBounds();
  testInvalidCommandsFailClosed();
  return 0;
}
EOF

python3 - <<'PY'
from pathlib import Path

# Freeze captured lamp and humidifier profiles in the neutral RF hardware layer.
p = Path("src/climate/rf433/Rf433HardwareConfig.h")
s = p.read_text()
anchor = '''inline constexpr RemoteSocketHardwareConfig kRemoteSocket1{\n    kRemoteSocket1Label,\n    kRemoteSocket1On,\n    kRemoteSocket1Off,\n};\n\n} // namespace growbox::app::climate_io::rf433\n'''
insert = '''inline constexpr RemoteSocketHardwareConfig kRemoteSocket1{\n    kRemoteSocket1Label,\n    kRemoteSocket1On,\n    kRemoteSocket1Off,\n};\n\n// Stage28D service-console captured profiles. These identities are neutral hardware\n// records and do not assign semantic actuator roles. Their 560 us transmit profile\n// still requires physical ESP-to-socket validation.\ninline constexpr char kRemoteSocket2Label[] = "remote_socket_2";\ninline constexpr FrameConfig kRemoteSocket2On{{235030016U, 32U, 2U}, 10U, 560U};\ninline constexpr FrameConfig kRemoteSocket2Off{{16926208U, 32U, 2U}, 10U, 560U};\ninline constexpr RemoteSocketHardwareConfig kRemoteSocket2{\n    kRemoteSocket2Label,\n    kRemoteSocket2On,\n    kRemoteSocket2Off,\n};\n\ninline constexpr char kRemoteSocket3Label[] = "remote_socket_3";\ninline constexpr FrameConfig kRemoteSocket3On{{637683200U, 32U, 2U}, 10U, 560U};\ninline constexpr FrameConfig kRemoteSocket3Off{{771900928U, 32U, 2U}, 10U, 560U};\ninline constexpr RemoteSocketHardwareConfig kRemoteSocket3{\n    kRemoteSocket3Label,\n    kRemoteSocket3On,\n    kRemoteSocket3Off,\n};\n\n} // namespace growbox::app::climate_io::rf433\n'''
if anchor not in s:
    raise SystemExit("Rf433HardwareConfig anchor missing")
p.write_text(s.replace(anchor, insert, 1))

# Expose bounded manual RF operations from the already-owned diagnostics transport.
p = Path("src/climate/runtime/Stage28RfDiagnostics.h")
s = p.read_text()
old = '''  bool begin() noexcept;\n  void tick(std::uint64_t now_ms) noexcept;\n\n  bool ready() const noexcept {\n'''
new = '''  bool begin() noexcept;\n  void tick(std::uint64_t now_ms) noexcept;\n  bool manualTransmit(const rf433::FrameConfig& frame, rf433::LoopbackEvidence& evidence) noexcept;\n  bool manualReceive(std::uint32_t timeout_ms, rf433::ReceiveEvidence& evidence) noexcept;\n\n  bool ready() const noexcept {\n'''
if old not in s:
    raise SystemExit("Stage28RfDiagnostics.h anchor missing")
p.write_text(s.replace(old, new, 1))

p = Path("src/climate/runtime/Stage28RfDiagnostics.cpp")
s = p.read_text()
anchor = '''void Stage28RfDiagnostics::capturePassive() noexcept {\n'''
methods = '''bool Stage28RfDiagnostics::manualTransmit(const rf433::FrameConfig& frame,\n                                               rf433::LoopbackEvidence& evidence) noexcept {\n  evidence = {};\n  if (!ready_) {\n    return false;\n  }\n  static_cast<void>(loopback_.transmitAndReceive(frame, config_.smoke_timeout_ms, evidence));\n  return evidence.tx_completed;\n}\n\nbool Stage28RfDiagnostics::manualReceive(std::uint32_t timeout_ms,\n                                          rf433::ReceiveEvidence& evidence) noexcept {\n  evidence = {};\n  return ready_ && timeout_ms > 0U && loopback_.receiveOnce(timeout_ms, evidence);\n}\n\n'''
if anchor not in s:
    raise SystemExit("Stage28RfDiagnostics.cpp anchor missing")
p.write_text(s.replace(anchor, methods + anchor, 1))

# Wire the service console into the real-input runtime.
p = Path("src/climate/ClimateV6RealInputRuntime.cpp")
s = p.read_text()
s = s.replace(
    '#include "climate/runtime/Stage28RfDiagnostics.h"\n',
    '#include "climate/runtime/Stage28RfDiagnostics.h"\n#include "climate/runtime/Stage28ServiceConsole.h"\n',
    1,
)
macro_anchor = '''#ifndef GROWBOX_RF433_RX_GPIO\n#define GROWBOX_RF433_RX_GPIO 14\n#endif\n'''
macro_new = macro_anchor + '''#ifndef GROWBOX_STAGE28_SERVICE_CONSOLE_ENABLED\n#define GROWBOX_STAGE28_SERVICE_CONSOLE_ENABLED 1\n#endif\n'''
if macro_anchor not in s:
    raise SystemExit("ClimateV6RealInputRuntime macro anchor missing")
s = s.replace(macro_anchor, macro_new, 1)
old = '''  runtime::Stage28RfDiagnostics rf_diagnostics(rfDiagnosticsConfig());\n  const bool rf_ready = rf_diagnostics.begin();\n\n  runtime::Stage27InsideSource inside(ble, scd41);\n'''
new = '''  runtime::Stage28RfDiagnostics rf_diagnostics(rfDiagnosticsConfig());\n  const bool rf_ready = rf_diagnostics.begin();\n  runtime::Stage28ServiceConsole service_console(\n      {GROWBOX_STAGE28_SERVICE_CONSOLE_ENABLED != 0, GROWBOX_FIRMWARE_GIT_SHA}, ble, scd41, clock,\n      rf_diagnostics);\n  const bool service_console_ready = service_console.begin();\n\n  runtime::Stage27InsideSource inside(ble, scd41);\n'''
if old not in s:
    raise SystemExit("ClimateV6RealInputRuntime RF construction anchor missing")
s = s.replace(old, new, 1)
old = '''           "flash_fallback=%d storage_logger=%d rf433_loopback=%d rf433_tx_gpio=%d "\n           "rf433_rx_gpio=%d outputs=fake-locked",\n           i2c_ready, scd41_ready, rtc_ready, ble_ready, storage_config.sd_enabled,\n           storage_config.flash_fallback_enabled, storage_logger_ready, rf_ready,\n           GROWBOX_RF433_TX_GPIO, GROWBOX_RF433_RX_GPIO);\n'''
new = '''           "flash_fallback=%d storage_logger=%d rf433_loopback=%d rf433_tx_gpio=%d "\n           "rf433_rx_gpio=%d service_console=%d outputs=fake-locked",\n           i2c_ready, scd41_ready, rtc_ready, ble_ready, storage_config.sd_enabled,\n           storage_config.flash_fallback_enabled, storage_logger_ready, rf_ready,\n           GROWBOX_RF433_TX_GPIO, GROWBOX_RF433_RX_GPIO, service_console_ready);\n'''
if old not in s:
    raise SystemExit("ClimateV6RealInputRuntime log anchor missing")
s = s.replace(old, new, 1)
old = '''    const std::uint64_t now_ms = monotonicMilliseconds();\n    rf_diagnostics.tick(now_ms);\n\n    ::growbox::climate::ClimateRuntimeDecision decision{};\n'''
new = '''    const std::uint64_t now_ms = monotonicMilliseconds();\n    service_console.poll(now_ms);\n    rf_diagnostics.tick(now_ms);\n\n    ::growbox::climate::ClimateRuntimeDecision decision{};\n'''
if old not in s:
    raise SystemExit("ClimateV6RealInputRuntime loop anchor missing")
p.write_text(s.replace(old, new, 1))

# Build metadata: firmware console sources and host parser test.
p = Path("src/CMakeLists.txt")
s = p.read_text()
old = '''      "climate/runtime/Stage28RfDiagnostics.cpp"\n      "climate/telemetry/Stage27LogFormat.cpp"\n'''
new = '''      "climate/runtime/Stage28RfDiagnostics.cpp"\n      "climate/runtime/Stage28ServiceConsole.cpp"\n      "climate/runtime/Stage28ServiceConsoleCommand.cpp"\n      "climate/telemetry/Stage27LogFormat.cpp"\n'''
if old not in s:
    raise SystemExit("src CMake runtime source anchor missing")
s = s.replace(old, new, 1)
cache_anchor = 'set(GROWBOX_RF433_RX_GPIO "14" CACHE STRING "Stage28 RF433 RX GPIO")\n'
cache_new = cache_anchor + 'set(GROWBOX_STAGE28_SERVICE_CONSOLE_ENABLED "1" CACHE STRING "Enable Stage28 USB service console")\n'
if cache_anchor not in s:
    raise SystemExit("src CMake cache anchor missing")
s = s.replace(cache_anchor, cache_new, 1)
def_anchor = '    GROWBOX_RF433_RX_GPIO=${GROWBOX_RF433_RX_GPIO}\n'
def_new = def_anchor + '    GROWBOX_STAGE28_SERVICE_CONSOLE_ENABLED=${GROWBOX_STAGE28_SERVICE_CONSOLE_ENABLED}\n'
if def_anchor not in s:
    raise SystemExit("src CMake definition anchor missing")
s = s.replace(def_anchor, def_new, 1)
p.write_text(s)

p = Path("test/host/CMakeLists.txt")
s = p.read_text()
anchor = '''add_executable(\n  rf433_protocol_tests\n'''
block = '''add_executable(\n  stage28_service_console_tests\n  "${PROJECT_ROOT}/test/test_stage28_service_console/test_main.cpp"\n  "${PROJECT_ROOT}/src/climate/runtime/Stage28ServiceConsoleCommand.cpp"\n)\ntarget_include_directories(stage28_service_console_tests PRIVATE "${PROJECT_ROOT}/src")\ntarget_compile_features(stage28_service_console_tests PRIVATE cxx_std_17)\ntarget_compile_options(stage28_service_console_tests PRIVATE -Wall -Wextra -Wpedantic)\n\n\n'''
if anchor not in s:
    raise SystemExit("host CMake RF target anchor missing")
s = s.replace(anchor, block + anchor, 1)
test_anchor = 'add_test(NAME rf433_protocol_tests COMMAND rf433_protocol_tests)\n'
if test_anchor not in s:
    raise SystemExit("host CMake add_test anchor missing")
s = s.replace(test_anchor, 'add_test(NAME stage28_service_console_tests COMMAND stage28_service_console_tests)\n' + test_anchor, 1)
p.write_text(s)

# Extend RF host tests without changing the frozen Stage28C fan profile.
p = Path("test/test_rf433_protocol/test_main.cpp")
s = p.read_text()
anchor = '''void testHardwareQualifiedRmtReceiveContract() {\n'''
block = '''void testCapturedServiceConsoleHardwareProfiles() {\n  static_assert(kRemoteSocket2On.key.code == 235030016U);\n  static_assert(kRemoteSocket2Off.key.code == 16926208U);\n  static_assert(kRemoteSocket3On.key.code == 637683200U);\n  static_assert(kRemoteSocket3Off.key.code == 771900928U);\n  static_assert(kRemoteSocket2On.key.bit_length == 32U);\n  static_assert(kRemoteSocket3On.key.bit_length == 32U);\n  static_assert(kRemoteSocket2On.key.protocol == 2U);\n  static_assert(kRemoteSocket3On.key.protocol == 2U);\n  static_assert(kRemoteSocket2On.pulse_us == 560U);\n  static_assert(kRemoteSocket2Off.pulse_us == 560U);\n  static_assert(kRemoteSocket3On.pulse_us == 560U);\n  static_assert(kRemoteSocket3Off.pulse_us == 560U);\n  static_assert(kRemoteSocket2On.repeat == 10U);\n  static_assert(kRemoteSocket3On.repeat == 10U);\n\n  assert(std::string_view(kRemoteSocket2.label) == "remote_socket_2");\n  assert(std::string_view(kRemoteSocket3.label) == "remote_socket_3");\n  assert(validateFrameConfig(kRemoteSocket2.on) == CodecStatus::Ok);\n  assert(validateFrameConfig(kRemoteSocket2.off) == CodecStatus::Ok);\n  assert(validateFrameConfig(kRemoteSocket3.on) == CodecStatus::Ok);\n  assert(validateFrameConfig(kRemoteSocket3.off) == CodecStatus::Ok);\n}\n\n'''
if anchor not in s:
    raise SystemExit("RF test insertion anchor missing")
s = s.replace(anchor, block + anchor, 1)
main_anchor = '  testFrozenRemoteSocketHardwareConfig();\n'
if main_anchor not in s:
    raise SystemExit("RF test main anchor missing")
s = s.replace(main_anchor, main_anchor + '  testCapturedServiceConsoleHardwareProfiles();\n', 1)
p.write_text(s)

# Keep the CrowPanel helper able to explicitly enable/disable the console.
p = Path("scripts/stage27c_crowpanel.sh")
s = p.read_text()
var_anchor = 'RF433_RX_GPIO="${GROWBOX_RF433_RX_GPIO:-14}"\n'
var_new = var_anchor + 'SERVICE_CONSOLE_ENABLED="${GROWBOX_STAGE28_SERVICE_CONSOLE_ENABLED:-1}"\n'
if var_anchor not in s:
    raise SystemExit("stage27c helper variable anchor missing")
s = s.replace(var_anchor, var_new, 1)
arg_anchor = '  -D "GROWBOX_RF433_RX_GPIO=$RF433_RX_GPIO"\n'
arg_new = arg_anchor + '  -D "GROWBOX_STAGE28_SERVICE_CONSOLE_ENABLED=$SERVICE_CONSOLE_ENABLED"\n'
if arg_anchor not in s:
    raise SystemExit("stage27c helper argument anchor missing")
p.write_text(s.replace(arg_anchor, arg_new, 1))

# Documentation and bootstrap synchronization.
p = Path("README.md")
s = p.read_text()
s = s.replace(
    '> **Current controller status:** Stage28C has frozen one neutral RF433 remote/socket pair and the pre-Stage28D golden gate is complete. Stage28D is not started. Rule is authoritative, ML is shadow/research-only, and physical outputs remain fake/locked for unattended work. See [docs/CURRENT_STATUS.md](docs/CURRENT_STATUS.md), [docs/PRESTAGE28D_GOLDEN_CHECKPOINT.md](docs/PRESTAGE28D_GOLDEN_CHECKPOINT.md) and [docs/STAGE28C_FINAL_EVIDENCE.md](docs/STAGE28C_FINAL_EVIDENCE.md).',
    '> **Current controller status:** Stage28C and the pre-Stage28D golden gate are complete; Stage28D is in progress. A bounded USB service console now provides read-only diagnostics plus explicitly manual RF433 service commands while the climate runtime remains fake-locked for unattended outputs. See [docs/CURRENT_STATUS.md](docs/CURRENT_STATUS.md), [docs/RF433_DEVICE_CODES.md](docs/RF433_DEVICE_CODES.md) and [docs/PRESTAGE28D_GOLDEN_CHECKPOINT.md](docs/PRESTAGE28D_GOLDEN_CHECKPOINT.md).',
    1,
)
p.write_text(s)

p = Path("docs/RF433_DEVICE_CODES.md")
s = p.read_text()
marker = '''## Data to record for every learned device\n'''
section = '''## Serial service commands\n\nThe real-input firmware includes a bounded USB service console. The captured lamp and humidifier profiles are now also frozen in `Rf433HardwareConfig.h` for manual diagnostics, but their physical socket validation is still pending. The fan keeps the already-qualified `575 us / repeat 10` transmit profile.\n\nUseful commands:\n\n```text\nhelp\nstatus\nsensors\nrf list\nrf lamp on\nrf lamp off\nrf fan on\nrf fan off\nrf humidifier on\nrf humidifier off\nrf rx 1000\n```\n\nNamed RF transmit commands are accepted only when the RF diagnostics transport is ready. They are explicit operator service actions and do not unlock the automatic climate-output path. A `manual_rf_tx` line proves local transmit lifecycle only; physical device observation remains the acceptance criterion.\n\n'''
if marker not in s:
    raise SystemExit("RF codes docs marker missing")
s = s.replace(marker, section + marker, 1)
p.write_text(s)

p = Path("docs/CURRENT_STATUS.md")
s = p.read_text()
old = '''## Next work\n\nStage28D is IN PROGRESS. Semantic role-to-endpoint mapping validates fail-closed, and stable climate endpoint ID `1` maps to `remote_socket_1`, now physically identified as the fan socket. No semantic actuator role is yet assigned in firmware, the real runtime still uses `LockedFakeRoleDriver`, and no unattended physical-output gate is open. The next bounded hardware step is manual ON/OFF validation of lamp, fan and humidifier using the identities in `docs/RF433_DEVICE_CODES.md`, with physical load observation as the acceptance criterion.\n'''
new = '''## Stage28D service console\n\nThe real-input runtime now includes a bounded USB service console with `help`, `status`, `sensors`, `rf list`, named manual RF ON/OFF commands for lamp/fan/humidifier, and bounded one-shot `rf rx` capture. Read-only menu items also have safe numeric aliases `0..3`; no single-key alias performs actuation.\n\nThe lamp and humidifier captured profiles are frozen in the neutral RF hardware config at `560 us / repeat 10`; their ESP-to-socket physical validation is still pending. The fan continues using the historically qualified `575 us / repeat 10` transmit profile. Manual RF commands use the existing Stage28 RF diagnostics transport and are unavailable when that transport is disabled.\n\nAutomatic climate outputs remain `LockedFakeRoleDriver` / fake-locked. Manual console RF transmit is an explicit service action, not semantic role binding and not physical load-state acknowledgement.\n\n## Next work\n\nStage28D is IN PROGRESS. The next bounded hardware step is to flash a service-console build with the RF diagnostics transport enabled, smoke-test the menu/read-only commands without transmitting, then manually validate ON/OFF for lamp, fan and humidifier while observing each physical load. No unattended physical-output gate is open.\n'''
if old not in s:
    raise SystemExit("CURRENT_STATUS next work marker missing")
p.write_text(s.replace(old, new, 1))

p = Path("docs/CONTINUATION_PLAN.md")
s = p.read_text()
old = '''The next bounded hardware step is manual ESP-to-socket ON/OFF validation for lamp, fan and humidifier, using physical device response as the acceptance criterion. Local TX completion or `SelfTx` alone is insufficient.\n\nKeep the real runtime fake-locked for unattended operation. Do not introduce unattended 230 V control or physical-state acknowledgement semantics during the manual validation step.\n'''
new = '''A bounded USB service console is now part of the real-input runtime. It provides `help`, `status`, `sensors`, `rf list`, named manual RF ON/OFF commands and bounded `rf rx` capture. The lamp/humidifier captured profiles are present in the neutral hardware config at `560 us / repeat 10`; the fan retains its physically qualified `575 us / repeat 10` profile.\n\nThe next bounded hardware step is to flash a console build with the RF diagnostics transport enabled, verify the menu/read-only commands without transmitting, then perform manual ESP-to-socket ON/OFF validation for lamp, fan and humidifier. Physical device response is the acceptance criterion. Local TX completion or `SelfTx` alone is insufficient.\n\nKeep the real runtime fake-locked for unattended operation. Manual console RF commands are explicit service actions only; do not introduce unattended 230 V control or physical-state acknowledgement semantics during this validation step.\n'''
if old not in s:
    raise SystemExit("CONTINUATION_PLAN next hardware marker missing")
p.write_text(s.replace(old, new, 1))

p = Path("continuation.md")
s = p.read_text()
marker = '''## What comes next\n'''
section = '''## Stage28D manual service console slice\n\nA bounded USB service console is now integrated into the real-input runtime. It is intentionally separate from semantic actuator binding and does not replace `LockedFakeRoleDriver`. The console provides read-only `help`, `status`, `sensors`, and `rf list` commands plus explicit named manual RF transmit commands for lamp, fan and humidifier and a bounded one-shot RF receive command. Safe numeric aliases `0..3` exist only for read-only menu actions.\n\nThe neutral RF hardware config now also contains `remote_socket_2` (lamp captured profile, 560 us / repeat 10) and `remote_socket_3` (humidifier captured profile, 560 us / repeat 10). These are capture-derived service profiles pending physical validation. `remote_socket_1` remains the fan and keeps its separately qualified 575 us / repeat 10 transmit evidence. No new climate endpoint IDs or semantic roles are assigned by this slice.\n\nManual RF service commands use the existing Stage28 RF diagnostics transport and therefore require that transport to be enabled in the hardware build. Console TX evidence must continue to be separated from physical socket/load observation.\n\n'''
if marker not in s:
    raise SystemExit("continuation what comes next marker missing")
s = s.replace(marker, section + marker, 1)
old = '''The neutral endpoint registry is now ready. The next semantic step must not guess which actuator role the physical `remote_socket_1` represents. A concrete role assignment and its binary-output policy require an explicit product-level choice; until then preserve `LockedFakeRoleDriver`, fake-lock/no-unattended-mains safety and the frozen hardware identity below the semantic layer.\n'''
new = '''The neutral endpoint registry and manual service console are now ready. Before further semantic output work, hardware-smoke the console and manually validate the captured lamp/fan/humidifier ON/OFF commands with physical load observation. A later semantic step must still not guess actuator-role binding from hardware identity. Preserve `LockedFakeRoleDriver`, fake-lock/no-unattended-mains safety and the frozen hardware identities below the semantic layer.\n'''
if old not in s:
    raise SystemExit("continuation next semantic marker missing")
s = s.replace(old, new, 1)
p.write_text(s)
PY

git diff --check
PC="$(git rev-parse --show-toplevel)/.venv/bin/pre-commit"
if [[ ! -x "$PC" ]]; then
  echo "pre-commit missing" >&2
  exit 2
fi
set +e
"$PC" run --files \
  src/climate/runtime/Stage28ServiceConsoleCommand.h \
  src/climate/runtime/Stage28ServiceConsoleCommand.cpp \
  src/climate/runtime/Stage28ServiceConsole.h \
  src/climate/runtime/Stage28ServiceConsole.cpp \
  src/climate/runtime/Stage28RfDiagnostics.h \
  src/climate/runtime/Stage28RfDiagnostics.cpp \
  src/climate/rf433/Rf433HardwareConfig.h \
  src/climate/ClimateV6RealInputRuntime.cpp \
  src/CMakeLists.txt test/host/CMakeLists.txt \
  test/test_stage28_service_console/test_main.cpp \
  test/test_rf433_protocol/test_main.cpp scripts/stage27c_crowpanel.sh \
  README.md docs/RF433_DEVICE_CODES.md docs/CURRENT_STATUS.md docs/CONTINUATION_PLAN.md continuation.md
FIRST_RC=$?
set -e
if [[ "$FIRST_RC" -ne 0 ]]; then
  "$PC" run --files \
    src/climate/runtime/Stage28ServiceConsoleCommand.h \
    src/climate/runtime/Stage28ServiceConsoleCommand.cpp \
    src/climate/runtime/Stage28ServiceConsole.h \
    src/climate/runtime/Stage28ServiceConsole.cpp \
    src/climate/runtime/Stage28RfDiagnostics.h \
    src/climate/runtime/Stage28RfDiagnostics.cpp \
    src/climate/rf433/Rf433HardwareConfig.h \
    src/climate/ClimateV6RealInputRuntime.cpp \
    src/CMakeLists.txt test/host/CMakeLists.txt \
    test/test_stage28_service_console/test_main.cpp \
    test/test_rf433_protocol/test_main.cpp scripts/stage27c_crowpanel.sh \
    README.md docs/RF433_DEVICE_CODES.md docs/CURRENT_STATUS.md docs/CONTINUATION_PLAN.md continuation.md
fi

git diff --check
export CMAKE_BUILD_PARALLEL_LEVEL=2
cmake -S test/host -B build/host-stage28d-service-console -DCMAKE_BUILD_TYPE=Debug >/tmp/stage28d-service-console-cmake.log
cmake --build build/host-stage28d-service-console --target stage28_service_console_tests rf433_protocol_tests --parallel 2
./build/host-stage28d-service-console/stage28_service_console_tests
./build/host-stage28d-service-console/rf433_protocol_tests

# Explicit CrowPanel firmware compile before the broad gate catches USB-console integration issues.
GROWBOX_RF433_LOOPBACK_ENABLED=1 GROWBOX_RF433_LOOPBACK_AUTO_SMOKE=0 GROWBOX_RF433_REMOTE_CAPTURE_ENABLED=0 \
  STAGE27C_BUILD_DIR=build/idf-stage28d-service-console-crowpanel \
  bash scripts/stage27c_crowpanel.sh build

git add src/climate/runtime/Stage28ServiceConsoleCommand.h \
        src/climate/runtime/Stage28ServiceConsoleCommand.cpp \
        src/climate/runtime/Stage28ServiceConsole.h \
        src/climate/runtime/Stage28ServiceConsole.cpp \
        src/climate/runtime/Stage28RfDiagnostics.h \
        src/climate/runtime/Stage28RfDiagnostics.cpp \
        src/climate/rf433/Rf433HardwareConfig.h \
        src/climate/ClimateV6RealInputRuntime.cpp \
        src/CMakeLists.txt test/host/CMakeLists.txt \
        test/test_stage28_service_console/test_main.cpp \
        test/test_rf433_protocol/test_main.cpp scripts/stage27c_crowpanel.sh \
        README.md docs/RF433_DEVICE_CODES.md docs/CURRENT_STATUS.md docs/CONTINUATION_PLAN.md continuation.md
git commit -m "Add Stage28D USB service console"
NEW=$(git rev-parse HEAD)

export CMAKE_BUILD_PARALLEL_LEVEL=2
bash scripts/quality_gate_push.sh

git diff --check
test -z "$(git status --porcelain)"
git fetch -q origin "$BRANCH"
test "$(git rev-parse origin/$BRANCH)" = "$EXPECTED"
git push origin HEAD:"$BRANCH"
git fetch -q origin "$BRANCH"
test "$(git rev-parse origin/$BRANCH)" = "$NEW"

printf 'STAGE28D_SERVICE_CONSOLE_READY commit=%s parent=%s parser_tests=pass rf_tests=pass crowpanel_build=pass quality_gate=pass runtime_outputs=fake-locked automatic_rf_tx=0\n' "$NEW" "$EXPECTED"
