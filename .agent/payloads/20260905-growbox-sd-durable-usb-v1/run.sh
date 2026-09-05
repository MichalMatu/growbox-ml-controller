#!/usr/bin/env bash
set -euo pipefail
EXPECTED=e744e1fdf430ac35165f61a21f4c4b7fbf8a7e4f
BRANCH=mvp/environment-controller

git fetch -q origin "$BRANCH"
git reset --hard "$EXPECTED" >/dev/null
test "$(git rev-parse HEAD)" = "$EXPECTED"
test "$(git rev-parse origin/$BRANCH)" = "$EXPECTED"
test -z "$(git status --porcelain)"

mkdir -p src/climate/storage test/test_stage27_file_durability scripts

cat > src/climate/storage/Stage27FileDurability.h <<'EOF'
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
EOF

cat > src/climate/storage/Stage27FileDurability.cpp <<'EOF'
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
EOF

python3 - <<'PY'
from pathlib import Path
p=Path('src/climate/storage/Stage27SdStorageBackend.cpp')
s=p.read_text()
s=s.replace('#include "climate/storage/Stage27SdStorageBackend.h"\n', '#include "climate/storage/Stage27SdStorageBackend.h"\n\n#include "climate/storage/Stage27FileDurability.h"\n', 1)
needle='''constexpr std::uint32_t kPowerOnDelayMs = 100U;\n\n} // namespace\n'''
insert='''constexpr std::uint32_t kPowerOnDelayMs = 100U;\n\nbool writeLineDurably(std::FILE* file, const char* data, std::size_t length,\n                      const char* context) noexcept {\n  if (file == nullptr || data == nullptr || length == 0U) {\n    return false;\n  }\n\n  errno = 0;\n  const std::size_t written = std::fwrite(data, 1U, length, file);\n  if (written != length) {\n    const int error_number = errno;\n    ESP_LOGW(kTag, "%s fwrite short write expected=%u actual=%u errno=%d ferror=%d", context,\n             static_cast<unsigned>(length), static_cast<unsigned>(written), error_number,\n             std::ferror(file));\n    return false;\n  }\n  errno = 0;\n  if (std::fputc('\\n', file) == EOF) {\n    ESP_LOGW(kTag, "%s newline write failed errno=%d ferror=%d", context, errno,\n             std::ferror(file));\n    return false;\n  }\n\n  const Stage27FileDurabilityResult durability = stage27FlushSyncAndStat(file);\n  if (!durability.ok) {\n    ESP_LOGW(kTag, "%s durability failed step=%s errno=%d", context,\n             stage27FileDurabilityStepName(durability.failed_step), durability.error_number);\n    return false;\n  }\n  if (durability.size_bytes == 0U) {\n    ESP_LOGW(kTag, "%s durability invariant failed: file size is zero after sync", context);\n    return false;\n  }\n  return true;\n}\n\n} // namespace\n'''
if needle not in s: raise SystemExit('storage namespace insertion target missing')
s=s.replace(needle, insert, 1)
old='''  const std::size_t header_length = std::strlen(session_header);\n  const bool ok = std::fwrite(session_header, 1U, header_length, file_) == header_length &&\n                  std::fputc('\\n', file_) != EOF && std::fflush(file_) == 0;\n  if (!ok) {\n    ESP_LOGW(kTag, "Failed to write SD session header: errno=%d", errno);\n    closeFile();\n    return false;\n  }\n'''
new='''  const std::size_t header_length = std::strlen(session_header);\n  if (!writeLineDurably(file_, session_header, header_length, "session_header")) {\n    closeFile();\n    return false;\n  }\n'''
if old not in s: raise SystemExit('session header write target missing')
s=s.replace(old,new,1)
old='''  const bool ok = std::fwrite(data, 1U, length, file_) == length &&\n                  std::fputc('\\n', file_) != EOF && std::fflush(file_) == 0;\n  if (!ok) {\n    ESP_LOGW(kTag, "SD telemetry write failed: errno=%d", errno);\n  }\n  return ok;\n'''
new='''  return writeLineDurably(file_, data, length, "telemetry_record");\n'''
if old not in s: raise SystemExit('append write target missing')
s=s.replace(old,new,1)
p.write_text(s)
PY

cat > src/climate/runtime/Stage28ServiceConsoleCommand.h <<'EOF'
#pragma once

#include <array>
#include <cstdint>

namespace growbox::app::climate_io::runtime {

enum class ServiceConsoleCommandKind : std::uint8_t {
  None = 0U,
  Help,
  Status,
  Sensors,
  RfList,
  RfTransmit,
  RfReceive,
  RtcSetUnix,
  SdLogStatus,
  SdLogList,
  SdLogRead,
  SdLogSelfTest,
  Invalid,
};

enum class ServiceConsoleRfDevice : std::uint8_t { Lamp = 0U, Fan, Humidifier };
enum class ServiceConsoleRfState : std::uint8_t { Off = 0U, On };

struct ServiceConsoleCommand {
  ServiceConsoleCommandKind kind{ServiceConsoleCommandKind::None};
  ServiceConsoleRfDevice device{ServiceConsoleRfDevice::Lamp};
  ServiceConsoleRfState state{ServiceConsoleRfState::Off};
  std::uint32_t timeout_ms{1000U};
  std::uint64_t unix_time_s{0U};
  std::array<char, 16U> filename{};
  std::uint32_t offset{0U};
  std::uint32_t length{0U};
};

ServiceConsoleCommand parseServiceConsoleCommand(const char* line) noexcept;
const char* serviceConsoleRfDeviceName(ServiceConsoleRfDevice device) noexcept;
const char* serviceConsoleRfStateName(ServiceConsoleRfState state) noexcept;

} // namespace growbox::app::climate_io::runtime
EOF

