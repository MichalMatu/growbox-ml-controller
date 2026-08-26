#include "ClimateContract.h"
#include "ClimateFeatureEncoder.h"
#include "ClimateMath.h"
#include "ClimateTrendEstimator.h"
#include <cmath>
#include <cstring>
#include <iostream>
namespace {
int failures = 0;
void check(bool c, const char* m) {
  if (!c) {
    ++failures;
    std::cerr << "FAIL: " << m << '\n';
  }
}
bool near(float a, float b, float t) {
  return std::abs(a - b) <= t;
}
float feature(const growbox::climate::ClimateFeatureVector& v,
              growbox::climate::contract::FeatureIndex i) {
  return v.values[growbox::climate::contract::index(i)];
}
void contractTest() {
  namespace c = growbox::climate::contract;
  check(c::kSchemaVersion == 6U, "schema version");
  check(c::kFeatureCount == 38U, "feature count");
  check(c::kOutputCount == 6U, "output count");
  const char* expected[] = {"heater",     "cooler",       "exhaust_fan",
                            "humidifier", "dehumidifier", "co2_doser"};
  for (std::size_t i = 0; i < c::kOutputCount; ++i)
    check(std::strcmp(c::kOutputNames[i], expected[i]) == 0, "output order");
}
void encoderTest() {
  using namespace growbox::climate;
  namespace c = growbox::climate::contract;
  ClimateControllerInput in{};
  in.state.measurements.air_temperature_c = {24.0F, true, 0U};
  in.state.measurements.relative_humidity_pct = {60.0F, true, 0U};
  in.state.measurements.co2_ppm = {999.0F, false, 0U};
  in.state.measurements.outside_temperature_c = {18.0F, true, 40'000U};
  in.state.measurements.outside_humidity_pct = {45.0F, true, 0U};
  in.humidity_control_mode = HumidityControlMode::Vpd;
  in.schedule.light_level = 0.75F;
  in.previous.heater = 2.0F;
  in.capabilities.heater = true;
  in.state.trends.temperature = {1.0F, true};
  in.state.trends.humidity = {-2.0F, true};
  in.state.trends.co2 = {100.0F, true};
  ClimateEncoderReport r{};
  const auto v = ClimateFeatureEncoder::encode(in, &r);
  check(near(feature(v, c::FeatureIndex::AirTemperatureC), 0.55F, 0.0001F),
        "temperature normalization");
  check(feature(v, c::FeatureIndex::Co2Valid) == 0.0F, "CO2 valid");
  check(feature(v, c::FeatureIndex::Co2Fresh) == 1.0F, "freshness independent");
  check(r.substituted(c::FeatureIndex::Co2Ppm), "invalid CO2 fallback");
  check(feature(v, c::FeatureIndex::OutsideTemperatureFresh) == 0.0F, "stale outside");
  check(r.substituted(c::FeatureIndex::OutsideTemperatureC), "stale fallback");
  check(feature(v, c::FeatureIndex::HumidityControlMode) == 1.0F, "VPD mode");
  check(near(feature(v, c::FeatureIndex::LightLevel), 0.75F, 0.0001F), "light context");
  check(feature(v, c::FeatureIndex::PreviousHeater) == 1.0F, "command clamp");
  check(r.clamped(c::FeatureIndex::PreviousHeater), "clamp diagnostic");
}
void trendTest() {
  using namespace growbox::climate;
  ClimateTrendEstimator e{};
  ClimateMeasurements m{};
  ClimateTrends tr{};
  for (std::uint64_t ms = 0U; ms <= 60'000U; ms += 5'000U) {
    const float min = static_cast<float>(ms) / 60'000.0F;
    m.air_temperature_c = {20.0F + min, true, 0U};
    m.relative_humidity_pct = {60.0F - 2.0F * min, true, 0U};
    m.co2_ppm = {500.0F + 100.0F * min, true, 0U};
    tr = e.update(m, ms);
    if (ms < 10'000U)
      check(!tr.temperature.available, "startup trend");
  }
  check(tr.temperature.available && near(tr.temperature.rate_per_min, 1.0F, 0.01F),
        "temperature trend");
  check(tr.humidity.available && near(tr.humidity.rate_per_min, -2.0F, 0.01F), "humidity trend");
  check(tr.co2.available && near(tr.co2.rate_per_min, 100.0F, 0.05F), "CO2 trend");
  m.co2_ppm.age_ms = kDefaultSensorTimeoutMs + 1U;
  tr = e.update(m, 65'000U);
  check(!tr.co2.available, "stale CO2 trend");
  tr = e.update(m, 1'000U);
  check(!tr.temperature.available, "rollback resets trend");
  ClimateTrendEstimator fast{};
  m.co2_ppm = {500.0F, true, 0U};
  for (std::uint64_t ms = 0U; ms <= 60'000U; ms += 1'000U) {
    const float min = static_cast<float>(ms) / 60'000.0F;
    m.air_temperature_c = {20.0F + min, true, 0U};
    m.relative_humidity_pct = {60.0F, true, 0U};
    tr = fast.update(m, ms);
  }
  check(tr.temperature.available && near(tr.temperature.rate_per_min, 1.0F, 0.02F), "1 Hz trend");
}
} // namespace
int main() {
  contractTest();
  check(near(growbox::climate::airVpdKpa(25.0F, 60.0F), 1.264F, 0.015F), "VPD math");
  encoderTest();
  trendTest();
  if (failures) {
    std::cerr << failures << " climate v6 checks failed\n";
    return 1;
  }
  std::cout << "climate v6 checks passed\n";
  return 0;
}
