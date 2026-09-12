#include "climate/storage/FileDurability.h"

#include <cerrno>
#include <sys/stat.h>
#include <unistd.h>

namespace growbox::app::climate_io::storage {

FileDurabilityResult flushSyncAndStat(std::FILE* file) noexcept {
  FileDurabilityResult result{};
  if (file == nullptr) {
    result.failed_step = FileDurabilityStep::Descriptor;
    result.error_number = EINVAL;
    return result;
  }

  errno = 0;
  if (std::fflush(file) != 0) {
    result.failed_step = FileDurabilityStep::Flush;
    result.error_number = errno;
    return result;
  }

  errno = 0;
  const int descriptor = ::fileno(file);
  if (descriptor < 0) {
    result.failed_step = FileDurabilityStep::Descriptor;
    result.error_number = errno;
    return result;
  }

  errno = 0;
  if (::fsync(descriptor) != 0) {
    result.failed_step = FileDurabilityStep::Sync;
    result.error_number = errno;
    return result;
  }

  struct stat file_stat{};
  errno = 0;
  if (::fstat(descriptor, &file_stat) != 0) {
    result.failed_step = FileDurabilityStep::Stat;
    result.error_number = errno;
    return result;
  }

  result.ok = true;
  result.size_bytes = file_stat.st_size > 0 ? static_cast<std::uint64_t>(file_stat.st_size) : 0U;
  return result;
}

const char* fileDurabilityStepName(FileDurabilityStep step) noexcept {
  switch (step) {
  case FileDurabilityStep::Flush:
    return "fflush";
  case FileDurabilityStep::Descriptor:
    return "fileno";
  case FileDurabilityStep::Sync:
    return "fsync";
  case FileDurabilityStep::Stat:
    return "fstat";
  case FileDurabilityStep::None:
  default:
    return "none";
  }
}

} // namespace growbox::app::climate_io::storage
