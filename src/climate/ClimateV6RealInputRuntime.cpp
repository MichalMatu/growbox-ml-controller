#include "climate/ClimateV6RealInputRuntime.h"

#include "climate/ClimateApplication.h"
#include "climate/ClimateCompositeInput.h"
#include "climate/native/BleOutsideSource.h"
#include "climate/native/Ds3231ClockSource.h"
#include "climate/native/NativeI2cBus.h"
#include "climate/native/Scd41InsideSource.h"

#include <esp_err.h>
#include <esp_log.h>
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
#ifndef GROWBOX_BLE_OUTSIDE_MAC
#define GROWBOX_BLE_OUTSIDE_MAC ""
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

  native::Scd41InsideSource inside;
  native::Ds3231ClockSource clock;
  native::BleOutsideSource outside;
  const bool scd41_ready = i2c_ready && inside.begin(i2c);
  const bool rtc_ready = i2c_ready && clock.begin(i2c);
  const bool ble_ready = outside.begin(GROWBOX_BLE_OUTSIDE_MAC);

  FixedStage27ScheduleConfigSource schedule_config;
  CompositeClimateSnapshotProvider composite(inside, outside, clock, schedule_config);
  LockedFakeRoleDriver output_driver;
  ::growbox::climate::ClimateRuntimeController runtime(nullptr, runtimeConfig());
  ClimateApplication application(runtime, composite, output_driver);

  ESP_LOGI(kTag, "Stage27 real-input runtime: i2c=%d scd41=%d ds3231=%d ble=%d outputs=fake-locked",
           i2c_ready, scd41_ready, rtc_ready, ble_ready);

  std::uint32_t diagnostic_tick = 0U;
  while (true) {
    const std::uint64_t now_ms = monotonicMilliseconds();
    ::growbox::climate::ClimateRuntimeDecision decision{};
    const auto result = application.tick(now_ms, decision);
    if ((diagnostic_tick++ % 10U) == 0U) {
      ESP_LOGI(kTag,
               "input_sampled=%d io_status=%u scd41_available=%d scd41_sample=%d "
               "rtc_available=%d rtc_trusted=%d ble_scanning=%d ble_last_valid_ms=%llu",
               result.input_sampled, static_cast<unsigned>(result.io_status), inside.available(),
               inside.hasMeasurement(), clock.available(), clock.trusted(), outside.scanning(),
               static_cast<unsigned long long>(outside.lastValidMeasurementMs()));
    }
    vTaskDelay(pdMS_TO_TICKS(kTickIntervalMs));
  }
}

} // namespace growbox::app::climate_io
