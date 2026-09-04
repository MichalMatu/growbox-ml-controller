#include "climate/ClimateV6RealInputRuntime.h"

#include "climate/ClimateApplication.h"
#include "climate/ClimateCompositeInput.h"
#include "climate/native/BleClimateScanner.h"
#include "climate/native/Ds3231ClockSource.h"
#include "climate/native/NativeI2cBus.h"
#include "climate/native/Scd41InsideSource.h"
#include "climate/rf433/Rf433RmtLoopback.h"
#include "climate/storage/Stage27TelemetryLogger.h"
#include "climate/telemetry/Stage27Telemetry.h"
#include "demo/protocol/HeapDiagnostics.h"

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

class LockedFakeRoleDriver final : public ClimateRoleDriver {
public:
  bool apply(ClimateActuatorRole, float, std::uint64_t) noexcept override {
    return true;
  }
};

class Stage27InsideSource final : public InsideEnvironmentSource {
public:
  Stage27InsideSource(native::BleClimateScanner& ble, native::Scd41InsideSource& scd41) noexcept
      : ble_(ble), scd41_(scd41) {}

  bool sample(std::uint64_t monotonic_ms, InsideEnvironmentSnapshot& output) noexcept override {
    output = {};

    native::BleClimateReading tp357{};
    const bool tp357_sampled = ble_.sampleTp357(monotonic_ms, tp357);
    if (tp357_sampled) {
      output.air_temperature_c = {tp357.temperature_c, true, tp357.age_ms};
      output.relative_humidity_pct = {tp357.relative_humidity_pct, true, tp357.age_ms};
    }

    InsideEnvironmentSnapshot scd41{};
    if (scd41_.sample(monotonic_ms, scd41) && scd41.co2_ppm.valid) {
      output.co2_ppm = scd41.co2_ppm;
    }

    return tp357_sampled || output.co2_ppm.valid;
  }

private:
  native::BleClimateScanner& ble_;
  native::Scd41InsideSource& scd41_;
};

class Stage27NearbySource final : public OutsideEnvironmentSource {
public:
  explicit Stage27NearbySource(native::BleClimateScanner& ble) noexcept : ble_(ble) {}

  bool sample(std::uint64_t monotonic_ms, OutsideEnvironmentSnapshot& output) noexcept override {
    output = {};
    native::BleClimateReading xiaomi{};
    if (!ble_.sampleXiaomi(monotonic_ms, xiaomi)) {
      return false;
    }
    output.air_temperature_c = {xiaomi.temperature_c, true, xiaomi.age_ms};
    output.relative_humidity_pct = {xiaomi.relative_humidity_pct, true, xiaomi.age_ms};
    return true;
  }

private:
  native::BleClimateScanner& ble_;
};

class FixedStage27ScheduleConfigSource final : public ClimateScheduleConfigSource {
public:
  bool resolve(std::uint64_t, const ClimateWallClockSnapshot& clock,
               ClimateScheduleConfigSnapshot& output) noexcept override {
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

    const std::uint8_t hour = static_cast<std::uint8_t>((clock.unix_time_s / 3600U) % 24U);
    const bool day = hour >= 6U && hour < 22U;
    output.targets.air_temperature_c = day ? 24.5F : 21.5F;
    output.targets.relative_humidity_pct = day ? 58.0F : 65.0F;
    output.targets.air_vpd_kpa = day ? 1.2F : 0.9F;
    output.targets.co2_enabled = day;
    output.targets.co2_ppm = day ? 950.0F : 450.0F;
    output.schedule.light_level = day ? 1.0F : 0.0F;
    return true;
  }
};

std::uint64_t monotonicMilliseconds() noexcept {
  return static_cast<std::uint64_t>(esp_timer_get_time()) / 1000U;
}

::growbox::climate::ClimateRuntimeConfig runtimeConfig() noexcept {
  ::growbox::climate::ClimateRuntimeConfig config{};
  config.mode = ::growbox::climate::ClimatePolicyMode::Rule;
  config.sensor_timeout_ms = ::growbox::climate::kDefaultSensorTimeoutMs;
  config.timestep_s = 1.0F;
  return config;
}

void logSoakRecord(const telemetry::Stage27TelemetrySnapshot& snapshot,
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

} // namespace

