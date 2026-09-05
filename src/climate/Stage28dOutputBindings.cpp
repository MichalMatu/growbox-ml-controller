#include "climate/Stage28dOutputBindings.h"

namespace growbox::app::climate_io::stage28d {
namespace {

bool mappingMatches(const ClimateSemanticOutputConfig& config, ClimateActuatorRole role,
                    ClimateEndpointId endpoint) noexcept {
  const std::size_t index = climateRoleIndex(role);
  if (index >= config.roles.size()) {
    return false;
  }
  const ClimateRoleEndpointMapping& mapping = config.roles[index];
  return mapping.enabled && mapping.endpoint == endpoint;
}

bool mappingIsCleanlyDisabled(const ClimateSemanticOutputConfig& config,
                              ClimateActuatorRole role) noexcept {
  const std::size_t index = climateRoleIndex(role);
  if (index >= config.roles.size()) {
    return false;
  }
  const ClimateRoleEndpointMapping& mapping = config.roles[index];
  return !mapping.enabled && mapping.endpoint == kUnmappedClimateEndpoint;
}

bool hardwareMatches(ClimateEndpointId endpoint,
                     const rf433::RemoteSocketHardwareConfig* expected) noexcept {
  const rf433::ClimateRf433EndpointBinding* binding = rf433::findClimateRf433Endpoint(endpoint);
  return binding != nullptr && binding->endpoint == endpoint && binding->hardware == expected;
}

} // namespace

ClimateSemanticOutputConfig makeClimateSemanticOutputConfig() noexcept {
  ClimateSemanticOutputConfig config{};
  const bool fan_bound =
      bindClimateRole(config, ClimateActuatorRole::ExhaustFan, kExhaustFanEndpoint);
  const bool humidifier_bound =
      bindClimateRole(config, ClimateActuatorRole::Humidifier, kHumidifierEndpoint);
  if (!fan_bound || !humidifier_bound) {
    return {};
  }
  return config;
}

OutputBindingStatus validateOutputBindings(const ClimateSemanticOutputConfig& config) noexcept {
  if (validateClimateSemanticOutputConfig(config) != ClimateSemanticOutputConfigStatus::Ok) {
    return OutputBindingStatus::ClimateConfigInvalid;
  }

  if (!hardwareMatches(kExhaustFanEndpoint, &rf433::kRemoteSocket1) ||
      !hardwareMatches(kScheduledLightEndpoint, &rf433::kRemoteSocket2) ||
      !hardwareMatches(kHumidifierEndpoint, &rf433::kRemoteSocket3)) {
    return OutputBindingStatus::HardwareRegistryMismatch;
  }

  for (const ClimateRoleEndpointMapping& mapping : config.roles) {
    if (mapping.enabled && mapping.endpoint == kScheduledLightEndpoint) {
      return OutputBindingStatus::ScheduledLightRoutedToClimate;
    }
  }

  if (!mappingMatches(config, ClimateActuatorRole::ExhaustFan, kExhaustFanEndpoint)) {
    return OutputBindingStatus::ExhaustFanMissingOrWrong;
  }
  if (!mappingMatches(config, ClimateActuatorRole::Humidifier, kHumidifierEndpoint)) {
    return OutputBindingStatus::HumidifierMissingOrWrong;
  }

  constexpr ClimateActuatorRole kDisabledClimateRoles[] = {
      ClimateActuatorRole::Heater,
      ClimateActuatorRole::Cooler,
      ClimateActuatorRole::Dehumidifier,
      ClimateActuatorRole::Co2Doser,
  };
  for (ClimateActuatorRole role : kDisabledClimateRoles) {
    if (!mappingIsCleanlyDisabled(config, role)) {
      return OutputBindingStatus::UnexpectedClimateRole;
    }
  }

  return OutputBindingStatus::Ok;
}

bool isScheduledLightEndpoint(ClimateEndpointId endpoint) noexcept {
  return endpoint == kScheduledLightEndpoint;
}

} // namespace growbox::app::climate_io::stage28d
