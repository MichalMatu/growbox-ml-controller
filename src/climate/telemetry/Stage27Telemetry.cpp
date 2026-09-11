#include "climate/telemetry/Stage27Telemetry.h"

#include <cinttypes>
#include <cstdio>

namespace growbox::app::climate_io::telemetry {
namespace {

const char* jsonBool(bool value) noexcept {
  return value ? "true" : "false";
}

} // namespace

std::size_t formatStage27TelemetryNdjson(char* buffer, std::size_t buffer_size,
                                         const Stage27TelemetrySnapshot& snapshot) noexcept {
  if (buffer == nullptr || buffer_size == 0U) {
    return 0U;
  }

  const int written = std::snprintf(
      buffer, buffer_size,
      "{\"type\":\"telemetry\",\"schema\":\"growbox-log-v1\","
      "\"uptime_ms\":%" PRIu64 ",\"unix_time_s\":%" PRIu64 ",\"reset_reason\":%" PRId32 ","
      "\"input_sampled\":%s,\"io_status\":%" PRIu32 ","
      "\"sensors\":{"
      "\"scd41\":{\"sample\":%s,\"available\":%s,\"temperature_c\":%.2f,"
      "\"humidity_pct\":%.2f,\"co2_ppm\":%.0f,\"age_ms\":%" PRIu64 ","
      "\"read_errors\":%" PRIu32 ",\"invalid\":%" PRIu32 ",\"samples\":%" PRIu32 "},"
      "\"tp357\":{\"sample\":%s,\"temperature_c\":%.2f,\"humidity_pct\":%.2f,"
      "\"age_ms\":%" PRIu64 ",\"packets\":%" PRIu32 ",\"accepted\":%" PRIu32
      ",\"rejected\":%" PRIu32 "},"
      "\"xiaomi\":{\"sample\":%s,\"temperature_c\":%.2f,\"humidity_pct\":%.2f,"
      "\"age_ms\":%" PRIu64 ",\"packets\":%" PRIu32 ",\"accepted\":%" PRIu32
      ",\"rejected\":%" PRIu32 "}},"
      "\"rtc\":{\"available\":%s,\"trusted\":%s,\"reads\":%" PRIu32 ","
      "\"read_errors\":%" PRIu32 ",\"untrusted\":%" PRIu32 ",\"last_success_ms\":%" PRIu64
      ",\"last_trusted_ms\":%" PRIu64 "},"
      "\"ble\":{\"scanning\":%s,\"scan_starts\":%" PRIu32 ",\"scan_errors\":%" PRIu32
      ",\"scan_restarts\":%" PRIu32 ",\"scan_completes\":%" PRIu32 ",\"adv_lock_drops\":%" PRIu32
      "},"
      "\"controller\":{\"runtime_status\":%" PRIu32 ",\"runtime_mode\":%" PRIu32 ","
      "\"rule_arbitration_interventions\":%" PRIu32 ",\"rule_safety_interventions\":%" PRIu32
      ",\"applied\":{\"heater\":%.3f,\"cooler\":%.3f,\"exhaust_fan\":%.3f,"
      "\"humidifier\":%.3f,\"dehumidifier\":%.3f,\"co2_doser\":%.3f},"
      "\"outputs\":\"fake-locked\"},"
      "\"system\":{\"heap_internal\":%" PRIu32 ",\"heap_internal_min\":%" PRIu32
      ",\"heap_internal_largest\":%" PRIu32 ",\"heap_psram\":%" PRIu32
      ",\"heap_psram_min\":%" PRIu32 ",\"heap_psram_largest\":%" PRIu32 ",\"stack_free\":%" PRIu32
      "},"
      "\"storage\":{\"mounted\":%s,\"mount_errors\":%" PRIu32 ",\"write_errors\":%" PRIu32
      ",\"queue_drops\":%" PRIu32 ",\"records_written\":%" PRIu32 ",\"records_skipped\":%" PRIu32
      ",\"last_write_ms\":%" PRIu64 "}}",
      snapshot.uptime_ms, snapshot.unix_time_s, snapshot.reset_reason,
      jsonBool(snapshot.input_sampled), snapshot.io_status, jsonBool(snapshot.scd_sample),
      jsonBool(snapshot.scd_available), static_cast<double>(snapshot.scd_temperature_c),
      static_cast<double>(snapshot.scd_humidity_pct), static_cast<double>(snapshot.scd_co2_ppm),
      snapshot.scd_age_ms, snapshot.scd_read_errors, snapshot.scd_invalid, snapshot.scd_samples,
      jsonBool(snapshot.tp_sample), static_cast<double>(snapshot.tp_temperature_c),
      static_cast<double>(snapshot.tp_humidity_pct), snapshot.tp_age_ms, snapshot.tp_packets,
      snapshot.tp_accepted, snapshot.tp_rejected, jsonBool(snapshot.xiaomi_sample),
      static_cast<double>(snapshot.xiaomi_temperature_c),
      static_cast<double>(snapshot.xiaomi_humidity_pct), snapshot.xiaomi_age_ms,
      snapshot.xiaomi_packets, snapshot.xiaomi_accepted, snapshot.xiaomi_rejected,
      jsonBool(snapshot.rtc_available), jsonBool(snapshot.rtc_trusted), snapshot.rtc_reads,
      snapshot.rtc_read_errors, snapshot.rtc_untrusted, snapshot.rtc_last_success_ms,
      snapshot.rtc_last_trusted_ms, jsonBool(snapshot.ble_scanning), snapshot.ble_scan_starts,
      snapshot.ble_scan_errors, snapshot.ble_scan_restarts, snapshot.ble_scan_completes,
      snapshot.ble_adv_lock_drops, snapshot.runtime_status, snapshot.runtime_mode,
      snapshot.rule_arbitration_interventions, snapshot.rule_safety_interventions,
      static_cast<double>(snapshot.applied_heater), static_cast<double>(snapshot.applied_cooler),
      static_cast<double>(snapshot.applied_exhaust_fan),
      static_cast<double>(snapshot.applied_humidifier),
      static_cast<double>(snapshot.applied_dehumidifier),
      static_cast<double>(snapshot.applied_co2_doser), snapshot.heap_internal,
      snapshot.heap_internal_min, snapshot.heap_internal_largest, snapshot.heap_psram,
      snapshot.heap_psram_min, snapshot.heap_psram_largest, snapshot.stack_free,
      jsonBool(snapshot.sd_mounted), snapshot.sd_mount_errors, snapshot.sd_write_errors,
      snapshot.sd_queue_drops, snapshot.sd_records_written, snapshot.sd_records_skipped,
      snapshot.sd_last_write_ms);

  if (written < 0 || static_cast<std::size_t>(written) >= buffer_size) {
    buffer[0] = '\0';
    return 0U;
  }
  return static_cast<std::size_t>(written);
}

} // namespace growbox::app::climate_io::telemetry
