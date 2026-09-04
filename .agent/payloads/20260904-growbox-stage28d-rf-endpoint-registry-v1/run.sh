#!/usr/bin/env bash
set -euo pipefail

EXPECTED=9b7cb532976e48343a2e28c2aa786417624f23c6
BRANCH=mvp/environment-controller

git fetch -q origin "$BRANCH"
git reset --hard "$EXPECTED"
test "$(git rev-parse HEAD)" = "$EXPECTED"
test "$(git rev-parse origin/$BRANCH)" = "$EXPECTED"
test -z "$(git status --porcelain)"

cat > src/climate/rf433/ClimateRf433EndpointRegistry.h <<'EOF'
#pragma once

#include "climate/ClimateSemanticOutput.h"
#include "climate/rf433/Rf433HardwareConfig.h"

namespace growbox::app::climate_io::rf433 {

// Stable neutral endpoint identity for the Stage28C-frozen hardware pair.
// Semantic actuator roles are assigned above this registry, never here.
inline constexpr ClimateEndpointId kRemoteSocket1ClimateEndpoint = 1U;

struct ClimateRf433EndpointBinding {
  ClimateEndpointId endpoint{kUnmappedClimateEndpoint};
  const RemoteSocketHardwareConfig* hardware{nullptr};
};

const ClimateRf433EndpointBinding*
findClimateRf433Endpoint(ClimateEndpointId endpoint) noexcept;

} // namespace growbox::app::climate_io::rf433
EOF

cat > src/climate/rf433/ClimateRf433EndpointRegistry.cpp <<'EOF'
#include "climate/rf433/ClimateRf433EndpointRegistry.h"

#include <array>

namespace growbox::app::climate_io::rf433 {
namespace {

constexpr std::array<ClimateRf433EndpointBinding, 1U> kBindings{{
    {kRemoteSocket1ClimateEndpoint, &kRemoteSocket1},
}};

} // namespace

const ClimateRf433EndpointBinding*
findClimateRf433Endpoint(ClimateEndpointId endpoint) noexcept {
  for (const ClimateRf433EndpointBinding& binding : kBindings) {
    if (binding.endpoint == endpoint) {
      return &binding;
    }
  }
  return nullptr;
}

} // namespace growbox::app::climate_io::rf433
EOF

python3 - <<'PY'
from pathlib import Path

# Compile the neutral registry into firmware builds.
p = Path("src/CMakeLists.txt")
s = p.read_text()
old = '    "climate/ClimateSemanticOutput.cpp"\n'
new = old + '    "climate/rf433/ClimateRf433EndpointRegistry.cpp"\n'
if old not in s or 'ClimateRf433EndpointRegistry.cpp' in s:
    raise SystemExit("src/CMakeLists registry insertion point invalid")
p.write_text(s.replace(old, new, 1))

# Compile the registry into the focused host semantic-output target.
p = Path("test/host/CMakeLists.txt")
s = p.read_text()
old = '  "${PROJECT_ROOT}/src/climate/ClimateSemanticOutput.cpp"\n)\n'
new = '  "${PROJECT_ROOT}/src/climate/ClimateSemanticOutput.cpp"\n  "${PROJECT_ROOT}/src/climate/rf433/ClimateRf433EndpointRegistry.cpp"\n)\n'
if old not in s or 'ClimateRf433EndpointRegistry.cpp' in s:
    raise SystemExit("host CMake registry insertion point invalid")
p.write_text(s.replace(old, new, 1))

