#include "climate/ClimateIoAdapters.h"

namespace growbox::app::climate_io {

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

} // namespace growbox::app::climate_io
