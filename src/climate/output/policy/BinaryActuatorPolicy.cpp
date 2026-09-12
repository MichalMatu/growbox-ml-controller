#include "climate/output/policy/BinaryActuatorPolicy.h"

#include <algorithm>
#include <cmath>

namespace growbox::app::output {

BinaryActuatorPolicy::BinaryActuatorPolicy(BinaryActuatorPolicyConfig config) noexcept
    : config_(sanitized(config)) {}

float BinaryActuatorPolicy::normalized(float value) noexcept {
  if (!std::isfinite(value)) {
    return 0.0F;
  }
  return std::clamp(value, 0.0F, 1.0F);
}

BinaryActuatorPolicyConfig
BinaryActuatorPolicy::sanitized(BinaryActuatorPolicyConfig config) noexcept {
  config.on_threshold = normalized(config.on_threshold);
  config.off_threshold = normalized(config.off_threshold);
  if (config.off_threshold > config.on_threshold) {
    config.off_threshold = config.on_threshold;
  }
  return config;
}

BinaryActuatorProposal BinaryActuatorPolicy::propose(float requested_level,
                                                     std::uint64_t monotonic_ms,
                                                     BinaryPolicyOverride override_mode) noexcept {
  BinaryActuatorProposal proposal{};
  proposal.proposed_at_ms = monotonic_ms;
  proposal.generation = generation_;

  const float request = normalized(requested_level);
  bool target_on = false;

  switch (override_mode) {
  case BinaryPolicyOverride::ForceOn:
    target_on = true;
    proposal.bypass_dwell = true;
    proposal.override_applied = !known_ || state_ != BinaryOutputState::On;
    break;
  case BinaryPolicyOverride::ForceOff:
    target_on = false;
    proposal.bypass_dwell = true;
    proposal.override_applied = !known_ || state_ != BinaryOutputState::Off;
    break;
  case BinaryPolicyOverride::None:
    if (!known_) {
      target_on = request >= config_.on_threshold;
    } else if (state_ == BinaryOutputState::On) {
      target_on = request > config_.off_threshold;
    } else {
      target_on = request >= config_.on_threshold;
    }
    break;
  }

  proposal.target = target_on ? BinaryOutputState::On : BinaryOutputState::Off;
  if (proposal.override_applied) {
    ++override_count_;
  }

  if (known_ && proposal.target == state_) {
    return proposal;
  }

  if (known_ && !proposal.bypass_dwell) {
    const std::uint64_t elapsed_ms =
        monotonic_ms >= last_change_ms_ ? monotonic_ms - last_change_ms_ : 0U;
    const std::uint64_t required_ms =
        state_ == BinaryOutputState::On ? config_.min_on_ms : config_.min_off_ms;
    if (elapsed_ms < required_ms) {
      proposal.held_by_dwell = true;
      ++dwell_hold_count_;
      return proposal;
    }
  }

  proposal.command_required = true;
  return proposal;
}

bool BinaryActuatorPolicy::commit(const BinaryActuatorProposal& proposal,
                                  bool command_completed) noexcept {
  if (!proposal.command_required || proposal.held_by_dwell || proposal.generation != generation_) {
    return false;
  }
  if (!command_completed) {
    return true;
  }

  if (!known_ || state_ != proposal.target) {
    ++transition_count_;
  }
  known_ = true;
  state_ = proposal.target;
  last_change_ms_ = proposal.proposed_at_ms;
  ++generation_;
  return true;
}

void BinaryActuatorPolicy::synchronize(BinaryOutputState state,
                                       std::uint64_t monotonic_ms) noexcept {
  known_ = true;
  state_ = state;
  last_change_ms_ = monotonic_ms;
  ++generation_;
}

} // namespace growbox::app::output
