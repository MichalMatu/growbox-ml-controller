#pragma once

#include "climate/application/ClimateApplication.h"
#include "climate/application/ClimateCompositeInput.h"
#include "climate/input/ble/BleClimateScanner.h"
#include "climate/input/rtc/Ds3231ClockSource.h"
#include "climate/input/sensors/Scd41InsideSource.h"
#include "climate/output/OutputExecutionTelemetry.h"
#include "climate/storage/Stage27TelemetryLogger.h"
#include "climate/telemetry/Stage27Telemetry.h"

#include <cstdint>

namespace growbox::app::climate_io::runtime {

class Stage27TelemetryReporter final {
public:
  Stage27TelemetryReporter(native::BleClimateScanner& ble, native::Scd41InsideSource& scd41,
                           native::Ds3231ClockSource& clock,
                           storage::Stage27TelemetryLogger& storage_logger,
                           bool storage_logger_ready, std::int32_t reset_reason) noexcept;

  void record(std::uint64_t now_ms, const ::growbox::climate::ClimateLoopResult& loop_result,
              const ::growbox::climate::ClimateRuntimeDecision& decision,
              const ::growbox::app::output::OutputExecutionTelemetrySnapshot& output_execution =
                  {}) noexcept;

private:
  void logRecord(const telemetry::Stage27TelemetrySnapshot& snapshot,
                 const storage::Stage27StorageStatus& storage_status) noexcept;

  native::BleClimateScanner& ble_;
  native::Scd41InsideSource& scd41_;
  native::Ds3231ClockSource& clock_;
  storage::Stage27TelemetryLogger& storage_logger_;
  bool storage_logger_ready_{false};
  std::int32_t reset_reason_{0};
  std::uint32_t heartbeat_sequence_{0U};
  std::uint32_t heap_integrity_check_count_{0U};
  std::uint32_t heap_integrity_failure_count_{0U};
};

} // namespace growbox::app::climate_io::runtime
