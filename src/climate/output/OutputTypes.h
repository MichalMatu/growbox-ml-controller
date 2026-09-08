#pragma once

#include <cstddef>
#include <cstdint>
#include <limits>

namespace growbox::app::output {

using OutputEndpointId = std::uint16_t;
using NormalizedOutputLevel = float;

inline constexpr OutputEndpointId kInvalidOutputEndpoint =
    std::numeric_limits<OutputEndpointId>::max();
inline constexpr std::size_t kOutputEndpointCapacity = 3U;

enum class BinaryOutputState : std::uint8_t { Off = 0U, On = 1U };

enum class OutputSource : std::uint8_t {
  None = 0U,
  Climate,
  Schedule,
  Manual,
  Safety,
  Lifecycle,
  Maintenance,
};

enum class OutputReason : std::uint8_t {
  None = 0U,
  ClimateDecision,
  ScheduleRequest,
  ManualRequest,
  ThermalSafety,
  LifecyclePolicy,
  FaultContainment,
  MaintenanceRequest,
};

enum class SupervisorMode : std::uint8_t {
  BootLocked = 0U,
  Arming,
  Automatic,
  Recovering,
  Disabled,
  FaultLocked,
  MaintenanceLocked,
};

enum class TransportStatus : std::uint8_t { NotAttempted = 0U, Completed, Failed };

enum class TransportError : std::uint8_t {
  None = 0U,
  InvalidEndpoint,
  InvalidCommand,
  Unavailable,
  Busy,
  IoFailure,
};

constexpr bool isValidOutputEndpoint(OutputEndpointId endpoint) noexcept {
  return endpoint != kInvalidOutputEndpoint;
}

} // namespace growbox::app::output
