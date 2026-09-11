#include "climate/native/BleClimateState.h"

#include <array>
#include <cassert>
#include <cmath>
#include <cstdint>

using growbox::app::climate_io::native::BleClimateIngestResult;
using growbox::app::climate_io::native::BleClimateReading;
using growbox::app::climate_io::native::BleClimateState;

namespace {

bool closeEnough(float left, float right) {
  return std::fabs(left - right) < 0.001F;
}

constexpr std::array<std::uint8_t, 6> kTp357NimbleAddress{
    {0x20U, 0x76U, 0x0FU, 0x8DU, 0x5FU, 0xF7U}};
constexpr std::array<std::uint8_t, 6> kXiaomiNimbleAddress{
    {0xCDU, 0x24U, 0x4FU, 0x38U, 0xC1U, 0xA4U}};
constexpr std::array<std::uint8_t, 6> kWrongAddress{{0x01U, 0x02U, 0x03U, 0x04U, 0x05U, 0x06U}};

constexpr std::array<std::uint8_t, 27> kTp357Advertisement{{
    0x02U, 0x01U, 0x06U, 0x0EU, 0x08U, 'T',   'P',   '3',   '5',   '7',   'S',   ' ',   '(',   '7',
    '6',   '2',   '0',   ')',   0x08U, 0xFFU, 0xC2U, 0xECU, 0x00U, 0x4AU, 0x22U, 0x0BU, 0x01U,
}};

constexpr std::array<std::uint8_t, 14> kXiaomiAdvertisement{{
    0x02U,
    0x01U,
    0x06U,
    0x0AU,
    0x16U,
    0xD2U,
    0xFCU,
    0x40U,
    0x02U,
    0xC4U,
    0x09U,
    0x03U,
    0xAEU,
    0x15U,
}};

void testExactIdentityRoutesBothSensors() {
  BleClimateState state;
  assert(state.configure("F7:5F:8D:0F:76:20", "A4:C1:38:4F:24:CD"));

  assert(state.ingestNimbleAdvertisement(kWrongAddress.data(), kTp357Advertisement.data(),
                                         kTp357Advertisement.size(),
                                         500U) == BleClimateIngestResult::Ignored);
  assert(state.tp357LastPacketSeenMs() == 0U);

  assert(state.ingestNimbleAdvertisement(kTp357NimbleAddress.data(), kTp357Advertisement.data(),
                                         kTp357Advertisement.size(),
                                         1000U) == BleClimateIngestResult::MeasurementAccepted);
  BleClimateReading tp357{};
  assert(state.sampleTp357(1250U, tp357));
  assert(closeEnough(tp357.temperature_c, 23.6F));
  assert(closeEnough(tp357.relative_humidity_pct, 74.0F));
  assert(tp357.has_battery);
  assert(tp357.battery_pct == 34U);
  assert(tp357.packet_seen_ms == 1000U);
  assert(tp357.valid_measurement_ms == 1000U);
  assert(tp357.age_ms == 250U);
  assert(state.tp357PacketCount() == 1U);
  assert(state.tp357AcceptedCount() == 1U);
  assert(state.tp357RejectedCount() == 0U);

  assert(state.ingestNimbleAdvertisement(kXiaomiNimbleAddress.data(), kXiaomiAdvertisement.data(),
                                         kXiaomiAdvertisement.size(),
                                         3000U) == BleClimateIngestResult::MeasurementAccepted);
  BleClimateReading xiaomi{};
  assert(state.sampleXiaomi(3400U, xiaomi));
  assert(closeEnough(xiaomi.temperature_c, 25.0F));
  assert(closeEnough(xiaomi.relative_humidity_pct, 55.5F));
  assert(xiaomi.packet_seen_ms == 3000U);
  assert(xiaomi.valid_measurement_ms == 3000U);
  assert(xiaomi.age_ms == 400U);
  assert(state.xiaomiPacketCount() == 1U);
  assert(state.xiaomiAcceptedCount() == 1U);
  assert(state.xiaomiRejectedCount() == 0U);
}

void testRejectedPacketsDoNotRefreshMeasurementFreshness() {
  BleClimateState state;
  assert(state.configure("F7:5F:8D:0F:76:20", "A4:C1:38:4F:24:CD"));
  assert(state.ingestNimbleAdvertisement(kTp357NimbleAddress.data(), kTp357Advertisement.data(),
                                         kTp357Advertisement.size(),
                                         1000U) == BleClimateIngestResult::MeasurementAccepted);

  constexpr std::array<std::uint8_t, 3> malformed_tp357{{0x08U, 0xFFU, 0xC2U}};
  assert(state.ingestNimbleAdvertisement(kTp357NimbleAddress.data(), malformed_tp357.data(),
                                         malformed_tp357.size(),
                                         2000U) == BleClimateIngestResult::PacketRejected);
  assert(state.tp357LastPacketSeenMs() == 2000U);
  assert(state.tp357LastValidMeasurementMs() == 1000U);
  assert(state.tp357PacketCount() == 2U);
  assert(state.tp357AcceptedCount() == 1U);
  assert(state.tp357RejectedCount() == 1U);
  BleClimateReading tp357{};
  assert(state.sampleTp357(2500U, tp357));
  assert(tp357.age_ms == 1500U);

  assert(state.ingestNimbleAdvertisement(kXiaomiNimbleAddress.data(), kXiaomiAdvertisement.data(),
                                         kXiaomiAdvertisement.size(),
                                         3000U) == BleClimateIngestResult::MeasurementAccepted);
  constexpr std::array<std::uint8_t, 5> encrypted_xiaomi{{0x04U, 0x16U, 0xD2U, 0xFCU, 0x41U}};
  assert(state.ingestNimbleAdvertisement(kXiaomiNimbleAddress.data(), encrypted_xiaomi.data(),
                                         encrypted_xiaomi.size(),
                                         4000U) == BleClimateIngestResult::PacketRejected);
  assert(state.xiaomiLastPacketSeenMs() == 4000U);
  assert(state.xiaomiLastValidMeasurementMs() == 3000U);
  assert(state.xiaomiPacketCount() == 2U);
  assert(state.xiaomiAcceptedCount() == 1U);
  assert(state.xiaomiRejectedCount() == 1U);
}

void testInvalidConfigurationIsRejected() {
  BleClimateState state;
  assert(!state.configure("F7:5F:8D:0F:76:20", "F7:5F:8D:0F:76:20"));
  assert(!state.configured());
  assert(!state.configure("invalid", "A4:C1:38:4F:24:CD"));
}

} // namespace

int main() {
  testExactIdentityRoutesBothSensors();
  testRejectedPacketsDoNotRefreshMeasurementFreshness();
  testInvalidConfigurationIsRejected();
  return 0;
}
