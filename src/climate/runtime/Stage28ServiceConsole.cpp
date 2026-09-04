#include "climate/runtime/Stage28ServiceConsole.h"

#include "climate/rf433/Rf433HardwareConfig.h"

#include <driver/uart.h>
#include <esp_heap_caps.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>
#include <sdkconfig.h>

#include <array>
#include <cstdarg>
#include <cstdio>
#include <cstring>

namespace growbox::app::climate_io::runtime {
namespace {

struct KnownRfDevice {
  ServiceConsoleRfDevice id;
  const char* physical_name;
  const rf433::RemoteSocketHardwareConfig* hardware;
  const char* tx_status;
};

constexpr std::array<KnownRfDevice, 3U> kKnownRfDevices{{
    {ServiceConsoleRfDevice::Lamp, "lamp", &rf433::kRemoteSocket2,
     "captured-profile; physical socket validation pending"},
    {ServiceConsoleRfDevice::Fan, "fan", &rf433::kRemoteSocket1,
     "physically validated at 575us/repeat10"},
    {ServiceConsoleRfDevice::Humidifier, "humidifier", &rf433::kRemoteSocket3,
     "captured-profile; physical socket validation pending"},
}};

#if !defined(CONFIG_ESP_CONSOLE_UART_NUM)
#error "Stage28 service console requires an ESP-IDF UART primary console"
#endif

constexpr uart_port_t kServiceConsoleUart = static_cast<uart_port_t>(CONFIG_ESP_CONSOLE_UART_NUM);
constexpr int kServiceConsoleRxBufferBytes = 1024;
constexpr int kServiceConsoleTxBufferBytes = 2048;

const KnownRfDevice* findKnownDevice(ServiceConsoleRfDevice id) noexcept {
  for (const KnownRfDevice& device : kKnownRfDevices) {
    if (device.id == id) {
      return &device;
    }
  }
  return nullptr;
}

} // namespace

Stage28ServiceConsole::Stage28ServiceConsole(Config config, native::BleClimateScanner& ble,
                                             native::Scd41InsideSource& scd41,
                                             native::Ds3231ClockSource& clock,
                                             Stage28RfDiagnostics& rf_diagnostics) noexcept
    : config_(config), ble_(ble), scd41_(scd41), clock_(clock), rf_diagnostics_(rf_diagnostics) {}

bool Stage28ServiceConsole::begin() noexcept {
  if (!config_.enabled) {
    return false;
  }

  // Use the configured primary console UART driver for service-console RX/TX.
  // Normal ESP-IDF logging remains on its existing primary logger transport.
  // Direct UART I/O avoids relying on newlib stdin/stdout routing on CrowPanel.
  if (!uart_is_driver_installed(kServiceConsoleUart)) {
    const esp_err_t install_result =
        uart_driver_install(kServiceConsoleUart, kServiceConsoleRxBufferBytes,
                            kServiceConsoleTxBufferBytes, 0, nullptr, 0);
    if (install_result != ESP_OK) {
      return false;
    }
  }
  if (uart_flush_input(kServiceConsoleUart) != ESP_OK) {
    return false;
  }

  ready_ = true;
  writeText("\r\n=== Growbox service console ===\r\n");
  writeText("Manual service commands only. Automatic climate outputs remain fake-locked.\r\n");
  printHelp();
  printPrompt();
  return true;
}

void Stage28ServiceConsole::poll(std::uint64_t now_ms) noexcept {
  if (!ready_) {
    return;
  }

  std::array<std::uint8_t, 96U> buffer{};
  const int received = uart_read_bytes(kServiceConsoleUart, buffer.data(), buffer.size(), 0U);
  if (received <= 0) {
    return;
  }

  for (int index = 0; index < received; ++index) {
    const char character = static_cast<char>(buffer[index]);
    if (character == '\r') {
      continue;
    }
    if (character == '\b' || character == 0x7F) {
      if (!discarding_ && length_ > 0U) {
        --length_;
        writeText("\b \b");
      }
      continue;
    }
    if (character == '\n') {
      writeText("\r\n");
      if (discarding_) {
        writeText("error: command line too long\r\n");
      } else if (length_ > 0U) {
        line_[length_] = '\0';
        processLine(now_ms);
      }
      length_ = 0U;
      discarding_ = false;
      printPrompt();
      continue;
    }
    if (discarding_) {
      continue;
    }
    if (length_ >= kMaximumLineBytes) {
      discarding_ = true;
      length_ = 0U;
      continue;
    }
    if (character >= 0x20 && character <= 0x7E) {
      line_[length_++] = character;
      char echo[2]{character, '\0'};
      writeText(echo);
    }
  }
}

void Stage28ServiceConsole::processLine(std::uint64_t now_ms) noexcept {
  const ServiceConsoleCommand command = parseServiceConsoleCommand(line_.data());
  switch (command.kind) {
  case ServiceConsoleCommandKind::None:
    return;
  case ServiceConsoleCommandKind::Help:
    printHelp();
    return;
  case ServiceConsoleCommandKind::Status:
    printStatus(now_ms);
    return;
  case ServiceConsoleCommandKind::Sensors:
    printSensors(now_ms);
    return;
  case ServiceConsoleCommandKind::RfList:
    printRfList();
    return;
  case ServiceConsoleCommandKind::RfTransmit:
    handleRfTransmit(command);
    return;
  case ServiceConsoleCommandKind::RfReceive:
    handleRfReceive(command);
    return;
  case ServiceConsoleCommandKind::Invalid:
    writeText("error: unknown/invalid command; type 'help'\r\n");
    return;
  }
}

void Stage28ServiceConsole::printHelp() noexcept {
  writeText("\r\nCommands:\r\n");
  writeText("  0 | help | ?                     show this menu\r\n");
  writeText("  1 | status                       firmware/runtime/heap/RF status\r\n");
  writeText("  2 | sensors                      SCD41, TP357, Xiaomi and RTC snapshot\r\n");
  writeText("  3 | rf | rf list                 list known RF433 devices/codes\r\n");
  writeText("  rf lamp on|off                   manual lamp socket transmit\r\n");
  writeText("  rf fan on|off                    manual fan socket transmit\r\n");
  writeText("  rf humidifier on|off             manual humidifier socket transmit\r\n");
  writeText("  rf rx [50..5000]                 capture/decode one RF frame\r\n");
  writeText("RF transmit commands require the RF diagnostics transport to be enabled.\r\n");
  writeText("Manual TX is not physical load-state acknowledgement.\r\n");
}

void Stage28ServiceConsole::printStatus(std::uint64_t now_ms) noexcept {
  const std::uint32_t free_internal =
      static_cast<std::uint32_t>(heap_caps_get_free_size(MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT));
  const std::uint32_t free_psram =
      static_cast<std::uint32_t>(heap_caps_get_free_size(MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT));
  const UBaseType_t stack_watermark = uxTaskGetStackHighWaterMark(nullptr);
  writeFormatted("status firmware_sha=%s uptime_ms=%llu outputs=fake-locked rf_ready=%d "
                 "free_internal=%lu free_psram=%lu stack_high_water=%lu\r\n",
                 config_.firmware_sha != nullptr ? config_.firmware_sha : "unknown",
                 static_cast<unsigned long long>(now_ms), rf_diagnostics_.ready(),
                 static_cast<unsigned long>(free_internal), static_cast<unsigned long>(free_psram),
                 static_cast<unsigned long>(stack_watermark));
}

void Stage28ServiceConsole::printSensors(std::uint64_t now_ms) noexcept {
  InsideEnvironmentSnapshot scd{};
  const bool scd_sampled = scd41_.sample(now_ms, scd);
  native::BleClimateReading tp357{};
  const bool tp357_sampled = ble_.sampleTp357(now_ms, tp357);
  native::BleClimateReading xiaomi{};
  const bool xiaomi_sampled = ble_.sampleXiaomi(now_ms, xiaomi);
  ClimateWallClockSnapshot rtc{};
  const bool rtc_sampled = clock_.sample(now_ms, rtc);

  writeText("sensors:\r\n");
  if (scd_sampled) {
    writeFormatted("  scd41 temp_c=%.2f rh_pct=%.2f co2_ppm=%.0f age_ms=%llu available=%d "
                   "reads=%lu errors=%lu invalid=%lu\r\n",
                   static_cast<double>(scd.air_temperature_c.value),
                   static_cast<double>(scd.relative_humidity_pct.value),
                   static_cast<double>(scd.co2_ppm.value),
                   static_cast<unsigned long long>(scd.air_temperature_c.age_ms),
                   scd41_.available(),
                   static_cast<unsigned long>(scd41_.successfulMeasurementCount()),
                   static_cast<unsigned long>(scd41_.readErrorCount()),
                   static_cast<unsigned long>(scd41_.invalidMeasurementCount()));
  } else {
    writeFormatted("  scd41 valid=0 available=%d reads=%lu errors=%lu invalid=%lu\r\n",
                   scd41_.available(),
                   static_cast<unsigned long>(scd41_.successfulMeasurementCount()),
                   static_cast<unsigned long>(scd41_.readErrorCount()),
                   static_cast<unsigned long>(scd41_.invalidMeasurementCount()));
  }

  if (tp357_sampled) {
    writeFormatted("  tp357 temp_c=%.2f rh_pct=%.2f age_ms=%llu battery_pct=%u battery_valid=%d "
                   "packets=%lu accepted=%lu rejected=%lu\r\n",
                   static_cast<double>(tp357.temperature_c),
                   static_cast<double>(tp357.relative_humidity_pct),
                   static_cast<unsigned long long>(tp357.age_ms), tp357.battery_pct,
                   tp357.has_battery, static_cast<unsigned long>(ble_.tp357PacketCount()),
                   static_cast<unsigned long>(ble_.tp357AcceptedCount()),
                   static_cast<unsigned long>(ble_.tp357RejectedCount()));
  } else {
    writeFormatted("  tp357 valid=0 packets=%lu accepted=%lu rejected=%lu\r\n",
                   static_cast<unsigned long>(ble_.tp357PacketCount()),
                   static_cast<unsigned long>(ble_.tp357AcceptedCount()),
                   static_cast<unsigned long>(ble_.tp357RejectedCount()));
  }

  if (xiaomi_sampled) {
    writeFormatted("  xiaomi temp_c=%.2f rh_pct=%.2f age_ms=%llu battery_pct=%u battery_valid=%d "
                   "packets=%lu accepted=%lu rejected=%lu\r\n",
                   static_cast<double>(xiaomi.temperature_c),
                   static_cast<double>(xiaomi.relative_humidity_pct),
                   static_cast<unsigned long long>(xiaomi.age_ms), xiaomi.battery_pct,
                   xiaomi.has_battery, static_cast<unsigned long>(ble_.xiaomiPacketCount()),
                   static_cast<unsigned long>(ble_.xiaomiAcceptedCount()),
                   static_cast<unsigned long>(ble_.xiaomiRejectedCount()));
  } else {
    writeFormatted("  xiaomi valid=0 packets=%lu accepted=%lu rejected=%lu\r\n",
                   static_cast<unsigned long>(ble_.xiaomiPacketCount()),
                   static_cast<unsigned long>(ble_.xiaomiAcceptedCount()),
                   static_cast<unsigned long>(ble_.xiaomiRejectedCount()));
  }

  writeFormatted("  rtc sampled=%d available=%d trusted=%d unix_time_s=%llu reads=%lu errors=%lu "
                 "untrusted=%lu\r\n",
                 rtc_sampled, clock_.available(), rtc.valid && clock_.trusted(),
                 static_cast<unsigned long long>(rtc.unix_time_s),
                 static_cast<unsigned long>(clock_.successfulReadCount()),
                 static_cast<unsigned long>(clock_.readErrorCount()),
                 static_cast<unsigned long>(clock_.untrustedReadCount()));
}

void Stage28ServiceConsole::printRfList() noexcept {
  writeFormatted("rf transport_ready=%d automatic_outputs=fake-locked\r\n",
                 rf_diagnostics_.ready());
  for (const KnownRfDevice& device : kKnownRfDevices) {
    writeFormatted("  %s label=%s on=%lu/0x%08lX off=%lu/0x%08lX bits=%u protocol=%u "
                   "pulse_us=%u repeat=%u status=%s\r\n",
                   device.physical_name, device.hardware->label,
                   static_cast<unsigned long>(device.hardware->on.key.code),
                   static_cast<unsigned long>(device.hardware->on.key.code),
                   static_cast<unsigned long>(device.hardware->off.key.code),
                   static_cast<unsigned long>(device.hardware->off.key.code),
                   device.hardware->on.key.bit_length, device.hardware->on.key.protocol,
                   device.hardware->on.pulse_us, device.hardware->on.repeat, device.tx_status);
  }
}

void Stage28ServiceConsole::handleRfTransmit(const ServiceConsoleCommand& command) noexcept {
  const KnownRfDevice* device = findKnownDevice(command.device);
  if (device == nullptr) {
    writeText("error: RF device not found\r\n");
    return;
  }
  if (!rf_diagnostics_.ready()) {
    writeText("error: RF transport is not ready; enable GROWBOX_RF433_LOOPBACK_ENABLED\r\n");
    return;
  }

  const rf433::FrameConfig& frame =
      command.state == ServiceConsoleRfState::On ? device->hardware->on : device->hardware->off;
  rf433::LoopbackEvidence evidence{};
  const bool tx_completed = rf_diagnostics_.manualTransmit(frame, evidence);
  writeFormatted(
      "manual_rf_tx device=%s state=%s code=%lu bits=%u protocol=%u pulse_us=%u "
      "repeat=%u tx_queued=%d tx_started=%d tx_completed=%d self_rx_captured=%d "
      "self_rx_decode_status=%u self_rx_classification=%u physical_state=unconfirmed\r\n",
      serviceConsoleRfDeviceName(command.device), serviceConsoleRfStateName(command.state),
      static_cast<unsigned long>(frame.key.code), frame.key.bit_length, frame.key.protocol,
      frame.pulse_us, frame.repeat, evidence.tx_queued, evidence.tx_started,
      tx_completed && evidence.tx_completed, evidence.rx_captured,
      static_cast<unsigned>(evidence.decoded.status),
      static_cast<unsigned>(evidence.classification));
}

void Stage28ServiceConsole::handleRfReceive(const ServiceConsoleCommand& command) noexcept {
  if (!rf_diagnostics_.ready()) {
    writeText("error: RF transport is not ready; enable GROWBOX_RF433_LOOPBACK_ENABLED\r\n");
    return;
  }
  rf433::ReceiveEvidence evidence{};
  const bool captured = rf_diagnostics_.manualReceive(command.timeout_ms, evidence);
  if (!captured) {
    writeFormatted("rf_rx captured=0 timeout_ms=%lu\r\n",
                   static_cast<unsigned long>(command.timeout_ms));
    return;
  }
  writeFormatted("rf_rx captured=%d timeout_ms=%lu symbols=%u overflow=%d decode_status=%u "
                 "code=%lu bits=%u protocol=%u estimated_pulse_us=%u observed_repeats=%u\r\n",
                 evidence.rx_captured, static_cast<unsigned long>(command.timeout_ms),
                 static_cast<unsigned>(evidence.symbol_count), evidence.overflow,
                 static_cast<unsigned>(evidence.decoded.status),
                 static_cast<unsigned long>(evidence.decoded.frame.code),
                 evidence.decoded.frame.bit_length, evidence.decoded.frame.protocol,
                 evidence.decoded.estimated_pulse_us, evidence.decoded.observed_repeats);
}

void Stage28ServiceConsole::writeText(const char* text) noexcept {
  if (!ready_ || text == nullptr) {
    return;
  }
  const std::size_t length = std::strlen(text);
  std::size_t offset = 0U;
  while (offset < length) {
    const int written = uart_write_bytes(kServiceConsoleUart, text + offset, length - offset);
    if (written <= 0) {
      break;
    }
    offset += static_cast<std::size_t>(written);
  }
}

void Stage28ServiceConsole::writeFormatted(const char* format, ...) noexcept {
  if (!ready_ || format == nullptr) {
    return;
  }
  std::array<char, 640U> buffer{};
  va_list arguments;
  va_start(arguments, format);
  const int written = std::vsnprintf(buffer.data(), buffer.size(), format, arguments);
  va_end(arguments);
  if (written <= 0) {
    return;
  }
  buffer.back() = '\0';
  writeText(buffer.data());
}

void Stage28ServiceConsole::printPrompt() noexcept {
  writeText("growbox> ");
}

} // namespace growbox::app::climate_io::runtime
