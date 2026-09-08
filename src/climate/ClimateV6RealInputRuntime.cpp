#include "climate/ClimateV6RealInputRuntime.h"

#include "climate/ClimateApplication.h"
#include "climate/ClimateCompositeInput.h"
#include "climate/ClimateSemanticOutput.h"
#include "climate/Stage28dLampSafety.h"
#include "climate/Stage28dOutputBindings.h"
#include "climate/native/BleClimateScanner.h"
#include "climate/native/Ds3231ClockSource.h"
#include "climate/native/NativeI2cBus.h"
#include "climate/native/Scd41InsideSource.h"
#include "climate/output/BinaryActuatorPolicy.h"
#include "climate/output/ClimateOutputSupervisorSink.h"
#include "climate/output/OutputAutomationControl.h"
#include "climate/output/OutputExecutionTelemetry.h"
#include "climate/output/OutputLifecycleExecutor.h"
#include "climate/output/OutputMaintenanceControl.h"
#include "climate/output/OutputManualControl.h"
#include "climate/output/OutputNvsBackend.h"
#include "climate/output/OutputPersistenceCoordinator.h"
#include "climate/output/OutputPersistenceStore.h"
#include "climate/output/OutputRuntimeLifecycleControl.h"
#include "climate/output/OutputStateStore.h"
#include "climate/output/OutputSupervisorExecutor.h"
#include "climate/output/OutputSupervisorLifecycle.h"
#include "climate/output/OutputSupervisorResolver.h"
#include "climate/rf433/Rf433OutputTransport.h"
#include "climate/rf433/Rf433RmtFrameSender.h"
#include "climate/rf433/Rf433RmtLoopback.h"
#include "climate/runtime/Stage27RuntimeAdapters.h"
#include "climate/runtime/Stage27ScheduleIntentAdapter.h"
#include "climate/runtime/Stage27TelemetryReporter.h"
#include "climate/runtime/Stage28MaintenanceRfTransport.h"
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

