#pragma once

#include "climate/ClimateSemanticOutput.h"
#include "climate/rf433/Rf433HardwareConfig.h"

#include <array>
#include <cstdint>

namespace growbox::app::climate_io::stage28d {

class RfCommandTransmitter {
public:
  virtual ~RfCommandTransmitter() = default;
  virtual bool transmit(const rf433::FrameConfig& frame) noexcept = 0;
};

struct RfOutputEndpointConfig {
  bool enabled{false};
  float on_threshold{0.5F};
};

class Stage28dRfOutputEndpoint final : public ClimateOutputEndpoint {
public:
  Stage28dRfOutputEndpoint(RfOutputEndpointConfig config, RfCommandTransmitter& transmitter) noexcept;

  bool initializeSafeState(std::uint64_t monotonic_ms) noexcept;
  bool write(ClimateEndpointId endpoint, float normalized_level,
             std::uint64_t monotonic_ms) noexcept override;
  bool writeScheduledLight(bool on, std::uint64_t monotonic_ms) noexcept;
  void setSafetyForceExhaust(bool force) noexcept { safety_force_exhaust_ = force; }

  bool stateKnown(ClimateEndpointId endpoint) const noexcept;
  bool stateOn(ClimateEndpointId endpoint) const noexcept;
  std::uint32_t transmitCount() const noexcept { return transmit_count_; }
  std::uint32_t transmitErrorCount() const noexcept { return transmit_error_count_; }

private:
  struct EndpointState {
    bool known{false};
    bool on{false};
    std::uint64_t changed_ms{0U};
  };

  static std::size_t stateIndex(ClimateEndpointId endpoint) noexcept;
  bool applyBinary(ClimateEndpointId endpoint, bool on, std::uint64_t monotonic_ms,
                   bool force_send = false) noexcept;

  RfOutputEndpointConfig config_{};
  RfCommandTransmitter& transmitter_;
  std::array<EndpointState, 3U> states_{};
  bool safety_force_exhaust_{false};
  std::uint32_t transmit_count_{0U};
  std::uint32_t transmit_error_count_{0U};
};

} // namespace growbox::app::climate_io::stage28d
