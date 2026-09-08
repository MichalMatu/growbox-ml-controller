from pathlib import Path

header = Path('src/climate/output/ClimateOutputSupervisorSink.h')
header.write_text(r'''#pragma once

#include "climate/ClimateSemanticOutput.h"
#include "climate/output/OutputSupervisorExecutor.h"

#include <cstdint>

namespace growbox::app::climate_io {

struct ClimateOutputSupervisorCycleContext {
  ::growbox::app::output::SupervisorMode mode =
      ::growbox::app::output::SupervisorMode::Automatic;
  ::growbox::app::output::ScheduleIntent schedule{};
  ::growbox::app::output::ManualIntent manual{};
  ::growbox::app::output::SafetyEnvelope safety{};
};

class ClimateOutputSupervisorSink final : public ::growbox::climate::ClimateActuatorSink {
public:
  ClimateOutputSupervisorSink(
      ClimateSemanticOutputConfig climate_config,
      ::growbox::app::output::OutputSupervisorResolver& resolver,
      ::growbox::app::output::OutputSupervisorExecutor& executor,
      ::growbox::app::output::OutputStateStore& state_store,
      ::growbox::climate::ClimateActuatorSink* fail_safe_fallback = nullptr) noexcept;

  bool valid() const noexcept;
  void setCycleContext(const ClimateOutputSupervisorCycleContext& context) noexcept {
    context_ = context;
  }

  bool apply(const ::growbox::climate::ClimatePolicyRequest& request,
             std::uint64_t monotonic_ms) noexcept override;
  bool applyAndReport(const ::growbox::climate::ClimatePolicyRequest& request,
                      std::uint64_t monotonic_ms,
                      ::growbox::climate::ClimatePolicyRequest& executed_projection) noexcept override;
  bool applyFailSafeOff(std::uint64_t monotonic_ms) noexcept override;

  const ::growbox::app::output::OutputSupervisorResolution& lastResolution() const noexcept {
    return last_resolution_;
  }
  const ::growbox::app::output::ExecutionReport& lastReport() const noexcept {
    return last_report_;
  }

private:
  static float roleLevel(const ::growbox::climate::ClimatePolicyRequest& request,
                         ClimateActuatorRole role) noexcept;
  static void setRoleLevel(::growbox::climate::ClimatePolicyRequest& request,
                           ClimateActuatorRole role, float level) noexcept;
  static bool reportTransportCompleted(
      const ::growbox::app::output::ExecutionReport& report) noexcept;

  bool buildControlIntent(const ::growbox::climate::ClimatePolicyRequest& request,
                          std::uint64_t monotonic_ms,
                          ::growbox::app::output::ControlIntent& intent) noexcept;
  bool executeCycle(const ::growbox::app::output::ControlIntent& control,
                    std::uint64_t monotonic_ms, bool& transport_completed) noexcept;
  bool projectExecutedClimate(
      ::growbox::climate::ClimatePolicyRequest& projection) const noexcept;
  std::uint64_t nextSequence() noexcept;

  ClimateSemanticOutputConfig climate_config_{};
  ClimateSemanticOutputConfigStatus config_status_{ClimateSemanticOutputConfigStatus::Ok};
  ::growbox::app::output::OutputSupervisorResolver& resolver_;
  ::growbox::app::output::OutputSupervisorExecutor& executor_;
  ::growbox::app::output::OutputStateStore& state_store_;
  ::growbox::climate::ClimateActuatorSink* fail_safe_fallback_{nullptr};
  ClimateOutputSupervisorCycleContext context_{};
  ::growbox::app::output::OutputSupervisorResolution last_resolution_{};
  ::growbox::app::output::ExecutionReport last_report_{};
  std::uint64_t sequence_{0U};
};

} // namespace growbox::app::climate_io
''')

