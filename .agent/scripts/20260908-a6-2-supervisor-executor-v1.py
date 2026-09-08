from pathlib import Path

HEADER = r'''#pragma once

#include "climate/output/OutputSupervisorResolver.h"
#include "climate/output/OutputTransport.h"

#include <cstdint>

namespace growbox::app::output {

class OutputSupervisorExecutor final {
public:
  OutputSupervisorExecutor(OutputTransport& transport, OutputStateStore& state_store,
                           OutputSupervisorResolverConfig config) noexcept;

  bool valid() const noexcept { return valid_; }

  // A transport failure is represented in ExecutionReport and does not make
  // this method fail. false is reserved for invalid supervisor contracts or
  // internal bookkeeping failures.
  bool execute(const OutputSupervisorResolution& resolution, std::uint64_t attempted_ms,
               ExecutionReport& report) noexcept;

private:
  static bool validConfig(const OutputSupervisorResolverConfig& config) noexcept;
  const OutputSupervisorEndpointBinding* findBinding(OutputEndpointId endpoint) const noexcept;
  static const OutputSupervisorEndpointResolution*
  findResolution(const OutputSupervisorResolution& resolution, OutputEndpointId endpoint) noexcept;
  bool validateResolution(const OutputSupervisorResolution& resolution) const noexcept;

  OutputTransport& transport_;
  OutputStateStore& state_store_;
  OutputSupervisorResolverConfig config_{};
  bool valid_{false};
};

} // namespace growbox::app::output
'''

SOURCE = r'''#include "climate/output/OutputSupervisorExecutor.h"

#include <cstddef>

namespace growbox::app::output {

OutputSupervisorExecutor::OutputSupervisorExecutor(OutputTransport& transport,
                                                   OutputStateStore& state_store,
                                                   OutputSupervisorResolverConfig config) noexcept
    : transport_(transport), state_store_(state_store), config_(config),
      valid_(validConfig(config_)) {}

bool OutputSupervisorExecutor::validConfig(
    const OutputSupervisorResolverConfig& config) noexcept {
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

const OutputSupervisorEndpointResolution* OutputSupervisorExecutor::findResolution(
    const OutputSupervisorResolution& resolution, OutputEndpointId endpoint) noexcept {
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
'''

