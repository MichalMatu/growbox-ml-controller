#pragma once

#include "climate/ClimateIoAdapters.h"
#include "climate/output/BinaryActuatorPolicy.h"

#include <cstdint>

namespace growbox::app::climate_io::stage28d {

struct BinaryActuatorConfig {
  float on_threshold{0.10F};
  float off_threshold{0.03F};
  std::uint64_t min_on_ms{120'000U};
  std::uint64_t min_off_ms{120'000U};
};

struct BinaryRoleArbiterConfig {
  BinaryActuatorConfig exhaust_fan{0.10F, 0.03F, 120'000U, 120'000U};
  BinaryActuatorConfig humidifier{0.10F, 0.03F, 180'000U, 180'000U};
};

bool binaryArbiterCounterRegressed(std::uint32_t previous, std::uint32_t current,
                                   std::uint32_t maximum_expected_advance = 1024U) noexcept;

class Stage28dBinaryRoleArbiter final : public ClimateRoleDriver {
public:
  explicit Stage28dBinaryRoleArbiter(ClimateRoleDriver& downstream,
                                     BinaryRoleArbiterConfig config = {}) noexcept;

  bool apply(ClimateActuatorRole role, float level,
             std::uint64_t monotonic_ms) noexcept override;
  float appliedLevel(ClimateActuatorRole role,
                     float requested_level) const noexcept override;
  bool forceSafeOff(ClimateActuatorRole role,
                    std::uint64_t monotonic_ms) noexcept override;

  // Call after the downstream endpoint has been explicitly initialized OFF.
  // This gives dwell timing a truthful starting point without retransmitting RF.
  void synchronizeSafeOff(std::uint64_t monotonic_ms) noexcept;

  // Thermal safety bypasses fan minimum-OFF dwell immediately. Clearing the
  // override does not bypass minimum-ON dwell, which prevents chatter.
  void setSafetyForceExhaust(bool force_on) noexcept {
    safety_force_exhaust_ = force_on;
  }

  bool exhaustOn() const noexcept { return exhaust_policy_.on(); }
  bool humidifierOn() const noexcept { return humidifier_policy_.on(); }
  std::uint32_t transitionCount() const noexcept {
    return exhaust_policy_.transitionCount() + humidifier_policy_.transitionCount();
  }
  std::uint32_t dwellHoldCount() const noexcept {
    return exhaust_policy_.dwellHoldCount() + humidifier_policy_.dwellHoldCount();
  }
  std::uint32_t safetyOverrideCount() const noexcept { return safety_override_count_; }
  std::uint32_t continuityFaultCount() const noexcept { return continuity_fault_count_; }
  std::uint32_t instanceId() const noexcept { return instance_id_; }
  static std::uint32_t constructionCount() noexcept;

private:
  struct CounterSnapshot {
    std::uint32_t transitions{0U};
    std::uint32_t dwell_holds{0U};
    std::uint32_t safety_overrides{0U};
  };

  static float normalized(float value) noexcept;
  static BinaryActuatorConfig sanitized(BinaryActuatorConfig config) noexcept;
  static ::growbox::app::output::BinaryActuatorPolicyConfig
  policyConfig(BinaryActuatorConfig config) noexcept;
  void checkCounterContinuity() noexcept;
  bool applyBinary(ClimateActuatorRole role, float requested_level,
                   std::uint64_t monotonic_ms,
                   ::growbox::app::output::BinaryActuatorPolicy& policy,
                   bool force_on) noexcept;
  bool forceBinaryOff(ClimateActuatorRole role, std::uint64_t monotonic_ms,
                      ::growbox::app::output::BinaryActuatorPolicy& policy) noexcept;

  ClimateRoleDriver& downstream_;
  std::uint32_t instance_id_{0U};
  ::growbox::app::output::BinaryActuatorPolicy exhaust_policy_{};
  ::growbox::app::output::BinaryActuatorPolicy humidifier_policy_{};
  bool safety_force_exhaust_{false};
  std::uint32_t safety_override_count_{0U};
  CounterSnapshot last_counter_snapshot_{};
  bool counter_snapshot_initialized_{false};
  std::uint32_t continuity_fault_count_{0U};
};

} // namespace growbox::app::climate_io::stage28d
