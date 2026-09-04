#!/usr/bin/env bash
set -euo pipefail

EXPECTED=b3e90c92dd39c50c23ed618aba47e9fe8ddf26ec
BRANCH=mvp/environment-controller

test "$(git rev-parse HEAD)" = "$EXPECTED"
git fetch -q origin "$BRANCH"
test "$(git rev-parse origin/$BRANCH)" = "$EXPECTED"
test -z "$(git status --porcelain)"

mkdir -p src/climate/runtime

cat > src/climate/runtime/Stage27RuntimeAdapters.h <<'EOF'
#pragma once

#include "climate/ClimateCompositeInput.h"
#include "climate/native/BleClimateScanner.h"
#include "climate/native/Scd41InsideSource.h"

#include <cstdint>

namespace growbox::app::climate_io::runtime {

class LockedFakeRoleDriver final : public ClimateRoleDriver {
public:
  bool apply(ClimateActuatorRole role, float level,
             std::uint64_t monotonic_ms) noexcept override;
};

class Stage27InsideSource final : public InsideEnvironmentSource {
public:
  Stage27InsideSource(native::BleClimateScanner& ble,
                      native::Scd41InsideSource& scd41) noexcept;

  bool sample(std::uint64_t monotonic_ms,
              InsideEnvironmentSnapshot& output) noexcept override;

private:
  native::BleClimateScanner& ble_;
  native::Scd41InsideSource& scd41_;
};

class Stage27NearbySource final : public OutsideEnvironmentSource {
public:
  explicit Stage27NearbySource(native::BleClimateScanner& ble) noexcept;

  bool sample(std::uint64_t monotonic_ms,
              OutsideEnvironmentSnapshot& output) noexcept override;

private:
  native::BleClimateScanner& ble_;
};

class FixedStage27ScheduleConfigSource final : public ClimateScheduleConfigSource {
public:
  bool resolve(std::uint64_t monotonic_ms,
               const ClimateWallClockSnapshot& clock,
               ClimateScheduleConfigSnapshot& output) noexcept override;
};

::growbox::climate::ClimateRuntimeConfig defaultRuntimeConfig() noexcept;

}  // namespace growbox::app::climate_io::runtime
EOF

cat > src/climate/runtime/Stage27RuntimeAdapters.cpp <<'EOF'
#include "climate/runtime/Stage27RuntimeAdapters.h"

