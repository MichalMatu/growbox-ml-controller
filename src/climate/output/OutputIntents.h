#pragma once

#include "climate/output/OutputTypes.h"

#include <array>
#include <cstdint>

namespace growbox::app::output {

struct IntentMetadata {
  std::uint64_t sequence = 0U;
  std::uint64_t monotonic_ms = 0U;
  OutputSource source = OutputSource::None;
  OutputReason reason = OutputReason::None;
};

struct EndpointIntent {
  OutputEndpointId endpoint = kInvalidOutputEndpoint;
  NormalizedOutputLevel level = 0.0F;
};

constexpr bool endpointIntentActive(const EndpointIntent& intent) noexcept {
  return isValidOutputEndpoint(intent.endpoint);
}

constexpr bool setEndpointIntent(EndpointIntent& intent, OutputEndpointId endpoint,
                                 NormalizedOutputLevel level) noexcept {
  if (!isValidOutputEndpoint(endpoint)) {
    intent = {};
    return false;
  }
  intent.endpoint = endpoint;
  intent.level = level;
  return true;
}

struct ControlIntent {
  IntentMetadata metadata{};
  std::array<EndpointIntent, kOutputEndpointCapacity> endpoints{};
};

struct ScheduleIntent {
  IntentMetadata metadata{};
  std::array<EndpointIntent, kOutputEndpointCapacity> endpoints{};
};

struct ManualIntent {
  IntentMetadata metadata{};
  std::array<EndpointIntent, kOutputEndpointCapacity> endpoints{};
};

enum class SafetyConstraint : std::uint8_t { Allow = 0U, ForceOff, ForceOn, Inhibit };

struct SafetyEndpointConstraint {
  OutputEndpointId endpoint = kInvalidOutputEndpoint;
  SafetyConstraint constraint = SafetyConstraint::Allow;
  OutputReason reason = OutputReason::None;
};

constexpr bool safetyConstraintActive(const SafetyEndpointConstraint& constraint) noexcept {
  return isValidOutputEndpoint(constraint.endpoint);
}

constexpr bool setSafetyConstraint(SafetyEndpointConstraint& target, OutputEndpointId endpoint,
                                   SafetyConstraint constraint, OutputReason reason) noexcept {
  if (!isValidOutputEndpoint(endpoint)) {
    target = {};
    return false;
  }
  target.endpoint = endpoint;
  target.constraint = constraint;
  target.reason = reason;
  return true;
}

struct SafetyEnvelope {
  IntentMetadata metadata{};
  std::array<SafetyEndpointConstraint, kOutputEndpointCapacity> endpoints{};
};

} // namespace growbox::app::output
