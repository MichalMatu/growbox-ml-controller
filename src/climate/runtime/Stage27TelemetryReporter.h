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

struct Stage27PhysicalOutputSnapshot {
  bool real_outputs_active{false};
  bool light_on{false};
  bool exhaust_on{false};
  bool humidifier_on{false};
  bool thermal_safety_latched{false};
  bool safety_force_exhaust{false};
  std::uint32_t safety_reason{0U};
  std::uint32_t arbiter_transition_count{0U};
  std::uint32_t arbiter_dwell_hold_count{0U};
  std::uint32_t arbiter_safety_override_count{0U};
};

class Stage27TelemetryReporter final {
public:
  Stage27TelemetryReporter(native::BleClimateScanner& ble, native::Scd41InsideSource& scd41,
                           native::Ds3231ClockSource& clock,
                           storage::Stage27TelemetryLogger& storage_logger,
                           bool storage_logger_ready, std::int32_t reset_reason) noexcept;

  void record(std::uint64_t now_ms, const ::growbox::climate::ClimateLoopResult& loop_result,
              const ::growbox::climate::ClimateRuntimeDecision& decision,
              const Stage27PhysicalOutputSnapshot& physical_outputs = {}) noexcept;

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
