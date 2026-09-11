#include "climate/native/BthomeV2Decoder.h"

namespace growbox::app::climate_io::native {
namespace {

constexpr std::uint8_t kBthomeVersion = 2U;
constexpr std::uint8_t kEncryptedMask = 0x01U;
constexpr std::uint8_t kPacketIdObject = 0x00U;
constexpr std::uint8_t kBatteryObject = 0x01U;
constexpr std::uint8_t kTemperatureObject = 0x02U;
constexpr std::uint8_t kHumidityObject = 0x03U;
constexpr std::uint8_t kServiceDataUuid16AdType = 0x16U;
constexpr std::uint8_t kBthomeUuidLow = 0xD2U;
constexpr std::uint8_t kBthomeUuidHigh = 0xFCU;

std::uint16_t readLe16(const std::uint8_t* data) noexcept {
  return static_cast<std::uint16_t>(data[0]) |
         static_cast<std::uint16_t>(static_cast<std::uint16_t>(data[1]) << 8U);
}

} // namespace

BthomeV2DecodeStatus decodeBthomeV2(const std::uint8_t* data, std::size_t size,
                                    BthomeV2Measurement& output) noexcept {
  output = {};
  if (data == nullptr || size < 1U) {
    return BthomeV2DecodeStatus::TooShort;
  }

  const std::uint8_t device_info = data[0];
  if ((device_info >> 5U) != kBthomeVersion) {
    return BthomeV2DecodeStatus::UnsupportedVersion;
  }
  if ((device_info & kEncryptedMask) != 0U) {
    return BthomeV2DecodeStatus::Encrypted;
  }

  std::size_t offset = 1U;
  while (offset < size) {
    const std::uint8_t object_id = data[offset++];
    switch (object_id) {
    case kPacketIdObject:
      if (size - offset < 1U) {
        return BthomeV2DecodeStatus::TruncatedObject;
      }
      ++offset;
      break;
    case kBatteryObject:
      if (size - offset < 1U) {
        return BthomeV2DecodeStatus::TruncatedObject;
      }
      output.battery_pct = data[offset++];
      output.has_battery = true;
      break;
    case kTemperatureObject: {
      if (size - offset < 2U) {
        return BthomeV2DecodeStatus::TruncatedObject;
      }
      const auto raw = static_cast<std::int16_t>(readLe16(data + offset));
      offset += 2U;
      output.temperature_c = static_cast<float>(raw) * 0.01F;
      output.has_temperature = true;
      break;
    }
    case kHumidityObject:
      if (size - offset < 2U) {
        return BthomeV2DecodeStatus::TruncatedObject;
      }
      output.relative_humidity_pct = static_cast<float>(readLe16(data + offset)) * 0.01F;
      offset += 2U;
      output.has_humidity = true;
      break;
    default:
      return BthomeV2DecodeStatus::UnsupportedObject;
    }
  }

  if (!output.has_temperature || !output.has_humidity) {
    return BthomeV2DecodeStatus::MissingClimateMeasurement;
  }
  if (output.relative_humidity_pct < 0.0F || output.relative_humidity_pct > 100.0F) {
    return BthomeV2DecodeStatus::MissingClimateMeasurement;
  }
  return BthomeV2DecodeStatus::Ok;
}

bool findBthomeV2ServiceData(const std::uint8_t* advertisement, std::size_t size,
                             const std::uint8_t*& payload, std::size_t& payload_size) noexcept {
  payload = nullptr;
  payload_size = 0U;
  if (advertisement == nullptr) {
    return false;
  }

  std::size_t offset = 0U;
  while (offset < size) {
    const std::uint8_t field_length = advertisement[offset++];
    if (field_length == 0U) {
      break;
    }
    if (field_length > size - offset) {
      return false;
    }
    const std::uint8_t field_type = advertisement[offset];
    if (field_type == kServiceDataUuid16AdType && field_length >= 4U &&
        advertisement[offset + 1U] == kBthomeUuidLow &&
        advertisement[offset + 2U] == kBthomeUuidHigh) {
      payload = advertisement + offset + 3U;
      payload_size = static_cast<std::size_t>(field_length) - 3U;
      return true;
    }
    offset += field_length;
  }
  return false;
}

} // namespace growbox::app::climate_io::native
