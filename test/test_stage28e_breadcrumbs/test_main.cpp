#include "climate/runtime/Stage28eBreadcrumbs.h"

#include <cassert>

using namespace growbox::app::climate_io::runtime;

int main() {
  Stage28eBreadcrumbState state{};
  assert(!stage28eBreadcrumbValid(state));

  state.magic = kStage28eBreadcrumbMagic;
  state.version = kStage28eBreadcrumbVersion;
  state.write_sequence = 7U;
  state.boot_sequence = 3U;
  state.boot_id = 0x12345678U;
  state.reset_reason = 12;
  state.last_log_sequence = 42U;
  state.last_log_uptime_ms = 123456789ULL;
  state.last_log_module = static_cast<std::uint32_t>(DiagnosticLogModule::Watchdog);
  state.last_log_level = static_cast<std::uint32_t>(DiagnosticLogLevel::Info);
  state.last_fault_code = static_cast<std::uint32_t>(Stage28eBreadcrumbFault::ArbiterContinuity);
  state.arbiter_instance_id = 2U;
  state.arbiter_construction_count = 2U;
  state.arbiter_transition_count = 5U;
  state.arbiter_dwell_hold_count = 43U;
  state.arbiter_safety_override_count = 1U;
  state.arbiter_continuity_fault_count = 1U;
  state.checksum = stage28eBreadcrumbChecksum(state);
  assert(stage28eBreadcrumbValid(state));

  const std::uint32_t original_checksum = state.checksum;
  ++state.arbiter_dwell_hold_count;
  assert(!stage28eBreadcrumbValid(state));
  assert(stage28eBreadcrumbChecksum(state) != original_checksum);

  state.arbiter_dwell_hold_count = 43U;
  state.checksum = stage28eBreadcrumbChecksum(state);
  assert(stage28eBreadcrumbValid(state));

  return 0;
}
