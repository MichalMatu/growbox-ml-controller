#pragma once

#include "climate/output/OutputTypes.h"

#include <array>
#include <cstddef>
#include <cstdint>

namespace growbox::app::output {

inline constexpr std::uint16_t kOutputPolicySchemaVersion = 1U;
inline constexpr std::uint32_t kMaxLifecycleDelayMs = 60'000U;
inline constexpr std::uint8_t kMaxLifecycleRetries = 3U;
inline constexpr std::uint8_t kMaxLifecycleContainmentFailures = 3U;

enum class OutputEndpointRole : std::uint8_t {
  ExhaustFan = 0U,
  ScheduledLight,
  Humidifier,
};

enum class OutputLifecycleEvent : std::uint8_t {
  Boot = 0U,
  AutomationOff,
  Recovery,
  Fault,
};

inline constexpr std::size_t kOutputLifecycleEventCount = 4U;

enum class OutputPolicyAction : std::uint8_t {
  NoCommand = 0U,
  ForceOff,
  ForceOn,
  ApplySchedule,
  RestoreLastCommand,
};

struct OutputLifecycleActionPolicy {
  OutputPolicyAction action = OutputPolicyAction::ForceOff;
  std::uint8_t order = 0U;
  std::uint32_t delay_ms = 0U;
  bool retransmit = true;
  std::uint8_t max_retries = 1U;
};

struct OutputEndpointPolicy {
  OutputEndpointId endpoint = kInvalidOutputEndpoint;
  OutputEndpointRole role = OutputEndpointRole::ExhaustFan;
  std::array<OutputLifecycleActionPolicy, kOutputLifecycleEventCount> lifecycle{};
};

struct OutputPolicyConfig {
  std::uint16_t version = kOutputPolicySchemaVersion;
  std::array<OutputEndpointPolicy, kOutputEndpointCapacity> endpoints{};
  std::uint8_t count = 0U;
  std::uint8_t max_transition_failures = 1U;
};

enum class OutputPolicyConfigStatus : std::uint8_t {
  Ok = 0U,
  UnsupportedVersion,
  InvalidEndpointCount,
  InvalidEndpoint,
  DuplicateEndpoint,
  InvalidRole,
  DuplicateRole,
  MissingRequiredRole,
  InvalidAction,
  InvalidOrder,
  DuplicateOrder,
  DelayOutOfRange,
  RetryOutOfRange,
  ContainmentOutOfRange,
  ApplyScheduleOnNonScheduleRole,
  NoCommandMetadataInvalid,
};

constexpr std::size_t outputLifecycleEventIndex(OutputLifecycleEvent event) noexcept {
  return static_cast<std::size_t>(event);
}

OutputPolicyConfigStatus validateOutputPolicyConfig(const OutputPolicyConfig& config) noexcept;

OutputPolicyConfig makeSafeDefaultOutputPolicyConfig(OutputEndpointId exhaust_fan,
                                                     OutputEndpointId scheduled_light,
                                                     OutputEndpointId humidifier) noexcept;

const OutputEndpointPolicy* findOutputPolicyEndpoint(const OutputPolicyConfig& config,
                                                     OutputEndpointId endpoint) noexcept;
const OutputEndpointPolicy* findOutputPolicyRole(const OutputPolicyConfig& config,
                                                 OutputEndpointRole role) noexcept;

} // namespace growbox::app::output