TEST = r'''#include "climate/output/OutputSupervisorExecutor.h"

#include <array>
#include <cassert>
#include <cstddef>
#include <cstdint>

namespace {

namespace output = growbox::app::output;
constexpr output::OutputEndpointId kFan = 1U;
constexpr output::OutputEndpointId kLamp = 2U;
constexpr output::OutputEndpointId kHumidifier = 3U;

class FakeTransport final : public output::OutputTransport {
public:
  std::array<output::TxResult, output::kOutputEndpointCapacity> scripted{};
  std::array<output::OutputCommand, output::kOutputEndpointCapacity> sent{};
  std::size_t scripted_count{0U};
  std::size_t sent_count{0U};

  output::TxResult send(const output::OutputCommand& command) noexcept override {
    assert(sent_count < sent.size());
    sent[sent_count] = command;
    const auto result = sent_count < scripted_count
                            ? scripted[sent_count]
                            : output::TxResult{output::TransportStatus::Completed,
                                               output::TransportError::None};
    ++sent_count;
    return result;
  }
};

output::OutputStateStore makeStore() {
  output::OutputStateStore store;
  const std::array<output::OutputEndpointId, output::kOutputEndpointCapacity> endpoints{
      kFan, kLamp, kHumidifier};
  assert(store.configure(endpoints, endpoints.size()));
  return store;
}

output::OutputSupervisorResolverConfig makeConfig(output::BinaryActuatorPolicy& fan,
                                                  output::BinaryActuatorPolicy& humidifier) {
  output::OutputSupervisorResolverConfig config{};
  config.endpoints[0] = {kFan, &fan};
  config.endpoints[1] = {kLamp, nullptr};
  config.endpoints[2] = {kHumidifier, &humidifier};
  config.count = 3U;
  return config;
}

void setIntent(output::EndpointIntent& intent, output::OutputEndpointId endpoint, float level) {
  assert(output::setEndpointIntent(intent, endpoint, level));
}

output::OutputSupervisorCycleInput allOnInput(std::uint64_t now_ms) {
  output::OutputSupervisorCycleInput input{};
  input.monotonic_ms = now_ms;
  input.control.metadata.sequence = 11U;
  input.control.metadata.reason = output::OutputReason::ClimateDecision;
  setIntent(input.control.endpoints[0], kFan, 1.0F);
  setIntent(input.control.endpoints[1], kHumidifier, 1.0F);
  input.schedule.metadata.sequence = 12U;
  input.schedule.metadata.reason = output::OutputReason::ScheduleRequest;
  setIntent(input.schedule.endpoints[0], kLamp, 1.0F);
  return input;
}

void assertPhysicalUnknown(const output::OutputStateStore& store, output::OutputEndpointId endpoint) {
  const auto* state = store.find(endpoint);
  assert(state != nullptr);
  assert(state->physical.state == output::PhysicalOutputState::Unknown);
  assert(!state->physical.has_independent_feedback);
}

void runPartialFailureAt(std::size_t failure_index) {
  output::BinaryActuatorPolicy fan;
  output::BinaryActuatorPolicy humidifier;
  auto store = makeStore();
  const auto config = makeConfig(fan, humidifier);
  output::OutputSupervisorResolver resolver(config);
  FakeTransport transport;
  transport.scripted_count = 3U;
  for (std::size_t i = 0U; i < 3U; ++i) {
    transport.scripted[i] = {output::TransportStatus::Completed, output::TransportError::None};
  }
  transport.scripted[failure_index] = {output::TransportStatus::Failed,
                                       output::TransportError::IoFailure};
  output::OutputSupervisorExecutor executor(transport, store, config);
  assert(executor.valid());

  output::OutputSupervisorResolution resolution{};
  assert(resolver.resolve(allOnInput(1'000U), store, resolution));
  assert(resolution.plan.size == 3U);
  assert(resolution.plan.steps[0].endpoint == kFan);
  assert(resolution.plan.steps[1].endpoint == kLamp);
  assert(resolution.plan.steps[2].endpoint == kHumidifier);

  output::ExecutionReport report{};
  assert(executor.execute(resolution, 1'005U, report));
  assert(transport.sent_count == 3U);
  assert(report.size == 3U);
  for (std::size_t i = 0U; i < 3U; ++i) {
    assert(report.steps[i].command.endpoint == resolution.plan.steps[i].endpoint);
    assert(report.steps[i].physical == output::PhysicalOutputState::Unknown);
    const auto expected_status = i == failure_index ? output::TransportStatus::Failed
                                                     : output::TransportStatus::Completed;
    assert(report.steps[i].transport.status == expected_status);
    const auto* state = store.find(resolution.plan.steps[i].endpoint);
    assert(state != nullptr);
    assert(state->has_resolved);
    assert(state->has_attempt);
    assert(state->last_attempt_ms == 1'005U);
    assert(state->last_transport.status == expected_status);
    assert(state->has_successful_command == (i != failure_index));
    assertPhysicalUnknown(store, resolution.plan.steps[i].endpoint);
  }

  if (failure_index == 0U) {
    assert(!fan.known());
  } else {
    assert(fan.known() && fan.on());
  }
  if (failure_index == 2U) {
    assert(!humidifier.known());
  } else {
    assert(humidifier.known() && humidifier.on());
  }
}

void testFirstMiddleLastFailureRemainExplicitAndDoNotStopPlan() {
  runPartialFailureAt(0U);
  runPartialFailureAt(1U);
  runPartialFailureAt(2U);
}

void testFailedPolicyCommandDoesNotAdvanceAndCanRetry() {
  output::BinaryActuatorPolicy fan;
  output::BinaryActuatorPolicy humidifier;
  auto store = makeStore();
  const auto config = makeConfig(fan, humidifier);
  output::OutputSupervisorResolver resolver(config);
  FakeTransport transport;
  transport.scripted_count = 2U;
  transport.scripted[0] = {output::TransportStatus::Failed, output::TransportError::IoFailure};
  transport.scripted[1] = {output::TransportStatus::Completed, output::TransportError::None};
  output::OutputSupervisorExecutor executor(transport, store, config);

  output::OutputSupervisorCycleInput input{};
  input.monotonic_ms = 2'000U;
  input.control.metadata.sequence = 20U;
  setIntent(input.control.endpoints[0], kFan, 1.0F);

  output::OutputSupervisorResolution first{};
  assert(resolver.resolve(input, store, first));
  assert(first.plan.size == 1U);
  const auto generation_before = fan.generation();
  output::ExecutionReport report{};
  assert(executor.execute(first, 2'001U, report));
  assert(report.steps[0].transport.status == output::TransportStatus::Failed);
  assert(!fan.known());
  assert(fan.generation() == generation_before);

  input.monotonic_ms = 2'100U;
  output::OutputSupervisorResolution retry{};
  assert(resolver.resolve(input, store, retry));
  assert(retry.plan.size == 1U);
  assert(executor.execute(retry, 2'101U, report));
  assert(report.steps[0].transport.status == output::TransportStatus::Completed);
  assert(fan.known() && fan.on());
  assert(fan.generation() == generation_before + 1U);
}

void testSuccessfulCommandsDeduplicateOnNextResolution() {
  output::BinaryActuatorPolicy fan;
  output::BinaryActuatorPolicy humidifier;
  auto store = makeStore();
  const auto config = makeConfig(fan, humidifier);
  output::OutputSupervisorResolver resolver(config);
  FakeTransport transport;
  output::OutputSupervisorExecutor executor(transport, store, config);

  auto input = allOnInput(3'000U);
  output::OutputSupervisorResolution first{};
  assert(resolver.resolve(input, store, first));
  assert(first.plan.size == 3U);
  output::ExecutionReport report{};
  assert(executor.execute(first, 3'001U, report));
  assert(transport.sent_count == 3U);

  input.monotonic_ms = 3'100U;
  output::OutputSupervisorResolution repeated{};
  assert(resolver.resolve(input, store, repeated));
  assert(repeated.plan.size == 0U);
  assert(executor.execute(repeated, 3'101U, report));
  assert(report.size == 0U);
  assert(transport.sent_count == 3U);
}

void testStalePolicyProposalFailsBeforeTransport() {
  output::BinaryActuatorPolicy fan;
  output::BinaryActuatorPolicy humidifier;
  auto store = makeStore();
  const auto config = makeConfig(fan, humidifier);
  output::OutputSupervisorResolver resolver(config);
  FakeTransport transport;
  output::OutputSupervisorExecutor executor(transport, store, config);

  output::OutputSupervisorCycleInput input{};
  input.monotonic_ms = 4'000U;
  setIntent(input.control.endpoints[0], kFan, 1.0F);
  output::OutputSupervisorResolution resolution{};
  assert(resolver.resolve(input, store, resolution));
  assert(resolution.plan.size == 1U);

  fan.synchronize(output::BinaryOutputState::Off, 4'001U);
  output::ExecutionReport report{};
  assert(!executor.execute(resolution, 4'002U, report));
  assert(report.size == 0U);
  assert(transport.sent_count == 0U);
}

void testTransportNeverOverwritesIndependentPhysicalFeedback() {
  output::BinaryActuatorPolicy fan;
  output::BinaryActuatorPolicy humidifier;
  auto store = makeStore();
  assert(store.recordPhysicalObservation(kLamp, output::PhysicalOutputState::On, 5'000U, 91U));
  const auto config = makeConfig(fan, humidifier);
  output::OutputSupervisorResolver resolver(config);
  FakeTransport transport;
  output::OutputSupervisorExecutor executor(transport, store, config);

  output::OutputSupervisorCycleInput input{};
  input.monotonic_ms = 5'100U;
  input.schedule.metadata.sequence = 92U;
  setIntent(input.schedule.endpoints[0], kLamp, 0.0F);
  output::OutputSupervisorResolution resolution{};
  assert(resolver.resolve(input, store, resolution));
  assert(resolution.plan.size == 1U);

  output::ExecutionReport report{};
  assert(executor.execute(resolution, 5'101U, report));
  assert(report.size == 1U);
  assert(report.steps[0].physical == output::PhysicalOutputState::Unknown);
  const auto* lamp = store.find(kLamp);
  assert(lamp != nullptr);
  assert(lamp->has_successful_command);
  assert(lamp->last_successful_command.state == output::BinaryOutputState::Off);
  assert(lamp->physical.has_independent_feedback);
  assert(lamp->physical.state == output::PhysicalOutputState::On);
  assert(lamp->physical.observed_ms == 5'000U);
  assert(lamp->physical.sequence == 91U);
}

} // namespace

int main() {
  testFirstMiddleLastFailureRemainExplicitAndDoNotStopPlan();
  testFailedPolicyCommandDoesNotAdvanceAndCanRetry();
  testSuccessfulCommandsDeduplicateOnNextResolution();
  testStalePolicyProposalFailsBeforeTransport();
  testTransportNeverOverwritesIndependentPhysicalFeedback();
  return 0;
}
'''

