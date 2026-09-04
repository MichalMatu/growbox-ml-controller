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
#include "climate/runtime/Stage28ServiceConsole.h"
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
#ifndef GROWBOX_STAGE28_SERVICE_CONSOLE_ENABLED
#define GROWBOX_STAGE28_SERVICE_CONSOLE_ENABLED 1
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
  config.sd_pins = {GROWBOX_SD_MOSI_GPIO, GROWBOX_SD_MISO_GPIO, GROWBOX_SD_SCLK_GPIO,
                    GROWBOX_SD_CS_GPIO, GROWBOX_SD_POWER_GPIO};
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
  config.smoke = {{static_cast<std::uint32_t>(GROWBOX_RF433_LOOPBACK_SMOKE_CODE),
                   static_cast<std::uint8_t>(GROWBOX_RF433_LOOPBACK_SMOKE_BITS),
                   static_cast<std::uint8_t>(GROWBOX_RF433_LOOPBACK_SMOKE_PROTOCOL)},
                  static_cast<std::uint8_t>(GROWBOX_RF433_LOOPBACK_SMOKE_REPEAT),
                  static_cast<std::uint16_t>(GROWBOX_RF433_LOOPBACK_SMOKE_PULSE_US)};
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

  const auto storage_config = storageConfig();
  storage::Stage27TelemetryLogger storage_logger(storage_config);
  const bool storage_enabled = storage_config.sd_enabled || storage_config.flash_fallback_enabled;
  const bool storage_logger_ready =
      storage_enabled && storage_logger.begin(GROWBOX_FIRMWARE_GIT_SHA);

  runtime::Stage28RfDiagnostics rf_diagnostics(rfDiagnosticsConfig());
  const bool rf_ready = rf_diagnostics.begin();
  runtime::Stage28ServiceConsole service_console(
      {GROWBOX_STAGE28_SERVICE_CONSOLE_ENABLED != 0, GROWBOX_FIRMWARE_GIT_SHA}, ble, scd41, clock,
      rf_diagnostics);
  const bool service_console_ready = service_console.begin();

  runtime::Stage27InsideSource inside(ble, scd41);
  runtime::Stage27NearbySource outside(ble);
  runtime::FixedStage27ScheduleConfigSource schedule_config;
  CompositeClimateSnapshotProvider composite(inside, outside, clock, schedule_config);
  runtime::LockedFakeRoleDriver output_driver;
  ::growbox::climate::ClimateRuntimeController runtime_controller(nullptr,
                                                                  runtime::defaultRuntimeConfig());
  ClimateApplication application(runtime_controller, composite, output_driver);

  const esp_reset_reason_t reset_reason = esp_reset_reason();
  runtime::Stage27TelemetryReporter telemetry_reporter(ble, scd41, clock, storage_logger,
                                                       storage_logger_ready,
                                                       static_cast<std::int32_t>(reset_reason));

  ESP_LOGI(kTag,
           "Stage27 real-input runtime: i2c=%d scd41=%d ds3231=%d ble=%d sd=%d "
           "flash_fallback=%d storage_logger=%d rf433_loopback=%d rf433_tx_gpio=%d "
           "rf433_rx_gpio=%d service_console=%d outputs=fake-locked",
           i2c_ready, scd41_ready, rtc_ready, ble_ready, storage_config.sd_enabled,
           storage_config.flash_fallback_enabled, storage_logger_ready, rf_ready,
           GROWBOX_RF433_TX_GPIO, GROWBOX_RF433_RX_GPIO, service_console_ready);
  ESP_LOGI(kTag, "Stage27 soak boot: firmware_sha=%s reset_reason=%d", GROWBOX_FIRMWARE_GIT_SHA,
           static_cast<int>(reset_reason));

  std::uint32_t diagnostic_tick = 0U;
  while (true) {
    const std::uint64_t now_ms = monotonicMilliseconds();
    service_console.poll(now_ms);
    rf_diagnostics.tick(now_ms);

    ::growbox::climate::ClimateRuntimeDecision decision{};
    const auto loop_result = application.tick(now_ms, decision);
    if ((diagnostic_tick++ % kTelemetryEveryTicks) == 0U) {
      telemetry_reporter.record(now_ms, loop_result, decision);
    }

    vTaskDelay(pdMS_TO_TICKS(kTickIntervalMs));
  }
}

} // namespace growbox::app::climate_io
