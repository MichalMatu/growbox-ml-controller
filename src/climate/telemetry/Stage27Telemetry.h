#pragma once

#include <cstdint>

namespace growbox::app::climate_io::telemetry {

struct Stage27TelemetrySnapshot {
  std::uint64_t uptime_ms = 0U;
  std::uint64_t unix_time_s = 0U;
  std::int32_t reset_reason = 0;
  bool input_sampled = false;
  std::uint32_t io_status = 0U;

  std::uint32_t heap_internal = 0U;
  std::uint32_t heap_internal_min = 0U;
  std::uint32_t heap_internal_largest = 0U;
  std::uint32_t heap_psram = 0U;
  std::uint32_t heap_psram_min = 0U;
  std::uint32_t heap_psram_largest = 0U;
  std::uint32_t stack_free = 0U;

  bool scd_available = false;
  bool scd_sample = false;
  float scd_temperature_c = 0.0F;
  float scd_humidity_pct = 0.0F;
  float scd_co2_ppm = 0.0F;
  std::uint64_t scd_age_ms = 0U;
  std::uint32_t scd_read_errors = 0U;
  std::uint32_t scd_invalid = 0U;
  std::uint32_t scd_samples = 0U;

  bool rtc_available = false;
  bool rtc_trusted = false;
  std::uint32_t rtc_reads = 0U;
  std::uint32_t rtc_read_errors = 0U;
  std::uint32_t rtc_untrusted = 0U;
  std::uint64_t rtc_last_success_ms = 0U;
  std::uint64_t rtc_last_trusted_ms = 0U;

  bool ble_scanning = false;
  std::uint32_t ble_scan_starts = 0U;
  std::uint32_t ble_scan_errors = 0U;
  std::uint32_t ble_scan_restarts = 0U;
  std::uint32_t ble_scan_completes = 0U;
  std::uint32_t ble_adv_lock_drops = 0U;

  bool tp_sample = false;
  float tp_temperature_c = 0.0F;
  float tp_humidity_pct = 0.0F;
  std::uint64_t tp_age_ms = 0U;
  std::uint32_t tp_packets = 0U;
  std::uint32_t tp_accepted = 0U;
  std::uint32_t tp_rejected = 0U;

  bool xiaomi_sample = false;
  float xiaomi_temperature_c = 0.0F;
  float xiaomi_humidity_pct = 0.0F;
  std::uint64_t xiaomi_age_ms = 0U;
  std::uint32_t xiaomi_packets = 0U;
  std::uint32_t xiaomi_accepted = 0U;
  std::uint32_t xiaomi_rejected = 0U;

  std::uint32_t runtime_status = 0U;
  std::uint32_t runtime_mode = 0U;
  std::uint32_t rule_arbitration_interventions = 0U;
  std::uint32_t rule_safety_interventions = 0U;
  float applied_heater = 0.0F;
  float applied_cooler = 0.0F;
  float applied_exhaust_fan = 0.0F;
  float applied_humidifier = 0.0F;
  float applied_dehumidifier = 0.0F;
  float applied_co2_doser = 0.0F;

  // Physical-output observability. These fields describe the RF endpoint's
  // internally confirmed transmitted state, not a direct load acknowledgement.
  // Shelly power feedback remains the external physical confirmation channel.
  bool real_outputs_active = false;
  bool physical_light_on = false;
  bool physical_exhaust_on = false;
  bool physical_humidifier_on = false;
};

} // namespace growbox::app::climate_io::telemetry
