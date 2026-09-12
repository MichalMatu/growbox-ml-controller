#pragma once

#include <array>
#include <cstddef>
#include <cstdint>

namespace growbox::app::climate_io::native {

struct BleClimateReading {
  float temperature_c = 0.0F;
  float relative_humidity_pct = 0.0F;
  std::uint8_t battery_pct = 0U;
  bool has_battery = false;
  std::uint64_t packet_seen_ms = 0U;
  std::uint64_t valid_measurement_ms = 0U;
  std::uint64_t age_ms = 0U;
};

enum class BleClimateIngestResult : std::uint8_t {
  Ignored = 0U,
  PacketRejected,
  MeasurementAccepted,
};

class BleClimateState {
public:
  bool configure(const char* tp357_inside_mac, const char* xiaomi_nearby_mac) noexcept;

  bool configured() const noexcept {
    return configured_;
  }

  BleClimateIngestResult ingestNimbleAdvertisement(const std::uint8_t* nimble_address,
                                                   const std::uint8_t* advertisement,
                                                   std::size_t advertisement_size,
                                                   std::uint64_t monotonic_ms) noexcept;

  bool sampleTp357(std::uint64_t monotonic_ms, BleClimateReading& output) const noexcept;
  bool sampleXiaomi(std::uint64_t monotonic_ms, BleClimateReading& output) const noexcept;

  std::uint64_t tp357LastPacketSeenMs() const noexcept;
  std::uint64_t tp357LastValidMeasurementMs() const noexcept;
  std::uint64_t xiaomiLastPacketSeenMs() const noexcept;
  std::uint64_t xiaomiLastValidMeasurementMs() const noexcept;

  std::uint32_t tp357PacketCount() const noexcept;
  std::uint32_t tp357AcceptedCount() const noexcept;
  std::uint32_t tp357RejectedCount() const noexcept;
  std::uint32_t xiaomiPacketCount() const noexcept;
  std::uint32_t xiaomiAcceptedCount() const noexcept;
  std::uint32_t xiaomiRejectedCount() const noexcept;

private:
  struct TargetState {
    std::array<std::uint8_t, 6> canonical_mac{};
    bool has_measurement = false;
    std::uint64_t last_packet_seen_ms = 0U;
    std::uint64_t last_measurement_ms = 0U;
    float temperature_c = 0.0F;
    float relative_humidity_pct = 0.0F;
    std::uint8_t battery_pct = 0U;
    bool has_battery = false;
    std::uint32_t packet_count = 0U;
    std::uint32_t accepted_count = 0U;
    std::uint32_t rejected_count = 0U;
  };

  static bool parseMac(const char* text, std::array<std::uint8_t, 6>& output) noexcept;
  static bool matchesNimbleAddress(const std::array<std::uint8_t, 6>& canonical,
                                   const std::uint8_t* nimble_address) noexcept;
  static bool sampleTarget(const TargetState& target, std::uint64_t monotonic_ms,
                           BleClimateReading& output) noexcept;

  bool configured_ = false;
  TargetState tp357_{};
  TargetState xiaomi_{};
};

} // namespace growbox::app::climate_io::native
