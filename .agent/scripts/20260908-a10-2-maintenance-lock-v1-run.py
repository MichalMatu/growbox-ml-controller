import os
import subprocess
from pathlib import Path

BASE = '54962531bc9825a049352db830858f2098d51700'
BRANCH = 'mvp/environment-controller'
EXPECTED = sorted([
    'src/CMakeLists.txt',
    'src/climate/ClimateV6RealInputRuntime.cpp',
    'src/climate/output/OutputMaintenanceControl.cpp',
    'src/climate/output/OutputMaintenanceControl.h',
    'src/climate/output/OutputStateStore.cpp',
    'src/climate/output/OutputStateStore.h',
    'src/climate/runtime/Stage28MaintenanceRfTransport.cpp',
    'src/climate/runtime/Stage28MaintenanceRfTransport.h',
    'src/climate/runtime/Stage28ServiceConsole.cpp',
    'src/climate/runtime/Stage28ServiceConsole.h',
    'src/climate/runtime/Stage28ServiceConsoleCommand.cpp',
    'src/climate/runtime/Stage28ServiceConsoleCommand.h',
    'test/host/CMakeLists.txt',
    'test/test_output_maintenance_control/test_main.cpp',
    'test/test_stage28_service_console/test_main.cpp',
])


def run(cmd, env=None):
    print('+', ' '.join(cmd), flush=True)
    subprocess.run(cmd, check=True, env=env)


def out(cmd):
    return subprocess.check_output(cmd, text=True).strip()


def replace_once(path, old, new):
    p = Path(path)
    text = p.read_text()
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'{path}: expected one replacement, found {count}')
    p.write_text(text.replace(old, new, 1))


run(['git', 'fetch', '-q', 'origin', BRANCH])
if out(['git', 'rev-parse', 'HEAD']) != BASE:
    raise SystemExit('A10_2_IDENTITY_FAIL local HEAD mismatch')
if out(['git', 'rev-parse', 'FETCH_HEAD']) != BASE:
    raise SystemExit('A10_2_IDENTITY_FAIL remote branch mismatch')
if out(['git', 'status', '--porcelain']):
    raise SystemExit('A10_2_IDENTITY_FAIL worktree not clean')
print('A10_2_IDENTITY_PASS')

Path('src/climate/output/OutputMaintenanceControl.h').write_text(r'''#pragma once

#include "climate/output/OutputAutomationControl.h"
#include "climate/output/OutputStateStore.h"
#include "climate/output/OutputTransport.h"

#include <cstdint>

namespace growbox::app::output {

enum class OutputMaintenanceStatus : std::uint8_t {
  Ready = 0U,
  EnterPending,
  ExitPending,
  RawPending,
  SafetyVeto,
  TxFailed,
  ModeDenied,
  Busy,
  FaultLocked,
  Invalid,
};

struct OutputMaintenanceReport {
  OutputMaintenanceStatus status = OutputMaintenanceStatus::Invalid;
  SupervisorMode mode = SupervisorMode::BootLocked;
  bool enter_pending = false;
  bool exit_pending = false;
  bool rearm_pending = false;
  bool raw_pending = false;
  bool has_raw_result = false;
  OutputCommand raw_command{};
  TxResult raw_transport{};
  PhysicalOutputState physical = PhysicalOutputState::Unknown;
};

class OutputMaintenanceControl final {
public:
  OutputMaintenanceControl(const OutputPolicyConfig& policy,
                           OutputSupervisorLifecycle& lifecycle,
                           OutputAutomationControl& automation_control,
                           OutputLifecycleExecutor& lifecycle_executor,
                           OutputStateStore& state_store,
                           OutputSupervisorResolverConfig resolver_config,
                           OutputTransport& raw_transport) noexcept;

  bool valid() const noexcept { return valid_; }
  SupervisorMode mode() const noexcept { return lifecycle_.mode(); }
  bool transitionActive() const noexcept {
    return enter_pending_ || exit_pending_ || rearm_pending_ || raw_pending_ ||
           automation_control_.transitionActive() || lifecycle_executor_.active();
  }

  bool requestEnter() noexcept;
  bool requestExit() noexcept;
  bool requestRaw(OutputEndpointRole role, BinaryOutputState state,
                  std::uint64_t monotonic_ms) noexcept;
  OutputMaintenanceReport tick(std::uint64_t monotonic_ms,
                               const SafetyEnvelope& safety) noexcept;
  OutputMaintenanceReport report() const noexcept;

private:
  const OutputSupervisorEndpointBinding* findBinding(OutputEndpointId endpoint) const noexcept;
  static const SafetyEndpointConstraint* findSafety(const SafetyEnvelope& safety,
                                                    OutputEndpointId endpoint) noexcept;
  static bool safetyVetoes(const SafetyEndpointConstraint* safety,
                           BinaryOutputState state) noexcept;
  static bool binaryStateValid(BinaryOutputState state) noexcept;
  std::uint64_t nextSequence() noexcept;
  bool clearPhysicalUncertainty() noexcept;
  bool clearPhysicalUncertainty(OutputEndpointId endpoint) noexcept;
  void synchronizeBinary(const OutputCommand& command, std::uint64_t monotonic_ms) noexcept;
  OutputMaintenanceReport makeReport() const noexcept;
  void failClosed() noexcept;

  OutputPolicyConfig policy_{};
  OutputSupervisorLifecycle& lifecycle_;
  OutputAutomationControl& automation_control_;
  OutputLifecycleExecutor& lifecycle_executor_;
  OutputStateStore& state_store_;
  OutputSupervisorResolverConfig resolver_config_{};
  OutputTransport& raw_transport_;
  bool valid_{false};
  bool enter_pending_{false};
  bool exit_pending_{false};
  bool rearm_pending_{false};
  bool raw_pending_{false};
  OutputCommand raw_command_{};
  bool has_raw_result_{false};
  TxResult last_raw_transport_{};
  OutputMaintenanceStatus last_terminal_status_{OutputMaintenanceStatus::Ready};
  std::uint64_t sequence_{0U};
};

} // namespace growbox::app::output
''')

