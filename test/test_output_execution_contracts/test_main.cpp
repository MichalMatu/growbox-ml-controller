#include "climate/output/OutputExecution.h"

#include <cassert>
#include <type_traits>

using namespace growbox::app::output;

static_assert(std::is_trivially_copyable_v<OutputCommand>);
static_assert(std::is_trivially_copyable_v<OutputPlan>);
static_assert(std::is_trivially_copyable_v<TxResult>);
static_assert(std::is_trivially_copyable_v<ExecutionStepResult>);
static_assert(std::is_trivially_copyable_v<ExecutionReport>);
static_assert(std::is_trivially_copyable_v<ExecutedControlProjection>);

int main() {
  OutputPlan plan{};
  ExecutionReport report{};
  assert(plan.size == 0U);
  assert(report.size == 0U);

  OutputCommand first{};
  first.endpoint = 2U;
  first.state = BinaryOutputState::On;
  first.sequence = 10U;
  OutputCommand second{};
  second.endpoint = 1U;
  second.state = BinaryOutputState::Off;
  second.sequence = 11U;
  assert(appendOutputCommand(plan, first));
  assert(appendOutputCommand(plan, second));
  assert(plan.size == 2U);
  assert(plan.steps[0].endpoint == 2U);
  assert(plan.steps[1].endpoint == 1U);

  OutputCommand third{}; third.endpoint = 3U;
  assert(appendOutputCommand(plan, third));
  OutputCommand overflow{}; overflow.endpoint = 4U;
  assert(!appendOutputCommand(plan, overflow));
  assert(plan.size == kOutputEndpointCapacity);
  OutputCommand invalid{};
  OutputPlan invalid_plan{};
  assert(!appendOutputCommand(invalid_plan, invalid));
  assert(invalid_plan.size == 0U);

  ExecutionStepResult failed{};
  failed.command = first;
  failed.transport = {TransportStatus::Failed, TransportError::IoFailure};
  failed.physical = PhysicalOutputState::Unknown;
  assert(appendExecutionResult(report, failed));
  assert(report.steps[0].transport.status == TransportStatus::Failed);
  assert(report.steps[0].physical == PhysicalOutputState::Unknown);

  ExecutionStepResult completed{};
  completed.command = second;
  completed.transport = {TransportStatus::Completed, TransportError::None};
  completed.physical = PhysicalOutputState::Unknown;
  assert(appendExecutionResult(report, completed));
  assert(report.size == 2U);
  assert(report.steps[0].transport.status == TransportStatus::Failed);
  assert(report.steps[1].transport.status == TransportStatus::Completed);
  return 0;
}
