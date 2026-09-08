from pathlib import Path

header = Path('src/climate/output/OutputSupervisorResolver.h')
header.parent.mkdir(parents=True, exist_ok=True)
header.write_text(r'''#pragma once

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

  bool valid() const noexcept { return valid_; }
  const OutputSupervisorResolverConfig& config() const noexcept { return config_; }

  bool resolve(const OutputSupervisorCycleInput& input, const OutputStateStore& state_store,
               OutputSupervisorResolution& output) noexcept;

private:
  static bool validConfig(const OutputSupervisorResolverConfig& config) noexcept;
  static const EndpointIntent* findIntent(const std::array<EndpointIntent, kOutputEndpointCapacity>& intents,
                                          OutputEndpointId endpoint) noexcept;
  static const SafetyEndpointConstraint*
  findSafetyConstraint(const SafetyEnvelope& safety, OutputEndpointId endpoint) noexcept;
  static BinaryOutputState directBinaryState(NormalizedOutputLevel level) noexcept;
  static bool commandAlreadyCompleted(const OutputStateStore& state_store,
                                      const OutputCommand& command) noexcept;

  OutputSupervisorResolverConfig config_{};
  bool valid_{false};
};

} // namespace growbox::app::output
''')

source = Path('src/climate/output/OutputSupervisorResolver.cpp')
source.write_text(r'''#include "climate/output/OutputSupervisorResolver.h"

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

const SafetyEndpointConstraint* OutputSupervisorResolver::findSafetyConstraint(
    const SafetyEnvelope& safety, OutputEndpointId endpoint) noexcept {
  for (const auto& candidate : safety.endpoints) {
    if (safetyConstraintActive(candidate) && candidate.endpoint == endpoint) {
      return &candidate;
    }
  }
  return nullptr;
}

BinaryOutputState OutputSupervisorResolver::directBinaryState(NormalizedOutputLevel level) noexcept {
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
    resolved.resolved_state = direct_override ? direct_override_state : directBinaryState(selected.level);
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
''')

