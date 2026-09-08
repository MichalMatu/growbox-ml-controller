#pragma once

#include "climate/ClimateTypes.h"
#include "climate/output/OutputIntents.h"

#include <cstdint>

namespace growbox::app::climate_io::stage28d {

struct LampSafetyConfig {
  float trip_temperature_c{28.0F};
  float recovery_temperature_c{26.0F};
  std::uint64_t recovery_hold_ms{600'000U};
  float light_on_threshold{0.5F};
  std::uint64_t temperature_timeout_ms{::growbox::climate::kDefaultSensorTimeoutMs};
};

enum class LampSafetyReason : std::uint8_t {
  Safe = 0U,
  TimerOff,
  TemperatureUnavailable,
  OverTemperature,
  RecoveryHold,
  InvalidConfig,
};

struct LampSafetyInput {
  float scheduled_light_level{0.0F};
  ::growbox::climate::MeasuredValue inside_temperature_c{};
  bool exhaust_fan_available{false};
  std::uint64_t monotonic_ms{0U};
};

struct LampSafetyDecision {
  bool schedule_requests_lamp_on{false};
  bool effective_lamp_on{false};
  bool force_exhaust_on{false};
  bool thermal_latched{false};
  bool recovery_running{false};
  std::uint64_t recovery_started_ms{0U};
  LampSafetyReason reason{LampSafetyReason::Safe};
};

struct LampSafetyEnvelopeSnapshot {
  ::growbox::app::output::SafetyEnvelope envelope{};
  LampSafetyReason reason{LampSafetyReason::Safe};
  bool thermal_latched{false};
  bool recovery_running{false};
  std::uint64_t recovery_started_ms{0U};
  std::uint64_t evidence_monotonic_ms{0U};
  std::uint64_t temperature_age_ms{0U};
};

bool buildLampSafetyEnvelope(const LampSafetyInput& input, const LampSafetyDecision& decision,
                             std::uint64_t sequence,
                             LampSafetyEnvelopeSnapshot& output) noexcept;

bool validateLampSafetyConfig(const LampSafetyConfig& config) noexcept;

class LampSafetyController {
public:
  explicit LampSafetyController(LampSafetyConfig config = {}) noexcept;

  LampSafetyDecision evaluate(const LampSafetyInput& input) noexcept;
  void reset() noexcept;
  const LampSafetyConfig& config() const noexcept { return config_; }

private:
  LampSafetyConfig config_{};
  bool thermal_latched_{false};
  bool recovery_running_{false};
  std::uint64_t recovery_started_ms_{0U};
};

} // namespace growbox::app::climate_io::stage28d
