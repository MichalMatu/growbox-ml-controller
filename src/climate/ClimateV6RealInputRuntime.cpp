#include "climate/ClimateV6RealInputRuntime.h"

#include "climate/ClimateApplication.h"
#include "climate/ClimateCompositeInput.h"
#include "climate/ClimateSemanticOutput.h"
#include "climate/Stage28dBinaryRoleArbiter.h"
#include "climate/Stage28dLampSafety.h"
#include "climate/Stage28dOutputBindings.h"
#include "climate/Stage28dRfOutputEndpoint.h"
#include "climate/Stage28dThermalTestSequence.h"
#include "climate/native/BleClimateScanner.h"
#include "climate/native/Ds3231ClockSource.h"
#include "climate/native/NativeI2cBus.h"
#include "climate/native/Scd41InsideSource.h"
#include "climate/runtime/Stage27RuntimeAdapters.h"
#include "climate/runtime/Stage27TelemetryReporter.h"
#include "climate/runtime/Stage28RfDiagnostics.h"
#include "climate/runtime/Stage28ServiceConsole.h"
#include "climate/runtime/Stage28eLog.h"
#include "climate/runtime/Stage28ePlatformDiagnostics.h"
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
#ifndef GROWBOX_STAGE28_REAL_OUTPUTS_ENABLED
#define GROWBOX_STAGE28_REAL_OUTPUTS_ENABLED 0
#endif
#ifndef GROWBOX_STAGE28_THERMAL_TEST_SEQUENCE_ENABLED
#define GROWBOX_STAGE28_THERMAL_TEST_SEQUENCE_ENABLED 0
#endif

namespace growbox::app::climate_io {
namespace {

constexpr char kTag[] = "climate_stage27";
constexpr std::uint64_t kTickIntervalMs = 1'000U;
constexpr std::uint32_t kTelemetryEveryTicks = 10U;
constexpr unsigned kSafeStateAttempts = 3U;

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

class DiagnosticsRfTransmitter final : public stage28d::RfCommandTransmitter {
public:
  explicit DiagnosticsRfTransmitter(runtime::Stage28RfDiagnostics& diagnostics) noexcept
      : diagnostics_(diagnostics) {}

  bool transmit(const rf433::FrameConfig& frame) noexcept override {
    rf433::LoopbackEvidence evidence{};
    return diagnostics_.manualTransmit(frame, evidence) && evidence.tx_completed;
  }

private:
  runtime::Stage28RfDiagnostics& diagnostics_;
};

class SwitchableRoleDriver final : public ClimateRoleDriver {
public:
  SwitchableRoleDriver(runtime::LockedFakeRoleDriver& fake_driver, ClimateRoleDriver& real_driver,
                       bool real_enabled) noexcept
      : fake_driver_(fake_driver), real_driver_(real_driver), real_enabled_(real_enabled) {}

  bool apply(ClimateActuatorRole role, float level, std::uint64_t monotonic_ms) noexcept override {
    return real_enabled_ ? real_driver_.apply(role, level, monotonic_ms)
                         : fake_driver_.apply(role, level, monotonic_ms);
  }

  float appliedLevel(ClimateActuatorRole role, float requested_level) const noexcept override {
    return real_enabled_ ? real_driver_.appliedLevel(role, requested_level)
                         : fake_driver_.appliedLevel(role, requested_level);
  }

  bool forceSafeOff(ClimateActuatorRole role, std::uint64_t monotonic_ms) noexcept override {
    return real_enabled_ ? real_driver_.forceSafeOff(role, monotonic_ms)
                         : fake_driver_.forceSafeOff(role, monotonic_ms);
  }

