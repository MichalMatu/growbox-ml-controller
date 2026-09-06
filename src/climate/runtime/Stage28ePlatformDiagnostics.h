#pragma once

#include "climate/runtime/Stage28eDiagnosticsCore.h"

#include <esp_heap_caps.h>
#include <esp_random.h>
#include <esp_system.h>
#include <esp_timer.h>

#include <cstdint>

namespace growbox::app::climate_io::runtime {

inline HeapRegionMetrics sampleHeapRegionMetrics(std::uint32_t caps) noexcept {
  HeapRegionMetrics metrics{};
  metrics.total_bytes = static_cast<std::uint32_t>(heap_caps_get_total_size(caps));
  metrics.free_bytes = static_cast<std::uint32_t>(heap_caps_get_free_size(caps));
  metrics.minimum_free_bytes = static_cast<std::uint32_t>(heap_caps_get_minimum_free_size(caps));
  metrics.largest_free_block_bytes =
      static_cast<std::uint32_t>(heap_caps_get_largest_free_block(caps));
  return metrics;
}

inline RuntimeMemoryMetrics sampleRuntimeMemoryMetrics() noexcept {
  RuntimeMemoryMetrics metrics{};
  metrics.internal = sampleHeapRegionMetrics(MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT);
  metrics.psram = sampleHeapRegionMetrics(MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
  return metrics;
}

inline BootIdentity captureBootIdentity(const char* firmware_sha) noexcept {
  BootIdentity identity{};
  identity.boot_id = esp_random();
  identity.reset_reason = static_cast<std::int32_t>(esp_reset_reason());
  identity.started_monotonic_us = static_cast<std::uint64_t>(esp_timer_get_time());
  identity.firmware_sha = firmware_sha != nullptr ? firmware_sha : "unknown";
  return identity;
}

} // namespace growbox::app::climate_io::runtime
