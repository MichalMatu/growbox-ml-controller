#include "climate/storage/Stage27FileDurability.h"

#include <cerrno>
#include <sys/stat.h>
#include <unistd.h>

namespace growbox::app::climate_io::storage {

Stage27FileDurabilityResult stage27FlushSyncAndStat(std::FILE* file) noexcept {
  Stage27FileDurabilityResult result{};
  if (file == nullptr) {
    result.failed_step = Stage27FileDurabilityStep::Descriptor;
    result.error_number = EINVAL;
    return result;
  }

  errno = 0;
  if (std::fflush(file) != 0) {
    result.failed_step = Stage27FileDurabilityStep::Flush;
    result.error_number = errno;
    return result;
  }

  errno = 0;
  const int descriptor = ::fileno(file);
  if (descriptor < 0) {
    result.failed_step = Stage27FileDurabilityStep::Descriptor;
    result.error_number = errno;
    return result;
  }

  errno = 0;
  if (::fsync(descriptor) != 0) {
    result.failed_step = Stage27FileDurabilityStep::Sync;
    result.error_number = errno;
    return result;
  }

  struct stat file_stat {};
  errno = 0;
  if (::fstat(descriptor, &file_stat) != 0) {
    result.failed_step = Stage27FileDurabilityStep::Stat;
    result.error_number = errno;
    return result;
  }

  result.ok = true;
  result.size_bytes = file_stat.st_size > 0 ? static_cast<std::uint64_t>(file_stat.st_size) : 0U;
  return result;
}

const char* stage27FileDurabilityStepName(Stage27FileDurabilityStep step) noexcept {
  switch (step) {
  case Stage27FileDurabilityStep::Flush:
    return "fflush";
  case Stage27FileDurabilityStep::Descriptor:
    return "fileno";
  case Stage27FileDurabilityStep::Sync:
    return "fsync";
  case Stage27FileDurabilityStep::Stat:
    return "fstat";
  case Stage27FileDurabilityStep::None:
  default:
    return "none";
  }
}

} // namespace growbox::app::climate_io::storage