test = Path('test/test_output_supervisor_resolver/test_main.cpp')
test.parent.mkdir(parents=True, exist_ok=True)
test.write_text(r'''#include "climate/output/OutputSupervisorResolver.h"

#include <array>
#include <cassert>
#include <cstdint>

namespace {

namespace output = growbox::app::output;
constexpr output::OutputEndpointId kFan = 1U;
constexpr output::OutputEndpointId kLamp = 2U;
constexpr output::OutputEndpointId kHumidifier = 3U;

output::OutputStateStore makeStore() {
  output::OutputStateStore store;
  const std::array<output::OutputEndpointId, output::kOutputEndpointCapacity> endpoints{
      kFan, kLamp, kHumidifier};
  assert(store.configure(endpoints, endpoints.size()));
  return store;
}

output::OutputSupervisorResolver makeResolver(output::BinaryActuatorPolicy& fan,
                                              output::BinaryActuatorPolicy& humidifier) {
  output::OutputSupervisorResolverConfig config{};
  config.endpoints[0] = {kFan, &fan};
  config.endpoints[1] = {kLamp, nullptr};
  config.endpoints[2] = {kHumidifier, &humidifier};
  config.count = 3U;
  return output::OutputSupervisorResolver(config);
}

void setIntent(output::EndpointIntent& intent, output::OutputEndpointId endpoint, float level) {
  assert(output::setEndpointIntent(intent, endpoint, level));
}

void testRejectsInvalidConfigurationAndUnconfiguredStore() {
  output::OutputSupervisorResolver invalid({});
  assert(!invalid.valid());

  output::BinaryActuatorPolicy fan;
  output::BinaryActuatorPolicy humidifier;
  auto resolver = makeResolver(fan, humidifier);
  assert(resolver.valid());
  output::OutputStateStore empty_store;
  output::OutputSupervisorResolution resolution{};
  assert(!resolver.resolve({}, empty_store, resolution));
  assert(resolution.plan.size == 0U);
}

void testManualScheduleClimatePrecedence() {
  output::BinaryActuatorPolicy fan;
  output::BinaryActuatorPolicy humidifier;
  auto resolver = makeResolver(fan, humidifier);
  auto store = makeStore();

  output::OutputSupervisorCycleInput input{};
  input.monotonic_ms = 100U;
  setIntent(input.control.endpoints[0], kLamp, 1.0F);
  input.control.metadata.reason = output::OutputReason::ClimateDecision;
  input.control.metadata.sequence = 1U;
  setIntent(input.schedule.endpoints[0], kLamp, 0.0F);
  input.schedule.metadata.reason = output::OutputReason::ScheduleRequest;
  input.schedule.metadata.sequence = 2U;
  setIntent(input.manual.endpoints[0], kLamp, 1.0F);
  input.manual.metadata.reason = output::OutputReason::ManualRequest;
  input.manual.metadata.sequence = 3U;

  output::OutputSupervisorResolution resolution{};
  assert(resolver.resolve(input, store, resolution));
  assert(resolution.plan.size == 1U);
  assert(resolution.plan.steps[0].endpoint == kLamp);
  assert(resolution.plan.steps[0].state == output::BinaryOutputState::On);
  assert(resolution.plan.steps[0].source == output::OutputSource::Manual);
  assert(resolution.plan.steps[0].sequence == 3U);

  input.manual = {};
  assert(resolver.resolve(input, store, resolution));
  assert(resolution.plan.size == 1U);
  assert(resolution.plan.steps[0].state == output::BinaryOutputState::Off);
  assert(resolution.plan.steps[0].source == output::OutputSource::Schedule);

  input.schedule = {};
  assert(resolver.resolve(input, store, resolution));
  assert(resolution.plan.size == 1U);
  assert(resolution.plan.steps[0].state == output::BinaryOutputState::On);
  assert(resolution.plan.steps[0].source == output::OutputSource::Climate);
}

void testSafetyOverridesManualAndCanActWithoutLowerIntent() {
  output::BinaryActuatorPolicyConfig policy_config{};
  policy_config.min_on_ms = 1'000U;
  policy_config.min_off_ms = 1'000U;
  output::BinaryActuatorPolicy fan(policy_config);
  output::BinaryActuatorPolicy humidifier(policy_config);
  auto resolver = makeResolver(fan, humidifier);
  auto store = makeStore();

  output::OutputSupervisorCycleInput input{};
  input.monotonic_ms = 200U;
  setIntent(input.manual.endpoints[0], kLamp, 1.0F);
  input.manual.metadata.sequence = 5U;
  assert(output::setSafetyConstraint(input.safety.endpoints[0], kLamp,
                                     output::SafetyConstraint::ForceOff,
                                     output::OutputReason::ThermalSafety));
  input.safety.metadata.sequence = 9U;

  output::OutputSupervisorResolution resolution{};
  assert(resolver.resolve(input, store, resolution));
  assert(resolution.plan.size == 1U);
  assert(resolution.plan.steps[0].state == output::BinaryOutputState::Off);
  assert(resolution.plan.steps[0].source == output::OutputSource::Safety);
  assert(resolution.plan.steps[0].reason == output::OutputReason::ThermalSafety);
  assert(resolution.plan.steps[0].sequence == 9U);

  input = {};
  input.monotonic_ms = 300U;
  assert(output::setSafetyConstraint(input.safety.endpoints[0], kFan,
                                     output::SafetyConstraint::ForceOn,
                                     output::OutputReason::ThermalSafety));
  input.safety.metadata.sequence = 10U;
  assert(resolver.resolve(input, store, resolution));
  assert(resolution.plan.size == 1U);
  assert(resolution.plan.steps[0].endpoint == kFan);
  assert(resolution.plan.steps[0].state == output::BinaryOutputState::On);
  assert(resolution.endpoints[0].has_policy_proposal);
  assert(resolution.endpoints[0].policy_proposal.bypass_dwell);
  assert(!fan.known());
}

void testInhibitSuppressesLowerCommand() {
  output::BinaryActuatorPolicy fan;
  output::BinaryActuatorPolicy humidifier;
  auto resolver = makeResolver(fan, humidifier);
  auto store = makeStore();

  output::OutputSupervisorCycleInput input{};
  input.monotonic_ms = 400U;
  setIntent(input.schedule.endpoints[0], kLamp, 1.0F);
  assert(output::setSafetyConstraint(input.safety.endpoints[0], kLamp,
                                     output::SafetyConstraint::Inhibit,
                                     output::OutputReason::ThermalSafety));

  output::OutputSupervisorResolution resolution{};
  assert(resolver.resolve(input, store, resolution));
  assert(resolution.plan.size == 0U);
  assert(resolution.endpoints[1].inhibited);
  assert(!resolution.endpoints[1].has_resolved_state);
}

void testBinaryPolicyProposalRequiresExternalCommitAndHonorsDwell() {
  output::BinaryActuatorPolicyConfig policy_config{};
  policy_config.on_threshold = 0.10F;
  policy_config.off_threshold = 0.03F;
  policy_config.min_on_ms = 1'000U;
  policy_config.min_off_ms = 1'000U;
  output::BinaryActuatorPolicy fan(policy_config);
  output::BinaryActuatorPolicy humidifier(policy_config);
  auto resolver = makeResolver(fan, humidifier);
  auto store = makeStore();

  output::OutputSupervisorCycleInput input{};
  input.monotonic_ms = 1'000U;
  setIntent(input.control.endpoints[0], kFan, 0.20F);
  input.control.metadata.sequence = 11U;

  output::OutputSupervisorResolution resolution{};
  assert(resolver.resolve(input, store, resolution));
  assert(resolution.plan.size == 1U);
  assert(resolution.plan.steps[0].state == output::BinaryOutputState::On);
  assert(resolution.endpoints[0].has_policy_proposal);
  assert(!fan.known());
  assert(fan.commit(resolution.endpoints[0].policy_proposal, true));
  assert(fan.on());

  input.monotonic_ms = 1'500U;
  input.control.endpoints[0].level = 0.0F;
  assert(resolver.resolve(input, store, resolution));
  assert(resolution.plan.size == 0U);
  assert(resolution.endpoints[0].held_by_dwell);
  assert(fan.on());

  input.monotonic_ms = 2'000U;
  assert(resolver.resolve(input, store, resolution));
  assert(resolution.plan.size == 1U);
  assert(resolution.plan.steps[0].state == output::BinaryOutputState::Off);
  assert(fan.on());
}

void testDirectEndpointDedupeUsesSuccessfulCommandTruth() {
  output::BinaryActuatorPolicy fan;
  output::BinaryActuatorPolicy humidifier;
  auto resolver = makeResolver(fan, humidifier);
  auto store = makeStore();

  output::OutputCommand completed{};
  completed.endpoint = kLamp;
  completed.state = output::BinaryOutputState::On;
  assert(store.recordAttempt(completed, 10U,
                             {output::TransportStatus::Completed, output::TransportError::None}));

  output::OutputSupervisorCycleInput input{};
  input.monotonic_ms = 20U;
  setIntent(input.schedule.endpoints[0], kLamp, 1.0F);

  output::OutputSupervisorResolution resolution{};
  assert(resolver.resolve(input, store, resolution));
  assert(resolution.plan.size == 0U);
  assert(resolution.endpoints[1].has_resolved_state);
  assert(resolution.endpoints[1].resolved_state == output::BinaryOutputState::On);
  assert(store.find(kLamp)->physical.state == output::PhysicalOutputState::Unknown);
}

void testNonAutomaticModeSuppressesNormalIntentButNotSafety() {
  output::BinaryActuatorPolicy fan;
  output::BinaryActuatorPolicy humidifier;
  auto resolver = makeResolver(fan, humidifier);
  auto store = makeStore();

  output::OutputSupervisorCycleInput input{};
  input.mode = output::SupervisorMode::Disabled;
  input.monotonic_ms = 500U;
  setIntent(input.manual.endpoints[0], kLamp, 1.0F);

  output::OutputSupervisorResolution resolution{};
  assert(resolver.resolve(input, store, resolution));
  assert(resolution.plan.size == 0U);

  assert(output::setSafetyConstraint(input.safety.endpoints[0], kLamp,
                                     output::SafetyConstraint::ForceOff,
                                     output::OutputReason::ThermalSafety));
  assert(resolver.resolve(input, store, resolution));
  assert(resolution.plan.size == 1U);
  assert(resolution.plan.steps[0].source == output::OutputSource::Safety);
  assert(resolution.plan.steps[0].state == output::BinaryOutputState::Off);
}

} // namespace

int main() {
  testRejectsInvalidConfigurationAndUnconfiguredStore();
  testManualScheduleClimatePrecedence();
  testSafetyOverridesManualAndCanActWithoutLowerIntent();
  testInhibitSuppressesLowerCommand();
  testBinaryPolicyProposalRequiresExternalCommitAndHonorsDwell();
  testDirectEndpointDedupeUsesSuccessfulCommandTruth();
  testNonAutomaticModeSuppressesNormalIntentButNotSafety();
  return 0;
}
''')

