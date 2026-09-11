#include "climate/ClimateIoAdapters.h"

namespace growbox::app::climate_io {
namespace {

void setRoleLevel(::growbox::climate::ClimatePolicyRequest& request, ClimateActuatorRole role,
                  float level) noexcept {
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

} // namespace

bool ClimateInputAdapter::sample(std::uint64_t monotonic_ms,
                                 ::growbox::climate::ClimateControllerInput& input) noexcept {
  ClimateInputSnapshot snapshot{};
  if (!provider_.snapshot(monotonic_ms, snapshot)) {
    input = {};
    return false;
  }

  input = {};
  input.state.measurements = snapshot.measurements;
  input.humidity_control_mode = snapshot.humidity_control_mode;
  input.targets = snapshot.targets;
  input.schedule = snapshot.schedule;
  input.capabilities = snapshot.capabilities;
  input.sensor_timeout_ms = snapshot.sensor_timeout_ms;
  return true;
}

bool ClimateActuatorAdapter::apply(const ::growbox::climate::ClimatePolicyRequest& request,
                                   std::uint64_t monotonic_ms) noexcept {
  bool all_applied = true;
  const auto apply_role = [this, monotonic_ms, &all_applied](ClimateActuatorRole role,
                                                             float level) noexcept {
    const bool applied = driver_.apply(role, level, monotonic_ms);
    all_applied = applied && all_applied;
  };

  apply_role(ClimateActuatorRole::Heater, request.heater);
  apply_role(ClimateActuatorRole::Cooler, request.cooler);
  apply_role(ClimateActuatorRole::ExhaustFan, request.exhaust_fan);
  apply_role(ClimateActuatorRole::Humidifier, request.humidifier);
  apply_role(ClimateActuatorRole::Dehumidifier, request.dehumidifier);
  apply_role(ClimateActuatorRole::Co2Doser, request.co2_doser);
  return all_applied;
}

bool ClimateActuatorAdapter::applyAndReport(
    const ::growbox::climate::ClimatePolicyRequest& request, std::uint64_t monotonic_ms,
    ::growbox::climate::ClimatePolicyRequest& confirmed_applied) noexcept {
  confirmed_applied = {};
  if (!apply(request, monotonic_ms)) {
    return false;
  }

  const auto report = [this, &confirmed_applied](ClimateActuatorRole role,
                                                 float requested_level) noexcept {
    setRoleLevel(confirmed_applied, role, driver_.appliedLevel(role, requested_level));
  };
  report(ClimateActuatorRole::Heater, request.heater);
  report(ClimateActuatorRole::Cooler, request.cooler);
  report(ClimateActuatorRole::ExhaustFan, request.exhaust_fan);
  report(ClimateActuatorRole::Humidifier, request.humidifier);
  report(ClimateActuatorRole::Dehumidifier, request.dehumidifier);
  report(ClimateActuatorRole::Co2Doser, request.co2_doser);
  return true;
}

bool ClimateActuatorAdapter::applyFailSafeOff(std::uint64_t monotonic_ms) noexcept {
  bool all_off = true;
  constexpr ClimateActuatorRole kRoles[]{
      ClimateActuatorRole::Heater,       ClimateActuatorRole::Cooler,
      ClimateActuatorRole::ExhaustFan,   ClimateActuatorRole::Humidifier,
      ClimateActuatorRole::Dehumidifier, ClimateActuatorRole::Co2Doser,
  };
  for (const auto role : kRoles) {
    all_off = driver_.forceSafeOff(role, monotonic_ms) && all_off;
  }
  return all_off;
}

} // namespace growbox::app::climate_io
