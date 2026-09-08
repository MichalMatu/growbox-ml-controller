import os
import re
import subprocess
from pathlib import Path

BASE = '819f931dfffa9cd7be7d39a82610f240bdac9236'
BRANCH = 'mvp/environment-controller'
EXPECTED = sorted([
    'src/CMakeLists.txt',
    'src/climate/ClimateV6RealInputRuntime.cpp',
    'src/climate/output/OutputManualControl.cpp',
    'src/climate/output/OutputManualControl.h',
    'src/climate/runtime/Stage28ServiceConsole.cpp',
    'src/climate/runtime/Stage28ServiceConsole.h',
    'src/climate/runtime/Stage28ServiceConsoleCommand.cpp',
    'src/climate/runtime/Stage28ServiceConsoleCommand.h',
    'test/host/CMakeLists.txt',
    'test/test_output_manual_control/test_main.cpp',
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


def regex_replace_once(path, pattern, replacement):
    p = Path(path)
    text = p.read_text()
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.S)
    if count != 1:
        raise SystemExit(f'{path}: expected one regex replacement, found {count}')
    p.write_text(updated)


run(['git', 'fetch', '-q', 'origin', BRANCH])
if out(['git', 'rev-parse', 'HEAD']) != BASE:
    raise SystemExit('A10_1_IDENTITY_FAIL local HEAD mismatch')
if out(['git', 'rev-parse', 'FETCH_HEAD']) != BASE:
    raise SystemExit('A10_1_IDENTITY_FAIL remote branch mismatch')
if out(['git', 'status', '--porcelain']):
    raise SystemExit('A10_1_IDENTITY_FAIL worktree not clean')
print('A10_1_IDENTITY_PASS')

Path('src/climate/output/OutputManualControl.h').write_text(r'''#pragma once

#include "climate/output/OutputPolicyConfig.h"
#include "climate/output/OutputSupervisorLifecycle.h"

#include <cstdint>

namespace growbox::app::output {

enum class OutputManualRequestStatus : std::uint8_t {
  Accepted = 0U,
  Busy,
  ModeDenied,
  InvalidRole,
  InvalidState,
  InvalidConfiguration,
};

struct OutputManualRequestReport {
  OutputManualRequestStatus status = OutputManualRequestStatus::InvalidConfiguration;
  SupervisorMode mode = SupervisorMode::BootLocked;
  OutputEndpointRole role = OutputEndpointRole::ScheduledLight;
  OutputEndpointId endpoint = kInvalidOutputEndpoint;
  BinaryOutputState state = BinaryOutputState::Off;
  std::uint64_t sequence = 0U;
};

class OutputManualControl final {
public:
  OutputManualControl(const OutputPolicyConfig& policy,
                      const OutputSupervisorLifecycle& lifecycle) noexcept;

  bool valid() const noexcept { return valid_; }
  bool pending() const noexcept { return pending_; }
  SupervisorMode mode() const noexcept { return lifecycle_.mode(); }

  OutputManualRequestReport request(OutputEndpointRole role, BinaryOutputState state,
                                    std::uint64_t monotonic_ms) noexcept;
  bool consume(ManualIntent& intent) noexcept;

private:
  static bool validState(BinaryOutputState state) noexcept;
  std::uint64_t nextSequence() noexcept;

  OutputPolicyConfig policy_{};
  const OutputSupervisorLifecycle& lifecycle_;
  ManualIntent pending_intent_{};
  bool valid_{false};
  bool pending_{false};
  std::uint64_t sequence_{0U};
};

} // namespace growbox::app::output
''')

Path('src/climate/output/OutputManualControl.cpp').write_text(r'''#include "climate/output/OutputManualControl.h"

namespace growbox::app::output {

OutputManualControl::OutputManualControl(const OutputPolicyConfig& policy,
                                         const OutputSupervisorLifecycle& lifecycle) noexcept
    : policy_(policy), lifecycle_(lifecycle),
      valid_(validateOutputPolicyConfig(policy_) == OutputPolicyConfigStatus::Ok &&
             lifecycle_.valid()) {}

bool OutputManualControl::validState(BinaryOutputState state) noexcept {
  return state == BinaryOutputState::Off || state == BinaryOutputState::On;
}

std::uint64_t OutputManualControl::nextSequence() noexcept {
  ++sequence_;
  if (sequence_ == 0U) {
    ++sequence_;
  }
  return sequence_;
}

OutputManualRequestReport OutputManualControl::request(OutputEndpointRole role,
                                                       BinaryOutputState state,
                                                       std::uint64_t monotonic_ms) noexcept {
  OutputManualRequestReport report{};
  report.mode = lifecycle_.mode();
  report.role = role;
  report.state = state;

  if (!valid_) {
    report.status = OutputManualRequestStatus::InvalidConfiguration;
    return report;
  }
  if (!validState(state)) {
    report.status = OutputManualRequestStatus::InvalidState;
    return report;
  }
  if (lifecycle_.mode() != SupervisorMode::Automatic) {
    report.status = OutputManualRequestStatus::ModeDenied;
    return report;
  }
  if (pending_) {
    report.status = OutputManualRequestStatus::Busy;
    return report;
  }

  const OutputEndpointPolicy* endpoint = findOutputPolicyRole(policy_, role);
  if (endpoint == nullptr || !isValidOutputEndpoint(endpoint->endpoint)) {
    report.status = OutputManualRequestStatus::InvalidRole;
    return report;
  }

  ManualIntent intent{};
  intent.metadata.sequence = nextSequence();
  intent.metadata.monotonic_ms = monotonic_ms;
  intent.metadata.source = OutputSource::Manual;
  intent.metadata.reason = OutputReason::ManualRequest;
  if (!setEndpointIntent(intent.endpoints[0], endpoint->endpoint,
                         state == BinaryOutputState::On ? 1.0F : 0.0F)) {
    report.status = OutputManualRequestStatus::InvalidRole;
    return report;
  }

  pending_intent_ = intent;
  pending_ = true;
  report.status = OutputManualRequestStatus::Accepted;
  report.endpoint = endpoint->endpoint;
  report.sequence = intent.metadata.sequence;
  return report;
}

bool OutputManualControl::consume(ManualIntent& intent) noexcept {
  intent = {};
  if (!valid_ || !pending_) {
    return false;
  }
  intent = pending_intent_;
  pending_intent_ = {};
  pending_ = false;
  return true;
}

} // namespace growbox::app::output
''')

replace_once(
    'src/CMakeLists.txt',
    '    "climate/output/OutputAutomationControl.cpp"\n',
    '    "climate/output/OutputAutomationControl.cpp"\n    "climate/output/OutputManualControl.cpp"\n',
)

replace_once(
    'src/climate/runtime/Stage28ServiceConsoleCommand.h',
    '  RfTransmit,\n',
    '  ManualOutput,\n',
)

replace_once(
    'src/climate/runtime/Stage28ServiceConsoleCommand.cpp',
    '  if (!equalsIgnoreCase(tokens[0],"rf")) return invalidCommand();\n'
    '  if (count==2U && equalsIgnoreCase(tokens[1],"list")) { command.kind=ServiceConsoleCommandKind::RfList; return command; }',
    '  if (equalsIgnoreCase(tokens[0],"output")) {\n'
    '    if (count==3U && parseDevice(tokens[1],command.device) && parseState(tokens[2],command.state)) { command.kind=ServiceConsoleCommandKind::ManualOutput; return command; }\n'
    '    return invalidCommand();\n'
    '  }\n'
    '  if (!equalsIgnoreCase(tokens[0],"rf")) return invalidCommand();\n'
    '  if (count==2U && equalsIgnoreCase(tokens[1],"list")) { command.kind=ServiceConsoleCommandKind::RfList; return command; }',
)
replace_once(
    'src/climate/runtime/Stage28ServiceConsoleCommand.cpp',
    '  if (count==3U && parseDevice(tokens[1],command.device) && parseState(tokens[2],command.state)) { command.kind=ServiceConsoleCommandKind::RfTransmit; return command; }',
    '  if (count==3U && parseDevice(tokens[1],command.device) && parseState(tokens[2],command.state)) { command.kind=ServiceConsoleCommandKind::ManualOutput; return command; }',
)

replace_once(
    'src/climate/runtime/Stage28ServiceConsole.h',
    'namespace growbox::app::output { class OutputAutomationControl; }',
    'namespace growbox::app::output {\nclass OutputAutomationControl;\nclass OutputManualControl;\n}',
)
replace_once(
    'src/climate/runtime/Stage28ServiceConsole.h',
    '    ::growbox::app::output::OutputAutomationControl* automation_control{nullptr};\n',
    '    ::growbox::app::output::OutputAutomationControl* automation_control{nullptr};\n'
    '    ::growbox::app::output::OutputManualControl* manual_control{nullptr};\n',
)
replace_once(
    'src/climate/runtime/Stage28ServiceConsole.h',
    '  void handleRfTransmit(const ServiceConsoleCommand& command) noexcept;\n',
    '  void handleManualOutput(const ServiceConsoleCommand& command, std::uint64_t now_ms) noexcept;\n',
)

replace_once(
    'src/climate/runtime/Stage28ServiceConsole.cpp',
    '#include "climate/output/OutputAutomationControl.h"\n',
    '#include "climate/output/OutputAutomationControl.h"\n#include "climate/output/OutputManualControl.h"\n',
)
replace_once(
    'src/climate/runtime/Stage28ServiceConsole.cpp',
    '  case ServiceConsoleCommandKind::RfTransmit:\n    handleRfTransmit(command);\n    return;\n',
    '  case ServiceConsoleCommandKind::ManualOutput:\n    handleManualOutput(command, now_ms);\n    return;\n',
)
replace_once(
    'src/climate/runtime/Stage28ServiceConsole.cpp',
    '  writeText("  rf lamp on|off                   manual lamp socket transmit\\r\\n");\n'
    '  writeText("  rf fan on|off                    manual fan socket transmit\\r\\n");\n'
    '  writeText("  rf humidifier on|off             manual humidifier socket transmit\\r\\n");\n',
    '  writeText("  output lamp on|off               supervised manual lamp command\\r\\n");\n'
    '  writeText("  output fan on|off                supervised manual fan command\\r\\n");\n'
    '  writeText("  output humidifier on|off         supervised manual humidifier command\\r\\n");\n'
    '  writeText("  rf <device> on|off               compatibility alias for output command\\r\\n");\n',
)
replace_once(
    'src/climate/runtime/Stage28ServiceConsole.cpp',
    '  writeText("RF transmit commands require the RF diagnostics transport to be enabled.\\r\\n");\n'
    '  writeText("Manual RF TX is blocked while automatic outputs are real-bounded.\\r\\n");\n'
    '  writeText("Manual TX is not physical load-state acknowledgement.\\r\\n");\n',
    '  writeText("Configured manual outputs are supervisor-owned and mode/safety constrained.\\r\\n");\n'
    '  writeText("Manual output completion is command truth, not physical load acknowledgement.\\r\\n");\n',
)

regex_replace_once(
    'src/climate/runtime/Stage28ServiceConsole.cpp',
    r'void Stage28ServiceConsole::handleRfTransmit\(const ServiceConsoleCommand& command\) noexcept \{.*?\n\}\n\nvoid Stage28ServiceConsole::handleRfReceive',
    r'''void Stage28ServiceConsole::handleManualOutput(const ServiceConsoleCommand& command,
                                                   std::uint64_t now_ms) noexcept {
  if (config_.manual_control == nullptr) {
    writeText("error: manual output control unavailable\r\n");
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
  const auto report = config_.manual_control->request(role, state, now_ms);
  const char* status = "invalid-configuration";
  using ::growbox::app::output::OutputManualRequestStatus;
  switch (report.status) {
  case OutputManualRequestStatus::Accepted: status = "accepted"; break;
  case OutputManualRequestStatus::Busy: status = "busy"; break;
  case OutputManualRequestStatus::ModeDenied: status = "mode-denied"; break;
  case OutputManualRequestStatus::InvalidRole: status = "invalid-role"; break;
  case OutputManualRequestStatus::InvalidState: status = "invalid-state"; break;
  case OutputManualRequestStatus::InvalidConfiguration: break;
  }

  writeFormatted(
      "manual_output device=%s state=%s accepted=%d status=%s mode=%s endpoint=%u "
      "sequence=%llu outputs=%s physical_state=unconfirmed\r\n",
      serviceConsoleRfDeviceName(command.device), serviceConsoleRfStateName(command.state),
      report.status == OutputManualRequestStatus::Accepted, status,
      supervisorModeName(report.mode), static_cast<unsigned>(report.endpoint),
      static_cast<unsigned long long>(report.sequence), outputModeName());
}

void Stage28ServiceConsole::handleRfReceive''',
)

replace_once(
    'src/climate/ClimateV6RealInputRuntime.cpp',
    '#include "climate/output/OutputLifecycleExecutor.h"\n',
    '#include "climate/output/OutputLifecycleExecutor.h"\n#include "climate/output/OutputManualControl.h"\n',
)
replace_once(
    'src/climate/ClimateV6RealInputRuntime.cpp',
    '  output::OutputAutomationControl automation_control(output_lifecycle, lifecycle_executor);\n'
    '  lifecycle_ready = lifecycle_ready && automation_control.valid();\n',
    '  output::OutputAutomationControl automation_control(output_lifecycle, lifecycle_executor);\n'
    '  output::OutputManualControl manual_control(output_policy, output_lifecycle);\n'
    '  lifecycle_ready = lifecycle_ready && automation_control.valid() && manual_control.valid();\n',
)
replace_once(
    'src/climate/ClimateV6RealInputRuntime.cpp',
    '       &real_output_ready, &storage_logger, &runtime_timing, &automation_control},\n',
    '       &real_output_ready, &storage_logger, &runtime_timing, &automation_control, &manual_control},\n',
)
replace_once(
    'src/climate/ClimateV6RealInputRuntime.cpp',
    '      ClimateOutputSupervisorCycleContext supervisor_context{};\n'
    '      supervisor_context.mode = automation_report.mode;\n'
    '      supervisor_context.schedule = schedule_intent;\n'
    '      supervisor_context.safety = safety_snapshot.envelope;\n',
    '      output::ManualIntent manual_intent{};\n'
    '      (void)manual_control.consume(manual_intent);\n\n'
    '      ClimateOutputSupervisorCycleContext supervisor_context{};\n'
    '      supervisor_context.mode = automation_report.mode;\n'
    '      supervisor_context.schedule = schedule_intent;\n'
    '      supervisor_context.manual = manual_intent;\n'
    '      supervisor_context.safety = safety_snapshot.envelope;\n',
)

Path('test/test_output_manual_control').mkdir(parents=True, exist_ok=True)
Path('test/test_output_manual_control/test_main.cpp').write_text(r'''#include "climate/output/OutputManualControl.h"

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
  const auto first = control.request(output::OutputEndpointRole::ExhaustFan,
                                     output::BinaryOutputState::On, 10U);
  assert(first.status == output::OutputManualRequestStatus::Accepted);
  const auto second = control.request(output::OutputEndpointRole::Humidifier,
                                      output::BinaryOutputState::Off, 20U);
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
  const auto report = control.request(output::OutputEndpointRole::ExhaustFan,
                                      output::BinaryOutputState::On, 0U);
  assert(report.status == output::OutputManualRequestStatus::InvalidConfiguration);
}

void testSequenceAdvancesAcrossConsumedRequests() {
  const auto config = policy();
  auto lifecycle = automaticLifecycle(config);
  output::OutputManualControl control(config, lifecycle);
  const auto first = control.request(output::OutputEndpointRole::Humidifier,
                                     output::BinaryOutputState::On, 1U);
  output::ManualIntent intent{};
  assert(control.consume(intent));
  const auto second = control.request(output::OutputEndpointRole::Humidifier,
                                      output::BinaryOutputState::Off, 2U);
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
''')

Path('test/test_stage28_service_console/test_main.cpp').write_text(r'''#include "climate/runtime/Stage28ServiceConsoleCommand.h"
#include <cassert>
#include <cstring>
using namespace growbox::app::climate_io::runtime;
namespace {
void testReadOnlyMenuCommands(){assert(parseServiceConsoleCommand("help").kind==ServiceConsoleCommandKind::Help);assert(parseServiceConsoleCommand("status").kind==ServiceConsoleCommandKind::Status);assert(parseServiceConsoleCommand("sensors").kind==ServiceConsoleCommandKind::Sensors);assert(parseServiceConsoleCommand("rf list").kind==ServiceConsoleCommandKind::RfList);}
void testAutomationCommands(){auto c=parseServiceConsoleCommand("automation");assert(c.kind==ServiceConsoleCommandKind::AutomationStatus);c=parseServiceConsoleCommand("automation status");assert(c.kind==ServiceConsoleCommandKind::AutomationStatus);c=parseServiceConsoleCommand("AUTOMATION ON");assert(c.kind==ServiceConsoleCommandKind::AutomationEnable);c=parseServiceConsoleCommand("automation off");assert(c.kind==ServiceConsoleCommandKind::AutomationDisable);assert(parseServiceConsoleCommand("automation maybe").kind==ServiceConsoleCommandKind::Invalid);}
void testSupervisedManualOutputCommands(){auto c=parseServiceConsoleCommand("output lamp on");assert(c.kind==ServiceConsoleCommandKind::ManualOutput&&c.device==ServiceConsoleRfDevice::Lamp&&c.state==ServiceConsoleRfState::On);c=parseServiceConsoleCommand("OUTPUT FAN OFF");assert(c.kind==ServiceConsoleCommandKind::ManualOutput&&c.device==ServiceConsoleRfDevice::Fan&&c.state==ServiceConsoleRfState::Off);c=parseServiceConsoleCommand("rf humidifier on");assert(c.kind==ServiceConsoleCommandKind::ManualOutput&&c.device==ServiceConsoleRfDevice::Humidifier&&c.state==ServiceConsoleRfState::On);assert(parseServiceConsoleCommand("output rx").kind==ServiceConsoleCommandKind::Invalid);assert(parseServiceConsoleCommand("output lamp maybe").kind==ServiceConsoleCommandKind::Invalid);}
void testRfReceiveTimeoutBounds(){auto c=parseServiceConsoleCommand("rf rx");assert(c.kind==ServiceConsoleCommandKind::RfReceive&&c.timeout_ms==1000U);assert(parseServiceConsoleCommand("rf rx 49").kind==ServiceConsoleCommandKind::Invalid);assert(parseServiceConsoleCommand("rf rx 5001").kind==ServiceConsoleCommandKind::Invalid);}
void testRtcSetUnixCommand(){auto c=parseServiceConsoleCommand("rtc set-unix 1788589800");assert(c.kind==ServiceConsoleCommandKind::RtcSetUnix&&c.unix_time_s==1788589800ULL);assert(parseServiceConsoleCommand("rtc set-unix -1").kind==ServiceConsoleCommandKind::Invalid);}
void testSdLogCommands(){assert(parseServiceConsoleCommand("sdlog status").kind==ServiceConsoleCommandKind::SdLogStatus);assert(parseServiceConsoleCommand("sdlog list").kind==ServiceConsoleCommandKind::SdLogList);assert(parseServiceConsoleCommand("sdlog selftest").kind==ServiceConsoleCommandKind::SdLogSelfTest);auto c=parseServiceConsoleCommand("sdlog read B37B41D6.JL 0 384");assert(c.kind==ServiceConsoleCommandKind::SdLogRead);assert(std::strcmp(c.filename.data(),"B37B41D6.JL")==0);assert(c.offset==0U&&c.length==384U);assert(parseServiceConsoleCommand("sdlog read ../secret 0 10").kind==ServiceConsoleCommandKind::Invalid);assert(parseServiceConsoleCommand("sdlog read B37B41D6.JL 0 0").kind==ServiceConsoleCommandKind::Invalid);assert(parseServiceConsoleCommand("sdlog read B37B41D6.JL 0 385").kind==ServiceConsoleCommandKind::Invalid);}
void testInvalidCommandsFailClosed(){assert(parseServiceConsoleCommand(nullptr).kind==ServiceConsoleCommandKind::Invalid);assert(parseServiceConsoleCommand("").kind==ServiceConsoleCommandKind::None);assert(parseServiceConsoleCommand("rf lamp maybe").kind==ServiceConsoleCommandKind::Invalid);assert(parseServiceConsoleCommand("sdlog erase all").kind==ServiceConsoleCommandKind::Invalid);}
}
int main(){testReadOnlyMenuCommands();testAutomationCommands();testSupervisedManualOutputCommands();testRfReceiveTimeoutBounds();testRtcSetUnixCommand();testSdLogCommands();testInvalidCommandsFailClosed();return 0;}
''')

host = Path('test/host/CMakeLists.txt')
text = host.read_text()
marker = 'target_compile_options(output_automation_control_tests PRIVATE -Wall -Wextra -Wpedantic)\n\nadd_executable(\n  climate_semantic_output_tests'
insert = '''target_compile_options(output_automation_control_tests PRIVATE -Wall -Wextra -Wpedantic)\n\nadd_executable(\n  output_manual_control_tests\n  "${PROJECT_ROOT}/test/test_output_manual_control/test_main.cpp"\n  "${PROJECT_ROOT}/src/climate/output/OutputManualControl.cpp"\n  "${PROJECT_ROOT}/src/climate/output/OutputSupervisorLifecycle.cpp"\n  "${PROJECT_ROOT}/src/climate/output/OutputPolicyConfig.cpp"\n)\ntarget_include_directories(output_manual_control_tests PRIVATE "${PROJECT_ROOT}/src")\ntarget_compile_features(output_manual_control_tests PRIVATE cxx_std_17)\ntarget_compile_options(output_manual_control_tests PRIVATE -Wall -Wextra -Wpedantic)\n\nadd_executable(\n  climate_semantic_output_tests'''
if text.count(marker) != 1:
    raise SystemExit(f'test/host/CMakeLists.txt: manual target anchor count={text.count(marker)}')
text = text.replace(marker, insert, 1)
marker = 'add_test(NAME output_automation_control_tests COMMAND output_automation_control_tests)\nadd_test(NAME climate_semantic_output_tests COMMAND climate_semantic_output_tests)'
insert = 'add_test(NAME output_automation_control_tests COMMAND output_automation_control_tests)\nadd_test(NAME output_manual_control_tests COMMAND output_manual_control_tests)\nadd_test(NAME climate_semantic_output_tests COMMAND climate_semantic_output_tests)'
if text.count(marker) != 1:
    raise SystemExit(f'test/host/CMakeLists.txt: manual add_test anchor count={text.count(marker)}')
host.write_text(text.replace(marker, insert, 1))

run(['git', 'add', '-N',
     'src/climate/output/OutputManualControl.cpp',
     'src/climate/output/OutputManualControl.h',
     'test/test_output_manual_control/test_main.cpp'])
run(['git', 'diff', '--check'])
changed = sorted(filter(None, out(['git', 'diff', '--name-only']).splitlines()))
if changed != EXPECTED:
    raise SystemExit(f'A10_1_ALLOWLIST_FAIL changed={changed!r}')

console = Path('src/climate/runtime/Stage28ServiceConsole.cpp').read_text()
runtime = Path('src/climate/ClimateV6RealInputRuntime.cpp').read_text()
resolver = Path('src/climate/output/OutputSupervisorResolver.cpp').read_text()
if 'manualTransmit(' in console:
    raise SystemExit('A10_1_STATIC_FAIL service console still owns direct manual RF TX')
if 'manual_control.consume(manual_intent)' not in runtime or 'supervisor_context.manual = manual_intent' not in runtime:
    raise SystemExit('A10_1_STATIC_FAIL runtime manual intent wiring missing')
if 'input.mode == SupervisorMode::Automatic' not in resolver or 'input.manual.endpoints' not in resolver:
    raise SystemExit('A10_1_STATIC_FAIL resolver manual/mode contract missing')
if resolver.find('input.manual.endpoints') > resolver.find('input.schedule.endpoints'):
    raise SystemExit('A10_1_STATIC_FAIL manual precedence below schedule')
if resolver.find('findSafetyConstraint') < resolver.find('input.manual.endpoints'):
    raise SystemExit('A10_1_STATIC_FAIL safety precedence check ordering unexpected')
print('A10_1_STATIC_PASS')

build = 'build/host-tests-a10-1-v1'
run(['cmake', '-S', 'test/host', '-B', build])
targets = [
    'output_manual_control_tests',
    'stage28_service_console_tests',
    'output_supervisor_resolver_tests',
    'climate_output_supervisor_sink_tests',
    'output_automation_control_tests',
    'output_persistence_coordinator_tests',
]
run(['cmake', '--build', build, '--parallel', '--target', *targets])
regex = '^(' + '|'.join(targets) + ')$'
run(['ctest', '--test-dir', build, '-R', regex, '--output-on-failure'])
print('A10_1_FOCUSED_PASS')

fw_build = 'build/stage27c-a10-1-v1'
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
print('A10_1_CANONICAL_BUILD_PASS')

run(['git', 'diff', '--check'])
run(['git', 'add', *EXPECTED])
run(['git', 'diff', '--cached', '--check'])
staged = sorted(filter(None, out(['git', 'diff', '--cached', '--name-only']).splitlines()))
if staged != EXPECTED:
    raise SystemExit(f'A10_1_STAGED_ALLOWLIST_FAIL staged={staged!r}')
run(['git', 'commit', '-m', 'Route service output commands through supervisor'])
commit = out(['git', 'rev-parse', 'HEAD'])
run(['git', 'push', 'origin', f'HEAD:{BRANCH}'])
run(['git', 'fetch', '-q', 'origin', BRANCH])
if out(['git', 'rev-parse', 'FETCH_HEAD']) != commit:
    raise SystemExit('A10_1_PUSH_VERIFY_FAIL')
if out(['git', 'status', '--porcelain']):
    raise SystemExit('A10_1_CLEAN_FAIL')
print(f'A10_1_PASS commit={commit}')
