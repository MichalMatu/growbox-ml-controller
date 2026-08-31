#pragma once

#include <cstddef>
#include <cstdint>

namespace growbox::app::climate_io::native {

struct Tp357Measurement {
  float temperature_c = 0.0F;
  float relative_humidity_pct = 0.0F;
  std::uint8_t battery_pct = 0U;
};

enum class Tp357DecodeStatus : std::uint8_t {
  Ok = 0,
  NotFound,
  MalformedAdvertisement,
  OutOfRange,
};

Tp357DecodeStatus decodeTp357Advertisement(const std::uint8_t* data, std::size_t size,
                                           Tp357Measurement& output) noexcept;

} // namespace growbox::app::climate_io::native
