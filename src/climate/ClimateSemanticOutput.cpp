#include "climate/ClimateSemanticOutput.h"

#include <algorithm>
#include <cmath>

namespace growbox::app::climate_io {

ClimateSemanticOutputConfigStatus
validateClimateSemanticOutputConfig(const ClimateSemanticOutputConfig& config) noexcept {
  for (std::size_t index = 0U; index < config.roles.size(); ++index) {
    const ClimateRoleEndpointMapping& mapping = config.roles[index];
    if (!mapping.enabled) {
      continue;
    }
    if (mapping.endpoint == kUnmappedClimateEndpoint) {
      return ClimateSemanticOutputConfigStatus::EnabledRoleUnmapped;
    }
    for (std::size_t previous = 0U; previous < index; ++previous) {
      const ClimateRoleEndpointMapping& other = config.roles[previous];
      if (other.enabled && other.endpoint == mapping.endpoint) {
        return ClimateSemanticOutputConfigStatus::DuplicateEndpoint;
      }
    }
  }
  return ClimateSemanticOutputConfigStatus::Ok;
}

bool bindClimateRole(ClimateSemanticOutputConfig& config, ClimateActuatorRole role,
                     ClimateEndpointId endpoint) noexcept {
  const std::size_t index = climateRoleIndex(role);
  if (index >= config.roles.size() || endpoint == kUnmappedClimateEndpoint) {
    return false;
  }

  for (std::size_t other_index = 0U; other_index < config.roles.size(); ++other_index) {
    if (other_index == index) {
      continue;
    }
    const ClimateRoleEndpointMapping& other = config.roles[other_index];
    if (other.enabled && other.endpoint == endpoint) {
      return false;
    }
  }

  config.roles[index] = {true, endpoint};
  return true;
}

bool unbindClimateRole(ClimateSemanticOutputConfig& config, ClimateActuatorRole role) noexcept {
  const std::size_t index = climateRoleIndex(role);
  if (index >= config.roles.size()) {
    return false;
  }
  config.roles[index] = {};
  return true;
}

bool MappedClimateRoleDriver::apply(ClimateActuatorRole role, float level,
                                    std::uint64_t monotonic_ms) noexcept {
  if (config_status_ != ClimateSemanticOutputConfigStatus::Ok || !std::isfinite(level)) {
    return false;
  }

  const std::size_t index = climateRoleIndex(role);
  if (index >= config_.roles.size()) {
    return false;
  }

  const float normalized = std::clamp(level, 0.0F, 1.0F);
  const ClimateRoleEndpointMapping& mapping = config_.roles[index];
  if (!mapping.enabled || mapping.endpoint == kUnmappedClimateEndpoint) {
    return normalized == 0.0F;
  }

  return endpoint_.write(mapping.endpoint, normalized, monotonic_ms);
}

} // namespace growbox::app::climate_io
