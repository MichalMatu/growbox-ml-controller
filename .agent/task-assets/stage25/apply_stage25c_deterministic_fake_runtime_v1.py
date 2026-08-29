from pathlib import Path

ROOT = Path('.')

header = r'''#pragma once

#include "climate/ClimateIoAdapters.h"

#include <cstdint>

namespace growbox::app::climate_io {

class DeterministicClimateScenarioProvider final : public ClimateSnapshotProvider {
public:
  static constexpr std::uint64_t kTickIntervalMs = 1'000U;
  static constexpr std::uint32_t kPeriodTicks = 240U;

  bool snapshot(std::uint64_t monotonic_ms, ClimateInputSnapshot& output) noexcept override;

  static std::uint32_t phaseTick(std::uint64_t monotonic_ms) noexcept;
};

} // namespace growbox::app::climate_io
'''

source = r'''#include "climate/ClimateDeterministicFake.h"

namespace growbox::app::climate_io {
namespace {

constexpr std::uint32_t kQuarterTicks = DeterministicClimateScenarioProvider::kPeriodTicks / 4U;

float lerp(float start, float end, float fraction) noexcept {
  return start + ((end - start) * fraction);
}

float quarterFraction(std::uint32_t phase_tick) noexcept {
  const std::uint32_t within = phase_tick % kQuarterTicks;
  return static_cast<float>(within) / static_cast<float>(kQuarterTicks - 1U);
}

void enableAll(ClimateInputSnapshot& output) noexcept {
  output.capabilities.heater = true;
  output.capabilities.cooler = true;
  output.capabilities.exhaust_fan = true;
  output.capabilities.humidifier = true;
  output.capabilities.dehumidifier = true;
  output.capabilities.co2_doser = true;
}

void setDayTargets(ClimateInputSnapshot& output) noexcept {
  output.targets.air_temperature_c = 24.5F;
  output.targets.relative_humidity_pct = 58.0F;
  output.targets.air_vpd_kpa = 1.2F;
  output.targets.co2_enabled = true;
  output.targets.co2_ppm = 950.0F;
  output.schedule.light_level = 1.0F;
}

void setNightTargets(ClimateInputSnapshot& output) noexcept {
  output.targets.air_temperature_c = 21.5F;
  output.targets.relative_humidity_pct = 65.0F;
  output.targets.air_vpd_kpa = 0.9F;
  output.targets.co2_enabled = false;
  output.targets.co2_ppm = 450.0F;
  output.schedule.light_level = 0.0F;
}

} // namespace

std::uint32_t DeterministicClimateScenarioProvider::phaseTick(
    std::uint64_t monotonic_ms) noexcept {
  return static_cast<std::uint32_t>((monotonic_ms / kTickIntervalMs) % kPeriodTicks);
}

bool DeterministicClimateScenarioProvider::snapshot(std::uint64_t monotonic_ms,
                                                    ClimateInputSnapshot& output) noexcept {
  output = {};
  output.sensor_timeout_ms = ::growbox::climate::kDefaultSensorTimeoutMs;
  enableAll(output);

  const std::uint32_t phase_tick = phaseTick(monotonic_ms);
  const std::uint32_t quarter = phase_tick / kQuarterTicks;
  const float fraction = quarterFraction(phase_tick);

  float temperature = 20.0F;
  float humidity = 68.0F;
  float co2 = 450.0F;
  float outside_temperature = 14.0F;
  float outside_humidity = 72.0F;

  switch (quarter) {
  case 0U:
    temperature = lerp(20.0F, 24.0F, fraction);
    humidity = lerp(68.0F, 60.0F, fraction);
    co2 = lerp(450.0F, 900.0F, fraction);
    outside_temperature = lerp(14.0F, 16.0F, fraction);
    outside_humidity = lerp(72.0F, 65.0F, fraction);
    setDayTargets(output);
    break;
  case 1U:
    temperature = lerp(24.0F, 28.0F, fraction);
    humidity = lerp(60.0F, 50.0F, fraction);
    co2 = lerp(900.0F, 1'200.0F, fraction);
    outside_temperature = lerp(16.0F, 20.0F, fraction);
    outside_humidity = lerp(65.0F, 55.0F, fraction);
    output.capabilities.cooler = false;
    setDayTargets(output);
    break;
  case 2U:
    temperature = lerp(28.0F, 25.0F, fraction);
    humidity = lerp(50.0F, 60.0F, fraction);
    co2 = lerp(1'200.0F, 700.0F, fraction);
    outside_temperature = lerp(20.0F, 16.0F, fraction);
    outside_humidity = lerp(55.0F, 70.0F, fraction);
    output.capabilities.humidifier = false;
    output.capabilities.co2_doser = false;
    setNightTargets(output);
    break;
  default:
    temperature = lerp(25.0F, 20.0F, fraction);
    humidity = lerp(60.0F, 68.0F, fraction);
    co2 = lerp(700.0F, 450.0F, fraction);
    outside_temperature = lerp(16.0F, 14.0F, fraction);
    outside_humidity = lerp(70.0F, 72.0F, fraction);
    output.capabilities.heater = false;
    output.capabilities.dehumidifier = false;
    setNightTargets(output);
    break;
  }

  output.measurements.air_temperature_c = {temperature, true, 0U};
  output.measurements.relative_humidity_pct = {humidity, true, 0U};
  output.measurements.co2_ppm = {co2, true, 0U};
  output.measurements.outside_temperature_c = {outside_temperature, true, 0U};
  output.measurements.outside_humidity_pct = {outside_humidity, true, 0U};
  return true;
}

} // namespace growbox::app::climate_io
'''

