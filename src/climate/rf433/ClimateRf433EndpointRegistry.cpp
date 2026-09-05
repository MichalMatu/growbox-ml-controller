#include "climate/rf433/ClimateRf433EndpointRegistry.h"

#include <array>

namespace growbox::app::climate_io::rf433 {
namespace {

constexpr std::array<ClimateRf433EndpointBinding, 3U> kBindings{{
    {kRemoteSocket1ClimateEndpoint, &kRemoteSocket1},
    {kRemoteSocket2ClimateEndpoint, &kRemoteSocket2},
    {kRemoteSocket3ClimateEndpoint, &kRemoteSocket3},
}};

} // namespace

const ClimateRf433EndpointBinding* findClimateRf433Endpoint(ClimateEndpointId endpoint) noexcept {
  for (const ClimateRf433EndpointBinding& binding : kBindings) {
    if (binding.endpoint == endpoint) {
      return &binding;
    }
  }
  return nullptr;
}

} // namespace growbox::app::climate_io::rf433
