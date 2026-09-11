#pragma once

#include <cstdint>

namespace growbox::app::climate_io::runtime {

struct EuropeWarsawLocalTime {
  std::uint16_t year{0U};
  std::uint8_t month{0U};
  std::uint8_t day{0U};
  std::uint8_t hour{0U};
  std::uint8_t minute{0U};
  std::uint8_t second{0U};
  std::int32_t utc_offset_seconds{0};
  bool daylight_saving{false};
};

bool resolveEuropeWarsawLocalTime(std::uint64_t utc_unix_time_s,
                                  EuropeWarsawLocalTime& output) noexcept;

} // namespace growbox::app::climate_io::runtime
