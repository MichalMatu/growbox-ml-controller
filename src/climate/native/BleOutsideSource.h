#pragma once

#include "climate/ClimateCompositeInput.h"
#include "climate/native/BthomeV2Decoder.h"

#include <freertos/FreeRTOS.h>
#include <freertos/semphr.h>

#include <array>
#include <atomic>
#include <cstddef>
#include <cstdint>

struct ble_gap_event;

namespace growbox::app::climate_io::native {

class BleOutsideSource final : public OutsideEnvironmentSource {
public:
  BleOutsideSource() = default;
  ~BleOutsideSource();

  bool begin(const char* canonical_mac) noexcept;
  bool sample(std::uint64_t monotonic_ms, OutsideEnvironmentSnapshot& output) noexcept override;

  bool configured() const noexcept {
    return configured_;
  }
  bool scanning() const noexcept {
    return scanning_.load(std::memory_order_relaxed);
  }
  std::uint64_t lastPacketSeenMs() const noexcept;
  std::uint64_t lastValidMeasurementMs() const noexcept;

private:
  static int gapEvent(struct ble_gap_event* event, void* context);
  static void hostTask(void* parameter);
  static void onSync();
  static bool parseMac(const char* text, std::array<std::uint8_t, 6>& output) noexcept;
  static bool matchesNimbleAddress(const std::array<std::uint8_t, 6>& canonical,
                                   const std::uint8_t* nimble_address) noexcept;

  void handleAdvertisement(const std::uint8_t* address, const std::uint8_t* data,
                           std::size_t size) noexcept;
  bool startScan() noexcept;

  std::array<std::uint8_t, 6> target_mac_{};
  SemaphoreHandle_t mutex_ = nullptr;
  bool configured_ = false;
  std::atomic_bool scanning_{false};
  bool has_measurement_ = false;
  std::uint64_t last_packet_seen_ms_ = 0U;
  std::uint64_t last_measurement_ms_ = 0U;
  float temperature_c_ = 0.0F;
  float humidity_pct_ = 0.0F;
};

} // namespace growbox::app::climate_io::native