cat > src/climate/runtime/Stage28ServiceConsoleCommand.cpp <<'EOF'
#include "climate/runtime/Stage28ServiceConsoleCommand.h"

#include <array>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <string_view>

namespace growbox::app::climate_io::runtime {
namespace {

constexpr std::uint32_t kDefaultRxTimeoutMs = 1000U;
constexpr std::uint32_t kMinimumRxTimeoutMs = 50U;
constexpr std::uint32_t kMaximumRxTimeoutMs = 5000U;
constexpr std::uint32_t kMaximumSdReadBytes = 384U;

char lowerAscii(char value) noexcept { return value >= 'A' && value <= 'Z' ? static_cast<char>(value - 'A' + 'a') : value; }
bool equalsIgnoreCase(std::string_view left, std::string_view right) noexcept {
  if (left.size() != right.size()) return false;
  for (std::size_t i=0; i<left.size(); ++i) if (lowerAscii(left[i]) != lowerAscii(right[i])) return false;
  return true;
}
bool isSpace(char value) noexcept { return value == ' ' || value == '\t'; }
std::size_t splitTokens(std::string_view line, std::array<std::string_view, 5U>& tokens) noexcept {
  std::size_t count=0U, cursor=0U;
  while (cursor < line.size()) {
    while (cursor < line.size() && isSpace(line[cursor])) ++cursor;
    if (cursor >= line.size()) break;
    const std::size_t start=cursor;
    while (cursor < line.size() && !isSpace(line[cursor])) ++cursor;
    if (count >= tokens.size()) return tokens.size()+1U;
    tokens[count++] = line.substr(start, cursor-start);
  }
  return count;
}
bool parseUnsigned(std::string_view token, std::uint32_t& output) noexcept {
  if (token.empty()) return false;
  std::uint64_t value=0U;
  for (char c: token) {
    if (c<'0'||c>'9') return false;
    value=value*10U+static_cast<std::uint64_t>(c-'0');
    if (value>std::numeric_limits<std::uint32_t>::max()) return false;
  }
  output=static_cast<std::uint32_t>(value); return true;
}
bool parseUnsigned64(std::string_view token, std::uint64_t& output) noexcept {
  if (token.empty()) return false;
  std::uint64_t value=0U;
  for (char c: token) {
    if (c<'0'||c>'9') return false;
    const auto d=static_cast<std::uint64_t>(c-'0');
    if (value>(std::numeric_limits<std::uint64_t>::max()-d)/10U) return false;
    value=value*10U+d;
  }
  output=value; return true;
}
bool parseDevice(std::string_view token, ServiceConsoleRfDevice& device) noexcept {
  if (equalsIgnoreCase(token,"lamp")) { device=ServiceConsoleRfDevice::Lamp; return true; }
  if (equalsIgnoreCase(token,"fan")) { device=ServiceConsoleRfDevice::Fan; return true; }
  if (equalsIgnoreCase(token,"humidifier")) { device=ServiceConsoleRfDevice::Humidifier; return true; }
  return false;
}
bool parseState(std::string_view token, ServiceConsoleRfState& state) noexcept {
  if (equalsIgnoreCase(token,"on")) { state=ServiceConsoleRfState::On; return true; }
  if (equalsIgnoreCase(token,"off")) { state=ServiceConsoleRfState::Off; return true; }
  return false;
}
bool copyLogFilename(std::string_view token, std::array<char,16U>& output) noexcept {
  if (token.size()!=11U || token[8]!='.' || lowerAscii(token[9])!='j' || lowerAscii(token[10])!='l') return false;
  for (std::size_t i=0; i<8U; ++i) {
    const char c=token[i];
    const bool hex=(c>='0'&&c<='9')||(c>='a'&&c<='f')||(c>='A'&&c<='F');
    if (!hex) return false;
  }
  for (std::size_t i=0; i<token.size(); ++i) output[i]=token[i];
  output[token.size()]='\0';
  return true;
}
ServiceConsoleCommand invalidCommand() noexcept { ServiceConsoleCommand c{}; c.kind=ServiceConsoleCommandKind::Invalid; return c; }

} // namespace

ServiceConsoleCommand parseServiceConsoleCommand(const char* line) noexcept {
  if (line==nullptr) return invalidCommand();
  const std::string_view input(line);
  std::array<std::string_view,5U> tokens{};
  const std::size_t count=splitTokens(input,tokens);
  if (count==0U) return {};
  if (count>tokens.size()) return invalidCommand();

  ServiceConsoleCommand command{};
  if (count==1U) {
    if (equalsIgnoreCase(tokens[0],"help")||equalsIgnoreCase(tokens[0],"menu")||tokens[0]=="?"||tokens[0]=="0") { command.kind=ServiceConsoleCommandKind::Help; return command; }
    if (equalsIgnoreCase(tokens[0],"status")||tokens[0]=="1") { command.kind=ServiceConsoleCommandKind::Status; return command; }
    if (equalsIgnoreCase(tokens[0],"sensors")||tokens[0]=="2") { command.kind=ServiceConsoleCommandKind::Sensors; return command; }
    if (equalsIgnoreCase(tokens[0],"rf")||tokens[0]=="3") { command.kind=ServiceConsoleCommandKind::RfList; return command; }
    return invalidCommand();
  }
  if (count==3U && equalsIgnoreCase(tokens[0],"rtc") && equalsIgnoreCase(tokens[1],"set-unix")) {
    if (!parseUnsigned64(tokens[2],command.unix_time_s)) return invalidCommand();
    command.kind=ServiceConsoleCommandKind::RtcSetUnix; return command;
  }
  if (equalsIgnoreCase(tokens[0],"sdlog")) {
    if (count==2U && equalsIgnoreCase(tokens[1],"status")) { command.kind=ServiceConsoleCommandKind::SdLogStatus; return command; }
    if (count==2U && equalsIgnoreCase(tokens[1],"list")) { command.kind=ServiceConsoleCommandKind::SdLogList; return command; }
    if (count==2U && equalsIgnoreCase(tokens[1],"selftest")) { command.kind=ServiceConsoleCommandKind::SdLogSelfTest; return command; }
    if (count==5U && equalsIgnoreCase(tokens[1],"read")) {
      if (!copyLogFilename(tokens[2],command.filename) || !parseUnsigned(tokens[3],command.offset) || !parseUnsigned(tokens[4],command.length) || command.length==0U || command.length>kMaximumSdReadBytes) return invalidCommand();
      command.kind=ServiceConsoleCommandKind::SdLogRead; return command;
    }
    return invalidCommand();
  }
  if (!equalsIgnoreCase(tokens[0],"rf")) return invalidCommand();
  if (count==2U && equalsIgnoreCase(tokens[1],"list")) { command.kind=ServiceConsoleCommandKind::RfList; return command; }
  if (equalsIgnoreCase(tokens[1],"rx")) {
    if (count==2U) { command.kind=ServiceConsoleCommandKind::RfReceive; command.timeout_ms=kDefaultRxTimeoutMs; return command; }
    if (count==3U) { if (!parseUnsigned(tokens[2],command.timeout_ms)||command.timeout_ms<kMinimumRxTimeoutMs||command.timeout_ms>kMaximumRxTimeoutMs) return invalidCommand(); command.kind=ServiceConsoleCommandKind::RfReceive; return command; }
    return invalidCommand();
  }
  if (count==3U && parseDevice(tokens[1],command.device) && parseState(tokens[2],command.state)) { command.kind=ServiceConsoleCommandKind::RfTransmit; return command; }
  return invalidCommand();
}

const char* serviceConsoleRfDeviceName(ServiceConsoleRfDevice device) noexcept {
  switch(device) { case ServiceConsoleRfDevice::Lamp:return "lamp"; case ServiceConsoleRfDevice::Fan:return "fan"; case ServiceConsoleRfDevice::Humidifier:return "humidifier"; }
  return "unknown";
}
const char* serviceConsoleRfStateName(ServiceConsoleRfState state) noexcept { return state==ServiceConsoleRfState::On ? "on" : "off"; }

} // namespace growbox::app::climate_io::runtime
EOF

