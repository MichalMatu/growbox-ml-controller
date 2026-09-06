#include "climate/runtime/Stage28eBreadcrumbs.h"

#include <esp_attr.h>

#include <limits>

namespace growbox::app::climate_io::runtime {
namespace {

RTC_NOINIT_ATTR Stage28eBreadcrumbState g_stage28e_breadcrumb{};

std::uint32_t nextSequence(std::uint32_t value) noexcept {
  return value == std::numeric_limits<std::uint32_t>::max() ? 1U : value + 1U;
}

void storeBreadcrumb(Stage28eBreadcrumbState state) noexcept {
  state.magic = kStage28eBreadcrumbMagic;
  state.version = kStage28eBreadcrumbVersion;
  state.checksum = 0U;
  state.checksum = stage28eBreadcrumbChecksum(state);
  g_stage28e_breadcrumb = state;
}

Stage28eBreadcrumbState currentOrEmpty() noexcept {
  const Stage28eBreadcrumbState current = g_stage28e_breadcrumb;
  return stage28eBreadcrumbValid(current) ? current : Stage28eBreadcrumbState{};
}

} // namespace

Stage28eBreadcrumbState readStage28eBreadcrumb() noexcept {
  return g_stage28e_breadcrumb;
}

void beginStage28eBreadcrumb(std::uint32_t boot_id, std::int32_t reset_reason) noexcept {
  const Stage28eBreadcrumbState previous = currentOrEmpty();
  Stage28eBreadcrumbState state{};
  state.write_sequence = stage28eBreadcrumbValid(previous) ? nextSequence(previous.write_sequence) : 1U;
  state.boot_sequence = stage28eBreadcrumbValid(previous) ? nextSequence(previous.boot_sequence) : 1U;
  state.boot_id = boot_id;
  state.reset_reason = reset_reason;
  storeBreadcrumb(state);
}

void recordStage28eBreadcrumbLog(std::uint32_t sequence, std::uint64_t uptime_ms,
                                 DiagnosticLogModule module, DiagnosticLogLevel level) noexcept {
  Stage28eBreadcrumbState state = currentOrEmpty();
  state.write_sequence = nextSequence(state.write_sequence);
  state.last_log_sequence = sequence;
  state.last_log_uptime_ms = uptime_ms;
  state.last_log_module = static_cast<std::uint32_t>(module);
  state.last_log_level = static_cast<std::uint32_t>(level);
  if (level == DiagnosticLogLevel::Error) {
    state.last_fault_sequence = sequence;
    state.last_fault_uptime_ms = uptime_ms;
    state.last_fault_module = static_cast<std::uint32_t>(module);
    state.last_fault_level = static_cast<std::uint32_t>(level);
    state.last_fault_code = static_cast<std::uint32_t>(Stage28eBreadcrumbFault::DiagnosticError);
  }
  storeBreadcrumb(state);
}

void recordStage28eBreadcrumbArbiter(std::uint64_t uptime_ms, std::uint32_t instance_id,
                                     std::uint32_t construction_count,
                                     std::uint32_t transition_count,
                                     std::uint32_t dwell_hold_count,
                                     std::uint32_t safety_override_count,
                                     std::uint32_t continuity_fault_count,
                                     bool continuity_fault) noexcept {
  Stage28eBreadcrumbState state = currentOrEmpty();
  state.write_sequence = nextSequence(state.write_sequence);
  state.last_arbiter_uptime_ms = uptime_ms;
  state.arbiter_instance_id = instance_id;
  state.arbiter_construction_count = construction_count;
  state.arbiter_transition_count = transition_count;
  state.arbiter_dwell_hold_count = dwell_hold_count;
  state.arbiter_safety_override_count = safety_override_count;
  state.arbiter_continuity_fault_count = continuity_fault_count;
  if (continuity_fault) {
    state.last_fault_sequence = state.last_log_sequence;
    state.last_fault_uptime_ms = uptime_ms;
    state.last_fault_module = static_cast<std::uint32_t>(DiagnosticLogModule::Arbiter);
    state.last_fault_level = static_cast<std::uint32_t>(DiagnosticLogLevel::Error);
    state.last_fault_code = static_cast<std::uint32_t>(Stage28eBreadcrumbFault::ArbiterContinuity);
  }
  storeBreadcrumb(state);
}

} // namespace growbox::app::climate_io::runtime
