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

} // namespace growbox::app::climate_io::native