# Extend the semantic-output tests with the neutral hardware endpoint contract
# and remove side effects from assert expressions.
p = Path("test/test_climate_semantic_output/test_main.cpp")
s = p.read_text()
s = s.replace(
    '#include "climate/ClimateSemanticOutput.h"\n',
    '#include "climate/ClimateSemanticOutput.h"\n#include "climate/rf433/ClimateRf433EndpointRegistry.h"\n',
    1,
)
s = s.replace(
    '    assert(bindClimateRole(config, roles[index], endpoint_ids[index]));\n',
    '    const bool bound = bindClimateRole(config, roles[index], endpoint_ids[index]);\n    assert(bound);\n',
)
s = s.replace(
    '  assert(unbindClimateRole(config, ClimateActuatorRole::Humidifier));\n',
    '  const bool humidifier_unbound = unbindClimateRole(config, ClimateActuatorRole::Humidifier);\n  assert(humidifier_unbound);\n',
    1,
)
old = '''void testBindingHelpersEnforceOneRolePerEndpoint() {
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
'''
new = '''void testBindingHelpersEnforceOneRolePerEndpoint() {
  ClimateSemanticOutputConfig config{};
  const bool heater_bound = bindClimateRole(config, ClimateActuatorRole::Heater, 42U);
  const bool duplicate_rejected = !bindClimateRole(config, ClimateActuatorRole::ExhaustFan, 42U);
  const bool unmapped_rejected =
      !bindClimateRole(config, ClimateActuatorRole::Cooler, kUnmappedClimateEndpoint);
  assert(heater_bound);
  assert(duplicate_rejected);
  assert(unmapped_rejected);
  assert(validateClimateSemanticOutputConfig(config) == ClimateSemanticOutputConfigStatus::Ok);

  const auto heater = config.roles[climateRoleIndex(ClimateActuatorRole::Heater)];
  const auto fan = config.roles[climateRoleIndex(ClimateActuatorRole::ExhaustFan)];
  assert(heater.enabled && heater.endpoint == 42U);
  assert(!fan.enabled && fan.endpoint == kUnmappedClimateEndpoint);

  const bool heater_unbound = unbindClimateRole(config, ClimateActuatorRole::Heater);
  const bool fan_bound = bindClimateRole(config, ClimateActuatorRole::ExhaustFan, 42U);
  assert(heater_unbound);
  assert(fan_bound);
  assert(validateClimateSemanticOutputConfig(config) == ClimateSemanticOutputConfigStatus::Ok);
}
'''
if old not in s:
    raise SystemExit("semantic helper test block missing")
