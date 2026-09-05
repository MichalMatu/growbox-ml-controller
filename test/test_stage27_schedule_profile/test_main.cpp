#include "climate/runtime/Stage27ScheduleProfile.h"

#include <cassert>

using growbox::app::climate_io::ClimateScheduleConfigSnapshot;
using growbox::app::climate_io::runtime::buildMintScheduleProfile;

namespace {

void assertHardwareCapabilities(const ClimateScheduleConfigSnapshot& profile) {
  assert(!profile.capabilities.heater);
  assert(!profile.capabilities.cooler);
  assert(profile.capabilities.exhaust_fan);
  assert(profile.capabilities.humidifier);
  assert(!profile.capabilities.dehumidifier);
  assert(!profile.capabilities.co2_doser);
}

void testDayProfile() {
  ClimateScheduleConfigSnapshot profile{};
  assert(buildMintScheduleProfile(6U, profile));
  assertHardwareCapabilities(profile);
  assert(profile.schedule.light_level == 1.0F);
  assert(profile.targets.air_temperature_c == 24.5F);
  assert(profile.targets.relative_humidity_pct == 58.0F);
  assert(profile.targets.air_vpd_kpa == 1.2F);
  assert(!profile.targets.co2_enabled);
  assert(profile.targets.co2_ppm == 0.0F);
}

void testNightProfileAndBoundaries() {
  ClimateScheduleConfigSnapshot profile{};
  assert(buildMintScheduleProfile(5U, profile));
  assert(profile.schedule.light_level == 0.0F);
  assert(buildMintScheduleProfile(21U, profile));
  assert(profile.schedule.light_level == 1.0F);
  assert(buildMintScheduleProfile(22U, profile));
  assert(profile.schedule.light_level == 0.0F);
  assert(profile.targets.air_temperature_c == 21.5F);
  assert(profile.targets.relative_humidity_pct == 65.0F);
  assert(profile.targets.air_vpd_kpa == 0.9F);
  assertHardwareCapabilities(profile);
}

void testInvalidHourFailsClosed() {
  ClimateScheduleConfigSnapshot profile{};
  profile.capabilities.heater = true;
  assert(!buildMintScheduleProfile(24U, profile));
  assert(!profile.capabilities.heater);
  assert(profile.schedule.light_level == 0.0F);
}

} // namespace

int main() {
  testDayProfile();
  testNightProfileAndBoundaries();
  testInvalidHourFailsClosed();
  return 0;
}
