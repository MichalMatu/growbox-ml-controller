#include "climate/native/BleClimateScanner.h"

#include <esp_err.h>
#include <esp_timer.h>
#include <host/ble_hs.h>
#include <nimble/nimble_port.h>
#include <nimble/nimble_port_freertos.h>
#include <nvs_flash.h>

namespace growbox::app::climate_io::native {
namespace {

BleClimateScanner* g_instance = nullptr;

std::uint64_t monotonicMilliseconds() noexcept {
  return static_cast<std::uint64_t>(esp_timer_get_time()) / 1000U;
}

} // namespace

BleClimateScanner::~BleClimateScanner() {
  if (g_instance == this) {
    g_instance = nullptr;
  }
  if (mutex_ != nullptr) {
    vSemaphoreDelete(mutex_);
  }
}

bool BleClimateScanner::begin(const char* tp357_inside_mac,
                              const char* xiaomi_nearby_mac) noexcept {
  if (configured_) {
    return true;
  }
  if (g_instance != nullptr || !state_.configure(tp357_inside_mac, xiaomi_nearby_mac)) {
    return false;
  }

  mutex_ = xSemaphoreCreateMutex();
  if (mutex_ == nullptr) {
    return false;
  }

  esp_err_t nvs_error = nvs_flash_init();
  if (nvs_error == ESP_ERR_NVS_NO_FREE_PAGES || nvs_error == ESP_ERR_NVS_NEW_VERSION_FOUND) {
    if (nvs_flash_erase() != ESP_OK) {
      vSemaphoreDelete(mutex_);
      mutex_ = nullptr;
      return false;
    }
    nvs_error = nvs_flash_init();
  }
  if (nvs_error != ESP_OK || nimble_port_init() != 0) {
    vSemaphoreDelete(mutex_);
    mutex_ = nullptr;
    return false;
  }

  g_instance = this;
  configured_ = true;
  ble_hs_cfg.sync_cb = &BleClimateScanner::onSync;
  nimble_port_freertos_init(&BleClimateScanner::hostTask);
  return true;
}

void BleClimateScanner::hostTask(void*) {
  nimble_port_run();
  nimble_port_freertos_deinit();
}

void BleClimateScanner::onSync() {
  if (g_instance != nullptr) {
    g_instance->startScan();
  }
}

bool BleClimateScanner::startScan() noexcept {
  uint8_t own_address_type = 0U;
  if (ble_hs_id_infer_auto(0, &own_address_type) != 0) {
    scanning_.store(false, std::memory_order_relaxed);
    scan_start_error_count_.fetch_add(1U, std::memory_order_relaxed);
    return false;
  }

  struct ble_gap_disc_params params{};
  params.passive = 1U;
  params.filter_duplicates = 0U;
  params.filter_policy = 0U;
  params.limited = 0U;
  const int error =
      ble_gap_disc(own_address_type, BLE_HS_FOREVER, &params, &BleClimateScanner::gapEvent, this);
  scanning_.store(error == 0, std::memory_order_relaxed);
  if (error == 0) {
    scan_start_count_.fetch_add(1U, std::memory_order_relaxed);
    return true;
  }
  scan_start_error_count_.fetch_add(1U, std::memory_order_relaxed);
  return false;
}

int BleClimateScanner::gapEvent(struct ble_gap_event* event, void* context) {
  auto* self = static_cast<BleClimateScanner*>(context);
  if (self == nullptr || event == nullptr) {
    return 0;
  }
  if (event->type == BLE_GAP_EVENT_DISC) {
    self->handleAdvertisement(event->disc.addr.val, event->disc.data, event->disc.length_data);
  } else if (event->type == BLE_GAP_EVENT_DISC_COMPLETE) {
    self->scan_complete_count_.fetch_add(1U, std::memory_order_relaxed);
    self->scan_restart_count_.fetch_add(1U, std::memory_order_relaxed);
    self->scanning_.store(false, std::memory_order_relaxed);
    self->startScan();
  }
  return 0;
}

void BleClimateScanner::handleAdvertisement(const std::uint8_t* address, const std::uint8_t* data,
                                            std::size_t size) noexcept {
  if (mutex_ == nullptr || xSemaphoreTake(mutex_, pdMS_TO_TICKS(20)) != pdTRUE) {
    advertisement_lock_drop_count_.fetch_add(1U, std::memory_order_relaxed);
    return;
  }
  static_cast<void>(state_.ingestNimbleAdvertisement(address, data, size, monotonicMilliseconds()));
  xSemaphoreGive(mutex_);
}

bool BleClimateScanner::sampleTp357(std::uint64_t monotonic_ms,
                                    BleClimateReading& output) const noexcept {
  output = {};
  if (mutex_ == nullptr || xSemaphoreTake(mutex_, pdMS_TO_TICKS(20)) != pdTRUE) {
    return false;
  }
  const bool sampled = state_.sampleTp357(monotonic_ms, output);
  xSemaphoreGive(mutex_);
  return sampled;
}

bool BleClimateScanner::sampleXiaomi(std::uint64_t monotonic_ms,
                                     BleClimateReading& output) const noexcept {
  output = {};
  if (mutex_ == nullptr || xSemaphoreTake(mutex_, pdMS_TO_TICKS(20)) != pdTRUE) {
    return false;
  }
  const bool sampled = state_.sampleXiaomi(monotonic_ms, output);
  xSemaphoreGive(mutex_);
  return sampled;
}

std::uint64_t BleClimateScanner::tp357LastPacketSeenMs() const noexcept {
  if (mutex_ == nullptr || xSemaphoreTake(mutex_, pdMS_TO_TICKS(20)) != pdTRUE) {
    return 0U;
  }
  const std::uint64_t value = state_.tp357LastPacketSeenMs();
  xSemaphoreGive(mutex_);
  return value;
}

std::uint64_t BleClimateScanner::tp357LastValidMeasurementMs() const noexcept {
  if (mutex_ == nullptr || xSemaphoreTake(mutex_, pdMS_TO_TICKS(20)) != pdTRUE) {
    return 0U;
  }
  const std::uint64_t value = state_.tp357LastValidMeasurementMs();
  xSemaphoreGive(mutex_);
  return value;
}

std::uint64_t BleClimateScanner::xiaomiLastPacketSeenMs() const noexcept {
  if (mutex_ == nullptr || xSemaphoreTake(mutex_, pdMS_TO_TICKS(20)) != pdTRUE) {
    return 0U;
  }
  const std::uint64_t value = state_.xiaomiLastPacketSeenMs();
  xSemaphoreGive(mutex_);
  return value;
}

std::uint64_t BleClimateScanner::xiaomiLastValidMeasurementMs() const noexcept {
  if (mutex_ == nullptr || xSemaphoreTake(mutex_, pdMS_TO_TICKS(20)) != pdTRUE) {
    return 0U;
  }
  const std::uint64_t value = state_.xiaomiLastValidMeasurementMs();
  xSemaphoreGive(mutex_);
  return value;
}

std::uint32_t BleClimateScanner::tp357PacketCount() const noexcept {
  if (mutex_ == nullptr || xSemaphoreTake(mutex_, pdMS_TO_TICKS(20)) != pdTRUE) {
    return 0U;
  }
  const std::uint32_t value = state_.tp357PacketCount();
  xSemaphoreGive(mutex_);
  return value;
}

std::uint32_t BleClimateScanner::tp357AcceptedCount() const noexcept {
  if (mutex_ == nullptr || xSemaphoreTake(mutex_, pdMS_TO_TICKS(20)) != pdTRUE) {
    return 0U;
  }
  const std::uint32_t value = state_.tp357AcceptedCount();
  xSemaphoreGive(mutex_);
  return value;
}

std::uint32_t BleClimateScanner::tp357RejectedCount() const noexcept {
  if (mutex_ == nullptr || xSemaphoreTake(mutex_, pdMS_TO_TICKS(20)) != pdTRUE) {
    return 0U;
  }
  const std::uint32_t value = state_.tp357RejectedCount();
  xSemaphoreGive(mutex_);
  return value;
}

std::uint32_t BleClimateScanner::xiaomiPacketCount() const noexcept {
  if (mutex_ == nullptr || xSemaphoreTake(mutex_, pdMS_TO_TICKS(20)) != pdTRUE) {
    return 0U;
  }
  const std::uint32_t value = state_.xiaomiPacketCount();
  xSemaphoreGive(mutex_);
  return value;
}

std::uint32_t BleClimateScanner::xiaomiAcceptedCount() const noexcept {
  if (mutex_ == nullptr || xSemaphoreTake(mutex_, pdMS_TO_TICKS(20)) != pdTRUE) {
    return 0U;
  }
  const std::uint32_t value = state_.xiaomiAcceptedCount();
  xSemaphoreGive(mutex_);
  return value;
}

std::uint32_t BleClimateScanner::xiaomiRejectedCount() const noexcept {
  if (mutex_ == nullptr || xSemaphoreTake(mutex_, pdMS_TO_TICKS(20)) != pdTRUE) {
    return 0U;
  }
  const std::uint32_t value = state_.xiaomiRejectedCount();
  xSemaphoreGive(mutex_);
  return value;
}

} // namespace growbox::app::climate_io::native