#include <array>
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
#ifndef GROWBOX_RF433_REMOTE_CAPTURE_ENABLED
#define GROWBOX_RF433_REMOTE_CAPTURE_ENABLED 0
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
constexpr output::BinaryActuatorPolicyConfig kExhaustPolicyConfig{0.10F, 0.03F, 120'000U, 120'000U};
constexpr output::BinaryActuatorPolicyConfig kHumidifierPolicyConfig{0.10F, 0.03F, 180'000U,
                                                                     180'000U};

std::uint64_t monotonicMilliseconds() noexcept {
  return static_cast<std::uint64_t>(esp_timer_get_time()) / 1000U;
}

storage::Stage27TelemetryLogger::Config makeStorageConfig() noexcept {
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
  config.tx_gpio = GROWBOX_RF433_TX_GPIO;
  config.rx_gpio = GROWBOX_RF433_RX_GPIO;
  return config;
}

class RuntimeOutputTransport final : public output::OutputTransport {
public:
  RuntimeOutputTransport(output::OutputTransport& real_transport, const bool& real_enabled) noexcept
      : real_transport_(real_transport), real_enabled_(real_enabled) {}

  output::TxResult send(const output::OutputCommand& command) noexcept override {
    if (!real_enabled_) {
      return {output::TransportStatus::Completed, output::TransportError::None};
    }
    const auto result = real_transport_.send(command);
    if (result.status == output::TransportStatus::Completed) {
      ++transmit_count_;
    } else {
      ++transmit_error_count_;
    }
    return result;
  }

  std::uint32_t transmitCount() const noexcept {
    return transmit_count_;
  }
  std::uint32_t transmitErrorCount() const noexcept {
    return transmit_error_count_;
  }

private:
  output::OutputTransport& real_transport_;
  const bool& real_enabled_;
  std::uint32_t transmit_count_{0U};
  std::uint32_t transmit_error_count_{0U};
};

std::uint64_t nextOutputIntentSequence(std::uint64_t& sequence) noexcept {
  ++sequence;
  if (sequence == 0U) {
    ++sequence;
  }
  return sequence;
}

class RuntimeIoOwner final {
public:
  RuntimeIoOwner() noexcept
      : storage_config_(makeStorageConfig()), storage_logger_(storage_config_),
        rf_diagnostics_config_(rfDiagnosticsConfig()),
        rf_radio_(rf433::Rf433RmtLoopback::Config{rf_diagnostics_config_.tx_gpio,
                                                  rf_diagnostics_config_.rx_gpio}),
        rf_diagnostics_(rf_diagnostics_config_, rf_radio_), rf_frame_sender_(rf_radio_),
        rf_output_transport_(rf_frame_sender_) {}

  RuntimeIoOwner(const RuntimeIoOwner&) = delete;
  RuntimeIoOwner& operator=(const RuntimeIoOwner&) = delete;

  const storage::Stage27TelemetryLogger::Config& storageConfig() const noexcept {
    return storage_config_;
  }

  storage::Stage27TelemetryLogger& storageLogger() noexcept {
    return storage_logger_;
  }

  bool beginRf() noexcept {
    const bool radio_ready = rf_diagnostics_config_.enabled && rf_radio_.begin();
    return rf_diagnostics_.begin(radio_ready);
  }

  runtime::Stage28RfDiagnostics& rfDiagnostics() noexcept {
    return rf_diagnostics_;
  }

  rf433::Rf433RmtLoopback& rfRadio() noexcept {
    return rf_radio_;
  }

  rf433::Rf433OutputTransport& rfOutputTransport() noexcept {
    return rf_output_transport_;
  }

private:
  storage::Stage27TelemetryLogger::Config storage_config_{};
  storage::Stage27TelemetryLogger storage_logger_;
  runtime::Stage28RfDiagnosticsConfig rf_diagnostics_config_{};
  rf433::Rf433RmtLoopback rf_radio_;
  runtime::Stage28RfDiagnostics rf_diagnostics_;
  rf433::Rf433RmtFrameSender rf_frame_sender_;
  rf433::Rf433OutputTransport rf_output_transport_;
};

class RuntimeControlOwner final {
public:
  RuntimeControlOwner() noexcept : runtime_controller_(nullptr, runtime::defaultRuntimeConfig()) {}

  RuntimeControlOwner(const RuntimeControlOwner&) = delete;
  RuntimeControlOwner& operator=(const RuntimeControlOwner&) = delete;

  ::growbox::climate::ClimateRuntimeController& runtimeController() noexcept {
    return runtime_controller_;
  }

  stage28d::LampSafetyController& lampSafety() noexcept {
    return lamp_safety_;
  }

private:
  ::growbox::climate::ClimateRuntimeController runtime_controller_;
  stage28d::LampSafetyController lamp_safety_;
};

const output::OutputPolicyConfig& safeOutputPolicy() noexcept {
  static const output::OutputPolicyConfig policy = stage28d::makeOutputPolicyConfig();
  return policy;
}

output::OutputSupervisorResolverConfig
makeRuntimeSupervisorConfig(output::BinaryActuatorPolicy& exhaust_policy,
                            output::BinaryActuatorPolicy& humidifier_policy) noexcept {
  output::OutputSupervisorResolverConfig config{};
  config.endpoints[0] = {stage28d::kScheduledLightEndpoint, nullptr};
  config.endpoints[1] = {stage28d::kExhaustFanEndpoint, &exhaust_policy};
  config.endpoints[2] = {stage28d::kHumidifierEndpoint, &humidifier_policy};
  config.count = 3U;
  return config;
}

class RuntimeOutputOwner final {
public:
  RuntimeOutputOwner(output::OutputTransport& real_transport, const bool& real_enabled,
                     runtime::Stage28RfDiagnostics& diagnostics,
                     const output::OutputPolicyConfig& policy,
                     output::OutputStateStore& state_store) noexcept
      : policy_(policy),
        semantic_output_config_(stage28d::makeClimateSemanticOutputConfig(policy_)),
        exhaust_policy_(kExhaustPolicyConfig), humidifier_policy_(kHumidifierPolicyConfig),
        supervisor_config_(makeRuntimeSupervisorConfig(exhaust_policy_, humidifier_policy_)),
        supervisor_transport_(real_transport, real_enabled), output_lifecycle_(policy_),
        lifecycle_executor_(policy_, output_lifecycle_, supervisor_transport_, state_store,
                            supervisor_config_),
        runtime_lifecycle_(output_lifecycle_, lifecycle_executor_),
        automation_control_(output_lifecycle_, lifecycle_executor_),
        manual_control_(policy_, output_lifecycle_), maintenance_rf_transport_(diagnostics),
        maintenance_control_(policy_, output_lifecycle_, automation_control_, lifecycle_executor_,
                             state_store, supervisor_config_, maintenance_rf_transport_),
        supervisor_resolver_(supervisor_config_),
        supervisor_executor_(supervisor_transport_, state_store, supervisor_config_),
        supervisor_sink_(semantic_output_config_, supervisor_resolver_, supervisor_executor_,
                         state_store) {
    bindings_valid_ = stage28d::validateOutputBindings(semantic_output_config_, policy_) ==
                      stage28d::OutputBindingStatus::Ok;
    valid_ = bindings_valid_ && output_lifecycle_.valid() && lifecycle_executor_.valid() &&
             runtime_lifecycle_.valid() && automation_control_.valid() && manual_control_.valid() &&
             maintenance_control_.valid() && supervisor_sink_.valid();
  }

  RuntimeOutputOwner(const RuntimeOutputOwner&) = delete;
  RuntimeOutputOwner& operator=(const RuntimeOutputOwner&) = delete;

  bool valid() const noexcept {
    return valid_;
  }
  bool bindingsValid() const noexcept {
    return bindings_valid_;
  }

  RuntimeOutputTransport& transport() noexcept {
    return supervisor_transport_;
  }
  output::OutputSupervisorLifecycle& lifecycle() noexcept {
    return output_lifecycle_;
  }
  output::OutputLifecycleExecutor& lifecycleExecutor() noexcept {
    return lifecycle_executor_;
  }
  output::OutputRuntimeLifecycleControl& runtimeLifecycle() noexcept {
    return runtime_lifecycle_;
  }
  output::OutputAutomationControl& automationControl() noexcept {
    return automation_control_;
  }
  output::OutputManualControl& manualControl() noexcept {
    return manual_control_;
  }
  output::OutputMaintenanceControl& maintenanceControl() noexcept {
    return maintenance_control_;
  }
  ClimateOutputSupervisorSink& supervisorSink() noexcept {
    return supervisor_sink_;
  }

private:
  output::OutputPolicyConfig policy_{};
  ClimateSemanticOutputConfig semantic_output_config_{};
  output::BinaryActuatorPolicy exhaust_policy_;
  output::BinaryActuatorPolicy humidifier_policy_;
  output::OutputSupervisorResolverConfig supervisor_config_{};
  RuntimeOutputTransport supervisor_transport_;
  output::OutputSupervisorLifecycle output_lifecycle_;
  output::OutputLifecycleExecutor lifecycle_executor_;
  output::OutputRuntimeLifecycleControl runtime_lifecycle_;
  output::OutputAutomationControl automation_control_;
  output::OutputManualControl manual_control_;
  runtime::Stage28MaintenanceRfTransport maintenance_rf_transport_;
  output::OutputMaintenanceControl maintenance_control_;
  output::OutputSupervisorResolver supervisor_resolver_;
  output::OutputSupervisorExecutor supervisor_executor_;
  ClimateOutputSupervisorSink supervisor_sink_;
  bool bindings_valid_{false};
  bool valid_{false};
};

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

  static RuntimeIoOwner runtime_io_owner;
  const auto& storage_config = runtime_io_owner.storageConfig();
  auto& storage_logger = runtime_io_owner.storageLogger();
  const bool storage_enabled = storage_config.sd_enabled || storage_config.flash_fallback_enabled;
  const bool storage_logger_ready =
      storage_enabled && storage_logger.begin(GROWBOX_FIRMWARE_GIT_SHA);
  auto& rf_diagnostics = runtime_io_owner.rfDiagnostics();
  const bool rf_ready = runtime_io_owner.beginRf();
  static output::OutputStateStore output_state_store;
  static constexpr std::array<output::OutputEndpointId, output::kOutputEndpointCapacity>
      kShadowOutputEndpoints{stage28d::kExhaustFanEndpoint, stage28d::kScheduledLightEndpoint,
                             stage28d::kHumidifierEndpoint};
  const bool output_state_store_ready =
      output_state_store.configure(kShadowOutputEndpoints, kShadowOutputEndpoints.size());
  if (!output_state_store_ready) {
    ESP_LOGE(kTag, "Output state-store shadow configuration failed");
  }

  static output::OutputNvsBackend output_nvs_backend;
  static output::OutputPersistenceStore output_persistence_store(output_nvs_backend,
                                                                 safeOutputPolicy());
  static output::OutputPersistenceCoordinator output_persistence(output_persistence_store);
  const auto persistence_init = output_state_store_ready
                                    ? output_persistence.initialize(output_state_store)
                                    : output::OutputPersistenceCoordinatorInitResult{};
  const output::OutputPolicyConfig& output_policy =
      output_persistence.valid() ? output_persistence.policy() : safeOutputPolicy();
  if (!output_persistence.valid()) {
    ESP_LOGW(kTag, "Output persistence unavailable status=%u store_status=%u; using safe policy",
             static_cast<unsigned>(persistence_init.status),
             static_cast<unsigned>(persistence_init.load.status));
  }

  static bool real_transport_available = false;
  real_transport_available = GROWBOX_STAGE28_REAL_OUTPUTS_ENABLED != 0 && rf_ready;

  // The pre-supervisor Gate6 qualification path was a direct configured-output
  // writer. Keep the build knob fail-closed until A13 defines the replacement
  // supervisor-owned hardware qualification contract.
  if (GROWBOX_STAGE28_THERMAL_TEST_SEQUENCE_ENABLED != 0) {
    ESP_LOGW(kTag,
             "Legacy Gate6 thermal qualification is retired; locking real transport until A13");
    real_transport_available = false;
  }

  static RuntimeOutputOwner runtime_output_owner(runtime_io_owner.rfOutputTransport(),
                                                 real_transport_available, rf_diagnostics,
                                                 output_policy, output_state_store);
  const bool output_bindings_valid = runtime_output_owner.bindingsValid();
  if (!output_bindings_valid) {
    real_transport_available = false;
  }

  static bool real_output_ready = false;
  real_output_ready = false;
  if (GROWBOX_STAGE28_REAL_OUTPUTS_ENABLED != 0 && !real_transport_available) {
    ESP_LOGE(kTag, "Real-output transport unavailable; automatic outputs remain fake-locked");
  }

  static runtime::RuntimeTimingMetrics runtime_timing{};
  runtime_timing.loop_active.budget_us = kTickIntervalMs * 1000U;

  runtime::Stage27InsideSource inside(ble, scd41);
  runtime::Stage27NearbySource outside(ble);
  runtime::FixedStage27ScheduleConfigSource schedule_config;
  CompositeClimateSnapshotProvider composite(inside, outside, clock, schedule_config);

  auto& supervisor_transport = runtime_output_owner.transport();
  auto& output_lifecycle = runtime_output_owner.lifecycle();
  auto& lifecycle_executor = runtime_output_owner.lifecycleExecutor();
  auto& runtime_lifecycle = runtime_output_owner.runtimeLifecycle();
  auto& automation_control = runtime_output_owner.automationControl();
  auto& manual_control = runtime_output_owner.manualControl();
  auto& maintenance_control = runtime_output_owner.maintenanceControl();
  auto& supervisor_sink = runtime_output_owner.supervisorSink();

  if (!runtime_output_owner.valid()) {
    ESP_LOGE(kTag, "Output supervisor/lifecycle composition invalid; physical execution locked");
    // There is no direct emergency writer here anymore. If the supervisor cannot
    // be composed, fail closed by disabling transport ownership for this boot.
    real_transport_available = false;
    real_output_ready = false;
  }

  runtime::Stage28ServiceConsole service_console(
      {GROWBOX_STAGE28_SERVICE_CONSOLE_ENABLED != 0, GROWBOX_FIRMWARE_GIT_SHA, &real_output_ready,
       &storage_logger, &runtime_timing, &automation_control, &manual_control,
       &maintenance_control},
      ble, scd41, clock, rf_diagnostics);
  const bool service_console_ready = service_console.begin();

  static RuntimeControlOwner runtime_control_owner;
  auto& runtime_controller = runtime_control_owner.runtimeController();
  ClimateApplication application(runtime_controller, composite, supervisor_sink);
  auto& lamp_safety = runtime_control_owner.lampSafety();

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
  GROWBOX_STAGE28E_LOG_INFO(runtime::DiagnosticLogModule::Sys,
                            "boot firmware_sha=%s reset_reason=%d started_us=%llu outputs=%s",
                            boot_identity.firmware_sha, static_cast<int>(reset_reason),
                            static_cast<unsigned long long>(boot_identity.started_monotonic_us),
                            real_output_ready ? "real-bounded" : "fake-locked");

  std::uint32_t diagnostic_tick = 0U;
  std::uint64_t output_intent_sequence = 0U;
  while (true) {
    const std::uint64_t loop_started_us = static_cast<std::uint64_t>(esp_timer_get_time());
    const std::uint64_t now_ms = loop_started_us / 1000U;
    const std::uint64_t console_started_us = static_cast<std::uint64_t>(esp_timer_get_time());
    service_console.poll(now_ms);
    runtime_timing.service_console.observe(static_cast<std::uint64_t>(esp_timer_get_time()) -
                                           console_started_us);
    const std::uint64_t rf_started_us = static_cast<std::uint64_t>(esp_timer_get_time());
    rf_diagnostics.tick(now_ms);
    runtime_timing.rf_tick.observe(static_cast<std::uint64_t>(esp_timer_get_time()) -
                                   rf_started_us);

    ::growbox::climate::ClimateLoopResult loop_result{};
    ::growbox::climate::ClimateRuntimeDecision decision{};
    stage28d::LampSafetyDecision lamp_decision{};

    const std::uint64_t control_started_us = static_cast<std::uint64_t>(esp_timer_get_time());
    const bool real_transport_active_this_cycle = real_transport_available;
    ClimateWallClockSnapshot rtc_snapshot{};
    native::BleClimateReading tp357{};
    const bool rtc_sampled = clock.sample(now_ms, rtc_snapshot) && rtc_snapshot.valid;
    const bool tp357_sampled = ble.sampleTp357(now_ms, tp357);

    output::ScheduleIntent schedule_intent{};
    const std::uint64_t schedule_sequence = nextOutputIntentSequence(output_intent_sequence);
    const bool schedule_intent_ready =
        rtc_sampled && runtime::buildStage27ScheduleIntent(now_ms, rtc_snapshot, schedule_sequence,
                                                           schedule_intent);
    if (!schedule_intent_ready) {
      schedule_intent = {};
      schedule_intent.metadata.sequence = schedule_sequence;
      schedule_intent.metadata.monotonic_ms = now_ms;
      schedule_intent.metadata.source = output::OutputSource::Schedule;
      schedule_intent.metadata.reason = output::OutputReason::ScheduleRequest;
      (void)output::setEndpointIntent(schedule_intent.endpoints[0],
                                      stage28d::kScheduledLightEndpoint, 0.0F);
    }

    ::growbox::climate::MeasuredValue safety_temperature{};
    if (tp357_sampled) {
      safety_temperature = {tp357.temperature_c, true, tp357.age_ms};
    }
    const float scheduled_light = output::endpointIntentActive(schedule_intent.endpoints[0])
                                      ? schedule_intent.endpoints[0].level
                                      : 0.0F;
    const stage28d::LampSafetyInput lamp_safety_input{scheduled_light, safety_temperature,
                                                      output_bindings_valid, now_ms};
    lamp_decision = lamp_safety.evaluate(lamp_safety_input);

    stage28d::LampSafetyEnvelopeSnapshot safety_snapshot{};
    const bool safety_envelope_ready = stage28d::buildLampSafetyEnvelope(
        lamp_safety_input, lamp_decision, nextOutputIntentSequence(output_intent_sequence),
        safety_snapshot);
    if (!safety_envelope_ready && real_transport_available &&
        output_lifecycle.mode() != output::SupervisorMode::FaultLocked) {
      ESP_LOGE(kTag, "Lamp safety envelope build failed; requesting supervisor fault containment");
      if (!runtime_lifecycle.requestFault(now_ms, schedule_intent)) {
        ESP_LOGE(kTag, "Supervisor fault request failed; disabling physical transport");
        real_transport_available = false;
      }
      real_output_ready = false;
    } else if (safety_envelope_ready &&
               output_lifecycle.mode() == output::SupervisorMode::BootLocked &&
               !runtime_lifecycle.transitionActive()) {
      if (!runtime_lifecycle.beginBoot(now_ms, schedule_intent)) {
        ESP_LOGE(kTag, "Supervisor boot plan failed to start; disabling physical transport");
        real_transport_available = false;
        real_output_ready = false;
      }
    }

    // Runtime boot/recovery/fault owns the lifecycle executor only while its
    // own transition is active. Automation/maintenance retain their existing
    // executor ownership outside those windows. Hard safety defers lifecycle
    // TX and remains executable by the supervisor resolver below.
    (void)runtime_lifecycle.tick(now_ms, safety_snapshot.envelope);
    if (!runtime_lifecycle.transitionActive()) {
      (void)automation_control.tick(now_ms, schedule_intent, safety_snapshot.envelope);
      (void)maintenance_control.tick(now_ms, safety_snapshot.envelope);
    }

    real_output_ready = real_transport_available && runtime_lifecycle.bootCompleted() &&
                        output_lifecycle.mode() != output::SupervisorMode::FaultLocked;

    output::ManualIntent manual_intent{};
    (void)manual_control.consume(manual_intent);

    ClimateOutputSupervisorCycleContext supervisor_context{};
    supervisor_context.mode = output_lifecycle.mode();
    supervisor_context.schedule = schedule_intent;
    supervisor_context.manual = manual_intent;
    supervisor_context.safety = safety_snapshot.envelope;
    supervisor_sink.setCycleContext(supervisor_context);

    loop_result = application.tick(now_ms, decision);
    if (real_transport_available && !loop_result.command_applied &&
        output_lifecycle.mode() != output::SupervisorMode::FaultLocked) {
      ESP_LOGE(kTag, "Supervisor output apply failed; requesting lifecycle fault containment");
      if (!runtime_lifecycle.requestFault(now_ms, schedule_intent)) {
        ESP_LOGE(kTag, "Lifecycle fault containment failed to start; disabling physical transport");
        real_transport_available = false;
      }
      real_output_ready = false;
    }
    if (output_persistence.valid()) {
      const auto persistence_status = output_persistence.syncFromStateStore(
          output_state_store, real_transport_active_this_cycle);
      if (persistence_status == output::OutputPersistenceCoordinatorStatus::InvalidPolicy ||
          persistence_status == output::OutputPersistenceCoordinatorStatus::InvalidStateStore) {
        ESP_LOGE(kTag, "Output persistence synchronization invalid status=%u",
                 static_cast<unsigned>(persistence_status));
      }
    }
    runtime_timing.control_cycle.observe(static_cast<std::uint64_t>(esp_timer_get_time()) -
                                         control_started_us);

    if ((diagnostic_tick++ % kTelemetryEveryTicks) == 0U) {
      const std::uint64_t telemetry_started_us = static_cast<std::uint64_t>(esp_timer_get_time());
      output::OutputSupervisorCycleInput telemetry_cycle{};
      telemetry_cycle.mode = output_lifecycle.mode();
      telemetry_cycle.monotonic_ms = now_ms;
      telemetry_cycle.control = supervisor_sink.lastControlIntent();
      telemetry_cycle.schedule = schedule_intent;
      telemetry_cycle.manual = manual_intent;
      telemetry_cycle.safety = safety_snapshot.envelope;

      const auto lifecycle_report = lifecycle_executor.report();
      output::OutputExecutionTelemetrySnapshot output_telemetry{};
      const bool output_telemetry_ready = output::buildOutputExecutionTelemetry(
          telemetry_cycle, supervisor_sink.lastResolution(), output_state_store,
          real_transport_available, lifecycle_report.active, lifecycle_report.event,
          automation_control.requestedEnabled(), output_telemetry);
      output_telemetry.safety_latched = lamp_decision.thermal_latched;
      output_telemetry.safety_reason_code = static_cast<std::uint32_t>(lamp_decision.reason);
      if (!output_telemetry_ready) {
        ESP_LOGE(kTag, "Output execution telemetry snapshot build failed");
      }
      telemetry_reporter.record(now_ms, loop_result, decision, output_telemetry);
      ESP_LOGI(kTag,
               "output_exec_v=2 supervisor_mode=%u transport_active=%d lifecycle_active=%d "
               "lifecycle_event=%u automation_requested=%d safety_latched=%d safety_reason=%u "
               "tx=%lu tx_errors=%lu",
               static_cast<unsigned>(output_telemetry.mode), output_telemetry.transport_active,
               output_telemetry.lifecycle_active,
               static_cast<unsigned>(output_telemetry.lifecycle_event),
               output_telemetry.automation_requested, output_telemetry.safety_latched,
               output_telemetry.safety_reason_code,
               static_cast<unsigned long>(supervisor_transport.transmitCount()),
               static_cast<unsigned long>(supervisor_transport.transmitErrorCount()));
      for (std::size_t index = 0U; index < output_telemetry.endpoint_count; ++index) {
        const auto& endpoint = output_telemetry.endpoints[index];
        ESP_LOGI(kTag,
                 "output_endpoint endpoint=%u control=%d/%.3f schedule=%d/%.3f manual=%d/%.3f "
                 "safety=%d/%u/%u selected=%d/%.3f/%u/%u resolved=%d/%u dwell=%d "
                 "override=%d inhibited=%d attempt=%d current=%d state=%u source=%u reason=%u "
                 "transport=%u error=%u last_command=%d/%u/%u/%u physical_state=%u independent=%d",
                 static_cast<unsigned>(endpoint.endpoint), endpoint.control.active,
                 static_cast<double>(endpoint.control.level), endpoint.schedule.active,
                 static_cast<double>(endpoint.schedule.level), endpoint.manual.active,
                 static_cast<double>(endpoint.manual.level), endpoint.safety_active,
                 static_cast<unsigned>(endpoint.safety_constraint),
                 static_cast<unsigned>(endpoint.safety_reason), endpoint.selected,
                 static_cast<double>(endpoint.selected_level),
                 static_cast<unsigned>(endpoint.selected_source),
                 static_cast<unsigned>(endpoint.selected_reason), endpoint.resolved,
                 static_cast<unsigned>(endpoint.resolved_state), endpoint.held_by_dwell,
                 endpoint.safety_override, endpoint.inhibited, endpoint.attempt_known,
                 endpoint.attempted_this_cycle, static_cast<unsigned>(endpoint.attempt_state),
                 static_cast<unsigned>(endpoint.attempt_source),
                 static_cast<unsigned>(endpoint.attempt_reason),
                 static_cast<unsigned>(endpoint.transport_status),
                 static_cast<unsigned>(endpoint.transport_error), endpoint.last_command_known,
                 static_cast<unsigned>(endpoint.last_command_state),
                 static_cast<unsigned>(endpoint.last_command_source),
                 static_cast<unsigned>(endpoint.last_command_reason),
                 static_cast<unsigned>(endpoint.physical_state), endpoint.physical_independent);
      }
      runtime_timing.telemetry.observe(static_cast<std::uint64_t>(esp_timer_get_time()) -
                                       telemetry_started_us);
    }

    runtime_timing.loop_active.observe(static_cast<std::uint64_t>(esp_timer_get_time()) -
                                       loop_started_us);
    vTaskDelay(pdMS_TO_TICKS(kTickIntervalMs));
  }
}

} // namespace growbox::app::climate_io
