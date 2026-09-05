#include "climate/Stage28dRfOutputEndpoint.h"

#include "climate/Stage28dOutputBindings.h"
#include "climate/rf433/ClimateRf433EndpointRegistry.h"

#include <cmath>
#include <limits>

namespace growbox::app::climate_io::stage28d {
namespace {

constexpr std::size_t kInvalidStateIndex = std::numeric_limits<std::size_t>::max();

} // namespace

Stage28dRfOutputEndpoint::Stage28dRfOutputEndpoint(RfOutputEndpointConfig config,
                                                   RfCommandTransmitter& transmitter) noexcept
    : config_(config), transmitter_(transmitter) {}

std::size_t Stage28dRfOutputEndpoint::stateIndex(ClimateEndpointId endpoint) noexcept {
  if (endpoint == rf433::kRemoteSocket1ClimateEndpoint) {
    return 0U;
  }
  if (endpoint == rf433::kRemoteSocket2ClimateEndpoint) {
    return 1U;
  }
  if (endpoint == rf433::kRemoteSocket3ClimateEndpoint) {
    return 2U;
  }
  return kInvalidStateIndex;
}

bool Stage28dRfOutputEndpoint::initializeSafeState(std::uint64_t monotonic_ms) noexcept {
  if (!config_.enabled) {
    return false;
  }
  bool ok = true;
  ok = applyBinary(kScheduledLightEndpoint, false, monotonic_ms, true) && ok;
  ok = applyBinary(kExhaustFanEndpoint, false, monotonic_ms, true) && ok;
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
  const bool effective_on = endpoint == kExhaustFanEndpoint && safety_force_exhaust_
                                ? true
                                : requested_on;
  return applyBinary(endpoint, effective_on, monotonic_ms);
}

bool Stage28dRfOutputEndpoint::forceOff(ClimateEndpointId endpoint,
                                       std::uint64_t monotonic_ms) noexcept {
  if (!config_.enabled || endpoint == kScheduledLightEndpoint) {
    return false;
  }
  return applyBinary(endpoint, false, monotonic_ms, true);
}

bool Stage28dRfOutputEndpoint::writeScheduledLight(bool on, std::uint64_t monotonic_ms) noexcept {
  if (!config_.enabled) {
    return false;
  }
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

  const rf433::ClimateRf433EndpointBinding* binding = rf433::findClimateRf433Endpoint(endpoint);
  if (binding == nullptr || binding->hardware == nullptr) {
    return false;
  }
  const rf433::FrameConfig& frame = on ? binding->hardware->on : binding->hardware->off;
  if (!transmitter_.transmit(frame)) {
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