python3 - <<'PY'
from pathlib import Path
p=Path('src/climate/runtime/Stage28ServiceConsole.h')
s=p.read_text()
s=s.replace('namespace growbox::app::climate_io::runtime {\n', 'namespace growbox::app::climate_io::storage { class Stage27TelemetryLogger; }\n\nnamespace growbox::app::climate_io::runtime {\n',1)
s=s.replace('''    const bool* real_outputs_active{nullptr};\n''','''    const bool* real_outputs_active{nullptr};\n    const storage::Stage27TelemetryLogger* storage_logger{nullptr};\n''',1)
s=s.replace('''  void handleRtcSetUnix(const ServiceConsoleCommand& command, std::uint64_t now_ms) noexcept;\n''','''  void handleRtcSetUnix(const ServiceConsoleCommand& command, std::uint64_t now_ms) noexcept;\n  void printSdLogStatus() noexcept;\n  void printSdLogList() noexcept;\n  void handleSdLogRead(const ServiceConsoleCommand& command) noexcept;\n  void handleSdLogSelfTest() noexcept;\n''',1)
p.write_text(s)
PY

python3 - <<'PY'
from pathlib import Path
p=Path('src/climate/runtime/Stage28ServiceConsole.cpp')
s=p.read_text()
s=s.replace('#include "climate/runtime/EuropeWarsawTime.h"\n', '#include "climate/runtime/EuropeWarsawTime.h"\n#include "climate/storage/Stage27FileDurability.h"\n#include "climate/storage/Stage27TelemetryLogger.h"\n',1)
s=s.replace('#include <sdkconfig.h>\n', '#include <sdkconfig.h>\n#include <mbedtls/base64.h>\n',1)
s=s.replace('#include <array>\n', '#include <array>\n#include <cerrno>\n#include <dirent.h>\n#include <sys/stat.h>\n',1)
needle='''constexpr int kServiceConsoleTxBufferBytes = 2048;\n\nconst KnownRfDevice* findKnownDevice'''
insert='''constexpr int kServiceConsoleTxBufferBytes = 2048;\nconstexpr char kSdLogDirectory[] = "/sdcard/GBLOG";\nconstexpr char kSdSelfTestPath[] = "/sdcard/GBLOG/.SELFTEST";\nconstexpr std::size_t kSdReadMaxBytes = 384U;\n\nbool isLogFilename(const char* name) noexcept {\n  if (name == nullptr || std::strlen(name) != 11U || name[8] != '.' ||\n      (name[9] != 'J' && name[9] != 'j') || (name[10] != 'L' && name[10] != 'l')) return false;\n  for (std::size_t i=0U; i<8U; ++i) {\n    const char c=name[i];\n    if (!((c>='0'&&c<='9')||(c>='a'&&c<='f')||(c>='A'&&c<='F'))) return false;\n  }\n  return true;\n}\n\nstd::uint32_t crc32(const std::uint8_t* data, std::size_t length) noexcept {\n  std::uint32_t crc=0xFFFFFFFFU;\n  for (std::size_t i=0U; i<length; ++i) {\n    crc ^= data[i];\n    for (unsigned bit=0U; bit<8U; ++bit) crc=(crc>>1U) ^ ((crc&1U)!=0U ? 0xEDB88320U : 0U);\n  }\n  return crc ^ 0xFFFFFFFFU;\n}\n\nconst KnownRfDevice* findKnownDevice'''
if needle not in s: raise SystemExit('service console constants target missing')
s=s.replace(needle,insert,1)
old='''  case ServiceConsoleCommandKind::RtcSetUnix:\n    handleRtcSetUnix(command, now_ms);\n    return;\n  case ServiceConsoleCommandKind::Invalid:\n'''
new='''  case ServiceConsoleCommandKind::RtcSetUnix:\n    handleRtcSetUnix(command, now_ms);\n    return;\n  case ServiceConsoleCommandKind::SdLogStatus:\n    printSdLogStatus();\n    return;\n  case ServiceConsoleCommandKind::SdLogList:\n    printSdLogList();\n    return;\n  case ServiceConsoleCommandKind::SdLogRead:\n    handleSdLogRead(command);\n    return;\n  case ServiceConsoleCommandKind::SdLogSelfTest:\n    handleSdLogSelfTest();\n    return;\n  case ServiceConsoleCommandKind::Invalid:\n'''
if old not in s: raise SystemExit('service switch target missing')
s=s.replace(old,new,1)
old='''  writeText("  rf rx [50..5000]                 capture/decode one RF frame\\r\\n");\n  writeText("RTC stores UTC; lighting schedule converts UTC to Europe/Warsaw.\\r\\n");\n'''
new='''  writeText("  rf rx [50..5000]                 capture/decode one RF frame\\r\\n");\n  writeText("  sdlog status                     SD logger status/counters\\r\\n");\n  writeText("  sdlog list                       list GBLOG/*.JL with sizes\\r\\n");\n  writeText("  sdlog read <file.JL> <off> <n>  read 1..384 bytes as Base64 + CRC32\\r\\n");\n  writeText("  sdlog selftest                   durable write/read/delete SD probe\\r\\n");\n  writeText("RTC stores UTC; lighting schedule converts UTC to Europe/Warsaw.\\r\\n");\n'''
if old not in s: raise SystemExit('help target missing')
s=s.replace(old,new,1)
needle='''void Stage28ServiceConsole::writeText(const char* text) noexcept {\n'''
methods=r'''void Stage28ServiceConsole::printSdLogStatus() noexcept {
  if (config_.storage_logger == nullptr) {
    writeText("sdlog_status available=0 reason=no_storage_logger\r\n");
    return;
  }
  const auto status = config_.storage_logger->status();
  writeFormatted("sdlog_status available=1 active=%s sd_mounted=%d sd_mount_errors=%lu "
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

void Stage28ServiceConsole::printSdLogList() noexcept {
  if (config_.storage_logger == nullptr || !config_.storage_logger->status().sd_mounted) {
    writeText("sdlog_error op=list reason=sd_not_mounted\r\n");
    return;
  }
  DIR* directory = ::opendir(kSdLogDirectory);
  if (directory == nullptr) {
    writeFormatted("sdlog_error op=list reason=opendir errno=%d\r\n", errno);
    return;
  }
  std::uint32_t count=0U;
  while (dirent* entry = ::readdir(directory)) {
    if (!isLogFilename(entry->d_name)) continue;
    char path[80]{};
    std::snprintf(path,sizeof(path),"%s/%s",kSdLogDirectory,entry->d_name);
    struct stat st {};
    if (::stat(path,&st)!=0) continue;
    writeFormatted("sdlog_file name=%s size=%llu\r\n",entry->d_name,
                   static_cast<unsigned long long>(st.st_size));
    ++count;
  }
  ::closedir(directory);
  writeFormatted("sdlog_list_end count=%lu\r\n",static_cast<unsigned long>(count));
}

void Stage28ServiceConsole::handleSdLogRead(const ServiceConsoleCommand& command) noexcept {
  if (config_.storage_logger == nullptr || !config_.storage_logger->status().sd_mounted) {
    writeText("sdlog_error op=read reason=sd_not_mounted\r\n");
    return;
  }
  if (!isLogFilename(command.filename.data()) || command.length==0U || command.length>kSdReadMaxBytes) {
    writeText("sdlog_error op=read reason=invalid_request\r\n");
    return;
  }
  char path[80]{};
  std::snprintf(path,sizeof(path),"%s/%s",kSdLogDirectory,command.filename.data());
  std::FILE* file=std::fopen(path,"rb");
  if (file==nullptr) {
    writeFormatted("sdlog_error op=read reason=open errno=%d\r\n",errno);
    return;
  }
  struct stat st {};
  if (::stat(path,&st)!=0 || static_cast<std::uint64_t>(command.offset)>static_cast<std::uint64_t>(st.st_size)) {
    std::fclose(file);
    writeText("sdlog_error op=read reason=offset\r\n");
    return;
  }
  if (std::fseek(file,static_cast<long>(command.offset),SEEK_SET)!=0) {
    const int e=errno; std::fclose(file); writeFormatted("sdlog_error op=read reason=seek errno=%d\r\n",e); return;
  }
  std::array<std::uint8_t,kSdReadMaxBytes> raw{};
  const std::size_t read=std::fread(raw.data(),1U,command.length,file);
  const bool read_error=std::ferror(file)!=0;
  std::fclose(file);
  if (read_error) { writeFormatted("sdlog_error op=read reason=fread errno=%d\r\n",errno); return; }
  std::array<unsigned char, 520U> encoded{};
  std::size_t encoded_length=0U;
  const int b64=mbedtls_base64_encode(encoded.data(),encoded.size()-1U,&encoded_length,raw.data(),read);
  if (b64!=0 || encoded_length>=encoded.size()) { writeFormatted("sdlog_error op=read reason=base64 code=%d\r\n",b64); return; }
  encoded[encoded_length]='\0';
  const std::uint32_t checksum=crc32(raw.data(),read);
  const std::uint64_t file_size=static_cast<std::uint64_t>(st.st_size);
  writeFormatted("sdlog_chunk name=%s offset=%lu size=%u file_size=%llu eof=%d crc32=%08lX b64=%s\r\n",
                 command.filename.data(),static_cast<unsigned long>(command.offset),
                 static_cast<unsigned>(read),static_cast<unsigned long long>(file_size),
                 static_cast<std::uint64_t>(command.offset)+read>=file_size,
                 static_cast<unsigned long>(checksum),reinterpret_cast<const char*>(encoded.data()));
}

void Stage28ServiceConsole::handleSdLogSelfTest() noexcept {
  if (config_.storage_logger == nullptr || !config_.storage_logger->status().sd_mounted) {
    writeText("sdlog_selftest ok=0 reason=sd_not_mounted\r\n");
    return;
  }
  constexpr char payload[]="growbox-sd-selftest-v1\n";
  std::FILE* file=std::fopen(kSdSelfTestPath,"wb");
  if (file==nullptr) { writeFormatted("sdlog_selftest ok=0 reason=open_write errno=%d\r\n",errno); return; }
  const std::size_t expected=sizeof(payload)-1U;
  if (std::fwrite(payload,1U,expected,file)!=expected) { const int e=errno; std::fclose(file); ::unlink(kSdSelfTestPath); writeFormatted("sdlog_selftest ok=0 reason=write errno=%d\r\n",e); return; }
  const auto durable=storage::stage27FlushSyncAndStat(file);
  std::fclose(file);
  if (!durable.ok || durable.size_bytes!=expected) { ::unlink(kSdSelfTestPath); writeFormatted("sdlog_selftest ok=0 reason=durability step=%s errno=%d size=%llu\r\n",storage::stage27FileDurabilityStepName(durable.failed_step),durable.error_number,static_cast<unsigned long long>(durable.size_bytes)); return; }
  file=std::fopen(kSdSelfTestPath,"rb");
  if (file==nullptr) { ::unlink(kSdSelfTestPath); writeFormatted("sdlog_selftest ok=0 reason=open_read errno=%d\r\n",errno); return; }
  std::array<char,sizeof(payload)> readback{};
  const std::size_t got=std::fread(readback.data(),1U,expected,file);
  std::fclose(file);
  const bool match=got==expected && std::memcmp(readback.data(),payload,expected)==0;
  const int unlink_result=::unlink(kSdSelfTestPath);
  writeFormatted("sdlog_selftest ok=%d size=%llu readback=%d cleanup=%d\r\n",match,
                 static_cast<unsigned long long>(durable.size_bytes),match,unlink_result==0);
}

'''
if needle not in s: raise SystemExit('writeText insertion target missing')
s=s.replace(needle,methods+needle,1)
p.write_text(s)
PY