namespace growbox::app::climate_io::runtime {

bool LockedFakeRoleDriver::apply(ClimateActuatorRole, float,
                                 std::uint64_t) noexcept {
  return true;
}

Stage27InsideSource::Stage27InsideSource(native::BleClimateScanner& ble,
                                         native::Scd41InsideSource& scd41) noexcept
    : ble_(ble), scd41_(scd41) {}

bool Stage27InsideSource::sample(std::uint64_t monotonic_ms,
                                 InsideEnvironmentSnapshot& output) noexcept {
  output = {};

  native::BleClimateReading tp357{};
  const bool tp357_sampled = ble_.sampleTp357(monotonic_ms, tp357);
  if (tp357_sampled) {
    output.air_temperature_c = {tp357.temperature_c, true, tp357.age_ms};
    output.relative_humidity_pct = {tp357.relative_humidity_pct, true,
                                    tp357.age_ms};
  }

  InsideEnvironmentSnapshot scd41{};
  if (scd41_.sample(monotonic_ms, scd41) && scd41.co2_ppm.valid) {
    output.co2_ppm = scd41.co2_ppm;
  }

  return tp357_sampled || output.co2_ppm.valid;
}

Stage27NearbySource::Stage27NearbySource(native::BleClimateScanner& ble) noexcept
    : ble_(ble) {}

bool Stage27NearbySource::sample(std::uint64_t monotonic_ms,
                                 OutsideEnvironmentSnapshot& output) noexcept {
  output = {};
  native::BleClimateReading xiaomi{};
  if (!ble_.sampleXiaomi(monotonic_ms, xiaomi)) {
    return false;
  }
  output.air_temperature_c = {xiaomi.temperature_c, true, xiaomi.age_ms};
  output.relative_humidity_pct = {xiaomi.relative_humidity_pct, true,
                                  xiaomi.age_ms};
  return true;
}

bool FixedStage27ScheduleConfigSource::resolve(
    std::uint64_t, const ClimateWallClockSnapshot& clock,
    ClimateScheduleConfigSnapshot& output) noexcept {
  if (!clock.valid) {
    return false;
  }

  output = {};
  output.sensor_timeout_ms = ::growbox::climate::kDefaultSensorTimeoutMs;
  output.humidity_control_mode = ::growbox::climate::HumidityControlMode::Rh;
  output.capabilities.heater = true;
  output.capabilities.cooler = true;
  output.capabilities.exhaust_fan = true;
  output.capabilities.humidifier = true;
  output.capabilities.dehumidifier = true;
  output.capabilities.co2_doser = true;

  const std::uint8_t hour =
      static_cast<std::uint8_t>((clock.unix_time_s / 3600U) % 24U);
  const bool day = hour >= 6U && hour < 22U;
  output.targets.air_temperature_c = day ? 24.5F : 21.5F;
  output.targets.relative_humidity_pct = day ? 58.0F : 65.0F;
  output.targets.air_vpd_kpa = day ? 1.2F : 0.9F;
  output.targets.co2_enabled = day;
  output.targets.co2_ppm = day ? 950.0F : 450.0F;
  output.schedule.light_level = day ? 1.0F : 0.0F;
  return true;
}

::growbox::climate::ClimateRuntimeConfig defaultRuntimeConfig() noexcept {
  ::growbox::climate::ClimateRuntimeConfig config{};
  config.mode = ::growbox::climate::ClimatePolicyMode::Rule;
  config.sensor_timeout_ms = ::growbox::climate::kDefaultSensorTimeoutMs;
  config.timestep_s = 1.0F;
  return config;
}

}  // namespace growbox::app::climate_io::runtime
EOF

cat > src/climate/runtime/Stage27TelemetryReporter.h <<'EOF'
#pragma once

#include "climate/ClimateApplication.h"
#include "climate/ClimateCompositeInput.h"
#include "climate/native/BleClimateScanner.h"
#include "climate/native/Ds3231ClockSource.h"
#include "climate/native/Scd41InsideSource.h"
#include "climate/storage/Stage27TelemetryLogger.h"
#include "climate/telemetry/Stage27Telemetry.h"

#include <cstdint>

namespace growbox::app::climate_io::runtime {

class Stage27TelemetryReporter final {
public:
  Stage27TelemetryReporter(native::BleClimateScanner& ble,
                           native::Scd41InsideSource& scd41,
                           native::Ds3231ClockSource& clock,
                           storage::Stage27TelemetryLogger& storage_logger,
                           bool storage_logger_ready,
                           std::int32_t reset_reason) noexcept;

  void record(std::uint64_t now_ms,
              const ::growbox::climate::ClimateLoopResult& loop_result,
              const ::growbox::climate::ClimateRuntimeDecision& decision) noexcept;

private:
  void logRecord(const telemetry::Stage27TelemetrySnapshot& snapshot,
                 const storage::Stage27StorageStatus& storage_status) noexcept;

  native::BleClimateScanner& ble_;
  native::Scd41InsideSource& scd41_;
  native::Ds3231ClockSource& clock_;
  storage::Stage27TelemetryLogger& storage_logger_;
  bool storage_logger_ready_{false};
  std::int32_t reset_reason_{0};
};

}  // namespace growbox::app::climate_io::runtime
EOF

cat > src/climate/runtime/Stage27TelemetryReporter.cpp <<'EOF'
#include "climate/runtime/Stage27TelemetryReporter.h"

#include "demo/protocol/HeapDiagnostics.h"

#include <esp_log.h>

#ifndef GROWBOX_FIRMWARE_GIT_SHA
#define GROWBOX_FIRMWARE_GIT_SHA "unknown"
#endif

