#pragma once

#include "climate/ClimateCompositeInput.h"
#include "climate/native/BleClimateScanner.h"
#include "climate/native/Scd41InsideSource.h"

#include <cstdint>

namespace growbox::app::climate_io::runtime {

class LockedFakeRoleDriver final : public ClimateRoleDriver {
public:
  bool apply(ClimateActuatorRole role, float level, std::uint64_t monotonic_ms) noexcept override;
};

class Stage27InsideSource final : public InsideEnvironmentSource {
public:
  Stage27InsideSource(native::BleClimateScanner& ble, native::Scd41InsideSource& scd41) noexcept;

  bool sample(std::uint64_t monotonic_ms, InsideEnvironmentSnapshot& output) noexcept override;

private:
  native::BleClimateScanner& ble_;
  native::Scd41InsideSource& scd41_;
};

class Stage27NearbySource final : public OutsideEnvironmentSource {
public:
  explicit Stage27NearbySource(native::BleClimateScanner& ble) noexcept;

  bool sample(std::uint64_t monotonic_ms, OutsideEnvironmentSnapshot& output) noexcept override;

private:
  native::BleClimateScanner& ble_;
};

class FixedStage27ScheduleConfigSource final : public ClimateScheduleConfigSource {
public:
  bool resolve(std::uint64_t monotonic_ms, const ClimateWallClockSnapshot& clock,
               ClimateScheduleConfigSnapshot& output) noexcept override;
};

::growbox::climate::ClimateRuntimeConfig defaultRuntimeConfig() noexcept;

} // namespace growbox::app::climate_io::runtime