python3 - <<'PY'
from pathlib import Path
p=Path('src/climate/ClimateV6RealInputRuntime.cpp')
s=p.read_text()
old='''  runtime::Stage28ServiceConsole service_console(\n      {GROWBOX_STAGE28_SERVICE_CONSOLE_ENABLED != 0, GROWBOX_FIRMWARE_GIT_SHA,\n       &real_output_ready},\n      ble, scd41, clock, rf_diagnostics);\n'''
new='''  runtime::Stage28ServiceConsole service_console(\n      {GROWBOX_STAGE28_SERVICE_CONSOLE_ENABLED != 0, GROWBOX_FIRMWARE_GIT_SHA,\n       &real_output_ready, &storage_logger},\n      ble, scd41, clock, rf_diagnostics);\n'''
if old not in s: raise SystemExit('service console constructor target missing')
s=s.replace(old,new,1)
p.write_text(s)
PY

python3 - <<'PY'
from pathlib import Path
p=Path('src/CMakeLists.txt')
s=p.read_text()
s=s.replace('''    wear_levelling\n)\n''','''    wear_levelling\n    mbedtls\n)\n''',1)
s=s.replace('''      "climate/storage/Stage27TelemetryLogger.cpp"\n''','''      "climate/storage/Stage27TelemetryLogger.cpp"\n      "climate/storage/Stage27FileDurability.cpp"\n''',1)
p.write_text(s)
PY

