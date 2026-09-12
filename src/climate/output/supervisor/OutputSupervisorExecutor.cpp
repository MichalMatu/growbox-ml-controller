#include "climate/output/supervisor/OutputSupervisorExecutor.h"

#include <cstddef>

namespace growbox::app::output {

OutputSupervisorExecutor::OutputSupervisorExecutor(OutputTransport& transport,
                                                   OutputStateStore& state_store,
                                                   OutputSupervisorResolverConfig config) noexcept
    : transport_(transport), state_store_(state_store), config_(config),
      valid_(validConfig(config_)) {}

bool OutputSupervisorExecutor::validConfig(const OutputSupervisorResolverConfig& config) noexcept {
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

const OutputSupervisorEndpointBinding*
OutputSupervisorExecutor::findBinding(OutputEndpointId endpoint) const noexcept {
  for (std::size_t i = 0U; i < config_.count; ++i) {
    if (config_.endpoints[i].endpoint == endpoint) {
      return &config_.endpoints[i];
    }
  }
  return nullptr;
}

const OutputSupervisorEndpointResolution*
OutputSupervisorExecutor::findResolution(const OutputSupervisorResolution& resolution,
                                         OutputEndpointId endpoint) noexcept {
  for (std::size_t i = 0U; i < resolution.endpoint_count; ++i) {
    if (resolution.endpoints[i].endpoint == endpoint) {
      return &resolution.endpoints[i];
    }
  }
  return nullptr;
}

bool OutputSupervisorExecutor::validateResolution(
    const OutputSupervisorResolution& resolution) const noexcept {
  if (!valid_ || !state_store_.valid() || resolution.endpoint_count > kOutputEndpointCapacity ||
      resolution.plan.size > kOutputEndpointCapacity) {
    return false;
  }

  for (std::size_t i = 0U; i < resolution.endpoint_count; ++i) {
    const auto& endpoint = resolution.endpoints[i];
    if (!isValidOutputEndpoint(endpoint.endpoint) || findBinding(endpoint.endpoint) == nullptr ||
        state_store_.find(endpoint.endpoint) == nullptr) {
      return false;
    }
    for (std::size_t j = 0U; j < i; ++j) {
      if (resolution.endpoints[j].endpoint == endpoint.endpoint) {
        return false;
      }
    }
  }

  for (std::size_t i = 0U; i < resolution.plan.size; ++i) {
    const auto& command = resolution.plan.steps[i];
    if (!outputCommandValid(command) || state_store_.find(command.endpoint) == nullptr) {
      return false;
    }
    for (std::size_t j = 0U; j < i; ++j) {
      if (resolution.plan.steps[j].endpoint == command.endpoint) {
        return false;
      }
    }

    const auto* binding = findBinding(command.endpoint);
    const auto* endpoint = findResolution(resolution, command.endpoint);
    if (binding == nullptr || endpoint == nullptr || !endpoint->has_resolved_state ||
        endpoint->resolved_state != command.state) {
      return false;
    }

    if (binding->binary_policy != nullptr) {
      if (!endpoint->has_policy_proposal || !endpoint->policy_proposal.command_required ||
          endpoint->policy_proposal.held_by_dwell ||
          endpoint->policy_proposal.target != command.state ||
          endpoint->policy_proposal.generation != binding->binary_policy->generation()) {
        return false;
      }
    } else if (endpoint->has_policy_proposal) {
      return false;
    }
  }
  return true;
}

bool OutputSupervisorExecutor::execute(const OutputSupervisorResolution& resolution,
                                       std::uint64_t attempted_ms,
                                       ExecutionReport& report) noexcept {
  report = {};
  if (!validateResolution(resolution)) {
    return false;
  }

  bool internal_ok = true;
  for (std::size_t i = 0U; i < resolution.plan.size; ++i) {
    const auto& command = resolution.plan.steps[i];
    const auto* binding = findBinding(command.endpoint);
    const auto* endpoint = findResolution(resolution, command.endpoint);
    if (binding == nullptr || endpoint == nullptr) {
      return false;
    }

    if (!state_store_.recordResolved(command)) {
      return false;
    }

    const TxResult result = transport_.send(command);
    if (!state_store_.recordAttempt(command, attempted_ms, result)) {
      internal_ok = false;
    }

    if (binding->binary_policy != nullptr) {
      const bool completed = result.status == TransportStatus::Completed;
      if (!binding->binary_policy->commit(endpoint->policy_proposal, completed)) {
        internal_ok = false;
      }
    }

    ExecutionStepResult step{};
    step.command = command;
    step.transport = result;
    step.physical = PhysicalOutputState::Unknown;
    if (!appendExecutionResult(report, step)) {
      internal_ok = false;
    }
  }

  return internal_ok;
}

} // namespace growbox::app::output
