#!/usr/bin/env bash
set -euo pipefail

EXPECTED=ed5afcebec68fe89dffa27fc03a8e19122644b9e
BRANCH=mvp/environment-controller

# Stage28D slice 1 is software-only. It must not flash hardware, transmit RF,
# assign remote_socket_1 to a concrete actuator role, or unlock physical outputs.
git fetch -q origin "$BRANCH"
git reset --hard "$EXPECTED"
test "$(git rev-parse HEAD)" = "$EXPECTED"
test "$(git rev-parse origin/$BRANCH)" = "$EXPECTED"
test -z "$(git status --porcelain)"

cat > src/climate/ClimateSemanticOutput.h <<'EOF'
#pragma once

#include "climate/ClimateIoAdapters.h"

#include <array>
#include <cstddef>
#include <cstdint>
#include <limits>

namespace growbox::app::climate_io {

using ClimateEndpointId = std::uint16_t;
inline constexpr std::size_t kClimateActuatorRoleCount = 6U;
inline constexpr ClimateEndpointId kUnmappedClimateEndpoint =
    std::numeric_limits<ClimateEndpointId>::max();

struct ClimateRoleEndpointMapping {
  bool enabled = false;
  ClimateEndpointId endpoint = kUnmappedClimateEndpoint;
};

struct ClimateSemanticOutputConfig {
  std::array<ClimateRoleEndpointMapping, kClimateActuatorRoleCount> roles{};
};

enum class ClimateSemanticOutputConfigStatus : std::uint8_t {
  Ok = 0U,
  EnabledRoleUnmapped,
  DuplicateEndpoint,
};

constexpr std::size_t climateRoleIndex(ClimateActuatorRole role) noexcept {
  switch (role) {
  case ClimateActuatorRole::Heater:
    return 0U;
  case ClimateActuatorRole::Cooler:
    return 1U;
  case ClimateActuatorRole::ExhaustFan:
    return 2U;
  case ClimateActuatorRole::Humidifier:
    return 3U;
  case ClimateActuatorRole::Dehumidifier:
    return 4U;
  case ClimateActuatorRole::Co2Doser:
    return 5U;
  }
  return kClimateActuatorRoleCount;
}

ClimateSemanticOutputConfigStatus
validateClimateSemanticOutputConfig(const ClimateSemanticOutputConfig& config) noexcept;

bool bindClimateRole(ClimateSemanticOutputConfig& config, ClimateActuatorRole role,
                     ClimateEndpointId endpoint) noexcept;
bool unbindClimateRole(ClimateSemanticOutputConfig& config, ClimateActuatorRole role) noexcept;

class ClimateOutputEndpoint {
public:
  virtual ~ClimateOutputEndpoint() = default;
  virtual bool write(ClimateEndpointId endpoint, float normalized_level,
                     std::uint64_t monotonic_ms) noexcept = 0;
};

class MappedClimateRoleDriver final : public ClimateRoleDriver {
public:
  MappedClimateRoleDriver(ClimateSemanticOutputConfig config,
                          ClimateOutputEndpoint& endpoint) noexcept
      : config_(config), config_status_(validateClimateSemanticOutputConfig(config_)),
        endpoint_(endpoint) {}

  bool apply(ClimateActuatorRole role, float level, std::uint64_t monotonic_ms) noexcept override;

  const ClimateSemanticOutputConfig& config() const noexcept {
    return config_;
  }

  ClimateSemanticOutputConfigStatus configStatus() const noexcept {
    return config_status_;
  }

private:
  ClimateSemanticOutputConfig config_{};
  ClimateSemanticOutputConfigStatus config_status_{ClimateSemanticOutputConfigStatus::Ok};
  ClimateOutputEndpoint& endpoint_;
};

} // namespace growbox::app::climate_io
EOF

cat > src/climate/ClimateSemanticOutput.cpp <<'EOF'
#include "climate/ClimateSemanticOutput.h"

#include <algorithm>
#include <cmath>

