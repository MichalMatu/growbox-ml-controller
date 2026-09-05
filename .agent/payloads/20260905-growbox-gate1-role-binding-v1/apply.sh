#!/usr/bin/env bash
set -euo pipefail

EXPECTED=3f413a2bb517f90637cf9b7849ea2fd1e09e5e5b
BRANCH=mvp/environment-controller

git fetch -q origin "$BRANCH"
test "$(git rev-parse HEAD)" = "$EXPECTED"
test "$(git rev-parse origin/$BRANCH)" = "$EXPECTED"
test -z "$(git status --porcelain)"

cat > src/climate/rf433/ClimateRf433EndpointRegistry.h <<'EOF'
#pragma once

#include "climate/ClimateSemanticOutput.h"
#include "climate/rf433/Rf433HardwareConfig.h"

namespace growbox::app::climate_io::rf433 {

// Stable neutral endpoint identities for the three physically validated Stage28D loads.
// Semantic actuator roles are assigned above this hardware registry.
inline constexpr ClimateEndpointId kRemoteSocket1ClimateEndpoint = 1U;
inline constexpr ClimateEndpointId kRemoteSocket2ClimateEndpoint = 2U;
inline constexpr ClimateEndpointId kRemoteSocket3ClimateEndpoint = 3U;

struct ClimateRf433EndpointBinding {
  ClimateEndpointId endpoint{kUnmappedClimateEndpoint};
  const RemoteSocketHardwareConfig* hardware{nullptr};
};

const ClimateRf433EndpointBinding* findClimateRf433Endpoint(ClimateEndpointId endpoint) noexcept;

} // namespace growbox::app::climate_io::rf433
EOF

cat > src/climate/rf433/ClimateRf433EndpointRegistry.cpp <<'EOF'
#include "climate/rf433/ClimateRf433EndpointRegistry.h"

#include <array>

namespace growbox::app::climate_io::rf433 {
namespace {

constexpr std::array<ClimateRf433EndpointBinding, 3U> kBindings{{
    {kRemoteSocket1ClimateEndpoint, &kRemoteSocket1},
    {kRemoteSocket2ClimateEndpoint, &kRemoteSocket2},
    {kRemoteSocket3ClimateEndpoint, &kRemoteSocket3},
}};

} // namespace

const ClimateRf433EndpointBinding* findClimateRf433Endpoint(ClimateEndpointId endpoint) noexcept {
  for (const ClimateRf433EndpointBinding& binding : kBindings) {
    if (binding.endpoint == endpoint) {
      return &binding;
    }
  }
  return nullptr;
}

} // namespace growbox::app::climate_io::rf433
EOF

cat > src/climate/Stage28dOutputBindings.h <<'EOF'
#pragma once

#include "climate/ClimateSemanticOutput.h"
#include "climate/rf433/ClimateRf433EndpointRegistry.h"

#include <cstdint>

namespace growbox::app::climate_io::stage28d {

inline constexpr ClimateEndpointId kExhaustFanEndpoint =
    rf433::kRemoteSocket1ClimateEndpoint;
inline constexpr ClimateEndpointId kScheduledLightEndpoint =
    rf433::kRemoteSocket2ClimateEndpoint;
inline constexpr ClimateEndpointId kHumidifierEndpoint =
    rf433::kRemoteSocket3ClimateEndpoint;

enum class OutputBindingStatus : std::uint8_t {
  Ok = 0U,
  ClimateConfigInvalid,
  HardwareRegistryMismatch,
  ScheduledLightRoutedToClimate,
  ExhaustFanMissingOrWrong,
  HumidifierMissingOrWrong,
  UnexpectedClimateRole,
};

ClimateSemanticOutputConfig makeClimateSemanticOutputConfig() noexcept;
OutputBindingStatus validateOutputBindings(const ClimateSemanticOutputConfig& config) noexcept;
bool isScheduledLightEndpoint(ClimateEndpointId endpoint) noexcept;

} // namespace growbox::app::climate_io::stage28d
EOF

cat > src/climate/Stage28dOutputBindings.cpp <<'EOF'
#include "climate/Stage28dOutputBindings.h"

