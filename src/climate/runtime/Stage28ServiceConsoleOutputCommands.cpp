#include "climate/runtime/Stage28ServiceConsoleOutputCommands.h"

#include "climate/output/OutputAutomationControl.h"
#include "climate/output/OutputMaintenanceControl.h"
#include "climate/output/OutputManualControl.h"

namespace growbox::app::climate_io::runtime {
namespace {

const char* supervisorModeName(::growbox::app::output::SupervisorMode mode) noexcept {
  using ::growbox::app::output::SupervisorMode;
  switch (mode) {
  case SupervisorMode::BootLocked:
    return "boot-locked";
  case SupervisorMode::Arming:
    return "arming";
  case SupervisorMode::Automatic:
    return "automatic";
  case SupervisorMode::Recovering:
    return "recovering";
  case SupervisorMode::Disabled:
    return "disabled";
  case SupervisorMode::FaultLocked:
    return "fault-locked";
  case SupervisorMode::MaintenanceLocked:
    return "maintenance-locked";
  }
  return "unknown";
}

} // namespace

bool Stage28ServiceConsoleOutputCommands::realOutputsActive() const noexcept {
  return config_.real_outputs_active != nullptr && *config_.real_outputs_active;
}

const char* Stage28ServiceConsoleOutputCommands::outputModeName() const noexcept {
  return realOutputsActive() ? "real-bounded" : "fake-locked";
}

bool Stage28ServiceConsoleOutputCommands::handle(const ServiceConsoleCommand& command,
                                                 std::uint64_t now_ms) noexcept {
  switch (command.kind) {
  case ServiceConsoleCommandKind::ManualOutput:
    handleManualOutput(command, now_ms);
    return true;
  case ServiceConsoleCommandKind::AutomationStatus:
    printAutomationStatus();
    return true;
  case ServiceConsoleCommandKind::AutomationEnable:
    handleAutomationRequest(true);
    return true;
  case ServiceConsoleCommandKind::AutomationDisable:
    handleAutomationRequest(false);
    return true;
  case ServiceConsoleCommandKind::MaintenanceStatus:
    printMaintenanceStatus();
    return true;
  case ServiceConsoleCommandKind::MaintenanceEnter:
    handleMaintenanceRequest(true);
    return true;
  case ServiceConsoleCommandKind::MaintenanceExit:
    handleMaintenanceRequest(false);
    return true;
  case ServiceConsoleCommandKind::MaintenanceRawOutput:
    handleMaintenanceRaw(command, now_ms);
    return true;
  default:
    return false;
  }
}

void Stage28ServiceConsoleOutputCommands::printStatusDetails() noexcept {
  if (config_.automation_control != nullptr) {
    printAutomationStatus();
  }
  if (config_.maintenance_control != nullptr) {
    printMaintenanceStatus();
  }
}

void Stage28ServiceConsoleOutputCommands::printAutomationStatus() noexcept {
  if (config_.automation_control == nullptr) {
    sink_.writeText("automation unavailable\r\n");
    return;
  }
  const auto& control = *config_.automation_control;
  sink_.writeFormatted(
      "automation mode=%s requested=%s transition_active=%d request_pending=%d\r\n",
      supervisorModeName(control.mode()), control.requestedEnabled() ? "on" : "off",
      control.transitionActive(), control.requestPending());
}

void Stage28ServiceConsoleOutputCommands::handleAutomationRequest(bool enabled) noexcept {
  if (config_.automation_control == nullptr) {
    sink_.writeText("error: automation control unavailable\r\n");
    return;
  }
  const bool accepted = config_.automation_control->requestEnabled(enabled);
  sink_.writeFormatted("automation request=%s accepted=%d mode=%s\r\n", enabled ? "on" : "off",
                       accepted, supervisorModeName(config_.automation_control->mode()));
}

void Stage28ServiceConsoleOutputCommands::printMaintenanceStatus() noexcept {
  if (config_.maintenance_control == nullptr) {
    sink_.writeText("maintenance unavailable\r\n");
    return;
  }
  const auto report = config_.maintenance_control->report();
  sink_.writeFormatted(
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

void Stage28ServiceConsoleOutputCommands::handleMaintenanceRequest(bool enter) noexcept {
  if (config_.maintenance_control == nullptr) {
    sink_.writeText("error: maintenance control unavailable\r\n");
    return;
  }
  const bool accepted = enter ? config_.maintenance_control->requestEnter()
                              : config_.maintenance_control->requestExit();
  sink_.writeFormatted("maintenance request=%s accepted=%d mode=%s\r\n", enter ? "enter" : "exit",
                       accepted, supervisorModeName(config_.maintenance_control->mode()));
}

void Stage28ServiceConsoleOutputCommands::handleMaintenanceRaw(const ServiceConsoleCommand& command,
                                                               std::uint64_t now_ms) noexcept {
  if (config_.maintenance_control == nullptr) {
    sink_.writeText("error: maintenance control unavailable\r\n");
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
  sink_.writeFormatted("maintenance_raw device=%s state=%s accepted=%d mode=%s queued_only=1 "
                       "physical_state=unknown\r\n",
                       serviceConsoleRfDeviceName(command.device),
                       serviceConsoleRfStateName(command.state), accepted,
                       supervisorModeName(config_.maintenance_control->mode()));
}

void Stage28ServiceConsoleOutputCommands::handleManualOutput(const ServiceConsoleCommand& command,
                                                             std::uint64_t now_ms) noexcept {
  if (config_.manual_control == nullptr) {
    sink_.writeText("error: manual output control unavailable\r\n");
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
  case OutputManualRequestStatus::Accepted:
    status = "accepted";
    break;
  case OutputManualRequestStatus::Busy:
    status = "busy";
    break;
  case OutputManualRequestStatus::ModeDenied:
    status = "mode-denied";
    break;
  case OutputManualRequestStatus::InvalidRole:
    status = "invalid-role";
    break;
  case OutputManualRequestStatus::InvalidState:
    status = "invalid-state";
    break;
  case OutputManualRequestStatus::InvalidConfiguration:
    break;
  }

  sink_.writeFormatted("manual_output device=%s state=%s accepted=%d status=%s mode=%s endpoint=%u "
                       "sequence=%llu outputs=%s physical_state=unconfirmed\r\n",
                       serviceConsoleRfDeviceName(command.device),
                       serviceConsoleRfStateName(command.state),
                       report.status == OutputManualRequestStatus::Accepted, status,
                       supervisorModeName(report.mode), static_cast<unsigned>(report.endpoint),
                       static_cast<unsigned long long>(report.sequence), outputModeName());
}

} // namespace growbox::app::climate_io::runtime