namespace growbox::app::climate_io {

ClimateSemanticOutputConfigStatus
validateClimateSemanticOutputConfig(const ClimateSemanticOutputConfig& config) noexcept {
  for (std::size_t index = 0U; index < config.roles.size(); ++index) {
    const ClimateRoleEndpointMapping& mapping = config.roles[index];
    if (!mapping.enabled) {
      continue;
    }
    if (mapping.endpoint == kUnmappedClimateEndpoint) {
      return ClimateSemanticOutputConfigStatus::EnabledRoleUnmapped;
    }
    for (std::size_t previous = 0U; previous < index; ++previous) {
      const ClimateRoleEndpointMapping& other = config.roles[previous];
      if (other.enabled && other.endpoint == mapping.endpoint) {
        return ClimateSemanticOutputConfigStatus::DuplicateEndpoint;
      }
    }
  }
  return ClimateSemanticOutputConfigStatus::Ok;
}

bool bindClimateRole(ClimateSemanticOutputConfig& config, ClimateActuatorRole role,
                     ClimateEndpointId endpoint) noexcept {
  const std::size_t index = climateRoleIndex(role);
  if (index >= config.roles.size() || endpoint == kUnmappedClimateEndpoint) {
    return false;
  }

  for (std::size_t other_index = 0U; other_index < config.roles.size(); ++other_index) {
    if (other_index == index) {
      continue;
    }
    const ClimateRoleEndpointMapping& other = config.roles[other_index];
    if (other.enabled && other.endpoint == endpoint) {
      return false;
    }
  }

  config.roles[index] = {true, endpoint};
  return true;
}

bool unbindClimateRole(ClimateSemanticOutputConfig& config, ClimateActuatorRole role) noexcept {
  const std::size_t index = climateRoleIndex(role);
  if (index >= config.roles.size()) {
    return false;
  }
  config.roles[index] = {};
  return true;
}

bool MappedClimateRoleDriver::apply(ClimateActuatorRole role, float level,
                                    std::uint64_t monotonic_ms) noexcept {
  if (config_status_ != ClimateSemanticOutputConfigStatus::Ok || !std::isfinite(level)) {
    return false;
  }

  const std::size_t index = climateRoleIndex(role);
  if (index >= config_.roles.size()) {
    return false;
  }

  const float normalized = std::clamp(level, 0.0F, 1.0F);
  const ClimateRoleEndpointMapping& mapping = config_.roles[index];
  if (!mapping.enabled || mapping.endpoint == kUnmappedClimateEndpoint) {
    return normalized == 0.0F;
  }

  return endpoint_.write(mapping.endpoint, normalized, monotonic_ms);
}

} // namespace growbox::app::climate_io
EOF

cat > test/test_climate_semantic_output/test_main.cpp <<'EOF'
#include "climate/ClimateSemanticOutput.h"

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

struct EndpointWrite {
  ClimateEndpointId endpoint = 0U;
  float level = 0.0F;
  std::uint64_t monotonic_ms = 0U;
};

class RecordingEndpoint final : public ClimateOutputEndpoint {
public:
  bool write(ClimateEndpointId endpoint, float normalized_level,
             std::uint64_t monotonic_ms) noexcept override {
    writes.push_back({endpoint, normalized_level, monotonic_ms});
    return endpoint != rejected_endpoint;
  }

  ClimateEndpointId rejected_endpoint = kUnmappedClimateEndpoint;
  std::vector<EndpointWrite> writes{};
};

ClimateSemanticOutputConfig mappedConfig() {
  ClimateSemanticOutputConfig config{};
  const std::array<ClimateEndpointId, kClimateActuatorRoleCount> endpoint_ids = {101U, 202U, 303U,
                                                                                 404U, 505U, 606U};
  const std::array<ClimateActuatorRole, kClimateActuatorRoleCount> roles = {
      ClimateActuatorRole::Heater,       ClimateActuatorRole::Cooler,
      ClimateActuatorRole::ExhaustFan,   ClimateActuatorRole::Humidifier,
      ClimateActuatorRole::Dehumidifier, ClimateActuatorRole::Co2Doser,
  };
  for (std::size_t index = 0U; index < endpoint_ids.size(); ++index) {
    assert(bindClimateRole(config, roles[index], endpoint_ids[index]));
  }
  assert(validateClimateSemanticOutputConfig(config) == ClimateSemanticOutputConfigStatus::Ok);
  return config;
}

