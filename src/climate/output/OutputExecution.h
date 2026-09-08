#pragma once

#include "climate/output/OutputIntents.h"

#include <array>
#include <cstddef>
#include <cstdint>

namespace growbox::app::output {

struct OutputCommand {
  OutputEndpointId endpoint = kInvalidOutputEndpoint;
  BinaryOutputState state = BinaryOutputState::Off;
  OutputSource source = OutputSource::None;
  OutputReason reason = OutputReason::None;
  std::uint64_t sequence = 0U;
  std::uint64_t due_ms = 0U;
};

constexpr bool outputCommandValid(const OutputCommand& command) noexcept {
  return isValidOutputEndpoint(command.endpoint);
}

struct OutputPlan {
  std::array<OutputCommand, kOutputEndpointCapacity> steps{};
  std::uint8_t size = 0U;
};

constexpr bool appendOutputCommand(OutputPlan& plan, const OutputCommand& command) noexcept {
  if (!outputCommandValid(command) || plan.size >= kOutputEndpointCapacity) {
    return false;
  }
  plan.steps[plan.size] = command;
  ++plan.size;
  return true;
}

struct TxResult {
  TransportStatus status = TransportStatus::NotAttempted;
  TransportError error = TransportError::None;
};

struct ExecutionStepResult {
  OutputCommand command{};
  TxResult transport{};
  PhysicalOutputState physical = PhysicalOutputState::Unknown;
};

struct ExecutionReport {
  std::array<ExecutionStepResult, kOutputEndpointCapacity> steps{};
  std::uint8_t size = 0U;
};

constexpr bool appendExecutionResult(ExecutionReport& report,
                                     const ExecutionStepResult& result) noexcept {
  if (report.size >= kOutputEndpointCapacity) {
    return false;
  }
  report.steps[report.size] = result;
  ++report.size;
  return true;
}

struct ExecutedControlProjection {
  std::array<EndpointIntent, kOutputEndpointCapacity> endpoints{};
};

} // namespace growbox::app::output
