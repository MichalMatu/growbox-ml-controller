#include "climate/output/OutputPolicyConfig.h"

#include <cassert>
#include <cstdint>

namespace output = growbox::app::output;

namespace {

constexpr output::OutputEndpointId kFan = 1U;
constexpr output::OutputEndpointId kLamp = 2U;
constexpr output::OutputEndpointId kHumidifier = 3U;

output::OutputPolicyConfig defaults() {
  return output::makeSafeDefaultOutputPolicyConfig(kFan, kLamp, kHumidifier);
}

void testSafeDefaults() {
  const auto config = defaults();
  assert(config.version == output::kOutputPolicySchemaVersion);
  assert(config.count == output::kOutputEndpointCapacity);
  assert(config.max_transition_failures == 1U);
  assert(output::validateOutputPolicyConfig(config) == output::OutputPolicyConfigStatus::Ok);

  const auto* fan = output::findOutputPolicyRole(config, output::OutputEndpointRole::ExhaustFan);
  const auto* lamp =
      output::findOutputPolicyRole(config, output::OutputEndpointRole::ScheduledLight);
  const auto* humidifier =
      output::findOutputPolicyRole(config, output::OutputEndpointRole::Humidifier);
  assert(fan != nullptr && fan->endpoint == kFan);
  assert(lamp != nullptr && lamp->endpoint == kLamp);
  assert(humidifier != nullptr && humidifier->endpoint == kHumidifier);
  assert(output::findOutputPolicyEndpoint(config, kLamp) == lamp);

  for (std::size_t event = 0U; event < output::kOutputLifecycleEventCount; ++event) {
    assert(fan->lifecycle[event].action == output::OutputPolicyAction::ForceOff);
    assert(fan->lifecycle[event].order == 1U);
    assert(fan->lifecycle[event].retransmit);
    assert(fan->lifecycle[event].max_retries == 1U);
    assert(humidifier->lifecycle[event].action == output::OutputPolicyAction::ForceOff);
    assert(humidifier->lifecycle[event].order == 2U);
    assert(lamp->lifecycle[event].order == 0U);
  }
  assert(lamp->lifecycle[output::outputLifecycleEventIndex(output::OutputLifecycleEvent::Boot)]
             .action == output::OutputPolicyAction::ForceOff);
  assert(lamp->lifecycle[output::outputLifecycleEventIndex(output::OutputLifecycleEvent::AutomationOff)]
             .action == output::OutputPolicyAction::ApplySchedule);
  assert(lamp->lifecycle[output::outputLifecycleEventIndex(output::OutputLifecycleEvent::Recovery)]
             .action == output::OutputPolicyAction::ForceOff);
  assert(lamp->lifecycle[output::outputLifecycleEventIndex(output::OutputLifecycleEvent::Fault)]
             .action == output::OutputPolicyAction::ForceOff);
}

void testIdentityAndRoleValidation() {
  auto config = defaults();
  config.endpoints[1].endpoint = kFan;
  assert(output::validateOutputPolicyConfig(config) ==
         output::OutputPolicyConfigStatus::DuplicateEndpoint);

  config = defaults();
  config.endpoints[1].role = output::OutputEndpointRole::ExhaustFan;
  assert(output::validateOutputPolicyConfig(config) == output::OutputPolicyConfigStatus::DuplicateRole);

  config = defaults();
  config.endpoints[0].endpoint = output::kInvalidOutputEndpoint;
  assert(output::validateOutputPolicyConfig(config) == output::OutputPolicyConfigStatus::InvalidEndpoint);

  config = defaults();
  config.endpoints[0].role = static_cast<output::OutputEndpointRole>(99U);
  assert(output::validateOutputPolicyConfig(config) == output::OutputPolicyConfigStatus::InvalidRole);

  config = defaults();
  config.version = output::kOutputPolicySchemaVersion + 1U;
  assert(output::validateOutputPolicyConfig(config) ==
         output::OutputPolicyConfigStatus::UnsupportedVersion);
}

void testLifecycleValidation() {
  auto config = defaults();
  auto& fan_boot =
      config.endpoints[0].lifecycle[output::outputLifecycleEventIndex(output::OutputLifecycleEvent::Boot)];
  fan_boot.action = output::OutputPolicyAction::ApplySchedule;
  assert(output::validateOutputPolicyConfig(config) ==
         output::OutputPolicyConfigStatus::ApplyScheduleOnNonScheduleRole);

  config = defaults();
  auto& lamp_boot =
      config.endpoints[1].lifecycle[output::outputLifecycleEventIndex(output::OutputLifecycleEvent::Boot)];
  lamp_boot.action = static_cast<output::OutputPolicyAction>(99U);
  assert(output::validateOutputPolicyConfig(config) == output::OutputPolicyConfigStatus::InvalidAction);

  config = defaults();
  config.endpoints[0].lifecycle[0].order = static_cast<std::uint8_t>(output::kOutputEndpointCapacity);
  assert(output::validateOutputPolicyConfig(config) == output::OutputPolicyConfigStatus::InvalidOrder);

  config = defaults();
  config.endpoints[0].lifecycle[0].order = config.endpoints[1].lifecycle[0].order;
  assert(output::validateOutputPolicyConfig(config) == output::OutputPolicyConfigStatus::DuplicateOrder);

  config = defaults();
  config.endpoints[0].lifecycle[0].delay_ms = output::kMaxLifecycleDelayMs + 1U;
  assert(output::validateOutputPolicyConfig(config) ==
         output::OutputPolicyConfigStatus::DelayOutOfRange);

  config = defaults();
  config.endpoints[0].lifecycle[0].max_retries = output::kMaxLifecycleRetries + 1U;
  assert(output::validateOutputPolicyConfig(config) == output::OutputPolicyConfigStatus::RetryOutOfRange);

  config = defaults();
  config.max_transition_failures = output::kMaxLifecycleContainmentFailures + 1U;
  assert(output::validateOutputPolicyConfig(config) ==
         output::OutputPolicyConfigStatus::ContainmentOutOfRange);

  config = defaults();
  auto& no_command = config.endpoints[0].lifecycle[0];
  no_command.action = output::OutputPolicyAction::NoCommand;
  assert(output::validateOutputPolicyConfig(config) ==
         output::OutputPolicyConfigStatus::NoCommandMetadataInvalid);
  no_command.retransmit = false;
  no_command.max_retries = 0U;
  no_command.delay_ms = 0U;
  assert(output::validateOutputPolicyConfig(config) == output::OutputPolicyConfigStatus::Ok);
}

} // namespace

int main() {
  testSafeDefaults();
  testIdentityAndRoleValidation();
  testLifecycleValidation();
  return 0;
}