namespace growbox::app::climate_io::stage28d {
namespace {

bool mappingMatches(const ClimateSemanticOutputConfig& config, ClimateActuatorRole role,
                    ClimateEndpointId endpoint) noexcept {
  const std::size_t index = climateRoleIndex(role);
  if (index >= config.roles.size()) {
    return false;
  }
  const ClimateRoleEndpointMapping& mapping = config.roles[index];
  return mapping.enabled && mapping.endpoint == endpoint;
}

bool mappingIsCleanlyDisabled(const ClimateSemanticOutputConfig& config,
                              ClimateActuatorRole role) noexcept {
  const std::size_t index = climateRoleIndex(role);
  if (index >= config.roles.size()) {
    return false;
  }
  const ClimateRoleEndpointMapping& mapping = config.roles[index];
  return !mapping.enabled && mapping.endpoint == kUnmappedClimateEndpoint;
}

bool hardwareMatches(ClimateEndpointId endpoint,
                     const rf433::RemoteSocketHardwareConfig* expected) noexcept {
  const rf433::ClimateRf433EndpointBinding* binding = rf433::findClimateRf433Endpoint(endpoint);
  return binding != nullptr && binding->endpoint == endpoint && binding->hardware == expected;
}

} // namespace

ClimateSemanticOutputConfig makeClimateSemanticOutputConfig() noexcept {
  ClimateSemanticOutputConfig config{};
  const bool fan_bound = bindClimateRole(config, ClimateActuatorRole::ExhaustFan,
                                         kExhaustFanEndpoint);
  const bool humidifier_bound = bindClimateRole(config, ClimateActuatorRole::Humidifier,
                                                kHumidifierEndpoint);
  if (!fan_bound || !humidifier_bound) {
    return {};
  }
  return config;
}

OutputBindingStatus validateOutputBindings(const ClimateSemanticOutputConfig& config) noexcept {
  if (validateClimateSemanticOutputConfig(config) != ClimateSemanticOutputConfigStatus::Ok) {
    return OutputBindingStatus::ClimateConfigInvalid;
  }

  if (!hardwareMatches(kExhaustFanEndpoint, &rf433::kRemoteSocket1) ||
      !hardwareMatches(kScheduledLightEndpoint, &rf433::kRemoteSocket2) ||
      !hardwareMatches(kHumidifierEndpoint, &rf433::kRemoteSocket3)) {
    return OutputBindingStatus::HardwareRegistryMismatch;
  }

  for (const ClimateRoleEndpointMapping& mapping : config.roles) {
    if (mapping.enabled && mapping.endpoint == kScheduledLightEndpoint) {
      return OutputBindingStatus::ScheduledLightRoutedToClimate;
    }
  }

  if (!mappingMatches(config, ClimateActuatorRole::ExhaustFan, kExhaustFanEndpoint)) {
    return OutputBindingStatus::ExhaustFanMissingOrWrong;
  }
  if (!mappingMatches(config, ClimateActuatorRole::Humidifier, kHumidifierEndpoint)) {
    return OutputBindingStatus::HumidifierMissingOrWrong;
  }

  constexpr ClimateActuatorRole kDisabledClimateRoles[] = {
      ClimateActuatorRole::Heater,
      ClimateActuatorRole::Cooler,
      ClimateActuatorRole::Dehumidifier,
      ClimateActuatorRole::Co2Doser,
  };
  for (ClimateActuatorRole role : kDisabledClimateRoles) {
    if (!mappingIsCleanlyDisabled(config, role)) {
      return OutputBindingStatus::UnexpectedClimateRole;
    }
  }

  return OutputBindingStatus::Ok;
}

bool isScheduledLightEndpoint(ClimateEndpointId endpoint) noexcept {
  return endpoint == kScheduledLightEndpoint;
}

} // namespace growbox::app::climate_io::stage28d
EOF

python3 - <<'PY'
from pathlib import Path

