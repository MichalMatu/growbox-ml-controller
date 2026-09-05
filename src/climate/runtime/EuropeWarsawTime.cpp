#include "climate/runtime/EuropeWarsawTime.h"

#include <cstdint>

namespace growbox::app::climate_io::runtime {
namespace {

constexpr std::int32_t kCetOffsetSeconds = 3600;
constexpr std::int32_t kCestOffsetSeconds = 7200;

bool leapYear(std::int64_t year) noexcept {
  return (year % 4 == 0 && year % 100 != 0) || year % 400 == 0;
}

std::uint8_t daysInMonth(std::int64_t year, std::uint8_t month) noexcept {
  constexpr std::uint8_t kDays[]{31U, 28U, 31U, 30U, 31U, 30U, 31U, 31U, 30U, 31U, 30U, 31U};
  if (month == 0U || month > 12U) {
    return 0U;
  }
  if (month == 2U && leapYear(year)) {
    return 29U;
  }
  return kDays[month - 1U];
}

std::int64_t daysFromCivil(std::int64_t year, unsigned month, unsigned day) noexcept {
  year -= month <= 2U ? 1 : 0;
  const std::int64_t era = (year >= 0 ? year : year - 399) / 400;
  const unsigned yoe = static_cast<unsigned>(year - era * 400);
  const unsigned adjusted_month = month > 2U ? month - 3U : month + 9U;
  const unsigned doy = (153U * adjusted_month + 2U) / 5U + day - 1U;
  const unsigned doe = yoe * 365U + yoe / 4U - yoe / 100U + doy;
  return era * 146097 + static_cast<std::int64_t>(doe) - 719468;
}

void civilFromDays(std::int64_t days, std::int64_t& year, unsigned& month, unsigned& day) noexcept {
  days += 719468;
  const std::int64_t era = (days >= 0 ? days : days - 146096) / 146097;
  const unsigned doe = static_cast<unsigned>(days - era * 146097);
  const unsigned yoe = (doe - doe / 1460U + doe / 36524U - doe / 146096U) / 365U;
  year = static_cast<std::int64_t>(yoe) + era * 400;
  const unsigned doy = doe - (365U * yoe + yoe / 4U - yoe / 100U);
  const unsigned mp = (5U * doy + 2U) / 153U;
  day = doy - (153U * mp + 2U) / 5U + 1U;
  month = mp < 10U ? mp + 3U : mp - 9U;
  year += month <= 2U ? 1 : 0;
}

std::uint8_t weekdaySundayZero(std::int64_t year, std::uint8_t month, std::uint8_t day) noexcept {
  const std::int64_t days = daysFromCivil(year, month, day);
  const std::int64_t normalized = (days + 4) % 7;
  return static_cast<std::uint8_t>(normalized >= 0 ? normalized : normalized + 7);
}

std::uint8_t lastSundayOfMonth(std::int64_t year, std::uint8_t month) noexcept {
  const std::uint8_t last_day = daysInMonth(year, month);
  return static_cast<std::uint8_t>(last_day - weekdaySundayZero(year, month, last_day));
}

std::uint64_t unixFromCivilUtc(std::int64_t year, std::uint8_t month, std::uint8_t day,
                               std::uint8_t hour) noexcept {
  const std::int64_t days = daysFromCivil(year, month, day);
  if (days < 0) {
    return 0U;
  }
  return static_cast<std::uint64_t>(days) * 86400ULL +
         static_cast<std::uint64_t>(hour) * 3600ULL;
}

bool isEuropeWarsawDst(std::uint64_t utc_unix_time_s, std::int64_t year) noexcept {
  const std::uint8_t march_sunday = lastSundayOfMonth(year, 3U);
  const std::uint8_t october_sunday = lastSundayOfMonth(year, 10U);
  const std::uint64_t start = unixFromCivilUtc(year, 3U, march_sunday, 1U);
  const std::uint64_t end = unixFromCivilUtc(year, 10U, october_sunday, 1U);
  return utc_unix_time_s >= start && utc_unix_time_s < end;
}

} // namespace

bool resolveEuropeWarsawLocalTime(std::uint64_t utc_unix_time_s,
                                  EuropeWarsawLocalTime& output) noexcept {
  output = {};

  const std::uint64_t utc_days = utc_unix_time_s / 86400ULL;
  if (utc_days > static_cast<std::uint64_t>(INT64_MAX)) {
    return false;
  }

  std::int64_t utc_year = 0;
  unsigned utc_month = 0U;
  unsigned utc_day = 0U;
  civilFromDays(static_cast<std::int64_t>(utc_days), utc_year, utc_month, utc_day);
  if (utc_year < 2000 || utc_year > 2199) {
    return false;
  }

  const bool dst = isEuropeWarsawDst(utc_unix_time_s, utc_year);
  const std::int32_t offset = dst ? kCestOffsetSeconds : kCetOffsetSeconds;
  const std::uint64_t local_unix_time_s = utc_unix_time_s + static_cast<std::uint64_t>(offset);
  const std::uint64_t local_days = local_unix_time_s / 86400ULL;
  const std::uint64_t seconds_of_day = local_unix_time_s % 86400ULL;

  std::int64_t local_year = 0;
  unsigned local_month = 0U;
  unsigned local_day = 0U;
  civilFromDays(static_cast<std::int64_t>(local_days), local_year, local_month, local_day);
  if (local_year < 2000 || local_year > 2199) {
    return false;
  }

  output.year = static_cast<std::uint16_t>(local_year);
  output.month = static_cast<std::uint8_t>(local_month);
  output.day = static_cast<std::uint8_t>(local_day);
  output.hour = static_cast<std::uint8_t>(seconds_of_day / 3600ULL);
  output.minute = static_cast<std::uint8_t>((seconds_of_day / 60ULL) % 60ULL);
  output.second = static_cast<std::uint8_t>(seconds_of_day % 60ULL);
  output.utc_offset_seconds = offset;
  output.daylight_saving = dst;
  return true;
}

} // namespace growbox::app::climate_io::runtime
