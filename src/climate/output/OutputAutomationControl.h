#pragma once

#include "climate/output/OutputLifecycleExecutor.h"

#include <cstdint>

namespace growbox::app::output {

enum class OutputAutomationControlStatus : std::uint8_t {
  Ready = 0U,
  TransitionPending,
  SafetyDeferred,
  FaultLocked,
  Invalid,
};

struct OutputAutomationControlReport {
  OutputAutomationControlStatus status = OutputAutomationControlStatus::Ready;
  SupervisorMode mode = SupervisorMode::BootLocked;
  bool requested_enabled = false;
  bool request_pending = false;
  bool safety_deferred = false;
  bool lifecycle_active = false;
  OutputLifecycleExecutionReport lifecycle{};
};

class OutputAutomationControl final {
public:
  OutputAutomationControl(OutputSupervisorLifecycle& lifecycle,
                          OutputLifecycleExecutor& lifecycle_executor) noexcept;

  bool valid() const noexcept {
    return valid_;
  }
  bool requestEnabled(bool enabled) noexcept;
  bool requestedEnabled() const noexcept {
    return requested_enabled_;
  }
  bool requestPending() const noexcept {
    return request_pending_;
  }
  SupervisorMode mode() const noexcept {
    return lifecycle_.mode();
  }
  bool transitionActive() const noexcept {
    return lifecycle_executor_.active() || arming_completion_pending_ || request_pending_;
  }

  OutputAutomationControlReport tick(std::uint64_t monotonic_ms, const ScheduleIntent& schedule,
                                     const SafetyEnvelope& safety) noexcept;

private:
  static bool hardSafetyActive(const SafetyEnvelope& safety) noexcept;
  bool completeArming() noexcept;
  bool applyPendingRequest(std::uint64_t monotonic_ms, const ScheduleIntent& schedule) noexcept;
  OutputAutomationControlReport makeReport(bool safety_deferred) const noexcept;

  OutputSupervisorLifecycle& lifecycle_;
  OutputLifecycleExecutor& lifecycle_executor_;
  bool valid_{false};
  bool requested_enabled_{false};
  bool request_pending_{false};
  bool pending_enabled_{false};
  bool arming_completion_pending_{false};
};

} // namespace growbox::app::output
