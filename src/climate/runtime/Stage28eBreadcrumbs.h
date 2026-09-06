#pragma once

#include "climate/runtime/Stage28eDiagnosticsCore.h"

#include <cstdint>

namespace growbox::app::climate_io::runtime {

constexpr std::uint32_t kStage28eBreadcrumbMagic = 0x53323845U; // "S28E"
constexpr std::uint32_t kStage28eBreadcrumbVersion = 1U;

enum class Stage28eBreadcrumbFault : std::uint32_t {
  None = 0U,
  DiagnosticError = 1U,
  ArbiterContinuity = 2U,
};

struct Stage28eBreadcrumbState {
  std::uint32_t magic{0U};
  std::uint32_t version{0U};
  std::uint32_t checksum{0U};
  std::uint32_t write_sequence{0U};
  std::uint32_t boot_sequence{0U};
  std::uint32_t boot_id{0U};
  std::int32_t reset_reason{0};
  std::uint32_t last_log_sequence{0U};
  std::uint64_t last_log_uptime_ms{0U};
  std::uint32_t last_log_module{0U};
  std::uint32_t last_log_level{0U};
  std::uint32_t last_fault_sequence{0U};
  std::uint64_t last_fault_uptime_ms{0U};
  std::uint32_t last_fault_module{0U};
  std::uint32_t last_fault_level{0U};
  std::uint32_t last_fault_code{0U};
  std::uint64_t last_arbiter_uptime_ms{0U};
  std::uint32_t arbiter_instance_id{0U};
  std::uint32_t arbiter_construction_count{0U};
  std::uint32_t arbiter_transition_count{0U};
  std::uint32_t arbiter_dwell_hold_count{0U};
  std::uint32_t arbiter_safety_override_count{0U};
  std::uint32_t arbiter_continuity_fault_count{0U};
};

constexpr std::uint32_t stage28eBreadcrumbMix32(std::uint32_t hash,
                                                std::uint32_t value) noexcept {
  for (unsigned shift = 0U; shift < 32U; shift += 8U) {
    hash ^= (value >> shift) & 0xFFU;
    hash *= 16777619U;
  }
  return hash;
}

constexpr std::uint32_t stage28eBreadcrumbChecksum(const Stage28eBreadcrumbState& state) noexcept {
  std::uint32_t hash = 2166136261U;
  hash = stage28eBreadcrumbMix32(hash, state.magic);
  hash = stage28eBreadcrumbMix32(hash, state.version);
  hash = stage28eBreadcrumbMix32(hash, state.write_sequence);
  hash = stage28eBreadcrumbMix32(hash, state.boot_sequence);
  hash = stage28eBreadcrumbMix32(hash, state.boot_id);
  hash = stage28eBreadcrumbMix32(hash, static_cast<std::uint32_t>(state.reset_reason));
  hash = stage28eBreadcrumbMix32(hash, state.last_log_sequence);
  hash = stage28eBreadcrumbMix32(hash, static_cast<std::uint32_t>(state.last_log_uptime_ms));
  hash = stage28eBreadcrumbMix32(hash, static_cast<std::uint32_t>(state.last_log_uptime_ms >> 32U));
  hash = stage28eBreadcrumbMix32(hash, state.last_log_module);
  hash = stage28eBreadcrumbMix32(hash, state.last_log_level);
  hash = stage28eBreadcrumbMix32(hash, state.last_fault_sequence);
  hash = stage28eBreadcrumbMix32(hash, static_cast<std::uint32_t>(state.last_fault_uptime_ms));
  hash = stage28eBreadcrumbMix32(hash, static_cast<std::uint32_t>(state.last_fault_uptime_ms >> 32U));
  hash = stage28eBreadcrumbMix32(hash, state.last_fault_module);
  hash = stage28eBreadcrumbMix32(hash, state.last_fault_level);
  hash = stage28eBreadcrumbMix32(hash, state.last_fault_code);
  hash = stage28eBreadcrumbMix32(hash, static_cast<std::uint32_t>(state.last_arbiter_uptime_ms));
  hash = stage28eBreadcrumbMix32(hash, static_cast<std::uint32_t>(state.last_arbiter_uptime_ms >> 32U));
  hash = stage28eBreadcrumbMix32(hash, state.arbiter_instance_id);
  hash = stage28eBreadcrumbMix32(hash, state.arbiter_construction_count);
  hash = stage28eBreadcrumbMix32(hash, state.arbiter_transition_count);
  hash = stage28eBreadcrumbMix32(hash, state.arbiter_dwell_hold_count);
  hash = stage28eBreadcrumbMix32(hash, state.arbiter_safety_override_count);
  hash = stage28eBreadcrumbMix32(hash, state.arbiter_continuity_fault_count);
  return hash;
}

constexpr bool stage28eBreadcrumbValid(const Stage28eBreadcrumbState& state) noexcept {
  return state.magic == kStage28eBreadcrumbMagic &&
         state.version == kStage28eBreadcrumbVersion &&
         state.checksum == stage28eBreadcrumbChecksum(state);
}

Stage28eBreadcrumbState readStage28eBreadcrumb() noexcept;
void beginStage28eBreadcrumb(std::uint32_t boot_id, std::int32_t reset_reason) noexcept;
void recordStage28eBreadcrumbLog(std::uint32_t sequence, std::uint64_t uptime_ms,
                                 DiagnosticLogModule module, DiagnosticLogLevel level) noexcept;
void recordStage28eBreadcrumbArbiter(std::uint64_t uptime_ms, std::uint32_t instance_id,
                                     std::uint32_t construction_count,
                                     std::uint32_t transition_count,
                                     std::uint32_t dwell_hold_count,
                                     std::uint32_t safety_override_count,
                                     std::uint32_t continuity_fault_count,
                                     bool continuity_fault) noexcept;

} // namespace growbox::app::climate_io::runtime
