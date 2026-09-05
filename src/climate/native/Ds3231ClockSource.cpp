#include "climate/native/Ds3231ClockSource.h"

#include "climate/native/Ds3231Codec.h"

#include <array>

namespace growbox::app::climate_io::native {
namespace {

constexpr std::uint8_t kDs3231Address = 0x68U;
constexpr std::uint8_t kTimeRegister = 0x00U;
constexpr std::uint8_t kStatusRegister = 0x0FU;
constexpr std::uint8_t kOscillatorStopFlag = 0x80U;
constexpr std::uint32_t kI2cClockHz = 100'000U;
constexpr int kTimeoutMs = 1000;

} // namespace

Ds3231ClockSource::~Ds3231ClockSource() {
  if (device_ != nullptr) {
    i2c_master_bus_rm_device(device_);
  }
}

bool Ds3231ClockSource::begin(NativeI2cBus& bus) noexcept {
  if (device_ != nullptr) {
    return true;
  }
  const esp_err_t error = bus.addDevice(kDs3231Address, kI2cClockHz, device_);
  available_ = error == ESP_OK;
  trusted_ = false;
  return available_;
}

bool Ds3231ClockSource::sample(std::uint64_t monotonic_ms,
                               ClimateWallClockSnapshot& output) noexcept {
  output = {};
  if (device_ == nullptr) {
    available_ = false;
    trusted_ = false;
    return false;
  }

  std::array<std::uint8_t, 7> registers{};
  const std::uint8_t time_register = kTimeRegister;
  if (i2c_master_transmit_receive(device_, &time_register, 1U, registers.data(), registers.size(),
                                  kTimeoutMs) != ESP_OK) {
    ++read_error_count_;
    available_ = false;
    trusted_ = false;
    return false;
  }

  std::uint8_t status = 0U;
  const std::uint8_t status_register = kStatusRegister;
  if (i2c_master_transmit_receive(device_, &status_register, 1U, &status, 1U, kTimeoutMs) !=
      ESP_OK) {
    ++read_error_count_;
    available_ = false;
    trusted_ = false;
    return false;
  }

  ++successful_read_count_;
  last_successful_read_ms_ = monotonic_ms;
  available_ = true;
  Ds3231DecodedTime decoded{};
  trusted_ = decodeDs3231Time(registers, status, decoded);
  if (trusted_) {
    last_trusted_read_ms_ = monotonic_ms;
    last_trusted_unix_time_s_ = decoded.unix_time_s;
  } else {
    ++untrusted_read_count_;
  }
  output.valid = trusted_;
  output.unix_time_s = trusted_ ? decoded.unix_time_s : 0U;
  return true;
}

bool Ds3231ClockSource::setUnixTimeUtc(std::uint64_t unix_time_s) noexcept {
  if (device_ == nullptr) {
    ++write_error_count_;
    available_ = false;
    trusted_ = false;
    return false;
  }

  std::array<std::uint8_t, 7> registers{};
  if (!encodeDs3231UtcTime(unix_time_s, registers)) {
    ++write_error_count_;
    return false;
  }

  std::array<std::uint8_t, 8> write_buffer{};
  write_buffer[0] = kTimeRegister;
  for (std::size_t index = 0U; index < registers.size(); ++index) {
    write_buffer[index + 1U] = registers[index];
  }
  if (i2c_master_transmit(device_, write_buffer.data(), write_buffer.size(), kTimeoutMs) != ESP_OK) {
    ++write_error_count_;
    available_ = false;
    trusted_ = false;
    return false;
  }

  std::uint8_t status = 0U;
  const std::uint8_t status_register = kStatusRegister;
  if (i2c_master_transmit_receive(device_, &status_register, 1U, &status, 1U, kTimeoutMs) !=
      ESP_OK) {
    ++write_error_count_;
    available_ = false;
    trusted_ = false;
    return false;
  }

  if ((status & kOscillatorStopFlag) != 0U) {
    const std::array<std::uint8_t, 2> status_write{{
        kStatusRegister,
        static_cast<std::uint8_t>(status & static_cast<std::uint8_t>(~kOscillatorStopFlag)),
    }};
    if (i2c_master_transmit(device_, status_write.data(), status_write.size(), kTimeoutMs) != ESP_OK) {
      ++write_error_count_;
      available_ = false;
      trusted_ = false;
      return false;
    }
  }

  ++successful_write_count_;
  available_ = true;
  trusted_ = false;
  return true;
}

} // namespace growbox::app::climate_io::native
