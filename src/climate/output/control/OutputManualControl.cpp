#include "climate/output/control/OutputManualControl.h"

namespace growbox::app::output {

OutputManualControl::OutputManualControl(const OutputPolicyConfig& policy,
                                         const OutputSupervisorLifecycle& lifecycle) noexcept
    : policy_(policy), lifecycle_(lifecycle),
      valid_(validateOutputPolicyConfig(policy_) == OutputPolicyConfigStatus::Ok &&
             lifecycle_.valid()) {}

bool OutputManualControl::validState(BinaryOutputState state) noexcept {
  return state == BinaryOutputState::Off || state == BinaryOutputState::On;
}

std::uint64_t OutputManualControl::nextSequence() noexcept {
  ++sequence_;
  if (sequence_ == 0U) {
    ++sequence_;
  }
  return sequence_;
}

OutputManualRequestReport OutputManualControl::request(OutputEndpointRole role,
                                                       BinaryOutputState state,
                                                       std::uint64_t monotonic_ms) noexcept {
  OutputManualRequestReport report{};
  report.mode = lifecycle_.mode();
  report.role = role;
  report.state = state;

  if (!valid_) {
    report.status = OutputManualRequestStatus::InvalidConfiguration;
    return report;
  }
  if (!validState(state)) {
    report.status = OutputManualRequestStatus::InvalidState;
    return report;
  }
  if (lifecycle_.mode() != SupervisorMode::Automatic) {
    report.status = OutputManualRequestStatus::ModeDenied;
    return report;
  }
  if (pending_) {
    report.status = OutputManualRequestStatus::Busy;
    return report;
  }

  const OutputEndpointPolicy* endpoint = findOutputPolicyRole(policy_, role);
  if (endpoint == nullptr || !isValidOutputEndpoint(endpoint->endpoint)) {
    report.status = OutputManualRequestStatus::InvalidRole;
    return report;
  }

  ManualIntent intent{};
  intent.metadata.sequence = nextSequence();
  intent.metadata.monotonic_ms = monotonic_ms;
  intent.metadata.source = OutputSource::Manual;
  intent.metadata.reason = OutputReason::ManualRequest;
  if (!setEndpointIntent(intent.endpoints[0], endpoint->endpoint,
                         state == BinaryOutputState::On ? 1.0F : 0.0F)) {
    report.status = OutputManualRequestStatus::InvalidRole;
    return report;
  }

  pending_intent_ = intent;
  pending_ = true;
  report.status = OutputManualRequestStatus::Accepted;
  report.endpoint = endpoint->endpoint;
  report.sequence = intent.metadata.sequence;
  return report;
}

bool OutputManualControl::consume(ManualIntent& intent) noexcept {
  intent = {};
  if (!valid_ || !pending_) {
    return false;
  }
  intent = pending_intent_;
  pending_intent_ = {};
  pending_ = false;
  return true;
}

} // namespace growbox::app::output
