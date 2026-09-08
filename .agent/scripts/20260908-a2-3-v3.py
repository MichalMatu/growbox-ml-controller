from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text()
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one replacement, found {count}: {old[:80]!r}")
    p.write_text(text.replace(old, new, 1))


Path("src/climate/Stage28dRfOutputEndpoint.h").write_text(r'''#pragma once

#include "climate/ClimateSemanticOutput.h"
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
  Stage28dRfOutputEndpoint(RfOutputEndpointConfig config,
                           ::growbox::app::output::OutputTransport& transport) noexcept;

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
  bool applyBinary(ClimateEndpointId endpoint, bool on, std::uint64_t monotonic_ms,
                   bool force_send = false) noexcept;

  RfOutputEndpointConfig config_{};
  ::growbox::app::output::OutputTransport& transport_;
  std::array<EndpointState, 3U> states_{};
  bool safety_force_exhaust_{false};
  std::uint32_t transmit_count_{0U};
  std::uint32_t transmit_error_count_{0U};
};

} // namespace growbox::app::climate_io::stage28d
''')

Path("src/climate/Stage28dRfOutputEndpoint.cpp").write_text(r'''#include "climate/Stage28dRfOutputEndpoint.h"

#include "climate/Stage28dOutputBindings.h"

#include <cmath>
#include <limits>

namespace growbox::app::climate_io::stage28d {
namespace {

constexpr std::size_t kInvalidStateIndex = std::numeric_limits<std::size_t>::max();

} // namespace

Stage28dRfOutputEndpoint::Stage28dRfOutputEndpoint(
    RfOutputEndpointConfig config, ::growbox::app::output::OutputTransport& transport) noexcept
    : config_(config), transport_(transport) {}

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

bool Stage28dRfOutputEndpoint::initializeSafeState(std::uint64_t monotonic_ms) noexcept {
  if (!config_.enabled) {
    return false;
  }
  bool ok = true;
  ok = applyBinary(kScheduledLightEndpoint, false, monotonic_ms, true) && ok;
  ok = applyBinary(kExhaustFanEndpoint, false, monotonic_ms, true) && ok;
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
  return applyBinary(endpoint, effective_on, monotonic_ms);
}

bool Stage28dRfOutputEndpoint::forceOff(ClimateEndpointId endpoint,
                                       std::uint64_t monotonic_ms) noexcept {
  if (!config_.enabled || endpoint == kScheduledLightEndpoint) {
    return false;
  }
  return applyBinary(endpoint, false, monotonic_ms, true);
}

bool Stage28dRfOutputEndpoint::writeScheduledLight(bool on, std::uint64_t monotonic_ms) noexcept {
  if (!config_.enabled) {
    return false;
  }
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

  const ::growbox::app::output::OutputCommand command{
      endpoint,
      on ? ::growbox::app::output::BinaryOutputState::On
         : ::growbox::app::output::BinaryOutputState::Off,
  };
  const auto result = transport_.send(command);
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
''')

Path("test/test_stage28d_rf_output_endpoint/test_main.cpp").write_text(r'''#include "climate/Stage28dOutputBindings.h"
#include "climate/Stage28dRfOutputEndpoint.h"
#include "climate/output/OutputTransport.h"

#include <array>
#include <cassert>
#include <cstddef>

using namespace growbox::app::climate_io;
using namespace growbox::app::climate_io::stage28d;

namespace {

class FakeTransport final : public growbox::app::output::OutputTransport {
public:
  growbox::app::output::TxResult
  send(const growbox::app::output::OutputCommand& command) noexcept override {
    assert(count < commands.size());
    commands[count++] = command;
    if (fail_next) {
      fail_next = false;
      return {growbox::app::output::TransportStatus::Failed,
              growbox::app::output::TransportError::IoFailure};
    }
    return {growbox::app::output::TransportStatus::Completed,
            growbox::app::output::TransportError::None};
  }

  std::array<growbox::app::output::OutputCommand, 16U> commands{};
  std::size_t count{0U};
  bool fail_next{false};
};

void expectLast(const FakeTransport& tx, ClimateEndpointId endpoint, bool on) {
  assert(tx.count > 0U);
  const auto& command = tx.commands[tx.count - 1U];
  assert(command.endpoint == endpoint);
  assert(command.state == (on ? growbox::app::output::BinaryOutputState::On
                              : growbox::app::output::BinaryOutputState::Off));
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

} // namespace

int main() {
  testSafeInitializationAndDeduplication();
  testSafetyForceExhaustOverridesRuleRequest();
  testEmergencyOffBypassesSafetyForce();
  testScheduledLightUsesDedicatedPath();
  testTransmitFailureDoesNotAdvanceState();
  testDisabledEndpointFailsClosed();
  return 0;
}
''')

