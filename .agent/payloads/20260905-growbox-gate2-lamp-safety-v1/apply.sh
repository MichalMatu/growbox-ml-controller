#!/usr/bin/env bash
set -euo pipefail

EXPECTED=2665f0ae864bf347c18b9ff8c3f9116a466313b3
BRANCH=mvp/environment-controller

git fetch -q origin "$BRANCH"
test "$(git rev-parse HEAD)" = "$EXPECTED"
test "$(git rev-parse origin/$BRANCH)" = "$EXPECTED"
test -z "$(git status --porcelain)"

mkdir -p test/test_stage28d_lamp_safety

cat > src/climate/Stage28dLampSafety.h <<'EOF'
#pragma once

#include "climate/ClimateTypes.h"

#include <cstdint>

namespace growbox::app::climate_io::stage28d {

struct LampSafetyConfig {
  float trip_temperature_c{28.0F};
  float recovery_temperature_c{26.0F};
  std::uint64_t recovery_hold_ms{600'000U};
  float light_on_threshold{0.5F};
  std::uint64_t temperature_timeout_ms{::growbox::climate::kDefaultSensorTimeoutMs};
};

enum class LampSafetyReason : std::uint8_t {
  Safe = 0U,
  TimerOff,
  TemperatureUnavailable,
  OverTemperature,
  RecoveryHold,
  InvalidConfig,
};

struct LampSafetyInput {
  float scheduled_light_level{0.0F};
  ::growbox::climate::MeasuredValue inside_temperature_c{};
  bool exhaust_fan_available{false};
  std::uint64_t monotonic_ms{0U};
};

struct LampSafetyDecision {
  bool schedule_requests_lamp_on{false};
  bool effective_lamp_on{false};
  bool force_exhaust_on{false};
  bool thermal_latched{false};
  LampSafetyReason reason{LampSafetyReason::Safe};
};

bool validateLampSafetyConfig(const LampSafetyConfig& config) noexcept;

class LampSafetyController {
public:
  explicit LampSafetyController(LampSafetyConfig config = {}) noexcept;

