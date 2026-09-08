from pathlib import Path

header = r'''#pragma once

#include "climate/ClimateSemanticOutput.h"
#include "climate/output/OutputStateStore.h"
#include "climate/output/OutputTransport.h"

#include <array>
#include <cstdint>

namespace growbox::app::climate_io::stage28d {

struct RfOutputEndpointConfig {
  bool enabled{false};
  float on_threshold{0.5F};
};

class Stage28dRfOutputEndpoint final : public ClimateOutputEndpoint {
public:
  Stage28dRfOutputEndpoint(
      RfOutputEndpointConfig config, ::growbox::app::output::OutputTransport& transport,
      ::growbox::app::output::OutputStateStore* shadow_state_store = nullptr) noexcept;

  bool initializeSafeState(std::uint64_t monotonic_ms) noexcept;
  bool write(ClimateEndpointId endpoint, float normalized_level,
             std::uint64_t monotonic_ms) noexcept override;
  bool forceOff(ClimateEndpointId endpoint, std::uint64_t monotonic_ms) noexcept override;
  bool writeScheduledLight(bool on, std::uint64_t monotonic_ms) noexcept;
  void setSafetyForceExhaust(bool force) noexcept { safety_force_exhaust_ = force; }

  bool stateKnown(ClimateEndpointId endpoint) const noexcept;
  bool stateOn(ClimateEndpointId endpoint) const noexcept;
  std::uint32_t transmitCount() const noexcept { return transmit_count_; }
  std::uint32_t transmitErrorCount() const noexcept { return transmit_error_count_; }

private:
  struct EndpointState {
    bool known{false};
    bool on{false};
    std::uint64_t changed_ms{0U};
  };

  static std::size_t stateIndex(ClimateEndpointId endpoint) noexcept;
  void mirrorDesiredResolved(ClimateEndpointId endpoint, bool desired_on,
                             bool resolved_on) noexcept;
  bool applyBinary(ClimateEndpointId endpoint, bool on, std::uint64_t monotonic_ms,
                   bool force_send = false) noexcept;

  RfOutputEndpointConfig config_{};
  ::growbox::app::output::OutputTransport& transport_;
  ::growbox::app::output::OutputStateStore* shadow_state_store_{nullptr};
  std::array<EndpointState, 3U> states_{};
  bool safety_force_exhaust_{false};
  std::uint32_t transmit_count_{0U};
  std::uint32_t transmit_error_count_{0U};
};

} // namespace growbox::app::climate_io::stage28d
'''

