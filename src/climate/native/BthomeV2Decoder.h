#pragma once

#include <cstddef>
#include <cstdint>

namespace growbox::app::climate_io::native {

struct BthomeV2Measurement {
  float temperature_c = 0.0F;
  float relative_humidity_pct = 0.0F;
  std::uint8_t battery_pct = 0U;
  bool has_temperature = false;
  bool has_humidity = false;
  bool has_battery = false;
};

enum class BthomeV2DecodeStatus : std::uint8_t {
  Ok = 0U,
  TooShort,
  UnsupportedVersion,
  Encrypted,
  TruncatedObject,
  UnsupportedObject,
  MissingClimateMeasurement,
};

BthomeV2DecodeStatus decodeBthomeV2(const std::uint8_t* data, std::size_t size,
                                    BthomeV2Measurement& output) noexcept;

bool findBthomeV2ServiceData(const std::uint8_t* advertisement, std::size_t size,
                             const std::uint8_t*& payload,
                             std::size_t& payload_size) noexcept;

} // namespace growbox::app::climate_io::native