Path('src/climate/output/OutputMaintenanceControl.cpp').write_text(r'''#include "climate/output/OutputMaintenanceControl.h"

#include <cstddef>

namespace growbox::app::output {

OutputMaintenanceControl::OutputMaintenanceControl(
    const OutputPolicyConfig& policy, OutputSupervisorLifecycle& lifecycle,
    OutputAutomationControl& automation_control, OutputLifecycleExecutor& lifecycle_executor,
    OutputStateStore& state_store, OutputSupervisorResolverConfig resolver_config,
    OutputTransport& raw_transport) noexcept
    : policy_(policy), lifecycle_(lifecycle), automation_control_(automation_control),
      lifecycle_executor_(lifecycle_executor), state_store_(state_store),
      resolver_config_(resolver_config), raw_transport_(raw_transport) {
  valid_ = validateOutputPolicyConfig(policy_) == OutputPolicyConfigStatus::Ok &&
           lifecycle_.valid() && automation_control_.valid() && lifecycle_executor_.valid() &&
           state_store_.valid() && resolver_config_.count == policy_.count &&
           resolver_config_.count > 0U && resolver_config_.count <= kOutputEndpointCapacity;
  if (!valid_) {
    last_terminal_status_ = OutputMaintenanceStatus::Invalid;
    return;
  }
  for (std::size_t index = 0U; index < policy_.count; ++index) {
    const auto endpoint = policy_.endpoints[index].endpoint;
    if (state_store_.find(endpoint) == nullptr || findBinding(endpoint) == nullptr) {
      valid_ = false;
      last_terminal_status_ = OutputMaintenanceStatus::Invalid;
      return;
    }
  }
}

const OutputSupervisorEndpointBinding*
OutputMaintenanceControl::findBinding(OutputEndpointId endpoint) const noexcept {
  const OutputSupervisorEndpointBinding* found = nullptr;
  for (std::size_t index = 0U; index < resolver_config_.count; ++index) {
    const auto& candidate = resolver_config_.endpoints[index];
    if (candidate.endpoint != endpoint) {
      continue;
    }
    if (found != nullptr) {
      return nullptr;
    }
    found = &candidate;
  }
  return found;
}

const SafetyEndpointConstraint*
OutputMaintenanceControl::findSafety(const SafetyEnvelope& safety,
                                     OutputEndpointId endpoint) noexcept {
  for (const auto& candidate : safety.endpoints) {
    if (safetyConstraintActive(candidate) && candidate.endpoint == endpoint) {
      return &candidate;
    }
  }
  return nullptr;
}

bool OutputMaintenanceControl::safetyVetoes(const SafetyEndpointConstraint* safety,
                                            BinaryOutputState state) noexcept {
  if (safety == nullptr || safety->constraint == SafetyConstraint::Allow) {
    return false;
  }
  if (safety->constraint == SafetyConstraint::Inhibit) {
    return true;
  }
  if (safety->constraint == SafetyConstraint::ForceOff) {
    return state == BinaryOutputState::On;
  }
  if (safety->constraint == SafetyConstraint::ForceOn) {
    return state == BinaryOutputState::Off;
  }
  return true;
}

bool OutputMaintenanceControl::binaryStateValid(BinaryOutputState state) noexcept {
  return state == BinaryOutputState::Off || state == BinaryOutputState::On;
}

std::uint64_t OutputMaintenanceControl::nextSequence() noexcept {
  ++sequence_;
  if (sequence_ == 0U) {
    ++sequence_;
  }
  return sequence_;
}

bool OutputMaintenanceControl::clearPhysicalUncertainty(OutputEndpointId endpoint) noexcept {
  return state_store_.clearPhysicalObservation(endpoint);
}

bool OutputMaintenanceControl::clearPhysicalUncertainty() noexcept {
  for (std::size_t index = 0U; index < policy_.count; ++index) {
    if (!clearPhysicalUncertainty(policy_.endpoints[index].endpoint)) {
      return false;
    }
  }
  return true;
}

void OutputMaintenanceControl::synchronizeBinary(const OutputCommand& command,
                                                 std::uint64_t monotonic_ms) noexcept {
  const auto* binding = findBinding(command.endpoint);
  if (binding != nullptr && binding->binary_policy != nullptr) {
    binding->binary_policy->synchronize(command.state, monotonic_ms);
  }
}

void OutputMaintenanceControl::failClosed() noexcept {
  enter_pending_ = false;
  exit_pending_ = false;
  rearm_pending_ = false;
  raw_pending_ = false;
  last_terminal_status_ = OutputMaintenanceStatus::FaultLocked;
  if (lifecycle_.valid() && lifecycle_.mode() != SupervisorMode::FaultLocked) {
    (void)lifecycle_.apply(OutputLifecycleCommand::EnterFault);
  }
}

bool OutputMaintenanceControl::requestEnter() noexcept {
  if (!valid_ || exit_pending_ || rearm_pending_ || raw_pending_ || enter_pending_) {
    return false;
  }
  if (lifecycle_.mode() == SupervisorMode::MaintenanceLocked) {
    return true;
  }
  if (lifecycle_.mode() == SupervisorMode::Automatic) {
    if (automation_control_.transitionActive() || !automation_control_.requestEnabled(false)) {
      last_terminal_status_ = OutputMaintenanceStatus::Busy;
      return false;
    }
    enter_pending_ = true;
    last_terminal_status_ = OutputMaintenanceStatus::EnterPending;
    return true;
  }
  if (lifecycle_.mode() == SupervisorMode::Disabled &&
      !automation_control_.transitionActive() && !lifecycle_executor_.active()) {
    enter_pending_ = true;
    last_terminal_status_ = OutputMaintenanceStatus::EnterPending;
    return true;
  }
  last_terminal_status_ = OutputMaintenanceStatus::ModeDenied;
  return false;
}

bool OutputMaintenanceControl::requestExit() noexcept {
  if (!valid_ || enter_pending_ || exit_pending_ || rearm_pending_ || raw_pending_) {
    return false;
  }
  if (lifecycle_.mode() != SupervisorMode::MaintenanceLocked ||
      automation_control_.transitionActive() || lifecycle_executor_.active()) {
    last_terminal_status_ = OutputMaintenanceStatus::ModeDenied;
    return false;
  }
  exit_pending_ = true;
  last_terminal_status_ = OutputMaintenanceStatus::ExitPending;
  return true;
}

bool OutputMaintenanceControl::requestRaw(OutputEndpointRole role, BinaryOutputState state,
                                          std::uint64_t monotonic_ms) noexcept {
  if (!valid_ || enter_pending_ || exit_pending_ || rearm_pending_ || raw_pending_) {
    last_terminal_status_ = OutputMaintenanceStatus::Busy;
    return false;
  }
  if (lifecycle_.mode() != SupervisorMode::MaintenanceLocked ||
      automation_control_.transitionActive() || lifecycle_executor_.active()) {
    last_terminal_status_ = OutputMaintenanceStatus::ModeDenied;
    return false;
  }
  if (!binaryStateValid(state)) {
    last_terminal_status_ = OutputMaintenanceStatus::Invalid;
    return false;
  }
  const auto* endpoint = findOutputPolicyRole(policy_, role);
  if (endpoint == nullptr || !isValidOutputEndpoint(endpoint->endpoint)) {
    last_terminal_status_ = OutputMaintenanceStatus::Invalid;
    return false;
  }
  raw_command_ = {};
  raw_command_.endpoint = endpoint->endpoint;
  raw_command_.state = state;
  raw_command_.source = OutputSource::Maintenance;
  raw_command_.reason = OutputReason::MaintenanceRequest;
  raw_command_.sequence = nextSequence();
  raw_command_.due_ms = monotonic_ms;
  raw_pending_ = true;
  has_raw_result_ = false;
  last_raw_transport_ = {};
  last_terminal_status_ = OutputMaintenanceStatus::RawPending;
  return true;
}

OutputMaintenanceReport OutputMaintenanceControl::tick(std::uint64_t monotonic_ms,
                                                        const SafetyEnvelope& safety) noexcept {
  if (!valid_) {
    last_terminal_status_ = OutputMaintenanceStatus::Invalid;
    return makeReport();
  }
  if (lifecycle_.mode() == SupervisorMode::FaultLocked) {
    enter_pending_ = false;
    exit_pending_ = false;
    rearm_pending_ = false;
    raw_pending_ = false;
    last_terminal_status_ = OutputMaintenanceStatus::FaultLocked;
    return makeReport();
  }

  if (rearm_pending_) {
    if (lifecycle_.mode() == SupervisorMode::Automatic &&
        !automation_control_.transitionActive()) {
      rearm_pending_ = false;
      last_terminal_status_ = OutputMaintenanceStatus::Ready;
    }
    return makeReport();
  }

  if (enter_pending_) {
    if (automation_control_.transitionActive() || lifecycle_executor_.active()) {
      return makeReport();
    }
    if (lifecycle_.mode() == SupervisorMode::MaintenanceLocked) {
      enter_pending_ = false;
      last_terminal_status_ = OutputMaintenanceStatus::Ready;
      return makeReport();
    }
    if (lifecycle_.mode() != SupervisorMode::Disabled) {
      failClosed();
      return makeReport();
    }
    const auto transition = lifecycle_.apply(OutputLifecycleCommand::EnterMaintenance);
    if (transition.status != OutputLifecycleTransitionStatus::Applied ||
        lifecycle_.mode() != SupervisorMode::MaintenanceLocked ||
        !clearPhysicalUncertainty()) {
      failClosed();
      return makeReport();
    }
    enter_pending_ = false;
    last_terminal_status_ = OutputMaintenanceStatus::Ready;
    return makeReport();
  }

  if (exit_pending_) {
    if (lifecycle_.mode() != SupervisorMode::MaintenanceLocked ||
        automation_control_.transitionActive() || lifecycle_executor_.active()) {
      failClosed();
      return makeReport();
    }
    const auto transition = lifecycle_.apply(OutputLifecycleCommand::ExitMaintenance);
    if (transition.status != OutputLifecycleTransitionStatus::Applied ||
        lifecycle_.mode() != SupervisorMode::Disabled ||
        !automation_control_.requestEnabled(true)) {
      failClosed();
      return makeReport();
    }
    exit_pending_ = false;
    rearm_pending_ = true;
    last_terminal_status_ = OutputMaintenanceStatus::ExitPending;
    return makeReport();
  }

  if (raw_pending_) {
    if (lifecycle_.mode() != SupervisorMode::MaintenanceLocked ||
        automation_control_.transitionActive() || lifecycle_executor_.active()) {
      raw_pending_ = false;
      last_terminal_status_ = OutputMaintenanceStatus::ModeDenied;
      return makeReport();
    }
    if (safetyVetoes(findSafety(safety, raw_command_.endpoint), raw_command_.state)) {
      raw_pending_ = false;
      has_raw_result_ = false;
      last_raw_transport_ = {};
      last_terminal_status_ = OutputMaintenanceStatus::SafetyVeto;
      return makeReport();
    }
    raw_command_.due_ms = monotonic_ms;
    if (!state_store_.recordDesired(raw_command_) || !state_store_.recordResolved(raw_command_) ||
        !clearPhysicalUncertainty(raw_command_.endpoint)) {
      failClosed();
      return makeReport();
    }
    const TxResult tx = raw_transport_.send(raw_command_);
    if (!state_store_.recordAttempt(raw_command_, monotonic_ms, tx)) {
      failClosed();
      return makeReport();
    }
    has_raw_result_ = true;
    last_raw_transport_ = tx;
    raw_pending_ = false;
    if (tx.status == TransportStatus::Completed) {
      synchronizeBinary(raw_command_, monotonic_ms);
      last_terminal_status_ = OutputMaintenanceStatus::Ready;
    } else {
      last_terminal_status_ = OutputMaintenanceStatus::TxFailed;
    }
  }
  return makeReport();
}

OutputMaintenanceReport OutputMaintenanceControl::makeReport() const noexcept {
  OutputMaintenanceReport value{};
  value.status = last_terminal_status_;
  value.mode = lifecycle_.mode();
  value.enter_pending = enter_pending_;
  value.exit_pending = exit_pending_;
  value.rearm_pending = rearm_pending_;
  value.raw_pending = raw_pending_;
  value.has_raw_result = has_raw_result_;
  value.raw_command = raw_command_;
  value.raw_transport = last_raw_transport_;
  value.physical = PhysicalOutputState::Unknown;
  if (!valid_) {
    value.status = OutputMaintenanceStatus::Invalid;
  } else if (value.mode == SupervisorMode::FaultLocked) {
    value.status = OutputMaintenanceStatus::FaultLocked;
  } else if (enter_pending_) {
    value.status = OutputMaintenanceStatus::EnterPending;
  } else if (exit_pending_ || rearm_pending_) {
    value.status = OutputMaintenanceStatus::ExitPending;
  } else if (raw_pending_) {
    value.status = OutputMaintenanceStatus::RawPending;
  }
  return value;
}

OutputMaintenanceReport OutputMaintenanceControl::report() const noexcept { return makeReport(); }

} // namespace growbox::app::output
''')

