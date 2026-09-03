#include "ClimateRuntimeController.h"
#include "climate/native/BleClimateState.h"

#include <array>
#include <cassert>
#include <cstdint>

using growbox::app::climate_io::native::BleClimateIngestResult;
using growbox::app::climate_io::native::BleClimateReading;
using growbox::app::climate_io::native::BleClimateState;
using growbox::climate::ClimateControllerInput;
using growbox::climate::ClimatePolicyMode;
using growbox::climate::ClimateRuntimeConfig;
using growbox::climate::ClimateRuntimeController;
using growbox::climate::ClimateRuntimeDecision;

namespace {

constexpr std::array<std::uint8_t, 6> kTp357NimbleAddress{
    {0x20U, 0x76U, 0x0FU, 0x8DU, 0x5FU, 0xF7U}};

constexpr std::array<std::uint8_t, 27> kTp357Advertisement{{
    0x02U, 0x01U, 0x06U, 0x0EU, 0x08U, 'T',   'P',   '3',   '5',   '7',   'S',   ' ',   '(',   '7',
    '6',   '2',   '0',   ')',   0x08U, 0xFFU, 0xC2U, 0xECU, 0x00U, 0x4AU, 0x22U, 0x0BU, 0x01U,
}};

void assertAllOff(const growbox::climate::ClimatePolicyRequest& request) {
  assert(request.heater == 0.0F);
  assert(request.cooler == 0.0F);
  assert(request.exhaust_fan == 0.0F);
  assert(request.humidifier == 0.0F);
  assert(request.dehumidifier == 0.0F);
  assert(request.co2_doser == 0.0F);
}

void testMalformedPacketsCannotKeepStaleInsideClimateUsable() {
  BleClimateState state;
  assert(state.configure("F7:5F:8D:0F:76:20", "A4:C1:38:4F:24:CD"));

  assert(state.ingestNimbleAdvertisement(kTp357NimbleAddress.data(), kTp357Advertisement.data(),
                                         kTp357Advertisement.size(),
                                         1'000U) == BleClimateIngestResult::MeasurementAccepted);

  constexpr std::array<std::uint8_t, 3> malformed{{0x08U, 0xFFU, 0xC2U}};
  assert(state.ingestNimbleAdvertisement(kTp357NimbleAddress.data(), malformed.data(),
                                         malformed.size(),
                                         31'500U) == BleClimateIngestResult::PacketRejected);

  BleClimateReading reading{};
  assert(state.sampleTp357(32'001U, reading));
  assert(state.tp357LastPacketSeenMs() == 31'500U);
  assert(state.tp357LastValidMeasurementMs() == 1'000U);
  assert(state.tp357PacketCount() == 2U);
  assert(state.tp357AcceptedCount() == 1U);
  assert(state.tp357RejectedCount() == 1U);
  assert(reading.age_ms == 31'001U);

  ClimateControllerInput input{};
  input.state.measurements.air_temperature_c = {reading.temperature_c, true, reading.age_ms};
  input.state.measurements.relative_humidity_pct =
      {reading.relative_humidity_pct, true, reading.age_ms};
  input.targets.air_temperature_c = 30.0F;
  input.targets.relative_humidity_pct = reading.relative_humidity_pct;
  input.capabilities.heater = true;

  ClimateRuntimeConfig config{};
  config.mode = ClimatePolicyMode::Rule;
  config.sensor_timeout_ms = 30'000U;
  ClimateRuntimeController runtime(nullptr, config);
  ClimateRuntimeDecision decision{};
  runtime.step(input, 32'001U, decision);

  assertAllOff(decision.rule.raw);
  assertAllOff(decision.rule.safe);
  assertAllOff(decision.applied);
}

} // namespace

int main() {
  testMalformedPacketsCannotKeepStaleInsideClimateUsable();
  return 0;
}
