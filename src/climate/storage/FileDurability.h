#pragma once

#include <cstdint>
#include <cstdio>

namespace growbox::app::climate_io::storage {

enum class FileDurabilityStep : std::uint8_t {
  None = 0U,
  Flush,
  Descriptor,
  Sync,
  Stat,
};

struct FileDurabilityResult {
  bool ok{false};
  FileDurabilityStep failed_step{FileDurabilityStep::None};
  int error_number{0};
  std::uint64_t size_bytes{0U};
};

FileDurabilityResult flushSyncAndStat(std::FILE* file) noexcept;
const char* fileDurabilityStepName(FileDurabilityStep step) noexcept;

} // namespace growbox::app::climate_io::storage
