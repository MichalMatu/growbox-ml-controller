#pragma once

#include <cstdint>
#include <cstdio>

namespace growbox::app::climate_io::storage {

enum class Stage27FileDurabilityStep : std::uint8_t {
  None = 0U,
  Flush,
  Descriptor,
  Sync,
  Stat,
};

struct Stage27FileDurabilityResult {
  bool ok{false};
  Stage27FileDurabilityStep failed_step{Stage27FileDurabilityStep::None};
  int error_number{0};
  std::uint64_t size_bytes{0U};
};

Stage27FileDurabilityResult stage27FlushSyncAndStat(std::FILE* file) noexcept;
const char* stage27FileDurabilityStepName(Stage27FileDurabilityStep step) noexcept;

} // namespace growbox::app::climate_io::storage
