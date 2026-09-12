#include "climate/output/supervisor/ClimateOutputSupervisorSink.h"

#include "climate/output/OutputExecutionProjection.h"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstddef>

namespace growbox::app::climate_io {
namespace {

constexpr std::array<ClimateActuatorRole, kClimateActuatorRoleCount> kClimateRoles{
    ClimateActuatorRole::Heater,       ClimateActuatorRole::Cooler,
    ClimateActuatorRole::ExhaustFan,   ClimateActuatorRole::Humidifier,
    ClimateActuatorRole::Dehumidifier, ClimateActuatorRole::Co2Doser,
};

float normalizedLevel(float value) noexcept {
  return std::clamp(value, 0.0F, 1.0F);
}

::growbox::climate::ClimateExecutionKnownMask
executionKnownMask(ClimateActuatorRole role) noexcept {
  switch (role) {
  case ClimateActuatorRole::Heater:
    return ::growbox::climate::ClimateExecutionKnownHeater;
  case ClimateActuatorRole::Cooler:
    return ::growbox::climate::ClimateExecutionKnownCooler;
  case ClimateActuatorRole::ExhaustFan:
    return ::growbox::climate::ClimateExecutionKnownExhaustFan;
  case ClimateActuatorRole::Humidifier:
    return ::growbox::climate::ClimateExecutionKnownHumidifier;
  case ClimateActuatorRole::Dehumidifier:
    return ::growbox::climate::ClimateExecutionKnownDehumidifier;
  case ClimateActuatorRole::Co2Doser:
    return ::growbox::climate::ClimateExecutionKnownCo2Doser;
  }
  return ::growbox::climate::ClimateExecutionKnownNone;
}

} // namespace

ClimateOutputSupervisorSink::ClimateOutputSupervisorSink(
    ClimateSemanticOutputConfig climate_config,
    ::growbox::app::output::OutputSupervisorResolver& resolver,
    ::growbox::app::output::OutputSupervisorExecutor& executor,
    ::growbox::app::output::OutputStateStore& state_store) noexcept
    : climate_config_(climate_config),
      config_status_(validateClimateSemanticOutputConfig(climate_config_)), resolver_(resolver),
      executor_(executor), state_store_(state_store) {}

bool ClimateOutputSupervisorSink::valid() const noexcept {
  return config_status_ == ClimateSemanticOutputConfigStatus::Ok && resolver_.valid() &&
         executor_.valid() && state_store_.valid();
}

float ClimateOutputSupervisorSink::roleLevel(
    const ::growbox::climate::ClimatePolicyRequest& request, ClimateActuatorRole role) noexcept {
  switch (role) {
  case ClimateActuatorRole::Heater:
    return request.heater;
  case ClimateActuatorRole::Cooler:
    return request.cooler;
  case ClimateActuatorRole::ExhaustFan:
    return request.exhaust_fan;
  case ClimateActuatorRole::Humidifier:
    return request.humidifier;
  case ClimateActuatorRole::Dehumidifier:
    return request.dehumidifier;
  case ClimateActuatorRole::Co2Doser:
    return request.co2_doser;
  }
  return 0.0F;
}

void ClimateOutputSupervisorSink::setRoleLevel(::growbox::climate::ClimatePolicyRequest& request,
                                               ClimateActuatorRole role, float level) noexcept {
  switch (role) {
  case ClimateActuatorRole::Heater:
    request.heater = level;
    return;
  case ClimateActuatorRole::Cooler:
    request.cooler = level;
    return;
  case ClimateActuatorRole::ExhaustFan:
    request.exhaust_fan = level;
    return;
  case ClimateActuatorRole::Humidifier:
    request.humidifier = level;
    return;
  case ClimateActuatorRole::Dehumidifier:
    request.dehumidifier = level;
    return;
  case ClimateActuatorRole::Co2Doser:
    request.co2_doser = level;
    return;
  }
}

std::uint64_t ClimateOutputSupervisorSink::nextSequence() noexcept {
  ++sequence_;
  if (sequence_ == 0U) {
    ++sequence_;
  }
  return sequence_;
}

bool ClimateOutputSupervisorSink::buildControlIntent(
    const ::growbox::climate::ClimatePolicyRequest& request, std::uint64_t monotonic_ms,
    ::growbox::app::output::ControlIntent& intent) noexcept {
  intent = {};
  if (config_status_ != ClimateSemanticOutputConfigStatus::Ok) {
    return false;
  }

  std::size_t intent_index = 0U;
  for (const auto role : kClimateRoles) {
    const float raw_level = roleLevel(request, role);
    if (!std::isfinite(raw_level)) {
      intent = {};
      return false;
    }
    const float level = normalizedLevel(raw_level);
    const std::size_t role_index = climateRoleIndex(role);
    if (role_index >= climate_config_.roles.size()) {
      intent = {};
      return false;
    }
    const auto& mapping = climate_config_.roles[role_index];
    if (!mapping.enabled) {
      if (level != 0.0F) {
        intent = {};
        return false;
      }
      continue;
    }
    if (mapping.endpoint == kUnmappedClimateEndpoint || intent_index >= intent.endpoints.size() ||
        !::growbox::app::output::setEndpointIntent(intent.endpoints[intent_index], mapping.endpoint,
                                                   level)) {
      intent = {};
      return false;
    }
    ++intent_index;
  }

  intent.metadata.sequence = nextSequence();
  intent.metadata.monotonic_ms = monotonic_ms;
  intent.metadata.source = ::growbox::app::output::OutputSource::Climate;
  intent.metadata.reason = ::growbox::app::output::OutputReason::ClimateDecision;
  return true;
}

bool ClimateOutputSupervisorSink::reportTransportCompleted(
    const ::growbox::app::output::ExecutionReport& report) noexcept {
  for (std::size_t index = 0U; index < report.size; ++index) {
    if (report.steps[index].transport.status !=
        ::growbox::app::output::TransportStatus::Completed) {
      return false;
    }
  }
  return true;
}

bool ClimateOutputSupervisorSink::executeCycle(const ::growbox::app::output::ControlIntent& control,
                                               std::uint64_t monotonic_ms,
                                               bool& transport_completed) noexcept {
  transport_completed = false;
  last_resolution_ = {};
  last_report_ = {};
  if (!valid()) {
    return false;
  }

  ::growbox::app::output::OutputSupervisorCycleInput cycle{};
  cycle.mode = context_.mode;
  cycle.monotonic_ms = monotonic_ms;
  cycle.control = control;
  cycle.schedule = context_.schedule;
  cycle.manual = context_.manual;
  cycle.safety = context_.safety;

  if (!resolver_.resolve(cycle, state_store_, last_resolution_)) {
    last_resolution_ = {};
    return false;
  }
  if (!executor_.execute(last_resolution_, monotonic_ms, last_report_)) {
    last_report_ = {};
    return false;
  }
  transport_completed = reportTransportCompleted(last_report_);
  return true;
}

bool ClimateOutputSupervisorSink::projectExecutedClimate(
    ::growbox::climate::ClimateExecutionProjection& projection) const noexcept {
  projection = {};
  if (config_status_ != ClimateSemanticOutputConfigStatus::Ok) {
    return false;
  }

  ::growbox::app::output::ExecutedControlProjection executed{};
  if (!::growbox::app::output::buildExecutedControlProjection(last_resolution_, last_report_,
                                                              state_store_, executed)) {
    return false;
  }

  for (const auto role : kClimateRoles) {
    const std::size_t role_index = climateRoleIndex(role);
    if (role_index >= climate_config_.roles.size()) {
      projection = {};
      return false;
    }
    const auto mask = executionKnownMask(role);
    if (mask == ::growbox::climate::ClimateExecutionKnownNone) {
      projection = {};
      return false;
    }
    const auto& mapping = climate_config_.roles[role_index];
    if (!mapping.enabled) {
      // Unsupported climate roles are rejected unless requested at zero, so zero
      // is honest semantic execution truth for those roles.
      setRoleLevel(projection.executed, role, 0.0F);
      projection.known_mask |= static_cast<std::uint8_t>(mask);
      continue;
    }
    const auto* endpoint =
        ::growbox::app::output::findExecutedEndpointProjection(executed, mapping.endpoint);
    if (endpoint == nullptr) {
      projection = {};
      return false;
    }
    if (!endpoint->has_executed_state) {
      // Lifecycle arming/recovery can legitimately leave command truth unknown
      // for an endpoint that has not been executed yet. Preserve that unknown
      // state in the mask instead of fabricating OFF or reporting an I/O fault.
      continue;
    }
    const float level =
        endpoint->executed_state == ::growbox::app::output::BinaryOutputState::On ? 1.0F : 0.0F;
    setRoleLevel(projection.executed, role, level);
    projection.known_mask |= static_cast<std::uint8_t>(mask);
  }
  return true;
}

bool ClimateOutputSupervisorSink::apply(const ::growbox::climate::ClimatePolicyRequest& request,
                                        std::uint64_t monotonic_ms) noexcept {
  ::growbox::climate::ClimatePolicyRequest projection{};
  return applyAndReport(request, monotonic_ms, projection);
}

bool ClimateOutputSupervisorSink::applyAndReportExecution(
    const ::growbox::climate::ClimatePolicyRequest& request, std::uint64_t monotonic_ms,
    ::growbox::climate::ClimateExecutionProjection& execution) noexcept {
  execution = {};
  last_control_intent_ = {};
  ::growbox::app::output::ControlIntent control{};
  if (!buildControlIntent(request, monotonic_ms, control)) {
    return false;
  }

  last_control_intent_ = control;
  bool transport_completed = false;
  if (!executeCycle(control, monotonic_ms, transport_completed)) {
    return false;
  }
  if (!projectExecutedClimate(execution)) {
    execution = {};
    return false;
  }
  return transport_completed;
}

bool ClimateOutputSupervisorSink::applyAndReport(
    const ::growbox::climate::ClimatePolicyRequest& request, std::uint64_t monotonic_ms,
    ::growbox::climate::ClimatePolicyRequest& executed_projection) noexcept {
  ::growbox::climate::ClimateExecutionProjection execution{};
  const bool completed = applyAndReportExecution(request, monotonic_ms, execution);
  executed_projection = execution.executed;
  return completed && execution.known_mask ==
                          static_cast<std::uint8_t>(::growbox::climate::ClimateExecutionKnownAll);
}

bool ClimateOutputSupervisorSink::applyFailSafeOff(std::uint64_t monotonic_ms) noexcept {
  using ::growbox::app::output::OutputReason;
  using ::growbox::app::output::OutputSource;
  using ::growbox::app::output::SafetyConstraint;

  last_control_intent_ = {};
  last_resolution_ = {};
  last_report_ = {};
  if (!valid()) {
    return false;
  }

  ::growbox::app::output::SafetyEnvelope fail_safe{};
  fail_safe.metadata.sequence = nextSequence();
  fail_safe.metadata.monotonic_ms = monotonic_ms;
  fail_safe.metadata.source = OutputSource::Safety;
  fail_safe.metadata.reason = OutputReason::FaultContainment;

  std::size_t constraint_count = 0U;
  for (const auto role : kClimateRoles) {
    const std::size_t role_index = climateRoleIndex(role);
    if (role_index >= climate_config_.roles.size()) {
      return false;
    }
    const auto& mapping = climate_config_.roles[role_index];
    if (!mapping.enabled) {
      continue;
    }
    if (constraint_count >= fail_safe.endpoints.size() ||
        !::growbox::app::output::setSafetyConstraint(fail_safe.endpoints[constraint_count],
                                                     mapping.endpoint, SafetyConstraint::ForceOff,
                                                     OutputReason::FaultContainment)) {
      return false;
    }
    ++constraint_count;
  }

  // Existing hard-safety constraints override the generic climate fail-safe.
  // This preserves the non-bypassable thermal fan ForceOn / lamp ForceOff rules.
  for (const auto& hard : context_.safety.endpoints) {
    if (!::growbox::app::output::safetyConstraintActive(hard)) {
      continue;
    }
    bool replaced = false;
    for (std::size_t index = 0U; index < constraint_count; ++index) {
      if (fail_safe.endpoints[index].endpoint == hard.endpoint) {
        fail_safe.endpoints[index] = hard;
        replaced = true;
        break;
      }
    }
    if (!replaced) {
      if (constraint_count >= fail_safe.endpoints.size()) {
        return false;
      }
      fail_safe.endpoints[constraint_count++] = hard;
    }
  }

  ::growbox::app::output::OutputSupervisorCycleInput cycle{};
  cycle.mode = context_.mode;
  cycle.monotonic_ms = monotonic_ms;
  cycle.safety = fail_safe;
  if (!resolver_.resolve(cycle, state_store_, last_resolution_)) {
    last_resolution_ = {};
    return false;
  }
  if (!executor_.execute(last_resolution_, monotonic_ms, last_report_)) {
    last_report_ = {};
    return false;
  }
  return reportTransportCompleted(last_report_);
}

} // namespace growbox::app::climate_io