namespace growbox::app::climate_io::runtime {
namespace {
constexpr char kTag[] = "climate_stage27";
}  // namespace

Stage27TelemetryReporter::Stage27TelemetryReporter(
    native::BleClimateScanner& ble, native::Scd41InsideSource& scd41,
    native::Ds3231ClockSource& clock,
    storage::Stage27TelemetryLogger& storage_logger, bool storage_logger_ready,
    std::int32_t reset_reason) noexcept
    : ble_(ble), scd41_(scd41), clock_(clock), storage_logger_(storage_logger),
      storage_logger_ready_(storage_logger_ready), reset_reason_(reset_reason) {}

void Stage27TelemetryReporter::record(
    std::uint64_t now_ms,
    const ::growbox::climate::ClimateLoopResult& loop_result,
    const ::growbox::climate::ClimateRuntimeDecision& decision) noexcept {
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
  snapshot.scd_humidity_pct = scd_diag.relative_humidity_pct.valid
                                  ? scd_diag.relative_humidity_pct.value
                                  : 0.0F;
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
      "storage_backend=%s storage_sd_mounted=%d storage_flash_mounted=%d "
      "storage_sd_mount_errors=%u storage_flash_mount_errors=%u storage_write_errors=%u "
      "storage_queue_drops=%u storage_records_written=%u storage_records_skipped=%u "
      "storage_fallbacks=%u storage_sd_recoveries=%u storage_last_write_ms=%llu "
      "sd_mounted=%d sd_mount_errors=%u sd_write_errors=%u sd_queue_drops=%u "
      "sd_records_written=%u sd_records_skipped=%u sd_last_write_ms=%llu outputs=fake-locked",
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
      static_cast<double>(snapshot.applied_co2_doser),
      storage::stage27StorageBackendName(storage_status.active_backend), storage_status.sd_mounted,
      storage_status.flash_mounted, storage_status.sd_mount_errors,
      storage_status.flash_mount_errors, storage_status.write_errors, storage_status.queue_drops,
      storage_status.records_written, storage_status.records_skipped,
      storage_status.fallback_activations, storage_status.sd_recoveries,
      static_cast<unsigned long long>(storage_status.last_write_ms), storage_status.sd_mounted,
      storage_status.sd_mount_errors, storage_status.write_errors, storage_status.queue_drops,
      storage_status.records_written, storage_status.records_skipped,
      static_cast<unsigned long long>(storage_status.last_write_ms));
}

}  // namespace growbox::app::climate_io::runtime
EOF

cat > src/climate/runtime/Stage28RfDiagnostics.h <<'EOF'
#pragma once

#include "climate/rf433/Rf433RmtLoopback.h"

#include <cstdint>

