from pathlib import Path

ROOT = Path('.')

HEADER = r'''#pragma once

#include "climate/output/OutputTypes.h"

#include <array>
#include <cstddef>
#include <cstdint>

namespace growbox::app::output {

inline constexpr std::uint16_t kOutputPolicySchemaVersion = 1U;
inline constexpr std::uint32_t kMaxLifecycleDelayMs = 60'000U;
inline constexpr std::uint8_t kMaxLifecycleRetries = 3U;
inline constexpr std::uint8_t kMaxLifecycleContainmentFailures = 3U;

enum class OutputEndpointRole : std::uint8_t {
  ExhaustFan = 0U,
  ScheduledLight,
  Humidifier,
};

enum class OutputLifecycleEvent : std::uint8_t {
  Boot = 0U,
  AutomationOff,
  Recovery,
  Fault,
};

inline constexpr std::size_t kOutputLifecycleEventCount = 4U;

enum class OutputPolicyAction : std::uint8_t {
  NoCommand = 0U,
  ForceOff,
  ForceOn,
  ApplySchedule,
  RestoreLastCommand,
};

struct OutputLifecycleActionPolicy {
  OutputPolicyAction action = OutputPolicyAction::ForceOff;
  std::uint8_t order = 0U;
  std::uint32_t delay_ms = 0U;
  bool retransmit = true;
  std::uint8_t max_retries = 1U;
};

struct OutputEndpointPolicy {
  OutputEndpointId endpoint = kInvalidOutputEndpoint;
  OutputEndpointRole role = OutputEndpointRole::ExhaustFan;
  std::array<OutputLifecycleActionPolicy, kOutputLifecycleEventCount> lifecycle{};
};

struct OutputPolicyConfig {
  std::uint16_t version = kOutputPolicySchemaVersion;
  std::array<OutputEndpointPolicy, kOutputEndpointCapacity> endpoints{};
  std::uint8_t count = 0U;
  std::uint8_t max_transition_failures = 1U;
};

enum class OutputPolicyConfigStatus : std::uint8_t {
  Ok = 0U,
  UnsupportedVersion,
  InvalidEndpointCount,
  InvalidEndpoint,
  DuplicateEndpoint,
  InvalidRole,
  DuplicateRole,
  MissingRequiredRole,
  InvalidAction,
  InvalidOrder,
  DuplicateOrder,
  DelayOutOfRange,
  RetryOutOfRange,
  ContainmentOutOfRange,
  ApplyScheduleOnNonScheduleRole,
  NoCommandMetadataInvalid,
};

constexpr std::size_t outputLifecycleEventIndex(OutputLifecycleEvent event) noexcept {
  return static_cast<std::size_t>(event);
}

OutputPolicyConfigStatus validateOutputPolicyConfig(const OutputPolicyConfig& config) noexcept;

OutputPolicyConfig makeSafeDefaultOutputPolicyConfig(OutputEndpointId exhaust_fan,
                                                     OutputEndpointId scheduled_light,
                                                     OutputEndpointId humidifier) noexcept;

const OutputEndpointPolicy* findOutputPolicyEndpoint(const OutputPolicyConfig& config,
                                                     OutputEndpointId endpoint) noexcept;
const OutputEndpointPolicy* findOutputPolicyRole(const OutputPolicyConfig& config,
                                                 OutputEndpointRole role) noexcept;

} // namespace growbox::app::output
'''