# Compile the frozen Stage28D binding contract into firmware and focused host tests.
p = Path("src/CMakeLists.txt")
s = p.read_text()
old = '    "climate/rf433/ClimateRf433EndpointRegistry.cpp"\n'
new = old + '    "climate/Stage28dOutputBindings.cpp"\n'
if old not in s or 'Stage28dOutputBindings.cpp' in s:
    raise SystemExit("src/CMakeLists binding insertion point invalid")
p.write_text(s.replace(old, new, 1))

p = Path("test/host/CMakeLists.txt")
s = p.read_text()
old = '  "${PROJECT_ROOT}/src/climate/rf433/ClimateRf433EndpointRegistry.cpp"\n)\n'
new = '  "${PROJECT_ROOT}/src/climate/rf433/ClimateRf433EndpointRegistry.cpp"\n  "${PROJECT_ROOT}/src/climate/Stage28dOutputBindings.cpp"\n)\n'
if old not in s or 'Stage28dOutputBindings.cpp' in s:
    raise SystemExit("host CMake binding insertion point invalid")
p.write_text(s.replace(old, new, 1))

p = Path("test/test_climate_semantic_output/test_main.cpp")
s = p.read_text()
include_anchor = '#include "climate/ClimateSemanticOutput.h"\n'
if include_anchor not in s or 'Stage28dOutputBindings.h' in s:
    raise SystemExit("semantic-output include anchor invalid")
