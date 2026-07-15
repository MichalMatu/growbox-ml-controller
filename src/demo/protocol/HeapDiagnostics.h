#pragma once

#include <cstddef>
#include <cstdint>

namespace growbox {
namespace demo {
namespace wire {

struct HeapSnapshot {
  std::size_t total_internal = 0U;
  std::size_t free_internal = 0U;
  std::size_t used_internal = 0U;
  std::size_t min_free_internal = 0U;
  std::size_t largest_free_internal = 0U;
  std::size_t total_psram = 0U;
  std::size_t free_psram = 0U;
  std::size_t used_psram = 0U;
  std::size_t min_free_psram = 0U;
  std::size_t largest_free_psram = 0U;
  bool psram_enabled = false;
};

struct TaskSnapshot {
  std::uint32_t main_stack_free_bytes = 0U;
};

HeapSnapshot captureHeapSnapshot() noexcept;
TaskSnapshot captureTaskSnapshot() noexcept;

}  // namespace wire
}  // namespace demo
}  // namespace growbox