replace_once(
    'src/climate/output/OutputStateStore.h',
    '  bool recordPhysicalObservation(OutputEndpointId endpoint, PhysicalOutputState state,\n'
    '                                 std::uint64_t observed_ms,\n'
    '                                 std::uint64_t sequence = 0U) noexcept;\n',
    '  bool recordPhysicalObservation(OutputEndpointId endpoint, PhysicalOutputState state,\n'
    '                                 std::uint64_t observed_ms,\n'
    '                                 std::uint64_t sequence = 0U) noexcept;\n'
    '  bool clearPhysicalObservation(OutputEndpointId endpoint) noexcept;\n',
)
replace_once(
    'src/climate/output/OutputStateStore.cpp',
    'bool OutputStateStore::recordPhysicalObservation(OutputEndpointId endpoint,\n'
    '                                                 PhysicalOutputState state,\n'
    '                                                 std::uint64_t observed_ms,\n'
    '                                                 std::uint64_t sequence) noexcept {\n'
    '  OutputStateEntry* entry = findMutable(endpoint);\n'
    '  if (entry == nullptr) {\n'
    '    return false;\n'
    '  }\n'
    '  entry->physical.state = state;\n'
    '  entry->physical.has_independent_feedback = true;\n'
    '  entry->physical.observed_ms = observed_ms;\n'
    '  entry->physical.sequence = sequence;\n'
    '  return true;\n'
    '}\n',
    'bool OutputStateStore::recordPhysicalObservation(OutputEndpointId endpoint,\n'
    '                                                 PhysicalOutputState state,\n'
    '                                                 std::uint64_t observed_ms,\n'
    '                                                 std::uint64_t sequence) noexcept {\n'
    '  OutputStateEntry* entry = findMutable(endpoint);\n'
    '  if (entry == nullptr) {\n'
    '    return false;\n'
    '  }\n'
    '  entry->physical.state = state;\n'
    '  entry->physical.has_independent_feedback = true;\n'
    '  entry->physical.observed_ms = observed_ms;\n'
    '  entry->physical.sequence = sequence;\n'
    '  return true;\n'
    '}\n\n'
    'bool OutputStateStore::clearPhysicalObservation(OutputEndpointId endpoint) noexcept {\n'
    '  OutputStateEntry* entry = findMutable(endpoint);\n'
    '  if (entry == nullptr) {\n'
    '    return false;\n'
    '  }\n'
    '  entry->physical = {};\n'
    '  return true;\n'
    '}\n',
)

