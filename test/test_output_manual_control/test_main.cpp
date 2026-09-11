#include "climate/output/control/OutputManualControl.h"

#include <cassert>

namespace {
namespace output = growbox::app::output;

output::OutputPolicyConfig policy() {
  return output::makeSafeDefaultOutputPolicyConfig(1U, 2U, 3U);
}

output::OutputSupervisorLifecycle automaticLifecycle(const output::OutputPolicyConfig& config) {
  output::OutputSupervisorLifecycle lifecycle(config);
  assert(lifecycle.valid());
  assert(lifecycle.apply(output::OutputLifecycleCommand::BeginArming).status ==
         output::OutputLifecycleTransitionStatus::Applied);
  assert(lifecycle.apply(output::OutputLifecycleCommand::ArmingSucceeded).status ==
         output::OutputLifecycleTransitionStatus::Applied);
  assert(lifecycle.mode() == output::SupervisorMode::Automatic);
  return lifecycle;
}

void testRoleMappingAndConsumeOnce() {
  const auto config = policy();
  auto lifecycle = automaticLifecycle(config);
  output::OutputManualControl control(config, lifecycle);
  assert(control.valid());

  const auto report = control.request(output::OutputEndpointRole::ScheduledLight,
                                      output::BinaryOutputState::On, 1234U);
  assert(report.status == output::OutputManualRequestStatus::Accepted);
  assert(report.endpoint == 2U);
  assert(report.sequence != 0U);
  assert(control.pending());

  output::ManualIntent intent{};
  assert(control.consume(intent));
  assert(!control.pending());
  assert(intent.metadata.source == output::OutputSource::Manual);
  assert(intent.metadata.reason == output::OutputReason::ManualRequest);
  assert(intent.metadata.monotonic_ms == 1234U);
  assert(intent.metadata.sequence == report.sequence);
  assert(output::endpointIntentActive(intent.endpoints[0]));
  assert(intent.endpoints[0].endpoint == 2U);
  assert(intent.endpoints[0].level == 1.0F);

  assert(!control.consume(intent));
  assert(!output::endpointIntentActive(intent.endpoints[0]));
}

void testBusyDoesNotReplacePendingCommand() {
  const auto config = policy();
  auto lifecycle = automaticLifecycle(config);
  output::OutputManualControl control(config, lifecycle);
  const auto first =
      control.request(output::OutputEndpointRole::ExhaustFan, output::BinaryOutputState::On, 10U);
  assert(first.status == output::OutputManualRequestStatus::Accepted);
  const auto second =
      control.request(output::OutputEndpointRole::Humidifier, output::BinaryOutputState::Off, 20U);
  assert(second.status == output::OutputManualRequestStatus::Busy);

  output::ManualIntent intent{};
  assert(control.consume(intent));
  assert(intent.endpoints[0].endpoint == 1U);
  assert(intent.endpoints[0].level == 1.0F);
}

void testNonAutomaticModesDenyRequests() {
  const auto config = policy();
  output::OutputSupervisorLifecycle lifecycle(config);
  output::OutputManualControl control(config, lifecycle);
  assert(control.valid());
  auto report = control.request(output::OutputEndpointRole::ScheduledLight,
                                output::BinaryOutputState::On, 1U);
  assert(report.status == output::OutputManualRequestStatus::ModeDenied);
  assert(!control.pending());

  assert(lifecycle.apply(output::OutputLifecycleCommand::BeginArming).status ==
         output::OutputLifecycleTransitionStatus::Applied);
  report = control.request(output::OutputEndpointRole::ScheduledLight,
                           output::BinaryOutputState::On, 2U);
  assert(report.status == output::OutputManualRequestStatus::ModeDenied);

  assert(lifecycle.apply(output::OutputLifecycleCommand::ArmingSucceeded).status ==
         output::OutputLifecycleTransitionStatus::Applied);
  assert(lifecycle.apply(output::OutputLifecycleCommand::DisableAutomation).status ==
         output::OutputLifecycleTransitionStatus::Applied);
  report = control.request(output::OutputEndpointRole::ScheduledLight,
                           output::BinaryOutputState::On, 3U);
  assert(report.status == output::OutputManualRequestStatus::ModeDenied);
}

void testInvalidConfigurationFailsClosed() {
  output::OutputPolicyConfig invalid{};
  output::OutputSupervisorLifecycle lifecycle(invalid);
  output::OutputManualControl control(invalid, lifecycle);
  assert(!control.valid());
  const auto report =
      control.request(output::OutputEndpointRole::ExhaustFan, output::BinaryOutputState::On, 0U);
  assert(report.status == output::OutputManualRequestStatus::InvalidConfiguration);
}

void testSequenceAdvancesAcrossConsumedRequests() {
  const auto config = policy();
  auto lifecycle = automaticLifecycle(config);
  output::OutputManualControl control(config, lifecycle);
  const auto first =
      control.request(output::OutputEndpointRole::Humidifier, output::BinaryOutputState::On, 1U);
  output::ManualIntent intent{};
  assert(control.consume(intent));
  const auto second =
      control.request(output::OutputEndpointRole::Humidifier, output::BinaryOutputState::Off, 2U);
  assert(second.status == output::OutputManualRequestStatus::Accepted);
  assert(second.sequence > first.sequence);
  assert(control.consume(intent));
  assert(intent.endpoints[0].endpoint == 3U);
  assert(intent.endpoints[0].level == 0.0F);
}

} // namespace

int main() {
  testRoleMappingAndConsumeOnce();
  testBusyDoesNotReplacePendingCommand();
  testNonAutomaticModesDenyRequests();
  testInvalidConfigurationFailsClosed();
  testSequenceAdvancesAcrossConsumedRequests();
  return 0;
}