source = Path('src/climate/output/ClimateOutputSupervisorSink.cpp')
source.write_text(r'''#include "climate/output/ClimateOutputSupervisorSink.h"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstddef>

namespace growbox::app::climate_io {
namespace {

constexpr std::array<ClimateActuatorRole, kClimateActuatorRoleCount> kClimateRoles{
    ClimateActuatorRole::Heater,       ClimateActuatorRole::Cooler,
    ClimateActuatorRole::ExhaustFan,   ClimateActuatorRole::Humidifier,
    ClimateActuatorRole::Dehumidifier, ClimateActuatorRole::Co2Doser,
};

float normalizedLevel(float value) noexcept {
  return std::clamp(value, 0.0F, 1.0F);
}

} // namespace

ClimateOutputSupervisorSink::ClimateOutputSupervisorSink(
    ClimateSemanticOutputConfig climate_config,
    ::growbox::app::output::OutputSupervisorResolver& resolver,
    ::growbox::app::output::OutputSupervisorExecutor& executor,
    ::growbox::app::output::OutputStateStore& state_store,
    ::growbox::climate::ClimateActuatorSink* fail_safe_fallback) noexcept
    : climate_config_(climate_config),
      config_status_(validateClimateSemanticOutputConfig(climate_config_)), resolver_(resolver),
      executor_(executor), state_store_(state_store), fail_safe_fallback_(fail_safe_fallback) {}

bool ClimateOutputSupervisorSink::valid() const noexcept {
  return config_status_ == ClimateSemanticOutputConfigStatus::Ok && resolver_.valid() &&
         executor_.valid() && state_store_.valid();
}

float ClimateOutputSupervisorSink::roleLevel(
    const ::growbox::climate::ClimatePolicyRequest& request,
    ClimateActuatorRole role) noexcept {
  switch (role) {
  case ClimateActuatorRole::Heater:
    return request.heater;
  case ClimateActuatorRole::Cooler:
    return request.cooler;
  case ClimateActuatorRole::ExhaustFan:
    return request.exhaust_fan;
  case ClimateActuatorRole::Humidifier:
    return request.humidifier;
  case ClimateActuatorRole::Dehumidifier:
    return request.dehumidifier;
  case ClimateActuatorRole::Co2Doser:
    return request.co2_doser;
  }
  return 0.0F;
}

void ClimateOutputSupervisorSink::setRoleLevel(
    ::growbox::climate::ClimatePolicyRequest& request, ClimateActuatorRole role,
    float level) noexcept {
  switch (role) {
  case ClimateActuatorRole::Heater:
    request.heater = level;
    return;
  case ClimateActuatorRole::Cooler:
    request.cooler = level;
    return;
  case ClimateActuatorRole::ExhaustFan:
    request.exhaust_fan = level;
    return;
  case ClimateActuatorRole::Humidifier:
    request.humidifier = level;
    return;
  case ClimateActuatorRole::Dehumidifier:
    request.dehumidifier = level;
    return;
  case ClimateActuatorRole::Co2Doser:
    request.co2_doser = level;
    return;
  }
}

std::uint64_t ClimateOutputSupervisorSink::nextSequence() noexcept {
  ++sequence_;
  if (sequence_ == 0U) {
    ++sequence_;
  }
  return sequence_;
}

bool ClimateOutputSupervisorSink::buildControlIntent(
    const ::growbox::climate::ClimatePolicyRequest& request, std::uint64_t monotonic_ms,
    ::growbox::app::output::ControlIntent& intent) noexcept {
  intent = {};
  if (config_status_ != ClimateSemanticOutputConfigStatus::Ok) {
    return false;
  }

  std::size_t intent_index = 0U;
  for (const auto role : kClimateRoles) {
    const float raw_level = roleLevel(request, role);
    if (!std::isfinite(raw_level)) {
      intent = {};
      return false;
    }
    const float level = normalizedLevel(raw_level);
    const std::size_t role_index = climateRoleIndex(role);
    if (role_index >= climate_config_.roles.size()) {
      intent = {};
      return false;
    }
    const auto& mapping = climate_config_.roles[role_index];
    if (!mapping.enabled) {
      if (level != 0.0F) {
        intent = {};
        return false;
      }
      continue;
    }
    if (mapping.endpoint == kUnmappedClimateEndpoint || intent_index >= intent.endpoints.size() ||
        !::growbox::app::output::setEndpointIntent(intent.endpoints[intent_index], mapping.endpoint,
                                                   level)) {
      intent = {};
      return false;
    }
    ++intent_index;
  }

  intent.metadata.sequence = nextSequence();
  intent.metadata.monotonic_ms = monotonic_ms;
  intent.metadata.source = ::growbox::app::output::OutputSource::Climate;
  intent.metadata.reason = ::growbox::app::output::OutputReason::ClimateDecision;
  return true;
}

bool ClimateOutputSupervisorSink::reportTransportCompleted(
    const ::growbox::app::output::ExecutionReport& report) noexcept {
  for (std::size_t index = 0U; index < report.size; ++index) {
    if (report.steps[index].transport.status !=
        ::growbox::app::output::TransportStatus::Completed) {
      return false;
    }
  }
  return true;
}

bool ClimateOutputSupervisorSink::executeCycle(
    const ::growbox::app::output::ControlIntent& control, std::uint64_t monotonic_ms,
    bool& transport_completed) noexcept {
  transport_completed = false;
  last_resolution_ = {};
  last_report_ = {};
  if (!valid()) {
    return false;
  }

  ::growbox::app::output::OutputSupervisorCycleInput cycle{};
  cycle.mode = context_.mode;
  cycle.monotonic_ms = monotonic_ms;
  cycle.control = control;
  cycle.schedule = context_.schedule;
  cycle.manual = context_.manual;
  cycle.safety = context_.safety;

  if (!resolver_.resolve(cycle, state_store_, last_resolution_)) {
    last_resolution_ = {};
    return false;
  }
  if (!executor_.execute(last_resolution_, monotonic_ms, last_report_)) {
    last_report_ = {};
    return false;
  }
  transport_completed = reportTransportCompleted(last_report_);
  return true;
}

bool ClimateOutputSupervisorSink::projectExecutedClimate(
    ::growbox::climate::ClimatePolicyRequest& projection) const noexcept {
  projection = {};
  if (config_status_ != ClimateSemanticOutputConfigStatus::Ok || !state_store_.valid()) {
    return false;
  }

  for (const auto role : kClimateRoles) {
    const std::size_t role_index = climateRoleIndex(role);
    if (role_index >= climate_config_.roles.size()) {
      projection = {};
      return false;
    }
    const auto& mapping = climate_config_.roles[role_index];
    if (!mapping.enabled) {
      continue;
    }
    const auto* state = state_store_.find(mapping.endpoint);
    if (state == nullptr) {
      projection = {};
      return false;
    }
    float level = 0.0F;
    if (state->has_successful_command) {
      level = state->last_successful_command.state ==
                      ::growbox::app::output::BinaryOutputState::On
                  ? 1.0F
                  : 0.0F;
    }
    setRoleLevel(projection, role, level);
  }
  return true;
}

bool ClimateOutputSupervisorSink::apply(
    const ::growbox::climate::ClimatePolicyRequest& request,
    std::uint64_t monotonic_ms) noexcept {
  ::growbox::climate::ClimatePolicyRequest projection{};
  return applyAndReport(request, monotonic_ms, projection);
}

bool ClimateOutputSupervisorSink::applyAndReport(
    const ::growbox::climate::ClimatePolicyRequest& request, std::uint64_t monotonic_ms,
    ::growbox::climate::ClimatePolicyRequest& executed_projection) noexcept {
  executed_projection = {};
  ::growbox::app::output::ControlIntent control{};
  if (!buildControlIntent(request, monotonic_ms, control)) {
    return false;
  }

  bool transport_completed = false;
  if (!executeCycle(control, monotonic_ms, transport_completed)) {
    return false;
  }
  if (!projectExecutedClimate(executed_projection)) {
    executed_projection = {};
    return false;
  }
  return transport_completed;
}

bool ClimateOutputSupervisorSink::applyFailSafeOff(std::uint64_t monotonic_ms) noexcept {
  last_resolution_ = {};
  last_report_ = {};
  if (fail_safe_fallback_ == nullptr) {
    return false;
  }
  return fail_safe_fallback_->applyFailSafeOff(monotonic_ms);
}

} // namespace growbox::app::climate_io
''')