Path('src/climate/runtime/Stage28MaintenanceRfTransport.h').write_text(r'''#pragma once

#include "climate/output/OutputTransport.h"
#include "climate/runtime/Stage28RfDiagnostics.h"

namespace growbox::app::climate_io::runtime {

class Stage28MaintenanceRfTransport final : public ::growbox::app::output::OutputTransport {
public:
  explicit Stage28MaintenanceRfTransport(Stage28RfDiagnostics& diagnostics) noexcept
      : diagnostics_(diagnostics) {}

  ::growbox::app::output::TxResult
  send(const ::growbox::app::output::OutputCommand& command) noexcept override;

private:
  Stage28RfDiagnostics& diagnostics_;
};

} // namespace growbox::app::climate_io::runtime
''')

Path('src/climate/runtime/Stage28MaintenanceRfTransport.cpp').write_text(r'''#include "climate/runtime/Stage28MaintenanceRfTransport.h"

#include "climate/rf433/ClimateRf433EndpointRegistry.h"

namespace growbox::app::climate_io::runtime {

::growbox::app::output::TxResult
Stage28MaintenanceRfTransport::send(const ::growbox::app::output::OutputCommand& command) noexcept {
  using ::growbox::app::output::BinaryOutputState;
  using ::growbox::app::output::OutputReason;
  using ::growbox::app::output::OutputSource;
  using ::growbox::app::output::TransportError;
  using ::growbox::app::output::TransportStatus;

  if (command.source != OutputSource::Maintenance ||
      command.reason != OutputReason::MaintenanceRequest) {
    return {TransportStatus::Failed, TransportError::InvalidCommand};
  }
  if (command.state != BinaryOutputState::Off && command.state != BinaryOutputState::On) {
    return {TransportStatus::Failed, TransportError::InvalidCommand};
  }
  const auto* binding = rf433::findClimateRf433Endpoint(command.endpoint);
  if (binding == nullptr || binding->hardware == nullptr) {
    return {TransportStatus::Failed, TransportError::InvalidEndpoint};
  }
  if (!diagnostics_.ready()) {
    return {TransportStatus::Failed, TransportError::Unavailable};
  }
  const auto& frame = command.state == BinaryOutputState::On ? binding->hardware->on
                                                              : binding->hardware->off;
  rf433::LoopbackEvidence evidence{};
  if (!diagnostics_.manualTransmit(frame, evidence)) {
    return {TransportStatus::Failed, TransportError::IoFailure};
  }
  return {TransportStatus::Completed, TransportError::None};
}

} // namespace growbox::app::climate_io::runtime
''')

replace_once(
    'src/CMakeLists.txt',
    '    "climate/output/OutputManualControl.cpp"\n',
    '    "climate/output/OutputManualControl.cpp"\n    "climate/output/OutputMaintenanceControl.cpp"\n',
)
replace_once(
    'src/CMakeLists.txt',
    '      "climate/runtime/Stage28RfDiagnostics.cpp"\n',
    '      "climate/runtime/Stage28RfDiagnostics.cpp"\n      "climate/runtime/Stage28MaintenanceRfTransport.cpp"\n',
)

replace_once(
    'src/climate/runtime/Stage28ServiceConsoleCommand.h',
    '  AutomationDisable,\n',
    '  AutomationDisable,\n  MaintenanceStatus,\n  MaintenanceEnter,\n  MaintenanceExit,\n  MaintenanceRawOutput,\n',
)
replace_once(
    'src/climate/runtime/Stage28ServiceConsoleCommand.cpp',
    '  if (equalsIgnoreCase(tokens[0],"automation")) {\n'
    '    if (count==1U || (count==2U && equalsIgnoreCase(tokens[1],"status"))) { command.kind=ServiceConsoleCommandKind::AutomationStatus; return command; }\n'
    '    if (count==2U && equalsIgnoreCase(tokens[1],"on")) { command.kind=ServiceConsoleCommandKind::AutomationEnable; return command; }\n'
    '    if (count==2U && equalsIgnoreCase(tokens[1],"off")) { command.kind=ServiceConsoleCommandKind::AutomationDisable; return command; }\n'
    '    return invalidCommand();\n'
    '  }\n',
    '  if (equalsIgnoreCase(tokens[0],"automation")) {\n'
    '    if (count==1U || (count==2U && equalsIgnoreCase(tokens[1],"status"))) { command.kind=ServiceConsoleCommandKind::AutomationStatus; return command; }\n'
    '    if (count==2U && equalsIgnoreCase(tokens[1],"on")) { command.kind=ServiceConsoleCommandKind::AutomationEnable; return command; }\n'
    '    if (count==2U && equalsIgnoreCase(tokens[1],"off")) { command.kind=ServiceConsoleCommandKind::AutomationDisable; return command; }\n'
    '    return invalidCommand();\n'
    '  }\n'
    '  if (equalsIgnoreCase(tokens[0],"maintenance")) {\n'
    '    if (count==1U || (count==2U && equalsIgnoreCase(tokens[1],"status"))) { command.kind=ServiceConsoleCommandKind::MaintenanceStatus; return command; }\n'
    '    if (count==2U && equalsIgnoreCase(tokens[1],"enter")) { command.kind=ServiceConsoleCommandKind::MaintenanceEnter; return command; }\n'
    '    if (count==2U && equalsIgnoreCase(tokens[1],"exit")) { command.kind=ServiceConsoleCommandKind::MaintenanceExit; return command; }\n'
    '    return invalidCommand();\n'
    '  }\n',
)
replace_once(
    'src/climate/runtime/Stage28ServiceConsoleCommand.cpp',
    '  if (count==2U && equalsIgnoreCase(tokens[1],"list")) { command.kind=ServiceConsoleCommandKind::RfList; return command; }\n'
    '  if (equalsIgnoreCase(tokens[1],"rx")) {\n',
    '  if (count==2U && equalsIgnoreCase(tokens[1],"list")) { command.kind=ServiceConsoleCommandKind::RfList; return command; }\n'
    '  if (count==4U && equalsIgnoreCase(tokens[1],"raw") && parseDevice(tokens[2],command.device) && parseState(tokens[3],command.state)) { command.kind=ServiceConsoleCommandKind::MaintenanceRawOutput; return command; }\n'
    '  if (equalsIgnoreCase(tokens[1],"rx")) {\n',
)

replace_once(
    'src/climate/runtime/Stage28ServiceConsole.h',
    'class OutputManualControl;\n',
    'class OutputManualControl;\nclass OutputMaintenanceControl;\n',
)
replace_once(
    'src/climate/runtime/Stage28ServiceConsole.h',
    '    ::growbox::app::output::OutputManualControl* manual_control{nullptr};\n',
    '    ::growbox::app::output::OutputManualControl* manual_control{nullptr};\n'
    '    ::growbox::app::output::OutputMaintenanceControl* maintenance_control{nullptr};\n',
)
replace_once(
    'src/climate/runtime/Stage28ServiceConsole.h',
    '  void handleAutomationRequest(bool enabled) noexcept;\n',
    '  void handleAutomationRequest(bool enabled) noexcept;\n'
    '  void printMaintenanceStatus() noexcept;\n'
    '  void handleMaintenanceRequest(bool enter) noexcept;\n'
    '  void handleMaintenanceRaw(const ServiceConsoleCommand& command, std::uint64_t now_ms) noexcept;\n',
)