replace_once(
    "src/climate/ClimateV6RealInputRuntime.cpp",
    '#include "climate/rf433/Rf433RmtLoopback.h"\n',
    '#include "climate/rf433/Rf433OutputTransport.h"\n'
    '#include "climate/rf433/Rf433RmtFrameSender.h"\n'
    '#include "climate/rf433/Rf433RmtLoopback.h"\n',
)

replace_once(
    "src/climate/ClimateV6RealInputRuntime.cpp",
    '''class DiagnosticsRfTransmitter final : public stage28d::RfCommandTransmitter {\npublic:\n  explicit DiagnosticsRfTransmitter(runtime::Stage28RfDiagnostics& diagnostics) noexcept\n      : diagnostics_(diagnostics) {}\n\n  bool transmit(const rf433::FrameConfig& frame) noexcept override {\n    rf433::LoopbackEvidence evidence{};\n    return diagnostics_.manualTransmit(frame, evidence) && evidence.tx_completed;\n  }\n\nprivate:\n  runtime::Stage28RfDiagnostics& diagnostics_;\n};\n\n''',
    '',
)

replace_once(
    "src/climate/ClimateV6RealInputRuntime.cpp",
    '''  auto& rf_diagnostics = runtime_io_owner.rfDiagnostics();\n  const bool rf_ready = runtime_io_owner.beginRf();\n  DiagnosticsRfTransmitter rf_transmitter(rf_diagnostics);\n\n''',
    '''  auto& rf_diagnostics = runtime_io_owner.rfDiagnostics();\n  const bool rf_ready = runtime_io_owner.beginRf();\n  rf433::Rf433RmtFrameSender rf_frame_sender(runtime_io_owner.rfRadio());\n  rf433::Rf433OutputTransport rf_output_transport(rf_frame_sender);\n\n''',
)

replace_once(
    "src/climate/ClimateV6RealInputRuntime.cpp",
    '''  stage28d::Stage28dRfOutputEndpoint physical_endpoint(\n      {GROWBOX_STAGE28_REAL_OUTPUTS_ENABLED != 0 && rf_ready && output_bindings_valid, 0.5F},\n      rf_transmitter);\n''',
    '''  stage28d::Stage28dRfOutputEndpoint physical_endpoint(\n      {GROWBOX_STAGE28_REAL_OUTPUTS_ENABLED != 0 && rf_ready && output_bindings_valid, 0.5F},\n      rf_output_transport);\n''',
)

replace_once(
    "test/host/CMakeLists.txt",
    '''add_executable(\n  stage28d_rf_output_endpoint_tests\n  "${PROJECT_ROOT}/test/test_stage28d_rf_output_endpoint/test_main.cpp"\n  "${PROJECT_ROOT}/src/climate/Stage28dRfOutputEndpoint.cpp"\n  "${PROJECT_ROOT}/src/climate/rf433/ClimateRf433EndpointRegistry.cpp"\n)\n''',
    '''add_executable(\n  stage28d_rf_output_endpoint_tests\n  "${PROJECT_ROOT}/test/test_stage28d_rf_output_endpoint/test_main.cpp"\n  "${PROJECT_ROOT}/src/climate/Stage28dRfOutputEndpoint.cpp"\n)\n''',
)

print("A2_3_V3_EDIT_SCRIPT_PASS")
