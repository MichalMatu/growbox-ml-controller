from pathlib import Path

header = r'''#pragma once

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

  BinaryActuatorProposal propose(
      float requested_level, std::uint64_t monotonic_ms,
      BinaryPolicyOverride override_mode = BinaryPolicyOverride::None) noexcept;

  // Commit only after the downstream command has completed successfully.
  // A failed command is represented by command_completed=false and never
  // advances state, dwell timing or generation.
  bool commit(const BinaryActuatorProposal& proposal, bool command_completed) noexcept;

  void synchronize(BinaryOutputState state, std::uint64_t monotonic_ms) noexcept;

  bool known() const noexcept { return known_; }
  BinaryOutputState state() const noexcept { return state_; }
  bool on() const noexcept { return known_ && state_ == BinaryOutputState::On; }
  std::uint64_t lastChangeMs() const noexcept { return last_change_ms_; }
  std::uint32_t generation() const noexcept { return generation_; }
  std::uint32_t transitionCount() const noexcept { return transition_count_; }
  std::uint32_t dwellHoldCount() const noexcept { return dwell_hold_count_; }
  std::uint32_t overrideCount() const noexcept { return override_count_; }
  const BinaryActuatorPolicyConfig& config() const noexcept { return config_; }

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
'''

source = r'''#include "climate/output/BinaryActuatorPolicy.h"

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

BinaryActuatorProposal BinaryActuatorPolicy::propose(
    float requested_level, std::uint64_t monotonic_ms,
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
  if (!proposal.command_required || proposal.held_by_dwell ||
      proposal.generation != generation_) {
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
'''

