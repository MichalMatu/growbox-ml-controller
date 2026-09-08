#include "climate/output/OutputIntents.h"

#include <cassert>
#include <type_traits>

using namespace growbox::app::output;

static_assert(std::is_trivially_copyable_v<IntentMetadata>);
static_assert(std::is_trivially_copyable_v<EndpointIntent>);
static_assert(std::is_trivially_copyable_v<ControlIntent>);
static_assert(std::is_trivially_copyable_v<ScheduleIntent>);
static_assert(std::is_trivially_copyable_v<ManualIntent>);
static_assert(std::is_trivially_copyable_v<SafetyEndpointConstraint>);
static_assert(std::is_trivially_copyable_v<SafetyEnvelope>);
static_assert(std::is_standard_layout_v<SafetyEnvelope>);

int main() {
  ControlIntent control{};
  ScheduleIntent schedule{};
  ManualIntent manual{};
  SafetyEnvelope safety{};
  for (const auto& item : control.endpoints) assert(!endpointIntentActive(item));
  for (const auto& item : schedule.endpoints) assert(!endpointIntentActive(item));
  for (const auto& item : manual.endpoints) assert(!endpointIntentActive(item));
  for (const auto& item : safety.endpoints) assert(!safetyConstraintActive(item));

  EndpointIntent endpoint{};
  assert(!setEndpointIntent(endpoint, kInvalidOutputEndpoint, 1.0F));
  assert(!endpointIntentActive(endpoint));
  assert(setEndpointIntent(endpoint, 1U, 0.5F));
  assert(endpointIntentActive(endpoint));
  assert(endpoint.endpoint == 1U);
  assert(endpoint.level == 0.5F);

  SafetyEndpointConstraint rule{};
  assert(setSafetyConstraint(rule, 2U, SafetyConstraint::ForceOn, OutputReason::ThermalSafety));
  assert(safetyConstraintActive(rule));
  assert(rule.constraint == SafetyConstraint::ForceOn);
  auto copy = rule;
  assert(copy.endpoint == rule.endpoint);
  copy = {};
  assert(!safetyConstraintActive(copy));
  return 0;
}
