#include "climate/runtime/schedule/ScheduleIntentAdapter.h"

#include "climate/OutputBindings.h"
#include "climate/runtime/schedule/ScheduleProfile.h"

namespace growbox::app::climate_io::runtime {

bool buildScheduleIntent(std::uint64_t monotonic_ms, const ClimateWallClockSnapshot& clock,
                         std::uint64_t sequence,
                         ::growbox::app::output::ScheduleIntent& output) noexcept {
  output = {};

  ClimateScheduleConfigSnapshot profile{};
  if (!resolveMintScheduleProfile(clock, profile)) {
    return false;
  }

  ::growbox::app::output::ScheduleIntent intent{};
  intent.metadata.sequence = sequence;
  intent.metadata.monotonic_ms = monotonic_ms;
  intent.metadata.source = ::growbox::app::output::OutputSource::Schedule;
  intent.metadata.reason = ::growbox::app::output::OutputReason::ScheduleRequest;
  if (!::growbox::app::output::setEndpointIntent(
          intent.endpoints[0], stage28d::kScheduledLightEndpoint, profile.schedule.light_level)) {
    return false;
  }

  output = intent;
  return true;
}

} // namespace growbox::app::climate_io::runtime