[[noreturn]] void runClimateV6RealInputRuntime() noexcept {
  native::NativeI2cBus i2c(GROWBOX_I2C_SDA_GPIO, GROWBOX_I2C_SCL_GPIO);
  const bool i2c_ready = i2c.begin() == ESP_OK;
  const esp_err_t scd41_probe = i2c_ready ? i2c.probe(0x62U) : ESP_ERR_INVALID_STATE;
  const esp_err_t rtc_probe = i2c_ready ? i2c.probe(0x68U) : ESP_ERR_INVALID_STATE;
  ESP_LOGI(kTag, "I2C probe: scd41_0x62=%s ds3231_0x68=%s", esp_err_to_name(scd41_probe),
           esp_err_to_name(rtc_probe));

  native::Scd41InsideSource scd41;
  native::Ds3231ClockSource clock;
  native::BleClimateScanner ble;
  const bool scd41_ready = i2c_ready && scd41.begin(i2c);
  const bool rtc_ready = i2c_ready && clock.begin(i2c);
  const bool ble_ready = ble.begin(GROWBOX_BLE_TP357_MAC, GROWBOX_BLE_XIAOMI_MAC);

  storage::Stage27TelemetryLogger::Config storage_config{};
  storage_config.sd_pins = {GROWBOX_SD_MOSI_GPIO, GROWBOX_SD_MISO_GPIO, GROWBOX_SD_SCLK_GPIO,
                            GROWBOX_SD_CS_GPIO, GROWBOX_SD_POWER_GPIO};
  storage_config.sd_enabled = GROWBOX_STAGE27_SD_ENABLED != 0;
  storage_config.flash_fallback_enabled = GROWBOX_STAGE27_FLASH_FALLBACK_ENABLED != 0;
  storage_config.sd_cmd0_precondition = GROWBOX_SD_CMD0_PRECONDITION != 0;
  storage::Stage27TelemetryLogger storage_logger(storage_config);
  const bool storage_enabled = storage_config.sd_enabled || storage_config.flash_fallback_enabled;
  const bool storage_logger_ready =
      storage_enabled && storage_logger.begin(GROWBOX_FIRMWARE_GIT_SHA);

  rf433::Rf433RmtLoopback rf_loopback(
      rf433::Rf433RmtLoopback::Config{GROWBOX_RF433_TX_GPIO, GROWBOX_RF433_RX_GPIO});
  const bool rf_loopback_ready =
      GROWBOX_RF433_LOOPBACK_ENABLED != 0 && rf_loopback.begin();

  Stage27InsideSource inside(ble, scd41);
  Stage27NearbySource outside(ble);
  FixedStage27ScheduleConfigSource schedule_config;
  CompositeClimateSnapshotProvider composite(inside, outside, clock, schedule_config);
  LockedFakeRoleDriver output_driver;
  ::growbox::climate::ClimateRuntimeController runtime(nullptr, runtimeConfig());
  ClimateApplication application(runtime, composite, output_driver);

  const esp_reset_reason_t reset_reason = esp_reset_reason();
  ESP_LOGI(kTag,
           "Stage27 real-input runtime: i2c=%d scd41=%d ds3231=%d ble=%d sd=%d "
           "flash_fallback=%d storage_logger=%d rf433_loopback=%d rf433_tx_gpio=%d "
           "rf433_rx_gpio=%d outputs=fake-locked",
           i2c_ready, scd41_ready, rtc_ready, ble_ready, storage_config.sd_enabled,
           storage_config.flash_fallback_enabled, storage_logger_ready, rf_loopback_ready,
           GROWBOX_RF433_TX_GPIO, GROWBOX_RF433_RX_GPIO);
  ESP_LOGI(kTag, "Stage27 soak boot: firmware_sha=%s reset_reason=%d", GROWBOX_FIRMWARE_GIT_SHA,
           static_cast<int>(reset_reason));

  std::uint32_t diagnostic_tick = 0U;
  bool rf_smoke_attempted = false;
  while (true) {
    const std::uint64_t now_ms = monotonicMilliseconds();
    if (rf_loopback_ready && GROWBOX_RF433_LOOPBACK_AUTO_SMOKE != 0 &&
        !rf_smoke_attempted && now_ms >= 3'000U) {
      rf_smoke_attempted = true;
      rf433::LoopbackEvidence evidence{};
      const rf433::FrameConfig smoke{{0xA55AU, 16U, 1U}, 3U, 0U};
      const bool passed = rf_loopback.transmitAndReceive(smoke, 1'500U, evidence);
      const auto& rf_diag = rf_loopback.diagnostics();
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

    ::growbox::climate::ClimateRuntimeDecision decision{};
    const auto result = application.tick(now_ms, decision);
    if ((diagnostic_tick++ % 10U) == 0U) {
      native::BleClimateReading tp357{};
      native::BleClimateReading xiaomi{};
      const bool tp357_sampled = ble.sampleTp357(now_ms, tp357);
      const bool xiaomi_sampled = ble.sampleXiaomi(now_ms, xiaomi);

      InsideEnvironmentSnapshot scd_diag{};
      static_cast<void>(scd41.sample(now_ms, scd_diag));
      const auto heap = ::growbox::demo::wire::captureHeapSnapshot();
      const auto task = ::growbox::demo::wire::captureTaskSnapshot();

      telemetry::Stage27TelemetrySnapshot snapshot{};
      snapshot.uptime_ms = now_ms;
      snapshot.unix_time_s = clock.trusted() ? clock.lastTrustedUnixTimeS() : 0U;
      snapshot.reset_reason = static_cast<std::int32_t>(reset_reason);
      snapshot.input_sampled = result.input_sampled;
      snapshot.io_status = static_cast<std::uint32_t>(result.io_status);
      snapshot.heap_internal = heap.free_internal;
      snapshot.heap_internal_min = heap.min_free_internal;
      snapshot.heap_internal_largest = heap.largest_free_internal;
      snapshot.heap_psram = heap.free_psram;
      snapshot.heap_psram_min = heap.min_free_psram;
      snapshot.heap_psram_largest = heap.largest_free_psram;
      snapshot.stack_free = task.main_stack_free_bytes;

      snapshot.scd_available = scd41.available();
      snapshot.scd_sample = scd41.hasMeasurement();
      snapshot.scd_temperature_c =
          scd_diag.air_temperature_c.valid ? scd_diag.air_temperature_c.value : 0.0F;
      snapshot.scd_humidity_pct =
          scd_diag.relative_humidity_pct.valid ? scd_diag.relative_humidity_pct.value : 0.0F;
      snapshot.scd_co2_ppm = scd_diag.co2_ppm.valid ? scd_diag.co2_ppm.value : 0.0F;
      snapshot.scd_age_ms = scd_diag.co2_ppm.valid ? scd_diag.co2_ppm.age_ms : 0U;
      snapshot.scd_read_errors = scd41.readErrorCount();
      snapshot.scd_invalid = scd41.invalidMeasurementCount();
      snapshot.scd_samples = scd41.successfulMeasurementCount();

      snapshot.rtc_available = clock.available();
      snapshot.rtc_trusted = clock.trusted();
      snapshot.rtc_reads = clock.successfulReadCount();
      snapshot.rtc_read_errors = clock.readErrorCount();
      snapshot.rtc_untrusted = clock.untrustedReadCount();
      snapshot.rtc_last_success_ms = clock.lastSuccessfulReadMs();
      snapshot.rtc_last_trusted_ms = clock.lastTrustedReadMs();

      snapshot.ble_scanning = ble.scanning();
      snapshot.ble_scan_starts = ble.scanStartCount();
      snapshot.ble_scan_errors = ble.scanStartErrorCount();
      snapshot.ble_scan_restarts = ble.scanRestartCount();
      snapshot.ble_scan_completes = ble.scanCompleteCount();
      snapshot.ble_adv_lock_drops = ble.advertisementLockDropCount();

      snapshot.tp_sample = tp357_sampled;
      snapshot.tp_temperature_c = tp357_sampled ? tp357.temperature_c : 0.0F;
      snapshot.tp_humidity_pct = tp357_sampled ? tp357.relative_humidity_pct : 0.0F;
      snapshot.tp_age_ms = tp357_sampled ? tp357.age_ms : 0U;
      snapshot.tp_packets = ble.tp357PacketCount();
      snapshot.tp_accepted = ble.tp357AcceptedCount();
      snapshot.tp_rejected = ble.tp357RejectedCount();

      snapshot.xiaomi_sample = xiaomi_sampled;
      snapshot.xiaomi_temperature_c = xiaomi_sampled ? xiaomi.temperature_c : 0.0F;
      snapshot.xiaomi_humidity_pct = xiaomi_sampled ? xiaomi.relative_humidity_pct : 0.0F;
      snapshot.xiaomi_age_ms = xiaomi_sampled ? xiaomi.age_ms : 0U;
      snapshot.xiaomi_packets = ble.xiaomiPacketCount();
      snapshot.xiaomi_accepted = ble.xiaomiAcceptedCount();
      snapshot.xiaomi_rejected = ble.xiaomiRejectedCount();

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

      const auto storage_status = storage_logger.status();
      logSoakRecord(snapshot, storage_status);

      if (storage_logger_ready) {
        static_cast<void>(storage_logger.enqueue(snapshot));
      }
    }
    vTaskDelay(pdMS_TO_TICKS(kTickIntervalMs));
  }
}

} // namespace growbox::app::climate_io
