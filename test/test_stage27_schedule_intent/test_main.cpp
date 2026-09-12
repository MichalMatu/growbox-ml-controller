#include "climate/OutputBindings.h"
#include "climate/output/OutputIntents.h"
#include "climate/runtime/schedule/Stage27ScheduleIntentAdapter.h"
#include "climate/runtime/schedule/Stage27ScheduleProfile.h"

#include <array>
#include <cassert>
#include <cstdint>

namespace {

namespace output = growbox::app::output;
using growbox::app::climate_io::ClimateScheduleConfigSnapshot;
using growbox::app::climate_io::ClimateWallClockSnapshot;
using growbox::app::climate_io::runtime::buildStage27ScheduleIntent;
using growbox::app::climate_io::runtime::resolveMintScheduleProfile;
using growbox::app::climate_io::stage28d::kScheduledLightEndpoint;

ClimateWallClockSnapshot clockAt(std::uint64_t unix_time_s) {
  return {true, unix_time_s};
}

output::ScheduleIntent intentAt(std::uint64_t unix_time_s, std::uint64_t sequence = 7U,
                                std::uint64_t monotonic_ms = 1234U) {
  output::ScheduleIntent intent{};
  assert(buildStage27ScheduleIntent(monotonic_ms, clockAt(unix_time_s), sequence, intent));
  return intent;
}

void assertSingleLampIntent(const output::ScheduleIntent& intent, float expected_level) {
  assert(intent.metadata.source == output::OutputSource::Schedule);
  assert(intent.metadata.reason == output::OutputReason::ScheduleRequest);
  assert(output::endpointIntentActive(intent.endpoints[0]));
  assert(intent.endpoints[0].endpoint == kScheduledLightEndpoint);
  assert(intent.endpoints[0].level == expected_level);
  assert(!output::endpointIntentActive(intent.endpoints[1]));
  assert(!output::endpointIntentActive(intent.endpoints[2]));
}

void testMetadataAndSingleEndpoint() {
  const auto intent = intentAt(1768453200ULL, 91U, 4567U); // Warsaw 06:00 winter
  assertSingleLampIntent(intent, 1.0F);
  assert(intent.metadata.sequence == 91U);
  assert(intent.metadata.monotonic_ms == 4567U);
}

void testWarsawLightingBoundariesMatchExistingProfile() {
  constexpr std::array<std::uint64_t, 8U> kEpochs{
      1768453199ULL, // winter 05:59:59 local
      1768453200ULL, // winter 06:00:00 local
      1768510799ULL, // winter 21:59:59 local
      1768510800ULL, // winter 22:00:00 local
      1784087999ULL, // summer 05:59:59 local
      1784088000ULL, // summer 06:00:00 local
      1784145599ULL, // summer 21:59:59 local
      1784145600ULL, // summer 22:00:00 local
  };
  constexpr std::array<float, 8U> kExpected{0.0F, 1.0F, 1.0F, 0.0F, 0.0F, 1.0F, 1.0F, 0.0F};

  for (std::size_t i = 0U; i < kEpochs.size(); ++i) {
    ClimateScheduleConfigSnapshot profile{};
    const auto clock = clockAt(kEpochs[i]);
    assert(resolveMintScheduleProfile(clock, profile));
    const auto intent = intentAt(kEpochs[i], 100U + i, 500U + i);
    assert(profile.schedule.light_level == kExpected[i]);
    assertSingleLampIntent(intent, profile.schedule.light_level);
  }
}

void testInvalidClockFailsClosedAndClearsIntent() {
  output::ScheduleIntent intent{};
  intent.metadata.source = output::OutputSource::Manual;
  assert(output::setEndpointIntent(intent.endpoints[0], kScheduledLightEndpoint, 1.0F));

  ClimateWallClockSnapshot invalid{};
  assert(!buildStage27ScheduleIntent(1U, invalid, 2U, intent));
  assert(intent.metadata.source == output::OutputSource::None);
  assert(intent.metadata.reason == output::OutputReason::None);
  for (const auto& endpoint : intent.endpoints) {
    assert(!output::endpointIntentActive(endpoint));
  }
}

} // namespace

int main() {
  testMetadataAndSingleEndpoint();
  testWarsawLightingBoundariesMatchExistingProfile();
  testInvalidClockFailsClosedAndClearsIntent();
  return 0;
}
