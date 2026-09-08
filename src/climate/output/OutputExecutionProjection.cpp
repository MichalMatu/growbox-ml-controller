#include "climate/output/OutputExecutionProjection.h"

#include <cstddef>

namespace growbox::app::output {
namespace {

const OutputSupervisorEndpointResolution*
findResolution(const OutputSupervisorResolution& resolution, OutputEndpointId endpoint) noexcept {
  const OutputSupervisorEndpointResolution* found = nullptr;
  for (std::size_t index = 0U; index < resolution.endpoint_count; ++index) {
    if (resolution.endpoints[index].endpoint != endpoint) {
      continue;
    }
    if (found != nullptr) {
      return nullptr;
    }
    found = &resolution.endpoints[index];
  }
  return found;
}

const ExecutionStepResult* findReportStep(const ExecutionReport& report,
                                          OutputEndpointId endpoint,
                                          bool& duplicate) noexcept {
  duplicate = false;
  const ExecutionStepResult* found = nullptr;
  for (std::size_t index = 0U; index < report.size; ++index) {
    if (report.steps[index].command.endpoint != endpoint) {
      continue;
    }
    if (found != nullptr) {
      duplicate = true;
      return nullptr;
    }
    found = &report.steps[index];
  }
  return found;
}

bool resolutionEndpointsUnique(const OutputSupervisorResolution& resolution) noexcept {
  for (std::size_t index = 0U; index < resolution.endpoint_count; ++index) {
    const auto endpoint = resolution.endpoints[index].endpoint;
    if (!isValidOutputEndpoint(endpoint)) {
      return false;
    }
    for (std::size_t previous = 0U; previous < index; ++previous) {
      if (resolution.endpoints[previous].endpoint == endpoint) {
        return false;
      }
    }
  }
  return true;
}

} // namespace

bool buildExecutedControlProjection(const OutputSupervisorResolution& resolution,
                                    const ExecutionReport& report,
                                    const OutputStateStore& state_store,
                                    ExecutedControlProjection& output) noexcept {
  output = {};
  if (!state_store.valid() || resolution.endpoint_count > kOutputEndpointCapacity ||
      report.size > kOutputEndpointCapacity || !resolutionEndpointsUnique(resolution)) {
    return false;
  }

  for (std::size_t report_index = 0U; report_index < report.size; ++report_index) {
    const auto& step = report.steps[report_index];
    if (!outputCommandValid(step.command)) {
      return false;
    }
    const auto* endpoint_resolution = findResolution(resolution, step.command.endpoint);
    if (endpoint_resolution == nullptr || !endpoint_resolution->has_resolved_state ||
        endpoint_resolution->resolved_state != step.command.state) {
      return false;
    }
  }

  for (std::size_t index = 0U; index < resolution.endpoint_count; ++index) {
    const auto& endpoint_resolution = resolution.endpoints[index];
    const auto* state = state_store.find(endpoint_resolution.endpoint);
    if (state == nullptr || !state->configured) {
      output = {};
      return false;
    }

    ExecutedEndpointProjection endpoint{};
    endpoint.endpoint = endpoint_resolution.endpoint;
    endpoint.held_by_dwell = endpoint_resolution.held_by_dwell;
    endpoint.source = endpoint_resolution.source;
    endpoint.reason = endpoint_resolution.reason;

    bool duplicate_report = false;
    const auto* report_step = findReportStep(report, endpoint.endpoint, duplicate_report);
    if (duplicate_report) {
      output = {};
      return false;
    }
    if (report_step != nullptr) {
      endpoint.attempted = true;
      endpoint.transport = report_step->transport;
    }

    if (state->has_successful_command) {
      endpoint.has_executed_state = true;
      endpoint.executed_state = state->last_successful_command.state;
    }

    output.endpoints[output.size] = endpoint;
    ++output.size;
  }
  return true;
}

const ExecutedEndpointProjection*
findExecutedEndpointProjection(const ExecutedControlProjection& projection,
                               OutputEndpointId endpoint) noexcept {
  if (!isValidOutputEndpoint(endpoint) || projection.size > kOutputEndpointCapacity) {
    return nullptr;
  }
  for (std::size_t index = 0U; index < projection.size; ++index) {
    if (projection.endpoints[index].endpoint == endpoint) {
      return &projection.endpoints[index];
    }
  }
  return nullptr;
}

} // namespace growbox::app::output
