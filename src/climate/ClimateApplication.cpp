#include "climate/ClimateApplication.h"

namespace growbox::app::climate_io {

ClimateApplication::ClimateApplication(::growbox::climate::ClimateRuntimeController& runtime,
                                       ClimateSnapshotProvider& snapshot_provider,
                                       ClimateRoleDriver& role_driver) noexcept
    : input_adapter_(snapshot_provider), actuator_adapter_(role_driver),
      control_loop_(runtime, input_adapter_, actuator_adapter_) {}

::growbox::climate::ClimateLoopResult
ClimateApplication::tick(std::uint64_t monotonic_ms,
                         ::growbox::climate::ClimateRuntimeDecision& decision) noexcept {
  return control_loop_.tick(monotonic_ms, decision);
}

void ClimateApplication::reset() noexcept {
  control_loop_.reset();
}

} // namespace growbox::app::climate_io
