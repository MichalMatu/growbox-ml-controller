#pragma once

#include "climate/ClimateIoAdapters.h"

#include <cstdint>

namespace growbox::app::climate_io {

struct InsideEnvironmentSnapshot {
  ::growbox::climate::MeasuredValue air_temperature_c{};
  ::growbox::climate::MeasuredValue relative_humidity_pct{};
  ::growbox::climate::MeasuredValue co2_ppm{};
};

struct OutsideEnvironmentSnapshot {
  ::growbox::climate::MeasuredValue air_temperature_c{};
  ::growbox::climate::MeasuredValue relative_humidity_pct{};
};

struct ClimateWallClockSnapshot {
  bool valid = false;
  std::uint64_t unix_time_s = 0U;
};

struct ClimateScheduleConfigSnapshot {
  ::growbox::climate::HumidityControlMode humidity_control_mode =
      ::growbox::climate::HumidityControlMode::Rh;
  ::growbox::climate::ClimateTargets targets{};
  ::growbox::climate::ClimateSchedule schedule{};
  ::growbox::climate::ClimateCapabilities capabilities{};
  std::uint64_t sensor_timeout_ms = ::growbox::climate::kDefaultSensorTimeoutMs;
};

class InsideEnvironmentSource {
public:
  virtual ~InsideEnvironmentSource() = default;
  virtual bool sample(std::uint64_t monotonic_ms, InsideEnvironmentSnapshot& output) noexcept = 0;
};

class OutsideEnvironmentSource {
public:
  virtual ~OutsideEnvironmentSource() = default;
  virtual bool sample(std::uint64_t monotonic_ms, OutsideEnvironmentSnapshot& output) noexcept = 0;
};

class ClimateClockSource {
public:
  virtual ~ClimateClockSource() = default;
  virtual bool sample(std::uint64_t monotonic_ms, ClimateWallClockSnapshot& output) noexcept = 0;
};

class ClimateScheduleConfigSource {
public:
  virtual ~ClimateScheduleConfigSource() = default;
  virtual bool resolve(std::uint64_t monotonic_ms, const ClimateWallClockSnapshot& clock,
                       ClimateScheduleConfigSnapshot& output) noexcept = 0;
};

class CompositeClimateSnapshotProvider final : public ClimateSnapshotProvider {
public:
  CompositeClimateSnapshotProvider(InsideEnvironmentSource& inside_source,
                                   OutsideEnvironmentSource& outside_source,
                                   ClimateClockSource& clock_source,
                                   ClimateScheduleConfigSource& schedule_config_source) noexcept
      : inside_source_(inside_source), outside_source_(outside_source), clock_source_(clock_source),
        schedule_config_source_(schedule_config_source) {}

  bool snapshot(std::uint64_t monotonic_ms, ClimateInputSnapshot& output) noexcept override;

private:
  InsideEnvironmentSource& inside_source_;
  OutsideEnvironmentSource& outside_source_;
  ClimateClockSource& clock_source_;
  ClimateScheduleConfigSource& schedule_config_source_;
};

} // namespace growbox::app::climate_io
