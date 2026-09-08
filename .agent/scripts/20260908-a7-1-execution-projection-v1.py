from pathlib import Path

EXPECTED = '282d977f8b3d8ca6f062a8eb7660e2f5e9cb2e25'


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text()
    count = text.count(old)
    assert count == 1, f'{path}: expected one match, got {count}'
    path.write_text(text.replace(old, new, 1))

execution_h = Path('src/climate/output/OutputExecution.h')
replace_once(
    execution_h,
    '''struct ExecutedControlProjection {\n  std::array<EndpointIntent, kOutputEndpointCapacity> endpoints{};\n};\n''',
    '''struct ExecutedEndpointProjection {\n  OutputEndpointId endpoint = kInvalidOutputEndpoint;\n  bool has_executed_state = false;\n  BinaryOutputState executed_state = BinaryOutputState::Off;\n  bool attempted = false;\n  TxResult transport{};\n  bool held_by_dwell = false;\n  OutputSource source = OutputSource::None;\n  OutputReason reason = OutputReason::None;\n};\n\nstruct ExecutedControlProjection {\n  std::array<ExecutedEndpointProjection, kOutputEndpointCapacity> endpoints{};\n  std::uint8_t size = 0U;\n};\n'''
)

Path('src/climate/output/OutputExecutionProjection.h').write_text(r'''#pragma once

#include "climate/output/OutputSupervisorResolver.h"

namespace growbox::app::output {

bool buildExecutedControlProjection(const OutputSupervisorResolution& resolution,
                                    const ExecutionReport& report,
                                    const OutputStateStore& state_store,
                                    ExecutedControlProjection& output) noexcept;

const ExecutedEndpointProjection*
findExecutedEndpointProjection(const ExecutedControlProjection& projection,
                               OutputEndpointId endpoint) noexcept;

} // namespace growbox::app::output
''')

Path('src/climate/output/OutputExecutionProjection.cpp').write_text(r'''#include "climate/output/OutputExecutionProjection.h"

#include <cstddef>

namespace growbox::app::output {
namespace {

const OutputSupervisorEndpointResolution*
findResolution(const OutputSupervisorResolution& resolution, OutputEndpointId endpoint) noexcept {
  const OutputSupervisorEndpointResolution* found = nullptr;
  for (std::size_t index = 0U; index < resolution.endpoint_count; ++index) {
    if (resolution.endpoints[index].endpoint != endpoint) {
      continue;
    }
    if (found != nullptr) {
      return nullptr;
    }
    found = &resolution.endpoints[index];
  }
  return found;
}

const ExecutionStepResult* findReportStep(const ExecutionReport& report,
                                          OutputEndpointId endpoint,
                                          bool& duplicate) noexcept {
  duplicate = false;
  const ExecutionStepResult* found = nullptr;
  for (std::size_t index = 0U; index < report.size; ++index) {
    if (report.steps[index].command.endpoint != endpoint) {
      continue;
    }
    if (found != nullptr) {
      duplicate = true;
      return nullptr;
    }
    found = &report.steps[index];
  }
  return found;
}

bool resolutionEndpointsUnique(const OutputSupervisorResolution& resolution) noexcept {
  for (std::size_t index = 0U; index < resolution.endpoint_count; ++index) {
    const auto endpoint = resolution.endpoints[index].endpoint;
    if (!isValidOutputEndpoint(endpoint)) {
      return false;
    }
    for (std::size_t previous = 0U; previous < index; ++previous) {
      if (resolution.endpoints[previous].endpoint == endpoint) {
        return false;
      }
    }
  }
  return true;
}

} // namespace

bool buildExecutedControlProjection(const OutputSupervisorResolution& resolution,
                                    const ExecutionReport& report,
                                    const OutputStateStore& state_store,
                                    ExecutedControlProjection& output) noexcept {
  output = {};
  if (!state_store.valid() || resolution.endpoint_count > kOutputEndpointCapacity ||
      report.size > kOutputEndpointCapacity || !resolutionEndpointsUnique(resolution)) {
    return false;
  }

  for (std::size_t report_index = 0U; report_index < report.size; ++report_index) {
    const auto& step = report.steps[report_index];
    if (!outputCommandValid(step.command)) {
      return false;
    }
    const auto* endpoint_resolution = findResolution(resolution, step.command.endpoint);
    if (endpoint_resolution == nullptr || !endpoint_resolution->has_resolved_state ||
        endpoint_resolution->resolved_state != step.command.state) {
      return false;
    }
  }

  for (std::size_t index = 0U; index < resolution.endpoint_count; ++index) {
    const auto& endpoint_resolution = resolution.endpoints[index];
    const auto* state = state_store.find(endpoint_resolution.endpoint);
    if (state == nullptr || !state->configured) {
      output = {};
      return false;
    }

    ExecutedEndpointProjection endpoint{};
    endpoint.endpoint = endpoint_resolution.endpoint;
    endpoint.held_by_dwell = endpoint_resolution.held_by_dwell;
    endpoint.source = endpoint_resolution.source;
    endpoint.reason = endpoint_resolution.reason;

    bool duplicate_report = false;
    const auto* report_step = findReportStep(report, endpoint.endpoint, duplicate_report);
    if (duplicate_report) {
      output = {};
      return false;
    }
    if (report_step != nullptr) {
      endpoint.attempted = true;
      endpoint.transport = report_step->transport;
    }

    if (state->has_successful_command) {
      endpoint.has_executed_state = true;
      endpoint.executed_state = state->last_successful_command.state;
    }

    output.endpoints[output.size] = endpoint;
    ++output.size;
  }
  return true;
}

const ExecutedEndpointProjection*
findExecutedEndpointProjection(const ExecutedControlProjection& projection,
                               OutputEndpointId endpoint) noexcept {
  if (!isValidOutputEndpoint(endpoint) || projection.size > kOutputEndpointCapacity) {
    return nullptr;
  }
  for (std::size_t index = 0U; index < projection.size; ++index) {
    if (projection.endpoints[index].endpoint == endpoint) {
      return &projection.endpoints[index];
    }
  }
  return nullptr;
}

} // namespace growbox::app::output
''')