test = r'''#include "climate/ClimateApplication.h"
#include "climate/ClimateDeterministicFake.h"

#include <array>
#include <cassert>
#include <cmath>
#include <cstddef>
#include <cstdint>

using namespace growbox::app::climate_io;
using namespace growbox::climate;

namespace {

constexpr std::size_t kRoleCount = 6U;
constexpr std::array<ClimateActuatorRole, kRoleCount> kRoles{
    ClimateActuatorRole::Heater,       ClimateActuatorRole::Cooler,
    ClimateActuatorRole::ExhaustFan,   ClimateActuatorRole::Humidifier,
    ClimateActuatorRole::Dehumidifier, ClimateActuatorRole::Co2Doser,
};

bool near(float left, float right, float tolerance = 1.0e-5F) {
  return std::fabs(left - right) <= tolerance;
}

bool sameMeasured(const MeasuredValue& left, const MeasuredValue& right) {
  return near(left.value, right.value) && left.valid == right.valid && left.age_ms == right.age_ms;
}

bool sameSnapshot(const ClimateInputSnapshot& left, const ClimateInputSnapshot& right) {
  return sameMeasured(left.measurements.air_temperature_c, right.measurements.air_temperature_c) &&
         sameMeasured(left.measurements.relative_humidity_pct,
                      right.measurements.relative_humidity_pct) &&
         sameMeasured(left.measurements.co2_ppm, right.measurements.co2_ppm) &&
         sameMeasured(left.measurements.outside_temperature_c,
                      right.measurements.outside_temperature_c) &&
         sameMeasured(left.measurements.outside_humidity_pct,
                      right.measurements.outside_humidity_pct) &&
         near(left.targets.air_temperature_c, right.targets.air_temperature_c) &&
         near(left.targets.relative_humidity_pct, right.targets.relative_humidity_pct) &&
         near(left.targets.air_vpd_kpa, right.targets.air_vpd_kpa) &&
         left.targets.co2_enabled == right.targets.co2_enabled &&
         near(left.targets.co2_ppm, right.targets.co2_ppm) &&
         near(left.schedule.light_level, right.schedule.light_level) &&
         left.capabilities.heater == right.capabilities.heater &&
         left.capabilities.cooler == right.capabilities.cooler &&
         left.capabilities.exhaust_fan == right.capabilities.exhaust_fan &&
         left.capabilities.humidifier == right.capabilities.humidifier &&
         left.capabilities.dehumidifier == right.capabilities.dehumidifier &&
         left.capabilities.co2_doser == right.capabilities.co2_doser &&
         left.sensor_timeout_ms == right.sensor_timeout_ms;
}

bool sameRequest(const ClimatePolicyRequest& left, const ClimatePolicyRequest& right) {
  return near(left.heater, right.heater) && near(left.cooler, right.cooler) &&
         near(left.exhaust_fan, right.exhaust_fan) && near(left.humidifier, right.humidifier) &&
         near(left.dehumidifier, right.dehumidifier) && near(left.co2_doser, right.co2_doser);
}

bool samePrevious(const PreviousClimateActions& previous, const ClimatePolicyRequest& request) {
  return near(previous.heater, request.heater) && near(previous.cooler, request.cooler) &&
         near(previous.exhaust_fan, request.exhaust_fan) &&
         near(previous.humidifier, request.humidifier) &&
         near(previous.dehumidifier, request.dehumidifier) &&
         near(previous.co2_doser, request.co2_doser);
}

class RecordingRoleDriver final : public ClimateRoleDriver {
public:
  bool apply(ClimateActuatorRole role, float level, std::uint64_t monotonic_ms) noexcept override {
    const std::size_t role_index = calls % kRoleCount;
    assert(role == kRoles[role_index]);
    assert(level >= 0.0F && level <= 1.0F);
    if (role_index == 0U) {
      last_timestamp = monotonic_ms;
    } else {
      assert(monotonic_ms == last_timestamp);
    }
    last_levels[role_index] = level;
    ++calls;
    return true;
  }

  ClimatePolicyRequest lastRequest() const {
    ClimatePolicyRequest request{};
    request.heater = last_levels[0U];
    request.cooler = last_levels[1U];
    request.exhaust_fan = last_levels[2U];
    request.humidifier = last_levels[3U];
    request.dehumidifier = last_levels[4U];
    request.co2_doser = last_levels[5U];
    return request;
  }

  std::size_t calls = 0U;
  std::uint64_t last_timestamp = 0U;
  std::array<float, kRoleCount> last_levels{};
};

ClimateInputSnapshot snapshotAt(DeterministicClimateScenarioProvider& provider,
                                std::uint64_t timestamp) {
  ClimateInputSnapshot snapshot{};
  assert(provider.snapshot(timestamp, snapshot));
  return snapshot;
}

void testTimestampDeterminismAndPeriodicity() {
  DeterministicClimateScenarioProvider first;
  DeterministicClimateScenarioProvider second;
  constexpr std::array<std::uint64_t, 12U> kTimestamps{
      0U,      1'000U,   59'000U,  60'000U, 119'000U, 120'000U,
      179'000U, 180'000U, 239'000U, 240'000U, 241'000U, 777'000U,
  };

  for (const std::uint64_t timestamp : kTimestamps) {
    const ClimateInputSnapshot a = snapshotAt(first, timestamp);
    const ClimateInputSnapshot b = snapshotAt(first, timestamp);
    const ClimateInputSnapshot c = snapshotAt(second, timestamp);
    assert(sameSnapshot(a, b));
    assert(sameSnapshot(a, c));
  }

  assert(DeterministicClimateScenarioProvider::phaseTick(0U) == 0U);
  assert(DeterministicClimateScenarioProvider::phaseTick(239'000U) == 239U);
  assert(DeterministicClimateScenarioProvider::phaseTick(240'000U) == 0U);
  assert(DeterministicClimateScenarioProvider::phaseTick(241'000U) == 1U);
  assert(sameSnapshot(snapshotAt(first, 0U), snapshotAt(first, 240'000U)));
}

void testScenarioTransitionsMeasurementsTargetsScheduleAndCapabilities() {
  DeterministicClimateScenarioProvider provider;
  const ClimateInputSnapshot q0 = snapshotAt(provider, 0U);
  const ClimateInputSnapshot q0_end = snapshotAt(provider, 59'000U);
  const ClimateInputSnapshot q1 = snapshotAt(provider, 60'000U);
  const ClimateInputSnapshot q2 = snapshotAt(provider, 120'000U);
  const ClimateInputSnapshot q3 = snapshotAt(provider, 180'000U);

  assert(q0.measurements.air_temperature_c.valid);
  assert(q0.measurements.relative_humidity_pct.valid);
  assert(q0.measurements.co2_ppm.valid);
  assert(q0.measurements.outside_temperature_c.valid);
  assert(q0.measurements.outside_humidity_pct.valid);
  assert(q0.measurements.air_temperature_c.age_ms == 0U);
  assert(q0.sensor_timeout_ms == kDefaultSensorTimeoutMs);

  assert(q0_end.measurements.air_temperature_c.value > q0.measurements.air_temperature_c.value);
  assert(q0_end.measurements.relative_humidity_pct.value <
         q0.measurements.relative_humidity_pct.value);
  assert(q0_end.measurements.co2_ppm.value > q0.measurements.co2_ppm.value);
  assert(q0_end.measurements.outside_temperature_c.value >
         q0.measurements.outside_temperature_c.value);

  assert(near(q0.schedule.light_level, 1.0F));
  assert(near(q1.schedule.light_level, 1.0F));
  assert(near(q2.schedule.light_level, 0.0F));
  assert(near(q3.schedule.light_level, 0.0F));
  assert(q0.targets.co2_enabled);
  assert(!q2.targets.co2_enabled);
  assert(q0.targets.air_temperature_c > q2.targets.air_temperature_c);

  assert(q0.capabilities.cooler);
  assert(!q1.capabilities.cooler);
  assert(!q2.capabilities.humidifier);
  assert(!q2.capabilities.co2_doser);
  assert(!q3.capabilities.heater);
  assert(!q3.capabilities.dehumidifier);
  assert(q3.capabilities.cooler);
}

void testLongRunThroughFullApplicationPath() {
  DeterministicClimateScenarioProvider provider;
  RecordingRoleDriver driver;
  ClimateRuntimeConfig config{};
  config.mode = ClimatePolicyMode::Rule;
  config.sensor_timeout_ms = kDefaultSensorTimeoutMs;
  config.timestep_s = 1.0F;
  ClimateRuntimeController runtime(nullptr, config);
  ClimateApplication application(runtime, provider, driver);

  ClimatePolicyRequest previous_request{};
  bool saw_output_change = false;
  constexpr std::size_t kTicks = 1'200U;

  for (std::size_t tick = 0U; tick < kTicks; ++tick) {
    const std::uint64_t timestamp = tick * DeterministicClimateScenarioProvider::kTickIntervalMs;
    ClimateRuntimeDecision decision{};
    const ClimateLoopResult result = application.tick(timestamp, decision);

    assert(result.io_status == ClimateLoopIoStatus::Ok);
    assert(result.runtime_status == ClimateRuntimeStatus::Ok);
    assert(result.input_sampled);
    assert(result.command_applied);
    assert(!result.fail_safe_attempted);
    assert(!application.actuatorFaultLatched());
    assert(driver.calls == (tick + 1U) * kRoleCount);
    assert(driver.last_timestamp == timestamp);
    assert(sameRequest(driver.lastRequest(), decision.applied));
    assert(samePrevious(application.previousApplied(), decision.applied));

    if (tick > 0U && !sameRequest(previous_request, decision.applied)) {
      saw_output_change = true;
    }
    previous_request = decision.applied;

    const std::uint32_t phase = DeterministicClimateScenarioProvider::phaseTick(timestamp);
    if (phase == 60U) {
      assert(near(decision.applied.cooler, 0.0F));
    } else if (phase == 120U) {
      assert(near(decision.applied.humidifier, 0.0F));
      assert(near(decision.applied.co2_doser, 0.0F));
    } else if (phase == 180U) {
      assert(near(decision.applied.heater, 0.0F));
      assert(near(decision.applied.dehumidifier, 0.0F));
    }
  }

  assert(saw_output_change);
  assert(driver.calls == kTicks * kRoleCount);
}

} // namespace

int main() {
  testTimestampDeterminismAndPeriodicity();
  testScenarioTransitionsMeasurementsTargetsScheduleAndCapabilities();
  testLongRunThroughFullApplicationPath();
  return 0;
}
'''