namespace growbox::app::climate_io::runtime {

struct Stage28RfDiagnosticsConfig {
  bool enabled{false};
  bool passive_capture{false};
  bool auto_smoke{false};
  int tx_gpio{8};
  int rx_gpio{14};
  rf433::FrameConfig smoke{};
  std::uint32_t passive_timeout_ms{750U};
  std::uint32_t smoke_timeout_ms{1'500U};
  std::uint64_t smoke_after_ms{3'000U};
};

class Stage28RfDiagnostics final {
public:
  explicit Stage28RfDiagnostics(Stage28RfDiagnosticsConfig config) noexcept;

  bool begin() noexcept;
  void tick(std::uint64_t now_ms) noexcept;

  bool ready() const noexcept { return ready_; }

private:
  void capturePassive() noexcept;
  void runSmoke() noexcept;

  Stage28RfDiagnosticsConfig config_{};
  rf433::Rf433RmtLoopback loopback_;
  bool ready_{false};
  bool smoke_attempted_{false};
  bool capture_ready_logged_{false};
  std::uint32_t capture_id_{0U};
};

}  // namespace growbox::app::climate_io::runtime
EOF

cat > src/climate/runtime/Stage28RfDiagnostics.cpp <<'EOF'
#include "climate/runtime/Stage28RfDiagnostics.h"

#include <esp_log.h>

#include <cstddef>

namespace growbox::app::climate_io::runtime {
namespace {
constexpr char kTag[] = "climate_stage27";
}  // namespace

Stage28RfDiagnostics::Stage28RfDiagnostics(Stage28RfDiagnosticsConfig config) noexcept
    : config_(config),
      loopback_(rf433::Rf433RmtLoopback::Config{config.tx_gpio, config.rx_gpio}) {}

bool Stage28RfDiagnostics::begin() noexcept {
  ready_ = config_.enabled && loopback_.begin();
  return ready_;
}

void Stage28RfDiagnostics::tick(std::uint64_t now_ms) noexcept {
  if (!ready_) {
    return;
  }

  if (config_.passive_capture) {
    capturePassive();
    return;
  }

  if (config_.auto_smoke && !smoke_attempted_ && now_ms >= config_.smoke_after_ms) {
    runSmoke();
  }
}

void Stage28RfDiagnostics::capturePassive() noexcept {
  if (!capture_ready_logged_) {
    capture_ready_logged_ = true;
    ESP_LOGI(kTag,
             "rf433_remote_capture_ready_v=1 rx_gpio=%d passive_rx_only=1 "
             "outputs=fake-locked",
             config_.rx_gpio);
  }

  rf433::ReceiveEvidence capture{};
  if (!loopback_.receiveOnce(config_.passive_timeout_ms, capture)) {
    return;
  }

  const std::uint32_t capture_id = ++capture_id_;
  ESP_LOGI(
      kTag,
      "rf433_remote_capture_v=1 capture_id=%lu rx_start_ms=%lu rx_finish_ms=%lu "
      "symbol_count=%u overflow=%d decode_status=%u decoded_code=%lu "
      "decoded_bits=%u decoded_protocol=%u estimated_pulse_us=%u "
      "observed_repeats=%u candidate_count=%u outputs=fake-locked",
      static_cast<unsigned long>(capture_id),
      static_cast<unsigned long>(capture.rx_started_at_ms),
      static_cast<unsigned long>(capture.rx_finished_at_ms),
      static_cast<unsigned>(capture.symbol_count), capture.overflow,
      static_cast<unsigned>(capture.decoded.status),
      static_cast<unsigned long>(capture.decoded.frame.code),
      capture.decoded.frame.bit_length, capture.decoded.frame.protocol,
      capture.decoded.estimated_pulse_us, capture.decoded.observed_repeats,
      capture.decoded.candidate_count);

  for (std::size_t i = 0U; i < capture.symbol_count; ++i) {
    const auto& symbol = capture.symbols[i];
    ESP_LOGI(kTag,
             "rf433_remote_symbol_v=1 capture_id=%lu index=%u d0_us=%lu l0=%d "
             "d1_us=%lu l1=%d",
             static_cast<unsigned long>(capture_id), static_cast<unsigned>(i),
             static_cast<unsigned long>(
                 rf433::ticksToMicroseconds(symbol.duration0_ticks)),
             symbol.level0,
             static_cast<unsigned long>(
                 rf433::ticksToMicroseconds(symbol.duration1_ticks)),
             symbol.level1);
  }
}

void Stage28RfDiagnostics::runSmoke() noexcept {
  smoke_attempted_ = true;
  rf433::LoopbackEvidence evidence{};
  const bool passed =
      loopback_.transmitAndReceive(config_.smoke, config_.smoke_timeout_ms, evidence);
  const auto& rf_diag = loopback_.diagnostics();
  const auto& smoke = config_.smoke;

  ESP_LOGI(
      kTag,
      "rf433_loopback_v=1 pass=%d tx_id=%llu requested_code=%lu requested_bits=%u "
      "requested_protocol=%u requested_repeat=%u requested_pulse_us=%u tx_queued=%d "
      "tx_started=%d tx_completed=%d tx_started_ms=%lu tx_completed_ms=%lu "
      "rx_captured=%d rx_start_ms=%lu rx_finish_ms=%lu decode_status=%u "
      "decoded_code=%lu decoded_bits=%u decoded_protocol=%u estimated_pulse_us=%u "
      "observed_repeats=%u classification=%u tx_queue_errors=%lu tx_wait_errors=%lu "
      "rx_arm_errors=%lu rx_timeouts=%lu rx_decode_failures=%lu rx_ambiguous=%lu "
      "rx_self_tx=%lu rx_interference=%lu outputs=fake-locked",
      passed, static_cast<unsigned long long>(evidence.tx_id),
      static_cast<unsigned long>(smoke.key.code), smoke.key.bit_length,
      smoke.key.protocol, smoke.repeat, smoke.pulse_us, evidence.tx_queued,
      evidence.tx_started, evidence.tx_completed,
      static_cast<unsigned long>(evidence.tx_started_at_ms),
      static_cast<unsigned long>(evidence.tx_completed_at_ms), evidence.rx_captured,
      static_cast<unsigned long>(evidence.rx_started_at_ms),
      static_cast<unsigned long>(evidence.rx_finished_at_ms),
      static_cast<unsigned>(evidence.decoded.status),
      static_cast<unsigned long>(evidence.decoded.frame.code),
      evidence.decoded.frame.bit_length, evidence.decoded.frame.protocol,
      evidence.decoded.estimated_pulse_us, evidence.decoded.observed_repeats,
      static_cast<unsigned>(evidence.classification),
      static_cast<unsigned long>(rf_diag.tx_queue_errors),
      static_cast<unsigned long>(rf_diag.tx_wait_errors),
      static_cast<unsigned long>(rf_diag.rx_arm_errors),
      static_cast<unsigned long>(rf_diag.rx_timeouts),
      static_cast<unsigned long>(rf_diag.rx_decode_failures),
      static_cast<unsigned long>(rf_diag.rx_ambiguous),
      static_cast<unsigned long>(rf_diag.rx_self_tx),
      static_cast<unsigned long>(rf_diag.rx_interference));
}

}  // namespace growbox::app::climate_io::runtime
EOF

cat > src/climate/ClimateV6RealInputRuntime.cpp <<'EOF'
#include "climate/ClimateV6RealInputRuntime.h"

#include "climate/ClimateApplication.h"
#include "climate/ClimateCompositeInput.h"
#include "climate/native/BleClimateScanner.h"
#include "climate/native/Ds3231ClockSource.h"
#include "climate/native/NativeI2cBus.h"
#include "climate/native/Scd41InsideSource.h"
#include "climate/runtime/Stage27RuntimeAdapters.h"
#include "climate/runtime/Stage27TelemetryReporter.h"
#include "climate/runtime/Stage28RfDiagnostics.h"
#include "climate/storage/Stage27TelemetryLogger.h"

#include <esp_err.h>
#include <esp_log.h>
#include <esp_system.h>
#include <esp_timer.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>

#include <cstdint>

#ifndef GROWBOX_I2C_SDA_GPIO
#define GROWBOX_I2C_SDA_GPIO 8
#endif
#ifndef GROWBOX_I2C_SCL_GPIO
#define GROWBOX_I2C_SCL_GPIO 9
#endif
#ifndef GROWBOX_BLE_TP357_MAC
#define GROWBOX_BLE_TP357_MAC ""
#endif
#ifndef GROWBOX_BLE_XIAOMI_MAC
#define GROWBOX_BLE_XIAOMI_MAC ""
#endif
#ifndef GROWBOX_FIRMWARE_GIT_SHA
#define GROWBOX_FIRMWARE_GIT_SHA "unknown"
#endif
#ifndef GROWBOX_STAGE27_SD_ENABLED
#define GROWBOX_STAGE27_SD_ENABLED 0
#endif
#ifndef GROWBOX_STAGE27_FLASH_FALLBACK_ENABLED
#define GROWBOX_STAGE27_FLASH_FALLBACK_ENABLED 0
#endif
#ifndef GROWBOX_SD_CMD0_PRECONDITION
#define GROWBOX_SD_CMD0_PRECONDITION 0
#endif
#ifndef GROWBOX_SD_MOSI_GPIO
#define GROWBOX_SD_MOSI_GPIO 40
#endif
#ifndef GROWBOX_SD_MISO_GPIO
#define GROWBOX_SD_MISO_GPIO 13
#endif
#ifndef GROWBOX_SD_SCLK_GPIO
#define GROWBOX_SD_SCLK_GPIO 39
#endif
#ifndef GROWBOX_SD_CS_GPIO
#define GROWBOX_SD_CS_GPIO 10
#endif
#ifndef GROWBOX_SD_POWER_GPIO
#define GROWBOX_SD_POWER_GPIO -1
#endif
#ifndef GROWBOX_RF433_LOOPBACK_ENABLED
#define GROWBOX_RF433_LOOPBACK_ENABLED 0
#endif
#ifndef GROWBOX_RF433_LOOPBACK_AUTO_SMOKE
#define GROWBOX_RF433_LOOPBACK_AUTO_SMOKE 0
#endif
#ifndef GROWBOX_RF433_REMOTE_CAPTURE_ENABLED
#define GROWBOX_RF433_REMOTE_CAPTURE_ENABLED 0
#endif
#ifndef GROWBOX_RF433_LOOPBACK_SMOKE_CODE
#define GROWBOX_RF433_LOOPBACK_SMOKE_CODE 0xA55A
#endif
#ifndef GROWBOX_RF433_LOOPBACK_SMOKE_BITS
#define GROWBOX_RF433_LOOPBACK_SMOKE_BITS 16
#endif
#ifndef GROWBOX_RF433_LOOPBACK_SMOKE_PROTOCOL
#define GROWBOX_RF433_LOOPBACK_SMOKE_PROTOCOL 1
#endif
#ifndef GROWBOX_RF433_LOOPBACK_SMOKE_REPEAT
#define GROWBOX_RF433_LOOPBACK_SMOKE_REPEAT 3
#endif
#ifndef GROWBOX_RF433_LOOPBACK_SMOKE_PULSE_US
#define GROWBOX_RF433_LOOPBACK_SMOKE_PULSE_US 0
#endif
#ifndef GROWBOX_RF433_TX_GPIO
#define GROWBOX_RF433_TX_GPIO 8
#endif
#ifndef GROWBOX_RF433_RX_GPIO
#define GROWBOX_RF433_RX_GPIO 14
#endif

namespace growbox::app::climate_io {
namespace {

constexpr char kTag[] = "climate_stage27";
constexpr std::uint64_t kTickIntervalMs = 1'000U;
constexpr std::uint32_t kTelemetryEveryTicks = 10U;

std::uint64_t monotonicMilliseconds() noexcept {
  return static_cast<std::uint64_t>(esp_timer_get_time()) / 1000U;
}

storage::Stage27TelemetryLogger::Config storageConfig() noexcept {
  storage::Stage27TelemetryLogger::Config config{};
  config.sd_pins = {GROWBOX_SD_MOSI_GPIO, GROWBOX_SD_MISO_GPIO,
                    GROWBOX_SD_SCLK_GPIO, GROWBOX_SD_CS_GPIO,
                    GROWBOX_SD_POWER_GPIO};
  config.sd_enabled = GROWBOX_STAGE27_SD_ENABLED != 0;
  config.flash_fallback_enabled = GROWBOX_STAGE27_FLASH_FALLBACK_ENABLED != 0;
  config.sd_cmd0_precondition = GROWBOX_SD_CMD0_PRECONDITION != 0;
  return config;
}

runtime::Stage28RfDiagnosticsConfig rfDiagnosticsConfig() noexcept {
  runtime::Stage28RfDiagnosticsConfig config{};
  config.enabled = GROWBOX_RF433_LOOPBACK_ENABLED != 0;
  config.passive_capture = GROWBOX_RF433_REMOTE_CAPTURE_ENABLED != 0;
  config.auto_smoke = GROWBOX_RF433_LOOPBACK_AUTO_SMOKE != 0;
  config.tx_gpio = GROWBOX_RF433_TX_GPIO;
  config.rx_gpio = GROWBOX_RF433_RX_GPIO;
  config.smoke = {
      {static_cast<std::uint32_t>(GROWBOX_RF433_LOOPBACK_SMOKE_CODE),
       static_cast<std::uint8_t>(GROWBOX_RF433_LOOPBACK_SMOKE_BITS),
       static_cast<std::uint8_t>(GROWBOX_RF433_LOOPBACK_SMOKE_PROTOCOL)},
      static_cast<std::uint8_t>(GROWBOX_RF433_LOOPBACK_SMOKE_REPEAT),
      static_cast<std::uint16_t>(GROWBOX_RF433_LOOPBACK_SMOKE_PULSE_US)};
  return config;
}

}  // namespace

[[noreturn]] void runClimateV6RealInputRuntime() noexcept {
  native::NativeI2cBus i2c(GROWBOX_I2C_SDA_GPIO, GROWBOX_I2C_SCL_GPIO);
  const bool i2c_ready = i2c.begin() == ESP_OK;
  const esp_err_t scd41_probe =
      i2c_ready ? i2c.probe(0x62U) : ESP_ERR_INVALID_STATE;
  const esp_err_t rtc_probe =
      i2c_ready ? i2c.probe(0x68U) : ESP_ERR_INVALID_STATE;
  ESP_LOGI(kTag, "I2C probe: scd41_0x62=%s ds3231_0x68=%s",
           esp_err_to_name(scd41_probe), esp_err_to_name(rtc_probe));

  native::Scd41InsideSource scd41;
  native::Ds3231ClockSource clock;
  native::BleClimateScanner ble;
  const bool scd41_ready = i2c_ready && scd41.begin(i2c);
  const bool rtc_ready = i2c_ready && clock.begin(i2c);
  const bool ble_ready =
      ble.begin(GROWBOX_BLE_TP357_MAC, GROWBOX_BLE_XIAOMI_MAC);

  const auto storage_config = storageConfig();
  storage::Stage27TelemetryLogger storage_logger(storage_config);
  const bool storage_enabled =
      storage_config.sd_enabled || storage_config.flash_fallback_enabled;
  const bool storage_logger_ready =
      storage_enabled && storage_logger.begin(GROWBOX_FIRMWARE_GIT_SHA);

  runtime::Stage28RfDiagnostics rf_diagnostics(rfDiagnosticsConfig());
  const bool rf_ready = rf_diagnostics.begin();

  runtime::Stage27InsideSource inside(ble, scd41);
  runtime::Stage27NearbySource outside(ble);
  runtime::FixedStage27ScheduleConfigSource schedule_config;
  CompositeClimateSnapshotProvider composite(inside, outside, clock,
                                             schedule_config);
  runtime::LockedFakeRoleDriver output_driver;
  ::growbox::climate::ClimateRuntimeController runtime_controller(
      nullptr, runtime::defaultRuntimeConfig());
  ClimateApplication application(runtime_controller, composite, output_driver);

  const esp_reset_reason_t reset_reason = esp_reset_reason();
  runtime::Stage27TelemetryReporter telemetry_reporter(
      ble, scd41, clock, storage_logger, storage_logger_ready,
      static_cast<std::int32_t>(reset_reason));

  ESP_LOGI(kTag,
           "Stage27 real-input runtime: i2c=%d scd41=%d ds3231=%d ble=%d sd=%d "
           "flash_fallback=%d storage_logger=%d rf433_loopback=%d rf433_tx_gpio=%d "
           "rf433_rx_gpio=%d outputs=fake-locked",
           i2c_ready, scd41_ready, rtc_ready, ble_ready,
           storage_config.sd_enabled, storage_config.flash_fallback_enabled,
           storage_logger_ready, rf_ready, GROWBOX_RF433_TX_GPIO,
           GROWBOX_RF433_RX_GPIO);
  ESP_LOGI(kTag, "Stage27 soak boot: firmware_sha=%s reset_reason=%d",
           GROWBOX_FIRMWARE_GIT_SHA, static_cast<int>(reset_reason));

  std::uint32_t diagnostic_tick = 0U;
  while (true) {
    const std::uint64_t now_ms = monotonicMilliseconds();
    rf_diagnostics.tick(now_ms);

    ::growbox::climate::ClimateRuntimeDecision decision{};
    const auto loop_result = application.tick(now_ms, decision);
    if ((diagnostic_tick++ % kTelemetryEveryTicks) == 0U) {
      telemetry_reporter.record(now_ms, loop_result, decision);
    }

    vTaskDelay(pdMS_TO_TICKS(kTickIntervalMs));
  }
}

}  // namespace growbox::app::climate_io
EOF

python3 - <<'PY'
from pathlib import Path
p=Path('src/CMakeLists.txt')
s=p.read_text()
needle='      "climate/ClimateV6RealInputRuntime.cpp"\n'
addition=(needle +
'      "climate/runtime/Stage27RuntimeAdapters.cpp"\n'
'      "climate/runtime/Stage27TelemetryReporter.cpp"\n'
'      "climate/runtime/Stage28RfDiagnostics.cpp"\n')
assert s.count(needle)==1
s=s.replace(needle, addition)
p.write_text(s)
PY

if command -v clang-format >/dev/null 2>&1; then
  clang-format -i \
    src/climate/ClimateV6RealInputRuntime.cpp \
    src/climate/runtime/Stage27RuntimeAdapters.h \
    src/climate/runtime/Stage27RuntimeAdapters.cpp \
    src/climate/runtime/Stage27TelemetryReporter.h \
    src/climate/runtime/Stage27TelemetryReporter.cpp \
    src/climate/runtime/Stage28RfDiagnostics.h \
    src/climate/runtime/Stage28RfDiagnostics.cpp
fi

runtime_lines=$(wc -l < src/climate/ClimateV6RealInputRuntime.cpp | tr -d ' ')
test "$runtime_lines" -lt 260
! grep -q 'class Stage27InsideSource' src/climate/ClimateV6RealInputRuntime.cpp
! grep -q 'rf433_remote_symbol_v=1' src/climate/ClimateV6RealInputRuntime.cpp
grep -q 'Stage27TelemetryReporter' src/climate/ClimateV6RealInputRuntime.cpp
grep -q 'Stage28RfDiagnostics' src/climate/ClimateV6RealInputRuntime.cpp

cmake -S test/host -B build/host-prestage-runtime-refactor-v1
cmake --build build/host-prestage-runtime-refactor-v1 -j2
ctest --test-dir build/host-prestage-runtime-refactor-v1 --output-on-failure

if [[ -x .venv/bin/python ]]; then
  .venv/bin/python -m pytest tests/test_panel_layout.py -q
fi

export GROWBOX_FIRMWARE_GIT_SHA="$EXPECTED"
export GROWBOX_RF433_LOOPBACK_ENABLED=1
export GROWBOX_RF433_LOOPBACK_AUTO_SMOKE=0
export GROWBOX_RF433_REMOTE_CAPTURE_ENABLED=0
export STAGE27C_BUILD_DIR=build/idf-prestage-runtime-refactor-v1
scripts/stage27c_crowpanel.sh build

git diff --check
test -n "$(git status --porcelain)"

git add src/CMakeLists.txt src/climate/ClimateV6RealInputRuntime.cpp src/climate/runtime
git commit -m "Refactor real-input runtime responsibilities"
NEW=$(git rev-parse HEAD)
git push origin HEAD:"$BRANCH"
printf 'PRESTAGE_RUNTIME_REFACTOR_READY commit=%s runtime_lines=%s\n' "$NEW" "$runtime_lines"
