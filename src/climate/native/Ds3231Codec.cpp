#include "climate/native/Ds3231Codec.h"

#include <cstdint>

namespace growbox::app::climate_io::native {
namespace {

constexpr std::uint8_t kOscillatorStopFlag = 0x80U;

bool decodeBcd(std::uint8_t raw, std::uint8_t mask, std::uint8_t& value) noexcept {
  raw &= mask;
  const std::uint8_t low = raw & 0x0FU;
  const std::uint8_t high = (raw >> 4U) & 0x0FU;
  if (low > 9U || high > 9U) {
    return false;
  }
  value = static_cast<std::uint8_t>(high * 10U + low);
  return true;
}

std::uint8_t encodeBcd(std::uint8_t value) noexcept {
  return static_cast<std::uint8_t>(((value / 10U) << 4U) | (value % 10U));
}

bool leapYear(std::uint16_t year) noexcept {
  return (year % 4U == 0U && year % 100U != 0U) || year % 400U == 0U;
}

std::uint8_t daysInMonth(std::uint16_t year, std::uint8_t month) noexcept {
  constexpr std::uint8_t kDays[] = {31U, 28U, 31U, 30U, 31U, 30U, 31U, 31U, 30U, 31U, 30U, 31U};
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

std::uint8_t weekdaySundayOne(std::int64_t days_since_epoch) noexcept {
  const std::int64_t sunday_zero = (days_since_epoch + 4) % 7;
  const std::int64_t normalized = sunday_zero >= 0 ? sunday_zero : sunday_zero + 7;
  return static_cast<std::uint8_t>(normalized + 1);
}

bool decodeHour(std::uint8_t raw, std::uint8_t& hour) noexcept {
  if ((raw & 0x40U) == 0U) {
    if (!decodeBcd(raw, 0x3FU, hour) || hour > 23U) {
      return false;
    }
    return true;
  }

  std::uint8_t hour12 = 0U;
  if (!decodeBcd(raw, 0x1FU, hour12) || hour12 < 1U || hour12 > 12U) {
    return false;
  }
  const bool pm = (raw & 0x20U) != 0U;
  hour = static_cast<std::uint8_t>((hour12 % 12U) + (pm ? 12U : 0U));
  return true;
}

} // namespace

bool decodeDs3231Time(const std::array<std::uint8_t, 7>& registers, std::uint8_t status_register,
                      Ds3231DecodedTime& output) noexcept {
  output = {};
  if ((status_register & kOscillatorStopFlag) != 0U) {
    return false;
  }

  std::uint8_t second = 0U;
  std::uint8_t minute = 0U;
  std::uint8_t hour = 0U;
  std::uint8_t day = 0U;
  std::uint8_t month = 0U;
  std::uint8_t year2 = 0U;

  if (!decodeBcd(registers[0], 0x7FU, second) || second > 59U ||
      !decodeBcd(registers[1], 0x7FU, minute) || minute > 59U || !decodeHour(registers[2], hour) ||
      !decodeBcd(registers[4], 0x3FU, day) || !decodeBcd(registers[5], 0x1FU, month) ||
      !decodeBcd(registers[6], 0xFFU, year2)) {
    return false;
  }

  const std::uint16_t year =
      static_cast<std::uint16_t>(2000U + year2 + ((registers[5] & 0x80U) ? 100U : 0U));
  if (month < 1U || month > 12U || day < 1U || day > daysInMonth(year, month)) {
    return false;
  }

  const std::int64_t days = daysFromCivil(year, month, day);
  if (days < 0) {
    return false;
  }
  const std::uint64_t seconds = static_cast<std::uint64_t>(days) * 86400U +
                                static_cast<std::uint64_t>(hour) * 3600U +
                                static_cast<std::uint64_t>(minute) * 60U + second;

  output.year = year;
  output.month = month;
  output.day = day;
  output.hour = hour;
  output.minute = minute;
  output.second = second;
  output.unix_time_s = seconds;
  return true;
}

bool encodeDs3231UtcTime(std::uint64_t unix_time_s,
                         std::array<std::uint8_t, 7>& registers) noexcept {
  registers = {};
  const std::uint64_t days_u64 = unix_time_s / 86400ULL;
  if (days_u64 > 1000000ULL) {
    return false;
  }

  const std::int64_t days = static_cast<std::int64_t>(days_u64);
  std::int64_t year64 = 0;
  unsigned month_u = 0U;
  unsigned day_u = 0U;
  civilFromDays(days, year64, month_u, day_u);
  if (year64 < 2000 || year64 > 2199 || month_u < 1U || month_u > 12U || day_u < 1U ||
      day_u > 31U) {
    return false;
  }

  const std::uint64_t seconds_of_day = unix_time_s % 86400ULL;
  const std::uint8_t hour = static_cast<std::uint8_t>(seconds_of_day / 3600ULL);
  const std::uint8_t minute = static_cast<std::uint8_t>((seconds_of_day / 60ULL) % 60ULL);
  const std::uint8_t second = static_cast<std::uint8_t>(seconds_of_day % 60ULL);
  const std::uint16_t year = static_cast<std::uint16_t>(year64);
  const std::uint8_t month = static_cast<std::uint8_t>(month_u);
  const std::uint8_t day = static_cast<std::uint8_t>(day_u);

  registers[0] = encodeBcd(second);
  registers[1] = encodeBcd(minute);
  registers[2] = encodeBcd(hour);
  registers[3] = encodeBcd(weekdaySundayOne(days));
  registers[4] = encodeBcd(day);
  registers[5] = encodeBcd(month);
  if (year >= 2100U) {
    registers[5] = static_cast<std::uint8_t>(registers[5] | 0x80U);
  }
  registers[6] = encodeBcd(static_cast<std::uint8_t>(year % 100U));
  return true;
}

} // namespace growbox::app::climate_io::native
