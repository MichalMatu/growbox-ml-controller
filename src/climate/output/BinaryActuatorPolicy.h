#pragma once

#include "climate/output/OutputTypes.h"

#include <cstdint>

namespace growbox::app::output {

struct BinaryActuatorPolicyConfig {
  float on_threshold{0.10F};
  float off_threshold{0.03F};
  std::uint64_t min_on_ms{120'000U};
  std::uint64_t min_off_ms{120'000U};
};

enum class BinaryPolicyOverride : std::uint8_t {
  None = 0U,
  ForceOff,
  ForceOn,
};

struct BinaryActuatorProposal {
  BinaryOutputState target = BinaryOutputState::Off;
  bool command_required = false;
  bool held_by_dwell = false;
  bool bypass_dwell = false;
  bool override_applied = false;
  std::uint64_t proposed_at_ms = 0U;
  std::uint32_t generation = 0U;
};

class BinaryActuatorPolicy final {
public:
  explicit BinaryActuatorPolicy(BinaryActuatorPolicyConfig config = {}) noexcept;

  BinaryActuatorProposal
  propose(float requested_level, std::uint64_t monotonic_ms,
          BinaryPolicyOverride override_mode = BinaryPolicyOverride::None) noexcept;

  // Commit only after the downstream command has completed successfully.
  // A failed command is represented by command_completed=false and never
  // advances state, dwell timing or generation.
  bool commit(const BinaryActuatorProposal& proposal, bool command_completed) noexcept;

  void synchronize(BinaryOutputState state, std::uint64_t monotonic_ms) noexcept;

  bool known() const noexcept {
    return known_;
  }
  BinaryOutputState state() const noexcept {
    return state_;
  }
  bool on() const noexcept {
    return known_ && state_ == BinaryOutputState::On;
  }
  std::uint64_t lastChangeMs() const noexcept {
    return last_change_ms_;
  }
  std::uint32_t generation() const noexcept {
    return generation_;
  }
  std::uint32_t transitionCount() const noexcept {
    return transition_count_;
  }
  std::uint32_t dwellHoldCount() const noexcept {
    return dwell_hold_count_;
  }
  std::uint32_t overrideCount() const noexcept {
    return override_count_;
  }
  const BinaryActuatorPolicyConfig& config() const noexcept {
    return config_;
  }

private:
  static float normalized(float value) noexcept;
  static BinaryActuatorPolicyConfig sanitized(BinaryActuatorPolicyConfig config) noexcept;

  BinaryActuatorPolicyConfig config_{};
  bool known_{false};
  BinaryOutputState state_{BinaryOutputState::Off};
  std::uint64_t last_change_ms_{0U};
  std::uint32_t generation_{0U};
  std::uint32_t transition_count_{0U};
  std::uint32_t dwell_hold_count_{0U};
  std::uint32_t override_count_{0U};
};

} // namespace growbox::app::output
