#include "climate/runtime/EuropeWarsawTime.h"

#include <cassert>
#include <cstdint>

using growbox::app::climate_io::runtime::EuropeWarsawLocalTime;
using growbox::app::climate_io::runtime::resolveEuropeWarsawLocalTime;

namespace {

EuropeWarsawLocalTime local(std::uint64_t epoch) {
  EuropeWarsawLocalTime result{};
  assert(resolveEuropeWarsawLocalTime(epoch, result));
  return result;
}

void testWinterAndSummerOffsets() {
  const auto winter = local(1768453200ULL); // 2026-01-15 05:00:00 UTC
  assert(winter.year == 2026U);
  assert(winter.month == 1U);
  assert(winter.day == 15U);
  assert(winter.hour == 6U);
  assert(winter.utc_offset_seconds == 3600);
  assert(!winter.daylight_saving);

  const auto summer = local(1784088000ULL); // 2026-07-15 04:00:00 UTC
  assert(summer.year == 2026U);
  assert(summer.month == 7U);
  assert(summer.day == 15U);
  assert(summer.hour == 6U);
  assert(summer.utc_offset_seconds == 7200);
  assert(summer.daylight_saving);
}

void testDstStartBoundary() {
  const auto before = local(1774745999ULL); // 2026-03-29 00:59:59 UTC
  assert(before.hour == 1U);
  assert(before.minute == 59U);
  assert(before.second == 59U);
  assert(before.utc_offset_seconds == 3600);
  assert(!before.daylight_saving);

  const auto after = local(1774746000ULL); // 2026-03-29 01:00:00 UTC
  assert(after.hour == 3U);
  assert(after.minute == 0U);
  assert(after.second == 0U);
  assert(after.utc_offset_seconds == 7200);
  assert(after.daylight_saving);
}

void testDstEndBoundary() {
  const auto before = local(1792889999ULL); // 2026-10-25 00:59:59 UTC
  assert(before.hour == 2U);
  assert(before.minute == 59U);
  assert(before.second == 59U);
  assert(before.utc_offset_seconds == 7200);
  assert(before.daylight_saving);

  const auto after = local(1792890000ULL); // 2026-10-25 01:00:00 UTC
  assert(after.hour == 2U);
  assert(after.minute == 0U);
  assert(after.second == 0U);
  assert(after.utc_offset_seconds == 3600);
  assert(!after.daylight_saving);
}

void testLightingBoundariesLocalTime() {
  const auto winter_before_on = local(1768453199ULL);
  const auto winter_on = local(1768453200ULL);
  const auto winter_before_off = local(1768510799ULL);
  const auto winter_off = local(1768510800ULL);
  assert(winter_before_on.hour == 5U);
  assert(winter_on.hour == 6U);
  assert(winter_before_off.hour == 21U);
  assert(winter_off.hour == 22U);

  const auto summer_before_on = local(1784087999ULL);
  const auto summer_on = local(1784088000ULL);
  const auto summer_before_off = local(1784145599ULL);
  const auto summer_off = local(1784145600ULL);
  assert(summer_before_on.hour == 5U);
  assert(summer_on.hour == 6U);
  assert(summer_before_off.hour == 21U);
  assert(summer_off.hour == 22U);
}

void testSupportedRange() {
  assert(local(946684800ULL).year == 2000U);
  assert(local(7258118399ULL).year == 2200U || local(7258118399ULL).year == 2199U);
}

} // namespace

int main() {
  testWinterAndSummerOffsets();
  testDstStartBoundary();
  testDstEndBoundary();
  testLightingBoundariesLocalTime();
  return 0;
}
