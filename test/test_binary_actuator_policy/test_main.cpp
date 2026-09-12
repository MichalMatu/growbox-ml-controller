#include "climate/output/policy/BinaryActuatorPolicy.h"

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
