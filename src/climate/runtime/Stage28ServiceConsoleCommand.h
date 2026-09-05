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
  RtcSetUnix,
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
  std::uint64_t unix_time_s{0U};
};

ServiceConsoleCommand parseServiceConsoleCommand(const char* line) noexcept;
const char* serviceConsoleRfDeviceName(ServiceConsoleRfDevice device) noexcept;
const char* serviceConsoleRfStateName(ServiceConsoleRfState state) noexcept;

} // namespace growbox::app::climate_io::runtime
