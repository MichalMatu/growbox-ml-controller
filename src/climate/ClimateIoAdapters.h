#pragma once

#include "climate/ClimateControlLoop.h"

#include <cstdint>

namespace growbox::app::climate_io {

struct ClimateInputSnapshot {
  ::growbox::climate::ClimateMeasurements measurements{};
  ::growbox::climate::HumidityControlMode humidity_control_mode =
      ::growbox::climate::HumidityControlMode::Rh;
  ::growbox::climate::ClimateTargets targets{};
  ::growbox::climate::ClimateSchedule schedule{};
  ::growbox::climate::ClimateCapabilities capabilities{};
  std::uint64_t sensor_timeout_ms = ::growbox::climate::kDefaultSensorTimeoutMs;
};

class ClimateSnapshotProvider {
public:
  virtual ~ClimateSnapshotProvider() = default;
  virtual bool snapshot(std::uint64_t monotonic_ms, ClimateInputSnapshot& output) noexcept = 0;
};

enum class ClimateActuatorRole : std::uint8_t {
  Heater = 0U,
  Cooler,
  ExhaustFan,
  Humidifier,
  Dehumidifier,
  Co2Doser,
};

class ClimateRoleDriver {
public:
  virtual ~ClimateRoleDriver() = default;
  virtual bool apply(ClimateActuatorRole role, float level,
                     std::uint64_t monotonic_ms) noexcept = 0;

  // Most drivers are exact: accepted level equals requested level. Binary/dwell
  // arbiters override this to report the state that is actually being held.
  virtual float appliedLevel(ClimateActuatorRole, float requested_level) const noexcept {
    return requested_level;
  }

  // Fail-safe OFF bypasses normal arbitration where supported.
  virtual bool forceSafeOff(ClimateActuatorRole role, std::uint64_t monotonic_ms) noexcept {
    return apply(role, 0.0F, monotonic_ms);
  }
};

class ClimateInputAdapter final : public ::growbox::climate::ClimateInputSource {
public:
  explicit ClimateInputAdapter(ClimateSnapshotProvider& provider) noexcept : provider_(provider) {}

  bool sample(std::uint64_t monotonic_ms,
              ::growbox::climate::ClimateControllerInput& input) noexcept override;

private:
  ClimateSnapshotProvider& provider_;
};

class ClimateActuatorAdapter final : public ::growbox::climate::ClimateActuatorSink {
public:
  explicit ClimateActuatorAdapter(ClimateRoleDriver& driver) noexcept : driver_(driver) {}

  bool apply(const ::growbox::climate::ClimatePolicyRequest& request,
             std::uint64_t monotonic_ms) noexcept override;
  bool applyAndReport(const ::growbox::climate::ClimatePolicyRequest& request,
                      std::uint64_t monotonic_ms,
                      ::growbox::climate::ClimatePolicyRequest& confirmed_applied) noexcept override;
  bool applyFailSafeOff(std::uint64_t monotonic_ms) noexcept override;

private:
  ClimateRoleDriver& driver_;
};

} // namespace growbox::app::climate_io