  void disableReal() noexcept { real_enabled_ = false; }
  bool realEnabled() const noexcept { return real_enabled_; }

private:
  runtime::LockedFakeRoleDriver& fake_driver_;
  ClimateRoleDriver& real_driver_;
  bool real_enabled_{false};
};

bool forceSafeStateWithRetries(stage28d::Stage28dRfOutputEndpoint& endpoint,
                               std::uint64_t monotonic_ms) noexcept {
  for (unsigned attempt = 0U; attempt < kSafeStateAttempts; ++attempt) {
    if (endpoint.initializeSafeState(monotonic_ms)) {
      return true;
    }
  }
  return false;
}

runtime::Stage27PhysicalOutputSnapshot physicalOutputSnapshot(
    const stage28d::Stage28dRfOutputEndpoint& endpoint, bool real_active,
    const stage28d::LampSafetyDecision& lamp_decision,
    const stage28d::Stage28dBinaryRoleArbiter& binary_arbiter) noexcept {
  runtime::Stage27PhysicalOutputSnapshot snapshot{};
  snapshot.real_outputs_active = real_active;
  snapshot.light_on = endpoint.stateOn(stage28d::kScheduledLightEndpoint);
  snapshot.exhaust_on = endpoint.stateOn(stage28d::kExhaustFanEndpoint);
  snapshot.humidifier_on = endpoint.stateOn(stage28d::kHumidifierEndpoint);
  snapshot.thermal_safety_latched = lamp_decision.thermal_latched;
  snapshot.safety_force_exhaust = lamp_decision.force_exhaust_on;
  snapshot.safety_reason = static_cast<std::uint32_t>(lamp_decision.reason);
  snapshot.arbiter_transition_count = binary_arbiter.transitionCount();
  snapshot.arbiter_dwell_hold_count = binary_arbiter.dwellHoldCount();
  snapshot.arbiter_safety_override_count = binary_arbiter.safetyOverrideCount();
  return snapshot;
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
  DiagnosticsRfTransmitter rf_transmitter(rf_diagnostics);

  const auto semantic_output_config = stage28d::makeClimateSemanticOutputConfig();
  const bool output_bindings_valid =
      stage28d::validateOutputBindings(semantic_output_config) == stage28d::OutputBindingStatus::Ok;
  stage28d::Stage28dRfOutputEndpoint physical_endpoint(
      {GROWBOX_STAGE28_REAL_OUTPUTS_ENABLED != 0 && rf_ready && output_bindings_valid, 0.5F},
      rf_transmitter);

  bool real_output_ready = false;
  if (GROWBOX_STAGE28_REAL_OUTPUTS_ENABLED != 0) {
    real_output_ready = rf_ready && output_bindings_valid;
    if (real_output_ready) {
      real_output_ready = forceSafeStateWithRetries(physical_endpoint, monotonicMilliseconds());
    }
    if (!real_output_ready) {
      ESP_LOGE(kTag, "Real-output initialization failed; automatic outputs remain fake-locked");
    }
  }

  if (GROWBOX_STAGE28_THERMAL_TEST_SEQUENCE_ENABLED != 0 && !real_output_ready) {
    ESP_LOGE(kTag, "Gate6 thermal sequence requested but real outputs are not safely armed");
  }

  runtime::RuntimeTimingMetrics runtime_timing{};
  runtime_timing.loop_active.budget_us = kTickIntervalMs * 1000U;
  runtime::Stage28ServiceConsole service_console(
      {GROWBOX_STAGE28_SERVICE_CONSOLE_ENABLED != 0, GROWBOX_FIRMWARE_GIT_SHA,
       &real_output_ready, &storage_logger, &runtime_timing},
      ble, scd41, clock, rf_diagnostics);
  const bool service_console_ready = service_console.begin();

  runtime::Stage27InsideSource inside(ble, scd41);
  runtime::Stage27NearbySource outside(ble);
  runtime::FixedStage27ScheduleConfigSource schedule_config;
  CompositeClimateSnapshotProvider composite(inside, outside, clock, schedule_config);
  runtime::LockedFakeRoleDriver fake_output_driver;
  MappedClimateRoleDriver mapped_output_driver(semantic_output_config, physical_endpoint);
  stage28d::Stage28dBinaryRoleArbiter binary_arbiter(mapped_output_driver);
  if (real_output_ready) {
    binary_arbiter.synchronizeSafeOff(monotonicMilliseconds());
  }
  SwitchableRoleDriver output_driver(fake_output_driver, binary_arbiter, real_output_ready);
  ::growbox::climate::ClimateRuntimeController runtime_controller(nullptr,
                                                                  runtime::defaultRuntimeConfig());
  ClimateApplication application(runtime_controller, composite, output_driver);
  stage28d::LampSafetyController lamp_safety;
  stage28d::ThermalTestSequence thermal_test_sequence;
  const std::uint64_t thermal_test_started_ms = monotonicMilliseconds();
  stage28d::ThermalTestPhase last_test_phase = stage28d::ThermalTestPhase::Complete;
  bool thermal_test_finished_safe = false;

  const auto& boot_identity = runtime::bootIdentity(GROWBOX_FIRMWARE_GIT_SHA);
  const esp_reset_reason_t reset_reason =
      static_cast<esp_reset_reason_t>(boot_identity.reset_reason);
  runtime::configureStage28eLogging(boot_identity);
  runtime::Stage27TelemetryReporter telemetry_reporter(ble, scd41, clock, storage_logger,
                                                       storage_logger_ready,
                                                       static_cast<std::int32_t>(reset_reason));

  ESP_LOGI(kTag,
           "Stage27 real-input runtime: i2c=%d scd41=%d ds3231=%d ble=%d sd=%d "
           "flash_fallback=%d storage_logger=%d rf433_loopback=%d rf433_tx_gpio=%d "
           "rf433_rx_gpio=%d service_console=%d real_outputs_requested=%d real_outputs_ready=%d "
           "thermal_test=%d outputs=%s",
           i2c_ready, scd41_ready, rtc_ready, ble_ready, storage_config.sd_enabled,
           storage_config.flash_fallback_enabled, storage_logger_ready, rf_ready,
           GROWBOX_RF433_TX_GPIO, GROWBOX_RF433_RX_GPIO, service_console_ready,
           GROWBOX_STAGE28_REAL_OUTPUTS_ENABLED != 0, real_output_ready,
           GROWBOX_STAGE28_THERMAL_TEST_SEQUENCE_ENABLED != 0,
           real_output_ready ? "real-bounded" : "fake-locked");
  GROWBOX_STAGE28E_LOG_INFO(
      runtime::DiagnosticLogModule::Sys,
      "boot firmware_sha=%s reset_reason=%d started_us=%llu outputs=%s",
      boot_identity.firmware_sha, static_cast<int>(reset_reason),
      static_cast<unsigned long long>(boot_identity.started_monotonic_us),
      real_output_ready ? "real-bounded" : "fake-locked");

  std::uint32_t diagnostic_tick = 0U;
  while (true) {
    const std::uint64_t loop_started_us = static_cast<std::uint64_t>(esp_timer_get_time());
    const std::uint64_t now_ms = loop_started_us / 1000U;
    const std::uint64_t console_started_us = static_cast<std::uint64_t>(esp_timer_get_time());
    service_console.poll(now_ms);
    runtime_timing.service_console.observe(
        static_cast<std::uint64_t>(esp_timer_get_time()) - console_started_us);
    const std::uint64_t rf_started_us = static_cast<std::uint64_t>(esp_timer_get_time());
    rf_diagnostics.tick(now_ms);
    runtime_timing.rf_tick.observe(static_cast<std::uint64_t>(esp_timer_get_time()) - rf_started_us);

    ::growbox::climate::ClimateLoopResult loop_result{};
    ::growbox::climate::ClimateRuntimeDecision decision{};
    stage28d::LampSafetyDecision lamp_decision{};

    const std::uint64_t control_started_us = static_cast<std::uint64_t>(esp_timer_get_time());
    if (GROWBOX_STAGE28_THERMAL_TEST_SEQUENCE_ENABLED != 0 && real_output_ready &&
        !thermal_test_finished_safe) {
      const auto point = thermal_test_sequence.sample(now_ms - thermal_test_started_ms);
      lamp_decision = lamp_safety.evaluate(
          {point.scheduled_light_level, {point.temperature_c, true, 0U}, true, now_ms});
      physical_endpoint.setSafetyForceExhaust(lamp_decision.force_exhaust_on);

      bool physical_ok =
          physical_endpoint.writeScheduledLight(lamp_decision.effective_lamp_on, now_ms);
      physical_ok = physical_endpoint.write(stage28d::kExhaustFanEndpoint,
                                             lamp_decision.force_exhaust_on ? 1.0F : 0.0F,
                                             now_ms) &&
                    physical_ok;
      physical_ok = physical_endpoint.write(stage28d::kHumidifierEndpoint, 0.0F, now_ms) &&
                    physical_ok;

      decision.applied.exhaust_fan = lamp_decision.force_exhaust_on ? 1.0F : 0.0F;
      decision.applied.humidifier = 0.0F;

      if (point.phase != last_test_phase) {
        last_test_phase = point.phase;
        ESP_LOGI(kTag,
                 "GATE6_THERMAL_PHASE phase=%s temp_c=%.2f lamp_on=%d fan_on=%d latched=%d "
                 "reason=%u tx_count=%lu tx_errors=%lu physical_ok=%d",
                 stage28d::thermalTestPhaseName(point.phase), static_cast<double>(point.temperature_c),
                 lamp_decision.effective_lamp_on, lamp_decision.force_exhaust_on,
                 lamp_decision.thermal_latched, static_cast<unsigned>(lamp_decision.reason),
                 static_cast<unsigned long>(physical_endpoint.transmitCount()),
                 static_cast<unsigned long>(physical_endpoint.transmitErrorCount()), physical_ok);
      }

      if (!physical_ok) {
        ESP_LOGE(kTag, "Gate6 physical transition failed; forcing all outputs OFF");
        const bool safe_off = forceSafeStateWithRetries(physical_endpoint, now_ms);
        output_driver.disableReal();
        real_output_ready = false;
        ESP_LOGE(kTag, "GATE6_THERMAL_ABORT safe_off=%d outputs=fake-locked", safe_off);
      } else if (point.complete) {
        const bool safe_off = forceSafeStateWithRetries(physical_endpoint, now_ms);
        thermal_test_finished_safe = safe_off;
        output_driver.disableReal();
        real_output_ready = false;
        ESP_LOGI(kTag, "GATE6_THERMAL_SEQUENCE_COMPLETE safe_off=%d outputs=fake-locked", safe_off);
      }
    } else if (GROWBOX_STAGE28_THERMAL_TEST_SEQUENCE_ENABLED == 0) {
      ClimateWallClockSnapshot rtc_snapshot{};
      ClimateScheduleConfigSnapshot schedule_snapshot{};
      native::BleClimateReading tp357{};
      const bool rtc_sampled = clock.sample(now_ms, rtc_snapshot) && rtc_snapshot.valid;
      const bool schedule_sampled =
          rtc_sampled && schedule_config.resolve(now_ms, rtc_snapshot, schedule_snapshot);
      const bool tp357_sampled = ble.sampleTp357(now_ms, tp357);

      ::growbox::climate::MeasuredValue safety_temperature{};
      if (tp357_sampled) {
        safety_temperature = {tp357.temperature_c, true, tp357.age_ms};
      }
      const float scheduled_light = schedule_sampled ? schedule_snapshot.schedule.light_level : 0.0F;
      lamp_decision = lamp_safety.evaluate(
          {scheduled_light, safety_temperature, output_bindings_valid, now_ms});

      physical_endpoint.setSafetyForceExhaust(lamp_decision.force_exhaust_on);
      binary_arbiter.setSafetyForceExhaust(lamp_decision.force_exhaust_on);
      if (output_driver.realEnabled() &&
          !physical_endpoint.writeScheduledLight(lamp_decision.effective_lamp_on, now_ms)) {
        ESP_LOGE(kTag, "Lamp output apply failed; forcing safe state and locking real outputs");
        const bool safe_off = forceSafeStateWithRetries(physical_endpoint, now_ms);
        output_driver.disableReal();
        real_output_ready = false;
        ESP_LOGE(kTag, "Lamp output fault safe_off=%d outputs=fake-locked", safe_off);
      }

      loop_result = application.tick(now_ms, decision);
      if (output_driver.realEnabled() && !loop_result.command_applied) {
        ESP_LOGE(kTag, "Climate output apply failed; forcing safe state and locking real outputs");
        const bool safe_off = forceSafeStateWithRetries(physical_endpoint, now_ms);
        output_driver.disableReal();
        real_output_ready = false;
        ESP_LOGE(kTag, "Climate output fault safe_off=%d outputs=fake-locked", safe_off);
      }
    }
    runtime_timing.control_cycle.observe(
        static_cast<std::uint64_t>(esp_timer_get_time()) - control_started_us);

    if ((diagnostic_tick++ % kTelemetryEveryTicks) == 0U) {
      const std::uint64_t telemetry_started_us =
          static_cast<std::uint64_t>(esp_timer_get_time());
      const auto physical_outputs = physicalOutputSnapshot(
          physical_endpoint, output_driver.realEnabled(), lamp_decision, binary_arbiter);
      telemetry_reporter.record(now_ms, loop_result, decision, physical_outputs);
      ESP_LOGI(kTag,
               "stage28d_output real=%d lamp_known=%d lamp_on=%d fan_known=%d fan_on=%d "
               "humidifier_known=%d humidifier_on=%d safety_latched=%d force_fan=%d "
               "safety_reason=%u requested_fan=%.3f requested_humidifier=%.3f "
               "applied_fan=%.3f applied_humidifier=%.3f arbiter_transitions=%lu "
               "arbiter_dwell_holds=%lu arbiter_safety_overrides=%lu tx=%lu tx_errors=%lu",
               output_driver.realEnabled(),
               physical_endpoint.stateKnown(stage28d::kScheduledLightEndpoint),
               physical_endpoint.stateOn(stage28d::kScheduledLightEndpoint),
               physical_endpoint.stateKnown(stage28d::kExhaustFanEndpoint),
               physical_endpoint.stateOn(stage28d::kExhaustFanEndpoint),
               physical_endpoint.stateKnown(stage28d::kHumidifierEndpoint),
               physical_endpoint.stateOn(stage28d::kHumidifierEndpoint),
               lamp_decision.thermal_latched, lamp_decision.force_exhaust_on,
               static_cast<unsigned>(lamp_decision.reason),
               static_cast<double>(decision.rule.safe.exhaust_fan),
               static_cast<double>(decision.rule.safe.humidifier),
               static_cast<double>(decision.applied.exhaust_fan),
               static_cast<double>(decision.applied.humidifier),
               static_cast<unsigned long>(binary_arbiter.transitionCount()),
               static_cast<unsigned long>(binary_arbiter.dwellHoldCount()),
               static_cast<unsigned long>(binary_arbiter.safetyOverrideCount()),
               static_cast<unsigned long>(physical_endpoint.transmitCount()),
               static_cast<unsigned long>(physical_endpoint.transmitErrorCount()));
      runtime_timing.telemetry.observe(
          static_cast<std::uint64_t>(esp_timer_get_time()) - telemetry_started_us);
    }

    runtime_timing.loop_active.observe(
        static_cast<std::uint64_t>(esp_timer_get_time()) - loop_started_us);
    vTaskDelay(pdMS_TO_TICKS(kTickIntervalMs));
  }
}

} // namespace growbox::app::climate_io