#pragma once

#include "climate/ClimateIoAdapters.h"

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

  bool exhaustOn() const noexcept { return exhaust_.known && exhaust_.on; }
  bool humidifierOn() const noexcept { return humidifier_.known && humidifier_.on; }
  std::uint32_t transitionCount() const noexcept { return transition_count_; }
  std::uint32_t dwellHoldCount() const noexcept { return dwell_hold_count_; }
  std::uint32_t safetyOverrideCount() const noexcept { return safety_override_count_; }

private:
  struct BinaryState {
    bool known{false};
    bool on{false};
    std::uint64_t last_change_ms{0U};
  };

  static float normalized(float value) noexcept;
  static BinaryActuatorConfig sanitized(BinaryActuatorConfig config) noexcept;
  bool applyBinary(ClimateActuatorRole role, float requested_level,
                   std::uint64_t monotonic_ms, const BinaryActuatorConfig& config,
                   BinaryState& state, bool force_on) noexcept;
  bool forceBinaryOff(ClimateActuatorRole role, std::uint64_t monotonic_ms,
                      BinaryState& state) noexcept;

  ClimateRoleDriver& downstream_;
  BinaryRoleArbiterConfig config_{};
  BinaryState exhaust_{};
  BinaryState humidifier_{};
  bool safety_force_exhaust_{false};
  std::uint32_t transition_count_{0U};
  std::uint32_t dwell_hold_count_{0U};
  std::uint32_t safety_override_count_{0U};
};

} // namespace growbox::app::climate_io::stage28d
