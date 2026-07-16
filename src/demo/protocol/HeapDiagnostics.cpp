#include "HeapDiagnostics.h"

#include <esp_heap_caps.h>
#include <sdkconfig.h>

#include <freertos/FreeRTOS.h>
#include <freertos/task.h>

namespace growbox {
namespace demo {
namespace wire {

HeapSnapshot captureHeapSnapshot() noexcept {
  HeapSnapshot snapshot{};
  snapshot.total_internal = heap_caps_get_total_size(MALLOC_CAP_INTERNAL);
  snapshot.total_psram = heap_caps_get_total_size(MALLOC_CAP_SPIRAM);
  snapshot.psram_enabled = snapshot.total_psram > 0U;
  snapshot.free_internal = heap_caps_get_free_size(MALLOC_CAP_INTERNAL);
  snapshot.free_psram = heap_caps_get_free_size(MALLOC_CAP_SPIRAM);
  snapshot.min_free_internal = heap_caps_get_minimum_free_size(MALLOC_CAP_INTERNAL);
  snapshot.min_free_psram = heap_caps_get_minimum_free_size(MALLOC_CAP_SPIRAM);
  snapshot.largest_free_internal = heap_caps_get_largest_free_block(MALLOC_CAP_INTERNAL);
  snapshot.largest_free_psram = heap_caps_get_largest_free_block(MALLOC_CAP_SPIRAM);
  if (snapshot.total_internal > snapshot.free_internal) {
    snapshot.used_internal = snapshot.total_internal - snapshot.free_internal;
  }
  if (snapshot.total_psram > snapshot.free_psram) {
    snapshot.used_psram = snapshot.total_psram - snapshot.free_psram;
  }
  return snapshot;
}

TaskSnapshot captureTaskSnapshot() noexcept {
  TaskSnapshot snapshot{};
  snapshot.main_stack_size_bytes = static_cast<std::uint32_t>(CONFIG_ESP_MAIN_TASK_STACK_SIZE);
  const UBaseType_t words = uxTaskGetStackHighWaterMark(nullptr);
  snapshot.main_stack_free_bytes =
      static_cast<std::uint32_t>(words) * static_cast<std::uint32_t>(sizeof(StackType_t));
  return snapshot;
}

} // namespace wire
} // namespace demo
} // namespace growbox
