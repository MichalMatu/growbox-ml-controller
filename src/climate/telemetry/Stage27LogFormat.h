#pragma once

#include "climate/storage/Stage27StorageTypes.h"
#include "climate/telemetry/Stage27Telemetry.h"

#include <cstddef>
#include <cstdint>

namespace growbox::app::climate_io::telemetry {

struct Stage27LogSessionMetadata {
  const char* firmware_sha = "unknown";
  std::uint32_t session_id = 0U;
  storage::Stage27StorageBackendKind backend = storage::Stage27StorageBackendKind::None;
  std::int32_t reset_reason = 0;
  std::uint64_t start_uptime_ms = 0U;
  bool rtc_trusted = false;
  std::uint64_t start_unix_time_s = 0U;
};

std::size_t formatStage27SessionNdjson(char* buffer, std::size_t buffer_size,
                                       const Stage27LogSessionMetadata& session) noexcept;

std::size_t formatStage27SampleNdjson(char* buffer, std::size_t buffer_size,
                                      const Stage27TelemetrySnapshot& snapshot) noexcept;

std::size_t formatStage27HealthNdjson(char* buffer, std::size_t buffer_size,
                                      const Stage27TelemetrySnapshot& snapshot,
                                      const storage::Stage27StorageStatus& storage_status) noexcept;

} // namespace growbox::app::climate_io::telemetry
