from pathlib import Path


def write(path: str, content: str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


write(
    "src/climate/ClimateSemanticOutput.h",
    r'''#pragma once

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
      : config_(config), endpoint_(endpoint) {}

  bool apply(ClimateActuatorRole role, float level,
             std::uint64_t monotonic_ms) noexcept override;

  const ClimateSemanticOutputConfig& config() const noexcept {
    return config_;
  }

private:
  ClimateSemanticOutputConfig config_{};
  ClimateOutputEndpoint& endpoint_;
};

} // namespace growbox::app::climate_io
''',
)

write(
    "src/climate/ClimateSemanticOutput.cpp",
    r'''#include "climate/ClimateSemanticOutput.h"

#include <algorithm>
#include <cmath>

namespace growbox::app::climate_io {

bool MappedClimateRoleDriver::apply(ClimateActuatorRole role, float level,
                                    std::uint64_t monotonic_ms) noexcept {
  if (!std::isfinite(level)) {
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
''',
)

write(
    "test/test_climate_semantic_output/test_main.cpp",
    r'''#include "climate/ClimateSemanticOutput.h"

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
  const std::array<ClimateEndpointId, kClimateActuatorRoleCount> endpoint_ids = {
      101U, 202U, 303U, 404U, 505U, 606U};
  for (std::size_t index = 0U; index < endpoint_ids.size(); ++index) {
    config.roles[index].enabled = true;
    config.roles[index].endpoint = endpoint_ids[index];
  }
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

  const std::array<ClimateEndpointId, kClimateActuatorRoleCount> expected_ids = {
      101U, 202U, 303U, 404U, 505U, 606U};
  const std::array<float, kClimateActuatorRoleCount> expected_levels = {
      0.10F, 0.20F, 0.30F, 0.40F, 0.50F, 0.60F};
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
  config.roles[climateRoleIndex(ClimateActuatorRole::Humidifier)] = {};

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

} // namespace

int main() {
  testDeterministicRoleMappingThroughExistingAdapter();
  testExplicitOffReachesEveryEnabledEndpoint();
  testDisabledMappingAcceptsOffButRejectsNonzero();
  testEndpointAlwaysReceivesNormalizedFiniteLevel();
  testPartialEndpointRejectionPropagatesWithoutSkippingOtherRoles();
  return 0;
}
''',
)

src_cmake_path = Path("src/CMakeLists.txt")
src_cmake = src_cmake_path.read_text(encoding="utf-8")
needle = '    "climate/ClimateCompositeInput.cpp"\n'
assert needle in src_cmake
assert 'ClimateSemanticOutput.cpp' not in src_cmake
src_cmake = src_cmake.replace(needle, needle + '    "climate/ClimateSemanticOutput.cpp"\n', 1)
src_cmake_path.write_text(src_cmake, encoding="utf-8")

host_cmake_path = Path("test/host/CMakeLists.txt")
host_cmake = host_cmake_path.read_text(encoding="utf-8")
assert "climate_semantic_output_tests" not in host_cmake
anchor = "\nif(UNIX)\n"
assert anchor in host_cmake
block = r'''

add_executable(
  climate_semantic_output_tests
  "${PROJECT_ROOT}/test/test_climate_semantic_output/test_main.cpp"
  "${PROJECT_ROOT}/src/climate/ClimateIoAdapters.cpp"
  "${PROJECT_ROOT}/src/climate/ClimateSemanticOutput.cpp"
)
target_include_directories(
  climate_semantic_output_tests
  PRIVATE
    "${PROJECT_ROOT}/src"
    "${PROJECT_ROOT}/lib/environment_control/src"
)
target_compile_features(climate_semantic_output_tests PRIVATE cxx_std_17)
target_compile_options(climate_semantic_output_tests PRIVATE -Wall -Wextra -Wpedantic)
'''
host_cmake = host_cmake.replace(anchor, block + anchor, 1)
host_cmake = host_cmake.replace(
    "  target_link_libraries(climate_composite_input_tests PRIVATE m)\n",
    "  target_link_libraries(climate_composite_input_tests PRIVATE m)\n"
    "  target_link_libraries(climate_semantic_output_tests PRIVATE m)\n",
    1,
)
host_cmake = host_cmake.replace(
    "add_test(NAME climate_composite_input_tests COMMAND climate_composite_input_tests)\n",
    "add_test(NAME climate_composite_input_tests COMMAND climate_composite_input_tests)\n"
    "add_test(NAME climate_semantic_output_tests COMMAND climate_semantic_output_tests)\n",
    1,
)
host_cmake_path.write_text(host_cmake, encoding="utf-8")

tidy_path = Path("scripts/run_clang_tidy_host.sh")
tidy = tidy_path.read_text(encoding="utf-8")
needle = "  src/climate/ClimateCompositeInput.cpp\n"
assert needle in tidy
assert "ClimateSemanticOutput.cpp" not in tidy
tidy = tidy.replace(needle, needle + "  src/climate/ClimateSemanticOutput.cpp\n", 1)
tidy_path.write_text(tidy, encoding="utf-8")

plan_path = Path("docs/CONTINUATION_PLAN.md")
plan = plan_path.read_text(encoding="utf-8")
old = '''### Stage26B — hardware-ready semantic output layer

Introduce configuration/mapping beneath `ClimateRoleDriver` for the six stable semantic actuator
roles. Keep endpoint implementations fake and normalized; test disabled capabilities, OFF,
partial rejection and deterministic role mapping. Do not add GPIO/PWM/relay/Shelly code yet.
'''
new = '''### Stage26B completed — hardware-ready semantic output layer

A hardware-neutral `MappedClimateRoleDriver` now maps the six stable semantic roles to configured
endpoint identifiers beneath the existing `ClimateRoleDriver` seam. Endpoint writes always receive
finite normalized levels. Enabled mappings propagate explicit OFF writes; disabled/unmapped roles
accept OFF without I/O but reject nonzero commands, making capability/config mismatches fail visibly.
Host fakes cover deterministic role mapping, OFF, disabled mappings, normalization and partial
endpoint rejection. No physical output backend, bus or pin dependency is introduced.
'''
assert old in plan
plan_path.write_text(plan.replace(old, new, 1), encoding="utf-8")

status_path = Path("docs/CURRENT_STATUS.md")
status = status_path.read_text(encoding="utf-8")
marker = "## Not integrated yet\n"
assert marker in status
paragraph = (
    "Stage26B adds a hardware-neutral semantic output mapping beneath `ClimateRoleDriver`. "
    "`MappedClimateRoleDriver` maps the six stable roles to configured endpoint identifiers and "
    "forwards only finite normalized levels. Enabled mappings propagate explicit OFF writes; "
    "disabled/unmapped roles accept OFF without I/O and reject nonzero commands. Host fakes prove "
    "deterministic mapping and partial rejection without adding a physical output backend.\n\n"
)
assert paragraph not in status
status_path.write_text(status.replace(marker, paragraph + marker, 1), encoding="utf-8")