sink_cpp = Path('src/climate/output/ClimateOutputSupervisorSink.cpp')
replace_once(
    sink_cpp,
    '#include "climate/output/ClimateOutputSupervisorSink.h"\n',
    '#include "climate/output/ClimateOutputSupervisorSink.h"\n\n#include "climate/output/OutputExecutionProjection.h"\n'
)
old_projection = '''bool ClimateOutputSupervisorSink::projectExecutedClimate(\n    ::growbox::climate::ClimatePolicyRequest& projection) const noexcept {\n  projection = {};\n  if (config_status_ != ClimateSemanticOutputConfigStatus::Ok || !state_store_.valid()) {\n    return false;\n  }\n\n  for (const auto role : kClimateRoles) {\n    const std::size_t role_index = climateRoleIndex(role);\n    if (role_index >= climate_config_.roles.size()) {\n      projection = {};\n      return false;\n    }\n    const auto& mapping = climate_config_.roles[role_index];\n    if (!mapping.enabled) {\n      continue;\n    }\n    const auto* state = state_store_.find(mapping.endpoint);\n    if (state == nullptr) {\n      projection = {};\n      return false;\n    }\n    float level = 0.0F;\n    if (state->has_successful_command) {\n      level = state->last_successful_command.state ==\n                      ::growbox::app::output::BinaryOutputState::On\n                  ? 1.0F\n                  : 0.0F;\n    }\n    setRoleLevel(projection, role, level);\n  }\n  return true;\n}\n'''
new_projection = '''bool ClimateOutputSupervisorSink::projectExecutedClimate(\n    ::growbox::climate::ClimatePolicyRequest& projection) const noexcept {\n  projection = {};\n  if (config_status_ != ClimateSemanticOutputConfigStatus::Ok) {\n    return false;\n  }\n\n  ::growbox::app::output::ExecutedControlProjection executed{};\n  if (!::growbox::app::output::buildExecutedControlProjection(\n          last_resolution_, last_report_, state_store_, executed)) {\n    return false;\n  }\n\n  for (const auto role : kClimateRoles) {\n    const std::size_t role_index = climateRoleIndex(role);\n    if (role_index >= climate_config_.roles.size()) {\n      projection = {};\n      return false;\n    }\n    const auto& mapping = climate_config_.roles[role_index];\n    if (!mapping.enabled) {\n      continue;\n    }\n    const auto* endpoint = ::growbox::app::output::findExecutedEndpointProjection(\n        executed, mapping.endpoint);\n    if (endpoint == nullptr || !endpoint->has_executed_state) {\n      projection = {};\n      return false;\n    }\n    const float level = endpoint->executed_state ==\n                                ::growbox::app::output::BinaryOutputState::On\n                            ? 1.0F\n                            : 0.0F;\n    setRoleLevel(projection, role, level);\n  }\n  return true;\n}\n'''
replace_once(sink_cpp, old_projection, new_projection)

