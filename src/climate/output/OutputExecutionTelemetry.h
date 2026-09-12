#pragma once

#include "climate/output/policy/OutputPolicyConfig.h"
#include "climate/output/supervisor/OutputSupervisorResolver.h"

#include <array>
#include <cstddef>
#include <cstdint>

namespace growbox::app::output {

struct OutputIntentTelemetry {
  bool active = false;
  NormalizedOutputLevel level = 0.0F;
};

struct OutputEndpointExecutionTelemetry {
  OutputEndpointId endpoint = kInvalidOutputEndpoint;

  OutputIntentTelemetry control{};
  OutputIntentTelemetry schedule{};
  OutputIntentTelemetry manual{};

  bool safety_active = false;
  SafetyConstraint safety_constraint = SafetyConstraint::Allow;
  OutputReason safety_reason = OutputReason::None;

  bool selected = false;
  NormalizedOutputLevel selected_level = 0.0F;
  OutputSource selected_source = OutputSource::None;
  OutputReason selected_reason = OutputReason::None;

  bool resolved = false;
  BinaryOutputState resolved_state = BinaryOutputState::Off;
  bool held_by_dwell = false;
  bool safety_override = false;
  bool inhibited = false;

  bool attempt_known = false;
  bool attempted_this_cycle = false;
  BinaryOutputState attempt_state = BinaryOutputState::Off;
  OutputSource attempt_source = OutputSource::None;
  OutputReason attempt_reason = OutputReason::None;
  TransportStatus transport_status = TransportStatus::NotAttempted;
  TransportError transport_error = TransportError::None;

  bool last_command_known = false;
  BinaryOutputState last_command_state = BinaryOutputState::Off;
  OutputSource last_command_source = OutputSource::None;
  OutputReason last_command_reason = OutputReason::None;

  PhysicalOutputState physical_state = PhysicalOutputState::Unknown;
  bool physical_independent = false;
};

struct OutputExecutionTelemetrySnapshot {
  static constexpr std::uint8_t kVersion = 2U;

  std::uint8_t version = kVersion;
  SupervisorMode mode = SupervisorMode::BootLocked;
  bool transport_active = false;
  bool lifecycle_active = false;
  OutputLifecycleEvent lifecycle_event = OutputLifecycleEvent::Boot;
  bool automation_requested = false;
  bool safety_latched = false;
  std::uint32_t safety_reason_code = 0U;
  std::array<OutputEndpointExecutionTelemetry, kOutputEndpointCapacity> endpoints{};
  std::uint8_t endpoint_count = 0U;
};

bool buildOutputExecutionTelemetry(const OutputSupervisorCycleInput& cycle,
                                   const OutputSupervisorResolution& resolution,
                                   const OutputStateStore& state_store, bool transport_active,
                                   bool lifecycle_active, OutputLifecycleEvent lifecycle_event,
                                   bool automation_requested,
                                   OutputExecutionTelemetrySnapshot& output) noexcept;

} // namespace growbox::app::output
