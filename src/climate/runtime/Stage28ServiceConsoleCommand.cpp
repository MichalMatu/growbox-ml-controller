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

std::size_t splitTokens(std::string_view line, std::array<std::string_view, 4U>& tokens) noexcept {
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

bool parseUnsigned64(std::string_view token, std::uint64_t& output) noexcept {
  if (token.empty()) {
    return false;
  }
  std::uint64_t value = 0U;
  for (const char character : token) {
    if (character < '0' || character > '9') {
      return false;
    }
    const std::uint64_t digit = static_cast<std::uint64_t>(character - '0');
    if (value > (std::numeric_limits<std::uint64_t>::max() - digit) / 10U) {
      return false;
    }
    value = value * 10U + digit;
  }
  output = value;
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

  if (count == 3U && equalsIgnoreCase(tokens[0], "rtc") &&
      equalsIgnoreCase(tokens[1], "set-unix")) {
    std::uint64_t unix_time_s = 0U;
    if (!parseUnsigned64(tokens[2], unix_time_s)) {
      return invalidCommand();
    }
    command.kind = ServiceConsoleCommandKind::RtcSetUnix;
    command.unix_time_s = unix_time_s;
    return command;
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