cat > test/test_stage27_file_durability/test_main.cpp <<'EOF'
#include "climate/storage/Stage27FileDurability.h"

#include <cassert>
#include <cstdio>
#include <cstring>
#include <sys/stat.h>
#include <unistd.h>

using namespace growbox::app::climate_io::storage;

int main() {
  char path[]="/tmp/growbox-durable-XXXXXX";
  const int fd=mkstemp(path);
  assert(fd>=0);
  std::FILE* file=fdopen(fd,"w+");
  assert(file!=nullptr);
  constexpr char payload[]="durable-record\n";
  assert(std::fwrite(payload,1U,sizeof(payload)-1U,file)==sizeof(payload)-1U);
  const auto result=stage27FlushSyncAndStat(file);
  assert(result.ok);
  assert(result.failed_step==Stage27FileDurabilityStep::None);
  assert(result.size_bytes==sizeof(payload)-1U);
  struct stat st{};
  assert(::stat(path,&st)==0);
  assert(static_cast<std::size_t>(st.st_size)==sizeof(payload)-1U);
  std::fclose(file);
  assert(::unlink(path)==0);

  const auto invalid=stage27FlushSyncAndStat(nullptr);
  assert(!invalid.ok);
  assert(invalid.failed_step==Stage27FileDurabilityStep::Descriptor);
  return 0;
}
EOF

