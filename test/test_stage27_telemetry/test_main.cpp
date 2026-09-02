#include "climate/telemetry/Stage27Telemetry.h"

#include <cassert>
#include <cstring>

using growbox::app::climate_io::telemetry::formatStage27TelemetryNdjson;
using growbox::app::climate_io::telemetry::Stage27TelemetrySnapshot;

int main() {
  Stage27TelemetrySnapshot snapshot{};
  snapshot.uptime_ms = 123456U;
  snapshot.unix_time_s = 1788292800U;
  snapshot.reset_reason = 1;
  snapshot.input_sampled = true;
  snapshot.scd_available = true;
  snapshot.scd_sample = true;
  snapshot.scd_temperature_c = 24.25F;
  snapshot.scd_humidity_pct = 59.5F;
  snapshot.scd_co2_ppm = 721.0F;
  snapshot.rtc_available = true;
  snapshot.rtc_trusted = true;
  snapshot.ble_scanning = true;
  snapshot.tp_sample = true;
  snapshot.tp_temperature_c = 23.8F;
  snapshot.tp_humidity_pct = 71.0F;
  snapshot.xiaomi_sample = true;
  snapshot.xiaomi_temperature_c = 25.1F;
  snapshot.xiaomi_humidity_pct = 55.0F;
  snapshot.applied_exhaust_fan = 0.5F;
  snapshot.sd_mounted = true;
  snapshot.sd_records_written = 7U;

  char buffer[2048]{};
  const auto length = formatStage27TelemetryNdjson(buffer, sizeof(buffer), snapshot);
  assert(length > 0U);
  assert(std::strstr(buffer, "\"schema\":\"growbox-log-v1\"") != nullptr);
  assert(std::strstr(buffer, "\"uptime_ms\":123456") != nullptr);
  assert(std::strstr(buffer, "\"tp357\":{\"sample\":true") != nullptr);
  assert(std::strstr(buffer, "\"outputs\":\"fake-locked\"") != nullptr);
  assert(std::strstr(buffer, "\"mounted\":true") != nullptr);
  assert(std::strstr(buffer, "\"records_written\":7") != nullptr);

  char too_small[32]{};
  assert(formatStage27TelemetryNdjson(too_small, sizeof(too_small), snapshot) == 0U);
  return 0;
}
