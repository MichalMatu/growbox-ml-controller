#include "climate/native/Tp357Decoder.h"

#include <array>
#include <cassert>
#include <cmath>
#include <cstdint>

using growbox::app::climate_io::native::decodeTp357Advertisement;
using growbox::app::climate_io::native::Tp357DecodeStatus;
using growbox::app::climate_io::native::Tp357Measurement;

namespace {

bool closeEnough(float left, float right) {
  return std::fabs(left - right) < 0.001F;
}

void testRealHardwareFrameOffsetZeroFallback() {
  constexpr std::array<std::uint8_t, 27> advertisement{{
      0x02U, 0x01U, 0x06U, 0x0EU, 0x08U, 'T',   'P',   '3',   '5',
      '7',   'S',   ' ',   '(',   '7',   '6',   '2',   '0',   ')',
      0x08U, 0xFFU, 0xC2U, 0xECU, 0x00U, 0x4AU, 0x22U, 0x0BU, 0x01U,
  }};
  Tp357Measurement decoded{};
  assert(decodeTp357Advertisement(advertisement.data(), advertisement.size(), decoded) ==
         Tp357DecodeStatus::Ok);
  assert(closeEnough(decoded.temperature_c, 23.6F));
  assert(closeEnough(decoded.relative_humidity_pct, 74.0F));
  assert(decoded.battery_pct == 34U);
}

void testRealHardwareTemperatureChanges() {
  constexpr std::array<std::uint8_t, 27> advertisement{{
      0x02U, 0x01U, 0x06U, 0x0EU, 0x08U, 'T',   'P',   '3',   '5',
      '7',   'S',   ' ',   '(',   '7',   '6',   '2',   '0',   ')',
      0x08U, 0xFFU, 0xC2U, 0xEBU, 0x00U, 0x4AU, 0x22U, 0x0BU, 0x01U,
  }};
  Tp357Measurement decoded{};
  assert(decodeTp357Advertisement(advertisement.data(), advertisement.size(), decoded) ==
         Tp357DecodeStatus::Ok);
  assert(closeEnough(decoded.temperature_c, 23.5F));
}

void testLiteGraphOffsetTwoFixture() {
  constexpr std::array<std::uint8_t, 20> advertisement{{
      0x02U, 0x01U, 0x06U, 0x06U, 0x09U, 'T',   'P',   '3',   '5',   '7',
      0x09U, 0xFFU, 0x34U, 0x12U, 0x10U, 0xE8U, 0x00U, 0x32U, 0x64U, 0x00U,
  }};
  Tp357Measurement decoded{};
  assert(decodeTp357Advertisement(advertisement.data(), advertisement.size(), decoded) ==
         Tp357DecodeStatus::Ok);
  assert(closeEnough(decoded.temperature_c, 23.2F));
  assert(closeEnough(decoded.relative_humidity_pct, 50.0F));
  assert(decoded.battery_pct == 100U);
}

void testMalformedAndOutOfRangeAreRejected() {
  constexpr std::array<std::uint8_t, 4> truncated{{0x03U, 0xFFU, 0x01U, 0x02U}};
  Tp357Measurement decoded{};
  assert(decodeTp357Advertisement(truncated.data(), truncated.size(), decoded) ==
         Tp357DecodeStatus::MalformedAdvertisement);

  constexpr std::array<std::uint8_t, 7> invalid{{
      0x06U,
      0xFFU,
      0x00U,
      0xFFU,
      0x7FU,
      0x65U,
      0x65U,
  }};
  assert(decodeTp357Advertisement(invalid.data(), invalid.size(), decoded) ==
         Tp357DecodeStatus::OutOfRange);
}

} // namespace

int main() {
  testRealHardwareFrameOffsetZeroFallback();
  testRealHardwareTemperatureChanges();
  testLiteGraphOffsetTwoFixture();
  testMalformedAndOutOfRangeAreRejected();
  return 0;
}
