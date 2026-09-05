#include "climate/native/BthomeV2Decoder.h"
#include "climate/native/Ds3231Codec.h"

#include <array>
#include <cassert>
#include <cmath>
#include <cstdint>

using growbox::app::climate_io::native::BthomeV2DecodeStatus;
using growbox::app::climate_io::native::BthomeV2Measurement;
using growbox::app::climate_io::native::decodeBthomeV2;
using growbox::app::climate_io::native::decodeDs3231Time;
using growbox::app::climate_io::native::Ds3231DecodedTime;
using growbox::app::climate_io::native::encodeDs3231UtcTime;
using growbox::app::climate_io::native::findBthomeV2ServiceData;

namespace {

bool closeEnough(float left, float right) {
  return std::fabs(left - right) < 0.001F;
}

void testLiteGraphFixture() {
  constexpr std::array<std::uint8_t, 7> payload{{0x40U, 0x02U, 0xC4U, 0x09U, 0x03U, 0xAEU, 0x15U}};
  BthomeV2Measurement decoded{};
  assert(decodeBthomeV2(payload.data(), payload.size(), decoded) == BthomeV2DecodeStatus::Ok);
  assert(decoded.has_temperature);
  assert(decoded.has_humidity);
  assert(closeEnough(decoded.temperature_c, 25.0F));
  assert(closeEnough(decoded.relative_humidity_pct, 55.5F));
}

void testAdvertisementExtraction() {
  constexpr std::array<std::uint8_t, 11> advertisement{{
      0x02U,
      0x01U,
      0x06U,
      0x07U,
      0x16U,
      0xD2U,
      0xFCU,
      0x40U,
      0x02U,
      0xC4U,
      0x09U,
  }};
  const std::uint8_t* payload = nullptr;
  std::size_t payload_size = 0U;
  assert(
      findBthomeV2ServiceData(advertisement.data(), advertisement.size(), payload, payload_size));
  assert(payload_size == 4U);
  BthomeV2Measurement decoded{};
  assert(decodeBthomeV2(payload, payload_size, decoded) ==
         BthomeV2DecodeStatus::MissingClimateMeasurement);
}

void testMalformedAndEncryptedDoNotDecode() {
  constexpr std::array<std::uint8_t, 2> truncated{{0x40U, 0x02U}};
  BthomeV2Measurement decoded{};
  assert(decodeBthomeV2(truncated.data(), truncated.size(), decoded) ==
         BthomeV2DecodeStatus::TruncatedObject);
  constexpr std::array<std::uint8_t, 1> encrypted{{0x41U}};
  assert(decodeBthomeV2(encrypted.data(), encrypted.size(), decoded) ==
         BthomeV2DecodeStatus::Encrypted);
}

void testDs3231TrustedTime() {
  constexpr std::array<std::uint8_t, 7> registers{{
      0x00U,
      0x00U,
      0x00U,
      0x07U,
      0x01U,
      0x01U,
      0x00U,
  }};
  Ds3231DecodedTime decoded{};
  assert(decodeDs3231Time(registers, 0x00U, decoded));
  assert(decoded.year == 2000U);
  assert(decoded.month == 1U);
  assert(decoded.day == 1U);
  assert(decoded.unix_time_s == 946684800ULL);
}

void testDs3231UtcEncoderRoundTrips() {
  constexpr std::array<std::uint64_t, 5> epochs{{
      946684800ULL,  // 2000-01-01 00:00:00 UTC
      1774746000ULL, // 2026-03-29 01:00:00 UTC, Warsaw DST boundary
      1788589800ULL, // 2026-09-05 06:30:00 UTC
      1792890000ULL, // 2026-10-25 01:00:00 UTC, Warsaw DST boundary
      4102444799ULL, // 2099-12-31 23:59:59 UTC
  }};
  for (const std::uint64_t epoch : epochs) {
    std::array<std::uint8_t, 7> encoded{};
    assert(encodeDs3231UtcTime(epoch, encoded));
    Ds3231DecodedTime decoded{};
    assert(decodeDs3231Time(encoded, 0x00U, decoded));
    assert(decoded.unix_time_s == epoch);
    assert((encoded[2] & 0x40U) == 0U); // always encode DS3231 in 24-hour mode
  }
}

void testDs3231UtcEncoderRejectsUnsupportedCentury() {
  std::array<std::uint8_t, 7> encoded{};
  assert(!encodeDs3231UtcTime(7258118400ULL, encoded)); // 2200-01-01 00:00:00 UTC
}

void testDs3231OsfAndInvalidBcd() {
  constexpr std::array<std::uint8_t, 7> valid{{
      0x00U,
      0x00U,
      0x00U,
      0x07U,
      0x01U,
      0x01U,
      0x00U,
  }};
  Ds3231DecodedTime decoded{};
  assert(!decodeDs3231Time(valid, 0x80U, decoded));
  auto invalid = valid;
  invalid[1] = 0x7AU;
  assert(!decodeDs3231Time(invalid, 0x00U, decoded));
}

} // namespace

int main() {
  testLiteGraphFixture();
  testAdvertisementExtraction();
  testMalformedAndEncryptedDoNotDecode();
  testDs3231TrustedTime();
  testDs3231UtcEncoderRoundTrips();
  testDs3231UtcEncoderRejectsUnsupportedCentury();
  testDs3231OsfAndInvalidBcd();
  return 0;
}
