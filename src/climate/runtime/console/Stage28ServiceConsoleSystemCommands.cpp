#include "climate/runtime/console/Stage28ServiceConsoleSystemCommands.h"

#include "climate/input/ble/BleClimateScanner.h"
#include "climate/input/rtc/Ds3231ClockSource.h"
#include "climate/native/Scd41InsideSource.h"
#include "climate/rf433/Rf433HardwareConfig.h"
#include "climate/runtime/diagnostics/Stage28RfDiagnostics.h"
#include "climate/runtime/diagnostics/Stage28ePlatformDiagnostics.h"
#include "climate/runtime/schedule/EuropeWarsawTime.h"
#include "climate/storage/Stage27TelemetryLogger.h"

#include <array>
#include <cstring>
#include <esp_heap_caps.h>
#include <freertos/FreeRTOS.h>
#include <freertos/idf_additions.h>
#include <freertos/task.h>
#include <sdkconfig.h>

namespace growbox::app::climate_io::runtime {
namespace {
struct KnownRfDevice {
  ServiceConsoleRfDevice id;
  const char* physical_name;
  const rf433::RemoteSocketHardwareConfig* hardware;
  const char* tx_status;
};
constexpr std::array<KnownRfDevice, 3U> kKnownRfDevices{{
    {ServiceConsoleRfDevice::Lamp, "lamp", &rf433::kRemoteSocket2,
     "physically validated; Shelly signature about +97W"},
    {ServiceConsoleRfDevice::Fan, "fan", &rf433::kRemoteSocket1,
     "physically validated; Shelly signature about +2.9W"},
    {ServiceConsoleRfDevice::Humidifier, "humidifier", &rf433::kRemoteSocket3,
     "physically validated; Shelly signature about +15.7W"},
}};

std::uint32_t knownConfiguredTaskStackBytes(const char* name) noexcept {
  if (name == nullptr)
    return 0U;
  if (std::strcmp(name, "main") == 0)
    return static_cast<std::uint32_t>(CONFIG_ESP_MAIN_TASK_STACK_SIZE);
  if (std::strcmp(name, "stage27_store") == 0)
    return storage::Stage27TelemetryLogger::taskStackBytes();
#if defined(CONFIG_ESP_TIMER_TASK_STACK_SIZE)
  if (std::strcmp(name, "esp_timer") == 0)
    return static_cast<std::uint32_t>(CONFIG_ESP_TIMER_TASK_STACK_SIZE);
#endif
#if defined(CONFIG_ESP_SYSTEM_EVENT_TASK_STACK_SIZE)
  if (std::strcmp(name, "sys_evt") == 0)
    return static_cast<std::uint32_t>(CONFIG_ESP_SYSTEM_EVENT_TASK_STACK_SIZE);
#endif
#if defined(CONFIG_BT_NIMBLE_HOST_TASK_STACK_SIZE)
  if (std::strcmp(name, "nimble_host") == 0)
    return static_cast<std::uint32_t>(CONFIG_BT_NIMBLE_HOST_TASK_STACK_SIZE);
#endif
  return 0U;
}

const char* stackMarginSeverityName(StackMarginSeverity severity) noexcept {
  switch (severity) {
  case StackMarginSeverity::Normal:
    return "normal";
  case StackMarginSeverity::Warning:
    return "warning";
  case StackMarginSeverity::Critical:
    return "critical";
  case StackMarginSeverity::Unknown:
    break;
  }
  return "unknown";
}
} // namespace

bool Stage28ServiceConsoleSystemCommands::realOutputsActive() const noexcept {
  return config_.real_outputs_active != nullptr && *config_.real_outputs_active;
}
const char* Stage28ServiceConsoleSystemCommands::outputModeName() const noexcept {
  return realOutputsActive() ? "real-bounded" : "fake-locked";
}

bool Stage28ServiceConsoleSystemCommands::handle(const ServiceConsoleCommand& command,
                                                 std::uint64_t now_ms) noexcept {
  switch (command.kind) {
  case ServiceConsoleCommandKind::Status:
    printStatus(now_ms);
    return true;
  case ServiceConsoleCommandKind::Sensors:
    printSensors(now_ms);
    return true;
  case ServiceConsoleCommandKind::RfList:
    printRfList();
    return true;
  case ServiceConsoleCommandKind::RfReceive:
    handleRfReceive(command);
    return true;
  case ServiceConsoleCommandKind::RtcSetUnix:
    handleRtcSetUnix(command, now_ms);
    return true;
  default:
    return false;
  }
}

void Stage28ServiceConsoleSystemCommands::printStatus(std::uint64_t now_ms) noexcept {
  const auto& boot = bootIdentity(config_.firmware_sha);
  const RuntimeMemoryMetrics memory = sampleRuntimeMemoryMetrics();
  const UBaseType_t stack_watermark_bytes = uxTaskGetStackHighWaterMark(nullptr);

  UBaseType_t task_total = 0U;
  UBaseType_t task_captured = 0U;
  TaskStatus_t* task_status = nullptr;
#if CONFIG_FREERTOS_USE_TRACE_FACILITY
  task_total = uxTaskGetNumberOfTasks();
  const UBaseType_t task_capacity = task_total + 2U;
  const std::size_t task_bytes = static_cast<std::size_t>(task_capacity) * sizeof(TaskStatus_t);
  task_status =
      static_cast<TaskStatus_t*>(heap_caps_malloc(task_bytes, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT));
  if (task_status != nullptr) {
    task_captured = uxTaskGetSystemState(task_status, task_capacity, nullptr);
  }
#endif

  sink_.writeFormatted(
      "status firmware_sha=%s boot_id=%08lx reset_reason=%ld uptime_ms=%llu outputs=%s rf_ready=%d "
      "internal_total=%lu internal_free=%lu internal_min=%lu internal_largest=%lu "
      "psram_total=%lu psram_free=%lu psram_min=%lu psram_largest=%lu "
      "free_internal=%lu free_psram=%lu stack_high_water=%lu current_task_stack_hwm_bytes=%lu "
      "task_total=%lu task_captured=%lu task_snapshot_psram=%d "
      "hwm_semantics=min_free_since_create\r\n",
      boot.firmware_sha, static_cast<unsigned long>(boot.boot_id),
      static_cast<long>(boot.reset_reason), static_cast<unsigned long long>(now_ms),
      outputModeName(), rf_diagnostics_.ready(),
      static_cast<unsigned long>(memory.internal.total_bytes),
      static_cast<unsigned long>(memory.internal.free_bytes),
      static_cast<unsigned long>(memory.internal.minimum_free_bytes),
      static_cast<unsigned long>(memory.internal.largest_free_block_bytes),
      static_cast<unsigned long>(memory.psram.total_bytes),
      static_cast<unsigned long>(memory.psram.free_bytes),
      static_cast<unsigned long>(memory.psram.minimum_free_bytes),
      static_cast<unsigned long>(memory.psram.largest_free_block_bytes),
      static_cast<unsigned long>(memory.internal.free_bytes),
      static_cast<unsigned long>(memory.psram.free_bytes),
      static_cast<unsigned long>(stack_watermark_bytes),
      static_cast<unsigned long>(stack_watermark_bytes), static_cast<unsigned long>(task_total),
      static_cast<unsigned long>(task_captured), task_status != nullptr);

  status_contributor_.printStatusDetails();

  if (config_.timing_metrics != nullptr) {
    const RuntimeTimingMetrics& timing = *config_.timing_metrics;
    sink_.writeFormatted(
        "timing loop_samples=%llu loop_max_us=%llu loop_overruns=%llu loop_budget_us=%llu "
        "control_samples=%llu control_max_us=%llu rf_samples=%llu rf_max_us=%llu "
        "telemetry_samples=%llu telemetry_max_us=%llu console_samples=%llu console_max_us=%llu\r\n",
        static_cast<unsigned long long>(timing.loop_active.sample_count),
        static_cast<unsigned long long>(timing.loop_active.max_us),
        static_cast<unsigned long long>(timing.loop_active.overrun_count),
        static_cast<unsigned long long>(timing.loop_active.budget_us),
        static_cast<unsigned long long>(timing.control_cycle.sample_count),
        static_cast<unsigned long long>(timing.control_cycle.max_us),
        static_cast<unsigned long long>(timing.rf_tick.sample_count),
        static_cast<unsigned long long>(timing.rf_tick.max_us),
        static_cast<unsigned long long>(timing.telemetry.sample_count),
        static_cast<unsigned long long>(timing.telemetry.max_us),
        static_cast<unsigned long long>(timing.service_console.sample_count),
        static_cast<unsigned long long>(timing.service_console.max_us));
  }

  for (UBaseType_t index = 0U; index < task_captured; ++index) {
    const TaskStatus_t& task = task_status[index];
    const std::uint32_t configured_stack_bytes = knownConfiguredTaskStackBytes(task.pcTaskName);
    const std::uint32_t high_water_bytes = static_cast<std::uint32_t>(task.usStackHighWaterMark);
    const StackMarginSeverity severity =
        classifyStackMargin(high_water_bytes, configured_stack_bytes);
    sink_.writeFormatted(
        "task name=%s task_no=%lu core=%ld priority=%lu configured_stack_bytes=%lu "
        "hwm_bytes=%lu worst_hwm_bytes=%lu severity=%s\r\n",
        task.pcTaskName != nullptr ? task.pcTaskName : "unknown",
        static_cast<unsigned long>(task.xTaskNumber),
        static_cast<long>(xTaskGetCoreID(task.xHandle)),
        static_cast<unsigned long>(task.uxCurrentPriority),
        static_cast<unsigned long>(configured_stack_bytes),
        static_cast<unsigned long>(high_water_bytes), static_cast<unsigned long>(high_water_bytes),
        stackMarginSeverityName(severity));
  }
  if (task_status != nullptr) {
    heap_caps_free(task_status);
  }
}

void Stage28ServiceConsoleSystemCommands::printSensors(std::uint64_t now_ms) noexcept {
  InsideEnvironmentSnapshot scd{};
  const bool scd_sampled = scd41_.sample(now_ms, scd);
  native::BleClimateReading tp357{};
  const bool tp357_sampled = ble_.sampleTp357(now_ms, tp357);
  native::BleClimateReading xiaomi{};
  const bool xiaomi_sampled = ble_.sampleXiaomi(now_ms, xiaomi);
  ClimateWallClockSnapshot rtc{};
  const bool rtc_sampled = clock_.sample(now_ms, rtc);

  sink_.writeText("sensors:\r\n");
  if (scd_sampled) {
    sink_.writeFormatted("  scd41 temp_c=%.2f rh_pct=%.2f co2_ppm=%.0f age_ms=%llu available=%d "
                         "reads=%lu errors=%lu invalid=%lu\r\n",
                         static_cast<double>(scd.air_temperature_c.value),
                         static_cast<double>(scd.relative_humidity_pct.value),
                         static_cast<double>(scd.co2_ppm.value),
                         static_cast<unsigned long long>(scd.air_temperature_c.age_ms),
                         scd41_.available(),
                         static_cast<unsigned long>(scd41_.successfulMeasurementCount()),
                         static_cast<unsigned long>(scd41_.readErrorCount()),
                         static_cast<unsigned long>(scd41_.invalidMeasurementCount()));
  } else {
    sink_.writeFormatted("  scd41 valid=0 available=%d reads=%lu errors=%lu invalid=%lu\r\n",
                         scd41_.available(),
                         static_cast<unsigned long>(scd41_.successfulMeasurementCount()),
                         static_cast<unsigned long>(scd41_.readErrorCount()),
                         static_cast<unsigned long>(scd41_.invalidMeasurementCount()));
  }

  if (tp357_sampled) {
    sink_.writeFormatted(
        "  tp357 temp_c=%.2f rh_pct=%.2f age_ms=%llu battery_pct=%u battery_valid=%d "
        "packets=%lu accepted=%lu rejected=%lu\r\n",
        static_cast<double>(tp357.temperature_c), static_cast<double>(tp357.relative_humidity_pct),
        static_cast<unsigned long long>(tp357.age_ms), tp357.battery_pct, tp357.has_battery,
        static_cast<unsigned long>(ble_.tp357PacketCount()),
        static_cast<unsigned long>(ble_.tp357AcceptedCount()),
        static_cast<unsigned long>(ble_.tp357RejectedCount()));
  } else {
    sink_.writeFormatted("  tp357 valid=0 packets=%lu accepted=%lu rejected=%lu\r\n",
                         static_cast<unsigned long>(ble_.tp357PacketCount()),
                         static_cast<unsigned long>(ble_.tp357AcceptedCount()),
                         static_cast<unsigned long>(ble_.tp357RejectedCount()));
  }

  if (xiaomi_sampled) {
    sink_.writeFormatted(
        "  xiaomi temp_c=%.2f rh_pct=%.2f age_ms=%llu battery_pct=%u battery_valid=%d "
        "packets=%lu accepted=%lu rejected=%lu\r\n",
        static_cast<double>(xiaomi.temperature_c),
        static_cast<double>(xiaomi.relative_humidity_pct),
        static_cast<unsigned long long>(xiaomi.age_ms), xiaomi.battery_pct, xiaomi.has_battery,
        static_cast<unsigned long>(ble_.xiaomiPacketCount()),
        static_cast<unsigned long>(ble_.xiaomiAcceptedCount()),
        static_cast<unsigned long>(ble_.xiaomiRejectedCount()));
  } else {
    sink_.writeFormatted("  xiaomi valid=0 packets=%lu accepted=%lu rejected=%lu\r\n",
                         static_cast<unsigned long>(ble_.xiaomiPacketCount()),
                         static_cast<unsigned long>(ble_.xiaomiAcceptedCount()),
                         static_cast<unsigned long>(ble_.xiaomiRejectedCount()));
  }

  EuropeWarsawLocalTime local{};
  const bool local_valid = rtc.valid && resolveEuropeWarsawLocalTime(rtc.unix_time_s, local);
  sink_.writeFormatted(
      "  rtc sampled=%d available=%d trusted=%d unix_time_s=%llu reads=%lu errors=%lu "
      "writes=%lu write_errors=%lu untrusted=%lu local_valid=%d",
      rtc_sampled, clock_.available(), rtc.valid && clock_.trusted(),
      static_cast<unsigned long long>(rtc.unix_time_s),
      static_cast<unsigned long>(clock_.successfulReadCount()),
      static_cast<unsigned long>(clock_.readErrorCount()),
      static_cast<unsigned long>(clock_.successfulWriteCount()),
      static_cast<unsigned long>(clock_.writeErrorCount()),
      static_cast<unsigned long>(clock_.untrustedReadCount()), local_valid);
  if (local_valid) {
    sink_.writeFormatted(" local=%04u-%02u-%02uT%02u:%02u:%02u offset_s=%ld dst=%d",
                         static_cast<unsigned>(local.year), static_cast<unsigned>(local.month),
                         static_cast<unsigned>(local.day), static_cast<unsigned>(local.hour),
                         static_cast<unsigned>(local.minute), static_cast<unsigned>(local.second),
                         static_cast<long>(local.utc_offset_seconds), local.daylight_saving);
  }
  sink_.writeText("\r\n");
}

void Stage28ServiceConsoleSystemCommands::printRfList() noexcept {
  sink_.writeFormatted("rf transport_ready=%d automatic_outputs=%s\r\n", rf_diagnostics_.ready(),
                       outputModeName());
  for (const KnownRfDevice& device : kKnownRfDevices) {
    sink_.writeFormatted("  %s label=%s on=%lu/0x%08lX off=%lu/0x%08lX bits=%u protocol=%u "
                         "pulse_us=%u repeat=%u status=%s\r\n",
                         device.physical_name, device.hardware->label,
                         static_cast<unsigned long>(device.hardware->on.key.code),
                         static_cast<unsigned long>(device.hardware->on.key.code),
                         static_cast<unsigned long>(device.hardware->off.key.code),
                         static_cast<unsigned long>(device.hardware->off.key.code),
                         device.hardware->on.key.bit_length, device.hardware->on.key.protocol,
                         device.hardware->on.pulse_us, device.hardware->on.repeat,
                         device.tx_status);
  }
}

void Stage28ServiceConsoleSystemCommands::handleRfReceive(
    const ServiceConsoleCommand& command) noexcept {
  if (!rf_diagnostics_.ready()) {
    sink_.writeText("error: RF transport is not ready; enable GROWBOX_RF433_LOOPBACK_ENABLED\r\n");
    return;
  }
  rf433::ReceiveEvidence evidence{};
  const bool captured = rf_diagnostics_.manualReceive(command.timeout_ms, evidence);
  if (!captured) {
    sink_.writeFormatted("rf_rx captured=0 timeout_ms=%lu\r\n",
                         static_cast<unsigned long>(command.timeout_ms));
    return;
  }
  sink_.writeFormatted("rf_rx captured=%d timeout_ms=%lu symbols=%u overflow=%d decode_status=%u "
                       "code=%lu bits=%u protocol=%u estimated_pulse_us=%u observed_repeats=%u\r\n",
                       evidence.rx_captured, static_cast<unsigned long>(command.timeout_ms),
                       static_cast<unsigned>(evidence.symbol_count), evidence.overflow,
                       static_cast<unsigned>(evidence.decoded.status),
                       static_cast<unsigned long>(evidence.decoded.frame.code),
                       evidence.decoded.frame.bit_length, evidence.decoded.frame.protocol,
                       evidence.decoded.estimated_pulse_us, evidence.decoded.observed_repeats);
}

void Stage28ServiceConsoleSystemCommands::handleRtcSetUnix(const ServiceConsoleCommand& command,
                                                           std::uint64_t now_ms) noexcept {
  if (!clock_.setUnixTimeUtc(command.unix_time_s)) {
    sink_.writeFormatted("rtc_set_utc ok=0 requested_unix_s=%llu reason=write_failed\r\n",
                         static_cast<unsigned long long>(command.unix_time_s));
    return;
  }

  ClimateWallClockSnapshot readback{};
  if (!clock_.sample(now_ms, readback) || !readback.valid) {
    sink_.writeFormatted("rtc_set_utc ok=0 requested_unix_s=%llu reason=readback_untrusted\r\n",
                         static_cast<unsigned long long>(command.unix_time_s));
    return;
  }

  const std::uint64_t delta_s = readback.unix_time_s >= command.unix_time_s
                                    ? readback.unix_time_s - command.unix_time_s
                                    : command.unix_time_s - readback.unix_time_s;
  if (delta_s > 1U) {
    sink_.writeFormatted("rtc_set_utc ok=0 requested_unix_s=%llu readback_unix_s=%llu delta_s=%llu "
                         "reason=readback_mismatch\r\n",
                         static_cast<unsigned long long>(command.unix_time_s),
                         static_cast<unsigned long long>(readback.unix_time_s),
                         static_cast<unsigned long long>(delta_s));
    return;
  }

  EuropeWarsawLocalTime local{};
  const bool local_valid = resolveEuropeWarsawLocalTime(readback.unix_time_s, local);
  sink_.writeFormatted("rtc_set_utc ok=1 requested_unix_s=%llu readback_unix_s=%llu delta_s=%llu "
                       "trusted=1 local_valid=%d",
                       static_cast<unsigned long long>(command.unix_time_s),
                       static_cast<unsigned long long>(readback.unix_time_s),
                       static_cast<unsigned long long>(delta_s), local_valid);
  if (local_valid) {
    sink_.writeFormatted(" local=%04u-%02u-%02uT%02u:%02u:%02u offset_s=%ld dst=%d",
                         static_cast<unsigned>(local.year), static_cast<unsigned>(local.month),
                         static_cast<unsigned>(local.day), static_cast<unsigned>(local.hour),
                         static_cast<unsigned>(local.minute), static_cast<unsigned>(local.second),
                         static_cast<long>(local.utc_offset_seconds), local.daylight_saving);
  }
  sink_.writeText("\r\n");
}

} // namespace growbox::app::climate_io::runtime