  LampSafetyDecision evaluate(const LampSafetyInput& input) noexcept;
  void reset() noexcept;
  const LampSafetyConfig& config() const noexcept { return config_; }

private:
  LampSafetyConfig config_{};
  bool thermal_latched_{false};
  bool recovery_running_{false};
  std::uint64_t recovery_started_ms_{0U};
};

} // namespace growbox::app::climate_io::stage28d
EOF

cat > src/climate/Stage28dLampSafety.cpp <<'EOF'
#include "climate/Stage28dLampSafety.h"

#include <cmath>

namespace growbox::app::climate_io::stage28d {

bool validateLampSafetyConfig(const LampSafetyConfig& config) noexcept {
  return std::isfinite(config.trip_temperature_c) &&
         std::isfinite(config.recovery_temperature_c) &&
         std::isfinite(config.light_on_threshold) &&
         config.recovery_temperature_c < config.trip_temperature_c &&
         config.light_on_threshold >= 0.0F && config.light_on_threshold <= 1.0F &&
         config.temperature_timeout_ms > 0U;
}

LampSafetyController::LampSafetyController(LampSafetyConfig config) noexcept : config_(config) {}

void LampSafetyController::reset() noexcept {
  thermal_latched_ = false;
  recovery_running_ = false;
  recovery_started_ms_ = 0U;
}

LampSafetyDecision LampSafetyController::evaluate(const LampSafetyInput& input) noexcept {
  LampSafetyDecision output{};
  output.schedule_requests_lamp_on = input.scheduled_light_level >= config_.light_on_threshold;

  if (!validateLampSafetyConfig(config_)) {
    thermal_latched_ = true;
    recovery_running_ = false;
    output.effective_lamp_on = false;
    output.force_exhaust_on = input.exhaust_fan_available;
    output.thermal_latched = true;
    output.reason = LampSafetyReason::InvalidConfig;
    return output;
  }

  const auto& temperature = input.inside_temperature_c;
  const bool temperature_usable = temperature.valid && std::isfinite(temperature.value) &&
                                  temperature.age_ms <= config_.temperature_timeout_ms;
  if (!temperature_usable) {
    thermal_latched_ = true;
    recovery_running_ = false;
    output.effective_lamp_on = false;
    output.force_exhaust_on = input.exhaust_fan_available;
    output.thermal_latched = true;
    output.reason = LampSafetyReason::TemperatureUnavailable;
    return output;
  }

  if (temperature.value >= config_.trip_temperature_c) {
    thermal_latched_ = true;
    recovery_running_ = false;
  }

  if (thermal_latched_) {
    if (temperature.value <= config_.recovery_temperature_c) {
      if (!recovery_running_) {
        recovery_running_ = true;
        recovery_started_ms_ = input.monotonic_ms;
      }
      if ((input.monotonic_ms - recovery_started_ms_) >= config_.recovery_hold_ms) {
        thermal_latched_ = false;
        recovery_running_ = false;
      }
    } else {
      recovery_running_ = false;
    }
  }

  output.thermal_latched = thermal_latched_;
  output.force_exhaust_on = thermal_latched_ && input.exhaust_fan_available;
  if (thermal_latched_) {
    output.effective_lamp_on = false;
    output.reason = temperature.value >= config_.trip_temperature_c
                        ? LampSafetyReason::OverTemperature
                        : LampSafetyReason::RecoveryHold;
    return output;
  }

  output.effective_lamp_on = output.schedule_requests_lamp_on;
  output.reason = output.schedule_requests_lamp_on ? LampSafetyReason::Safe
                                                   : LampSafetyReason::TimerOff;
  return output;
}

} // namespace growbox::app::climate_io::stage28d
EOF

cat > test/test_stage28d_lamp_safety/test_main.cpp <<'EOF'
#include "climate/Stage28dLampSafety.h"

#include <cassert>
#include <cstdint>
#include <limits>

using growbox::app::climate_io::stage28d::LampSafetyConfig;
using growbox::app::climate_io::stage28d::LampSafetyController;
using growbox::app::climate_io::stage28d::LampSafetyInput;
using growbox::app::climate_io::stage28d::LampSafetyReason;
using growbox::app::climate_io::stage28d::validateLampSafetyConfig;

namespace {

LampSafetyInput input(float light, float temperature_c, bool valid, std::uint64_t age_ms,
                      std::uint64_t now_ms, bool fan = true) {
  LampSafetyInput value{};
  value.scheduled_light_level = light;
  value.inside_temperature_c = {temperature_c, valid, age_ms};
  value.exhaust_fan_available = fan;
  value.monotonic_ms = now_ms;
  return value;
}

void testSafeTimerOnAndTimerOff() {
  LampSafetyController controller;
  auto on = controller.evaluate(input(1.0F, 24.0F, true, 100U, 1'000U));
  assert(on.schedule_requests_lamp_on);
  assert(on.effective_lamp_on);
  assert(!on.force_exhaust_on);
  assert(!on.thermal_latched);
  assert(on.reason == LampSafetyReason::Safe);

  auto off = controller.evaluate(input(0.0F, 24.0F, true, 100U, 2'000U));
  assert(!off.schedule_requests_lamp_on);
  assert(!off.effective_lamp_on);
  assert(off.reason == LampSafetyReason::TimerOff);
}

void testTripAt28ForcesLampOffAndBinaryFanOn() {
  LampSafetyController controller;
  auto decision = controller.evaluate(input(1.0F, 28.0F, true, 0U, 10'000U));
  assert(decision.schedule_requests_lamp_on);
  assert(!decision.effective_lamp_on);
  assert(decision.force_exhaust_on);
  assert(decision.thermal_latched);
  assert(decision.reason == LampSafetyReason::OverTemperature);
}

void testRecoveryRequires26OrBelowForTenMinutes() {
  LampSafetyController controller;
  controller.evaluate(input(1.0F, 28.2F, true, 0U, 0U));

  auto start = controller.evaluate(input(1.0F, 26.0F, true, 0U, 10'000U));
  assert(!start.effective_lamp_on);
  assert(start.force_exhaust_on);
  assert(start.reason == LampSafetyReason::RecoveryHold);

  auto almost = controller.evaluate(input(1.0F, 25.9F, true, 0U, 609'999U));
  assert(!almost.effective_lamp_on);
  assert(almost.thermal_latched);

  auto recovered = controller.evaluate(input(1.0F, 25.9F, true, 0U, 610'000U));
  assert(recovered.effective_lamp_on);
  assert(!recovered.force_exhaust_on);
  assert(!recovered.thermal_latched);
  assert(recovered.reason == LampSafetyReason::Safe);
}

void testRecoveryHoldResetsAbove26() {
  LampSafetyController controller;
  controller.evaluate(input(1.0F, 29.0F, true, 0U, 0U));
  controller.evaluate(input(1.0F, 25.5F, true, 0U, 100U));
  controller.evaluate(input(1.0F, 26.1F, true, 0U, 500'000U));
  auto restarted = controller.evaluate(input(1.0F, 25.5F, true, 0U, 600'000U));
  assert(!restarted.effective_lamp_on);
  auto recovered = controller.evaluate(input(1.0F, 25.5F, true, 0U, 1'200'000U));
  assert(recovered.effective_lamp_on);
}

void testStaleInvalidAndNonFiniteTemperatureFailClosed() {
  LampSafetyController stale_controller;
  auto stale = stale_controller.evaluate(input(1.0F, 24.0F, true, 30'001U, 1U));
  assert(!stale.effective_lamp_on);
  assert(stale.force_exhaust_on);
  assert(stale.thermal_latched);
  assert(stale.reason == LampSafetyReason::TemperatureUnavailable);

  LampSafetyController invalid_controller;
  auto invalid = invalid_controller.evaluate(input(1.0F, 24.0F, false, 0U, 1U));
  assert(!invalid.effective_lamp_on);
  assert(invalid.force_exhaust_on);

  LampSafetyController nan_controller;
  auto nonfinite = nan_controller.evaluate(
      input(1.0F, std::numeric_limits<float>::quiet_NaN(), true, 0U, 1U));
  assert(!nonfinite.effective_lamp_on);
  assert(nonfinite.force_exhaust_on);
}

void testNoFanCapabilityDoesNotInventFanActuation() {
  LampSafetyController controller;
  auto decision = controller.evaluate(input(1.0F, 28.5F, true, 0U, 0U, false));
  assert(!decision.effective_lamp_on);
  assert(!decision.force_exhaust_on);
  assert(decision.thermal_latched);
}

void testInvalidConfigFailsClosed() {
  LampSafetyConfig config{};
  config.recovery_temperature_c = 29.0F;
  assert(!validateLampSafetyConfig(config));
  LampSafetyController controller(config);
  auto decision = controller.evaluate(input(1.0F, 24.0F, true, 0U, 0U));
  assert(!decision.effective_lamp_on);
  assert(decision.force_exhaust_on);
  assert(decision.reason == LampSafetyReason::InvalidConfig);
}

} // namespace

int main() {
  testSafeTimerOnAndTimerOff();
  testTripAt28ForcesLampOffAndBinaryFanOn();
  testRecoveryRequires26OrBelowForTenMinutes();
  testRecoveryHoldResetsAbove26();
  testStaleInvalidAndNonFiniteTemperatureFailClosed();
  testNoFanCapabilityDoesNotInventFanActuation();
  testInvalidConfigFailsClosed();
  return 0;
}
EOF

python3 - <<'PY'
from pathlib import Path

p = Path('src/CMakeLists.txt')
s = p.read_text()
anchor = '    "climate/Stage28dOutputBindings.cpp"\n'
insert = anchor + '    "climate/Stage28dLampSafety.cpp"\n'
if anchor not in s or 'Stage28dLampSafety.cpp' in s:
    raise SystemExit('src CMake anchor invalid')
p.write_text(s.replace(anchor, insert, 1))

p = Path('test/host/CMakeLists.txt')
s = p.read_text()
anchor = 'add_executable(\n  tp357_decoder_tests\n'
block = '''add_executable(\n  stage28d_lamp_safety_tests\n  "${PROJECT_ROOT}/test/test_stage28d_lamp_safety/test_main.cpp"\n  "${PROJECT_ROOT}/src/climate/Stage28dLampSafety.cpp"\n)\ntarget_include_directories(\n  stage28d_lamp_safety_tests\n  PRIVATE\n    "${PROJECT_ROOT}/src"\n    "${PROJECT_ROOT}/lib/environment_control/src"\n)\ntarget_compile_features(stage28d_lamp_safety_tests PRIVATE cxx_std_17)\ntarget_compile_options(stage28d_lamp_safety_tests PRIVATE -Wall -Wextra -Wpedantic)\n\n'''
if anchor not in s or 'stage28d_lamp_safety_tests' in s:
    raise SystemExit('host CMake anchor invalid')
p.write_text(s.replace(anchor, block + anchor, 1))

p = Path('docs/PROJECT_ROADMAP.md')
s = p.read_text()
s = s.replace('### Gate 2 — lamp timer + thermal safety, software only — NEXT\n',
              '### Gate 2 — lamp timer + thermal safety, software only — COMPLETE\n', 1)
marker = 'The exact thresholds should be configuration, not hidden magic constants in the RF driver.\n'
note = marker + ('\nFrozen mint-test baseline: `28.0 °C` trip, `26.0 °C` recovery threshold, '
                 '`10 min` continuous recovery hold, and binary exhaust-fan force ON while thermal '
                 'safety is latched. Invalid/stale TP357 temperature fails closed for lighting. '
                 'This controller remains software-only and performs no RF TX.\n')
if marker not in s:
    raise SystemExit('roadmap Gate 2 marker missing')
s = s.replace(marker, note, 1)
p.write_text(s)

p = Path('docs/CURRENT_STATUS.md')
s = p.read_text()
s = s.replace('Gate 1 semantic binding COMPLETE -> Gate 2 lamp safety NEXT',
              'Gate 1 semantic binding COMPLETE -> Gate 2 lamp safety COMPLETE -> Gate 3 verification NEXT', 1)
s = s.replace('The recovery threshold/hysteresis hold duration for the 28 °C lamp cutoff must remain explicit configuration in Gate 2 rather than being hidden in the RF driver.',
              'The Gate 2 lamp safety configuration is frozen at 28.0 °C trip, 26.0 °C recovery and a 10-minute continuous recovery hold. The exhaust fan remains a binary OFF/ON actuator. The thresholds live in the safety controller, not the RF driver.', 1)
p.write_text(s)
PY

cmake -S test/host -B build/host-gate2-lamp-safety -DCMAKE_BUILD_TYPE=Debug >/tmp/gate2-lamp-cmake.log
cmake --build build/host-gate2-lamp-safety --target stage28d_lamp_safety_tests --parallel 1
./build/host-gate2-lamp-safety/stage28d_lamp_safety_tests

git diff --check
git add src/climate/Stage28dLampSafety.h src/climate/Stage28dLampSafety.cpp test/test_stage28d_lamp_safety/test_main.cpp src/CMakeLists.txt test/host/CMakeLists.txt docs/PROJECT_ROADMAP.md docs/CURRENT_STATUS.md
git commit -m "Add Stage28D lamp thermal safety"
