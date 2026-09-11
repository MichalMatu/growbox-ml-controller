#pragma once

#include "climate/output/OutputIntents.h"
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

  bool valid() const noexcept {
    return valid_;
  }
  bool pending() const noexcept {
    return pending_;
  }
  SupervisorMode mode() const noexcept {
    return lifecycle_.mode();
  }

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
