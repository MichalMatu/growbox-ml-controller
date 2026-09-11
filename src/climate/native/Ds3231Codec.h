#pragma once

#include <array>
#include <cstdint>

namespace growbox::app::climate_io::native {

struct Ds3231DecodedTime {
  std::uint16_t year = 0U;
  std::uint8_t month = 0U;
  std::uint8_t day = 0U;
  std::uint8_t hour = 0U;
  std::uint8_t minute = 0U;
  std::uint8_t second = 0U;
  std::uint64_t unix_time_s = 0U;
};

bool decodeDs3231Time(const std::array<std::uint8_t, 7>& registers, std::uint8_t status_register,
                      Ds3231DecodedTime& output) noexcept;

bool encodeDs3231UtcTime(std::uint64_t unix_time_s,
                         std::array<std::uint8_t, 7>& registers) noexcept;

} // namespace growbox::app::climate_io::native
