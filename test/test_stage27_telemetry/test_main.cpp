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
namespace output = growbox::app::output;

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
  snapshot.runtime_status = 1U;
  snapshot.runtime_mode = 2U;
  snapshot.requested_exhaust_fan = 0.29F;
  snapshot.requested_humidifier = 0.14F;
  snapshot.ml_evaluated = true;
  snapshot.ml_arbitration_interventions = 16U;
  snapshot.ml_safety_interventions = 32U;
  snapshot.ml_safe_exhaust_fan = 0.41F;
  snapshot.ml_safe_humidifier = 0.22F;
  snapshot.applied_exhaust_fan = 1.0F;
  snapshot.applied_humidifier = 0.0F;

  snapshot.output.mode = output::SupervisorMode::Automatic;
  snapshot.output.transport_active = true;
  snapshot.output.lifecycle_active = false;
  snapshot.output.lifecycle_event = output::OutputLifecycleEvent::Boot;
  snapshot.output.automation_requested = true;
  snapshot.output.safety_latched = true;
  snapshot.output.safety_reason_code = 4U;
  snapshot.output.endpoint_count = 1U;
  auto& endpoint = snapshot.output.endpoints[0];
  endpoint.endpoint = 2U;
  endpoint.schedule = {true, 1.0F};
  endpoint.safety_active = true;
  endpoint.safety_constraint = output::SafetyConstraint::ForceOff;
  endpoint.safety_reason = output::OutputReason::ThermalSafety;
  endpoint.selected = true;
  endpoint.selected_level = 0.0F;
  endpoint.selected_source = output::OutputSource::Safety;
  endpoint.selected_reason = output::OutputReason::ThermalSafety;
  endpoint.resolved = true;
  endpoint.resolved_state = output::BinaryOutputState::Off;
  endpoint.safety_override = true;
  endpoint.attempt_known = true;
  endpoint.attempted_this_cycle = true;
  endpoint.attempt_state = output::BinaryOutputState::Off;
  endpoint.attempt_source = output::OutputSource::Safety;
  endpoint.attempt_reason = output::OutputReason::ThermalSafety;
  endpoint.transport_status = output::TransportStatus::Completed;
  endpoint.last_command_known = true;
  endpoint.last_command_state = output::BinaryOutputState::Off;
  endpoint.last_command_source = output::OutputSource::Safety;
  endpoint.last_command_reason = output::OutputReason::ThermalSafety;
  endpoint.physical_state = output::PhysicalOutputState::Unknown;
  endpoint.physical_independent = false;

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
  assert(session_length > 0U && session_length < 360U);
  assert(std::strstr(session_buffer, "\"schema\":\"growbox-log-v3\"") != nullptr);
  assert(std::strstr(session_buffer, "\"out_v\":2") != nullptr);

  char sample_buffer[1024]{};
  const auto sample_length =
      formatStage27SampleNdjson(sample_buffer, sizeof(sample_buffer), snapshot);
  assert(sample_length > 0U && sample_length < sizeof(sample_buffer));
  assert(std::strstr(sample_buffer, "\"t\":\"s\",\"v\":3") != nullptr);
  assert(std::strstr(sample_buffer, "\"out\":{\"v\":2,\"m\":2,\"ta\":1") != nullptr);
  assert(std::strstr(sample_buffer, "\"ep\":[[2,0,0.000,1,1.000") != nullptr);
  assert(std::strstr(sample_buffer, "\"ml\":[1,16,32,0.290,0.140,0.410,0.220]") != nullptr);
  assert(std::strstr(sample_buffer, "\"physical_light\"") == nullptr);

  Stage27StorageStatus storage{};
  storage.active_backend = Stage27StorageBackendKind::Flash;
  storage.flash_mounted = true;
  storage.sd_mount_errors = 2U;
  storage.records_written = 7U;
  storage.fallback_activations = 1U;
  storage.last_write_ms = 123000U;

  char health_buffer[1024]{};
  const auto health_length =
      formatStage27HealthNdjson(health_buffer, sizeof(health_buffer), snapshot, storage);
  assert(health_length > 0U && health_length < sizeof(health_buffer));
  assert(std::strstr(health_buffer, "\"t\":\"h\",\"v\":3") != nullptr);
  assert(std::strstr(health_buffer, "\"out\":{\"v\":2") != nullptr);
  assert(std::strstr(health_buffer, "\"st\":[\"flash\",0,1,2") != nullptr);

  char too_small[32]{};
  assert(formatStage27SessionNdjson(too_small, sizeof(too_small), session) == 0U);
  assert(formatStage27SampleNdjson(too_small, sizeof(too_small), snapshot) == 0U);
  assert(formatStage27HealthNdjson(too_small, sizeof(too_small), snapshot, storage) == 0U);
  return 0;
}
