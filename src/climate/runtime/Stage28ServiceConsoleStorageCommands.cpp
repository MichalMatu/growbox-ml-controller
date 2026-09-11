#include "climate/runtime/Stage28ServiceConsoleStorageCommands.h"

#include "climate/storage/Stage27FileDurability.h"
#include "climate/storage/Stage27TelemetryLogger.h"

#include <array>
#include <cerrno>
#include <cstdio>
#include <cstring>
#include <dirent.h>
#include <sys/stat.h>
#include <unistd.h>
#include <mbedtls/base64.h>

namespace growbox::app::climate_io::runtime {
namespace {
constexpr char kSdLogDirectory[] = "/sdcard/GBLOG";
constexpr char kSdSelfTestPath[] = "/sdcard/GBLOG/STEST.TMP";
constexpr std::size_t kSdReadMaxBytes = 384U;

bool isLogFilename(const char* name) noexcept {
  if (name == nullptr || std::strlen(name) != 11U || name[8] != '.' ||
      (name[9] != 'J' && name[9] != 'j') || (name[10] != 'L' && name[10] != 'l'))
    return false;
  for (std::size_t i = 0U; i < 8U; ++i) {
    const char c = name[i];
    if (!((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f') || (c >= 'A' && c <= 'F')))
      return false;
  }
  return true;
}

std::uint32_t crc32(const std::uint8_t* data, std::size_t length) noexcept {
  std::uint32_t crc = 0xFFFFFFFFU;
  for (std::size_t i = 0U; i < length; ++i) {
    crc ^= data[i];
    for (unsigned bit = 0U; bit < 8U; ++bit)
      crc = (crc >> 1U) ^ ((crc & 1U) != 0U ? 0xEDB88320U : 0U);
  }
  return crc ^ 0xFFFFFFFFU;
}
} // namespace

bool Stage28ServiceConsoleStorageCommands::handle(const ServiceConsoleCommand& command) noexcept {
  switch (command.kind) {
  case ServiceConsoleCommandKind::SdLogStatus: printSdLogStatus(); return true;
  case ServiceConsoleCommandKind::SdLogList: printSdLogList(); return true;
  case ServiceConsoleCommandKind::SdLogRead: handleSdLogRead(command); return true;
  case ServiceConsoleCommandKind::SdLogSelfTest: handleSdLogSelfTest(); return true;
  default: return false;
  }
}

void Stage28ServiceConsoleStorageCommands::printSdLogStatus() noexcept {
  if (storage_logger_ == nullptr) {
    sink_.writeText("sdlog_status available=0 reason=no_storage_logger\r\n");
    return;
  }
  const auto status = storage_logger_->status();
  sink_.writeFormatted("sdlog_status available=1 active=%s sd_mounted=%d sd_mount_errors=%lu "
                 "write_errors=%lu queue_drops=%lu records_written=%lu records_skipped=%lu "
                 "sd_recoveries=%lu last_write_ms=%llu\r\n",
                 storage::stage27StorageBackendName(status.active_backend), status.sd_mounted,
                 static_cast<unsigned long>(status.sd_mount_errors),
                 static_cast<unsigned long>(status.write_errors),
                 static_cast<unsigned long>(status.queue_drops),
                 static_cast<unsigned long>(status.records_written),
                 static_cast<unsigned long>(status.records_skipped),
                 static_cast<unsigned long>(status.sd_recoveries),
                 static_cast<unsigned long long>(status.last_write_ms));
}

void Stage28ServiceConsoleStorageCommands::printSdLogList() noexcept {
  if (storage_logger_ == nullptr || !storage_logger_->status().sd_mounted) {
    sink_.writeText("sdlog_error op=list reason=sd_not_mounted\r\n");
    return;
  }
  DIR* directory = ::opendir(kSdLogDirectory);
  if (directory == nullptr) {
    sink_.writeFormatted("sdlog_error op=list reason=opendir errno=%d\r\n", errno);
    return;
  }
  std::uint32_t count = 0U;
  while (dirent* entry = ::readdir(directory)) {
    if (!isLogFilename(entry->d_name))
      continue;
    char path[64]{};
    const int path_length =
        std::snprintf(path, sizeof(path), "%s/%.11s", kSdLogDirectory, entry->d_name);
    if (path_length <= 0 || static_cast<std::size_t>(path_length) >= sizeof(path))
      continue;
    struct stat st{};
    if (::stat(path, &st) != 0)
      continue;
    sink_.writeFormatted("sdlog_file name=%s size=%llu\r\n", entry->d_name,
                   static_cast<unsigned long long>(st.st_size));
    ++count;
  }
  ::closedir(directory);
  sink_.writeFormatted("sdlog_list_end count=%lu\r\n", static_cast<unsigned long>(count));
}

void Stage28ServiceConsoleStorageCommands::handleSdLogRead(const ServiceConsoleCommand& command) noexcept {
  if (storage_logger_ == nullptr || !storage_logger_->status().sd_mounted) {
    sink_.writeText("sdlog_error op=read reason=sd_not_mounted\r\n");
    return;
  }
  if (!isLogFilename(command.filename.data()) || command.length == 0U ||
      command.length > kSdReadMaxBytes) {
    sink_.writeText("sdlog_error op=read reason=invalid_request\r\n");
    return;
  }
  char path[64]{};
  const int path_length =
      std::snprintf(path, sizeof(path), "%s/%.11s", kSdLogDirectory, command.filename.data());
  if (path_length <= 0 || static_cast<std::size_t>(path_length) >= sizeof(path)) {
    sink_.writeText("sdlog_error op=read reason=path\r\n");
    return;
  }
  std::FILE* file = std::fopen(path, "rb");
  if (file == nullptr) {
    sink_.writeFormatted("sdlog_error op=read reason=open errno=%d\r\n", errno);
    return;
  }
  struct stat st{};
  if (::stat(path, &st) != 0 ||
      static_cast<std::uint64_t>(command.offset) > static_cast<std::uint64_t>(st.st_size)) {
    std::fclose(file);
    sink_.writeText("sdlog_error op=read reason=offset\r\n");
    return;
  }
  if (std::fseek(file, static_cast<long>(command.offset), SEEK_SET) != 0) {
    const int e = errno;
    std::fclose(file);
    sink_.writeFormatted("sdlog_error op=read reason=seek errno=%d\r\n", e);
    return;
  }
  std::array<std::uint8_t, kSdReadMaxBytes> raw{};
  const std::size_t read = std::fread(raw.data(), 1U, command.length, file);
  const bool read_error = std::ferror(file) != 0;
  std::fclose(file);
  if (read_error) {
    sink_.writeFormatted("sdlog_error op=read reason=fread errno=%d\r\n", errno);
    return;
  }
  std::array<unsigned char, 520U> encoded{};
  std::size_t encoded_length = 0U;
  const int b64 =
      mbedtls_base64_encode(encoded.data(), encoded.size() - 1U, &encoded_length, raw.data(), read);
  if (b64 != 0 || encoded_length >= encoded.size()) {
    sink_.writeFormatted("sdlog_error op=read reason=base64 code=%d\r\n", b64);
    return;
  }
  encoded[encoded_length] = '\0';
  const std::uint32_t checksum = crc32(raw.data(), read);
  const std::uint64_t file_size = static_cast<std::uint64_t>(st.st_size);
  sink_.writeFormatted(
      "sdlog_chunk name=%s offset=%lu size=%u file_size=%llu eof=%d crc32=%08lX b64=%s\r\n",
      command.filename.data(), static_cast<unsigned long>(command.offset),
      static_cast<unsigned>(read), static_cast<unsigned long long>(file_size),
      static_cast<std::uint64_t>(command.offset) + read >= file_size,
      static_cast<unsigned long>(checksum), reinterpret_cast<const char*>(encoded.data()));
}

void Stage28ServiceConsoleStorageCommands::handleSdLogSelfTest() noexcept {
  if (storage_logger_ == nullptr || !storage_logger_->status().sd_mounted) {
    sink_.writeText("sdlog_selftest ok=0 reason=sd_not_mounted\r\n");
    return;
  }
  constexpr char payload[] = "growbox-sd-selftest-v1\n";
  std::FILE* file = std::fopen(kSdSelfTestPath, "wb");
  if (file == nullptr) {
    sink_.writeFormatted("sdlog_selftest ok=0 reason=open_write errno=%d\r\n", errno);
    return;
  }
  const std::size_t expected = sizeof(payload) - 1U;
  if (std::fwrite(payload, 1U, expected, file) != expected) {
    const int e = errno;
    std::fclose(file);
    ::unlink(kSdSelfTestPath);
    sink_.writeFormatted("sdlog_selftest ok=0 reason=write errno=%d\r\n", e);
    return;
  }
  const auto durable = storage::stage27FlushSyncAndStat(file);
  std::fclose(file);
  if (!durable.ok || durable.size_bytes != expected) {
    ::unlink(kSdSelfTestPath);
    sink_.writeFormatted("sdlog_selftest ok=0 reason=durability step=%s errno=%d size=%llu\r\n",
                   storage::stage27FileDurabilityStepName(durable.failed_step),
                   durable.error_number, static_cast<unsigned long long>(durable.size_bytes));
    return;
  }
  file = std::fopen(kSdSelfTestPath, "rb");
  if (file == nullptr) {
    ::unlink(kSdSelfTestPath);
    sink_.writeFormatted("sdlog_selftest ok=0 reason=open_read errno=%d\r\n", errno);
    return;
  }
  std::array<char, sizeof(payload)> readback{};
  const std::size_t got = std::fread(readback.data(), 1U, expected, file);
  std::fclose(file);
  const bool match = got == expected && std::memcmp(readback.data(), payload, expected) == 0;
  const int unlink_result = ::unlink(kSdSelfTestPath);
  sink_.writeFormatted("sdlog_selftest ok=%d size=%llu readback=%d cleanup=%d\r\n", match,
                 static_cast<unsigned long long>(durable.size_bytes), match, unlink_result == 0);
}

} // namespace growbox::app::climate_io::runtime
