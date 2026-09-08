#pragma once

#include "climate/ClimateIoAdapters.h"

#include <cstdint>
#include <optional>

namespace growbox::app::climate_io {

class ClimateApplication {
public:
  ClimateApplication(::growbox::climate::ClimateRuntimeController& runtime,
                     ClimateSnapshotProvider& snapshot_provider,
                     ClimateRoleDriver& role_driver) noexcept;
  ClimateApplication(::growbox::climate::ClimateRuntimeController& runtime,
                     ClimateSnapshotProvider& snapshot_provider,
                     ::growbox::climate::ClimateActuatorSink& actuator_sink) noexcept;

  ::growbox::climate::ClimateLoopResult
  tick(std::uint64_t monotonic_ms, ::growbox::climate::ClimateRuntimeDecision& decision) noexcept;
  void reset() noexcept;

  bool actuatorFaultLatched() const noexcept {
    return control_loop_.actuatorFaultLatched();
  }

  const ::growbox::climate::PreviousClimateActions& previousApplied() const noexcept {
    return control_loop_.previousApplied();
  }

private:
  ClimateInputAdapter input_adapter_;
  std::optional<ClimateActuatorAdapter> actuator_adapter_;
  ::growbox::climate::ClimateControlLoop control_loop_;
};

} // namespace growbox::app::climate_io
