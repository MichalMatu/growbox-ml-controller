#include "climate/ClimateCompositeInput.h"

namespace growbox::app::climate_io {

bool CompositeClimateSnapshotProvider::snapshot(std::uint64_t monotonic_ms,
                                                ClimateInputSnapshot& output) noexcept {
  output = {};

  ClimateWallClockSnapshot clock{};
  if (!clock_source_.sample(monotonic_ms, clock) || !clock.valid) {
    return false;
  }

  ClimateScheduleConfigSnapshot schedule_config{};
  if (!schedule_config_source_.resolve(monotonic_ms, clock, schedule_config)) {
    return false;
  }

  InsideEnvironmentSnapshot inside{};
  if (inside_source_.sample(monotonic_ms, inside)) {
    output.measurements.air_temperature_c = inside.air_temperature_c;
    output.measurements.relative_humidity_pct = inside.relative_humidity_pct;
    output.measurements.co2_ppm = inside.co2_ppm;
  }

  OutsideEnvironmentSnapshot outside{};
  if (outside_source_.sample(monotonic_ms, outside)) {
    output.measurements.outside_temperature_c = outside.air_temperature_c;
    output.measurements.outside_humidity_pct = outside.relative_humidity_pct;
  }

  output.humidity_control_mode = schedule_config.humidity_control_mode;
  output.targets = schedule_config.targets;
  output.schedule = schedule_config.schedule;
  output.capabilities = schedule_config.capabilities;
  output.sensor_timeout_ms = schedule_config.sensor_timeout_ms;
  return true;
}

} // namespace growbox::app::climate_io
