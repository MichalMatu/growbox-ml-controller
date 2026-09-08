#include "climate/Stage28dOutputBindings.h"

namespace growbox::app::climate_io::stage28d {
namespace {

using ::growbox::app::output::OutputEndpointPolicy;
using ::growbox::app::output::OutputEndpointRole;
using ::growbox::app::output::OutputPolicyConfig;
using ::growbox::app::output::OutputPolicyConfigStatus;

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

const OutputEndpointPolicy* requiredRole(const OutputPolicyConfig& policy,
                                         OutputEndpointRole role) noexcept {
  return ::growbox::app::output::findOutputPolicyRole(policy, role);
}

} // namespace

OutputPolicyConfig makeOutputPolicyConfig() noexcept {
  return ::growbox::app::output::makeSafeDefaultOutputPolicyConfig(
      kExhaustFanEndpoint, kScheduledLightEndpoint, kHumidifierEndpoint);
}

ClimateSemanticOutputConfig makeClimateSemanticOutputConfig() noexcept {
  const OutputPolicyConfig policy = makeOutputPolicyConfig();
  if (::growbox::app::output::validateOutputPolicyConfig(policy) != OutputPolicyConfigStatus::Ok) {
    return {};
  }

  ClimateSemanticOutputConfig config{};
  const auto* fan = requiredRole(policy, OutputEndpointRole::ExhaustFan);
  const auto* humidifier = requiredRole(policy, OutputEndpointRole::Humidifier);
  if (fan == nullptr || humidifier == nullptr ||
      !bindClimateRole(config, ClimateActuatorRole::ExhaustFan, fan->endpoint) ||
      !bindClimateRole(config, ClimateActuatorRole::Humidifier, humidifier->endpoint)) {
    return {};
  }
  return config;
}

OutputBindingStatus validateOutputBindings(const ClimateSemanticOutputConfig& config) noexcept {
  const OutputPolicyConfig policy = makeOutputPolicyConfig();
  if (::growbox::app::output::validateOutputPolicyConfig(policy) != OutputPolicyConfigStatus::Ok) {
    return OutputBindingStatus::PolicyConfigInvalid;
  }

  if (validateClimateSemanticOutputConfig(config) != ClimateSemanticOutputConfigStatus::Ok) {
    return OutputBindingStatus::ClimateConfigInvalid;
  }

  const auto* fan = requiredRole(policy, OutputEndpointRole::ExhaustFan);
  const auto* lamp = requiredRole(policy, OutputEndpointRole::ScheduledLight);
  const auto* humidifier = requiredRole(policy, OutputEndpointRole::Humidifier);
  if (fan == nullptr || lamp == nullptr || humidifier == nullptr) {
    return OutputBindingStatus::PolicyConfigInvalid;
  }

  if (!hardwareMatches(fan->endpoint, &rf433::kRemoteSocket1) ||
      !hardwareMatches(lamp->endpoint, &rf433::kRemoteSocket2) ||
      !hardwareMatches(humidifier->endpoint, &rf433::kRemoteSocket3)) {
    return OutputBindingStatus::HardwareRegistryMismatch;
  }

  for (const ClimateRoleEndpointMapping& mapping : config.roles) {
    if (mapping.enabled && mapping.endpoint == lamp->endpoint) {
      return OutputBindingStatus::ScheduledLightRoutedToClimate;
    }
  }

  if (!mappingMatches(config, ClimateActuatorRole::ExhaustFan, fan->endpoint)) {
    return OutputBindingStatus::ExhaustFanMissingOrWrong;
  }
  if (!mappingMatches(config, ClimateActuatorRole::Humidifier, humidifier->endpoint)) {
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
  const OutputPolicyConfig policy = makeOutputPolicyConfig();
  const auto* lamp = requiredRole(policy, OutputEndpointRole::ScheduledLight);
  return lamp != nullptr && endpoint == lamp->endpoint;
}

} // namespace growbox::app::climate_io::stage28d
