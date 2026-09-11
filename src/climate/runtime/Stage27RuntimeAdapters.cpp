#include "climate/runtime/Stage27RuntimeAdapters.h"

#include "climate/runtime/schedule/Stage27ScheduleProfile.h"

namespace growbox::app::climate_io::runtime {

bool LockedFakeRoleDriver::apply(ClimateActuatorRole, float, std::uint64_t) noexcept {
  return true;
}

Stage27InsideSource::Stage27InsideSource(native::BleClimateScanner& ble,
                                         native::Scd41InsideSource& scd41) noexcept
    : ble_(ble), scd41_(scd41) {}

bool Stage27InsideSource::sample(std::uint64_t monotonic_ms,
                                 InsideEnvironmentSnapshot& output) noexcept {
  output = {};

  native::BleClimateReading tp357{};
  const bool tp357_sampled = ble_.sampleTp357(monotonic_ms, tp357);
  if (tp357_sampled) {
    output.air_temperature_c = {tp357.temperature_c, true, tp357.age_ms};
    output.relative_humidity_pct = {tp357.relative_humidity_pct, true, tp357.age_ms};
  }

  InsideEnvironmentSnapshot scd41{};
  if (scd41_.sample(monotonic_ms, scd41) && scd41.co2_ppm.valid) {
    output.co2_ppm = scd41.co2_ppm;
  }

  return tp357_sampled || output.co2_ppm.valid;
}

Stage27NearbySource::Stage27NearbySource(native::BleClimateScanner& ble) noexcept : ble_(ble) {}

bool Stage27NearbySource::sample(std::uint64_t monotonic_ms,
                                 OutsideEnvironmentSnapshot& output) noexcept {
  output = {};
  native::BleClimateReading xiaomi{};
  if (!ble_.sampleXiaomi(monotonic_ms, xiaomi)) {
    return false;
  }
  output.air_temperature_c = {xiaomi.temperature_c, true, xiaomi.age_ms};
  output.relative_humidity_pct = {xiaomi.relative_humidity_pct, true, xiaomi.age_ms};
  return true;
}

bool FixedStage27ScheduleConfigSource::resolve(std::uint64_t, const ClimateWallClockSnapshot& clock,
                                               ClimateScheduleConfigSnapshot& output) noexcept {
  return resolveMintScheduleProfile(clock, output);
}

} // namespace growbox::app::climate_io::runtime
