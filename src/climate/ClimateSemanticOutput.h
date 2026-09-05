#pragma once

#include "climate/ClimateIoAdapters.h"

#include <array>
#include <cstddef>
#include <cstdint>
#include <limits>

namespace growbox::app::climate_io {

using ClimateEndpointId = std::uint16_t;
inline constexpr std::size_t kClimateActuatorRoleCount = 6U;
inline constexpr ClimateEndpointId kUnmappedClimateEndpoint =
    std::numeric_limits<ClimateEndpointId>::max();

struct ClimateRoleEndpointMapping {
  bool enabled = false;
  ClimateEndpointId endpoint = kUnmappedClimateEndpoint;
};

struct ClimateSemanticOutputConfig {
  std::array<ClimateRoleEndpointMapping, kClimateActuatorRoleCount> roles{};
};

enum class ClimateSemanticOutputConfigStatus : std::uint8_t {
  Ok = 0U,
  EnabledRoleUnmapped,
  DuplicateEndpoint,
};

constexpr std::size_t climateRoleIndex(ClimateActuatorRole role) noexcept {
  switch (role) {
  case ClimateActuatorRole::Heater:
    return 0U;
  case ClimateActuatorRole::Cooler:
    return 1U;
  case ClimateActuatorRole::ExhaustFan:
    return 2U;
  case ClimateActuatorRole::Humidifier:
    return 3U;
  case ClimateActuatorRole::Dehumidifier:
    return 4U;
  case ClimateActuatorRole::Co2Doser:
    return 5U;
  }
  return kClimateActuatorRoleCount;
}

ClimateSemanticOutputConfigStatus
validateClimateSemanticOutputConfig(const ClimateSemanticOutputConfig& config) noexcept;

bool bindClimateRole(ClimateSemanticOutputConfig& config, ClimateActuatorRole role,
                     ClimateEndpointId endpoint) noexcept;
bool unbindClimateRole(ClimateSemanticOutputConfig& config, ClimateActuatorRole role) noexcept;

class ClimateOutputEndpoint {
public:
  virtual ~ClimateOutputEndpoint() = default;
  virtual bool write(ClimateEndpointId endpoint, float normalized_level,
                     std::uint64_t monotonic_ms) noexcept = 0;

  // Emergency OFF is distinct from an ordinary zero request because an endpoint
  // may have a safety override that intentionally keeps a role ON.
  virtual bool forceOff(ClimateEndpointId endpoint, std::uint64_t monotonic_ms) noexcept {
    return write(endpoint, 0.0F, monotonic_ms);
  }
};

class MappedClimateRoleDriver final : public ClimateRoleDriver {
public:
  MappedClimateRoleDriver(ClimateSemanticOutputConfig config,
                          ClimateOutputEndpoint& endpoint) noexcept
      : config_(config), config_status_(validateClimateSemanticOutputConfig(config_)),
        endpoint_(endpoint) {}

  bool apply(ClimateActuatorRole role, float level, std::uint64_t monotonic_ms) noexcept override;
  bool forceSafeOff(ClimateActuatorRole role, std::uint64_t monotonic_ms) noexcept override;

  const ClimateSemanticOutputConfig& config() const noexcept {
    return config_;
  }

  ClimateSemanticOutputConfigStatus configStatus() const noexcept {
    return config_status_;
  }

private:
  ClimateSemanticOutputConfig config_{};
  ClimateSemanticOutputConfigStatus config_status_{ClimateSemanticOutputConfigStatus::Ok};
  ClimateOutputEndpoint& endpoint_;
};

} // namespace growbox::app::climate_io
