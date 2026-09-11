#include "climate/ClimateDiagnostics.h"

#include <cassert>
#include <cmath>
#include <cstdint>

using namespace growbox::app::climate_io;
using namespace growbox::climate;

namespace {

bool near(float left, float right, float tolerance = 1.0e-6F) {
  return std::fabs(left - right) <= tolerance;
}

ClimateInputSnapshot sampleSnapshot() {
  ClimateInputSnapshot snapshot{};
  snapshot.measurements.air_temperature_c = {23.5F, true, 7U};
  snapshot.measurements.relative_humidity_pct = {61.0F, true, 8U};
  snapshot.measurements.co2_ppm = {712.0F, true, 9U};
  snapshot.measurements.outside_temperature_c = {17.0F, true, 10U};
  snapshot.measurements.outside_humidity_pct = {52.0F, true, 11U};
  snapshot.humidity_control_mode = HumidityControlMode::Vpd;
  snapshot.targets.air_temperature_c = 24.5F;
  snapshot.targets.relative_humidity_pct = 62.0F;
  snapshot.targets.air_vpd_kpa = 1.1F;
  snapshot.targets.co2_enabled = true;
  snapshot.targets.co2_ppm = 980.0F;
  snapshot.schedule.light_level = 0.75F;
  snapshot.capabilities.heater = true;
  snapshot.capabilities.cooler = false;
  snapshot.capabilities.exhaust_fan = true;
  snapshot.capabilities.humidifier = true;
  snapshot.capabilities.dehumidifier = false;
  snapshot.capabilities.co2_doser = true;
  snapshot.sensor_timeout_ms = 31'000U;
  return snapshot;
}

class ProbeProvider final : public ClimateSnapshotProvider {
public:
  explicit ProbeProvider(bool available) : available_(available) {}

  bool snapshot(std::uint64_t monotonic_ms, ClimateInputSnapshot& output) noexcept override {
    ++calls;
    last_monotonic_ms = monotonic_ms;
    if (!available_) {
      return false;
    }
    output = sampleSnapshot();
    return true;
  }

  std::uint32_t calls = 0U;
  std::uint64_t last_monotonic_ms = 0U;

private:
  bool available_ = true;
};

void testObservedProviderIsTransparentAndSingleRead() {
  ProbeProvider source(true);
  ObservedClimateSnapshotProvider observed(source);
  ClimateInputSnapshot output{};

  assert(observed.snapshot(12'345U, output));
  assert(source.calls == 1U);
  assert(source.last_monotonic_ms == 12'345U);
  assert(near(output.measurements.air_temperature_c.value, 23.5F));

  const ClimateSnapshotObservation& observation = observed.observation();
  assert(observation.attempted);
  assert(observation.available);
  assert(observation.monotonic_ms == 12'345U);
  assert(near(observation.snapshot.measurements.relative_humidity_pct.value, 61.0F));
  assert(observation.snapshot.measurements.co2_ppm.age_ms == 9U);
  assert(observation.snapshot.humidity_control_mode == HumidityControlMode::Vpd);
  assert(!observation.snapshot.capabilities.cooler);
  assert(observation.snapshot.sensor_timeout_ms == 31'000U);
}

void testObservedProviderRecordsUnavailableWithoutInventingSnapshot() {
  ProbeProvider source(false);
  ObservedClimateSnapshotProvider observed(source);
  ClimateInputSnapshot output = sampleSnapshot();

  assert(!observed.snapshot(77U, output));
  assert(source.calls == 1U);
  const ClimateSnapshotObservation& observation = observed.observation();
  assert(observation.attempted);
  assert(!observation.available);
  assert(observation.monotonic_ms == 77U);
  assert(!observation.snapshot.measurements.air_temperature_c.valid);
}

void testDiagnosticsCopiesExistingControlEvidenceOnly() {
  ProbeProvider source(true);
  ObservedClimateSnapshotProvider observed(source);
  ClimateInputSnapshot output{};
  assert(observed.snapshot(2'000U, output));

  ClimateRuntimeDecision decision{};
  decision.mode = ClimatePolicyMode::MlShadow;
  decision.ml_evaluated = true;
  decision.authoritative_ml = false;
  decision.rule.raw.heater = 0.4F;
  decision.rule.arbitrated.heater = 0.3F;
  decision.rule.safe.heater = 0.2F;
  decision.rule.arbitration_interventions = OppositionHeaterCooler;
  decision.rule.safety_interventions = HighTemperature;
  decision.ml.raw.cooler = 0.8F;
  decision.ml.arbitrated.cooler = 0.7F;
  decision.ml.safe.cooler = 0.6F;
  decision.ml.arbitration_interventions = UnavailableHeater;
  decision.ml.safety_interventions = HighHumidity;
  decision.applied.exhaust_fan = 0.55F;

  ClimateLoopResult result{};
  result.io_status = ClimateLoopIoStatus::ActuatorApplyFailed;
  result.runtime_status = ClimateRuntimeStatus::Ok;
  result.input_sampled = true;
  result.command_applied = false;
  result.fail_safe_attempted = true;
  result.fail_safe_applied = true;

  PreviousClimateActions confirmed{};
  confirmed.heater = 0.1F;
  confirmed.exhaust_fan = 0.25F;

  const ClimateDiagnostics diagnostics =
      makeClimateDiagnostics(2'000U, observed.observation(), result, decision, confirmed, true);

  assert(diagnostics.schema_version == kClimateDiagnosticsSchemaVersion);
  assert(diagnostics.monotonic_ms == 2'000U);
  assert(diagnostics.input.available);
  assert(diagnostics.policy_mode == ClimatePolicyMode::MlShadow);
  assert(diagnostics.runtime_status == ClimateRuntimeStatus::Ok);
  assert(diagnostics.io_status == ClimateLoopIoStatus::ActuatorApplyFailed);
  assert(diagnostics.ml_evaluated);
  assert(!diagnostics.authoritative_ml);
  assert(near(diagnostics.rule.raw.heater, 0.4F));
  assert(near(diagnostics.rule.arbitrated.heater, 0.3F));
  assert(near(diagnostics.rule.safe.heater, 0.2F));
  assert(diagnostics.rule.arbitration_interventions == OppositionHeaterCooler);
  assert(diagnostics.rule.safety_interventions == HighTemperature);
  assert(near(diagnostics.ml_shadow.raw.cooler, 0.8F));
  assert(near(diagnostics.ml_shadow.arbitrated.cooler, 0.7F));
  assert(near(diagnostics.ml_shadow.safe.cooler, 0.6F));
  assert(near(diagnostics.final_safe_request.exhaust_fan, 0.55F));
  assert(near(diagnostics.confirmed_applied.heater, 0.1F));
  assert(near(diagnostics.confirmed_applied.exhaust_fan, 0.25F));
  assert(diagnostics.input_sampled);
  assert(!diagnostics.command_applied);
  assert(diagnostics.fail_safe_attempted);
  assert(diagnostics.fail_safe_applied);
  assert(diagnostics.actuator_fault_latched);
}

} // namespace

int main() {
  testObservedProviderIsTransparentAndSingleRead();
  testObservedProviderRecordsUnavailableWithoutInventingSnapshot();
  testDiagnosticsCopiesExistingControlEvidenceOnly();
  return 0;
}
