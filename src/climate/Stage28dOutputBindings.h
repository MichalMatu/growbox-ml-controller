#pragma once

#include "climate/ClimateSemanticOutput.h"
#include "climate/rf433/ClimateRf433EndpointRegistry.h"

#include <cstdint>

namespace growbox::app::climate_io::stage28d {

inline constexpr ClimateEndpointId kExhaustFanEndpoint = rf433::kRemoteSocket1ClimateEndpoint;
inline constexpr ClimateEndpointId kScheduledLightEndpoint = rf433::kRemoteSocket2ClimateEndpoint;
inline constexpr ClimateEndpointId kHumidifierEndpoint = rf433::kRemoteSocket3ClimateEndpoint;

enum class OutputBindingStatus : std::uint8_t {
  Ok = 0U,
  ClimateConfigInvalid,
  HardwareRegistryMismatch,
  ScheduledLightRoutedToClimate,
  ExhaustFanMissingOrWrong,
  HumidifierMissingOrWrong,
  UnexpectedClimateRole,
};

ClimateSemanticOutputConfig makeClimateSemanticOutputConfig() noexcept;
OutputBindingStatus validateOutputBindings(const ClimateSemanticOutputConfig& config) noexcept;
bool isScheduledLightEndpoint(ClimateEndpointId endpoint) noexcept;

} // namespace growbox::app::climate_io::stage28d
