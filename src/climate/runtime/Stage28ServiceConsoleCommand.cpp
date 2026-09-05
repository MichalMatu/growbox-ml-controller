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
constexpr std::uint32_t kMaximumSdReadBytes = 384U;

char lowerAscii(char value) noexcept { return value >= 'A' && value <= 'Z' ? static_cast<char>(value - 'A' + 'a') : value; }
bool equalsIgnoreCase(std::string_view left, std::string_view right) noexcept {
  if (left.size() != right.size()) return false;
  for (std::size_t i=0; i<left.size(); ++i) if (lowerAscii(left[i]) != lowerAscii(right[i])) return false;
  return true;
}
bool isSpace(char value) noexcept { return value == ' ' || value == '\t'; }
std::size_t splitTokens(std::string_view line, std::array<std::string_view, 5U>& tokens) noexcept {
  std::size_t count=0U, cursor=0U;
  while (cursor < line.size()) {
    while (cursor < line.size() && isSpace(line[cursor])) ++cursor;
    if (cursor >= line.size()) break;
    const std::size_t start=cursor;
    while (cursor < line.size() && !isSpace(line[cursor])) ++cursor;
    if (count >= tokens.size()) return tokens.size()+1U;
    tokens[count++] = line.substr(start, cursor-start);
  }
  return count;
}
bool parseUnsigned(std::string_view token, std::uint32_t& output) noexcept {
  if (token.empty()) return false;
  std::uint64_t value=0U;
  for (char c: token) {
    if (c<'0'||c>'9') return false;
    value=value*10U+static_cast<std::uint64_t>(c-'0');
    if (value>std::numeric_limits<std::uint32_t>::max()) return false;
  }
  output=static_cast<std::uint32_t>(value); return true;
}
bool parseUnsigned64(std::string_view token, std::uint64_t& output) noexcept {
  if (token.empty()) return false;
  std::uint64_t value=0U;
  for (char c: token) {
    if (c<'0'||c>'9') return false;
    const auto d=static_cast<std::uint64_t>(c-'0');
    if (value>(std::numeric_limits<std::uint64_t>::max()-d)/10U) return false;
    value=value*10U+d;
  }
  output=value; return true;
}
bool parseDevice(std::string_view token, ServiceConsoleRfDevice& device) noexcept {
  if (equalsIgnoreCase(token,"lamp")) { device=ServiceConsoleRfDevice::Lamp; return true; }
  if (equalsIgnoreCase(token,"fan")) { device=ServiceConsoleRfDevice::Fan; return true; }
  if (equalsIgnoreCase(token,"humidifier")) { device=ServiceConsoleRfDevice::Humidifier; return true; }
  return false;
}
bool parseState(std::string_view token, ServiceConsoleRfState& state) noexcept {
  if (equalsIgnoreCase(token,"on")) { state=ServiceConsoleRfState::On; return true; }
  if (equalsIgnoreCase(token,"off")) { state=ServiceConsoleRfState::Off; return true; }
  return false;
}
bool copyLogFilename(std::string_view token, std::array<char,16U>& output) noexcept {
  if (token.size()!=11U || token[8]!='.' || lowerAscii(token[9])!='j' || lowerAscii(token[10])!='l') return false;
  for (std::size_t i=0; i<8U; ++i) {
    const char c=token[i];
    const bool hex=(c>='0'&&c<='9')||(c>='a'&&c<='f')||(c>='A'&&c<='F');
    if (!hex) return false;
  }
  for (std::size_t i=0; i<token.size(); ++i) output[i]=token[i];
  output[token.size()]='\0';
  return true;
}
ServiceConsoleCommand invalidCommand() noexcept { ServiceConsoleCommand c{}; c.kind=ServiceConsoleCommandKind::Invalid; return c; }

} // namespace