replace_once(
    'src/climate/runtime/Stage28ServiceConsole.cpp',
    '#include "climate/output/OutputManualControl.h"\n',
    '#include "climate/output/OutputManualControl.h"\n#include "climate/output/OutputMaintenanceControl.h"\n',
)
replace_once(
    'src/climate/runtime/Stage28ServiceConsole.cpp',
    '  case ServiceConsoleCommandKind::AutomationDisable:\n    handleAutomationRequest(false);\n    return;\n',
    '  case ServiceConsoleCommandKind::AutomationDisable:\n    handleAutomationRequest(false);\n    return;\n'
    '  case ServiceConsoleCommandKind::MaintenanceStatus:\n    printMaintenanceStatus();\n    return;\n'
    '  case ServiceConsoleCommandKind::MaintenanceEnter:\n    handleMaintenanceRequest(true);\n    return;\n'
    '  case ServiceConsoleCommandKind::MaintenanceExit:\n    handleMaintenanceRequest(false);\n    return;\n'
    '  case ServiceConsoleCommandKind::MaintenanceRawOutput:\n    handleMaintenanceRaw(command, now_ms);\n    return;\n',
)
replace_once(
    'src/climate/runtime/Stage28ServiceConsole.cpp',
    '  writeText("  automation on|off                request high-level automation mode\\r\\n");\n',
    '  writeText("  automation on|off                request high-level automation mode\\r\\n");\n'
    '  writeText("  maintenance [status]             show maintenance lock state\\r\\n");\n'
    '  writeText("  maintenance enter|exit           safe enter / explicit re-arm exit\\r\\n");\n',
)
replace_once(
    'src/climate/runtime/Stage28ServiceConsole.cpp',
    '  writeText("  rf <device> on|off               compatibility alias for output command\\r\\n");\n'
    '  writeText("  rf rx [50..5000]                 capture/decode one RF frame\\r\\n");\n',
    '  writeText("  rf <device> on|off               compatibility alias for output command\\r\\n");\n'
    '  writeText("  rf raw <device> on|off           maintenance-only raw RF diagnostic TX\\r\\n");\n'
    '  writeText("  rf rx [50..5000]                 capture/decode one RF frame\\r\\n");\n',
)
replace_once(
    'src/climate/runtime/Stage28ServiceConsole.cpp',
    '  writeText("Manual output completion is command truth, not physical load acknowledgement.\\r\\n");\n',
    '  writeText("Manual output completion is command truth, not physical load acknowledgement.\\r\\n");\n'
    '  writeText("Raw RF TX requires MaintenanceLocked and is vetoed by conflicting hard safety.\\r\\n");\n',
)

maintenance_methods = r'''
void Stage28ServiceConsole::printMaintenanceStatus() noexcept {
  if (config_.maintenance_control == nullptr) {
    writeText("maintenance unavailable\r\n");
    return;
  }
  const auto report = config_.maintenance_control->report();
  writeFormatted(
      "maintenance mode=%s status=%u enter_pending=%d exit_pending=%d rearm_pending=%d "
      "raw_pending=%d raw_result=%d raw_endpoint=%u raw_state=%u tx_status=%u tx_error=%u "
      "physical_state=unknown\r\n",
      supervisorModeName(report.mode), static_cast<unsigned>(report.status), report.enter_pending,
      report.exit_pending, report.rearm_pending, report.raw_pending, report.has_raw_result,
      static_cast<unsigned>(report.raw_command.endpoint),
      static_cast<unsigned>(report.raw_command.state),
      static_cast<unsigned>(report.raw_transport.status),
      static_cast<unsigned>(report.raw_transport.error));
}

void Stage28ServiceConsole::handleMaintenanceRequest(bool enter) noexcept {
  if (config_.maintenance_control == nullptr) {
    writeText("error: maintenance control unavailable\r\n");
    return;
  }
  const bool accepted = enter ? config_.maintenance_control->requestEnter()
                              : config_.maintenance_control->requestExit();
  writeFormatted("maintenance request=%s accepted=%d mode=%s\r\n",
                 enter ? "enter" : "exit", accepted,
                 supervisorModeName(config_.maintenance_control->mode()));
}

void Stage28ServiceConsole::handleMaintenanceRaw(const ServiceConsoleCommand& command,
                                                 std::uint64_t now_ms) noexcept {
  if (config_.maintenance_control == nullptr) {
    writeText("error: maintenance control unavailable\r\n");
    return;
  }
  ::growbox::app::output::OutputEndpointRole role =
      ::growbox::app::output::OutputEndpointRole::ScheduledLight;
  switch (command.device) {
  case ServiceConsoleRfDevice::Lamp:
    role = ::growbox::app::output::OutputEndpointRole::ScheduledLight;
    break;
  case ServiceConsoleRfDevice::Fan:
    role = ::growbox::app::output::OutputEndpointRole::ExhaustFan;
    break;
  case ServiceConsoleRfDevice::Humidifier:
    role = ::growbox::app::output::OutputEndpointRole::Humidifier;
    break;
  }
  const auto state = command.state == ServiceConsoleRfState::On
                         ? ::growbox::app::output::BinaryOutputState::On
                         : ::growbox::app::output::BinaryOutputState::Off;
  const bool accepted = config_.maintenance_control->requestRaw(role, state, now_ms);
  writeFormatted("maintenance_raw device=%s state=%s accepted=%d mode=%s queued_only=1 "
                 "physical_state=unknown\r\n",
                 serviceConsoleRfDeviceName(command.device), serviceConsoleRfStateName(command.state),
                 accepted, supervisorModeName(config_.maintenance_control->mode()));
}

'''
replace_once(
    'src/climate/runtime/Stage28ServiceConsole.cpp',
    'void Stage28ServiceConsole::printStatus(std::uint64_t now_ms) noexcept {\n',
    maintenance_methods + 'void Stage28ServiceConsole::printStatus(std::uint64_t now_ms) noexcept {\n',
)
replace_once(
    'src/climate/runtime/Stage28ServiceConsole.cpp',
    '  if (config_.automation_control != nullptr) {\n    printAutomationStatus();\n  }\n',
    '  if (config_.automation_control != nullptr) {\n    printAutomationStatus();\n  }\n'
    '  if (config_.maintenance_control != nullptr) {\n    printMaintenanceStatus();\n  }\n',
)

