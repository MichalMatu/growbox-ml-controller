#include "climate/native/BleOutsideSource.h"

#include <esp_err.h>
#include <esp_timer.h>
#include <host/ble_gap.h>
#include <host/ble_hs.h>
#include <nimble/nimble_port.h>
#include <nimble/nimble_port_freertos.h>
#include <nvs_flash.h>

#include <cctype>

namespace growbox::app::climate_io::native {
namespace {

BleOutsideSource* g_instance = nullptr;

std::uint64_t monotonicMilliseconds() noexcept {
  return static_cast<std::uint64_t>(esp_timer_get_time()) / 1000U;
}

int hexValue(char value) noexcept {
  if (value >= '0' && value <= '9') {
    return value - '0';
  }
  value = static_cast<char>(std::toupper(static_cast<unsigned char>(value)));
  if (value >= 'A' && value <= 'F') {
    return value - 'A' + 10;
  }
  return -1;
}

} // namespace

BleOutsideSource::~BleOutsideSource() {
  if (g_instance == this) {
    g_instance = nullptr;
  }
  if (mutex_ != nullptr) {
    vSemaphoreDelete(mutex_);
  }
}

bool BleOutsideSource::parseMac(const char* text,
                                std::array<std::uint8_t, 6>& output) noexcept {
  output = {};
  if (text == nullptr) {
    return false;
  }
  for (std::size_t i = 0U; i < output.size(); ++i) {
    const std::size_t offset = i * 3U;
    const int high = hexValue(text[offset]);
    const int low = hexValue(text[offset + 1U]);
    if (high < 0 || low < 0) {
      return false;
    }
    output[i] = static_cast<std::uint8_t>((high << 4) | low);
    if (i + 1U < output.size() && text[offset + 2U] != ':') {
      return false;
    }
  }
  return text[17] == '\0';
}

bool BleOutsideSource::matchesNimbleAddress(
    const std::array<std::uint8_t, 6>& canonical,
    const std::uint8_t* nimble_address) noexcept {
  if (nimble_address == nullptr) {
    return false;
  }
  for (std::size_t i = 0U; i < canonical.size(); ++i) {
    if (canonical[i] != nimble_address[canonical.size() - 1U - i]) {
      return false;
    }
  }
  return true;
}

bool BleOutsideSource::begin(const char* canonical_mac) noexcept {
  if (configured_) {
    return true;
  }
  if (!parseMac(canonical_mac, target_mac_) || g_instance != nullptr) {
    return false;
  }
  mutex_ = xSemaphoreCreateMutex();
  if (mutex_ == nullptr) {
    return false;
  }

  esp_err_t nvs_error = nvs_flash_init();
  if (nvs_error == ESP_ERR_NVS_NO_FREE_PAGES || nvs_error == ESP_ERR_NVS_NEW_VERSION_FOUND) {
    if (nvs_flash_erase() != ESP_OK) {
      return false;
    }
    nvs_error = nvs_flash_init();
  }
  if (nvs_error != ESP_OK) {
    return false;
  }

  const int nimble_error = nimble_port_init();
  if (nimble_error != 0) {
    return false;
  }

  g_instance = this;
  configured_ = true;
  ble_hs_cfg.sync_cb = &BleOutsideSource::onSync;
  nimble_port_freertos_init(&BleOutsideSource::hostTask);
  return true;
}

void BleOutsideSource::hostTask(void*) {
  nimble_port_run();
  nimble_port_freertos_deinit();
}

void BleOutsideSource::onSync() {
  if (g_instance != nullptr) {
    g_instance->startScan();
  }
}

bool BleOutsideSource::startScan() noexcept {
  uint8_t own_address_type = 0U;
  if (ble_hs_id_infer_auto(0, &own_address_type) != 0) {
    scanning_ = false;
    return false;
  }

  ble_gap_disc_params params{};
  params.passive = 1U;
  params.filter_duplicates = 0U;
  params.filter_policy = 0U;
  params.limited = 0U;
  const int error =
      ble_gap_disc(own_address_type, BLE_HS_FOREVER, &params, &BleOutsideSource::gapEvent, this);
  scanning_ = error == 0;
  return scanning_;
}

int BleOutsideSource::gapEvent(struct ble_gap_event* event, void* context) {
  auto* self = static_cast<BleOutsideSource*>(context);
  if (self == nullptr || event == nullptr) {
    return 0;
  }
  if (event->type == BLE_GAP_EVENT_DISC) {
    self->handleAdvertisement(event->disc.addr.val, event->disc.data,
                              event->disc.length_data);
  } else if (event->type == BLE_GAP_EVENT_DISC_COMPLETE) {
    self->scanning_ = false;
    self->startScan();
  }
  return 0;
}

void BleOutsideSource::handleAdvertisement(const std::uint8_t* address,
                                           const std::uint8_t* data,
                                           std::size_t size) noexcept {
  if (!matchesNimbleAddress(target_mac_, address)) {
    return;
  }

  const std::uint64_t now_ms = monotonicMilliseconds();
  if (mutex_ != nullptr && xSemaphoreTake(mutex_, pdMS_TO_TICKS(20)) == pdTRUE) {
    last_packet_seen_ms_ = now_ms;
    xSemaphoreGive(mutex_);
  }

  const std::uint8_t* payload = nullptr;
  std::size_t payload_size = 0U;
  if (!findBthomeV2ServiceData(data, size, payload, payload_size)) {
    return;
  }

  BthomeV2Measurement decoded{};
  if (decodeBthomeV2(payload, payload_size, decoded) != BthomeV2DecodeStatus::Ok) {
    return;
  }
  if (mutex_ == nullptr || xSemaphoreTake(mutex_, pdMS_TO_TICKS(20)) != pdTRUE) {
    return;
  }
  temperature_c_ = decoded.temperature_c;
  humidity_pct_ = decoded.relative_humidity_pct;
  last_measurement_ms_ = now_ms;
  has_measurement_ = true;
  xSemaphoreGive(mutex_);
}

bool BleOutsideSource::sample(std::uint64_t monotonic_ms,
                              OutsideEnvironmentSnapshot& output) noexcept {
  output = {};
  if (!configured_ || mutex_ == nullptr ||
      xSemaphoreTake(mutex_, pdMS_TO_TICKS(20)) != pdTRUE) {
    return false;
  }
  const bool has_measurement = has_measurement_;
  const std::uint64_t last_measurement_ms = last_measurement_ms_;
  const float temperature_c = temperature_c_;
  const float humidity_pct = humidity_pct_;
  xSemaphoreGive(mutex_);

  if (!has_measurement) {
    return false;
  }
  const std::uint64_t age_ms =
      monotonic_ms >= last_measurement_ms ? monotonic_ms - last_measurement_ms : 0U;
  output.air_temperature_c = {temperature_c, true, age_ms};
  output.relative_humidity_pct = {humidity_pct, true, age_ms};
  return true;
}

} // namespace growbox::app::climate_io::native
