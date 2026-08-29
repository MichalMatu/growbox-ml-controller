#pragma once

#include "climate/ClimateIoAdapters.h"

#include <cstdint>

namespace growbox::app::climate_io {

inline constexpr std::uint32_t kClimateDiagnosticsSchemaVersion = 1U;

struct ClimateSnapshotObservation {
  bool attempted = false;
  bool available = false;
  std::uint64_t monotonic_ms = 0U;
  ClimateInputSnapshot snapshot{};
};

class ObservedClimateSnapshotProvider final : public ClimateSnapshotProvider {
public:
  explicit ObservedClimateSnapshotProvider(ClimateSnapshotProvider& provider) noexcept
      : provider_(provider) {}

  bool snapshot(std::uint64_t monotonic_ms, ClimateInputSnapshot& output) noexcept override;

  const ClimateSnapshotObservation& observation() const noexcept {
    return observation_;
  }

private:
  ClimateSnapshotProvider& provider_;
  ClimateSnapshotObservation observation_{};
};

struct ClimateDiagnostics {
  std::uint32_t schema_version = kClimateDiagnosticsSchemaVersion;
  std::uint64_t monotonic_ms = 0U;
  ClimateSnapshotObservation input{};
  ::growbox::climate::ClimatePolicyMode policy_mode = ::growbox::climate::ClimatePolicyMode::Rule;
  ::growbox::climate::ClimateRuntimeStatus runtime_status =
      ::growbox::climate::ClimateRuntimeStatus::Ok;
  ::growbox::climate::ClimateLoopIoStatus io_status = ::growbox::climate::ClimateLoopIoStatus::Ok;
  bool ml_evaluated = false;
  bool authoritative_ml = false;
  ::growbox::climate::ClimatePolicyEvaluation rule{};
  ::growbox::climate::ClimatePolicyEvaluation ml_shadow{};
  ::growbox::climate::ClimatePolicyRequest final_safe_request{};
  ::growbox::climate::PreviousClimateActions confirmed_applied{};
  bool input_sampled = false;
  bool command_applied = false;
  bool fail_safe_attempted = false;
  bool fail_safe_applied = false;
  bool actuator_fault_latched = false;
};

ClimateDiagnostics
makeClimateDiagnostics(std::uint64_t monotonic_ms, const ClimateSnapshotObservation& input,
                       const ::growbox::climate::ClimateLoopResult& result,
                       const ::growbox::climate::ClimateRuntimeDecision& decision,
                       const ::growbox::climate::PreviousClimateActions& confirmed_applied,
                       bool actuator_fault_latched) noexcept;

} // namespace growbox::app::climate_io