replace_once(
    'src/climate/ClimateV6RealInputRuntime.cpp',
    '#include "climate/output/OutputManualControl.h"\n',
    '#include "climate/output/OutputManualControl.h"\n#include "climate/output/OutputMaintenanceControl.h"\n',
)
replace_once(
    'src/climate/ClimateV6RealInputRuntime.cpp',
    '#include "climate/runtime/Stage28RfDiagnostics.h"\n',
    '#include "climate/runtime/Stage28RfDiagnostics.h"\n#include "climate/runtime/Stage28MaintenanceRfTransport.h"\n',
)
replace_once(
    'src/climate/ClimateV6RealInputRuntime.cpp',
    '  output::OutputAutomationControl automation_control(output_lifecycle, lifecycle_executor);\n'
    '  output::OutputManualControl manual_control(output_policy, output_lifecycle);\n'
    '  lifecycle_ready = lifecycle_ready && automation_control.valid() && manual_control.valid();\n',
    '  output::OutputAutomationControl automation_control(output_lifecycle, lifecycle_executor);\n'
    '  output::OutputManualControl manual_control(output_policy, output_lifecycle);\n'
    '  runtime::Stage28MaintenanceRfTransport maintenance_rf_transport(rf_diagnostics);\n'
    '  output::OutputMaintenanceControl maintenance_control(\n'
    '      output_policy, output_lifecycle, automation_control, lifecycle_executor,\n'
    '      output_state_store, supervisor_config, maintenance_rf_transport);\n'
    '  lifecycle_ready = lifecycle_ready && automation_control.valid() && manual_control.valid() &&\n'
    '                    maintenance_control.valid();\n',
)
replace_once(
    'src/climate/ClimateV6RealInputRuntime.cpp',
    '       &real_output_ready, &storage_logger, &runtime_timing, &automation_control, &manual_control},\n',
    '       &real_output_ready, &storage_logger, &runtime_timing, &automation_control, &manual_control,\n'
    '       &maintenance_control},\n',
)
replace_once(
    'src/climate/ClimateV6RealInputRuntime.cpp',
    '      const auto automation_report =\n'
    '          automation_control.tick(now_ms, schedule_intent, safety_snapshot.envelope);\n\n'
    '      output::ManualIntent manual_intent{};\n',
    '      const auto automation_report =\n'
    '          automation_control.tick(now_ms, schedule_intent, safety_snapshot.envelope);\n'
    '      const auto maintenance_report =\n'
    '          maintenance_control.tick(now_ms, safety_snapshot.envelope);\n\n'
    '      output::ManualIntent manual_intent{};\n',
)
replace_once(
    'src/climate/ClimateV6RealInputRuntime.cpp',
    '      supervisor_context.mode = automation_report.mode;\n',
    '      supervisor_context.mode = maintenance_report.mode;\n',
)

Path('test/test_output_maintenance_control').mkdir(parents=True, exist_ok=True)
Path('test/test_output_maintenance_control/test_main.cpp').write_text(r'''#include "climate/output/OutputMaintenanceControl.h"

#include <array>
#include <cassert>
#include <cstdint>

namespace {
namespace output = growbox::app::output;

class FakeTransport final : public output::OutputTransport {
public:
  output::TxResult send(const output::OutputCommand& command) noexcept override {
    ++count;
    last = command;
    return result;
  }
  output::TxResult result{output::TransportStatus::Completed, output::TransportError::None};
  output::OutputCommand last{};
  unsigned count{0U};
};

struct Fixture {
  output::OutputPolicyConfig policy{output::makeSafeDefaultOutputPolicyConfig(1U, 2U, 3U)};
  output::OutputStateStore state{};
  output::BinaryActuatorPolicy fan{};
  output::BinaryActuatorPolicy humidifier{};
  output::OutputSupervisorResolverConfig resolver{};
  output::OutputSupervisorLifecycle lifecycle{policy};
  FakeTransport lifecycle_transport{};
  output::OutputLifecycleExecutor executor;
  output::OutputAutomationControl automation;
  FakeTransport raw_transport{};
  output::OutputMaintenanceControl maintenance;

  Fixture()
      : executor(policy, lifecycle, lifecycle_transport, state, configureResolver()),
        automation(lifecycle, executor),
        maintenance(policy, lifecycle, automation, executor, state, resolver, raw_transport) {
    assert(output::validateOutputPolicyConfig(policy) == output::OutputPolicyConfigStatus::Ok);
    assert(state.valid());
    assert(executor.valid());
    assert(automation.valid());
    assert(maintenance.valid());
  }

  output::OutputSupervisorResolverConfig configureResolver() {
    const std::array<output::OutputEndpointId, output::kOutputEndpointCapacity> endpoints{1U, 2U, 3U};
    assert(state.configure(endpoints, endpoints.size()));
    resolver.endpoints[0] = {1U, &fan};
    resolver.endpoints[1] = {2U, nullptr};
    resolver.endpoints[2] = {3U, &humidifier};
    resolver.count = 3U;
    return resolver;
  }

  output::ScheduleIntent scheduleOff() const {
    output::ScheduleIntent schedule{};
    schedule.metadata.source = output::OutputSource::Schedule;
    schedule.metadata.reason = output::OutputReason::ScheduleRequest;
    assert(output::setEndpointIntent(schedule.endpoints[0], 2U, 0.0F));
    return schedule;
  }

  void bootstrapAutomatic() {
    const auto begin = lifecycle.apply(output::OutputLifecycleCommand::BeginArming);
    assert(begin.status == output::OutputLifecycleTransitionStatus::Applied);
    assert(executor.start(begin, 0U, scheduleOff()));
    for (std::uint64_t now = 0U; executor.active() && now < 10U; ++now) {
      executor.tick(now);
    }
    assert(!executor.active());
    const auto armed = lifecycle.apply(output::OutputLifecycleCommand::ArmingSucceeded);
    assert(armed.status == output::OutputLifecycleTransitionStatus::Applied);
    assert(lifecycle.mode() == output::SupervisorMode::Automatic);
  }

  void enterMaintenance(output::SafetyEnvelope safety = {}) {
    assert(maintenance.requestEnter());
    for (std::uint64_t now = 100U; now < 120U &&
         lifecycle.mode() != output::SupervisorMode::MaintenanceLocked; ++now) {
      automation.tick(now, scheduleOff(), safety);
      maintenance.tick(now, safety);
    }
    assert(lifecycle.mode() == output::SupervisorMode::MaintenanceLocked);
    assert(!maintenance.transitionActive());
  }
};

void testRawDeniedOutsideMaintenance() {
  Fixture f;
  f.bootstrapAutomatic();
  assert(!f.maintenance.requestRaw(output::OutputEndpointRole::ScheduledLight,
                                   output::BinaryOutputState::On, 10U));
  assert(f.raw_transport.count == 0U);
}

void testSafeEntryCompletesBeforeMaintenanceAndClearsPhysicalTruth() {
  Fixture f;
  f.bootstrapAutomatic();
  assert(f.state.recordPhysicalObservation(2U, output::PhysicalOutputState::On, 50U, 1U));
  const unsigned before = f.lifecycle_transport.count;
  assert(f.maintenance.requestEnter());
  f.automation.tick(100U, f.scheduleOff(), {});
  auto report = f.maintenance.tick(100U, {});
  assert(report.mode == output::SupervisorMode::Disabled);
  assert(report.enter_pending);
  assert(f.lifecycle.mode() != output::SupervisorMode::MaintenanceLocked);
  for (std::uint64_t now = 101U; now < 120U &&
       f.lifecycle.mode() != output::SupervisorMode::MaintenanceLocked; ++now) {
    f.automation.tick(now, f.scheduleOff(), {});
    report = f.maintenance.tick(now, {});
  }
  assert(f.lifecycle.mode() == output::SupervisorMode::MaintenanceLocked);
  assert(f.lifecycle_transport.count >= before + 3U);
  const auto* lamp = f.state.find(2U);
  assert(lamp != nullptr);
  assert(!lamp->physical.has_independent_feedback);
  assert(lamp->physical.state == output::PhysicalOutputState::Unknown);
}

void testHardSafetyVetoAndAlignedRawCommand() {
  Fixture f;
  f.bootstrapAutomatic();
  f.enterMaintenance();

  output::SafetyEnvelope safety{};
  assert(output::setSafetyConstraint(safety.endpoints[0], 1U, output::SafetyConstraint::ForceOn,
                                     output::OutputReason::ThermalSafety));
  assert(f.maintenance.requestRaw(output::OutputEndpointRole::ExhaustFan,
                                  output::BinaryOutputState::Off, 200U));
  auto report = f.maintenance.tick(200U, safety);
  assert(report.status == output::OutputMaintenanceStatus::SafetyVeto);
  assert(f.raw_transport.count == 0U);

  assert(f.maintenance.requestRaw(output::OutputEndpointRole::ExhaustFan,
                                  output::BinaryOutputState::On, 201U));
  report = f.maintenance.tick(201U, safety);
  assert(report.status == output::OutputMaintenanceStatus::Ready);
  assert(report.has_raw_result);
  assert(f.raw_transport.count == 1U);
  assert(f.raw_transport.last.source == output::OutputSource::Maintenance);
  assert(f.raw_transport.last.reason == output::OutputReason::MaintenanceRequest);
  assert(f.fan.known() && f.fan.on());
  const auto* fan = f.state.find(1U);
  assert(fan != nullptr && fan->has_successful_command);
  assert(fan->last_successful_command.source == output::OutputSource::Maintenance);
  assert(fan->physical.state == output::PhysicalOutputState::Unknown);
}

void testFailedRawDoesNotAdvanceBinaryPolicy() {
  Fixture f;
  f.bootstrapAutomatic();
  f.enterMaintenance();
  assert(!f.humidifier.known() || !f.humidifier.on());
  f.raw_transport.result = {output::TransportStatus::Failed, output::TransportError::IoFailure};
  assert(f.maintenance.requestRaw(output::OutputEndpointRole::Humidifier,
                                  output::BinaryOutputState::On, 300U));
  const auto report = f.maintenance.tick(300U, {});
  assert(report.status == output::OutputMaintenanceStatus::TxFailed);
  assert(!f.humidifier.on());
  const auto* humidifier = f.state.find(3U);
  assert(humidifier != nullptr && humidifier->has_attempt);
  assert(humidifier->last_transport.status == output::TransportStatus::Failed);
  assert(!humidifier->has_successful_command ||
         humidifier->last_successful_command.state != output::BinaryOutputState::On);
}

void testExitRearmsThroughDisabledAndArming() {
  Fixture f;
  f.bootstrapAutomatic();
  f.enterMaintenance();
  assert(f.maintenance.requestExit());
  auto report = f.maintenance.tick(400U, {});
  assert(report.mode == output::SupervisorMode::Disabled);
  assert(report.rearm_pending);
  assert(f.automation.requestedEnabled());

  auto automation_report = f.automation.tick(401U, f.scheduleOff(), {});
  report = f.maintenance.tick(401U, {});
  assert(automation_report.mode == output::SupervisorMode::Arming);
  assert(report.rearm_pending);

  automation_report = f.automation.tick(402U, f.scheduleOff(), {});
  report = f.maintenance.tick(402U, {});
  assert(automation_report.mode == output::SupervisorMode::Automatic);
  assert(report.mode == output::SupervisorMode::Automatic);
  assert(!report.rearm_pending);
  assert(report.status == output::OutputMaintenanceStatus::Ready);
}

void testEntryFailureFaultLocks() {
  Fixture f;
  f.bootstrapAutomatic();
  f.lifecycle_transport.result = {output::TransportStatus::Failed, output::TransportError::IoFailure};
  assert(f.maintenance.requestEnter());
  output::OutputMaintenanceReport report{};
  for (std::uint64_t now = 500U; now < 540U &&
       f.lifecycle.mode() != output::SupervisorMode::FaultLocked; ++now) {
    f.automation.tick(now, f.scheduleOff(), {});
    report = f.maintenance.tick(now, {});
  }
  assert(f.lifecycle.mode() == output::SupervisorMode::FaultLocked);
  report = f.maintenance.tick(540U, {});
  assert(report.status == output::OutputMaintenanceStatus::FaultLocked);
  assert(f.raw_transport.count == 0U);
}

} // namespace

int main() {
  testRawDeniedOutsideMaintenance();
  testSafeEntryCompletesBeforeMaintenanceAndClearsPhysicalTruth();
  testHardSafetyVetoAndAlignedRawCommand();
  testFailedRawDoesNotAdvanceBinaryPolicy();
  testExitRearmsThroughDisabledAndArming();
  testEntryFailureFaultLocks();
  return 0;
}
''')

