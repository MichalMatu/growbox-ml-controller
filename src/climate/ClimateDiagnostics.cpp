#include "climate/ClimateDiagnostics.h"

namespace growbox::app::climate_io {

bool ObservedClimateSnapshotProvider::snapshot(std::uint64_t monotonic_ms,
                                               ClimateInputSnapshot& output) noexcept {
  const bool available = provider_.snapshot(monotonic_ms, output);
  observation_ = {};
  observation_.attempted = true;
  observation_.available = available;
  observation_.monotonic_ms = monotonic_ms;
  if (available) {
    observation_.snapshot = output;
  }
  return available;
}

ClimateDiagnostics
makeClimateDiagnostics(std::uint64_t monotonic_ms, const ClimateSnapshotObservation& input,
                       const ::growbox::climate::ClimateLoopResult& result,
                       const ::growbox::climate::ClimateRuntimeDecision& decision,
                       const ::growbox::climate::PreviousClimateActions& confirmed_applied,
                       bool actuator_fault_latched) noexcept {
  ClimateDiagnostics diagnostics{};
  diagnostics.monotonic_ms = monotonic_ms;
  diagnostics.input = input;
  diagnostics.policy_mode = decision.mode;
  diagnostics.runtime_status = result.runtime_status;
  diagnostics.io_status = result.io_status;
  diagnostics.ml_evaluated = decision.ml_evaluated;
  diagnostics.authoritative_ml = decision.authoritative_ml;
  diagnostics.rule = decision.rule;
  diagnostics.ml_shadow = decision.ml;
  diagnostics.final_safe_request = decision.applied;
  diagnostics.confirmed_applied = confirmed_applied;
  diagnostics.input_sampled = result.input_sampled;
  diagnostics.command_applied = result.command_applied;
  diagnostics.fail_safe_attempted = result.fail_safe_attempted;
  diagnostics.fail_safe_applied = result.fail_safe_applied;
  diagnostics.actuator_fault_latched = actuator_fault_latched;
  return diagnostics;
}

} // namespace growbox::app::climate_io
