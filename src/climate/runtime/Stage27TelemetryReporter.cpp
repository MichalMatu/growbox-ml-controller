#include "climate/runtime/Stage27TelemetryReporter.h"

#include "demo/protocol/HeapDiagnostics.h"

#include <esp_log.h>

#ifndef GROWBOX_FIRMWARE_GIT_SHA
#define GROWBOX_FIRMWARE_GIT_SHA "unknown"
#endif

namespace growbox::app::climate_io::runtime {
namespace {
constexpr char kTag[] = "climate_stage27";
} // namespace

Stage27TelemetryReporter::Stage27TelemetryReporter(native::BleClimateScanner& ble,
                                                   native::Scd41InsideSource& scd41,
                                                   native::Ds3231ClockSource& clock,
                                                   storage::Stage27TelemetryLogger& storage_logger,
                                                   bool storage_logger_ready,
                                                   std::int32_t reset_reason) noexcept
    : ble_(ble), scd41_(scd41), clock_(clock), storage_logger_(storage_logger),
      storage_logger_ready_(storage_logger_ready), reset_reason_(reset_reason) {}

void Stage27TelemetryReporter::record(
    std::uint64_t now_ms, const ::growbox::climate::ClimateLoopResult& loop_result,
    const ::growbox::climate::ClimateRuntimeDecision& decision,
    const Stage27PhysicalOutputSnapshot& physical_outputs) noexcept {
  native::BleClimateReading tp357{};
  native::BleClimateReading xiaomi{};
  const bool tp357_sampled = ble_.sampleTp357(now_ms, tp357);
  const bool xiaomi_sampled = ble_.sampleXiaomi(now_ms, xiaomi);

  InsideEnvironmentSnapshot scd_diag{};
  static_cast<void>(scd41_.sample(now_ms, scd_diag));
  const auto heap = ::growbox::demo::wire::captureHeapSnapshot();
  const auto task = ::growbox::demo::wire::captureTaskSnapshot();

  telemetry::Stage27TelemetrySnapshot snapshot{};
  snapshot.uptime_ms = now_ms;
  snapshot.unix_time_s = clock_.trusted() ? clock_.lastTrustedUnixTimeS() : 0U;
  snapshot.reset_reason = reset_reason_;
  snapshot.input_sampled = loop_result.input_sampled;
  snapshot.io_status = static_cast<std::uint32_t>(loop_result.io_status);
  snapshot.heap_internal = heap.free_internal;
  snapshot.heap_internal_min = heap.min_free_internal;
  snapshot.heap_internal_largest = heap.largest_free_internal;
  snapshot.heap_psram = heap.free_psram;
  snapshot.heap_psram_min = heap.min_free_psram;
  snapshot.heap_psram_largest = heap.largest_free_psram;
  snapshot.stack_free = task.main_stack_free_bytes;

  snapshot.scd_available = scd41_.available();
  snapshot.scd_sample = scd41_.hasMeasurement();
  snapshot.scd_temperature_c =
      scd_diag.air_temperature_c.valid ? scd_diag.air_temperature_c.value : 0.0F;
  snapshot.scd_humidity_pct =
      scd_diag.relative_humidity_pct.valid ? scd_diag.relative_humidity_pct.value : 0.0F;
  snapshot.scd_co2_ppm = scd_diag.co2_ppm.valid ? scd_diag.co2_ppm.value : 0.0F;
  snapshot.scd_age_ms = scd_diag.co2_ppm.valid ? scd_diag.co2_ppm.age_ms : 0U;
  snapshot.scd_read_errors = scd41_.readErrorCount();
  snapshot.scd_invalid = scd41_.invalidMeasurementCount();
  snapshot.scd_samples = scd41_.successfulMeasurementCount();

  snapshot.rtc_available = clock_.available();
  snapshot.rtc_trusted = clock_.trusted();
  snapshot.rtc_reads = clock_.successfulReadCount();
  snapshot.rtc_read_errors = clock_.readErrorCount();
  snapshot.rtc_untrusted = clock_.untrustedReadCount();
  snapshot.rtc_last_success_ms = clock_.lastSuccessfulReadMs();
  snapshot.rtc_last_trusted_ms = clock_.lastTrustedReadMs();

  snapshot.ble_scanning = ble_.scanning();
  snapshot.ble_scan_starts = ble_.scanStartCount();
  snapshot.ble_scan_errors = ble_.scanStartErrorCount();
  snapshot.ble_scan_restarts = ble_.scanRestartCount();
  snapshot.ble_scan_completes = ble_.scanCompleteCount();
  snapshot.ble_adv_lock_drops = ble_.advertisementLockDropCount();

  snapshot.tp_sample = tp357_sampled;
  snapshot.tp_temperature_c = tp357_sampled ? tp357.temperature_c : 0.0F;
  snapshot.tp_humidity_pct = tp357_sampled ? tp357.relative_humidity_pct : 0.0F;
  snapshot.tp_age_ms = tp357_sampled ? tp357.age_ms : 0U;
  snapshot.tp_packets = ble_.tp357PacketCount();
  snapshot.tp_accepted = ble_.tp357AcceptedCount();
  snapshot.tp_rejected = ble_.tp357RejectedCount();

  snapshot.xiaomi_sample = xiaomi_sampled;
  snapshot.xiaomi_temperature_c = xiaomi_sampled ? xiaomi.temperature_c : 0.0F;
  snapshot.xiaomi_humidity_pct = xiaomi_sampled ? xiaomi.relative_humidity_pct : 0.0F;
  snapshot.xiaomi_age_ms = xiaomi_sampled ? xiaomi.age_ms : 0U;
  snapshot.xiaomi_packets = ble_.xiaomiPacketCount();
  snapshot.xiaomi_accepted = ble_.xiaomiAcceptedCount();
  snapshot.xiaomi_rejected = ble_.xiaomiRejectedCount();

  snapshot.runtime_status = static_cast<std::uint32_t>(decision.status);
  snapshot.runtime_mode = static_cast<std::uint32_t>(decision.mode);
  snapshot.rule_arbitration_interventions = decision.rule.arbitration_interventions;
  snapshot.rule_safety_interventions = decision.rule.safety_interventions;
  snapshot.applied_heater = decision.applied.heater;
  snapshot.applied_cooler = decision.applied.cooler;
  snapshot.applied_exhaust_fan = decision.applied.exhaust_fan;
  snapshot.applied_humidifier = decision.applied.humidifier;
  snapshot.applied_dehumidifier = decision.applied.dehumidifier;
  snapshot.applied_co2_doser = decision.applied.co2_doser;

  snapshot.real_outputs_active = physical_outputs.real_outputs_active;
  snapshot.physical_light_on = physical_outputs.light_on;
  snapshot.physical_exhaust_on = physical_outputs.exhaust_on;
  snapshot.physical_humidifier_on = physical_outputs.humidifier_on;

  const auto storage_status = storage_logger_.status();
  logRecord(snapshot, storage_status);
  if (storage_logger_ready_) {
    static_cast<void>(storage_logger_.enqueue(snapshot));
  }
}

void Stage27TelemetryReporter::logRecord(
    const telemetry::Stage27TelemetrySnapshot& snapshot,
    const storage::Stage27StorageStatus& storage_status) noexcept {
  ESP_LOGI(
      kTag,
      "soak_v=2 firmware_sha=%s uptime_ms=%llu reset_reason=%d input_sampled=%d io_status=%u "
      "heap_internal=%u heap_internal_min=%u heap_internal_largest=%u "
      "heap_psram=%u heap_psram_min=%u heap_psram_largest=%u stack_free=%u "
      "scd_available=%d scd_sample=%d scd_t=%.2f scd_rh=%.2f scd_co2=%.0f "
      "scd_age_ms=%llu scd_read_errors=%u scd_invalid=%u scd_samples=%u "
      "rtc_available=%d rtc_trusted=%d rtc_reads=%u rtc_read_errors=%u rtc_untrusted=%u "
      "rtc_last_success_ms=%llu rtc_last_trusted_ms=%llu rtc_unix_time_s=%llu "
      "ble_scanning=%d ble_scan_starts=%u ble_scan_errors=%u ble_scan_restarts=%u "
      "ble_scan_completes=%u ble_adv_lock_drops=%u "
      "tp_sample=%d tp_t=%.2f tp_rh=%.2f tp_age_ms=%llu tp_packets=%u tp_accepted=%u "
      "tp_rejected=%u xiaomi_sample=%d xiaomi_t=%.2f xiaomi_rh=%.2f "
      "xiaomi_age_ms=%llu xiaomi_packets=%u xiaomi_accepted=%u xiaomi_rejected=%u "
      "runtime_status=%u runtime_mode=%u rule_arb=%u rule_safety=%u "
      "applied_heater=%.3f applied_cooler=%.3f applied_fan=%.3f applied_humidifier=%.3f "
      "applied_dehumidifier=%.3f applied_co2=%.3f "
      "physical_light=%d physical_fan=%d physical_humidifier=%d "
      "storage_backend=%s storage_sd_mounted=%d storage_flash_mounted=%d "
      "storage_sd_mount_errors=%u storage_flash_mount_errors=%u storage_write_errors=%u "
      "storage_queue_drops=%u storage_records_written=%u storage_records_skipped=%u "
      "storage_fallbacks=%u storage_sd_recoveries=%u storage_last_write_ms=%llu "
      "sd_mounted=%d sd_mount_errors=%u sd_write_errors=%u sd_queue_drops=%u "
      "sd_records_written=%u sd_records_skipped=%u sd_last_write_ms=%llu outputs=%s",
      GROWBOX_FIRMWARE_GIT_SHA, static_cast<unsigned long long>(snapshot.uptime_ms),
      snapshot.reset_reason, snapshot.input_sampled, snapshot.io_status, snapshot.heap_internal,
      snapshot.heap_internal_min, snapshot.heap_internal_largest, snapshot.heap_psram,
      snapshot.heap_psram_min, snapshot.heap_psram_largest, snapshot.stack_free,
      snapshot.scd_available, snapshot.scd_sample, static_cast<double>(snapshot.scd_temperature_c),
      static_cast<double>(snapshot.scd_humidity_pct), static_cast<double>(snapshot.scd_co2_ppm),
      static_cast<unsigned long long>(snapshot.scd_age_ms), snapshot.scd_read_errors,
      snapshot.scd_invalid, snapshot.scd_samples, snapshot.rtc_available, snapshot.rtc_trusted,
      snapshot.rtc_reads, snapshot.rtc_read_errors, snapshot.rtc_untrusted,
      static_cast<unsigned long long>(snapshot.rtc_last_success_ms),
      static_cast<unsigned long long>(snapshot.rtc_last_trusted_ms),
      static_cast<unsigned long long>(snapshot.unix_time_s), snapshot.ble_scanning,
      snapshot.ble_scan_starts, snapshot.ble_scan_errors, snapshot.ble_scan_restarts,
      snapshot.ble_scan_completes, snapshot.ble_adv_lock_drops, snapshot.tp_sample,
      static_cast<double>(snapshot.tp_temperature_c), static_cast<double>(snapshot.tp_humidity_pct),
      static_cast<unsigned long long>(snapshot.tp_age_ms), snapshot.tp_packets,
      snapshot.tp_accepted, snapshot.tp_rejected, snapshot.xiaomi_sample,
      static_cast<double>(snapshot.xiaomi_temperature_c),
      static_cast<double>(snapshot.xiaomi_humidity_pct),
      static_cast<unsigned long long>(snapshot.xiaomi_age_ms), snapshot.xiaomi_packets,
      snapshot.xiaomi_accepted, snapshot.xiaomi_rejected, snapshot.runtime_status,
      snapshot.runtime_mode, snapshot.rule_arbitration_interventions,
      snapshot.rule_safety_interventions, static_cast<double>(snapshot.applied_heater),
      static_cast<double>(snapshot.applied_cooler),
      static_cast<double>(snapshot.applied_exhaust_fan),
      static_cast<double>(snapshot.applied_humidifier),
      static_cast<double>(snapshot.applied_dehumidifier),
      static_cast<double>(snapshot.applied_co2_doser), snapshot.physical_light_on,
      snapshot.physical_exhaust_on, snapshot.physical_humidifier_on,
      storage::stage27StorageBackendName(storage_status.active_backend), storage_status.sd_mounted,
      storage_status.flash_mounted, storage_status.sd_mount_errors,
      storage_status.flash_mount_errors, storage_status.write_errors, storage_status.queue_drops,
      storage_status.records_written, storage_status.records_skipped,
      storage_status.fallback_activations, storage_status.sd_recoveries,
      static_cast<unsigned long long>(storage_status.last_write_ms), storage_status.sd_mounted,
      storage_status.sd_mount_errors, storage_status.write_errors, storage_status.queue_drops,
      storage_status.records_written, storage_status.records_skipped,
      static_cast<unsigned long long>(storage_status.last_write_ms),
      snapshot.real_outputs_active ? "real-bounded" : "fake-locked");
}

} // namespace growbox::app::climate_io::runtime