cat > test/test_stage28_service_console/test_main.cpp <<'EOF'
#include "climate/runtime/Stage28ServiceConsoleCommand.h"
#include <cassert>
#include <cstring>
using namespace growbox::app::climate_io::runtime;
namespace {
void testReadOnlyMenuCommands(){assert(parseServiceConsoleCommand("help").kind==ServiceConsoleCommandKind::Help);assert(parseServiceConsoleCommand("status").kind==ServiceConsoleCommandKind::Status);assert(parseServiceConsoleCommand("sensors").kind==ServiceConsoleCommandKind::Sensors);assert(parseServiceConsoleCommand("rf list").kind==ServiceConsoleCommandKind::RfList);}
void testNamedRfTransmitCommands(){auto c=parseServiceConsoleCommand("rf lamp on");assert(c.kind==ServiceConsoleCommandKind::RfTransmit&&c.device==ServiceConsoleRfDevice::Lamp&&c.state==ServiceConsoleRfState::On);c=parseServiceConsoleCommand("RF FAN OFF");assert(c.kind==ServiceConsoleCommandKind::RfTransmit&&c.device==ServiceConsoleRfDevice::Fan&&c.state==ServiceConsoleRfState::Off);}
void testRfReceiveTimeoutBounds(){auto c=parseServiceConsoleCommand("rf rx");assert(c.kind==ServiceConsoleCommandKind::RfReceive&&c.timeout_ms==1000U);assert(parseServiceConsoleCommand("rf rx 49").kind==ServiceConsoleCommandKind::Invalid);assert(parseServiceConsoleCommand("rf rx 5001").kind==ServiceConsoleCommandKind::Invalid);}
void testRtcSetUnixCommand(){auto c=parseServiceConsoleCommand("rtc set-unix 1788589800");assert(c.kind==ServiceConsoleCommandKind::RtcSetUnix&&c.unix_time_s==1788589800ULL);assert(parseServiceConsoleCommand("rtc set-unix -1").kind==ServiceConsoleCommandKind::Invalid);}
void testSdLogCommands(){assert(parseServiceConsoleCommand("sdlog status").kind==ServiceConsoleCommandKind::SdLogStatus);assert(parseServiceConsoleCommand("sdlog list").kind==ServiceConsoleCommandKind::SdLogList);assert(parseServiceConsoleCommand("sdlog selftest").kind==ServiceConsoleCommandKind::SdLogSelfTest);auto c=parseServiceConsoleCommand("sdlog read B37B41D6.JL 0 384");assert(c.kind==ServiceConsoleCommandKind::SdLogRead);assert(std::strcmp(c.filename.data(),"B37B41D6.JL")==0);assert(c.offset==0U&&c.length==384U);assert(parseServiceConsoleCommand("sdlog read ../secret 0 10").kind==ServiceConsoleCommandKind::Invalid);assert(parseServiceConsoleCommand("sdlog read B37B41D6.JL 0 0").kind==ServiceConsoleCommandKind::Invalid);assert(parseServiceConsoleCommand("sdlog read B37B41D6.JL 0 385").kind==ServiceConsoleCommandKind::Invalid);}
void testInvalidCommandsFailClosed(){assert(parseServiceConsoleCommand(nullptr).kind==ServiceConsoleCommandKind::Invalid);assert(parseServiceConsoleCommand("").kind==ServiceConsoleCommandKind::None);assert(parseServiceConsoleCommand("rf lamp maybe").kind==ServiceConsoleCommandKind::Invalid);assert(parseServiceConsoleCommand("sdlog erase all").kind==ServiceConsoleCommandKind::Invalid);}
}
int main(){testReadOnlyMenuCommands();testNamedRfTransmitCommands();testRfReceiveTimeoutBounds();testRtcSetUnixCommand();testSdLogCommands();testInvalidCommandsFailClosed();return 0;}
EOF

