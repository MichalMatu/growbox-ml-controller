#pragma once

#include "climate/ClimateSemanticOutput.h"
#include "climate/output/OutputPolicyConfig.h"
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
  PolicyConfigInvalid,
};

::growbox::app::output::OutputPolicyConfig makeOutputPolicyConfig() noexcept;
ClimateSemanticOutputConfig makeClimateSemanticOutputConfig() noexcept;
ClimateSemanticOutputConfig
makeClimateSemanticOutputConfig(const ::growbox::app::output::OutputPolicyConfig& policy) noexcept;
OutputBindingStatus validateOutputBindings(const ClimateSemanticOutputConfig& config) noexcept;
OutputBindingStatus
validateOutputBindings(const ClimateSemanticOutputConfig& config,
                       const ::growbox::app::output::OutputPolicyConfig& policy) noexcept;
bool isScheduledLightEndpoint(ClimateEndpointId endpoint) noexcept;
bool isScheduledLightEndpoint(ClimateEndpointId endpoint,
                              const ::growbox::app::output::OutputPolicyConfig& policy) noexcept;

} // namespace growbox::app::climate_io::stage28d
