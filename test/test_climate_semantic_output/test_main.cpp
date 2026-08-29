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
