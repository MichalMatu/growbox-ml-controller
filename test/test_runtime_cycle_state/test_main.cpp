#include "climate/runtime/RuntimeCycleState.h"

#include <cassert>
#include <cstdint>
#include <limits>

using growbox::app::climate_io::runtime::RuntimeCycleState;

namespace {

void testIntentSequenceSkipsZeroOnWrap() {
  RuntimeCycleState state(std::numeric_limits<std::uint64_t>::max());
  assert(state.nextOutputIntentSequence() == 1U);
  assert(state.outputIntentSequence() == 1U);
}

void testIntentSequenceIncrementsMonotonically() {
  RuntimeCycleState state;
  assert(state.nextOutputIntentSequence() == 1U);
  assert(state.nextOutputIntentSequence() == 2U);
}

void testTelemetryCadenceStartsImmediatelyAndRepeatsEveryTenTicks() {
  RuntimeCycleState state;
  assert(state.telemetryDue());
  for (std::uint32_t tick = 1U; tick < 10U; ++tick) {
    assert(!state.telemetryDue());
  }
  assert(state.telemetryDue());
  assert(state.diagnosticTick() == 11U);
}

} // namespace

int main() {
  testIntentSequenceSkipsZeroOnWrap();
  testIntentSequenceIncrementsMonotonically();
  testTelemetryCadenceStartsImmediatelyAndRepeatsEveryTenTicks();
  return 0;
}
