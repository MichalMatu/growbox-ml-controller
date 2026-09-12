#include "climate/output/supervisor/OutputSupervisorResolver.h"

#include <algorithm>
#include <cmath>

namespace growbox::app::output {
namespace {

struct SelectedInput {
  bool active{false};
  NormalizedOutputLevel level{0.0F};
  OutputSource source{OutputSource::None};
  OutputReason reason{OutputReason::None};
  std::uint64_t sequence{0U};
};

NormalizedOutputLevel normalizedLevel(NormalizedOutputLevel value) noexcept {
  if (!std::isfinite(value)) {
    return 0.0F;
  }
  return std::clamp(value, 0.0F, 1.0F);
}

OutputReason selectedReason(OutputReason candidate, OutputReason fallback) noexcept {
  return candidate == OutputReason::None ? fallback : candidate;
}

} // namespace

OutputSupervisorResolver::OutputSupervisorResolver(OutputSupervisorResolverConfig config) noexcept
    : config_(config), valid_(validConfig(config_)) {}

bool OutputSupervisorResolver::validConfig(const OutputSupervisorResolverConfig& config) noexcept {
  if (config.count == 0U || config.count > kOutputEndpointCapacity) {
    return false;
  }
  for (std::size_t i = 0U; i < config.count; ++i) {
    if (!isValidOutputEndpoint(config.endpoints[i].endpoint)) {
      return false;
    }
    for (std::size_t j = 0U; j < i; ++j) {
      if (config.endpoints[j].endpoint == config.endpoints[i].endpoint) {
        return false;
      }
    }
  }
  return true;
}

const EndpointIntent* OutputSupervisorResolver::findIntent(
    const std::array<EndpointIntent, kOutputEndpointCapacity>& intents,
    OutputEndpointId endpoint) noexcept {
  for (const auto& candidate : intents) {
    if (endpointIntentActive(candidate) && candidate.endpoint == endpoint) {
      return &candidate;
    }
  }
  return nullptr;
}

const SafetyEndpointConstraint*
OutputSupervisorResolver::findSafetyConstraint(const SafetyEnvelope& safety,
                                               OutputEndpointId endpoint) noexcept {
  for (const auto& candidate : safety.endpoints) {
    if (safetyConstraintActive(candidate) && candidate.endpoint == endpoint) {
      return &candidate;
    }
  }
  return nullptr;
}

BinaryOutputState
OutputSupervisorResolver::directBinaryState(NormalizedOutputLevel level) noexcept {
  return normalizedLevel(level) >= 0.5F ? BinaryOutputState::On : BinaryOutputState::Off;
}

bool OutputSupervisorResolver::commandAlreadyCompleted(const OutputStateStore& state_store,
                                                       const OutputCommand& command) noexcept {
  const auto* state = state_store.find(command.endpoint);
  return state != nullptr && state->has_successful_command &&
         state->last_successful_command.state == command.state;
}

bool OutputSupervisorResolver::resolve(const OutputSupervisorCycleInput& input,
                                       const OutputStateStore& state_store,
                                       OutputSupervisorResolution& output) noexcept {
  output = {};
  if (!valid_ || !state_store.valid()) {
    return false;
  }

  for (std::size_t index = 0U; index < config_.count; ++index) {
    const auto& binding = config_.endpoints[index];
    if (state_store.find(binding.endpoint) == nullptr) {
      output = {};
      return false;
    }

    auto& resolved = output.endpoints[output.endpoint_count++];
    resolved.endpoint = binding.endpoint;

    SelectedInput selected{};
    if (input.mode == SupervisorMode::Automatic) {
      if (const auto* manual = findIntent(input.manual.endpoints, binding.endpoint)) {
        selected = {true, normalizedLevel(manual->level), OutputSource::Manual,
                    selectedReason(input.manual.metadata.reason, OutputReason::ManualRequest),
                    input.manual.metadata.sequence};
      } else if (const auto* schedule = findIntent(input.schedule.endpoints, binding.endpoint)) {
        selected = {true, normalizedLevel(schedule->level), OutputSource::Schedule,
                    selectedReason(input.schedule.metadata.reason, OutputReason::ScheduleRequest),
                    input.schedule.metadata.sequence};
      } else if (const auto* control = findIntent(input.control.endpoints, binding.endpoint)) {
        selected = {true, normalizedLevel(control->level), OutputSource::Climate,
                    selectedReason(input.control.metadata.reason, OutputReason::ClimateDecision),
                    input.control.metadata.sequence};
      }
    }

    BinaryPolicyOverride policy_override = BinaryPolicyOverride::None;
    bool direct_override = false;
    BinaryOutputState direct_override_state = BinaryOutputState::Off;
    if (const auto* safety = findSafetyConstraint(input.safety, binding.endpoint)) {
      if (safety->constraint == SafetyConstraint::Inhibit) {
        resolved.has_selected_input = true;
        resolved.source = OutputSource::Safety;
        resolved.reason = selectedReason(safety->reason, OutputReason::ThermalSafety);
        resolved.sequence = input.safety.metadata.sequence;
        resolved.inhibited = true;
        continue;
      }
      if (safety->constraint == SafetyConstraint::ForceOff ||
          safety->constraint == SafetyConstraint::ForceOn) {
        selected.active = true;
        selected.level = safety->constraint == SafetyConstraint::ForceOn ? 1.0F : 0.0F;
        selected.source = OutputSource::Safety;
        selected.reason = selectedReason(safety->reason, OutputReason::ThermalSafety);
        selected.sequence = input.safety.metadata.sequence;
        resolved.safety_override = true;
        policy_override = safety->constraint == SafetyConstraint::ForceOn
                              ? BinaryPolicyOverride::ForceOn
                              : BinaryPolicyOverride::ForceOff;
        direct_override = true;
        direct_override_state = safety->constraint == SafetyConstraint::ForceOn
                                    ? BinaryOutputState::On
                                    : BinaryOutputState::Off;
      }
    }

    if (!selected.active) {
      continue;
    }

    resolved.has_selected_input = true;
    resolved.requested_level = selected.level;
    resolved.source = selected.source;
    resolved.reason = selected.reason;
    resolved.sequence = selected.sequence;

    OutputCommand command{};
    command.endpoint = binding.endpoint;
    command.source = selected.source;
    command.reason = selected.reason;
    command.sequence = selected.sequence;
    command.due_ms = input.monotonic_ms;

    if (binding.binary_policy != nullptr) {
      const auto proposal =
          binding.binary_policy->propose(selected.level, input.monotonic_ms, policy_override);
      resolved.has_policy_proposal = true;
      resolved.policy_proposal = proposal;
      resolved.held_by_dwell = proposal.held_by_dwell;
      resolved.has_resolved_state = true;
      resolved.resolved_state = proposal.target;
      if (!proposal.command_required) {
        continue;
      }
      command.state = proposal.target;
      if (!appendOutputCommand(output.plan, command)) {
        output = {};
        return false;
      }
      continue;
    }

    resolved.has_resolved_state = true;
    resolved.resolved_state =
        direct_override ? direct_override_state : directBinaryState(selected.level);
    command.state = resolved.resolved_state;
    if (commandAlreadyCompleted(state_store, command)) {
      continue;
    }
    if (!appendOutputCommand(output.plan, command)) {
      output = {};
      return false;
    }
  }

  return true;
}

} // namespace growbox::app::output
