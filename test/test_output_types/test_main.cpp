#include "climate/application/ClimateSemanticOutput.h"
#include "climate/output/OutputTypes.h"

#include <cassert>
#include <cstdint>
#include <type_traits>

using namespace growbox::app;

static_assert(std::is_same_v<output::OutputEndpointId, std::uint16_t>);
static_assert(std::is_same_v<climate_io::ClimateEndpointId, output::OutputEndpointId>);
static_assert(sizeof(output::OutputEndpointId) == 2U);
static_assert(sizeof(output::BinaryOutputState) == 1U);
static_assert(sizeof(output::OutputSource) == 1U);
static_assert(sizeof(output::SupervisorMode) == 1U);
static_assert(sizeof(output::TransportStatus) == 1U);
static_assert(sizeof(output::TransportError) == 1U);
static_assert(std::is_trivially_copyable_v<output::BinaryOutputState>);
static_assert(std::is_trivially_copyable_v<output::OutputSource>);
static_assert(std::is_trivially_copyable_v<output::SupervisorMode>);
static_assert(std::is_trivially_copyable_v<output::TransportStatus>);
static_assert(std::is_trivially_copyable_v<output::TransportError>);
static_assert(output::kOutputEndpointCapacity == 3U);

int main() {
  assert(!output::isValidOutputEndpoint(output::kInvalidOutputEndpoint));
  assert(output::isValidOutputEndpoint(0U));
  assert(climate_io::kUnmappedClimateEndpoint == output::kInvalidOutputEndpoint);
  return 0;
}