src_cmake = Path('src/CMakeLists.txt')
replace_once(
    src_cmake,
    '    "climate/output/OutputStateStore.cpp"\n',
    '    "climate/output/OutputStateStore.cpp"\n    "climate/output/OutputExecutionProjection.cpp"\n'
)

host_cmake = Path('test/host/CMakeLists.txt')
replace_once(
    host_cmake,
    '''target_compile_options(output_supervisor_executor_tests PRIVATE -Wall -Wextra -Wpedantic)\n\nadd_executable(\n  climate_output_supervisor_sink_tests\n''',
    '''target_compile_options(output_supervisor_executor_tests PRIVATE -Wall -Wextra -Wpedantic)\n\nadd_executable(\n  output_execution_projection_tests\n  "${PROJECT_ROOT}/test/test_output_execution_projection/test_main.cpp"\n  "${PROJECT_ROOT}/src/climate/output/OutputExecutionProjection.cpp"\n  "${PROJECT_ROOT}/src/climate/output/OutputStateStore.cpp"\n)\ntarget_include_directories(output_execution_projection_tests PRIVATE "${PROJECT_ROOT}/src")\ntarget_compile_features(output_execution_projection_tests PRIVATE cxx_std_17)\ntarget_compile_options(output_execution_projection_tests PRIVATE -Wall -Wextra -Wpedantic)\n\nadd_executable(\n  climate_output_supervisor_sink_tests\n'''
)
replace_once(
    host_cmake,
    '  "${PROJECT_ROOT}/src/climate/output/ClimateOutputSupervisorSink.cpp"\n',
    '  "${PROJECT_ROOT}/src/climate/output/ClimateOutputSupervisorSink.cpp"\n  "${PROJECT_ROOT}/src/climate/output/OutputExecutionProjection.cpp"\n'
)
replace_once(
    host_cmake,
    'add_test(NAME output_supervisor_executor_tests COMMAND output_supervisor_executor_tests)\n',
    'add_test(NAME output_supervisor_executor_tests COMMAND output_supervisor_executor_tests)\nadd_test(NAME output_execution_projection_tests COMMAND output_execution_projection_tests)\n'
)