SOURCE = r'''#include "climate/output/OutputPolicyConfig.h"

#include <array>
#include <cstddef>

namespace growbox::app::output {
namespace {

bool validRole(OutputEndpointRole role) noexcept {
  switch (role) {
  case OutputEndpointRole::ExhaustFan:
  case OutputEndpointRole::ScheduledLight:
  case OutputEndpointRole::Humidifier:
    return true;
  }
  return false;
}

bool validAction(OutputPolicyAction action) noexcept {
  switch (action) {
  case OutputPolicyAction::NoCommand:
  case OutputPolicyAction::ForceOff:
  case OutputPolicyAction::ForceOn:
  case OutputPolicyAction::ApplySchedule:
  case OutputPolicyAction::RestoreLastCommand:
    return true;
  }
  return false;
}

void fillLifecycle(OutputEndpointPolicy& endpoint, std::uint8_t order) noexcept {
  for (auto& lifecycle : endpoint.lifecycle) {
    lifecycle.action = OutputPolicyAction::ForceOff;
    lifecycle.order = order;
    lifecycle.delay_ms = 0U;
    lifecycle.retransmit = true;
    lifecycle.max_retries = 1U;
  }
}

} // namespace

OutputPolicyConfigStatus validateOutputPolicyConfig(const OutputPolicyConfig& config) noexcept {
  if (config.version != kOutputPolicySchemaVersion) {
    return OutputPolicyConfigStatus::UnsupportedVersion;
  }
  if (config.count != kOutputEndpointCapacity) {
    return OutputPolicyConfigStatus::InvalidEndpointCount;
  }
  if (config.max_transition_failures == 0U ||
      config.max_transition_failures > kMaxLifecycleContainmentFailures) {
    return OutputPolicyConfigStatus::ContainmentOutOfRange;
  }

  std::array<bool, kOutputEndpointCapacity> role_seen{};
  for (std::size_t index = 0U; index < config.count; ++index) {
    const auto& endpoint = config.endpoints[index];
    if (!isValidOutputEndpoint(endpoint.endpoint)) {
      return OutputPolicyConfigStatus::InvalidEndpoint;
    }
    if (!validRole(endpoint.role)) {
      return OutputPolicyConfigStatus::InvalidRole;
    }
    const std::size_t role_index = static_cast<std::size_t>(endpoint.role);
    if (role_index >= role_seen.size()) {
      return OutputPolicyConfigStatus::InvalidRole;
    }
    if (role_seen[role_index]) {
      return OutputPolicyConfigStatus::DuplicateRole;
    }
    role_seen[role_index] = true;

    for (std::size_t previous = 0U; previous < index; ++previous) {
      if (config.endpoints[previous].endpoint == endpoint.endpoint) {
        return OutputPolicyConfigStatus::DuplicateEndpoint;
      }
    }

    for (const auto& lifecycle : endpoint.lifecycle) {
      if (!validAction(lifecycle.action)) {
        return OutputPolicyConfigStatus::InvalidAction;
      }
      if (lifecycle.order >= config.count) {
        return OutputPolicyConfigStatus::InvalidOrder;
      }
      if (lifecycle.delay_ms > kMaxLifecycleDelayMs) {
        return OutputPolicyConfigStatus::DelayOutOfRange;
      }
      if (lifecycle.max_retries > kMaxLifecycleRetries) {
        return OutputPolicyConfigStatus::RetryOutOfRange;
      }
      if (lifecycle.action == OutputPolicyAction::ApplySchedule &&
          endpoint.role != OutputEndpointRole::ScheduledLight) {
        return OutputPolicyConfigStatus::ApplyScheduleOnNonScheduleRole;
      }
      if (lifecycle.action == OutputPolicyAction::NoCommand &&
          (lifecycle.delay_ms != 0U || lifecycle.retransmit || lifecycle.max_retries != 0U)) {
        return OutputPolicyConfigStatus::NoCommandMetadataInvalid;
      }
    }
  }

  for (bool seen : role_seen) {
    if (!seen) {
      return OutputPolicyConfigStatus::MissingRequiredRole;
    }
  }

  for (std::size_t event_index = 0U; event_index < kOutputLifecycleEventCount; ++event_index) {
    std::array<bool, kOutputEndpointCapacity> order_seen{};
    for (std::size_t endpoint_index = 0U; endpoint_index < config.count; ++endpoint_index) {
      const std::uint8_t order = config.endpoints[endpoint_index].lifecycle[event_index].order;
      if (order_seen[order]) {
        return OutputPolicyConfigStatus::DuplicateOrder;
      }
      order_seen[order] = true;
    }
  }

  return OutputPolicyConfigStatus::Ok;
}

OutputPolicyConfig makeSafeDefaultOutputPolicyConfig(OutputEndpointId exhaust_fan,
                                                     OutputEndpointId scheduled_light,
                                                     OutputEndpointId humidifier) noexcept {
  OutputPolicyConfig config{};
  config.count = static_cast<std::uint8_t>(kOutputEndpointCapacity);
  config.max_transition_failures = 1U;

  config.endpoints[0].endpoint = exhaust_fan;
  config.endpoints[0].role = OutputEndpointRole::ExhaustFan;
  fillLifecycle(config.endpoints[0], 1U);

  config.endpoints[1].endpoint = scheduled_light;
  config.endpoints[1].role = OutputEndpointRole::ScheduledLight;
  fillLifecycle(config.endpoints[1], 0U);
  config.endpoints[1].lifecycle[outputLifecycleEventIndex(OutputLifecycleEvent::AutomationOff)]
      .action = OutputPolicyAction::ApplySchedule;

  config.endpoints[2].endpoint = humidifier;
  config.endpoints[2].role = OutputEndpointRole::Humidifier;
  fillLifecycle(config.endpoints[2], 2U);

  return config;
}

const OutputEndpointPolicy* findOutputPolicyEndpoint(const OutputPolicyConfig& config,
                                                     OutputEndpointId endpoint) noexcept {
  if (!isValidOutputEndpoint(endpoint) || config.count > kOutputEndpointCapacity) {
    return nullptr;
  }
  const OutputEndpointPolicy* found = nullptr;
  for (std::size_t index = 0U; index < config.count; ++index) {
    if (config.endpoints[index].endpoint != endpoint) {
      continue;
    }
    if (found != nullptr) {
      return nullptr;
    }
    found = &config.endpoints[index];
  }
  return found;
}

const OutputEndpointPolicy* findOutputPolicyRole(const OutputPolicyConfig& config,
                                                 OutputEndpointRole role) noexcept {
  if (!validRole(role) || config.count > kOutputEndpointCapacity) {
    return nullptr;
  }
  const OutputEndpointPolicy* found = nullptr;
  for (std::size_t index = 0U; index < config.count; ++index) {
    if (config.endpoints[index].role != role) {
      continue;
    }
    if (found != nullptr) {
      return nullptr;
    }
    found = &config.endpoints[index];
  }
  return found;
}

} // namespace growbox::app::output
'''