(ROOT / 'src/climate/ClimateDeterministicFake.h').write_text(header, encoding='utf-8')
(ROOT / 'src/climate/ClimateDeterministicFake.cpp').write_text(source, encoding='utf-8')
test_dir = ROOT / 'test/test_climate_deterministic_fake_runtime'
test_dir.mkdir(parents=True, exist_ok=True)
(test_dir / 'test_main.cpp').write_text(test, encoding='utf-8')

runtime = ROOT / 'src/climate/ClimateV6FakeRuntime.cpp'
text = runtime.read_text(encoding='utf-8')
text = text.replace('#include "climate/ClimateApplication.h"\n', '#include "climate/ClimateApplication.h"\n#include "climate/ClimateDeterministicFake.h"\n', 1)
start = text.index('class FixedFakeSnapshotProvider final : public ClimateSnapshotProvider {')
end = text.index('class AcceptAllFakeRoleDriver final', start)
text = text[:start] + text[end:]
text = text.replace('constexpr std::uint32_t kTickIntervalMs = 1\'000U;\nconstexpr std::uint64_t kSensorTimeoutMs = 30\'000U;\n\n', '', 1)
text = text.replace('  config.sensor_timeout_ms = kSensorTimeoutMs;\n  config.timestep_s = static_cast<float>(kTickIntervalMs) / 1000.0F;\n',
                    '  config.sensor_timeout_ms = ::growbox::climate::kDefaultSensorTimeoutMs;\n  config.timestep_s = static_cast<float>(DeterministicClimateScenarioProvider::kTickIntervalMs) / 1000.0F;\n', 1)
