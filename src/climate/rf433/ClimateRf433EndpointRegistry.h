#pragma once

#include "climate/ClimateSemanticOutput.h"
#include "climate/rf433/Rf433HardwareConfig.h"

namespace growbox::app::climate_io::rf433 {

// Stable neutral endpoint identities for the three physically validated Stage28D loads.
// Semantic actuator roles are assigned above this hardware registry.
inline constexpr ClimateEndpointId kRemoteSocket1ClimateEndpoint = 1U;
inline constexpr ClimateEndpointId kRemoteSocket2ClimateEndpoint = 2U;
inline constexpr ClimateEndpointId kRemoteSocket3ClimateEndpoint = 3U;

struct ClimateRf433EndpointBinding {
  ClimateEndpointId endpoint{kUnmappedClimateEndpoint};
  const RemoteSocketHardwareConfig* hardware{nullptr};
};

const ClimateRf433EndpointBinding* findClimateRf433Endpoint(ClimateEndpointId endpoint) noexcept;

} // namespace growbox::app::climate_io::rf433
