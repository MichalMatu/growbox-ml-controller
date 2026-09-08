#pragma once

#include "climate/output/OutputLifecycleExecutor.h"

#include <cstdint>

namespace growbox::app::output {

enum class OutputRuntimeLifecycleOperation : std::uint8_t {
  None = 0U,
  Boot,
  Recovery,
  Fault,
};

enum class OutputRuntimeLifecycleStatus : std::uint8_t {
  Ready = 0U,
  TransitionPending,
  SafetyDeferred,
  FaultLocked,
  Invalid,
};

struct OutputRuntimeLifecycleReport {
  OutputRuntimeLifecycleStatus status = OutputRuntimeLifecycleStatus::Ready;
  SupervisorMode mode = SupervisorMode::BootLocked;
  OutputRuntimeLifecycleOperation operation = OutputRuntimeLifecycleOperation::None;
  bool active = false;
  bool safety_deferred = false;
  bool boot_completed = false;
  OutputLifecycleExecutionReport lifecycle{};
};

class OutputRuntimeLifecycleControl final {
public:
  OutputRuntimeLifecycleControl(OutputSupervisorLifecycle& lifecycle,
                                OutputLifecycleExecutor& executor) noexcept;

  bool valid() const noexcept { return valid_; }
  bool transitionActive() const noexcept {
    return operation_ != OutputRuntimeLifecycleOperation::None;
  }
  bool bootCompleted() const noexcept { return boot_completed_; }
  OutputRuntimeLifecycleOperation operation() const noexcept { return operation_; }

  bool beginBoot(std::uint64_t monotonic_ms, const ScheduleIntent& schedule) noexcept;
  bool requestRecovery(std::uint64_t monotonic_ms, const ScheduleIntent& schedule) noexcept;
  bool requestFault(std::uint64_t monotonic_ms, const ScheduleIntent& schedule) noexcept;

  OutputRuntimeLifecycleReport tick(std::uint64_t monotonic_ms,
                                    const SafetyEnvelope& safety) noexcept;
  OutputRuntimeLifecycleReport report() const noexcept;

private:
  static bool hardSafetyActive(const SafetyEnvelope& safety) noexcept;
  bool start(OutputLifecycleCommand command, OutputRuntimeLifecycleOperation operation,
             std::uint64_t monotonic_ms, const ScheduleIntent& schedule) noexcept;
  void finalizeCompletedOperation() noexcept;
  OutputRuntimeLifecycleReport makeReport(bool safety_deferred) const noexcept;

  OutputSupervisorLifecycle& lifecycle_;
  OutputLifecycleExecutor& executor_;
  OutputRuntimeLifecycleOperation operation_{OutputRuntimeLifecycleOperation::None};
  bool boot_completed_{false};
  bool valid_{false};
};

} // namespace growbox::app::output