s = s.replace(include_anchor, include_anchor + '#include "climate/Stage28dOutputBindings.h"\n', 1)
old_registry = '''void testNeutralRf433EndpointRegistryResolvesFrozenHardwareOnly() {
  using namespace growbox::app::climate_io::rf433;

  static_assert(kRemoteSocket1ClimateEndpoint != kUnmappedClimateEndpoint);
  const ClimateRf433EndpointBinding* binding =
      findClimateRf433Endpoint(kRemoteSocket1ClimateEndpoint);
  assert(binding != nullptr);
  assert(binding->endpoint == kRemoteSocket1ClimateEndpoint);
  assert(binding->hardware == &kRemoteSocket1);
  assert(findClimateRf433Endpoint(kUnmappedClimateEndpoint) == nullptr);
  assert(findClimateRf433Endpoint(0U) == nullptr);

  ClimateSemanticOutputConfig config{};
  assert(validateClimateSemanticOutputConfig(config) == ClimateSemanticOutputConfigStatus::Ok);
  for (const ClimateRoleEndpointMapping& role : config.roles) {
    assert(!role.enabled);
    assert(role.endpoint == kUnmappedClimateEndpoint);
  }
}
'''
new_registry = '''void testNeutralRf433EndpointRegistryResolvesAllValidatedHardware() {
  using namespace growbox::app::climate_io::rf433;

  static_assert(kRemoteSocket1ClimateEndpoint != kRemoteSocket2ClimateEndpoint);
  static_assert(kRemoteSocket1ClimateEndpoint != kRemoteSocket3ClimateEndpoint);
  static_assert(kRemoteSocket2ClimateEndpoint != kRemoteSocket3ClimateEndpoint);

  const ClimateRf433EndpointBinding* fan = findClimateRf433Endpoint(kRemoteSocket1ClimateEndpoint);
  const ClimateRf433EndpointBinding* lamp = findClimateRf433Endpoint(kRemoteSocket2ClimateEndpoint);
  const ClimateRf433EndpointBinding* humidifier =
      findClimateRf433Endpoint(kRemoteSocket3ClimateEndpoint);
  assert(fan != nullptr && fan->hardware == &kRemoteSocket1);
  assert(lamp != nullptr && lamp->hardware == &kRemoteSocket2);
  assert(humidifier != nullptr && humidifier->hardware == &kRemoteSocket3);
  assert(findClimateRf433Endpoint(kUnmappedClimateEndpoint) == nullptr);
  assert(findClimateRf433Endpoint(0U) == nullptr);
  assert(findClimateRf433Endpoint(99U) == nullptr);
}

void testStage28dBindingsFreezeFanHumidifierAndScheduledLightRoles() {
  using namespace growbox::app::climate_io::stage28d;

  const ClimateSemanticOutputConfig config = makeClimateSemanticOutputConfig();
  assert(validateOutputBindings(config) == OutputBindingStatus::Ok);

  const ClimateRoleEndpointMapping fan =
      config.roles[climateRoleIndex(ClimateActuatorRole::ExhaustFan)];
  const ClimateRoleEndpointMapping humidifier =
      config.roles[climateRoleIndex(ClimateActuatorRole::Humidifier)];
  assert(fan.enabled && fan.endpoint == kExhaustFanEndpoint);
  assert(humidifier.enabled && humidifier.endpoint == kHumidifierEndpoint);
  assert(isScheduledLightEndpoint(kScheduledLightEndpoint));
  assert(!isScheduledLightEndpoint(kExhaustFanEndpoint));
  assert(!isScheduledLightEndpoint(kHumidifierEndpoint));

  constexpr ClimateActuatorRole disabled_roles[] = {
      ClimateActuatorRole::Heater,
      ClimateActuatorRole::Cooler,
      ClimateActuatorRole::Dehumidifier,
      ClimateActuatorRole::Co2Doser,
  };
  for (ClimateActuatorRole role : disabled_roles) {
    const ClimateRoleEndpointMapping mapping = config.roles[climateRoleIndex(role)];
    assert(!mapping.enabled);
    assert(mapping.endpoint == kUnmappedClimateEndpoint);
  }
}

void testStage28dBindingsFailClosedForMissingDuplicateUnknownAndLampCollision() {
  using namespace growbox::app::climate_io::stage28d;

  ClimateSemanticOutputConfig missing = makeClimateSemanticOutputConfig();
  missing.roles[climateRoleIndex(ClimateActuatorRole::Humidifier)] = {};
  assert(validateOutputBindings(missing) == OutputBindingStatus::HumidifierMissingOrWrong);

  ClimateSemanticOutputConfig duplicate = makeClimateSemanticOutputConfig();
  duplicate.roles[climateRoleIndex(ClimateActuatorRole::Humidifier)] = {true,
                                                                        kExhaustFanEndpoint};
  assert(validateOutputBindings(duplicate) == OutputBindingStatus::ClimateConfigInvalid);

  ClimateSemanticOutputConfig unknown = makeClimateSemanticOutputConfig();
  unknown.roles[climateRoleIndex(ClimateActuatorRole::ExhaustFan)] = {true, 99U};
  assert(validateOutputBindings(unknown) == OutputBindingStatus::ExhaustFanMissingOrWrong);

  ClimateSemanticOutputConfig lamp_collision = makeClimateSemanticOutputConfig();
  lamp_collision.roles[climateRoleIndex(ClimateActuatorRole::ExhaustFan)] = {
      true, kScheduledLightEndpoint};
  assert(validateOutputBindings(lamp_collision) == OutputBindingStatus::ScheduledLightRoutedToClimate);

  ClimateSemanticOutputConfig unexpected = makeClimateSemanticOutputConfig();
  unexpected.roles[climateRoleIndex(ClimateActuatorRole::Heater)] = {true, 88U};
  assert(validateOutputBindings(unexpected) == OutputBindingStatus::UnexpectedClimateRole);

  ClimateSemanticOutputConfig stale_disabled = makeClimateSemanticOutputConfig();
  stale_disabled.roles[climateRoleIndex(ClimateActuatorRole::Cooler)] = {false, 77U};
  assert(validateOutputBindings(stale_disabled) == OutputBindingStatus::UnexpectedClimateRole);
}
'''
if old_registry not in s:
    raise SystemExit("neutral registry test block missing")
s = s.replace(old_registry, new_registry, 1)
s = s.replace(
    '  testNeutralRf433EndpointRegistryResolvesFrozenHardwareOnly();\n',
    '  testNeutralRf433EndpointRegistryResolvesAllValidatedHardware();\n'
    '  testStage28dBindingsFreezeFanHumidifierAndScheduledLightRoles();\n'
    '  testStage28dBindingsFailClosedForMissingDuplicateUnknownAndLampCollision();\n',
    1,
)
p.write_text(s)

