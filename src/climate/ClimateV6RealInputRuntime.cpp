#include "climate/ClimateV6RealInputRuntime.h"

#include "climate/application/ClimateApplication.h"
#include "climate/application/ClimateCompositeInput.h"
#include "climate/input/ble/BleClimateScanner.h"
#include "climate/input/i2c/NativeI2cBus.h"
#include "climate/input/rtc/Ds3231ClockSource.h"
#include "climate/input/sensors/Scd41InsideSource.h"
#include "climate/runtime/RuntimeBuildConfig.h"
#include "climate/runtime/Stage27RuntimeAdapters.h"
#include "climate/runtime/console/Stage28ServiceConsole.h"
#include "climate/runtime/core/RealInputRuntimeComposition.h"
#include "climate/runtime/core/RealInputRuntimeCoordinator.h"
#include "climate/runtime/diagnostics/Stage28eLog.h"
#include "climate/runtime/diagnostics/Stage28ePlatformDiagnostics.h"
#include "climate/runtime/telemetry/TelemetryReporter.h"

#include <esp_err.h>
#include <esp_log.h>
#include <esp_system.h>
#include <esp_timer.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>

#include <cstdint>

namespace growbox::app::climate_io {
namespace {

constexpr char kTag[] = "climate_stage27";
constexpr std::uint64_t kTickIntervalMs = 1'000U;

} // namespace

[[noreturn]] void runClimateV6RealInputRuntime() noexcept {
  native::NativeI2cBus i2c(runtime_config::kI2cSdaGpio, runtime_config::kI2cSclGpio);
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
  const bool ble_ready = ble.begin(runtime_config::kBleTp357Mac, runtime_config::kBleXiaomiMac);

  static runtime::RuntimeIoOwner io_owner;
  const auto& storage_config = io_owner.storageConfig();
  auto& storage_logger = io_owner.storageLogger();
  const bool storage_enabled = storage_config.sd_enabled || storage_config.flash_fallback_enabled;
  const bool storage_logger_ready =
      storage_enabled && storage_logger.begin(runtime_config::kFirmwareGitSha);
  auto& rf_diagnostics = io_owner.rfDiagnostics();
  const bool rf_ready = io_owner.beginRf();

  static runtime::RuntimePersistenceOwner persistence_owner;
  persistence_owner.initialize();
  if (!persistence_owner.stateStoreReady()) {
    ESP_LOGE(kTag, "Output state-store shadow configuration failed");
  }
  if (!persistence_owner.valid()) {
    const auto& persistence_init = persistence_owner.initResult();
    ESP_LOGW(kTag, "Output persistence unavailable status=%u store_status=%u; using safe policy",
             static_cast<unsigned>(persistence_init.status),
             static_cast<unsigned>(persistence_init.load.status));
  }

  static runtime::RuntimeExecutionStatus execution_status;
  execution_status.transport_available = runtime_config::kRealOutputsEnabled && rf_ready;
  execution_status.output_ready = false;

  // The pre-supervisor Gate6 qualification path was a direct configured-output writer. Keep the
  // build knob fail-closed until the current supervisor-owned qualification contract is used.
  if (runtime_config::kThermalTestSequenceEnabled) {
    ESP_LOGW(kTag,
             "Legacy Gate6 thermal qualification is retired; locking real transport until A13");
    execution_status.transport_available = false;
  }

  static runtime::RuntimeOutputOwner output_owner(io_owner.rfOutputTransport(), execution_status,
                                                  rf_diagnostics, persistence_owner.policy(),
                                                  persistence_owner.stateStore());
  const bool output_bindings_valid = output_owner.bindingsValid();
  if (!output_bindings_valid) {
    execution_status.transport_available = false;
  }
  if (runtime_config::kRealOutputsEnabled && !execution_status.transport_available) {
    ESP_LOGE(kTag, "Real-output transport unavailable; automatic outputs remain fake-locked");
  }

  static runtime::RuntimeTimingMetrics runtime_timing{};
  runtime_timing.loop_active.budget_us = kTickIntervalMs * 1000U;

  runtime::Stage27InsideSource inside(ble, scd41);
  runtime::Stage27NearbySource outside(ble);
  runtime::FixedStage27ScheduleConfigSource schedule_config;
  CompositeClimateSnapshotProvider composite(inside, outside, clock, schedule_config);

  if (!output_owner.valid()) {
    ESP_LOGE(kTag, "Output supervisor/lifecycle composition invalid; physical execution locked");
    execution_status.transport_available = false;
    execution_status.output_ready = false;
  }

  runtime::Stage28ServiceConsole service_console(
      {runtime_config::kServiceConsoleEnabled, runtime_config::kFirmwareGitSha,
       &execution_status.output_ready, &storage_logger, &runtime_timing,
       &output_owner.automationControl(), &output_owner.manualControl(),
       &output_owner.maintenanceControl()},
      ble, scd41, clock, rf_diagnostics);
  const bool service_console_ready = service_console.begin();

  static runtime::RuntimeControlOwner control_owner;
  ClimateApplication application(control_owner.runtimeController(), composite,
                                 output_owner.supervisorSink());

  const auto& boot_identity = runtime::bootIdentity(runtime_config::kFirmwareGitSha);
  const esp_reset_reason_t reset_reason =
      static_cast<esp_reset_reason_t>(boot_identity.reset_reason);
  runtime::configureStage28eLogging(boot_identity);
  runtime::TelemetryReporter telemetry_reporter(ble, scd41, clock, storage_logger,
                                                storage_logger_ready,
                                                static_cast<std::int32_t>(reset_reason));

  ESP_LOGI(kTag,
           "Stage27 real-input runtime: i2c=%d scd41=%d ds3231=%d ble=%d sd=%d "
           "flash_fallback=%d storage_logger=%d rf433_loopback=%d rf433_tx_gpio=%d "
           "rf433_rx_gpio=%d service_console=%d real_outputs_requested=%d real_outputs_ready=%d "
           "thermal_test=%d outputs=%s",
           i2c_ready, scd41_ready, rtc_ready, ble_ready, storage_config.sd_enabled,
           storage_config.flash_fallback_enabled, storage_logger_ready, rf_ready,
           runtime_config::kRf433TxGpio, runtime_config::kRf433RxGpio, service_console_ready,
           runtime_config::kRealOutputsEnabled, execution_status.output_ready,
           runtime_config::kThermalTestSequenceEnabled,
           execution_status.output_ready ? "real-bounded" : "fake-locked");
  GROWBOX_STAGE28E_LOG_INFO(runtime::DiagnosticLogModule::Sys,
                            "boot firmware_sha=%s reset_reason=%d started_us=%llu outputs=%s",
                            boot_identity.firmware_sha, static_cast<int>(reset_reason),
                            static_cast<unsigned long long>(boot_identity.started_monotonic_us),
                            execution_status.output_ready ? "real-bounded" : "fake-locked");

  runtime::RealInputRuntimeServices services{
      {ble, clock},
      application,
      {control_owner.lampSafety(), execution_status, output_owner.transport(),
       output_owner.lifecycle(), output_owner.lifecycleExecutor(), output_owner.runtimeLifecycle(),
       output_owner.automationControl(), output_owner.manualControl(),
       output_owner.maintenanceControl(), output_owner.supervisorSink(),
       persistence_owner.persistence(), persistence_owner.stateStore(), output_bindings_valid},
      {service_console, rf_diagnostics, telemetry_reporter, runtime_timing},
  };
  runtime::RealInputRuntimeCoordinator coordinator(services);

  while (true) {
    const std::uint64_t loop_started_us = static_cast<std::uint64_t>(esp_timer_get_time());
    coordinator.tick(loop_started_us);
    vTaskDelay(pdMS_TO_TICKS(kTickIntervalMs));
  }
}

} // namespace growbox::app::climate_io
