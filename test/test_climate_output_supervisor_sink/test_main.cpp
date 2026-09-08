#include "climate/output/ClimateOutputSupervisorSink.h"

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

output::OutputSupervisorResolverConfig
makeSupervisorConfig(output::BinaryActuatorPolicy& fan, output::BinaryActuatorPolicy& humidifier) {
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
  climate_io::ClimateOutputSupervisorSink sink(makeClimateConfig(), resolver, executor, store);
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
  assert(
      store.recordPhysicalObservation(kHumidifier, output::PhysicalOutputState::Off, 1'010U, 2U));
  sink.setCycleContext(scheduleContext(true));
  assert(sink.applyAndReport(request(1.0F, 1.0F), 2'000U, projection));
  assert(transport.sent_count == 3U);
  assert(sink.lastReport().size == 0U);
  assert(near(projection.exhaust_fan, 1.0F));
  assert(near(projection.humidifier, 1.0F));
  assert(store.find(kFan)->physical.state == output::PhysicalOutputState::Off);
  assert(store.find(kHumidifier)->physical.state == output::PhysicalOutputState::Off);
}

void testExecutionFeedbackIsCompleteCommandTruthAndNotPhysicalAck() {
  auto fan = makePolicy();
  auto humidifier = makePolicy();
  auto store = makeStore();
  const auto supervisor_config = makeSupervisorConfig(fan, humidifier);
  output::OutputSupervisorResolver resolver(supervisor_config);
  FakeTransport transport;
  output::OutputSupervisorExecutor executor(transport, store, supervisor_config);
  climate_io::ClimateOutputSupervisorSink sink(makeClimateConfig(), resolver, executor, store);
  sink.setCycleContext(scheduleContext(true));

  climate::ClimateExecutionProjection execution{};
  assert(sink.applyAndReportExecution(request(1.0F, 1.0F), 5'000U, execution));
  assert(execution.known_mask == climate::ClimateExecutionKnownAll);
  assert(execution.known(climate::ClimateExecutionKnownHeater));
  assert(execution.known(climate::ClimateExecutionKnownCooler));
  assert(execution.known(climate::ClimateExecutionKnownExhaustFan));
  assert(execution.known(climate::ClimateExecutionKnownHumidifier));
  assert(execution.known(climate::ClimateExecutionKnownDehumidifier));
  assert(execution.known(climate::ClimateExecutionKnownCo2Doser));
  assert(near(execution.executed.heater, 0.0F));
  assert(near(execution.executed.cooler, 0.0F));
  assert(near(execution.executed.exhaust_fan, 1.0F));
  assert(near(execution.executed.humidifier, 1.0F));
  assert(near(execution.executed.dehumidifier, 0.0F));
  assert(near(execution.executed.co2_doser, 0.0F));
  assertPhysicalUnknown(store, kFan);
  assertPhysicalUnknown(store, kHumidifier);
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

void testFailSafeOffExecutesThroughSupervisorOnly() {
  auto fan = makePolicy();
  auto humidifier = makePolicy();
  auto store = makeStore();
  const auto supervisor_config = makeSupervisorConfig(fan, humidifier);
  output::OutputSupervisorResolver resolver(supervisor_config);
  FakeTransport transport;
  output::OutputSupervisorExecutor executor(transport, store, supervisor_config);
  climate_io::ClimateOutputSupervisorSink sink(makeClimateConfig(), resolver, executor, store);
  sink.setCycleContext(scheduleContext(true));

  climate::ClimatePolicyRequest projection{};
  assert(sink.applyAndReport(request(1.0F, 1.0F), 50'000U, projection));
  assert(transport.sent_count == 3U);
  assert(store.find(kLamp)->last_successful_command.state == output::BinaryOutputState::On);

  sink.setCycleContext(scheduleContext(true));
  assert(sink.applyFailSafeOff(50'001U));
  assert(transport.sent_count == 5U);
  assert(sink.lastReport().size == 2U);
  assert(transport.sent[3].endpoint == kFan);
  assert(transport.sent[3].state == output::BinaryOutputState::Off);
  assert(transport.sent[3].source == output::OutputSource::Safety);
  assert(transport.sent[3].reason == output::OutputReason::FaultContainment);
  assert(transport.sent[4].endpoint == kHumidifier);
  assert(transport.sent[4].state == output::BinaryOutputState::Off);
  assert(transport.sent[4].source == output::OutputSource::Safety);
  assert(transport.sent[4].reason == output::OutputReason::FaultContainment);
  assert(store.find(kLamp)->last_successful_command.state == output::BinaryOutputState::On);
  assertPhysicalUnknown(store, kFan);
  assertPhysicalUnknown(store, kHumidifier);
}

void testHardSafetyOverridesSupervisorFailSafeOff() {
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
  assert(sink.applyAndReport(request(0.0F, 0.0F), 60'000U, projection));
  assert(transport.sent_count == 3U);

  auto context = scheduleContext(false);
  context.safety.metadata.sequence = 91U;
  context.safety.metadata.source = output::OutputSource::Safety;
  context.safety.metadata.reason = output::OutputReason::ThermalSafety;
  assert(output::setSafetyConstraint(context.safety.endpoints[0], kFan,
                                     output::SafetyConstraint::ForceOn,
                                     output::OutputReason::ThermalSafety));
  sink.setCycleContext(context);

  assert(sink.applyFailSafeOff(60'001U));
  assert(transport.sent_count == 4U);
  assert(sink.lastReport().size == 1U);
  assert(transport.sent[3].endpoint == kFan);
  assert(transport.sent[3].state == output::BinaryOutputState::On);
  assert(transport.sent[3].source == output::OutputSource::Safety);
  assert(transport.sent[3].reason == output::OutputReason::ThermalSafety);
  assert(store.find(kHumidifier)->last_successful_command.state == output::BinaryOutputState::Off);
}

} // namespace

int main() {
  testCompleteClimateRequestUsesOneSupervisorCycleAndProjectsCommandTruth();
  testExecutionFeedbackIsCompleteCommandTruthAndNotPhysicalAck();
  testPartialFailureReturnsFalseAndProjectsLastSuccessfulCommands();
  testDwellHoldReturnsHeldExecutionProjectionWithoutTransport();
  testSafetyContextOverridesClimateWithoutChangingProjectionMeaning();
  testRejectsUnsupportedOrNonFiniteClimateRequestBeforeTransport();
  testFailSafeOffExecutesThroughSupervisorOnly();
  testHardSafetyOverridesSupervisorFailSafeOff();
  return 0;
}