TEST = r'''#include "climate/output/OutputPolicyConfig.h"

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
'''

(ROOT / 'src/climate/output/OutputPolicyConfig.h').write_text(HEADER)
(ROOT / 'src/climate/output/OutputPolicyConfig.cpp').write_text(SOURCE)
(ROOT / 'test/test_output_policy_config').mkdir(parents=True, exist_ok=True)
(ROOT / 'test/test_output_policy_config/test_main.cpp').write_text(TEST)

# Register the production source.
src_cmake = ROOT / 'src/CMakeLists.txt'
text = src_cmake.read_text()
needle = '    "climate/output/OutputStateStore.cpp"\n'
assert text.count(needle) == 1
text = text.replace(needle, needle + '    "climate/output/OutputPolicyConfig.cpp"\n')
src_cmake.write_text(text)

# Route Stage28D product binding through the validated policy configuration.
h = ROOT / 'src/climate/Stage28dOutputBindings.h'
text = h.read_text()
needle = '#include "climate/ClimateSemanticOutput.h"\n'
assert text.count(needle) == 1
text = text.replace(needle, needle + '#include "climate/output/OutputPolicyConfig.h"\n')
needle = '  UnexpectedClimateRole,\n};\n\nClimateSemanticOutputConfig makeClimateSemanticOutputConfig() noexcept;\n'
assert text.count(needle) == 1
text = text.replace(
    needle,
    '  UnexpectedClimateRole,\n  PolicyConfigInvalid,\n};\n\n'
    '::growbox::app::output::OutputPolicyConfig makeOutputPolicyConfig() noexcept;\n'
    'ClimateSemanticOutputConfig makeClimateSemanticOutputConfig() noexcept;\n')
h.write_text(text)

