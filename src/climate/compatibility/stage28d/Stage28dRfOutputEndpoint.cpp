#include "climate/compatibility/stage28d/Stage28dRfOutputEndpoint.h"

#include "climate/output/OutputBindings.h"

#include <cmath>
#include <limits>

namespace growbox::app::climate_io::stage28d {
namespace {

constexpr std::size_t kInvalidStateIndex = std::numeric_limits<std::size_t>::max();

::growbox::app::output::OutputCommand makeBinaryCommand(ClimateEndpointId endpoint,
                                                        bool on) noexcept {
  return {
      endpoint,
      on ? ::growbox::app::output::BinaryOutputState::On
         : ::growbox::app::output::BinaryOutputState::Off,
  };
}

} // namespace

Stage28dRfOutputEndpoint::Stage28dRfOutputEndpoint(
    RfOutputEndpointConfig config, ::growbox::app::output::OutputTransport& transport,
    ::growbox::app::output::OutputStateStore* shadow_state_store) noexcept
    : config_(config), transport_(transport), shadow_state_store_(shadow_state_store) {}

std::size_t Stage28dRfOutputEndpoint::stateIndex(ClimateEndpointId endpoint) noexcept {
  if (endpoint == kExhaustFanEndpoint) {
    return 0U;
  }
  if (endpoint == kScheduledLightEndpoint) {
    return 1U;
  }
  if (endpoint == kHumidifierEndpoint) {
    return 2U;
  }
  return kInvalidStateIndex;
}

void Stage28dRfOutputEndpoint::mirrorDesiredResolved(ClimateEndpointId endpoint, bool desired_on,
                                                     bool resolved_on) noexcept {
  if (shadow_state_store_ == nullptr) {
    return;
  }
  (void)shadow_state_store_->recordDesired(makeBinaryCommand(endpoint, desired_on));
  (void)shadow_state_store_->recordResolved(makeBinaryCommand(endpoint, resolved_on));
}

bool Stage28dRfOutputEndpoint::initializeSafeState(std::uint64_t monotonic_ms) noexcept {
  if (!config_.enabled) {
    return false;
  }
  bool ok = true;
  mirrorDesiredResolved(kScheduledLightEndpoint, false, false);
  ok = applyBinary(kScheduledLightEndpoint, false, monotonic_ms, true) && ok;
  mirrorDesiredResolved(kExhaustFanEndpoint, false, false);
  ok = applyBinary(kExhaustFanEndpoint, false, monotonic_ms, true) && ok;
  mirrorDesiredResolved(kHumidifierEndpoint, false, false);
  ok = applyBinary(kHumidifierEndpoint, false, monotonic_ms, true) && ok;
  return ok;
}

bool Stage28dRfOutputEndpoint::write(ClimateEndpointId endpoint, float normalized_level,
                                     std::uint64_t monotonic_ms) noexcept {
  if (!config_.enabled || !std::isfinite(normalized_level) || config_.on_threshold < 0.0F ||
      config_.on_threshold > 1.0F || endpoint == kScheduledLightEndpoint) {
    return false;
  }
  const bool requested_on = normalized_level >= config_.on_threshold;
  const bool effective_on =
      endpoint == kExhaustFanEndpoint && safety_force_exhaust_ ? true : requested_on;
  mirrorDesiredResolved(endpoint, requested_on, effective_on);
  return applyBinary(endpoint, effective_on, monotonic_ms);
}

bool Stage28dRfOutputEndpoint::forceOff(ClimateEndpointId endpoint,
                                        std::uint64_t monotonic_ms) noexcept {
  if (!config_.enabled || endpoint == kScheduledLightEndpoint) {
    return false;
  }
  mirrorDesiredResolved(endpoint, false, false);
  return applyBinary(endpoint, false, monotonic_ms, true);
}

bool Stage28dRfOutputEndpoint::writeScheduledLight(bool on, std::uint64_t monotonic_ms) noexcept {
  if (!config_.enabled) {
    return false;
  }
  mirrorDesiredResolved(kScheduledLightEndpoint, on, on);
  return applyBinary(kScheduledLightEndpoint, on, monotonic_ms);
}

bool Stage28dRfOutputEndpoint::stateKnown(ClimateEndpointId endpoint) const noexcept {
  const std::size_t index = stateIndex(endpoint);
  return index != kInvalidStateIndex && states_[index].known;
}

bool Stage28dRfOutputEndpoint::stateOn(ClimateEndpointId endpoint) const noexcept {
  const std::size_t index = stateIndex(endpoint);
  return index != kInvalidStateIndex && states_[index].known && states_[index].on;
}

bool Stage28dRfOutputEndpoint::applyBinary(ClimateEndpointId endpoint, bool on,
                                           std::uint64_t monotonic_ms, bool force_send) noexcept {
  const std::size_t index = stateIndex(endpoint);
  if (index == kInvalidStateIndex) {
    return false;
  }
  EndpointState& state = states_[index];
  if (!force_send && state.known && state.on == on) {
    return true;
  }

  const auto command = makeBinaryCommand(endpoint, on);
  const auto result = transport_.send(command);
  if (shadow_state_store_ != nullptr) {
    (void)shadow_state_store_->recordAttempt(command, monotonic_ms, result);
  }
  if (result.status != ::growbox::app::output::TransportStatus::Completed) {
    ++transmit_error_count_;
    return false;
  }

  ++transmit_count_;
  state.known = true;
  state.on = on;
  state.changed_ms = monotonic_ms;
  return true;
}

} // namespace growbox::app::climate_io::stage28d