python3 - <<'PY'
from pathlib import Path
p=Path('test/host/CMakeLists.txt')
s=p.read_text()
needle='''add_executable(\n  stage28_service_console_tests\n'''
block='''add_executable(\n  stage27_file_durability_tests\n  "${PROJECT_ROOT}/test/test_stage27_file_durability/test_main.cpp"\n  "${PROJECT_ROOT}/src/climate/storage/Stage27FileDurability.cpp"\n)\ntarget_include_directories(stage27_file_durability_tests PRIVATE "${PROJECT_ROOT}/src")\ntarget_compile_features(stage27_file_durability_tests PRIVATE cxx_std_17)\ntarget_compile_options(stage27_file_durability_tests PRIVATE -Wall -Wextra -Wpedantic)\n\n'''
if needle not in s: raise SystemExit('host target insertion missing')
s=s.replace(needle,block+needle,1)
s=s.replace('''add_test(NAME stage28_service_console_tests COMMAND stage28_service_console_tests)\n''','''add_test(NAME stage27_file_durability_tests COMMAND stage27_file_durability_tests)\nadd_test(NAME stage28_service_console_tests COMMAND stage28_service_console_tests)\n''',1)
p.write_text(s)
PY

cat > scripts/growbox_log_pull.py <<'EOF'
#!/usr/bin/env python3
import argparse, base64, hashlib, os, re, sys, time, zlib
try:
    import serial
    from serial.tools import list_ports
except ImportError:
    print("pyserial is required: python3 -m pip install pyserial", file=sys.stderr); raise SystemExit(2)
FILE_RE=re.compile(r"sdlog_file name=([0-9A-Fa-f]{8}\.JL) size=(\d+)")
CHUNK_RE=re.compile(r"sdlog_chunk name=([0-9A-Fa-f]{8}\.JL) offset=(\d+) size=(\d+) file_size=(\d+) eof=(\d) crc32=([0-9A-Fa-f]{8}) b64=(\S*)")

def choose_port(explicit):
    if explicit: return explicit
    ports=list(list_ports.comports())
    preferred=[p.device for p in ports if any(x in p.device.lower() for x in ('usb','acm','serial','modem'))]
    if len(preferred)==1: return preferred[0]
    if not preferred: raise SystemExit('No likely USB serial port found; pass --port')
    raise SystemExit('Multiple USB serial ports found; pass --port: '+', '.join(preferred))

class Console:
    def __init__(self, port, baud, timeout):
        self.ser=serial.Serial(port, baudrate=baud, timeout=0.2, write_timeout=2)
        self.deadline=timeout
        time.sleep(0.25); self.ser.reset_input_buffer()
    def command_lines(self, command, terminal_prefix):
        self.ser.write((command+'\n').encode()); self.ser.flush(); end=time.monotonic()+self.deadline; lines=[]
        while time.monotonic()<end:
            raw=self.ser.readline()
            if not raw: continue
            line=raw.decode('utf-8','replace').strip()
            if line.startswith('sdlog_error') or line.startswith('sdlog_selftest ok=0'):
                raise RuntimeError(line)
            if line.startswith('sdlog_'): lines.append(line)
            if line.startswith(terminal_prefix): return lines
        raise TimeoutError(f'timeout waiting for {terminal_prefix!r} after {command!r}')
    def status(self):
        lines=self.command_lines('sdlog status','sdlog_status'); return lines[-1]
    def selftest(self):
        lines=self.command_lines('sdlog selftest','sdlog_selftest'); return lines[-1]
    def list_files(self):
        lines=self.command_lines('sdlog list','sdlog_list_end'); out=[]
        for line in lines:
            m=FILE_RE.fullmatch(line)
            if m: out.append((m.group(1),int(m.group(2))))
        return out
    def chunk(self,name,offset,length):
        lines=self.command_lines(f'sdlog read {name} {offset} {length}','sdlog_chunk')
        for line in reversed(lines):
            m=CHUNK_RE.fullmatch(line)
            if m:
                data=base64.b64decode(m.group(7),validate=True)
                if len(data)!=int(m.group(3)): raise RuntimeError('chunk size mismatch')
                if (zlib.crc32(data)&0xffffffff)!=int(m.group(6),16): raise RuntimeError('chunk CRC32 mismatch')
                if int(m.group(2))!=offset: raise RuntimeError('chunk offset mismatch')
                return data,int(m.group(4)),bool(int(m.group(5)))
        raise RuntimeError('missing sdlog_chunk response')

