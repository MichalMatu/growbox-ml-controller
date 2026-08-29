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

class ClimateOutputEndpoint {
public:
  virtual ~ClimateOutputEndpoint() = default;
  virtual bool write(ClimateEndpointId endpoint, float normalized_level,
                     std::uint64_t monotonic_ms) noexcept = 0;
};

class MappedClimateRoleDriver final : public ClimateRoleDriver {
public:
  MappedClimateRoleDriver(ClimateSemanticOutputConfig config,
                          ClimateOutputEndpoint& endpoint) noexcept
      : config_(config), endpoint_(endpoint) {}

  bool apply(ClimateActuatorRole role, float level, std::uint64_t monotonic_ms) noexcept override;

  const ClimateSemanticOutputConfig& config() const noexcept {
    return config_;
  }

private:
  ClimateSemanticOutputConfig config_{};
  ClimateOutputEndpoint& endpoint_;
};

} // namespace growbox::app::climate_io
