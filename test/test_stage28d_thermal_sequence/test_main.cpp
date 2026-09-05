#include "climate/Stage28dThermalTestSequence.h"

#include <cassert>

using namespace growbox::app::climate_io::stage28d;

int main() {
  ThermalTestSequence sequence;
  assert(sequence.sample(0U).phase == ThermalTestPhase::Safe);
  assert(sequence.sample(19'999U).temperature_c == 27.5F);
  assert(sequence.sample(20'000U).phase == ThermalTestPhase::Trip);
  assert(sequence.sample(20'000U).temperature_c == 28.0F);
  assert(sequence.sample(40'000U).phase == ThermalTestPhase::Hot);
  assert(sequence.sample(40'000U).temperature_c == 29.0F);
  assert(sequence.sample(60'000U).phase == ThermalTestPhase::RecoveryAbove);
  assert(sequence.sample(60'000U).temperature_c == 27.0F);
  assert(sequence.sample(80'000U).phase == ThermalTestPhase::RecoveryHold);
  assert(sequence.sample(80'000U).temperature_c == 26.0F);
  assert(!sequence.sample(sequence.completionTimeMs() - 1U).complete);
  assert(sequence.sample(sequence.completionTimeMs()).complete);
  assert(sequence.sample(sequence.completionTimeMs()).scheduled_light_level == 0.0F);
  return 0;
}
