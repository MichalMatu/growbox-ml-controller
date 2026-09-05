#include "climate/storage/Stage27StorageTypes.h"
#include "climate/telemetry/Stage27LogFormat.h"
#include "climate/telemetry/Stage27Telemetry.h"

#include <cassert>
#include <cstring>

using growbox::app::climate_io::storage::Stage27StorageBackendKind;
using growbox::app::climate_io::storage::Stage27StorageStatus;
using growbox::app::climate_io::telemetry::formatStage27HealthNdjson;
using growbox::app::climate_io::telemetry::formatStage27SampleNdjson;
using growbox::app::climate_io::telemetry::formatStage27SessionNdjson;
using growbox::app::climate_io::telemetry::Stage27LogSessionMetadata;
using growbox::app::climate_io::telemetry::Stage27TelemetrySnapshot;

int main() {
  Stage27TelemetrySnapshot snapshot{};
  snapshot.uptime_ms = 123456U;
  snapshot.unix_time_s = 1788292800U;
  snapshot.reset_reason = 1;
  snapshot.input_sampled = true;
  snapshot.io_status = 0U;
  snapshot.heap_internal = 260000U;
  snapshot.heap_internal_min = 259000U;
  snapshot.heap_internal_largest = 200000U;
  snapshot.heap_psram = 8380000U;
  snapshot.heap_psram_min = 8370000U;
  snapshot.heap_psram_largest = 8300000U;
  snapshot.stack_free = 4096U;
  snapshot.scd_available = true;
  snapshot.scd_sample = true;
  snapshot.scd_temperature_c = 24.25F;
  snapshot.scd_humidity_pct = 59.5F;
  snapshot.scd_co2_ppm = 721.0F;
  snapshot.scd_age_ms = 4050U;
  snapshot.scd_samples = 42U;
  snapshot.rtc_available = true;
  snapshot.rtc_trusted = true;
  snapshot.rtc_reads = 100U;
  snapshot.rtc_last_success_ms = 123000U;
  snapshot.rtc_last_trusted_ms = 123000U;
  snapshot.ble_scanning = true;
  snapshot.ble_scan_starts = 1U;
  snapshot.tp_sample = true;
  snapshot.tp_temperature_c = 23.8F;
  snapshot.tp_humidity_pct = 71.0F;
  snapshot.tp_age_ms = 15000U;
  snapshot.tp_packets = 20U;
  snapshot.tp_accepted = 20U;
  snapshot.xiaomi_sample = true;
  snapshot.xiaomi_temperature_c = 25.1F;
  snapshot.xiaomi_humidity_pct = 55.0F;
  snapshot.xiaomi_age_ms = 5000U;
  snapshot.xiaomi_packets = 50U;
  snapshot.xiaomi_accepted = 25U;
  snapshot.xiaomi_rejected = 25U;
  snapshot.requested_exhaust_fan = 0.29F;
  snapshot.requested_humidifier = 0.14F;
  snapshot.applied_exhaust_fan = 1.0F;
  snapshot.applied_humidifier = 0.0F;
  snapshot.real_outputs_active = true;
  snapshot.physical_light_on = true;
  snapshot.physical_exhaust_on = true;
  snapshot.physical_humidifier_on = false;
  snapshot.thermal_safety_latched = true;
  snapshot.safety_force_exhaust = true;
  snapshot.safety_reason = 4U;
  snapshot.arbiter_transition_count = 7U;
  snapshot.arbiter_dwell_hold_count = 11U;
  snapshot.arbiter_safety_override_count = 2U;

  Stage27LogSessionMetadata session{};
  session.firmware_sha = "0123456789abcdef0123456789abcdef01234567";
  session.session_id = 0x1234ABCDU;
  session.backend = Stage27StorageBackendKind::Sd;
  session.reset_reason = 1;
  session.start_uptime_ms = snapshot.uptime_ms;
  session.rtc_trusted = true;
  session.start_unix_time_s = snapshot.unix_time_s;

  char session_buffer[512]{};
  const auto session_length =
      formatStage27SessionNdjson(session_buffer, sizeof(session_buffer), session);
  assert(session_length > 0U && session_length < 320U);
  assert(std::strstr(session_buffer, "\"schema\":\"growbox-log-v2\"") != nullptr);
  assert(std::strstr(session_buffer, "\"backend\":\"sd\"") != nullptr);
  assert(std::strstr(session_buffer, "\"sample_ms\":10000") != nullptr);

  char sample_buffer[768]{};
  const auto sample_length =
      formatStage27SampleNdjson(sample_buffer, sizeof(sample_buffer), snapshot);
  assert(sample_length > 0U && sample_length < 600U);
  assert(std::strstr(sample_buffer, "\"t\":\"s\"") != nullptr);
  assert(std::strstr(sample_buffer, "\"scd\":[1,1,24.25,59.50,721,4050]") != nullptr);
  assert(std::strstr(sample_buffer, "\"tp\":[1,23.80,71.00,15000]") != nullptr);
  assert(std::strstr(sample_buffer, "\"o\":[1,1,1,0]") != nullptr);
  assert(std::strstr(sample_buffer,
                     "\"a\":[0.290,1.000,0.140,0.000,1,1,4,7,11,2]") != nullptr);

  Stage27StorageStatus storage{};
  storage.active_backend = Stage27StorageBackendKind::Flash;
  storage.flash_mounted = true;
  storage.sd_mount_errors = 2U;
  storage.records_written = 7U;
  storage.fallback_activations = 1U;
  storage.last_write_ms = 123000U;

  char health_buffer[768]{};
  const auto health_length =
      formatStage27HealthNdjson(health_buffer, sizeof(health_buffer), snapshot, storage);
  assert(health_length > 0U && health_length < 560U);
  assert(std::strstr(health_buffer, "\"t\":\"h\"") != nullptr);
  assert(std::strstr(health_buffer, "\"o\":[1,1,1,0]") != nullptr);
  assert(std::strstr(health_buffer, "\"st\":[\"flash\",0,1,2") != nullptr);

  char too_small[32]{};
  assert(formatStage27SessionNdjson(too_small, sizeof(too_small), session) == 0U);
  assert(formatStage27SampleNdjson(too_small, sizeof(too_small), snapshot) == 0U);
  assert(formatStage27HealthNdjson(too_small, sizeof(too_small), snapshot, storage) == 0U);

  assert(growbox::app::climate_io::storage::stage27SampleIntervalMs(
             Stage27StorageBackendKind::Flash) == 60'000U);
  assert(growbox::app::climate_io::storage::stage27HealthIntervalMs(
             Stage27StorageBackendKind::Flash) == 300'000U);
  return 0;
}