ServiceConsoleCommand parseServiceConsoleCommand(const char* line) noexcept {
  if (line==nullptr) return invalidCommand();
  const std::string_view input(line);
  std::array<std::string_view,5U> tokens{};
  const std::size_t count=splitTokens(input,tokens);
  if (count==0U) return {};
  if (count>tokens.size()) return invalidCommand();

  ServiceConsoleCommand command{};
  if (count==1U) {
    if (equalsIgnoreCase(tokens[0],"help")||equalsIgnoreCase(tokens[0],"menu")||tokens[0]=="?"||tokens[0]=="0") { command.kind=ServiceConsoleCommandKind::Help; return command; }
    if (equalsIgnoreCase(tokens[0],"status")||tokens[0]=="1") { command.kind=ServiceConsoleCommandKind::Status; return command; }
    if (equalsIgnoreCase(tokens[0],"sensors")||tokens[0]=="2") { command.kind=ServiceConsoleCommandKind::Sensors; return command; }
    if (equalsIgnoreCase(tokens[0],"rf")||tokens[0]=="3") { command.kind=ServiceConsoleCommandKind::RfList; return command; }
    return invalidCommand();
  }
  if (count==3U && equalsIgnoreCase(tokens[0],"rtc") && equalsIgnoreCase(tokens[1],"set-unix")) {
    if (!parseUnsigned64(tokens[2],command.unix_time_s)) return invalidCommand();
    command.kind=ServiceConsoleCommandKind::RtcSetUnix; return command;
  }
  if (equalsIgnoreCase(tokens[0],"sdlog")) {
    if (count==2U && equalsIgnoreCase(tokens[1],"status")) { command.kind=ServiceConsoleCommandKind::SdLogStatus; return command; }
    if (count==2U && equalsIgnoreCase(tokens[1],"list")) { command.kind=ServiceConsoleCommandKind::SdLogList; return command; }
    if (count==2U && equalsIgnoreCase(tokens[1],"selftest")) { command.kind=ServiceConsoleCommandKind::SdLogSelfTest; return command; }
    if (count==5U && equalsIgnoreCase(tokens[1],"read")) {
      if (!copyLogFilename(tokens[2],command.filename) || !parseUnsigned(tokens[3],command.offset) || !parseUnsigned(tokens[4],command.length) || command.length==0U || command.length>kMaximumSdReadBytes) return invalidCommand();
      command.kind=ServiceConsoleCommandKind::SdLogRead; return command;
    }
    return invalidCommand();
  }
  if (!equalsIgnoreCase(tokens[0],"rf")) return invalidCommand();
  if (count==2U && equalsIgnoreCase(tokens[1],"list")) { command.kind=ServiceConsoleCommandKind::RfList; return command; }
  if (equalsIgnoreCase(tokens[1],"rx")) {
    if (count==2U) { command.kind=ServiceConsoleCommandKind::RfReceive; command.timeout_ms=kDefaultRxTimeoutMs; return command; }
    if (count==3U) { if (!parseUnsigned(tokens[2],command.timeout_ms)||command.timeout_ms<kMinimumRxTimeoutMs||command.timeout_ms>kMaximumRxTimeoutMs) return invalidCommand(); command.kind=ServiceConsoleCommandKind::RfReceive; return command; }
    return invalidCommand();
  }
  if (count==3U && parseDevice(tokens[1],command.device) && parseState(tokens[2],command.state)) { command.kind=ServiceConsoleCommandKind::RfTransmit; return command; }
  return invalidCommand();
}

const char* serviceConsoleRfDeviceName(ServiceConsoleRfDevice device) noexcept {
  switch(device) { case ServiceConsoleRfDevice::Lamp:return "lamp"; case ServiceConsoleRfDevice::Fan:return "fan"; case ServiceConsoleRfDevice::Humidifier:return "humidifier"; }
  return "unknown";
}
const char* serviceConsoleRfStateName(ServiceConsoleRfState state) noexcept { return state==ServiceConsoleRfState::On ? "on" : "off"; }

} // namespace growbox::app::climate_io::runtime
