#include "climate/output/OutputPolicyConfig.h"

#include <array>
#include <cstddef>

namespace growbox::app::output {
namespace {

bool validRole(OutputEndpointRole role) noexcept {
  switch (role) {
  case OutputEndpointRole::ExhaustFan:
  case OutputEndpointRole::ScheduledLight:
  case OutputEndpointRole::Humidifier:
    return true;
  }
  return false;
}

bool validAction(OutputPolicyAction action) noexcept {
  switch (action) {
  case OutputPolicyAction::NoCommand:
  case OutputPolicyAction::ForceOff:
  case OutputPolicyAction::ForceOn:
  case OutputPolicyAction::ApplySchedule:
  case OutputPolicyAction::RestoreLastCommand:
    return true;
  }
  return false;
}

void fillLifecycle(OutputEndpointPolicy& endpoint, std::uint8_t order) noexcept {
  for (auto& lifecycle : endpoint.lifecycle) {
    lifecycle.action = OutputPolicyAction::ForceOff;
    lifecycle.order = order;
    lifecycle.delay_ms = 0U;
    lifecycle.retransmit = true;
    lifecycle.max_retries = 1U;
  }
}

} // namespace

OutputPolicyConfigStatus validateOutputPolicyConfig(const OutputPolicyConfig& config) noexcept {
  if (config.version != kOutputPolicySchemaVersion) {
    return OutputPolicyConfigStatus::UnsupportedVersion;
  }
  if (config.count != kOutputEndpointCapacity) {
    return OutputPolicyConfigStatus::InvalidEndpointCount;
  }
  if (config.max_transition_failures == 0U ||
      config.max_transition_failures > kMaxLifecycleContainmentFailures) {
    return OutputPolicyConfigStatus::ContainmentOutOfRange;
  }

  std::array<bool, kOutputEndpointCapacity> role_seen{};
  for (std::size_t index = 0U; index < config.count; ++index) {
    const auto& endpoint = config.endpoints[index];
    if (!isValidOutputEndpoint(endpoint.endpoint)) {
      return OutputPolicyConfigStatus::InvalidEndpoint;
    }
    if (!validRole(endpoint.role)) {
      return OutputPolicyConfigStatus::InvalidRole;
    }
    const std::size_t role_index = static_cast<std::size_t>(endpoint.role);
    if (role_index >= role_seen.size()) {
      return OutputPolicyConfigStatus::InvalidRole;
    }
    if (role_seen[role_index]) {
      return OutputPolicyConfigStatus::DuplicateRole;
    }
    role_seen[role_index] = true;

    for (std::size_t previous = 0U; previous < index; ++previous) {
      if (config.endpoints[previous].endpoint == endpoint.endpoint) {
        return OutputPolicyConfigStatus::DuplicateEndpoint;
      }
    }

    for (const auto& lifecycle : endpoint.lifecycle) {
      if (!validAction(lifecycle.action)) {
        return OutputPolicyConfigStatus::InvalidAction;
      }
      if (lifecycle.order >= config.count) {
        return OutputPolicyConfigStatus::InvalidOrder;
      }
      if (lifecycle.delay_ms > kMaxLifecycleDelayMs) {
        return OutputPolicyConfigStatus::DelayOutOfRange;
      }
      if (lifecycle.max_retries > kMaxLifecycleRetries) {
        return OutputPolicyConfigStatus::RetryOutOfRange;
      }
      if (lifecycle.action == OutputPolicyAction::ApplySchedule &&
          endpoint.role != OutputEndpointRole::ScheduledLight) {
        return OutputPolicyConfigStatus::ApplyScheduleOnNonScheduleRole;
      }
      if (lifecycle.action == OutputPolicyAction::NoCommand &&
          (lifecycle.delay_ms != 0U || lifecycle.retransmit || lifecycle.max_retries != 0U)) {
        return OutputPolicyConfigStatus::NoCommandMetadataInvalid;
      }
    }
  }

  for (bool seen : role_seen) {
    if (!seen) {
      return OutputPolicyConfigStatus::MissingRequiredRole;
    }
  }

  for (std::size_t event_index = 0U; event_index < kOutputLifecycleEventCount; ++event_index) {
    std::array<bool, kOutputEndpointCapacity> order_seen{};
    for (std::size_t endpoint_index = 0U; endpoint_index < config.count; ++endpoint_index) {
      const std::uint8_t order = config.endpoints[endpoint_index].lifecycle[event_index].order;
      if (order_seen[order]) {
        return OutputPolicyConfigStatus::DuplicateOrder;
      }
      order_seen[order] = true;
    }
  }

  return OutputPolicyConfigStatus::Ok;
}

OutputPolicyConfig makeSafeDefaultOutputPolicyConfig(OutputEndpointId exhaust_fan,
                                                     OutputEndpointId scheduled_light,
                                                     OutputEndpointId humidifier) noexcept {
  OutputPolicyConfig config{};
  config.count = static_cast<std::uint8_t>(kOutputEndpointCapacity);
  config.max_transition_failures = 1U;

  config.endpoints[0].endpoint = exhaust_fan;
  config.endpoints[0].role = OutputEndpointRole::ExhaustFan;
  fillLifecycle(config.endpoints[0], 1U);

  config.endpoints[1].endpoint = scheduled_light;
  config.endpoints[1].role = OutputEndpointRole::ScheduledLight;
  fillLifecycle(config.endpoints[1], 0U);
  config.endpoints[1]
      .lifecycle[outputLifecycleEventIndex(OutputLifecycleEvent::AutomationOff)]
      .action = OutputPolicyAction::ApplySchedule;

  config.endpoints[2].endpoint = humidifier;
  config.endpoints[2].role = OutputEndpointRole::Humidifier;
  fillLifecycle(config.endpoints[2], 2U);

  return config;
}

const OutputEndpointPolicy* findOutputPolicyEndpoint(const OutputPolicyConfig& config,
                                                     OutputEndpointId endpoint) noexcept {
  if (!isValidOutputEndpoint(endpoint) || config.count > kOutputEndpointCapacity) {
    return nullptr;
  }
  const OutputEndpointPolicy* found = nullptr;
  for (std::size_t index = 0U; index < config.count; ++index) {
    if (config.endpoints[index].endpoint != endpoint) {
      continue;
    }
    if (found != nullptr) {
      return nullptr;
    }
    found = &config.endpoints[index];
  }
  return found;
}

const OutputEndpointPolicy* findOutputPolicyRole(const OutputPolicyConfig& config,
                                                 OutputEndpointRole role) noexcept {
  if (!validRole(role) || config.count > kOutputEndpointCapacity) {
    return nullptr;
  }
  const OutputEndpointPolicy* found = nullptr;
  for (std::size_t index = 0U; index < config.count; ++index) {
    if (config.endpoints[index].role != role) {
      continue;
    }
    if (found != nullptr) {
      return nullptr;
    }
    found = &config.endpoints[index];
  }
  return found;
}

} // namespace growbox::app::output