void testDeterministicRoleMappingThroughExistingAdapter() {
  RecordingEndpoint endpoint;
  MappedClimateRoleDriver driver(mappedConfig(), endpoint);
  ClimateActuatorAdapter adapter(driver);

  ClimatePolicyRequest request{};
  request.heater = 0.10F;
  request.cooler = 0.20F;
  request.exhaust_fan = 0.30F;
  request.humidifier = 0.40F;
  request.dehumidifier = 0.50F;
  request.co2_doser = 0.60F;

  assert(adapter.apply(request, 12'345U));
  assert(endpoint.writes.size() == kClimateActuatorRoleCount);

  const std::array<ClimateEndpointId, kClimateActuatorRoleCount> expected_ids = {101U, 202U, 303U,
                                                                                 404U, 505U, 606U};
  const std::array<float, kClimateActuatorRoleCount> expected_levels = {0.10F, 0.20F, 0.30F,
                                                                        0.40F, 0.50F, 0.60F};
  for (std::size_t index = 0U; index < endpoint.writes.size(); ++index) {
    assert(endpoint.writes[index].endpoint == expected_ids[index]);
    assert(near(endpoint.writes[index].level, expected_levels[index]));
    assert(endpoint.writes[index].monotonic_ms == 12'345U);
  }
}

void testExplicitOffReachesEveryEnabledEndpoint() {
  RecordingEndpoint endpoint;
  MappedClimateRoleDriver driver(mappedConfig(), endpoint);
  ClimateActuatorAdapter adapter(driver);

  const ClimatePolicyRequest off{};
  assert(adapter.apply(off, 77U));
  assert(endpoint.writes.size() == kClimateActuatorRoleCount);
  for (const EndpointWrite& write : endpoint.writes) {
    assert(near(write.level, 0.0F));
    assert(write.monotonic_ms == 77U);
  }
}

void testDisabledMappingAcceptsOffButRejectsNonzero() {
  ClimateSemanticOutputConfig config = mappedConfig();
  assert(unbindClimateRole(config, ClimateActuatorRole::Humidifier));

  RecordingEndpoint endpoint;
  MappedClimateRoleDriver driver(config, endpoint);

  assert(driver.apply(ClimateActuatorRole::Humidifier, 0.0F, 100U));
  assert(endpoint.writes.empty());
  assert(!driver.apply(ClimateActuatorRole::Humidifier, 0.4F, 101U));
  assert(endpoint.writes.empty());

  assert(driver.apply(ClimateActuatorRole::Heater, 0.4F, 102U));
  assert(endpoint.writes.size() == 1U);
  assert(endpoint.writes.front().endpoint == 101U);
}

void testEndpointAlwaysReceivesNormalizedFiniteLevel() {
  RecordingEndpoint endpoint;
  MappedClimateRoleDriver driver(mappedConfig(), endpoint);

  assert(driver.apply(ClimateActuatorRole::Heater, -0.5F, 1U));
  assert(driver.apply(ClimateActuatorRole::Cooler, 1.5F, 2U));
  assert(endpoint.writes.size() == 2U);
  assert(near(endpoint.writes[0].level, 0.0F));
  assert(near(endpoint.writes[1].level, 1.0F));

  assert(!driver.apply(ClimateActuatorRole::ExhaustFan, std::nanf(""), 3U));
  assert(endpoint.writes.size() == 2U);
}

void testPartialEndpointRejectionPropagatesWithoutSkippingOtherRoles() {
  RecordingEndpoint endpoint;
  endpoint.rejected_endpoint = 303U;
  MappedClimateRoleDriver driver(mappedConfig(), endpoint);
  ClimateActuatorAdapter adapter(driver);

  ClimatePolicyRequest request{};
  request.heater = 0.2F;
  request.cooler = 0.3F;
  request.exhaust_fan = 0.4F;
  request.humidifier = 0.5F;
  request.dehumidifier = 0.6F;
  request.co2_doser = 0.7F;

  assert(!adapter.apply(request, 500U));
  assert(endpoint.writes.size() == kClimateActuatorRoleCount);
  assert(endpoint.writes[2].endpoint == 303U);
}

void testBindingHelpersEnforceOneRolePerEndpoint() {
  ClimateSemanticOutputConfig config{};
  assert(bindClimateRole(config, ClimateActuatorRole::Heater, 42U));
  assert(!bindClimateRole(config, ClimateActuatorRole::ExhaustFan, 42U));
  assert(!bindClimateRole(config, ClimateActuatorRole::Cooler, kUnmappedClimateEndpoint));
  assert(validateClimateSemanticOutputConfig(config) == ClimateSemanticOutputConfigStatus::Ok);

  const auto heater = config.roles[climateRoleIndex(ClimateActuatorRole::Heater)];
  const auto fan = config.roles[climateRoleIndex(ClimateActuatorRole::ExhaustFan)];
  assert(heater.enabled && heater.endpoint == 42U);
  assert(!fan.enabled && fan.endpoint == kUnmappedClimateEndpoint);

  assert(unbindClimateRole(config, ClimateActuatorRole::Heater));
  assert(bindClimateRole(config, ClimateActuatorRole::ExhaustFan, 42U));
  assert(validateClimateSemanticOutputConfig(config) == ClimateSemanticOutputConfigStatus::Ok);
}

void testInvalidSemanticConfigFailsClosedBeforeEndpointWrite() {
  ClimateSemanticOutputConfig unmapped{};
  unmapped.roles[climateRoleIndex(ClimateActuatorRole::Heater)].enabled = true;
  assert(validateClimateSemanticOutputConfig(unmapped) ==
         ClimateSemanticOutputConfigStatus::EnabledRoleUnmapped);

  ClimateSemanticOutputConfig duplicate{};
  duplicate.roles[climateRoleIndex(ClimateActuatorRole::Heater)] = {true, 7U};
  duplicate.roles[climateRoleIndex(ClimateActuatorRole::ExhaustFan)] = {true, 7U};
  assert(validateClimateSemanticOutputConfig(duplicate) ==
         ClimateSemanticOutputConfigStatus::DuplicateEndpoint);

  RecordingEndpoint endpoint;
  MappedClimateRoleDriver driver(duplicate, endpoint);
  assert(driver.configStatus() == ClimateSemanticOutputConfigStatus::DuplicateEndpoint);
  assert(!driver.apply(ClimateActuatorRole::Heater, 0.0F, 1U));
  assert(!driver.apply(ClimateActuatorRole::Heater, 1.0F, 2U));
  assert(endpoint.writes.empty());
}

} // namespace

int main() {
  testDeterministicRoleMappingThroughExistingAdapter();
  testExplicitOffReachesEveryEnabledEndpoint();
  testDisabledMappingAcceptsOffButRejectsNonzero();
  testEndpointAlwaysReceivesNormalizedFiniteLevel();
  testPartialEndpointRejectionPropagatesWithoutSkippingOtherRoles();
  testBindingHelpersEnforceOneRolePerEndpoint();
  testInvalidSemanticConfigFailsClosedBeforeEndpointWrite();
  return 0;
}
EOF

python3 - <<'PY'
from pathlib import Path

transition_old = "**Stage27C FROZEN -> Stage28A DONE -> Stage28B DONE -> Stage28C DONE -> pre-Stage28D golden gate COMPLETE -> Stage28D NOT STARTED**"
transition_new = "**Stage27C FROZEN -> Stage28A DONE -> Stage28B DONE -> Stage28C DONE -> pre-Stage28D golden gate COMPLETE -> Stage28D IN PROGRESS**"

p = Path("continuation.md")
s = p.read_text()
if transition_old not in s:
    raise SystemExit("continuation transition marker missing")
s = s.replace(transition_old, transition_new, 1)
anchor = "## What comes next\n"
section = """## Stage28D progress\n\nThe operator explicitly started Stage28D on 2026-09-04. The first bounded slice is software-only semantic binding hardening:\n\n- validate enabled role mappings before any endpoint write;\n- reject enabled mappings without a concrete endpoint;\n- reject one physical endpoint being assigned to multiple active semantic roles;\n- provide explicit bind/unbind helpers so mapping changes are transactional and reviewable;\n- fail closed before endpoint writes when the semantic mapping is invalid.\n\nThis slice does not assign `remote_socket_1` to heater, fan, humidifier or any other semantic role. The real-input runtime still uses `LockedFakeRoleDriver`; physical outputs remain `fake-locked`, and this task performs no RF transmit, flashing or mains-load actuation.\n\n"""
if anchor not in s:
    raise SystemExit("continuation next-work anchor missing")
s = s.replace(anchor, section + anchor, 1)
s = s.replace("Stage28D remains intentionally **NOT STARTED**.", "Stage28D is now **IN PROGRESS**.", 1)
p.write_text(s)

p = Path("docs/CURRENT_STATUS.md")
s = p.read_text()
if transition_old not in s:
    raise SystemExit("CURRENT_STATUS transition marker missing")
s = s.replace(transition_old, transition_new, 1)
s = s.replace(
    "Stage28D remains intentionally NOT STARTED and must begin only as an explicit later step.",
    "Stage28D is IN PROGRESS. The first software-only slice hardens semantic role-to-endpoint mapping validation while the real runtime remains fake-locked. No semantic role is yet assigned to `remote_socket_1`, and no physical RF output gate has been opened.",
    1,
)
p.write_text(s)

p = Path("docs/CONTINUATION_PLAN.md")
s = p.read_text()
short_old = "**Stage28A DONE -> Stage28B DONE -> Stage28C DONE -> pre-Stage28D golden gate COMPLETE -> Stage28D NOT STARTED**"
short_new = "**Stage28A DONE -> Stage28B DONE -> Stage28C DONE -> pre-Stage28D golden gate COMPLETE -> Stage28D IN PROGRESS**"
if short_old not in s:
    raise SystemExit("CONTINUATION_PLAN transition marker missing")
s = s.replace(short_old, short_new, 1)
s = s.replace(
    "Do not introduce semantic actuator-role mapping, unattended 230 V control or physical-state acknowledgement semantics unless the operator explicitly starts the relevant later stage. Stage28D must not start implicitly from a wake or from this handoff.",
    "Stage28D was explicitly started by the operator. Its first bounded slice only hardens semantic role-to-endpoint mapping invariants. Keep `remote_socket_1` neutral, keep the real runtime fake-locked, and do not introduce unattended 230 V control or physical-state acknowledgement semantics.",
    1,
)
p.write_text(s)
PY

git diff --check
PC="$(git rev-parse --show-toplevel)/.venv/bin/pre-commit"
if [[ ! -x "$PC" ]]; then
  echo "pre-commit missing" >&2
  exit 2
fi
set +e
"$PC" run --files \
  src/climate/ClimateSemanticOutput.h \
  src/climate/ClimateSemanticOutput.cpp \
  test/test_climate_semantic_output/test_main.cpp \
  continuation.md docs/CURRENT_STATUS.md docs/CONTINUATION_PLAN.md
FIRST_RC=$?
set -e
if [[ "$FIRST_RC" -ne 0 ]]; then
  "$PC" run --files \
    src/climate/ClimateSemanticOutput.h \
    src/climate/ClimateSemanticOutput.cpp \
    test/test_climate_semantic_output/test_main.cpp \
    continuation.md docs/CURRENT_STATUS.md docs/CONTINUATION_PLAN.md
fi
git diff --check

export CMAKE_BUILD_PARALLEL_LEVEL=2
cmake -S test/host -B build/host-stage28d-semantic-binding -DCMAKE_BUILD_TYPE=Debug >/tmp/stage28d-cmake-configure.log
cmake --build build/host-stage28d-semantic-binding --target climate_semantic_output_tests --parallel 2
./build/host-stage28d-semantic-binding/climate_semantic_output_tests

git add src/climate/ClimateSemanticOutput.h \
        src/climate/ClimateSemanticOutput.cpp \
        test/test_climate_semantic_output/test_main.cpp \
        continuation.md docs/CURRENT_STATUS.md docs/CONTINUATION_PLAN.md
git commit -m "Start Stage28D semantic binding validation"
NEW=$(git rev-parse HEAD)

export CMAKE_BUILD_PARALLEL_LEVEL=2
bash scripts/quality_gate_push.sh

git diff --check
test -z "$(git status --porcelain)"
git fetch -q origin "$BRANCH"
test "$(git rev-parse origin/$BRANCH)" = "$EXPECTED"
git push origin HEAD:"$BRANCH"
git fetch -q origin "$BRANCH"
test "$(git rev-parse origin/$BRANCH)" = "$NEW"

printf 'STAGE28D_SEMANTIC_BINDING_READY commit=%s parent=%s focused=pass quality_gate=pass runtime_outputs=fake-locked rf_tx=0 semantic_remote_socket_assignment=none\n' "$NEW" "$EXPECTED"