replace_once(
    'test/host/CMakeLists.txt',
    'target_compile_options(output_manual_control_tests PRIVATE -Wall -Wextra -Wpedantic)\n\nadd_executable(\n  climate_semantic_output_tests',
    'target_compile_options(output_manual_control_tests PRIVATE -Wall -Wextra -Wpedantic)\n\n'
    'add_executable(\n'
    '  output_maintenance_control_tests\n'
    '  "${PROJECT_ROOT}/test/test_output_maintenance_control/test_main.cpp"\n'
    '  "${PROJECT_ROOT}/src/climate/output/OutputMaintenanceControl.cpp"\n'
    '  "${PROJECT_ROOT}/src/climate/output/OutputAutomationControl.cpp"\n'
    '  "${PROJECT_ROOT}/src/climate/output/OutputLifecycleExecutor.cpp"\n'
    '  "${PROJECT_ROOT}/src/climate/output/OutputSupervisorLifecycle.cpp"\n'
    '  "${PROJECT_ROOT}/src/climate/output/OutputPolicyConfig.cpp"\n'
    '  "${PROJECT_ROOT}/src/climate/output/OutputStateStore.cpp"\n'
    '  "${PROJECT_ROOT}/src/climate/output/BinaryActuatorPolicy.cpp"\n'
    ')\n'
    'target_include_directories(output_maintenance_control_tests PRIVATE "${PROJECT_ROOT}/src")\n'
    'target_compile_features(output_maintenance_control_tests PRIVATE cxx_std_17)\n'
    'target_compile_options(output_maintenance_control_tests PRIVATE -Wall -Wextra -Wpedantic)\n\n'
    'add_executable(\n  climate_semantic_output_tests',
)
replace_once(
    'test/host/CMakeLists.txt',
    'add_test(NAME output_manual_control_tests COMMAND output_manual_control_tests)\n'
    'add_test(NAME climate_semantic_output_tests COMMAND climate_semantic_output_tests)',
    'add_test(NAME output_manual_control_tests COMMAND output_manual_control_tests)\n'
    'add_test(NAME output_maintenance_control_tests COMMAND output_maintenance_control_tests)\n'
    'add_test(NAME climate_semantic_output_tests COMMAND climate_semantic_output_tests)',
)