host = Path('test/host/CMakeLists.txt')
text = host.read_text()
needle = '''target_compile_features(output_supervisor_executor_tests PRIVATE cxx_std_17)\ntarget_compile_options(output_supervisor_executor_tests PRIVATE -Wall -Wextra -Wpedantic)\n\n'''
addition = needle + '''add_executable(\n  climate_output_supervisor_sink_tests\n  "${PROJECT_ROOT}/test/test_climate_output_supervisor_sink/test_main.cpp"\n  "${PROJECT_ROOT}/src/climate/output/ClimateOutputSupervisorSink.cpp"\n  "${PROJECT_ROOT}/src/climate/output/OutputSupervisorExecutor.cpp"\n  "${PROJECT_ROOT}/src/climate/output/OutputSupervisorResolver.cpp"\n  "${PROJECT_ROOT}/src/climate/output/BinaryActuatorPolicy.cpp"\n  "${PROJECT_ROOT}/src/climate/output/OutputStateStore.cpp"\n  "${PROJECT_ROOT}/src/climate/ClimateSemanticOutput.cpp"\n)\ntarget_include_directories(\n  climate_output_supervisor_sink_tests\n  PRIVATE\n    "${PROJECT_ROOT}/src"\n    "${PROJECT_ROOT}/lib/environment_control/src"\n)\ntarget_compile_features(climate_output_supervisor_sink_tests PRIVATE cxx_std_17)\ntarget_compile_options(climate_output_supervisor_sink_tests PRIVATE -Wall -Wextra -Wpedantic)\n\n'''
assert needle in text
text = text.replace(needle, addition, 1)
needle = 'add_test(NAME output_supervisor_executor_tests COMMAND output_supervisor_executor_tests)\n'
addition = needle + 'add_test(NAME climate_output_supervisor_sink_tests COMMAND climate_output_supervisor_sink_tests)\n'
assert needle in text
text = text.replace(needle, addition, 1)
host.write_text(text)

