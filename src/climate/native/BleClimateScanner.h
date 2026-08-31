#pragma once

#include "climate/native/BleClimateState.h"

#include <freertos/FreeRTOS.h>
#include <freertos/semphr.h>

#include <atomic>
#include <cstddef>
#include <cstdint>

struct ble_gap_event;

namespace growbox::app::climate_io::native {

class BleClimateScanner {
public:
  BleClimateScanner() = default;
  ~BleClimateScanner();

  bool begin(const char* tp357_inside_mac, const char* xiaomi_nearby_mac) noexcept;
  bool sampleTp357(std::uint64_t monotonic_ms, BleClimateReading& output) const noexcept;
  bool sampleXiaomi(std::uint64_t monotonic_ms, BleClimateReading& output) const noexcept;

  bool configured() const noexcept {
    return configured_;
  }
  bool scanning() const noexcept {
    return scanning_.load(std::memory_order_relaxed);
  }

  std::uint64_t tp357LastPacketSeenMs() const noexcept;
  std::uint64_t tp357LastValidMeasurementMs() const noexcept;
  std::uint64_t xiaomiLastPacketSeenMs() const noexcept;
  std::uint64_t xiaomiLastValidMeasurementMs() const noexcept;

private:
  static int gapEvent(struct ble_gap_event* event, void* context);
  static void hostTask(void* parameter);
  static void onSync();

  void handleAdvertisement(const std::uint8_t* address, const std::uint8_t* data,
                           std::size_t size) noexcept;
  bool startScan() noexcept;

  mutable SemaphoreHandle_t mutex_ = nullptr;
  BleClimateState state_{};
  bool configured_ = false;
  std::atomic_bool scanning_{false};
};

} // namespace growbox::app::climate_io::native