test = r'''#include "climate/output/BinaryActuatorPolicy.h"

#include <cassert>
#include <cmath>
#include <limits>

namespace {

using namespace growbox::app::output;

void testConfigSanitization() {
  BinaryActuatorPolicy policy({2.0F, 0.8F, 10U, 20U});
  assert(std::fabs(policy.config().on_threshold - 1.0F) < 1.0e-6F);
  assert(std::fabs(policy.config().off_threshold - 0.8F) < 1.0e-6F);

  BinaryActuatorPolicy swapped({0.2F, 0.7F, 1U, 1U});
  assert(std::fabs(swapped.config().on_threshold - 0.2F) < 1.0e-6F);
  assert(std::fabs(swapped.config().off_threshold - 0.2F) < 1.0e-6F);
}

void testV5DwellContinuityAndExactBoundary() {
  BinaryActuatorPolicy policy;
  policy.synchronize(BinaryOutputState::Off, 0U);

  auto quiet = policy.propose(0.099F, 500U);
  assert(!quiet.command_required);
  assert(!quiet.held_by_dwell);
  assert(policy.dwellHoldCount() == 0U);

  for (std::uint32_t index = 0U; index < 43U; ++index) {
    const auto proposal = policy.propose(0.111F, 1'000U + index);
    assert(!proposal.command_required);
    assert(proposal.held_by_dwell);
    assert(policy.dwellHoldCount() == index + 1U);
    assert(!policy.on());
  }

  const auto before_boundary = policy.propose(0.111F, 119'999U);
  assert(!before_boundary.command_required);
  assert(before_boundary.held_by_dwell);
  assert(policy.dwellHoldCount() == 44U);

  const auto at_boundary = policy.propose(0.111F, 120'000U);
  assert(at_boundary.command_required);
  assert(!at_boundary.held_by_dwell);
  assert(at_boundary.target == BinaryOutputState::On);
  assert(policy.commit(at_boundary, true));
  assert(policy.on());
  assert(policy.transitionCount() == 1U);
  assert(policy.dwellHoldCount() == 44U);
}

void testFanHysteresisAndMinimumDwell() {
  BinaryActuatorPolicy policy;
  policy.synchronize(BinaryOutputState::Off, 1'000U);

  auto proposal = policy.propose(0.29F, 60'000U);
  assert(proposal.held_by_dwell && !proposal.command_required);
  assert(!policy.on());

  proposal = policy.propose(0.29F, 121'000U);
  assert(proposal.command_required && proposal.target == BinaryOutputState::On);
  assert(policy.commit(proposal, true));
  assert(policy.on());

  proposal = policy.propose(0.05F, 121'001U);
  assert(!proposal.command_required);
  assert(!proposal.held_by_dwell);
  assert(policy.on());

  proposal = policy.propose(0.0F, 180'000U);
  assert(proposal.held_by_dwell && !proposal.command_required);
  assert(policy.on());

  proposal = policy.propose(0.0F, 241'000U);
  assert(proposal.command_required && proposal.target == BinaryOutputState::Off);
  assert(policy.commit(proposal, true));
  assert(!policy.on());
}

void testLongerHumidifierDwell() {
  BinaryActuatorPolicy policy({0.10F, 0.03F, 180'000U, 180'000U});
  policy.synchronize(BinaryOutputState::Off, 0U);

  auto proposal = policy.propose(0.40F, 120'000U);
  assert(proposal.held_by_dwell && !proposal.command_required);

  proposal = policy.propose(0.40F, 180'000U);
  assert(proposal.command_required);
  assert(policy.commit(proposal, true));
  assert(policy.on());

  proposal = policy.propose(0.0F, 300'000U);
  assert(proposal.held_by_dwell && !proposal.command_required);
  proposal = policy.propose(0.0F, 360'000U);
  assert(proposal.command_required);
  assert(policy.commit(proposal, true));
  assert(!policy.on());
}

void testFailedCommitDoesNotAdvanceStateOrDwellClock() {
  BinaryActuatorPolicy policy;
  policy.synchronize(BinaryOutputState::Off, 0U);
  const auto generation = policy.generation();

  auto proposal = policy.propose(0.50F, 120'000U);
  assert(proposal.command_required);
  assert(policy.commit(proposal, false));
  assert(!policy.on());
  assert(policy.lastChangeMs() == 0U);
  assert(policy.generation() == generation);
  assert(policy.transitionCount() == 0U);

  proposal = policy.propose(0.50F, 121'000U);
  assert(proposal.command_required);
  assert(policy.commit(proposal, true));
  assert(policy.on());
  assert(policy.lastChangeMs() == 121'000U);
  assert(policy.transitionCount() == 1U);
}

void testForceOnBypassesMinimumOffButClearRespectsMinimumOn() {
  BinaryActuatorPolicy policy;
  policy.synchronize(BinaryOutputState::Off, 10'000U);

  auto proposal = policy.propose(0.0F, 11'000U, BinaryPolicyOverride::ForceOn);
  assert(proposal.command_required);
  assert(proposal.bypass_dwell);
  assert(proposal.override_applied);
  assert(policy.overrideCount() == 1U);
  assert(policy.commit(proposal, true));
  assert(policy.on());

  proposal = policy.propose(0.0F, 12'000U);
  assert(!proposal.command_required);
  assert(proposal.held_by_dwell);
  assert(policy.on());

  proposal = policy.propose(0.0F, 131'000U);
  assert(proposal.command_required);
  assert(policy.commit(proposal, true));
  assert(!policy.on());
}

void testForceOffBypassesDwell() {
  BinaryActuatorPolicy policy;
  policy.synchronize(BinaryOutputState::On, 100U);
  const auto proposal = policy.propose(1.0F, 101U, BinaryPolicyOverride::ForceOff);
  assert(proposal.command_required);
  assert(proposal.bypass_dwell);
  assert(proposal.target == BinaryOutputState::Off);
  assert(policy.commit(proposal, true));
  assert(!policy.on());
  assert(policy.lastChangeMs() == 101U);
}

void testStaleProposalCannotCommit() {
  BinaryActuatorPolicy policy;
  policy.synchronize(BinaryOutputState::Off, 0U);
  const auto stale = policy.propose(1.0F, 120'000U);
  assert(stale.command_required);

  policy.synchronize(BinaryOutputState::Off, 130'000U);
  assert(!policy.commit(stale, true));
  assert(!policy.on());
  assert(policy.lastChangeMs() == 130'000U);
}

void testNonFiniteRequestFailsTowardOff() {
  BinaryActuatorPolicy policy;
  const auto proposal = policy.propose(std::numeric_limits<float>::quiet_NaN(), 0U);
  assert(proposal.command_required);
  assert(proposal.target == BinaryOutputState::Off);
}

} // namespace

int main() {
  testConfigSanitization();
  testV5DwellContinuityAndExactBoundary();
  testFanHysteresisAndMinimumDwell();
  testLongerHumidifierDwell();
  testFailedCommitDoesNotAdvanceStateOrDwellClock();
  testForceOnBypassesMinimumOffButClearRespectsMinimumOn();
  testForceOffBypassesDwell();
  testStaleProposalCannotCommit();
  testNonFiniteRequestFailsTowardOff();
  return 0;
}
'''

Path('src/climate/output/BinaryActuatorPolicy.h').write_text(header)
Path('src/climate/output/BinaryActuatorPolicy.cpp').write_text(source)
Path('test/test_binary_actuator_policy').mkdir(parents=True, exist_ok=True)
Path('test/test_binary_actuator_policy/test_main.cpp').write_text(test)

p = Path('src/CMakeLists.txt')
s = p.read_text()
needle = '    "climate/output/OutputStateStore.cpp"\n'
assert s.count(needle) == 1
s = s.replace(needle, needle + '    "climate/output/BinaryActuatorPolicy.cpp"\n', 1)
p.write_text(s)

p = Path('test/host/CMakeLists.txt')
s = p.read_text().rstrip('\n') + '\n'
block = r'''
add_executable(
  binary_actuator_policy_tests
  "${PROJECT_ROOT}/test/test_binary_actuator_policy/test_main.cpp"
  "${PROJECT_ROOT}/src/climate/output/BinaryActuatorPolicy.cpp"
)
target_include_directories(binary_actuator_policy_tests PRIVATE "${PROJECT_ROOT}/src")
target_compile_features(binary_actuator_policy_tests PRIVATE cxx_std_17)
target_compile_options(binary_actuator_policy_tests PRIVATE -Wall -Wextra -Wpedantic)
add_test(NAME binary_actuator_policy_tests COMMAND binary_actuator_policy_tests)
'''
assert 'binary_actuator_policy_tests' not in s
p.write_text(s + block)