cpp = ROOT / 'src/climate/Stage28dOutputBindings.cpp'
cpp.write_text(r'''#include "climate/Stage28dOutputBindings.h"

namespace growbox::app::climate_io::stage28d {
namespace {

using ::growbox::app::output::OutputEndpointPolicy;
using ::growbox::app::output::OutputEndpointRole;
using ::growbox::app::output::OutputPolicyConfig;
using ::growbox::app::output::OutputPolicyConfigStatus;

bool mappingMatches(const ClimateSemanticOutputConfig& config, ClimateActuatorRole role,
                    ClimateEndpointId endpoint) noexcept {
  const std::size_t index = climateRoleIndex(role);
  if (index >= config.roles.size()) {
    return false;
  }
  const ClimateRoleEndpointMapping& mapping = config.roles[index];
  return mapping.enabled && mapping.endpoint == endpoint;
}

bool mappingIsCleanlyDisabled(const ClimateSemanticOutputConfig& config,
                              ClimateActuatorRole role) noexcept {
  const std::size_t index = climateRoleIndex(role);
  if (index >= config.roles.size()) {
    return false;
  }
  const ClimateRoleEndpointMapping& mapping = config.roles[index];
  return !mapping.enabled && mapping.endpoint == kUnmappedClimateEndpoint;
}

bool hardwareMatches(ClimateEndpointId endpoint,
                     const rf433::RemoteSocketHardwareConfig* expected) noexcept {
  const rf433::ClimateRf433EndpointBinding* binding = rf433::findClimateRf433Endpoint(endpoint);
  return binding != nullptr && binding->endpoint == endpoint && binding->hardware == expected;
}

const OutputEndpointPolicy* requiredRole(const OutputPolicyConfig& policy,
                                         OutputEndpointRole role) noexcept {
  return ::growbox::app::output::findOutputPolicyRole(policy, role);
}

} // namespace

OutputPolicyConfig makeOutputPolicyConfig() noexcept {
  return ::growbox::app::output::makeSafeDefaultOutputPolicyConfig(
      kExhaustFanEndpoint, kScheduledLightEndpoint, kHumidifierEndpoint);
}

ClimateSemanticOutputConfig makeClimateSemanticOutputConfig() noexcept {
  const OutputPolicyConfig policy = makeOutputPolicyConfig();
  if (::growbox::app::output::validateOutputPolicyConfig(policy) != OutputPolicyConfigStatus::Ok) {
    return {};
  }

  ClimateSemanticOutputConfig config{};
  const auto* fan = requiredRole(policy, OutputEndpointRole::ExhaustFan);
  const auto* humidifier = requiredRole(policy, OutputEndpointRole::Humidifier);
  if (fan == nullptr || humidifier == nullptr ||
      !bindClimateRole(config, ClimateActuatorRole::ExhaustFan, fan->endpoint) ||
      !bindClimateRole(config, ClimateActuatorRole::Humidifier, humidifier->endpoint)) {
    return {};
  }
  return config;
}

OutputBindingStatus validateOutputBindings(const ClimateSemanticOutputConfig& config) noexcept {
  const OutputPolicyConfig policy = makeOutputPolicyConfig();
  if (::growbox::app::output::validateOutputPolicyConfig(policy) != OutputPolicyConfigStatus::Ok) {
    return OutputBindingStatus::PolicyConfigInvalid;
  }

  if (validateClimateSemanticOutputConfig(config) != ClimateSemanticOutputConfigStatus::Ok) {
    return OutputBindingStatus::ClimateConfigInvalid;
  }

  const auto* fan = requiredRole(policy, OutputEndpointRole::ExhaustFan);
  const auto* lamp = requiredRole(policy, OutputEndpointRole::ScheduledLight);
  const auto* humidifier = requiredRole(policy, OutputEndpointRole::Humidifier);
  if (fan == nullptr || lamp == nullptr || humidifier == nullptr) {
    return OutputBindingStatus::PolicyConfigInvalid;
  }

  if (!hardwareMatches(fan->endpoint, &rf433::kRemoteSocket1) ||
      !hardwareMatches(lamp->endpoint, &rf433::kRemoteSocket2) ||
      !hardwareMatches(humidifier->endpoint, &rf433::kRemoteSocket3)) {
    return OutputBindingStatus::HardwareRegistryMismatch;
  }

  for (const ClimateRoleEndpointMapping& mapping : config.roles) {
    if (mapping.enabled && mapping.endpoint == lamp->endpoint) {
      return OutputBindingStatus::ScheduledLightRoutedToClimate;
    }
  }

  if (!mappingMatches(config, ClimateActuatorRole::ExhaustFan, fan->endpoint)) {
    return OutputBindingStatus::ExhaustFanMissingOrWrong;
  }
  if (!mappingMatches(config, ClimateActuatorRole::Humidifier, humidifier->endpoint)) {
    return OutputBindingStatus::HumidifierMissingOrWrong;
  }

  constexpr ClimateActuatorRole kDisabledClimateRoles[] = {
      ClimateActuatorRole::Heater,
      ClimateActuatorRole::Cooler,
      ClimateActuatorRole::Dehumidifier,
      ClimateActuatorRole::Co2Doser,
  };
  for (ClimateActuatorRole role : kDisabledClimateRoles) {
    if (!mappingIsCleanlyDisabled(config, role)) {
      return OutputBindingStatus::UnexpectedClimateRole;
    }
  }

  return OutputBindingStatus::Ok;
}

bool isScheduledLightEndpoint(ClimateEndpointId endpoint) noexcept {
  const OutputPolicyConfig policy = makeOutputPolicyConfig();
  const auto* lamp = requiredRole(policy, OutputEndpointRole::ScheduledLight);
  return lamp != nullptr && endpoint == lamp->endpoint;
}

} // namespace growbox::app::climate_io::stage28d
''')

