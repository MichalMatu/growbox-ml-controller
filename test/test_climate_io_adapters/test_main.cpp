#include "climate/ClimateIoAdapters.h"

#include <array>
#include <cassert>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <vector>

using namespace growbox::app::climate_io;
using namespace growbox::climate;

namespace {

bool near(float left, float right, float tolerance = 1.0e-6F) {
  return std::fabs(left - right) <= tolerance;
}

class FakeSnapshotProvider final : public ClimateSnapshotProvider {
public:
  ClimateInputSnapshot value{};
  bool available = true;
  std::size_t calls = 0U;
  std::uint64_t last_monotonic_ms = 0U;

  bool snapshot(std::uint64_t monotonic_ms, ClimateInputSnapshot& output) noexcept override {
    ++calls;
    last_monotonic_ms = monotonic_ms;
    if (!available) {
      return false;
    }
    output = value;
    return true;
  }
};

struct RoleCall {
  ClimateActuatorRole role = ClimateActuatorRole::Heater;
  float level = 0.0F;
  std::uint64_t monotonic_ms = 0U;
};

class FakeRoleDriver final : public ClimateRoleDriver {
public:
  std::vector<RoleCall> calls{};
  ClimateActuatorRole failing_role = ClimateActuatorRole::Heater;
  bool fail_enabled = false;

  bool apply(ClimateActuatorRole role, float level, std::uint64_t monotonic_ms) noexcept override {
    calls.push_back(RoleCall{role, level, monotonic_ms});
    return !(fail_enabled && role == failing_role);
  }
};

ClimateInputSnapshot populatedSnapshot() {
  ClimateInputSnapshot snapshot{};
  snapshot.measurements.air_temperature_c = {23.5F, true, 111U};
  snapshot.measurements.relative_humidity_pct = {61.0F, true, 222U};
  snapshot.measurements.co2_ppm = {880.0F, true, 333U};
  snapshot.measurements.outside_temperature_c = {12.0F, true, 444U};
  snapshot.measurements.outside_humidity_pct = {52.0F, true, 555U};
  snapshot.humidity_control_mode = HumidityControlMode::Vpd;
  snapshot.targets.air_temperature_c = 24.0F;
  snapshot.targets.relative_humidity_pct = 60.0F;
  snapshot.targets.air_vpd_kpa = 1.15F;
  snapshot.targets.co2_enabled = true;
  snapshot.targets.co2_ppm = 950.0F;
  snapshot.schedule.light_level = 0.75F;
  snapshot.capabilities.heater = true;
  snapshot.capabilities.cooler = false;
  snapshot.capabilities.exhaust_fan = true;
  snapshot.capabilities.humidifier = true;
  snapshot.capabilities.dehumidifier = false;
  snapshot.capabilities.co2_doser = true;
  snapshot.sensor_timeout_ms = 45'000U;
  return snapshot;
}

void testInputAdapterMapsRuntimeObservableSnapshot() {
  FakeSnapshotProvider provider{};
  provider.value = populatedSnapshot();
  ClimateInputAdapter adapter(provider);
  ClimateControllerInput input{};
  input.previous.heater = 1.0F;
  input.estimated_effective.heater = 1.0F;

  assert(adapter.sample(123'456U, input));
  assert(provider.calls == 1U);
  assert(provider.last_monotonic_ms == 123'456U);
  assert(near(input.state.measurements.air_temperature_c.value, 23.5F));
  assert(input.state.measurements.air_temperature_c.valid);
  assert(input.state.measurements.air_temperature_c.age_ms == 111U);
  assert(near(input.state.measurements.relative_humidity_pct.value, 61.0F));
  assert(near(input.state.measurements.co2_ppm.value, 880.0F));
  assert(near(input.state.measurements.outside_temperature_c.value, 12.0F));
  assert(near(input.state.measurements.outside_humidity_pct.value, 52.0F));
  assert(input.humidity_control_mode == HumidityControlMode::Vpd);
  assert(near(input.targets.air_temperature_c, 24.0F));
  assert(near(input.targets.air_vpd_kpa, 1.15F));
  assert(input.targets.co2_enabled);
  assert(near(input.targets.co2_ppm, 950.0F));
  assert(near(input.schedule.light_level, 0.75F));
  assert(input.capabilities.heater);
  assert(!input.capabilities.cooler);
  assert(input.capabilities.exhaust_fan);
  assert(input.capabilities.humidifier);
  assert(!input.capabilities.dehumidifier);
  assert(input.capabilities.co2_doser);
  assert(input.sensor_timeout_ms == 45'000U);
  assert(near(input.previous.heater, 0.0F));
  assert(near(input.estimated_effective.heater, 0.0F));
}

void testInputAdapterClearsStaleStateOnProviderFailure() {
  FakeSnapshotProvider provider{};
  provider.available = false;
  ClimateInputAdapter adapter(provider);
  ClimateControllerInput input{};
  input.state.measurements.air_temperature_c = {99.0F, true, 0U};
  input.capabilities.heater = true;

  assert(!adapter.sample(8'000U, input));
  assert(!input.state.measurements.air_temperature_c.valid);
  assert(!input.capabilities.heater);
  assert(input.state.measurements.air_temperature_c.age_ms == kUnknownMeasurementAgeMs);
}

void testActuatorAdapterMapsEverySemanticRoleExactlyOnce() {
  FakeRoleDriver driver{};
  ClimateActuatorAdapter adapter(driver);
  ClimatePolicyRequest request{};
  request.heater = 0.1F;
  request.cooler = 0.2F;
  request.exhaust_fan = 0.3F;
  request.humidifier = 0.4F;
  request.dehumidifier = 0.5F;
  request.co2_doser = 0.6F;

  assert(adapter.apply(request, 77'000U));
  assert(driver.calls.size() == 6U);
  constexpr std::array<ClimateActuatorRole, 6U> expected_roles{
      ClimateActuatorRole::Heater,       ClimateActuatorRole::Cooler,
      ClimateActuatorRole::ExhaustFan,   ClimateActuatorRole::Humidifier,
      ClimateActuatorRole::Dehumidifier, ClimateActuatorRole::Co2Doser,
  };
  constexpr std::array<float, 6U> expected_levels{0.1F, 0.2F, 0.3F, 0.4F, 0.5F, 0.6F};
  for (std::size_t index = 0U; index < expected_roles.size(); ++index) {
    assert(driver.calls[index].role == expected_roles[index]);
    assert(near(driver.calls[index].level, expected_levels[index]));
    assert(driver.calls[index].monotonic_ms == 77'000U);
  }
}

void testActuatorAdapterReportsPartialFailureButStillVisitsAllRoles() {
  FakeRoleDriver driver{};
  driver.fail_enabled = true;
  driver.failing_role = ClimateActuatorRole::ExhaustFan;
  ClimateActuatorAdapter adapter(driver);
  ClimatePolicyRequest request{};
  request.heater = 0.2F;
  request.exhaust_fan = 0.8F;
  request.co2_doser = 0.4F;

  assert(!adapter.apply(request, 91'000U));
  assert(driver.calls.size() == 6U);
  assert(driver.calls[2].role == ClimateActuatorRole::ExhaustFan);
  assert(driver.calls[5].role == ClimateActuatorRole::Co2Doser);
}

} // namespace

int main() {
  testInputAdapterMapsRuntimeObservableSnapshot();
  testInputAdapterClearsStaleStateOnProviderFailure();
  testActuatorAdapterMapsEverySemanticRoleExactlyOnce();
  testActuatorAdapterReportsPartialFailureButStillVisitsAllRoles();
  return 0;
}