text = text.replace('  cJSON_AddNumberToObject(document, "tick_interval_ms", kTickIntervalMs);\n',
                    '  cJSON_AddNumberToObject(document, "tick_interval_ms",\n                          DeterministicClimateScenarioProvider::kTickIntervalMs);\n  cJSON_AddStringToObject(document, "scenario", "deterministic-240-tick-v1");\n', 1)
text = text.replace('  FixedFakeSnapshotProvider provider;\n', '  DeterministicClimateScenarioProvider provider;\n', 1)
text = text.replace('    vTaskDelay(pdMS_TO_TICKS(kTickIntervalMs));\n',
                    '    vTaskDelay(pdMS_TO_TICKS(DeterministicClimateScenarioProvider::kTickIntervalMs));\n', 1)
runtime.write_text(text, encoding='utf-8')

cmake = ROOT / 'src/CMakeLists.txt'
text = cmake.read_text(encoding='utf-8')
anchor = '    "climate/ClimateApplication.cpp"\n'
assert anchor in text and 'ClimateDeterministicFake.cpp' not in text
text = text.replace(anchor, anchor + '    "climate/ClimateDeterministicFake.cpp"\n', 1)
cmake.write_text(text, encoding='utf-8')

host = ROOT / 'test/host/CMakeLists.txt'
text = host.read_text(encoding='utf-8')
assert 'climate_deterministic_fake_runtime_tests' not in text
insert_before = '\nif(UNIX)\n'
assert insert_before in text
block = r'''

add_executable(
  climate_deterministic_fake_runtime_tests
  "${PROJECT_ROOT}/test/test_climate_deterministic_fake_runtime/test_main.cpp"
  "${PROJECT_ROOT}/src/climate/ClimateApplication.cpp"
  "${PROJECT_ROOT}/src/climate/ClimateIoAdapters.cpp"
  "${PROJECT_ROOT}/src/climate/ClimateDeterministicFake.cpp"
  "${PROJECT_ROOT}/lib/environment_control/src/climate/ClimateControlLoop.cpp"
  "${PROJECT_ROOT}/lib/environment_control/src/climate/ClimateFeatureEncoder.cpp"
  "${PROJECT_ROOT}/lib/environment_control/src/climate/ClimateRuntimeController.cpp"
  "${PROJECT_ROOT}/lib/environment_control/src/climate/ClimateTrendEstimator.cpp"
)
target_include_directories(
  climate_deterministic_fake_runtime_tests
  PRIVATE
    "${PROJECT_ROOT}/src"
    "${PROJECT_ROOT}/lib/environment_control/src"
)
target_compile_features(climate_deterministic_fake_runtime_tests PRIVATE cxx_std_17)
target_compile_options(climate_deterministic_fake_runtime_tests PRIVATE -Wall -Wextra -Wpedantic)
'''
text = text.replace(insert_before, block + insert_before, 1)
link_anchor = '  target_link_libraries(climate_application_composition_tests PRIVATE m)\n'
assert link_anchor in text
text = text.replace(link_anchor, link_anchor + '  target_link_libraries(climate_deterministic_fake_runtime_tests PRIVATE m)\n', 1)
test_anchor = 'add_test(NAME climate_application_composition_tests COMMAND climate_application_composition_tests)\n'
assert test_anchor in text
text = text.replace(test_anchor, test_anchor + 'add_test(NAME climate_deterministic_fake_runtime_tests COMMAND climate_deterministic_fake_runtime_tests)\n', 1)
host.write_text(text, encoding='utf-8')