# Register host tests and link the new config into the Stage28D semantic binding test.
host = ROOT / 'test/host/CMakeLists.txt'
text = host.read_text()
needle = '''add_executable(
  climate_semantic_output_tests
  "${PROJECT_ROOT}/test/test_climate_semantic_output/test_main.cpp"
  "${PROJECT_ROOT}/src/climate/ClimateIoAdapters.cpp"
  "${PROJECT_ROOT}/src/climate/ClimateSemanticOutput.cpp"
  "${PROJECT_ROOT}/src/climate/rf433/ClimateRf433EndpointRegistry.cpp"
  "${PROJECT_ROOT}/src/climate/Stage28dOutputBindings.cpp"
)
'''
assert text.count(needle) == 1
replacement = '''add_executable(
  output_policy_config_tests
  "${PROJECT_ROOT}/test/test_output_policy_config/test_main.cpp"
  "${PROJECT_ROOT}/src/climate/output/OutputPolicyConfig.cpp"
)
target_include_directories(output_policy_config_tests PRIVATE "${PROJECT_ROOT}/src")
target_compile_features(output_policy_config_tests PRIVATE cxx_std_17)
target_compile_options(output_policy_config_tests PRIVATE -Wall -Wextra -Wpedantic)

add_executable(
  climate_semantic_output_tests
  "${PROJECT_ROOT}/test/test_climate_semantic_output/test_main.cpp"
  "${PROJECT_ROOT}/src/climate/ClimateIoAdapters.cpp"
  "${PROJECT_ROOT}/src/climate/ClimateSemanticOutput.cpp"
  "${PROJECT_ROOT}/src/climate/rf433/ClimateRf433EndpointRegistry.cpp"
  "${PROJECT_ROOT}/src/climate/output/OutputPolicyConfig.cpp"
  "${PROJECT_ROOT}/src/climate/Stage28dOutputBindings.cpp"
)
'''
text = text.replace(needle, replacement)
needle = 'add_test(NAME climate_semantic_output_tests COMMAND climate_semantic_output_tests)\n'
assert text.count(needle) == 1
text = text.replace(needle, 'add_test(NAME output_policy_config_tests COMMAND output_policy_config_tests)\n' + needle)
host.write_text(text)

print('A8_1_EDIT_PASS')