cpp = r'''#include "climate/Stage28dRfOutputEndpoint.h"

#include "climate/Stage28dOutputBindings.h"

#include <cmath>
#include <limits>

namespace growbox::app::climate_io::stage28d {
namespace {

constexpr std::size_t kInvalidStateIndex = std::numeric_limits<std::size_t>::max();

::growbox::app::output::OutputCommand makeBinaryCommand(ClimateEndpointId endpoint,
                                                        bool on) noexcept {
  return {
      endpoint,
      on ? ::growbox::app::output::BinaryOutputState::On
         : ::growbox::app::output::BinaryOutputState::Off,
  };
}

} // namespace

Stage28dRfOutputEndpoint::Stage28dRfOutputEndpoint(
    RfOutputEndpointConfig config, ::growbox::app::output::OutputTransport& transport,
    ::growbox::app::output::OutputStateStore* shadow_state_store) noexcept
    : config_(config), transport_(transport), shadow_state_store_(shadow_state_store) {}

std::size_t Stage28dRfOutputEndpoint::stateIndex(ClimateEndpointId endpoint) noexcept {
  if (endpoint == kExhaustFanEndpoint) {
    return 0U;
  }
  if (endpoint == kScheduledLightEndpoint) {
    return 1U;
  }
  if (endpoint == kHumidifierEndpoint) {
    return 2U;
  }
  return kInvalidStateIndex;
}

void Stage28dRfOutputEndpoint::mirrorDesiredResolved(ClimateEndpointId endpoint, bool desired_on,
                                                     bool resolved_on) noexcept {
  if (shadow_state_store_ == nullptr) {
    return;
  }
  (void)shadow_state_store_->recordDesired(makeBinaryCommand(endpoint, desired_on));
  (void)shadow_state_store_->recordResolved(makeBinaryCommand(endpoint, resolved_on));
}

bool Stage28dRfOutputEndpoint::initializeSafeState(std::uint64_t monotonic_ms) noexcept {
  if (!config_.enabled) {
    return false;
  }
  bool ok = true;
  mirrorDesiredResolved(kScheduledLightEndpoint, false, false);
  ok = applyBinary(kScheduledLightEndpoint, false, monotonic_ms, true) && ok;
  mirrorDesiredResolved(kExhaustFanEndpoint, false, false);
  ok = applyBinary(kExhaustFanEndpoint, false, monotonic_ms, true) && ok;
  mirrorDesiredResolved(kHumidifierEndpoint, false, false);
  ok = applyBinary(kHumidifierEndpoint, false, monotonic_ms, true) && ok;
  return ok;
}

bool Stage28dRfOutputEndpoint::write(ClimateEndpointId endpoint, float normalized_level,
                                     std::uint64_t monotonic_ms) noexcept {
  if (!config_.enabled || !std::isfinite(normalized_level) || config_.on_threshold < 0.0F ||
      config_.on_threshold > 1.0F || endpoint == kScheduledLightEndpoint) {
    return false;
  }
  const bool requested_on = normalized_level >= config_.on_threshold;
  const bool effective_on = endpoint == kExhaustFanEndpoint && safety_force_exhaust_
                                ? true
                                : requested_on;
  mirrorDesiredResolved(endpoint, requested_on, effective_on);
  return applyBinary(endpoint, effective_on, monotonic_ms);
}

bool Stage28dRfOutputEndpoint::forceOff(ClimateEndpointId endpoint,
                                       std::uint64_t monotonic_ms) noexcept {
  if (!config_.enabled || endpoint == kScheduledLightEndpoint) {
    return false;
  }
  mirrorDesiredResolved(endpoint, false, false);
  return applyBinary(endpoint, false, monotonic_ms, true);
}

bool Stage28dRfOutputEndpoint::writeScheduledLight(bool on, std::uint64_t monotonic_ms) noexcept {
  if (!config_.enabled) {
    return false;
  }
  mirrorDesiredResolved(kScheduledLightEndpoint, on, on);
  return applyBinary(kScheduledLightEndpoint, on, monotonic_ms);
}

bool Stage28dRfOutputEndpoint::stateKnown(ClimateEndpointId endpoint) const noexcept {
  const std::size_t index = stateIndex(endpoint);
  return index != kInvalidStateIndex && states_[index].known;
}

bool Stage28dRfOutputEndpoint::stateOn(ClimateEndpointId endpoint) const noexcept {
  const std::size_t index = stateIndex(endpoint);
  return index != kInvalidStateIndex && states_[index].known && states_[index].on;
}

bool Stage28dRfOutputEndpoint::applyBinary(ClimateEndpointId endpoint, bool on,
                                          std::uint64_t monotonic_ms, bool force_send) noexcept {
  const std::size_t index = stateIndex(endpoint);
  if (index == kInvalidStateIndex) {
    return false;
  }
  EndpointState& state = states_[index];
  if (!force_send && state.known && state.on == on) {
    return true;
  }

  const auto command = makeBinaryCommand(endpoint, on);
  const auto result = transport_.send(command);
  if (shadow_state_store_ != nullptr) {
    (void)shadow_state_store_->recordAttempt(command, monotonic_ms, result);
  }
  if (result.status != ::growbox::app::output::TransportStatus::Completed) {
    ++transmit_error_count_;
    return false;
  }

  ++transmit_count_;
  state.known = true;
  state.on = on;
  state.changed_ms = monotonic_ms;
  return true;
}

} // namespace growbox::app::climate_io::stage28d
'''