# Mark Gate 1 complete only in the same executable commit that contains the contract.
p = Path("docs/PROJECT_ROADMAP.md")
s = p.read_text()
heading = '### Gate 1 — semantic binding, software only\n'
if heading not in s:
    raise SystemExit("PROJECT_ROADMAP Gate 1 heading missing")
s = s.replace(heading, '### Gate 1 — semantic binding, software only — COMPLETE\n', 1)
marker = 'Unknown/duplicate/missing bindings must fail closed. Keep the runtime output driver fake-locked.\n'
note = marker + '\nThe frozen software contract assigns `remote_socket_1` to `ExhaustFan`, `remote_socket_3` to `Humidifier`, and reserves `remote_socket_2` as the dedicated scheduled-light endpoint. The Stage28D binding validator rejects missing, duplicate, unknown, stale or lamp-as-climate mappings. Automatic physical TX remains fake-locked.\n'
if marker not in s:
    raise SystemExit("PROJECT_ROADMAP Gate 1 marker missing")
s = s.replace(marker, note, 1)
s = s.replace('### Gate 2 — lamp timer + thermal safety, software only\n',
              '### Gate 2 — lamp timer + thermal safety, software only — NEXT\n', 1)
p.write_text(s)

p = Path("docs/CURRENT_STATUS.md")
s = p.read_text()
s = s.replace(
    '**Stage27C FROZEN -> Stage28A DONE -> Stage28B DONE -> Stage28C DONE -> pre-Stage28D golden gate COMPLETE -> Stage28D manual RF path COMPLETE -> semantic/safety integration NEXT**',
    '**Stage27C FROZEN -> Stage28A DONE -> Stage28B DONE -> Stage28C DONE -> pre-Stage28D golden gate COMPLETE -> Stage28D manual RF path COMPLETE -> Gate 1 semantic binding COMPLETE -> Gate 2 lamp safety NEXT**',
    1,
)
s = s.replace(
    '## Intended actuator semantics\n\n- fan RF endpoint -> `ExhaustFan`;\n- humidifier RF endpoint -> `Humidifier`;\n- lamp RF endpoint -> scheduled lighting path, not a normal Climate-v6 ML output.\n',
    '## Frozen actuator semantics\n\n- `remote_socket_1` / endpoint 1 -> `ExhaustFan`;\n- `remote_socket_3` / endpoint 3 -> `Humidifier`;\n- `remote_socket_2` / endpoint 2 -> dedicated scheduled-light path, not a normal Climate-v6 ML output.\n\nThe Gate 1 validator fails closed for missing, duplicate, unknown, stale or scheduled-light-as-climate bindings. Automatic runtime outputs remain fake-locked.\n',
    1,
)
s = s.replace(
    '1. software-only semantic binding for fan/humidifier plus a dedicated scheduled-light path;\n2. software-only lamp timer + over-temperature safety override with hysteresis;\n3. focused tests/build while physical outputs remain fake-locked;\n4. exact-SHA flash/read-only smoke;\n5. operator-present physical role-routing validation;\n6. supervised thermal-safety validation using deterministic temperature injection rather than deliberately overheating the growbox;\n7. short supervised closed-loop run;\n8. only then consider a separately authorized unattended real-output soak.',
    '1. software-only lamp timer + over-temperature safety override with hysteresis;\n2. focused tests/build while physical outputs remain fake-locked;\n3. exact-SHA flash/read-only smoke;\n4. operator-present physical role-routing validation;\n5. supervised thermal-safety validation using deterministic temperature injection rather than deliberately overheating the growbox;\n6. short supervised closed-loop run;\n7. only then consider a separately authorized unattended real-output soak.',
    1,
)
p.write_text(s)

