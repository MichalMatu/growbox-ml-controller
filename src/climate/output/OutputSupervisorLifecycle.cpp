#include "climate/output/OutputSupervisorLifecycle.h"

namespace growbox::app::output {

OutputSupervisorLifecycle::OutputSupervisorLifecycle(const OutputPolicyConfig& policy) noexcept
    : valid_(validateOutputPolicyConfig(policy) == OutputPolicyConfigStatus::Ok) {
  if (!valid_) {
    mode_ = SupervisorMode::FaultLocked;
    fault_ = OutputLifecycleFaultReason::InvalidPolicy;
  }
}

OutputLifecycleTransitionReport OutputSupervisorLifecycle::transition(
    SupervisorMode next, OutputLifecycleFaultReason fault, bool has_policy_event,
    OutputLifecycleEvent policy_event) noexcept {
  const SupervisorMode before = mode_;
  mode_ = next;
  fault_ = fault;
  ++generation_;
  if (generation_ == 0U) {
    ++generation_;
  }
  return {OutputLifecycleTransitionStatus::Applied, before, mode_, fault_, has_policy_event,
          policy_event, generation_};
}

OutputLifecycleTransitionReport OutputSupervisorLifecycle::noChange() const noexcept {
  return {OutputLifecycleTransitionStatus::NoChange, mode_, mode_, fault_, false,
          OutputLifecycleEvent::Boot, generation_};
}

OutputLifecycleTransitionReport
OutputSupervisorLifecycle::failClosed(OutputLifecycleFaultReason fault) noexcept {
  const SupervisorMode before = mode_;
  mode_ = SupervisorMode::FaultLocked;
  fault_ = fault;
  ++generation_;
  if (generation_ == 0U) {
    ++generation_;
  }
  return {OutputLifecycleTransitionStatus::IllegalTransition, before, mode_, fault_, true,
          OutputLifecycleEvent::Fault, generation_};
}

OutputLifecycleTransitionReport
OutputSupervisorLifecycle::apply(OutputLifecycleCommand command) noexcept {
  if (!valid_) {
    return {OutputLifecycleTransitionStatus::InvalidPolicy, mode_, mode_, fault_, false,
            OutputLifecycleEvent::Boot, generation_};
  }

  switch (command) {
  case OutputLifecycleCommand::BeginArming:
    if (mode_ == SupervisorMode::BootLocked) {
      return transition(SupervisorMode::Arming, OutputLifecycleFaultReason::None, true,
                        OutputLifecycleEvent::Boot);
    }
    if (mode_ == SupervisorMode::Arming) {
      return noChange();
    }
    break;

  case OutputLifecycleCommand::ArmingSucceeded:
    if (mode_ == SupervisorMode::Arming) {
      return transition(SupervisorMode::Automatic, OutputLifecycleFaultReason::None, false,
                        OutputLifecycleEvent::Boot);
    }
    if (mode_ == SupervisorMode::Automatic) {
      return noChange();
    }
    break;

  case OutputLifecycleCommand::ArmingFailed:
    if (mode_ == SupervisorMode::Arming) {
      return transition(SupervisorMode::FaultLocked, OutputLifecycleFaultReason::ArmingFailed,
                        true, OutputLifecycleEvent::Fault);
    }
    break;

  case OutputLifecycleCommand::DisableAutomation:
    if (mode_ == SupervisorMode::Automatic) {
      return transition(SupervisorMode::Disabled, OutputLifecycleFaultReason::None, true,
                        OutputLifecycleEvent::AutomationOff);
    }
    if (mode_ == SupervisorMode::Disabled) {
      return noChange();
    }
    break;

  case OutputLifecycleCommand::EnableAutomation:
    if (mode_ == SupervisorMode::Disabled) {
      return transition(SupervisorMode::Arming, OutputLifecycleFaultReason::None, false,
                        OutputLifecycleEvent::Boot);
    }
    if (mode_ == SupervisorMode::Automatic || mode_ == SupervisorMode::Arming) {
      return noChange();
    }
    break;

  case OutputLifecycleCommand::BeginRecovery:
    if (mode_ == SupervisorMode::Automatic || mode_ == SupervisorMode::FaultLocked) {
      return transition(SupervisorMode::Recovering, OutputLifecycleFaultReason::None, true,
                        OutputLifecycleEvent::Recovery);
    }
    if (mode_ == SupervisorMode::Recovering) {
      return noChange();
    }
    break;

  case OutputLifecycleCommand::RecoverySucceeded:
    if (mode_ == SupervisorMode::Recovering) {
      return transition(SupervisorMode::Automatic, OutputLifecycleFaultReason::None, false,
                        OutputLifecycleEvent::Recovery);
    }
    break;

  case OutputLifecycleCommand::RecoveryFailed:
    if (mode_ == SupervisorMode::Recovering) {
      return transition(SupervisorMode::FaultLocked, OutputLifecycleFaultReason::RecoveryFailed,
                        true, OutputLifecycleEvent::Fault);
    }
    break;

  case OutputLifecycleCommand::EnterFault:
    if (mode_ == SupervisorMode::FaultLocked) {
      return noChange();
    }
    return transition(SupervisorMode::FaultLocked, OutputLifecycleFaultReason::ExplicitFault, true,
                      OutputLifecycleEvent::Fault);

  case OutputLifecycleCommand::EnterMaintenance:
    if (mode_ == SupervisorMode::Disabled) {
      return transition(SupervisorMode::MaintenanceLocked, OutputLifecycleFaultReason::None, false,
                        OutputLifecycleEvent::AutomationOff);
    }
    if (mode_ == SupervisorMode::MaintenanceLocked) {
      return noChange();
    }
    break;

  case OutputLifecycleCommand::ExitMaintenance:
    if (mode_ == SupervisorMode::MaintenanceLocked) {
      return transition(SupervisorMode::Disabled, OutputLifecycleFaultReason::None, false,
                        OutputLifecycleEvent::AutomationOff);
    }
    if (mode_ == SupervisorMode::Disabled) {
      return noChange();
    }
    break;
  }

  return failClosed(OutputLifecycleFaultReason::IllegalTransition);
}

} // namespace growbox::app::output
