#include "climate/ClimateV6RealInputRuntime.h"

#include "climate/ClimateApplication.h"
#include "climate/ClimateCompositeInput.h"
#include "climate/native/BleClimateScanner.h"
#include "climate/native/Ds3231ClockSource.h"
#include "climate/native/NativeI2cBus.h"
#include "climate/native/Scd41InsideSource.h"
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

  Stage27InsideSource inside(ble, scd41);
  Stage27NearbySource outside(ble);
  FixedStage27ScheduleConfigSource schedule_config;
  CompositeClimateSnapshotProvider composite(inside, outside, clock, schedule_config);
  LockedFakeRoleDriver output_driver;
  ::growbox::climate::ClimateRuntimeController runtime(nullptr, runtimeConfig());
  ClimateApplication application(runtime, composite, output_driver);

  const esp_reset_reason_t reset_reason = esp_reset_reason();
  ESP_LOGI(kTag, "Stage27 real-input runtime: i2c=%d scd41=%d ds3231=%d ble=%d outputs=fake-locked",
           i2c_ready, scd41_ready, rtc_ready, ble_ready);
  ESP_LOGI(kTag, "Stage27 soak boot: firmware_sha=%s reset_reason=%d", GROWBOX_FIRMWARE_GIT_SHA,
           static_cast<int>(reset_reason));

  std::uint32_t diagnostic_tick = 0U;
  while (true) {
    const std::uint64_t now_ms = monotonicMilliseconds();
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
      const float scd_t =
          scd_diag.air_temperature_c.valid ? scd_diag.air_temperature_c.value : 0.0F;
      const float scd_rh =
          scd_diag.relative_humidity_pct.valid ? scd_diag.relative_humidity_pct.value : 0.0F;
      const float scd_co2 = scd_diag.co2_ppm.valid ? scd_diag.co2_ppm.value : 0.0F;
      const std::uint64_t scd_age_ms = scd_diag.co2_ppm.valid ? scd_diag.co2_ppm.age_ms : 0U;

      ESP_LOGI(
          kTag,
          "soak_v=2 firmware_sha=%s uptime_ms=%llu reset_reason=%d input_sampled=%d io_status=%u "
          "heap_internal=%u heap_internal_min=%u heap_internal_largest=%u "
          "heap_psram=%u heap_psram_min=%u heap_psram_largest=%u stack_free=%u "
          "scd_available=%d scd_sample=%d scd_t=%.2f scd_rh=%.2f scd_co2=%.0f "
          "scd_age_ms=%llu scd_read_errors=%u scd_invalid=%u scd_samples=%u "
          "rtc_available=%d rtc_trusted=%d rtc_reads=%u rtc_read_errors=%u rtc_untrusted=%u "
          "rtc_last_success_ms=%llu rtc_last_trusted_ms=%llu "
          "ble_scanning=%d ble_scan_starts=%u ble_scan_errors=%u ble_scan_restarts=%u "
          "ble_scan_completes=%u ble_adv_lock_drops=%u "
          "tp_sample=%d tp_age_ms=%llu tp_packets=%u tp_accepted=%u tp_rejected=%u "
          "xiaomi_sample=%d xiaomi_age_ms=%llu xiaomi_packets=%u xiaomi_accepted=%u "
          "xiaomi_rejected=%u outputs=fake-locked",
          GROWBOX_FIRMWARE_GIT_SHA, static_cast<unsigned long long>(now_ms),
          static_cast<int>(reset_reason), result.input_sampled,
          static_cast<unsigned>(result.io_status), static_cast<unsigned>(heap.free_internal),
          static_cast<unsigned>(heap.min_free_internal),
          static_cast<unsigned>(heap.largest_free_internal), static_cast<unsigned>(heap.free_psram),
          static_cast<unsigned>(heap.min_free_psram),
          static_cast<unsigned>(heap.largest_free_psram),
          static_cast<unsigned>(task.main_stack_free_bytes), scd41.available(),
          scd41.hasMeasurement(), static_cast<double>(scd_t), static_cast<double>(scd_rh),
          static_cast<double>(scd_co2), static_cast<unsigned long long>(scd_age_ms),
          scd41.readErrorCount(), scd41.invalidMeasurementCount(),
          scd41.successfulMeasurementCount(), clock.available(), clock.trusted(),
          clock.successfulReadCount(), clock.readErrorCount(), clock.untrustedReadCount(),
          static_cast<unsigned long long>(clock.lastSuccessfulReadMs()),
          static_cast<unsigned long long>(clock.lastTrustedReadMs()), ble.scanning(),
          ble.scanStartCount(), ble.scanStartErrorCount(), ble.scanRestartCount(),
          ble.scanCompleteCount(), ble.advertisementLockDropCount(), tp357_sampled,
          static_cast<unsigned long long>(tp357.age_ms), ble.tp357PacketCount(),
          ble.tp357AcceptedCount(), ble.tp357RejectedCount(), xiaomi_sampled,
          static_cast<unsigned long long>(xiaomi.age_ms), ble.xiaomiPacketCount(),
          ble.xiaomiAcceptedCount(), ble.xiaomiRejectedCount());
    }
    vTaskDelay(pdMS_TO_TICKS(kTickIntervalMs));
  }
}

} // namespace growbox::app::climate_io