src_cmake = Path('src/CMakeLists.txt')
text = src_cmake.read_text()
needle = '    "climate/output/BinaryActuatorPolicy.cpp"\n'
assert needle in text
text = text.replace(needle, needle + '    "climate/output/OutputSupervisorResolver.cpp"\n', 1)
src_cmake.write_text(text)

host = Path('test/host/CMakeLists.txt')
text = host.read_text()
marker = '''add_executable(\n  climate_semantic_output_tests\n'''
block = '''add_executable(\n  output_supervisor_resolver_tests\n  "${PROJECT_ROOT}/test/test_output_supervisor_resolver/test_main.cpp"\n  "${PROJECT_ROOT}/src/climate/output/OutputSupervisorResolver.cpp"\n  "${PROJECT_ROOT}/src/climate/output/BinaryActuatorPolicy.cpp"\n  "${PROJECT_ROOT}/src/climate/output/OutputStateStore.cpp"\n)\ntarget_include_directories(output_supervisor_resolver_tests PRIVATE "${PROJECT_ROOT}/src")\ntarget_compile_features(output_supervisor_resolver_tests PRIVATE cxx_std_17)\ntarget_compile_options(output_supervisor_resolver_tests PRIVATE -Wall -Wextra -Wpedantic)\n\n'''
assert marker in text
text = text.replace(marker, block + marker, 1)
add_test_marker = 'add_test(NAME output_types_tests COMMAND output_types_tests)\n'
assert add_test_marker in text
text = text.replace(add_test_marker, add_test_marker + 'add_test(NAME output_supervisor_resolver_tests COMMAND output_supervisor_resolver_tests)\n', 1)
host.write_text(text)
