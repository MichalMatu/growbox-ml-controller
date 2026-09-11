#include "climate/native/BleClimateState.h"

#include "climate/native/BthomeV2Decoder.h"
#include "climate/native/Tp357Decoder.h"

#include <cctype>
#include <cstring>

namespace growbox::app::climate_io::native {
namespace {

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

bool BleClimateState::parseMac(const char* text, std::array<std::uint8_t, 6>& output) noexcept {
  output = {};
  if (text == nullptr || std::strlen(text) != 17U) {
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
  return true;
}

bool BleClimateState::matchesNimbleAddress(const std::array<std::uint8_t, 6>& canonical,
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

bool BleClimateState::configure(const char* tp357_inside_mac,
                                const char* xiaomi_nearby_mac) noexcept {
  TargetState tp357{};
  TargetState xiaomi{};
  if (!parseMac(tp357_inside_mac, tp357.canonical_mac) ||
      !parseMac(xiaomi_nearby_mac, xiaomi.canonical_mac) ||
      tp357.canonical_mac == xiaomi.canonical_mac) {
    configured_ = false;
    tp357_ = {};
    xiaomi_ = {};
    return false;
  }
  tp357_ = tp357;
  xiaomi_ = xiaomi;
  configured_ = true;
  return true;
}

BleClimateIngestResult BleClimateState::ingestNimbleAdvertisement(
    const std::uint8_t* nimble_address, const std::uint8_t* advertisement,
    std::size_t advertisement_size, std::uint64_t monotonic_ms) noexcept {
  if (!configured_ || nimble_address == nullptr) {
    return BleClimateIngestResult::Ignored;
  }

  if (matchesNimbleAddress(tp357_.canonical_mac, nimble_address)) {
    ++tp357_.packet_count;
    tp357_.last_packet_seen_ms = monotonic_ms;
    Tp357Measurement decoded{};
    if (decodeTp357Advertisement(advertisement, advertisement_size, decoded) !=
        Tp357DecodeStatus::Ok) {
      ++tp357_.rejected_count;
      return BleClimateIngestResult::PacketRejected;
    }
    tp357_.temperature_c = decoded.temperature_c;
    tp357_.relative_humidity_pct = decoded.relative_humidity_pct;
    tp357_.battery_pct = decoded.battery_pct;
    tp357_.has_battery = true;
    tp357_.last_measurement_ms = monotonic_ms;
    tp357_.has_measurement = true;
    ++tp357_.accepted_count;
    return BleClimateIngestResult::MeasurementAccepted;
  }

  if (matchesNimbleAddress(xiaomi_.canonical_mac, nimble_address)) {
    ++xiaomi_.packet_count;
    xiaomi_.last_packet_seen_ms = monotonic_ms;
    const std::uint8_t* payload = nullptr;
    std::size_t payload_size = 0U;
    if (!findBthomeV2ServiceData(advertisement, advertisement_size, payload, payload_size)) {
      ++xiaomi_.rejected_count;
      return BleClimateIngestResult::PacketRejected;
    }
    BthomeV2Measurement decoded{};
    if (decodeBthomeV2(payload, payload_size, decoded) != BthomeV2DecodeStatus::Ok) {
      ++xiaomi_.rejected_count;
      return BleClimateIngestResult::PacketRejected;
    }
    xiaomi_.temperature_c = decoded.temperature_c;
    xiaomi_.relative_humidity_pct = decoded.relative_humidity_pct;
    xiaomi_.battery_pct = decoded.battery_pct;
    xiaomi_.has_battery = decoded.has_battery;
    xiaomi_.last_measurement_ms = monotonic_ms;
    xiaomi_.has_measurement = true;
    ++xiaomi_.accepted_count;
    return BleClimateIngestResult::MeasurementAccepted;
  }

  return BleClimateIngestResult::Ignored;
}

bool BleClimateState::sampleTarget(const TargetState& target, std::uint64_t monotonic_ms,
                                   BleClimateReading& output) noexcept {
  output = {};
  if (!target.has_measurement) {
    return false;
  }
  output.temperature_c = target.temperature_c;
  output.relative_humidity_pct = target.relative_humidity_pct;
  output.battery_pct = target.battery_pct;
  output.has_battery = target.has_battery;
  output.packet_seen_ms = target.last_packet_seen_ms;
  output.valid_measurement_ms = target.last_measurement_ms;
  output.age_ms =
      monotonic_ms >= target.last_measurement_ms ? monotonic_ms - target.last_measurement_ms : 0U;
  return true;
}

bool BleClimateState::sampleTp357(std::uint64_t monotonic_ms,
                                  BleClimateReading& output) const noexcept {
  return sampleTarget(tp357_, monotonic_ms, output);
}

bool BleClimateState::sampleXiaomi(std::uint64_t monotonic_ms,
                                   BleClimateReading& output) const noexcept {
  return sampleTarget(xiaomi_, monotonic_ms, output);
}

std::uint64_t BleClimateState::tp357LastPacketSeenMs() const noexcept {
  return tp357_.last_packet_seen_ms;
}

std::uint64_t BleClimateState::tp357LastValidMeasurementMs() const noexcept {
  return tp357_.last_measurement_ms;
}

std::uint64_t BleClimateState::xiaomiLastPacketSeenMs() const noexcept {
  return xiaomi_.last_packet_seen_ms;
}

std::uint64_t BleClimateState::xiaomiLastValidMeasurementMs() const noexcept {
  return xiaomi_.last_measurement_ms;
}

std::uint32_t BleClimateState::tp357PacketCount() const noexcept {
  return tp357_.packet_count;
}

std::uint32_t BleClimateState::tp357AcceptedCount() const noexcept {
  return tp357_.accepted_count;
}

std::uint32_t BleClimateState::tp357RejectedCount() const noexcept {
  return tp357_.rejected_count;
}

std::uint32_t BleClimateState::xiaomiPacketCount() const noexcept {
  return xiaomi_.packet_count;
}

std::uint32_t BleClimateState::xiaomiAcceptedCount() const noexcept {
  return xiaomi_.accepted_count;
}

std::uint32_t BleClimateState::xiaomiRejectedCount() const noexcept {
  return xiaomi_.rejected_count;
}

} // namespace growbox::app::climate_io::native
