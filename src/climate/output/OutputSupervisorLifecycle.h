#pragma once

#include "climate/output/OutputPolicyConfig.h"

#include <cstdint>

namespace growbox::app::output {

enum class OutputLifecycleCommand : std::uint8_t {
  BeginArming = 0U,
  ArmingSucceeded,
  ArmingFailed,
  DisableAutomation,
  EnableAutomation,
  BeginRecovery,
  RecoverySucceeded,
  RecoveryFailed,
  EnterFault,
  EnterMaintenance,
  ExitMaintenance,
};

enum class OutputLifecycleTransitionStatus : std::uint8_t {
  Applied = 0U,
  NoChange,
  InvalidPolicy,
  IllegalTransition,
};

enum class OutputLifecycleFaultReason : std::uint8_t {
  None = 0U,
  InvalidPolicy,
  IllegalTransition,
  ArmingFailed,
  RecoveryFailed,
  ExplicitFault,
};

struct OutputLifecycleTransitionReport {
  OutputLifecycleTransitionStatus status = OutputLifecycleTransitionStatus::NoChange;
  SupervisorMode before = SupervisorMode::BootLocked;
  SupervisorMode after = SupervisorMode::BootLocked;
  OutputLifecycleFaultReason fault = OutputLifecycleFaultReason::None;
  bool has_policy_event = false;
  OutputLifecycleEvent policy_event = OutputLifecycleEvent::Boot;
  std::uint64_t generation = 0U;
};

class OutputSupervisorLifecycle final {
public:
  explicit OutputSupervisorLifecycle(const OutputPolicyConfig& policy) noexcept;

  bool valid() const noexcept { return valid_; }
  SupervisorMode mode() const noexcept { return mode_; }
  OutputLifecycleFaultReason fault() const noexcept { return fault_; }
  std::uint64_t generation() const noexcept { return generation_; }
  bool normalExecutionEnabled() const noexcept { return mode_ == SupervisorMode::Automatic; }
  bool safetyEvaluationEnabled() const noexcept { return true; }

  OutputLifecycleTransitionReport apply(OutputLifecycleCommand command) noexcept;

private:
  OutputLifecycleTransitionReport transition(SupervisorMode next,
                                             OutputLifecycleFaultReason fault,
                                             bool has_policy_event,
                                             OutputLifecycleEvent policy_event) noexcept;
  OutputLifecycleTransitionReport noChange() const noexcept;
  OutputLifecycleTransitionReport failClosed(OutputLifecycleFaultReason fault) noexcept;

  bool valid_{false};
  SupervisorMode mode_{SupervisorMode::BootLocked};
  OutputLifecycleFaultReason fault_{OutputLifecycleFaultReason::None};
  std::uint64_t generation_{0U};
};

} // namespace growbox::app::output
