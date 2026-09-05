#include "climate/telemetry/Stage27LogFormat.h"

#include <cinttypes>
#include <cstdio>

namespace growbox::app::climate_io::telemetry {
namespace {

std::size_t checkedLength(char* buffer, std::size_t buffer_size, int written) noexcept {
  if (buffer == nullptr || buffer_size == 0U || written < 0 ||
      static_cast<std::size_t>(written) >= buffer_size) {
    if (buffer != nullptr && buffer_size > 0U) {
      buffer[0] = '\0';
    }
    return 0U;
  }
  return static_cast<std::size_t>(written);
}

int flag(bool value) noexcept {
  return value ? 1 : 0;
}

} // namespace

std::size_t formatStage27SessionNdjson(char* buffer, std::size_t buffer_size,
                                       const Stage27LogSessionMetadata& session) noexcept {
  if (buffer == nullptr || buffer_size == 0U) {
    return 0U;
  }
  const auto sample_interval_ms = storage::stage27SampleIntervalMs(session.backend);
  const auto health_interval_ms = storage::stage27HealthIntervalMs(session.backend);
  const int written = std::snprintf(
      buffer, buffer_size,
      "{\"t\":\"session\",\"schema\":\"growbox-log-v2\",\"fw\":\"%s\",\"sid\":\"%08" PRIx32
      "\",\"backend\":\"%s\",\"reset\":%" PRId32 ",\"u0\":%" PRIu64 ",\"x0\":%" PRIu64
      ",\"rtc\":%d,\"sample_ms\":%" PRIu64 ",\"health_ms\":%" PRIu64 "}",
      session.firmware_sha != nullptr ? session.firmware_sha : "unknown", session.session_id,
      storage::stage27StorageBackendName(session.backend), session.reset_reason,
      session.start_uptime_ms, session.start_unix_time_s, flag(session.rtc_trusted),
      sample_interval_ms, health_interval_ms);
  return checkedLength(buffer, buffer_size, written);
}

std::size_t formatStage27SampleNdjson(char* buffer, std::size_t buffer_size,
                                      const Stage27TelemetrySnapshot& snapshot) noexcept {
  if (buffer == nullptr || buffer_size == 0U) {
    return 0U;
  }
  const int written = std::snprintf(
      buffer, buffer_size,
      "{\"t\":\"s\",\"v\":2,\"u\":%" PRIu64 ",\"x\":%" PRIu64 ",\"i\":[%d,%" PRIu32
      "],\"scd\":[%d,%d,%.2f,%.2f,%.0f,%" PRIu64 "],"
      "\"tp\":[%d,%.2f,%.2f,%" PRIu64 "],\"xm\":[%d,%.2f,%.2f,%" PRIu64 "],"
      "\"o\":[%d,%d,%d,%d],"
      "\"c\":[%" PRIu32 ",%" PRIu32 ",%" PRIu32 ",%" PRIu32 ",%.3f,%.3f,%.3f,%.3f,%.3f,%.3f]}",
      snapshot.uptime_ms, snapshot.unix_time_s, flag(snapshot.input_sampled), snapshot.io_status,
      flag(snapshot.scd_sample), flag(snapshot.scd_available),
      static_cast<double>(snapshot.scd_temperature_c),
      static_cast<double>(snapshot.scd_humidity_pct), static_cast<double>(snapshot.scd_co2_ppm),
      snapshot.scd_age_ms, flag(snapshot.tp_sample), static_cast<double>(snapshot.tp_temperature_c),
      static_cast<double>(snapshot.tp_humidity_pct), snapshot.tp_age_ms,
      flag(snapshot.xiaomi_sample), static_cast<double>(snapshot.xiaomi_temperature_c),
      static_cast<double>(snapshot.xiaomi_humidity_pct), snapshot.xiaomi_age_ms,
      flag(snapshot.real_outputs_active), flag(snapshot.physical_light_on),
      flag(snapshot.physical_exhaust_on), flag(snapshot.physical_humidifier_on),
      snapshot.runtime_status, snapshot.runtime_mode, snapshot.rule_arbitration_interventions,
      snapshot.rule_safety_interventions, static_cast<double>(snapshot.applied_heater),
      static_cast<double>(snapshot.applied_cooler),
      static_cast<double>(snapshot.applied_exhaust_fan),
      static_cast<double>(snapshot.applied_humidifier),
      static_cast<double>(snapshot.applied_dehumidifier),
      static_cast<double>(snapshot.applied_co2_doser));
  return checkedLength(buffer, buffer_size, written);
}

std::size_t
formatStage27HealthNdjson(char* buffer, std::size_t buffer_size,
                          const Stage27TelemetrySnapshot& snapshot,
                          const storage::Stage27StorageStatus& storage_status) noexcept {
  if (buffer == nullptr || buffer_size == 0U) {
    return 0U;
  }
  const int written = std::snprintf(
      buffer, buffer_size,
      "{\"t\":\"h\",\"v\":2,\"u\":%" PRIu64 ","
      "\"sys\":[%" PRIu32 ",%" PRIu32 ",%" PRIu32 ",%" PRIu32 ",%" PRIu32 ",%" PRIu32 ",%" PRIu32
      "],"
      "\"scd\":[%d,%" PRIu32 ",%" PRIu32 ",%" PRIu32 "],"
      "\"rtc\":[%d,%d,%" PRIu32 ",%" PRIu32 ",%" PRIu32 ",%" PRIu64 ",%" PRIu64 "],"
      "\"ble\":[%d,%" PRIu32 ",%" PRIu32 ",%" PRIu32 ",%" PRIu32 ",%" PRIu32 "],"
      "\"tp\":[%" PRIu32 ",%" PRIu32 ",%" PRIu32 "],"
      "\"xm\":[%" PRIu32 ",%" PRIu32 ",%" PRIu32 "],"
      "\"o\":[%d,%d,%d,%d],"
      "\"st\":[\"%s\",%d,%d,%" PRIu32 ",%" PRIu32 ",%" PRIu32 ",%" PRIu32 ",%" PRIu32 ",%" PRIu32
      ",%" PRIu32 ",%" PRIu32 ",%" PRIu64 "]}",
      snapshot.uptime_ms, snapshot.heap_internal, snapshot.heap_internal_min,
      snapshot.heap_internal_largest, snapshot.heap_psram, snapshot.heap_psram_min,
      snapshot.heap_psram_largest, snapshot.stack_free, flag(snapshot.scd_available),
      snapshot.scd_read_errors, snapshot.scd_invalid, snapshot.scd_samples,
      flag(snapshot.rtc_available), flag(snapshot.rtc_trusted), snapshot.rtc_reads,
      snapshot.rtc_read_errors, snapshot.rtc_untrusted, snapshot.rtc_last_success_ms,
      snapshot.rtc_last_trusted_ms, flag(snapshot.ble_scanning), snapshot.ble_scan_starts,
      snapshot.ble_scan_errors, snapshot.ble_scan_restarts, snapshot.ble_scan_completes,
      snapshot.ble_adv_lock_drops, snapshot.tp_packets, snapshot.tp_accepted, snapshot.tp_rejected,
      snapshot.xiaomi_packets, snapshot.xiaomi_accepted, snapshot.xiaomi_rejected,
      flag(snapshot.real_outputs_active), flag(snapshot.physical_light_on),
      flag(snapshot.physical_exhaust_on), flag(snapshot.physical_humidifier_on),
      storage::stage27StorageBackendName(storage_status.active_backend),
      flag(storage_status.sd_mounted), flag(storage_status.flash_mounted),
      storage_status.sd_mount_errors, storage_status.flash_mount_errors,
      storage_status.write_errors, storage_status.queue_drops, storage_status.records_written,
      storage_status.records_skipped, storage_status.fallback_activations,
      storage_status.sd_recoveries, storage_status.last_write_ms);
  return checkedLength(buffer, buffer_size, written);
}

} // namespace growbox::app::climate_io::telemetry
