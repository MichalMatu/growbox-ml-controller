#pragma once

#include "climate/output/BinaryActuatorPolicy.h"
#include "climate/output/OutputExecution.h"
#include "climate/output/OutputStateStore.h"

#include <array>
#include <cstddef>
#include <cstdint>

namespace growbox::app::output {

struct OutputSupervisorEndpointBinding {
  OutputEndpointId endpoint = kInvalidOutputEndpoint;
  BinaryActuatorPolicy* binary_policy = nullptr;
};

struct OutputSupervisorResolverConfig {
  std::array<OutputSupervisorEndpointBinding, kOutputEndpointCapacity> endpoints{};
  std::size_t count = 0U;
};

struct OutputSupervisorCycleInput {
  SupervisorMode mode = SupervisorMode::Automatic;
  std::uint64_t monotonic_ms = 0U;
  ControlIntent control{};
  ScheduleIntent schedule{};
  ManualIntent manual{};
  SafetyEnvelope safety{};
};

struct OutputSupervisorEndpointResolution {
  OutputEndpointId endpoint = kInvalidOutputEndpoint;
  bool has_selected_input = false;
  NormalizedOutputLevel requested_level = 0.0F;
  OutputSource source = OutputSource::None;
  OutputReason reason = OutputReason::None;
  std::uint64_t sequence = 0U;
  bool inhibited = false;
  bool has_resolved_state = false;
  BinaryOutputState resolved_state = BinaryOutputState::Off;
  bool held_by_dwell = false;
  bool safety_override = false;
  bool has_policy_proposal = false;
  BinaryActuatorProposal policy_proposal{};
};

struct OutputSupervisorResolution {
  OutputPlan plan{};
  std::array<OutputSupervisorEndpointResolution, kOutputEndpointCapacity> endpoints{};
  std::uint8_t endpoint_count = 0U;
};

class OutputSupervisorResolver final {
public:
  explicit OutputSupervisorResolver(OutputSupervisorResolverConfig config) noexcept;

  bool valid() const noexcept {
    return valid_;
  }
  const OutputSupervisorResolverConfig& config() const noexcept {
    return config_;
  }

  bool resolve(const OutputSupervisorCycleInput& input, const OutputStateStore& state_store,
               OutputSupervisorResolution& output) noexcept;

private:
  static bool validConfig(const OutputSupervisorResolverConfig& config) noexcept;
  static const EndpointIntent*
  findIntent(const std::array<EndpointIntent, kOutputEndpointCapacity>& intents,
             OutputEndpointId endpoint) noexcept;
  static const SafetyEndpointConstraint* findSafetyConstraint(const SafetyEnvelope& safety,
                                                              OutputEndpointId endpoint) noexcept;
  static BinaryOutputState directBinaryState(NormalizedOutputLevel level) noexcept;
  static bool commandAlreadyCompleted(const OutputStateStore& state_store,
                                      const OutputCommand& command) noexcept;

  OutputSupervisorResolverConfig config_{};
  bool valid_{false};
};

} // namespace growbox::app::output
