#include "climate/output/OutputExecutionTelemetry.h"

namespace growbox::app::output {
namespace {

const EndpointIntent* findIntent(
    const std::array<EndpointIntent, kOutputEndpointCapacity>& intents,
    OutputEndpointId endpoint) noexcept {
  for (const auto& candidate : intents) {
    if (endpointIntentActive(candidate) && candidate.endpoint == endpoint) {
      return &candidate;
    }
  }
  return nullptr;
}

const SafetyEndpointConstraint* findSafety(const SafetyEnvelope& safety,
                                           OutputEndpointId endpoint) noexcept {
  for (const auto& candidate : safety.endpoints) {
    if (safetyConstraintActive(candidate) && candidate.endpoint == endpoint) {
      return &candidate;
    }
  }
  return nullptr;
}

OutputIntentTelemetry intentTelemetry(
    const std::array<EndpointIntent, kOutputEndpointCapacity>& intents,
    OutputEndpointId endpoint) noexcept {
  OutputIntentTelemetry result{};
  if (const auto* intent = findIntent(intents, endpoint)) {
    result.active = true;
    result.level = intent->level;
  }
  return result;
}

} // namespace

bool buildOutputExecutionTelemetry(const OutputSupervisorCycleInput& cycle,
                                   const OutputSupervisorResolution& resolution,
                                   const OutputStateStore& state_store,
                                   bool transport_active,
                                   bool lifecycle_active,
                                   OutputLifecycleEvent lifecycle_event,
                                   bool automation_requested,
                                   OutputExecutionTelemetrySnapshot& output) noexcept {
  output = {};
  output.mode = cycle.mode;
  output.transport_active = transport_active;
  output.lifecycle_active = lifecycle_active;
  output.lifecycle_event = lifecycle_event;
  output.automation_requested = automation_requested;

  if (!state_store.valid() || resolution.endpoint_count > kOutputEndpointCapacity) {
    return false;
  }

  for (std::size_t index = 0U; index < resolution.endpoint_count; ++index) {
    const auto& resolved = resolution.endpoints[index];
    if (!isValidOutputEndpoint(resolved.endpoint)) {
      output = {};
      return false;
    }
    const auto* state = state_store.find(resolved.endpoint);
    if (state == nullptr || output.endpoint_count >= output.endpoints.size()) {
      output = {};
      return false;
    }

    auto& endpoint = output.endpoints[output.endpoint_count++];
    endpoint.endpoint = resolved.endpoint;
    endpoint.control = intentTelemetry(cycle.control.endpoints, resolved.endpoint);
    endpoint.schedule = intentTelemetry(cycle.schedule.endpoints, resolved.endpoint);
    endpoint.manual = intentTelemetry(cycle.manual.endpoints, resolved.endpoint);

    if (const auto* safety = findSafety(cycle.safety, resolved.endpoint)) {
      endpoint.safety_active = true;
      endpoint.safety_constraint = safety->constraint;
      endpoint.safety_reason = safety->reason;
    }

    endpoint.selected = resolved.has_selected_input;
    endpoint.selected_level = resolved.requested_level;
    endpoint.selected_source = resolved.source;
    endpoint.selected_reason = resolved.reason;
    endpoint.resolved = resolved.has_resolved_state;
    endpoint.resolved_state = resolved.resolved_state;
    endpoint.held_by_dwell = resolved.held_by_dwell;
    endpoint.safety_override = resolved.safety_override;
    endpoint.inhibited = resolved.inhibited;

    endpoint.attempt_known = state->has_attempt;
    endpoint.attempted_this_cycle = state->has_attempt && state->last_attempt_ms == cycle.monotonic_ms;
    if (state->has_attempt) {
      endpoint.attempt_state = state->last_attempt.state;
      endpoint.attempt_source = state->last_attempt.source;
      endpoint.attempt_reason = state->last_attempt.reason;
      endpoint.transport_status = state->last_transport.status;
      endpoint.transport_error = state->last_transport.error;
    }

    endpoint.last_command_known = state->has_successful_command;
    if (state->has_successful_command) {
      endpoint.last_command_state = state->last_successful_command.state;
      endpoint.last_command_source = state->last_successful_command.source;
      endpoint.last_command_reason = state->last_successful_command.reason;
    }

    endpoint.physical_state = state->physical.state;
    endpoint.physical_independent = state->physical.has_independent_feedback;
  }
  return true;
}

} // namespace growbox::app::output