service_test = Path('test/test_stage28_service_console/test_main.cpp')
text = service_test.read_text()
replace_old = 'void testAutomationCommands(){auto c=parseServiceConsoleCommand("automation");assert(c.kind==ServiceConsoleCommandKind::AutomationStatus);c=parseServiceConsoleCommand("automation status");assert(c.kind==ServiceConsoleCommandKind::AutomationStatus);c=parseServiceConsoleCommand("AUTOMATION ON");assert(c.kind==ServiceConsoleCommandKind::AutomationEnable);c=parseServiceConsoleCommand("automation off");assert(c.kind==ServiceConsoleCommandKind::AutomationDisable);assert(parseServiceConsoleCommand("automation maybe").kind==ServiceConsoleCommandKind::Invalid);}\n'
replace_new = replace_old + 'void testMaintenanceCommands(){auto c=parseServiceConsoleCommand("maintenance");assert(c.kind==ServiceConsoleCommandKind::MaintenanceStatus);c=parseServiceConsoleCommand("maintenance status");assert(c.kind==ServiceConsoleCommandKind::MaintenanceStatus);c=parseServiceConsoleCommand("maintenance enter");assert(c.kind==ServiceConsoleCommandKind::MaintenanceEnter);c=parseServiceConsoleCommand("maintenance exit");assert(c.kind==ServiceConsoleCommandKind::MaintenanceExit);c=parseServiceConsoleCommand("rf raw lamp on");assert(c.kind==ServiceConsoleCommandKind::MaintenanceRawOutput&&c.device==ServiceConsoleRfDevice::Lamp&&c.state==ServiceConsoleRfState::On);c=parseServiceConsoleCommand("RF RAW FAN OFF");assert(c.kind==ServiceConsoleCommandKind::MaintenanceRawOutput&&c.device==ServiceConsoleRfDevice::Fan&&c.state==ServiceConsoleRfState::Off);assert(parseServiceConsoleCommand("rf raw lamp maybe").kind==ServiceConsoleCommandKind::Invalid);assert(parseServiceConsoleCommand("maintenance maybe").kind==ServiceConsoleCommandKind::Invalid);}\n'
if text.count(replace_old) != 1:
    raise SystemExit('service console test automation anchor mismatch')
text = text.replace(replace_old, replace_new, 1)
old_main = 'int main(){testReadOnlyMenuCommands();testAutomationCommands();testSupervisedManualOutputCommands();testRfReceiveTimeoutBounds();testRtcSetUnixCommand();testSdLogCommands();testInvalidCommandsFailClosed();return 0;}\n'
new_main = 'int main(){testReadOnlyMenuCommands();testAutomationCommands();testMaintenanceCommands();testSupervisedManualOutputCommands();testRfReceiveTimeoutBounds();testRtcSetUnixCommand();testSdLogCommands();testInvalidCommandsFailClosed();return 0;}\n'
if text.count(old_main) != 1:
    raise SystemExit('service console test main anchor mismatch')
service_test.write_text(text.replace(old_main, new_main, 1))

run(['git', 'add', '-N',
     'src/climate/output/OutputMaintenanceControl.cpp',
     'src/climate/output/OutputMaintenanceControl.h',
     'src/climate/runtime/Stage28MaintenanceRfTransport.cpp',
     'src/climate/runtime/Stage28MaintenanceRfTransport.h',
     'test/test_output_maintenance_control/test_main.cpp'])
run(['git', 'diff', '--check'])
changed = sorted(filter(None, out(['git', 'diff', '--name-only']).splitlines()))
if changed != EXPECTED:
    raise SystemExit(f'A10_2_ALLOWLIST_FAIL changed={changed!r}')

console = Path('src/climate/runtime/Stage28ServiceConsole.cpp').read_text()
maintenance = Path('src/climate/output/OutputMaintenanceControl.cpp').read_text()
runtime = Path('src/climate/ClimateV6RealInputRuntime.cpp').read_text()
maint_transport = Path('src/climate/runtime/Stage28MaintenanceRfTransport.cpp').read_text()
if 'manualTransmit(' in console:
    raise SystemExit('A10_2_STATIC_FAIL service console directly transmits RF')
if 'manualTransmit(' not in maint_transport:
    raise SystemExit('A10_2_STATIC_FAIL maintenance-only RF adapter missing raw diagnostic TX')
if 'SupervisorMode::MaintenanceLocked' not in maintenance or 'OutputLifecycleCommand::EnterMaintenance' not in maintenance:
    raise SystemExit('A10_2_STATIC_FAIL maintenance lifecycle guard missing')
if 'automation_control_.requestEnabled(false)' not in maintenance or 'automation_control_.requestEnabled(true)' not in maintenance:
    raise SystemExit('A10_2_STATIC_FAIL safe entry/re-arm path missing')
if 'safetyVetoes(' not in maintenance or 'clearPhysicalObservation' not in maintenance:
    raise SystemExit('A10_2_STATIC_FAIL safety/physical uncertainty guard missing')
if 'maintenance_control.tick(now_ms, safety_snapshot.envelope)' not in runtime:
    raise SystemExit('A10_2_STATIC_FAIL main-loop maintenance execution missing')
if 'supervisor_context.mode = maintenance_report.mode;' not in runtime:
    raise SystemExit('A10_2_STATIC_FAIL supervisor mode not sourced after maintenance tick')
print('A10_2_STATIC_PASS')

build = 'build/host-tests-a10-2-v1'
run(['cmake', '-S', 'test/host', '-B', build])
targets = [
    'output_maintenance_control_tests',
    'output_manual_control_tests',
    'output_automation_control_tests',
    'output_lifecycle_executor_tests',
    'output_supervisor_lifecycle_tests',
    'output_supervisor_resolver_tests',
    'climate_output_supervisor_sink_tests',
    'output_persistence_coordinator_tests',
    'stage28_service_console_tests',
]
run(['cmake', '--build', build, '--parallel', '--target', *targets])
regex = '^(' + '|'.join(targets) + ')$'
run(['ctest', '--test-dir', build, '-R', regex, '--output-on-failure'])
print('A10_2_FOCUSED_PASS')

fw_build = 'build/stage27c-a10-2-v1'
Path(fw_build).mkdir(parents=True, exist_ok=True)
env = os.environ.copy()
env.update({
    'STAGE27C_BUILD_DIR': fw_build,
    'STAGE27C_SDKCONFIG': f'{fw_build}/sdkconfig',
    'GROWBOX_RF433_LOOPBACK_ENABLED': '1',
    'GROWBOX_STAGE28_REAL_OUTPUTS_ENABLED': '1',
    'GROWBOX_RF433_LOOPBACK_AUTO_SMOKE': '0',
    'GROWBOX_RF433_REMOTE_CAPTURE_ENABLED': '0',
})
run(['bash', 'scripts/stage27c_crowpanel.sh', 'build'], env=env)
print('A10_2_CANONICAL_BUILD_PASS')

run(['git', 'diff', '--check'])
run(['git', 'add', *EXPECTED])
run(['git', 'diff', '--cached', '--check'])
staged = sorted(filter(None, out(['git', 'diff', '--cached', '--name-only']).splitlines()))
if staged != EXPECTED:
    raise SystemExit(f'A10_2_STAGED_ALLOWLIST_FAIL staged={staged!r}')
run(['git', 'commit', '-m', 'Guard raw RF diagnostics with maintenance mode'])
commit = out(['git', 'rev-parse', 'HEAD'])
run(['git', 'push', 'origin', f'HEAD:{BRANCH}'])
run(['git', 'fetch', '-q', 'origin', BRANCH])
if out(['git', 'rev-parse', 'FETCH_HEAD']) != commit:
    raise SystemExit('A10_2_PUSH_VERIFY_FAIL')
if out(['git', 'status', '--porcelain']):
    raise SystemExit('A10_2_CLEAN_FAIL')
print(f'A10_2_PASS commit={commit}')