def pull(console,name,expected_size,outdir):
    os.makedirs(outdir,exist_ok=True); partial=os.path.join(outdir,name+'.partial'); final=os.path.join(outdir,name)
    offset=os.path.getsize(partial) if os.path.exists(partial) else 0
    if offset>expected_size: os.remove(partial); offset=0
    mode='ab' if offset else 'wb'
    with open(partial,mode) as f:
        while offset<expected_size:
            data,file_size,eof=console.chunk(name,offset,min(384,expected_size-offset))
            if file_size<expected_size: raise RuntimeError(f'{name}: board size shrank {file_size} < {expected_size}')
            if not data: raise RuntimeError(f'{name}: zero-length chunk at {offset}')
            f.write(data); f.flush(); os.fsync(f.fileno()); offset+=len(data)
    if offset!=expected_size: raise RuntimeError(f'{name}: final size {offset} != {expected_size}')
    os.replace(partial,final)
    digest=hashlib.sha256(open(final,'rb').read()).hexdigest()
    print(f'pulled {name} size={expected_size} sha256={digest}')

def main():
    ap=argparse.ArgumentParser(description='Read Growbox GBLOG files over the service-console USB serial link')
    ap.add_argument('action',choices=['status','list','selftest','pull','pull-all'])
    ap.add_argument('name',nargs='?'); ap.add_argument('--port'); ap.add_argument('--baud',type=int,default=115200); ap.add_argument('--timeout',type=float,default=5.0); ap.add_argument('--out',default='growbox-logs')
    args=ap.parse_args(); port=choose_port(args.port); c=Console(port,args.baud,args.timeout)
    if args.action=='status': print(c.status()); return
    if args.action=='selftest': print(c.selftest()); return
    files=c.list_files()
    if args.action=='list':
        for name,size in files: print(f'{name}\t{size}')
        return
    selected=files
    if args.action=='pull':
        if not args.name: raise SystemExit('pull requires filename')
        selected=[x for x in files if x[0].lower()==args.name.lower()]
        if not selected: raise SystemExit(f'{args.name}: not listed by board')
    for name,size in selected: pull(c,name,size,args.out)
if __name__=='__main__': main()
EOF
chmod +x scripts/growbox_log_pull.py

# Focused software verification only; no hardware access.
rm -rf build/host-sd-durable-v1 build/idf-sd-durable-v1
cmake -S test/host -B build/host-sd-durable-v1 -DCMAKE_BUILD_TYPE=Debug >/tmp/sd-durable-host-cmake.log
cmake --build build/host-sd-durable-v1 --target stage27_file_durability_tests stage28_service_console_tests --parallel 1
./build/host-sd-durable-v1/stage27_file_durability_tests
./build/host-sd-durable-v1/stage28_service_console_tests
python3 -m py_compile scripts/growbox_log_pull.py
GROWBOX_RF433_LOOPBACK_ENABLED=0 GROWBOX_STAGE28_REAL_OUTPUTS_ENABLED=0 GROWBOX_STAGE28_THERMAL_TEST_SEQUENCE_ENABLED=0 GROWBOX_FIRMWARE_GIT_SHA=sd-durable-v1 STAGE27C_BUILD_DIR=build/idf-sd-durable-v1 bash scripts/stage27c_crowpanel.sh build
git diff --check

git add src/climate/storage/Stage27FileDurability.h src/climate/storage/Stage27FileDurability.cpp src/climate/storage/Stage27SdStorageBackend.cpp src/climate/runtime/Stage28ServiceConsoleCommand.h src/climate/runtime/Stage28ServiceConsoleCommand.cpp src/climate/runtime/Stage28ServiceConsole.h src/climate/runtime/Stage28ServiceConsole.cpp src/climate/ClimateV6RealInputRuntime.cpp src/CMakeLists.txt test/test_stage27_file_durability/test_main.cpp test/test_stage28_service_console/test_main.cpp test/host/CMakeLists.txt scripts/growbox_log_pull.py
git commit -m "Make SD telemetry durable and exportable over USB"
git push origin HEAD:"$BRANCH"
echo "SD_DURABLE_USB_V1_COMPLETE commit=$(git rev-parse HEAD) real_outputs=0 rf_tx=0 hardware=untouched"
