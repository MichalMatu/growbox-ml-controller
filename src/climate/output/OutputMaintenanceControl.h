#pragma once

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
  OutputMaintenanceControl(const OutputPolicyConfig& policy, OutputSupervisorLifecycle& lifecycle,
                           OutputAutomationControl& automation_control,
                           OutputLifecycleExecutor& lifecycle_executor,
                           OutputStateStore& state_store,
                           OutputSupervisorResolverConfig resolver_config,
                           OutputTransport& raw_transport) noexcept;

  bool valid() const noexcept {
    return valid_;
  }
  SupervisorMode mode() const noexcept {
    return lifecycle_.mode();
  }
  bool transitionActive() const noexcept {
    return enter_pending_ || exit_pending_ || rearm_pending_ || raw_pending_ ||
           automation_control_.transitionActive() || lifecycle_executor_.active();
  }

  bool requestEnter() noexcept;
  bool requestExit() noexcept;
  bool requestRaw(OutputEndpointRole role, BinaryOutputState state,
                  std::uint64_t monotonic_ms) noexcept;
  OutputMaintenanceReport tick(std::uint64_t monotonic_ms, const SafetyEnvelope& safety) noexcept;
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
