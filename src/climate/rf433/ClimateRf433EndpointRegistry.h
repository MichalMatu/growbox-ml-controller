#pragma once

#include "climate/ClimateSemanticOutput.h"
#include "climate/rf433/Rf433HardwareConfig.h"

namespace growbox::app::climate_io::rf433 {

// Stable neutral endpoint identity for the Stage28C-frozen hardware pair.
// Semantic actuator roles are assigned above this registry, never here.
inline constexpr ClimateEndpointId kRemoteSocket1ClimateEndpoint = 1U;

struct ClimateRf433EndpointBinding {
  ClimateEndpointId endpoint{kUnmappedClimateEndpoint};
  const RemoteSocketHardwareConfig* hardware{nullptr};
};

const ClimateRf433EndpointBinding* findClimateRf433Endpoint(ClimateEndpointId endpoint) noexcept;

} // namespace growbox::app::climate_io::rf433