Path('test/test_output_execution_projection').mkdir(parents=True, exist_ok=True)
Path('test/test_output_execution_projection/test_main.cpp').write_text(r'''#include "climate/output/OutputExecutionProjection.h"

#include <array>
#include <cassert>
#include <cstdint>

using namespace growbox::app::output;

namespace {

constexpr OutputEndpointId kEndpoint = 41U;
constexpr OutputEndpointId kOtherEndpoint = 42U;

OutputStateStore configuredStore() {
  OutputStateStore store{};
  const std::array<OutputEndpointId, kOutputEndpointCapacity> endpoints{kEndpoint, kOtherEndpoint,
                                                                        43U};
  assert(store.configure(endpoints, endpoints.size()));
  return store;
}

OutputSupervisorResolution resolutionFor(BinaryOutputState resolved_state,
                                         bool held_by_dwell = false) {
  OutputSupervisorResolution resolution{};
  resolution.endpoint_count = 1U;
  auto& endpoint = resolution.endpoints[0];
  endpoint.endpoint = kEndpoint;
  endpoint.has_selected_input = true;
  endpoint.requested_level = resolved_state == BinaryOutputState::On ? 1.0F : 0.0F;
  endpoint.source = OutputSource::Climate;
  endpoint.reason = OutputReason::ClimateDecision;
  endpoint.sequence = 7U;
  endpoint.has_resolved_state = true;
  endpoint.resolved_state = resolved_state;
  endpoint.held_by_dwell = held_by_dwell;
  return resolution;
}

OutputCommand command(BinaryOutputState state, std::uint64_t sequence = 7U) {
  OutputCommand output{};
  output.endpoint = kEndpoint;
  output.state = state;
  output.source = OutputSource::Climate;
  output.reason = OutputReason::ClimateDecision;
  output.sequence = sequence;
  return output;
}

void testSuccessfulCommandProjectsCommandTruthNotPhysicalObservation() {
  auto store = configuredStore();
  const auto on = command(BinaryOutputState::On);
  assert(store.recordAttempt(on, 100U, {TransportStatus::Completed, TransportError::None}));
  assert(store.recordPhysicalObservation(kEndpoint, PhysicalOutputState::Off, 101U, 1U));

  const auto resolution = resolutionFor(BinaryOutputState::On);
  ExecutionReport report{};
  assert(appendExecutionResult(
      report, {on, {TransportStatus::Completed, TransportError::None}, PhysicalOutputState::Unknown}));

  ExecutedControlProjection projection{};
  assert(buildExecutedControlProjection(resolution, report, store, projection));
  assert(projection.size == 1U);
  const auto* endpoint = findExecutedEndpointProjection(projection, kEndpoint);
  assert(endpoint != nullptr);
  assert(endpoint->has_executed_state);
  assert(endpoint->executed_state == BinaryOutputState::On);
  assert(endpoint->attempted);
  assert(endpoint->transport.status == TransportStatus::Completed);
  assert(!endpoint->held_by_dwell);
}

void testFailedAttemptKeepsPreviousSuccessfulState() {
  auto store = configuredStore();
  const auto off = command(BinaryOutputState::Off, 1U);
  const auto on = command(BinaryOutputState::On, 2U);
  assert(store.recordAttempt(off, 10U, {TransportStatus::Completed, TransportError::None}));
  assert(store.recordAttempt(on, 20U, {TransportStatus::Failed, TransportError::IoFailure}));
  assert(store.recordPhysicalObservation(kEndpoint, PhysicalOutputState::On, 21U, 2U));

  const auto resolution = resolutionFor(BinaryOutputState::On);
  ExecutionReport report{};
  assert(appendExecutionResult(
      report, {on, {TransportStatus::Failed, TransportError::IoFailure}, PhysicalOutputState::Unknown}));

  ExecutedControlProjection projection{};
  assert(buildExecutedControlProjection(resolution, report, store, projection));
  const auto* endpoint = findExecutedEndpointProjection(projection, kEndpoint);
  assert(endpoint != nullptr);
  assert(endpoint->has_executed_state);
  assert(endpoint->executed_state == BinaryOutputState::Off);
  assert(endpoint->attempted);
  assert(endpoint->transport.status == TransportStatus::Failed);
}

void testDwellHoldProjectsHeldSuccessfulStateWithoutAttempt() {
  auto store = configuredStore();
  const auto on = command(BinaryOutputState::On, 3U);
  assert(store.recordAttempt(on, 30U, {TransportStatus::Completed, TransportError::None}));

  const auto resolution = resolutionFor(BinaryOutputState::On, true);
  ExecutionReport report{};
  ExecutedControlProjection projection{};
  assert(buildExecutedControlProjection(resolution, report, store, projection));
  const auto* endpoint = findExecutedEndpointProjection(projection, kEndpoint);
  assert(endpoint != nullptr);
  assert(endpoint->has_executed_state);
  assert(endpoint->executed_state == BinaryOutputState::On);
  assert(!endpoint->attempted);
  assert(endpoint->transport.status == TransportStatus::NotAttempted);
  assert(endpoint->held_by_dwell);
}

void testUnknownCommandTruthRemainsUnknownInsteadOfFabricatingOff() {
  auto store = configuredStore();
  const auto resolution = resolutionFor(BinaryOutputState::Off);
  ExecutionReport report{};
  ExecutedControlProjection projection{};
  assert(buildExecutedControlProjection(resolution, report, store, projection));
  const auto* endpoint = findExecutedEndpointProjection(projection, kEndpoint);
  assert(endpoint != nullptr);
  assert(!endpoint->has_executed_state);
  assert(!endpoint->attempted);
}

void testMalformedReportEndpointIsRejected() {
  auto store = configuredStore();
  const auto resolution = resolutionFor(BinaryOutputState::On);
  ExecutionReport report{};
  auto wrong = command(BinaryOutputState::On);
  wrong.endpoint = kOtherEndpoint;
  assert(appendExecutionResult(
      report, {wrong, {TransportStatus::Completed, TransportError::None}, PhysicalOutputState::Unknown}));

  ExecutedControlProjection projection{};
  assert(!buildExecutedControlProjection(resolution, report, store, projection));
  assert(projection.size == 0U);
}

} // namespace

int main() {
  testSuccessfulCommandProjectsCommandTruthNotPhysicalObservation();
  testFailedAttemptKeepsPreviousSuccessfulState();
  testDwellHoldProjectsHeldSuccessfulStateWithoutAttempt();
  testUnknownCommandTruthRemainsUnknownInsteadOfFabricatingOff();
  testMalformedReportEndpointIsRejected();
  return 0;
}
''')
