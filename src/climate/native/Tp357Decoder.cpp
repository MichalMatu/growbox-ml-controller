#include "climate/native/Tp357Decoder.h"

namespace growbox::app::climate_io::native {
namespace {

constexpr std::uint8_t kManufacturerDataType = 0xFFU;

bool parseCandidate(const std::uint8_t* data, std::size_t size, std::size_t offset,
                    Tp357Measurement& output) noexcept {
  if (data == nullptr || offset + 5U > size) {
    return false;
  }

  const std::uint8_t* payload = data + offset;
  const auto raw_temperature = static_cast<std::int16_t>(
      static_cast<std::uint16_t>(payload[1]) | (static_cast<std::uint16_t>(payload[2]) << 8U));
  const float temperature_c = static_cast<float>(raw_temperature) * 0.1F;
  const std::uint8_t humidity_pct = payload[3];
  const std::uint8_t battery_pct = payload[4];
  if (temperature_c < -50.0F || temperature_c > 100.0F || humidity_pct > 100U ||
      battery_pct > 100U) {
    return false;
  }

  output.temperature_c = temperature_c;
  output.relative_humidity_pct = static_cast<float>(humidity_pct);
  output.battery_pct = battery_pct;
  return true;
}

} // namespace

Tp357DecodeStatus decodeTp357Advertisement(const std::uint8_t* data, std::size_t size,
                                           Tp357Measurement& output) noexcept {
  output = {};
  if (data == nullptr || size == 0U) {
    return Tp357DecodeStatus::NotFound;
  }

  bool saw_manufacturer_data = false;
  bool saw_complete_candidate = false;
  std::size_t offset = 0U;
  while (offset < size) {
    const std::uint8_t field_length = data[offset];
    if (field_length == 0U) {
      break;
    }
    const std::size_t next_offset = offset + 1U + static_cast<std::size_t>(field_length);
    if (next_offset > size) {
      return Tp357DecodeStatus::MalformedAdvertisement;
    }
    if (field_length >= 1U && data[offset + 1U] == kManufacturerDataType) {
      saw_manufacturer_data = true;
      const std::uint8_t* manufacturer_data = data + offset + 2U;
      const std::size_t manufacturer_size = static_cast<std::size_t>(field_length - 1U);
      saw_complete_candidate = saw_complete_candidate || manufacturer_size >= 5U;

      Tp357Measurement decoded{};
      if (parseCandidate(manufacturer_data, manufacturer_size, 2U, decoded) ||
          parseCandidate(manufacturer_data, manufacturer_size, 0U, decoded)) {
        output = decoded;
        return Tp357DecodeStatus::Ok;
      }
    }
    offset = next_offset;
  }

  if (!saw_manufacturer_data) {
    return Tp357DecodeStatus::NotFound;
  }
  return saw_complete_candidate ? Tp357DecodeStatus::OutOfRange
                                : Tp357DecodeStatus::MalformedAdvertisement;
}

} // namespace growbox::app::climate_io::native