source_cmake = Path('src/CMakeLists.txt')
text = source_cmake.read_text()
needle = '    "climate/output/OutputSupervisorExecutor.cpp"\n'
addition = needle + '    "climate/output/ClimateOutputSupervisorSink.cpp"\n'
assert needle in text
text = text.replace(needle, addition, 1)
source_cmake.write_text(text)

test = Path('test/test_climate_output_supervisor_sink/test_main.cpp')
test.parent.mkdir(parents=True, exist_ok=True)
test.write_text(r'''#include "climate/output/ClimateOutputSupervisorSink.h"

#include <array>
#include <cassert>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <limits>

namespace {

namespace climate_io = growbox::app::climate_io;
namespace climate = growbox::climate;
namespace output = growbox::app::output;

constexpr output::OutputEndpointId kFan = 1U;
constexpr output::OutputEndpointId kLamp = 2U;
constexpr output::OutputEndpointId kHumidifier = 3U;

class FakeTransport final : public output::OutputTransport {
public:
  std::array<output::TxResult, 16U> scripted{};
  std::array<output::OutputCommand, 16U> sent{};
  std::size_t scripted_count{0U};
  std::size_t scripted_index{0U};
  std::size_t sent_count{0U};

  output::TxResult send(const output::OutputCommand& command) noexcept override {
    assert(sent_count < sent.size());
    sent[sent_count++] = command;
    if (scripted_index < scripted_count) {
      return scripted[scripted_index++];
    }
    return {output::TransportStatus::Completed, output::TransportError::None};
  }
};

class RecordingFailSafeSink final : public climate::ClimateActuatorSink {
public:
  bool apply(const climate::ClimatePolicyRequest&, std::uint64_t) noexcept override {
    ++apply_calls;
    return true;
  }

  bool applyFailSafeOff(std::uint64_t monotonic_ms) noexcept override {
    ++fail_safe_calls;
    last_fail_safe_ms = monotonic_ms;
    return fail_safe_result;
  }

  bool fail_safe_result{true};
  std::size_t apply_calls{0U};
  std::size_t fail_safe_calls{0U};
  std::uint64_t last_fail_safe_ms{0U};
};

output::BinaryActuatorPolicy makePolicy(std::uint64_t min_on_ms = 0U,
                                        std::uint64_t min_off_ms = 0U) {
  output::BinaryActuatorPolicyConfig config{};
  config.on_threshold = 0.10F;
  config.off_threshold = 0.03F;
  config.min_on_ms = min_on_ms;
  config.min_off_ms = min_off_ms;
  return output::BinaryActuatorPolicy(config);
}

output::OutputStateStore makeStore() {
  output::OutputStateStore store;
  const std::array<output::OutputEndpointId, output::kOutputEndpointCapacity> endpoints{
      kFan, kLamp, kHumidifier};
  assert(store.configure(endpoints, endpoints.size()));
  return store;
}

output::OutputSupervisorResolverConfig makeSupervisorConfig(
    output::BinaryActuatorPolicy& fan, output::BinaryActuatorPolicy& humidifier) {
  output::OutputSupervisorResolverConfig config{};
  config.endpoints[0] = {kFan, &fan};
  config.endpoints[1] = {kLamp, nullptr};
  config.endpoints[2] = {kHumidifier, &humidifier};
  config.count = 3U;
  return config;
}

climate_io::ClimateSemanticOutputConfig makeClimateConfig() {
  climate_io::ClimateSemanticOutputConfig config{};
  assert(climate_io::bindClimateRole(config, climate_io::ClimateActuatorRole::ExhaustFan, kFan));
  assert(climate_io::bindClimateRole(config, climate_io::ClimateActuatorRole::Humidifier,
                                    kHumidifier));
  assert(climate_io::validateClimateSemanticOutputConfig(config) ==
         climate_io::ClimateSemanticOutputConfigStatus::Ok);
  return config;
}

climate_io::ClimateOutputSupervisorCycleContext scheduleContext(bool lamp_on) {
  climate_io::ClimateOutputSupervisorCycleContext context{};
  context.schedule.metadata.sequence = 70U;
  context.schedule.metadata.source = output::OutputSource::Schedule;
  context.schedule.metadata.reason = output::OutputReason::ScheduleRequest;
  assert(output::setEndpointIntent(context.schedule.endpoints[0], kLamp, lamp_on ? 1.0F : 0.0F));
  return context;
}

climate::ClimatePolicyRequest request(float fan, float humidifier) {
  climate::ClimatePolicyRequest value{};
  value.exhaust_fan = fan;
  value.humidifier = humidifier;
  return value;
}

bool near(float left, float right) {
  return std::fabs(left - right) <= 1.0e-6F;
}

void assertPhysicalUnknown(const output::OutputStateStore& store,
                           output::OutputEndpointId endpoint) {
  const auto* state = store.find(endpoint);
  assert(state != nullptr);
  assert(state->physical.state == output::PhysicalOutputState::Unknown);
  assert(!state->physical.has_independent_feedback);
}

void testCompleteClimateRequestUsesOneSupervisorCycleAndProjectsCommandTruth() {
  auto fan = makePolicy();
  auto humidifier = makePolicy();
  auto store = makeStore();
  const auto supervisor_config = makeSupervisorConfig(fan, humidifier);
  output::OutputSupervisorResolver resolver(supervisor_config);
  FakeTransport transport;
  output::OutputSupervisorExecutor executor(transport, store, supervisor_config);
  RecordingFailSafeSink fallback;
  climate_io::ClimateOutputSupervisorSink sink(makeClimateConfig(), resolver, executor, store,
                                                &fallback);
  assert(sink.valid());
  sink.setCycleContext(scheduleContext(true));

  climate::ClimatePolicyRequest projection{};
  assert(sink.applyAndReport(request(1.0F, 1.0F), 1'000U, projection));
  assert(transport.sent_count == 3U);
  assert(transport.sent[0].endpoint == kFan);
  assert(transport.sent[1].endpoint == kLamp);
  assert(transport.sent[2].endpoint == kHumidifier);
  assert(sink.lastReport().size == 3U);
  assert(near(projection.exhaust_fan, 1.0F));
  assert(near(projection.humidifier, 1.0F));
  assert(near(projection.heater, 0.0F));
  assert(near(projection.cooler, 0.0F));
  assert(near(projection.dehumidifier, 0.0F));
  assert(near(projection.co2_doser, 0.0F));
  assertPhysicalUnknown(store, kFan);
  assertPhysicalUnknown(store, kLamp);
  assertPhysicalUnknown(store, kHumidifier);

  assert(store.recordPhysicalObservation(kFan, output::PhysicalOutputState::Off, 1'010U, 1U));
  assert(store.recordPhysicalObservation(kHumidifier, output::PhysicalOutputState::Off, 1'010U, 2U));
  sink.setCycleContext(scheduleContext(true));
  assert(sink.applyAndReport(request(1.0F, 1.0F), 2'000U, projection));
  assert(transport.sent_count == 3U);
  assert(sink.lastReport().size == 0U);
  assert(near(projection.exhaust_fan, 1.0F));
  assert(near(projection.humidifier, 1.0F));
  assert(store.find(kFan)->physical.state == output::PhysicalOutputState::Off);
  assert(store.find(kHumidifier)->physical.state == output::PhysicalOutputState::Off);
}

void testPartialFailureReturnsFalseAndProjectsLastSuccessfulCommands() {
  auto fan = makePolicy();
  auto humidifier = makePolicy();
  auto store = makeStore();
  const auto supervisor_config = makeSupervisorConfig(fan, humidifier);
  output::OutputSupervisorResolver resolver(supervisor_config);
  FakeTransport transport;
  output::OutputSupervisorExecutor executor(transport, store, supervisor_config);
  climate_io::ClimateOutputSupervisorSink sink(makeClimateConfig(), resolver, executor, store);
  sink.setCycleContext(scheduleContext(false));

  climate::ClimatePolicyRequest projection{};
  assert(sink.applyAndReport(request(0.0F, 0.0F), 10'000U, projection));
  assert(transport.sent_count == 3U);
  assert(near(projection.exhaust_fan, 0.0F));
  assert(near(projection.humidifier, 0.0F));

  transport.scripted_count = 2U;
  transport.scripted_index = 0U;
  transport.scripted[0] = {output::TransportStatus::Failed, output::TransportError::IoFailure};
  transport.scripted[1] = {output::TransportStatus::Completed, output::TransportError::None};
  sink.setCycleContext(scheduleContext(false));
  assert(!sink.applyAndReport(request(1.0F, 1.0F), 20'000U, projection));
  assert(sink.lastReport().size == 2U);
  assert(sink.lastReport().steps[0].command.endpoint == kFan);
  assert(sink.lastReport().steps[0].transport.status == output::TransportStatus::Failed);
  assert(sink.lastReport().steps[1].command.endpoint == kHumidifier);
  assert(sink.lastReport().steps[1].transport.status == output::TransportStatus::Completed);
  assert(near(projection.exhaust_fan, 0.0F));
  assert(near(projection.humidifier, 1.0F));
  assert(store.find(kFan)->last_successful_command.state == output::BinaryOutputState::Off);
  assert(store.find(kHumidifier)->last_successful_command.state == output::BinaryOutputState::On);
  assertPhysicalUnknown(store, kFan);
  assertPhysicalUnknown(store, kHumidifier);
}

void testDwellHoldReturnsHeldExecutionProjectionWithoutTransport() {
  auto fan = makePolicy(120'000U, 120'000U);
  auto humidifier = makePolicy();
  auto store = makeStore();
  const auto supervisor_config = makeSupervisorConfig(fan, humidifier);
  output::OutputSupervisorResolver resolver(supervisor_config);
  FakeTransport transport;
  output::OutputSupervisorExecutor executor(transport, store, supervisor_config);
  climate_io::ClimateOutputSupervisorSink sink(makeClimateConfig(), resolver, executor, store);
  sink.setCycleContext(scheduleContext(false));

  climate::ClimatePolicyRequest projection{};
  assert(sink.applyAndReport(request(0.0F, 0.0F), 100'000U, projection));
  const std::size_t after_initial = transport.sent_count;
  assert(after_initial == 3U);

  sink.setCycleContext(scheduleContext(false));
  assert(sink.applyAndReport(request(1.0F, 0.0F), 100'001U, projection));
  assert(transport.sent_count == after_initial);
  assert(sink.lastReport().size == 0U);
  assert(near(projection.exhaust_fan, 0.0F));
  assert(fan.dwellHoldCount() == 1U);
}

void testSafetyContextOverridesClimateWithoutChangingProjectionMeaning() {
  auto fan = makePolicy();
  auto humidifier = makePolicy();
  auto store = makeStore();
  const auto supervisor_config = makeSupervisorConfig(fan, humidifier);
  output::OutputSupervisorResolver resolver(supervisor_config);
  FakeTransport transport;
  output::OutputSupervisorExecutor executor(transport, store, supervisor_config);
  climate_io::ClimateOutputSupervisorSink sink(makeClimateConfig(), resolver, executor, store);

  auto context = scheduleContext(true);
  context.safety.metadata.sequence = 90U;
  context.safety.metadata.source = output::OutputSource::Safety;
  context.safety.metadata.reason = output::OutputReason::ThermalSafety;
  assert(output::setSafetyConstraint(context.safety.endpoints[0], kFan,
                                     output::SafetyConstraint::ForceOn,
                                     output::OutputReason::ThermalSafety));
  assert(output::setSafetyConstraint(context.safety.endpoints[1], kLamp,
                                     output::SafetyConstraint::ForceOff,
                                     output::OutputReason::ThermalSafety));
  sink.setCycleContext(context);

  climate::ClimatePolicyRequest projection{};
  assert(sink.applyAndReport(request(0.0F, 0.0F), 30'000U, projection));
  assert(transport.sent_count == 3U);
  assert(transport.sent[0].endpoint == kFan);
  assert(transport.sent[0].state == output::BinaryOutputState::On);
  assert(transport.sent[1].endpoint == kLamp);
  assert(transport.sent[1].state == output::BinaryOutputState::Off);
  assert(near(projection.exhaust_fan, 1.0F));
  assert(near(projection.humidifier, 0.0F));
}

void testRejectsUnsupportedOrNonFiniteClimateRequestBeforeTransport() {
  auto fan = makePolicy();
  auto humidifier = makePolicy();
  auto store = makeStore();
  const auto supervisor_config = makeSupervisorConfig(fan, humidifier);
  output::OutputSupervisorResolver resolver(supervisor_config);
  FakeTransport transport;
  output::OutputSupervisorExecutor executor(transport, store, supervisor_config);
  climate_io::ClimateOutputSupervisorSink sink(makeClimateConfig(), resolver, executor, store);

  climate::ClimatePolicyRequest projection{};
  auto unsupported = request(0.0F, 0.0F);
  unsupported.heater = 0.2F;
  assert(!sink.applyAndReport(unsupported, 40'000U, projection));
  assert(transport.sent_count == 0U);

  auto invalid = request(0.0F, 0.0F);
  invalid.exhaust_fan = std::numeric_limits<float>::quiet_NaN();
  assert(!sink.applyAndReport(invalid, 40'001U, projection));
  assert(transport.sent_count == 0U);
}

void testExceptionalFailSafeRemainsExplicitLegacyFallbackDebt() {
  auto fan = makePolicy();
  auto humidifier = makePolicy();
  auto store = makeStore();
  const auto supervisor_config = makeSupervisorConfig(fan, humidifier);
  output::OutputSupervisorResolver resolver(supervisor_config);
  FakeTransport transport;
  output::OutputSupervisorExecutor executor(transport, store, supervisor_config);
  RecordingFailSafeSink fallback;
  climate_io::ClimateOutputSupervisorSink sink(makeClimateConfig(), resolver, executor, store,
                                                &fallback);

  assert(sink.applyFailSafeOff(50'000U));
  assert(fallback.fail_safe_calls == 1U);
  assert(fallback.last_fail_safe_ms == 50'000U);
  assert(fallback.apply_calls == 0U);
  assert(transport.sent_count == 0U);
  assert(sink.lastReport().size == 0U);

  climate_io::ClimateOutputSupervisorSink no_fallback(makeClimateConfig(), resolver, executor,
                                                       store, nullptr);
  assert(!no_fallback.applyFailSafeOff(50'001U));
}

} // namespace

int main() {
  testCompleteClimateRequestUsesOneSupervisorCycleAndProjectsCommandTruth();
  testPartialFailureReturnsFalseAndProjectsLastSuccessfulCommands();
  testDwellHoldReturnsHeldExecutionProjectionWithoutTransport();
  testSafetyContextOverridesClimateWithoutChangingProjectionMeaning();
  testRejectsUnsupportedOrNonFiniteClimateRequestBeforeTransport();
  testExceptionalFailSafeRemainsExplicitLegacyFallbackDebt();
  return 0;
}
''')