test = r'''#include "climate/Stage28dOutputBindings.h"
#include "climate/Stage28dRfOutputEndpoint.h"
#include "climate/output/OutputStateStore.h"
#include "climate/output/OutputTransport.h"

#include <array>
#include <cassert>
#include <cstddef>

using namespace growbox::app::climate_io;
using namespace growbox::app::climate_io::stage28d;

namespace {

namespace output = growbox::app::output;

constexpr std::array<output::OutputEndpointId, output::kOutputEndpointCapacity> kOutputEndpoints{
    kExhaustFanEndpoint, kScheduledLightEndpoint, kHumidifierEndpoint};

class FakeTransport final : public output::OutputTransport {
public:
  output::TxResult send(const output::OutputCommand& command) noexcept override {
    assert(count < commands.size());
    commands[count++] = command;
    if (fail_next) {
      fail_next = false;
      return {output::TransportStatus::Failed, output::TransportError::IoFailure};
    }
    return {output::TransportStatus::Completed, output::TransportError::None};
  }

  std::array<output::OutputCommand, 16U> commands{};
  std::size_t count{0U};
  bool fail_next{false};
};

void expectLast(const FakeTransport& tx, ClimateEndpointId endpoint, bool on) {
  assert(tx.count > 0U);
  const auto& command = tx.commands[tx.count - 1U];
  assert(command.endpoint == endpoint);
  assert(command.state == (on ? output::BinaryOutputState::On : output::BinaryOutputState::Off));
}

void testSafeInitializationAndDeduplication() {
  FakeTransport tx;
  Stage28dRfOutputEndpoint endpoint({true, 0.5F}, tx);
  assert(endpoint.initializeSafeState(100U));
  assert(tx.count == 3U);
  assert(endpoint.stateKnown(kScheduledLightEndpoint));
  assert(!endpoint.stateOn(kScheduledLightEndpoint));
  assert(endpoint.stateKnown(kExhaustFanEndpoint));
  assert(!endpoint.stateOn(kExhaustFanEndpoint));
  assert(endpoint.stateKnown(kHumidifierEndpoint));
  assert(!endpoint.stateOn(kHumidifierEndpoint));

  assert(endpoint.write(kExhaustFanEndpoint, 0.0F, 200U));
  assert(tx.count == 3U);
  assert(endpoint.write(kExhaustFanEndpoint, 1.0F, 300U));
  assert(tx.count == 4U);
  expectLast(tx, kExhaustFanEndpoint, true);
  assert(endpoint.write(kExhaustFanEndpoint, 1.0F, 400U));
  assert(tx.count == 4U);
}

void testSafetyForceExhaustOverridesRuleRequest() {
  FakeTransport tx;
  Stage28dRfOutputEndpoint endpoint({true, 0.5F}, tx);
  assert(endpoint.initializeSafeState(0U));
  endpoint.setSafetyForceExhaust(true);
  assert(endpoint.write(kExhaustFanEndpoint, 0.0F, 100U));
  assert(endpoint.stateOn(kExhaustFanEndpoint));
  expectLast(tx, kExhaustFanEndpoint, true);

  endpoint.setSafetyForceExhaust(false);
  assert(endpoint.write(kExhaustFanEndpoint, 0.0F, 200U));
  assert(!endpoint.stateOn(kExhaustFanEndpoint));
  expectLast(tx, kExhaustFanEndpoint, false);
}

void testEmergencyOffBypassesSafetyForce() {
  FakeTransport tx;
  Stage28dRfOutputEndpoint endpoint({true, 0.5F}, tx);
  assert(endpoint.initializeSafeState(0U));
  endpoint.setSafetyForceExhaust(true);
  assert(endpoint.write(kExhaustFanEndpoint, 0.0F, 100U));
  assert(endpoint.stateOn(kExhaustFanEndpoint));

  assert(endpoint.forceOff(kExhaustFanEndpoint, 101U));
  assert(!endpoint.stateOn(kExhaustFanEndpoint));
  expectLast(tx, kExhaustFanEndpoint, false);

  assert(endpoint.write(kExhaustFanEndpoint, 0.0F, 102U));
  assert(endpoint.stateOn(kExhaustFanEndpoint));
  expectLast(tx, kExhaustFanEndpoint, true);
}

void testScheduledLightUsesDedicatedPath() {
  FakeTransport tx;
  Stage28dRfOutputEndpoint endpoint({true, 0.5F}, tx);
  assert(endpoint.initializeSafeState(0U));
  assert(!endpoint.write(kScheduledLightEndpoint, 1.0F, 100U));
  assert(!endpoint.forceOff(kScheduledLightEndpoint, 100U));
  assert(endpoint.writeScheduledLight(true, 100U));
  assert(endpoint.stateOn(kScheduledLightEndpoint));
  expectLast(tx, kScheduledLightEndpoint, true);
  assert(endpoint.writeScheduledLight(true, 200U));
  assert(tx.count == 4U);
  assert(endpoint.writeScheduledLight(false, 300U));
  assert(!endpoint.stateOn(kScheduledLightEndpoint));
  expectLast(tx, kScheduledLightEndpoint, false);
}

void testTransmitFailureDoesNotAdvanceState() {
  FakeTransport tx;
  Stage28dRfOutputEndpoint endpoint({true, 0.5F}, tx);
  assert(endpoint.initializeSafeState(0U));
  tx.fail_next = true;
  assert(!endpoint.write(kHumidifierEndpoint, 1.0F, 100U));
  assert(!endpoint.stateOn(kHumidifierEndpoint));
  assert(endpoint.transmitErrorCount() == 1U);
  assert(endpoint.write(kHumidifierEndpoint, 1.0F, 200U));
  assert(endpoint.stateOn(kHumidifierEndpoint));
  expectLast(tx, kHumidifierEndpoint, true);
}

void testDisabledEndpointFailsClosed() {
  FakeTransport tx;
  Stage28dRfOutputEndpoint endpoint({false, 0.5F}, tx);
  assert(!endpoint.initializeSafeState(0U));
  assert(!endpoint.write(kExhaustFanEndpoint, 1.0F, 100U));
  assert(!endpoint.forceOff(kExhaustFanEndpoint, 100U));
  assert(!endpoint.writeScheduledLight(true, 100U));
  assert(tx.count == 0U);
}

void testShadowStoreMirrorsCommandTruthWithoutFabricatingPhysicalState() {
  output::OutputStateStore store;
  assert(store.configure(kOutputEndpoints, kOutputEndpoints.size()));
  FakeTransport tx;
  Stage28dRfOutputEndpoint endpoint({true, 0.5F}, tx, &store);
  assert(endpoint.initializeSafeState(10U));

  const auto* fan_after_boot = store.find(kExhaustFanEndpoint);
  assert(fan_after_boot != nullptr && fan_after_boot->has_successful_command);
  assert(fan_after_boot->last_successful_command.state == output::BinaryOutputState::Off);
  assert(fan_after_boot->physical.state == output::PhysicalOutputState::Unknown);
  assert(!fan_after_boot->physical.has_independent_feedback);

  endpoint.setSafetyForceExhaust(true);
  assert(endpoint.write(kExhaustFanEndpoint, 0.0F, 100U));
  const auto* fan = store.find(kExhaustFanEndpoint);
  assert(fan != nullptr && fan->has_desired && fan->has_resolved && fan->has_attempt);
  assert(fan->desired.state == output::BinaryOutputState::Off);
  assert(fan->resolved.state == output::BinaryOutputState::On);
  assert(fan->last_transport.status == output::TransportStatus::Completed);
  assert(fan->last_successful_command.state == output::BinaryOutputState::On);
  assert(endpoint.stateOn(kExhaustFanEndpoint));
  assert(fan->physical.state == output::PhysicalOutputState::Unknown);
  const auto fan_attempt_ms = fan->last_attempt_ms;
  const auto tx_count = tx.count;

  assert(endpoint.write(kExhaustFanEndpoint, 0.0F, 110U));
  assert(tx.count == tx_count);
  fan = store.find(kExhaustFanEndpoint);
  assert(fan != nullptr && fan->last_attempt_ms == fan_attempt_ms);

  tx.fail_next = true;
  assert(!endpoint.write(kHumidifierEndpoint, 1.0F, 200U));
  const auto* humidifier = store.find(kHumidifierEndpoint);
  assert(humidifier != nullptr && humidifier->has_desired && humidifier->has_resolved);
  assert(humidifier->desired.state == output::BinaryOutputState::On);
  assert(humidifier->resolved.state == output::BinaryOutputState::On);
  assert(humidifier->has_attempt);
  assert(humidifier->last_attempt.state == output::BinaryOutputState::On);
  assert(humidifier->last_transport.status == output::TransportStatus::Failed);
  assert(humidifier->has_successful_command);
  assert(humidifier->last_successful_command.state == output::BinaryOutputState::Off);
  assert(!endpoint.stateOn(kHumidifierEndpoint));
  assert(humidifier->physical.state == output::PhysicalOutputState::Unknown);
  assert(!humidifier->physical.has_independent_feedback);
}

} // namespace

int main() {
  testSafeInitializationAndDeduplication();
  testSafetyForceExhaustOverridesRuleRequest();
  testEmergencyOffBypassesSafetyForce();
  testScheduledLightUsesDedicatedPath();
  testTransmitFailureDoesNotAdvanceState();
  testDisabledEndpointFailsClosed();
  testShadowStoreMirrorsCommandTruthWithoutFabricatingPhysicalState();
  return 0;
}
'''