p = Path("docs/CONTINUATION_PLAN.md")
s = p.read_text()
s = s.replace(
    '**Stage27C FROZEN -> Stage28A DONE -> Stage28B DONE -> Stage28C DONE -> pre-Stage28D golden gate COMPLETE -> Stage28D manual RF path COMPLETE -> semantic/safety integration NEXT**',
    '**Stage27C FROZEN -> Stage28A DONE -> Stage28B DONE -> Stage28C DONE -> pre-Stage28D golden gate COMPLETE -> Stage28D manual RF path COMPLETE -> Gate 1 semantic binding COMPLETE -> Gate 2 lamp safety NEXT**',
    1,
)
old = '''## First incomplete gate

Start with **software-only semantic/safety integration** while keeping the real runtime fake-locked:

1. bind fan endpoint to `ExhaustFan`;
2. bind humidifier endpoint to `Humidifier`;
3. create/use a dedicated scheduled-light endpoint/path for the lamp;
4. implement an independent lamp over-temperature OFF override with recovery hysteresis;
5. ensure high-temperature safety can demand maximum exhaust ventilation when available;
6. ensure unknown/duplicate/missing mappings fail closed;
7. add focused host tests proving mapping/arbitration without real RF TX.

Do not perform physical actuation in this first software slice.
'''
new = '''## First incomplete gate

Gate 1 semantic binding is complete: endpoint 1 / `remote_socket_1` is frozen as `ExhaustFan`, endpoint 3 / `remote_socket_3` as `Humidifier`, and endpoint 2 / `remote_socket_2` is reserved for scheduled lighting outside the six Climate-v6 roles. Binding validation fails closed and automatic outputs remain fake-locked.

Start with **Gate 2 — software-only lamp timer + thermal safety**:

1. implement scheduled requested lamp ON/OFF state;
2. add an independent over-temperature OFF override with configurable threshold;
3. require recovery hysteresis / hold conditions before lamp re-enable;
4. ensure high-temperature safety can demand maximum exhaust ventilation when available;
5. fail safe when the required temperature input is stale or unusable;
6. keep the lamp outside the normal Climate-v6 output roles;
7. add focused host tests proving schedule/safety arbitration without real RF TX.

Do not perform physical actuation in this software gate.
'''
if old not in s:
    raise SystemExit("CONTINUATION_PLAN first incomplete gate block missing")
s = s.replace(old, new, 1)
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
  src/climate/rf433/ClimateRf433EndpointRegistry.h \
  src/climate/rf433/ClimateRf433EndpointRegistry.cpp \
  src/climate/Stage28dOutputBindings.h \
  src/climate/Stage28dOutputBindings.cpp \
  src/CMakeLists.txt test/host/CMakeLists.txt \
  test/test_climate_semantic_output/test_main.cpp \
  docs/PROJECT_ROADMAP.md docs/CURRENT_STATUS.md docs/CONTINUATION_PLAN.md
RC=$?
set -e
if [[ "$RC" -ne 0 ]]; then
  "$PC" run --files \
    src/climate/rf433/ClimateRf433EndpointRegistry.h \
    src/climate/rf433/ClimateRf433EndpointRegistry.cpp \
    src/climate/Stage28dOutputBindings.h \
    src/climate/Stage28dOutputBindings.cpp \
    src/CMakeLists.txt test/host/CMakeLists.txt \
    test/test_climate_semantic_output/test_main.cpp \
    docs/PROJECT_ROADMAP.md docs/CURRENT_STATUS.md docs/CONTINUATION_PLAN.md
fi

git diff --check
git add src/climate/rf433/ClimateRf433EndpointRegistry.h \
        src/climate/rf433/ClimateRf433EndpointRegistry.cpp \
        src/climate/Stage28dOutputBindings.h \
        src/climate/Stage28dOutputBindings.cpp \
        src/CMakeLists.txt test/host/CMakeLists.txt \
        test/test_climate_semantic_output/test_main.cpp \
        docs/PROJECT_ROADMAP.md docs/CURRENT_STATUS.md docs/CONTINUATION_PLAN.md
git commit -m "Freeze Stage28D actuator role bindings"

test "$(git rev-parse HEAD^)" = "$EXPECTED"
test -z "$(git status --porcelain)"
printf 'GATE1_EDIT_READY commit=%s parent=%s outputs=fake-locked rf_tx=0\n' "$(git rev-parse HEAD)" "$EXPECTED"
