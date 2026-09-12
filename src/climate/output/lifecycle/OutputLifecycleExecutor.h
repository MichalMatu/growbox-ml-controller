#pragma once

#include "climate/output/OutputTransport.h"
#include "climate/output/lifecycle/OutputSupervisorLifecycle.h"
#include "climate/output/supervisor/OutputSupervisorResolver.h"

#include <array>
#include <cstddef>
#include <cstdint>

namespace growbox::app::output {

enum class OutputLifecycleExecutionStatus : std::uint8_t {
  Idle = 0U,
  Pending,
  Completed,
  CompletedWithFailures,
  FaultLocked,
  InvalidConfiguration,
  InvalidTransition,
  InvalidPlan,
  Busy,
};

struct OutputLifecycleExecutionReport {
  OutputLifecycleExecutionStatus status = OutputLifecycleExecutionStatus::Idle;
  bool active = false;
  bool containment_active = false;
  OutputLifecycleEvent event = OutputLifecycleEvent::Boot;
  std::uint8_t next_order = 0U;
  std::uint8_t terminal_failures = 0U;
  std::uint8_t current_attempts = 0U;
  bool has_last_result = false;
  ExecutionStepResult last_result{};
};

class OutputLifecycleExecutor final {
public:
  OutputLifecycleExecutor(const OutputPolicyConfig& policy, OutputSupervisorLifecycle& lifecycle,
                          OutputTransport& transport, OutputStateStore& state_store,
                          OutputSupervisorResolverConfig resolver_config) noexcept;

  bool valid() const noexcept {
    return valid_;
  }
  bool active() const noexcept {
    return active_;
  }
  OutputLifecycleExecutionStatus status() const noexcept {
    return status_;
  }

  bool start(const OutputLifecycleTransitionReport& transition, std::uint64_t monotonic_ms,
             const ScheduleIntent& schedule) noexcept;
  bool start(const OutputLifecycleTransitionReport& transition,
             std::uint64_t monotonic_ms) noexcept {
    return start(transition, monotonic_ms, ScheduleIntent{});
  }

  OutputLifecycleExecutionReport tick(std::uint64_t monotonic_ms) noexcept;
  // Abort a pending lifecycle plan without fabricating a transport result. This is
  // used only when a higher-priority fault transition supersedes the old plan.
  bool cancelPending() noexcept;
  OutputLifecycleExecutionReport report() const noexcept;

private:
  struct PendingStep {
    bool present = false;
    OutputLifecycleActionPolicy policy{};
    OutputCommand command{};
    std::uint8_t attempts = 0U;
  };

  bool validateComposition() const noexcept;
  const OutputSupervisorEndpointBinding* findBinding(OutputEndpointId endpoint) const noexcept;
  static bool timeReached(std::uint64_t now, std::uint64_t due) noexcept;
  static bool scheduleState(const ScheduleIntent& schedule, OutputEndpointId endpoint,
                            BinaryOutputState& state) noexcept;
  bool buildPlan(OutputLifecycleEvent event, std::uint64_t monotonic_ms,
                 const ScheduleIntent& schedule) noexcept;
  bool buildStep(const OutputEndpointPolicy& endpoint, OutputLifecycleEvent event,
                 std::uint64_t monotonic_ms, const ScheduleIntent& schedule,
                 PendingStep& step) noexcept;
  bool commandAlreadyCompleted(const OutputCommand& command) const noexcept;
  void synchronizeBinary(const OutputCommand& command, std::uint64_t monotonic_ms) noexcept;
  std::uint64_t nextSequence() noexcept;
  void clearPlan() noexcept;
  void finishPlan() noexcept;
  bool beginFaultContainment(std::uint64_t monotonic_ms) noexcept;
  void failClosed(OutputLifecycleExecutionStatus status) noexcept;

  OutputPolicyConfig policy_{};
  OutputSupervisorLifecycle& lifecycle_;
  OutputTransport& transport_;
  OutputStateStore& state_store_;
  OutputSupervisorResolverConfig resolver_config_{};
  std::array<PendingStep, kOutputEndpointCapacity> steps_{};
  ScheduleIntent schedule_snapshot_{};
  OutputLifecycleEvent event_{OutputLifecycleEvent::Boot};
  OutputLifecycleExecutionStatus status_{OutputLifecycleExecutionStatus::Idle};
  std::uint8_t cursor_{0U};
  std::uint8_t terminal_failures_{0U};
  std::uint64_t sequence_{0U};
  bool active_{false};
  bool containment_active_{false};
  bool valid_{false};
  bool has_last_result_{false};
  ExecutionStepResult last_result_{};
};

} // namespace growbox::app::output