Path('src/climate/output/OutputSupervisorExecutor.h').write_text(HEADER)
Path('src/climate/output/OutputSupervisorExecutor.cpp').write_text(SOURCE)
Path('test/test_output_supervisor_executor/test_main.cpp').parent.mkdir(parents=True, exist_ok=True)
Path('test/test_output_supervisor_executor/test_main.cpp').write_text(TEST)

src_cmake = Path('src/CMakeLists.txt')
text = src_cmake.read_text()
anchor = '    "climate/output/OutputSupervisorResolver.cpp"\n'
assert anchor in text and 'OutputSupervisorExecutor.cpp' not in text
text = text.replace(anchor, anchor + '    "climate/output/OutputSupervisorExecutor.cpp"\n')
src_cmake.write_text(text)

host = Path('test/host/CMakeLists.txt')
text = host.read_text()
anchor = '''target_compile_options(output_supervisor_resolver_tests PRIVATE -Wall -Wextra -Wpedantic)\n\n'''
block = '''add_executable(\n  output_supervisor_executor_tests\n  "${PROJECT_ROOT}/test/test_output_supervisor_executor/test_main.cpp"\n  "${PROJECT_ROOT}/src/climate/output/OutputSupervisorExecutor.cpp"\n  "${PROJECT_ROOT}/src/climate/output/OutputSupervisorResolver.cpp"\n  "${PROJECT_ROOT}/src/climate/output/BinaryActuatorPolicy.cpp"\n  "${PROJECT_ROOT}/src/climate/output/OutputStateStore.cpp"\n)\ntarget_include_directories(output_supervisor_executor_tests PRIVATE "${PROJECT_ROOT}/src")\ntarget_compile_features(output_supervisor_executor_tests PRIVATE cxx_std_17)\ntarget_compile_options(output_supervisor_executor_tests PRIVATE -Wall -Wextra -Wpedantic)\n\n'''
assert anchor in text and 'output_supervisor_executor_tests' not in text
text = text.replace(anchor, anchor + block)
reg = 'add_test(NAME output_supervisor_resolver_tests COMMAND output_supervisor_resolver_tests)\n'
assert reg in text
text = text.replace(reg, reg + 'add_test(NAME output_supervisor_executor_tests COMMAND output_supervisor_executor_tests)\n')
host.write_text(text)