s = s.replace(old, new, 1)
anchor = '''void testInvalidSemanticConfigFailsClosedBeforeEndpointWrite() {
'''
registry_test = '''void testNeutralRf433EndpointRegistryResolvesFrozenHardwareOnly() {
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
if anchor not in s:
    raise SystemExit("semantic invalid-config test anchor missing")
s = s.replace(anchor, registry_test + anchor, 1)
main_anchor = '  testBindingHelpersEnforceOneRolePerEndpoint();\n'
if main_anchor not in s:
    raise SystemExit("semantic test main anchor missing")
s = s.replace(main_anchor, main_anchor + '  testNeutralRf433EndpointRegistryResolvesFrozenHardwareOnly();\n', 1)
p.write_text(s)

# Synchronize Stage28D handoff text now that the stage has actually started.
p = Path("continuation.md")
s = p.read_text()
s = s.replace(
    "11. Do not start Stage28D merely because the handoff exists. Stage28D requires an explicit new user goal.",
    "11. Stage28D is already explicitly in progress. Continue only from the bounded scope recorded below and do not infer a semantic role for `remote_socket_1`.",
    1,
)
first_slice = "This slice does not assign `remote_socket_1` to heater, fan, humidifier or any other semantic role. The real-input runtime still uses `LockedFakeRoleDriver`; physical outputs remain `fake-locked`, and this task performs no RF transmit, flashing or mains-load actuation.\n"
second_slice = first_slice + "\nThe second bounded software-only slice adds a neutral RF433 endpoint registry: stable climate endpoint ID `1` resolves to the frozen `remote_socket_1` hardware configuration, while the registry itself contains no `ClimateActuatorRole` assignment. The registry is compiled by the firmware and covered by host tests; runtime output composition is still unchanged and fake-locked.\n"
if first_slice not in s:
    raise SystemExit("continuation Stage28D first-slice marker missing")
s = s.replace(first_slice, second_slice, 1)
s = s.replace(
    "If the operator explicitly authorizes Stage28D in the new conversation, first re-read the fresh active docs and exact source/daemon state, then define a bounded Stage28D plan before making semantic actuator-role changes. Preserve the frozen `remote_socket_1` hardware identity below the semantic layer and preserve fake-lock/no-unattended-mains safety until a later explicit physical-output gate proves otherwise.",
    "The neutral endpoint registry is now ready. The next semantic step must not guess which actuator role the physical `remote_socket_1` represents. A concrete role assignment and its binary-output policy require an explicit product-level choice; until then preserve `LockedFakeRoleDriver`, fake-lock/no-unattended-mains safety and the frozen hardware identity below the semantic layer.",
    1,
)
old_quote = "> Continue `MichalMatu/growbox-ml-controller` on branch `mvp/environment-controller`. First read `AGENTS.md`, `continuation.md`, `docs/CURRENT_STATUS.md`, `docs/PRESTAGE28D_GOLDEN_CHECKPOINT.md`, `docs/CONTINUATION_PLAN.md`, then fetch fresh HEAD and `agent-control:.agent/status/daemon.json`. Treat `316b58e76de609069ddbf2667fe86f6218fb2143` as the exact hardware-soaked Golden firmware SHA; later handoff/docs commits are docs-only. Stage27C and Stage28C are frozen, the known RF pair must not be rediscovered, outputs remain fake-locked, and Stage28D is NOT STARTED. Do not start Stage28D until I explicitly ask for it."
new_quote = "> Continue `MichalMatu/growbox-ml-controller` on branch `mvp/environment-controller`. First read `AGENTS.md`, `continuation.md`, `docs/CURRENT_STATUS.md`, `docs/PRESTAGE28D_GOLDEN_CHECKPOINT.md`, `docs/CONTINUATION_PLAN.md`, then fetch fresh HEAD and `agent-control:.agent/status/daemon.json`. Treat `316b58e76de609069ddbf2667fe86f6218fb2143` as the exact hardware-soaked Golden firmware SHA. Stage27C and Stage28C are frozen. Stage28D is IN PROGRESS: semantic mapping validation and the neutral `remote_socket_1` endpoint registry are implemented, but no semantic actuator role is assigned, runtime outputs remain fake-locked, and no physical RF output gate is open."
if old_quote not in s:
    raise SystemExit("continuation short instruction marker missing")
s = s.replace(old_quote, new_quote, 1)
p.write_text(s)

p = Path("docs/CURRENT_STATUS.md")
s = p.read_text()
old = "Stage28D is IN PROGRESS. The first software-only slice hardens semantic role-to-endpoint mapping validation while the real runtime remains fake-locked. No semantic role is yet assigned to `remote_socket_1`, and no physical RF output gate has been opened."
new = "Stage28D is IN PROGRESS. Semantic role-to-endpoint mapping now validates fail-closed, and a neutral RF433 registry maps stable climate endpoint ID `1` to the frozen `remote_socket_1` hardware configuration. No semantic role is yet assigned to that endpoint, the real runtime still uses `LockedFakeRoleDriver`, and no physical RF output gate has been opened. The next semantic role/binary-output choice must be explicit rather than inferred."
if old not in s:
    raise SystemExit("CURRENT_STATUS next-work marker missing")
p.write_text(s.replace(old, new, 1))

p = Path("docs/CONTINUATION_PLAN.md")
s = p.read_text()
old = "Stage28D was explicitly started by the operator. Its first bounded slice only hardens semantic role-to-endpoint mapping invariants. Keep `remote_socket_1` neutral, keep the real runtime fake-locked, and do not introduce unattended 230 V control or physical-state acknowledgement semantics."
new = "Stage28D was explicitly started by the operator. Semantic role-to-endpoint mapping is fail-closed, and the second bounded software slice adds stable endpoint ID `1` for the neutral frozen `remote_socket_1` hardware registry. No semantic role is assigned yet. Keep the real runtime fake-locked; the next role/binary-output policy is an explicit product choice, not something to infer. Do not introduce unattended 230 V control or physical-state acknowledgement semantics."
if old not in s:
    raise SystemExit("CONTINUATION_PLAN Stage28D marker missing")
p.write_text(s.replace(old, new, 1))
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
  src/CMakeLists.txt test/host/CMakeLists.txt \
  test/test_climate_semantic_output/test_main.cpp \
  continuation.md docs/CURRENT_STATUS.md docs/CONTINUATION_PLAN.md
FIRST_RC=$?
set -e
if [[ "$FIRST_RC" -ne 0 ]]; then
  "$PC" run --files \
    src/climate/rf433/ClimateRf433EndpointRegistry.h \
    src/climate/rf433/ClimateRf433EndpointRegistry.cpp \
    src/CMakeLists.txt test/host/CMakeLists.txt \
    test/test_climate_semantic_output/test_main.cpp \
    continuation.md docs/CURRENT_STATUS.md docs/CONTINUATION_PLAN.md
fi
git diff --check

export CMAKE_BUILD_PARALLEL_LEVEL=2
cmake -S test/host -B build/host-stage28d-rf-endpoint-registry -DCMAKE_BUILD_TYPE=Debug >/tmp/stage28d-registry-cmake-configure.log
cmake --build build/host-stage28d-rf-endpoint-registry --target climate_semantic_output_tests --parallel 2
./build/host-stage28d-rf-endpoint-registry/climate_semantic_output_tests

git add src/climate/rf433/ClimateRf433EndpointRegistry.h \
        src/climate/rf433/ClimateRf433EndpointRegistry.cpp \
        src/CMakeLists.txt test/host/CMakeLists.txt \
        test/test_climate_semantic_output/test_main.cpp \
        continuation.md docs/CURRENT_STATUS.md docs/CONTINUATION_PLAN.md
git commit -m "Add neutral Stage28D RF endpoint registry"
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

printf 'STAGE28D_RF_ENDPOINT_REGISTRY_READY commit=%s parent=%s endpoint_id=1 hardware=remote_socket_1 semantic_role=none focused=pass quality_gate=pass runtime_outputs=fake-locked rf_tx=0\n' "$NEW" "$EXPECTED"