Path('src/climate/Stage28dRfOutputEndpoint.h').write_text(header)
Path('src/climate/Stage28dRfOutputEndpoint.cpp').write_text(cpp)
Path('test/test_stage28d_rf_output_endpoint/test_main.cpp').write_text(test)

runtime_path = Path('src/climate/ClimateV6RealInputRuntime.cpp')
runtime = runtime_path.read_text()
old = '#include "climate/Stage28dThermalTestSequence.h"\n'
new = old + '#include "climate/output/OutputStateStore.h"\n'
assert runtime.count(old) == 1
runtime = runtime.replace(old, new, 1)
old = '#include <cstdint>\n'
new = '#include <array>\n#include <cstdint>\n'
assert runtime.count(old) == 1
runtime = runtime.replace(old, new, 1)
old = '''  rf433::Rf433RmtFrameSender rf_frame_sender(runtime_io_owner.rfRadio());
  rf433::Rf433OutputTransport rf_output_transport(rf_frame_sender);

  const auto semantic_output_config = stage28d::makeClimateSemanticOutputConfig();
'''
new = '''  rf433::Rf433RmtFrameSender rf_frame_sender(runtime_io_owner.rfRadio());
  rf433::Rf433OutputTransport rf_output_transport(rf_frame_sender);
  static output::OutputStateStore output_state_store;
  static constexpr std::array<output::OutputEndpointId, output::kOutputEndpointCapacity>
      kShadowOutputEndpoints{stage28d::kExhaustFanEndpoint, stage28d::kScheduledLightEndpoint,
                             stage28d::kHumidifierEndpoint};
  const bool output_state_store_ready =
      output_state_store.configure(kShadowOutputEndpoints, kShadowOutputEndpoints.size());
  if (!output_state_store_ready) {
    ESP_LOGE(kTag, "Output state-store shadow configuration failed");
  }

  const auto semantic_output_config = stage28d::makeClimateSemanticOutputConfig();
'''
assert runtime.count(old) == 1
runtime = runtime.replace(old, new, 1)
old = '''  stage28d::Stage28dRfOutputEndpoint physical_endpoint(
      {GROWBOX_STAGE28_REAL_OUTPUTS_ENABLED != 0 && rf_ready && output_bindings_valid, 0.5F},
      rf_output_transport);
'''
new = '''  stage28d::Stage28dRfOutputEndpoint physical_endpoint(
      {GROWBOX_STAGE28_REAL_OUTPUTS_ENABLED != 0 && rf_ready && output_bindings_valid, 0.5F},
      rf_output_transport, output_state_store_ready ? &output_state_store : nullptr);
'''
assert runtime.count(old) == 1
runtime = runtime.replace(old, new, 1)
runtime_path.write_text(runtime)

cmake_path = Path('test/host/CMakeLists.txt')
cmake = cmake_path.read_text()
old = '''add_executable(
  stage28d_rf_output_endpoint_tests
  "${PROJECT_ROOT}/test/test_stage28d_rf_output_endpoint/test_main.cpp"
  "${PROJECT_ROOT}/src/climate/Stage28dRfOutputEndpoint.cpp"
)
'''
new = '''add_executable(
  stage28d_rf_output_endpoint_tests
  "${PROJECT_ROOT}/test/test_stage28d_rf_output_endpoint/test_main.cpp"
  "${PROJECT_ROOT}/src/climate/Stage28dRfOutputEndpoint.cpp"
  "${PROJECT_ROOT}/src/climate/output/OutputStateStore.cpp"
)
'''
assert cmake.count(old) == 1
cmake = cmake.replace(old, new, 1)
cmake_path.write_text(cmake)