tidy = ROOT / 'scripts/run_clang_tidy_host.sh'
text = tidy.read_text(encoding='utf-8')
anchor = '  src/climate/ClimateApplication.cpp\n'
assert anchor in text and 'ClimateDeterministicFake.cpp' not in text
text = text.replace(anchor, anchor + '  src/climate/ClimateDeterministicFake.cpp\n', 1)
tidy.write_text(text, encoding='utf-8')

status = ROOT / 'docs/CURRENT_STATUS.md'
text = status.read_text(encoding='utf-8')
anchor = 'Stage25B adds an explicit build-time application boundary. `GROWBOX_APP_MODE` defaults to `legacy`, while `climate-v6-fake` selects a hardware-neutral climate-v6 runtime backed by a fixed fake snapshot provider and an accept-all fake role driver. The climate-v6 fake runtime emits startup/status identity (`application`, policy mode, input backend and output backend) and never touches GPIO or physical loads. Both application modes are required to compile in the ESP-IDF v5.5.4 gate.\n'
assert anchor in text and 'Stage25C replaces the fixed smoke snapshot' not in text
addition = anchor + '\nStage25C replaces the fixed smoke snapshot with `DeterministicClimateScenarioProvider`, a hardware-neutral provider whose output is a pure function of monotonic time. Its 240-tick cycle varies inside/outside T/RH/CO2, day/night targets and light schedule plus actuator capabilities. Host tests prove timestamp determinism, cycle periodicity and a 1,200-tick full `ClimateApplication` run with fake outputs. Fault injection remains intentionally reserved for Stage25E.\n'
text = text.replace(anchor, addition, 1)
status.write_text(text, encoding='utf-8')

plan = ROOT / 'docs/CONTINUATION_PLAN.md'
text = plan.read_text(encoding='utf-8')
old = '''### Stage25C — deterministic fake runtime

Replace the fixed smoke snapshot with a deterministic scenario provider that exercises changing
inside/outside measurements, target and schedule transitions, capabilities and long multi-tick
runs through exactly the same public provider/driver interfaces intended for hardware.
'''
new = '''### Stage25C completed — deterministic fake runtime

`DeterministicClimateScenarioProvider` is a hardware-neutral `ClimateSnapshotProvider` whose output
is a pure function of monotonic time. A 240-tick cycle changes inside/outside T/RH/CO2, day/night
targets, light schedule and actuator capabilities. The embedded `climate-v6-fake` runtime uses it,
and host coverage runs 1,200 ticks through the full `ClimateApplication` path. Sensor faults and
actuator rejection are deliberately deferred to Stage25E rather than mixed into the nominal fake.
'''
assert old in text
text = text.replace(old, new, 1)
plan.write_text(text, encoding='utf-8')
