#include "climate/ClimateSemanticOutput.h"

#include <algorithm>
#include <cmath>

namespace growbox::app::climate_io {

bool MappedClimateRoleDriver::apply(ClimateActuatorRole role, float level,
                                    std::uint64_t monotonic_ms) noexcept {
  if (!std::isfinite(level)) {
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
