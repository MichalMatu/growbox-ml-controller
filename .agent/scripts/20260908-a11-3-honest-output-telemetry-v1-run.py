import os
import re
import subprocess
from pathlib import Path

BASE = '5d8c324771bd6a49e993dbf96796ac0c2a7e1b27'
BRANCH = 'mvp/environment-controller'
EXPECTED = sorted([
    'src/CMakeLists.txt',
    'src/climate/ClimateV6RealInputRuntime.cpp',
    'src/climate/output/ClimateOutputSupervisorSink.cpp',
    'src/climate/output/ClimateOutputSupervisorSink.h',
    'src/climate/output/OutputExecutionTelemetry.cpp',
    'src/climate/output/OutputExecutionTelemetry.h',
    'src/climate/runtime/Stage27TelemetryReporter.cpp',
    'src/climate/runtime/Stage27TelemetryReporter.h',
    'src/climate/telemetry/Stage27LogFormat.cpp',
    'src/climate/telemetry/Stage27Telemetry.h',
    'test/host/CMakeLists.txt',
    'test/test_output_execution_telemetry/test_main.cpp',
    'test/test_stage27_telemetry/test_main.cpp',
])


def run(cmd, env=None):
    print('+', ' '.join(cmd), flush=True)
    subprocess.run(cmd, check=True, env=env)


def out(cmd):
    return subprocess.check_output(cmd, text=True).strip()


def replace_once(path, old, new):
    p = Path(path)
    text = p.read_text()
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'{path}: expected one replacement, found {count}: {old[:120]!r}')
    p.write_text(text.replace(old, new, 1))


def sub_once(path, pattern, repl, flags=0):
    p = Path(path)
    text = p.read_text()
    new, count = re.subn(pattern, repl, text, count=1, flags=flags)
    if count != 1:
        raise SystemExit(f'{path}: expected one regex replacement, found {count}: {pattern[:120]!r}')
    p.write_text(new)


run(['git', 'fetch', '-q', 'origin', BRANCH])
if out(['git', 'rev-parse', 'HEAD']) != BASE:
    raise SystemExit('A11_3_IDENTITY_FAIL local HEAD mismatch')
if out(['git', 'rev-parse', 'FETCH_HEAD']) != BASE:
    raise SystemExit('A11_3_IDENTITY_FAIL remote branch mismatch')
if out(['git', 'status', '--porcelain']):
    raise SystemExit('A11_3_IDENTITY_FAIL worktree not clean')
print('A11_3_IDENTITY_PASS')

Path('src/climate/output/OutputExecutionTelemetry.h').write_text(r'''#pragma once

#include "climate/output/OutputPolicyConfig.h"
#include "climate/output/OutputSupervisorResolver.h"

#include <array>
#include <cstddef>
#include <cstdint>

namespace growbox::app::output {

struct OutputIntentTelemetry {
  bool active = false;
  NormalizedOutputLevel level = 0.0F;
};

struct OutputEndpointExecutionTelemetry {
  OutputEndpointId endpoint = kInvalidOutputEndpoint;

  OutputIntentTelemetry control{};
  OutputIntentTelemetry schedule{};
  OutputIntentTelemetry manual{};

  bool safety_active = false;
  SafetyConstraint safety_constraint = SafetyConstraint::Allow;
  OutputReason safety_reason = OutputReason::None;

  bool selected = false;
  NormalizedOutputLevel selected_level = 0.0F;
  OutputSource selected_source = OutputSource::None;
  OutputReason selected_reason = OutputReason::None;

  bool resolved = false;
  BinaryOutputState resolved_state = BinaryOutputState::Off;
  bool held_by_dwell = false;
  bool safety_override = false;
  bool inhibited = false;

  bool attempt_known = false;
  bool attempted_this_cycle = false;
  BinaryOutputState attempt_state = BinaryOutputState::Off;
  OutputSource attempt_source = OutputSource::None;
  OutputReason attempt_reason = OutputReason::None;
  TransportStatus transport_status = TransportStatus::NotAttempted;
  TransportError transport_error = TransportError::None;

  bool last_command_known = false;
  BinaryOutputState last_command_state = BinaryOutputState::Off;
  OutputSource last_command_source = OutputSource::None;
  OutputReason last_command_reason = OutputReason::None;

  PhysicalOutputState physical_state = PhysicalOutputState::Unknown;
  bool physical_independent = false;
};

struct OutputExecutionTelemetrySnapshot {
  static constexpr std::uint8_t kVersion = 2U;

  std::uint8_t version = kVersion;
  SupervisorMode mode = SupervisorMode::BootLocked;
  bool transport_active = false;
  bool lifecycle_active = false;
  OutputLifecycleEvent lifecycle_event = OutputLifecycleEvent::Boot;
  bool automation_requested = false;
  bool safety_latched = false;
  std::uint32_t safety_reason_code = 0U;
  std::array<OutputEndpointExecutionTelemetry, kOutputEndpointCapacity> endpoints{};
  std::uint8_t endpoint_count = 0U;
};

bool buildOutputExecutionTelemetry(const OutputSupervisorCycleInput& cycle,
                                   const OutputSupervisorResolution& resolution,
                                   const OutputStateStore& state_store,
                                   bool transport_active,
                                   bool lifecycle_active,
                                   OutputLifecycleEvent lifecycle_event,
                                   bool automation_requested,
                                   OutputExecutionTelemetrySnapshot& output) noexcept;

} // namespace growbox::app::output
''')

Path('src/climate/output/OutputExecutionTelemetry.cpp').write_text(r'''#include "climate/output/OutputExecutionTelemetry.h"

namespace growbox::app::output {
namespace {

const EndpointIntent* findIntent(
    const std::array<EndpointIntent, kOutputEndpointCapacity>& intents,
    OutputEndpointId endpoint) noexcept {
  for (const auto& candidate : intents) {
    if (endpointIntentActive(candidate) && candidate.endpoint == endpoint) {
      return &candidate;
    }
  }
  return nullptr;
}

const SafetyEndpointConstraint* findSafety(const SafetyEnvelope& safety,
                                           OutputEndpointId endpoint) noexcept {
  for (const auto& candidate : safety.endpoints) {
    if (safetyConstraintActive(candidate) && candidate.endpoint == endpoint) {
      return &candidate;
    }
  }
  return nullptr;
}

OutputIntentTelemetry intentTelemetry(
    const std::array<EndpointIntent, kOutputEndpointCapacity>& intents,
    OutputEndpointId endpoint) noexcept {
  OutputIntentTelemetry result{};
  if (const auto* intent = findIntent(intents, endpoint)) {
    result.active = true;
    result.level = intent->level;
  }
  return result;
}

} // namespace

bool buildOutputExecutionTelemetry(const OutputSupervisorCycleInput& cycle,
                                   const OutputSupervisorResolution& resolution,
                                   const OutputStateStore& state_store,
                                   bool transport_active,
                                   bool lifecycle_active,
                                   OutputLifecycleEvent lifecycle_event,
                                   bool automation_requested,
                                   OutputExecutionTelemetrySnapshot& output) noexcept {
  output = {};
  output.mode = cycle.mode;
  output.transport_active = transport_active;
  output.lifecycle_active = lifecycle_active;
  output.lifecycle_event = lifecycle_event;
  output.automation_requested = automation_requested;

  if (!state_store.valid() || resolution.endpoint_count > kOutputEndpointCapacity) {
    return false;
  }

  for (std::size_t index = 0U; index < resolution.endpoint_count; ++index) {
    const auto& resolved = resolution.endpoints[index];
    if (!isValidOutputEndpoint(resolved.endpoint)) {
      output = {};
      return false;
    }
    const auto* state = state_store.find(resolved.endpoint);
    if (state == nullptr || output.endpoint_count >= output.endpoints.size()) {
      output = {};
      return false;
    }

    auto& endpoint = output.endpoints[output.endpoint_count++];
    endpoint.endpoint = resolved.endpoint;
    endpoint.control = intentTelemetry(cycle.control.endpoints, resolved.endpoint);
    endpoint.schedule = intentTelemetry(cycle.schedule.endpoints, resolved.endpoint);
    endpoint.manual = intentTelemetry(cycle.manual.endpoints, resolved.endpoint);

    if (const auto* safety = findSafety(cycle.safety, resolved.endpoint)) {
      endpoint.safety_active = true;
      endpoint.safety_constraint = safety->constraint;
      endpoint.safety_reason = safety->reason;
    }

    endpoint.selected = resolved.has_selected_input;
    endpoint.selected_level = resolved.requested_level;
    endpoint.selected_source = resolved.source;
    endpoint.selected_reason = resolved.reason;
    endpoint.resolved = resolved.has_resolved_state;
    endpoint.resolved_state = resolved.resolved_state;
    endpoint.held_by_dwell = resolved.held_by_dwell;
    endpoint.safety_override = resolved.safety_override;
    endpoint.inhibited = resolved.inhibited;

    endpoint.attempt_known = state->has_attempt;
    endpoint.attempted_this_cycle = state->has_attempt && state->last_attempt_ms == cycle.monotonic_ms;
    if (state->has_attempt) {
      endpoint.attempt_state = state->last_attempt.state;
      endpoint.attempt_source = state->last_attempt.source;
      endpoint.attempt_reason = state->last_attempt.reason;
      endpoint.transport_status = state->last_transport.status;
      endpoint.transport_error = state->last_transport.error;
    }

    endpoint.last_command_known = state->has_successful_command;
    if (state->has_successful_command) {
      endpoint.last_command_state = state->last_successful_command.state;
      endpoint.last_command_source = state->last_successful_command.source;
      endpoint.last_command_reason = state->last_successful_command.reason;
    }

    endpoint.physical_state = state->physical.state;
    endpoint.physical_independent = state->physical.has_independent_feedback;
  }
  return true;
}

} // namespace growbox::app::output
''')

# Firmware source registration.
replace_once(
    'src/CMakeLists.txt',
    '    "climate/output/OutputExecutionProjection.cpp"\n',
    '    "climate/output/OutputExecutionProjection.cpp"\n    "climate/output/OutputExecutionTelemetry.cpp"\n',
)

# Expose only the last raw control intent for telemetry observation.
replace_once(
    'src/climate/output/ClimateOutputSupervisorSink.h',
    '''  const ::growbox::app::output::ExecutionReport& lastReport() const noexcept {\n    return last_report_;\n  }\n''',
    '''  const ::growbox::app::output::ExecutionReport& lastReport() const noexcept {\n    return last_report_;\n  }\n  const ::growbox::app::output::ControlIntent& lastControlIntent() const noexcept {\n    return last_control_intent_;\n  }\n''',
)
replace_once(
    'src/climate/output/ClimateOutputSupervisorSink.h',
    '  ::growbox::app::output::OutputSupervisorResolution last_resolution_{};\n',
    '  ::growbox::app::output::ControlIntent last_control_intent_{};\n  ::growbox::app::output::OutputSupervisorResolution last_resolution_{};\n',
)
replace_once(
    'src/climate/output/ClimateOutputSupervisorSink.cpp',
    '''  execution = {};\n  ::growbox::app::output::ControlIntent control{};\n  if (!buildControlIntent(request, monotonic_ms, control)) {\n''',
    '''  execution = {};\n  last_control_intent_ = {};\n  ::growbox::app::output::ControlIntent control{};\n  if (!buildControlIntent(request, monotonic_ms, control)) {\n''',
)
replace_once(
    'src/climate/output/ClimateOutputSupervisorSink.cpp',
    '''  bool transport_completed = false;\n  if (!executeCycle(control, monotonic_ms, transport_completed)) {\n''',
    '''  last_control_intent_ = control;\n  bool transport_completed = false;\n  if (!executeCycle(control, monotonic_ms, transport_completed)) {\n''',
)
replace_once(
    'src/climate/output/ClimateOutputSupervisorSink.cpp',
    '''  last_resolution_ = {};\n  last_report_ = {};\n  if (!valid()) {\n''',
    '''  last_control_intent_ = {};\n  last_resolution_ = {};\n  last_report_ = {};\n  if (!valid()) {\n''',
)

# Replace the ambiguous Stage27 physical-output compatibility snapshot with the
# explicit output execution telemetry snapshot.
reporter_h = Path('src/climate/runtime/Stage27TelemetryReporter.h')
text = reporter_h.read_text()
text = text.replace('#include "climate/native/BleClimateScanner.h"\n', '#include "climate/native/BleClimateScanner.h"\n#include "climate/output/OutputExecutionTelemetry.h"\n', 1)
text, count = re.subn(r'struct Stage27PhysicalOutputSnapshot \{.*?\n\};\n\n', '', text, count=1, flags=re.S)
if count != 1:
    raise SystemExit('Stage27TelemetryReporter.h: physical snapshot block not found')
old = '''  void record(std::uint64_t now_ms, const ::growbox::climate::ClimateLoopResult& loop_result,\n              const ::growbox::climate::ClimateRuntimeDecision& decision,\n              const Stage27PhysicalOutputSnapshot& physical_outputs = {}) noexcept;\n'''
new = '''  void record(std::uint64_t now_ms, const ::growbox::climate::ClimateLoopResult& loop_result,\n              const ::growbox::climate::ClimateRuntimeDecision& decision,\n              const ::growbox::app::output::OutputExecutionTelemetrySnapshot& output_execution = {}) noexcept;\n'''
if text.count(old) != 1:
    raise SystemExit('Stage27TelemetryReporter.h: record signature anchor mismatch')
reporter_h.write_text(text.replace(old, new, 1))

reporter_cpp = Path('src/climate/runtime/Stage27TelemetryReporter.cpp')
text = reporter_cpp.read_text()
old = '''    std::uint64_t now_ms, const ::growbox::climate::ClimateLoopResult& loop_result,\n    const ::growbox::climate::ClimateRuntimeDecision& decision,\n    const Stage27PhysicalOutputSnapshot& physical_outputs) noexcept {\n'''
new = '''    std::uint64_t now_ms, const ::growbox::climate::ClimateLoopResult& loop_result,\n    const ::growbox::climate::ClimateRuntimeDecision& decision,\n    const ::growbox::app::output::OutputExecutionTelemetrySnapshot& output_execution) noexcept {\n'''
if text.count(old) != 1:
    raise SystemExit('Stage27TelemetryReporter.cpp: record signature anchor mismatch')
text = text.replace(old, new, 1)
old_block = '''  snapshot.real_outputs_active = physical_outputs.real_outputs_active;\n  snapshot.physical_light_on = physical_outputs.light_on;\n  snapshot.physical_exhaust_on = physical_outputs.exhaust_on;\n  snapshot.physical_humidifier_on = physical_outputs.humidifier_on;\n  snapshot.thermal_safety_latched = physical_outputs.thermal_safety_latched;\n  snapshot.safety_force_exhaust = physical_outputs.safety_force_exhaust;\n  snapshot.safety_reason = physical_outputs.safety_reason;\n  snapshot.arbiter_transition_count = physical_outputs.arbiter_transition_count;\n  snapshot.arbiter_dwell_hold_count = physical_outputs.arbiter_dwell_hold_count;\n  snapshot.arbiter_safety_override_count = physical_outputs.arbiter_safety_override_count;\n'''
if text.count(old_block) != 1:
    raise SystemExit('Stage27TelemetryReporter.cpp: legacy output assignment block mismatch')
text = text.replace(old_block, '  snapshot.output = output_execution;\n', 1)
start = text.index('void Stage27TelemetryReporter::logRecord(')
prefix = text[:start]
replacement = r'''void Stage27TelemetryReporter::logRecord(
    const telemetry::Stage27TelemetrySnapshot& snapshot,
    const storage::Stage27StorageStatus& storage_status) noexcept {
  ESP_LOGI(
      kTag,
      "soak_v=3 firmware_sha=%s uptime_ms=%llu reset_reason=%d input_sampled=%d io_status=%u "
      "heap_internal=%u heap_internal_min=%u heap_internal_largest=%u "
      "heap_psram=%u heap_psram_min=%u heap_psram_largest=%u stack_free=%u "
      "scd_available=%d scd_sample=%d scd_t=%.2f scd_rh=%.2f scd_co2=%.0f "
      "scd_age_ms=%llu scd_read_errors=%u scd_invalid=%u scd_samples=%u "
      "rtc_available=%d rtc_trusted=%d rtc_reads=%u rtc_read_errors=%u rtc_untrusted=%u "
      "rtc_last_success_ms=%llu rtc_last_trusted_ms=%llu rtc_unix_time_s=%llu "
      "ble_scanning=%d ble_scan_starts=%u ble_scan_errors=%u ble_scan_restarts=%u "
      "ble_scan_completes=%u ble_adv_lock_drops=%u "
      "tp_sample=%d tp_t=%.2f tp_rh=%.2f tp_age_ms=%llu tp_packets=%u tp_accepted=%u "
      "tp_rejected=%u xiaomi_sample=%d xiaomi_t=%.2f xiaomi_rh=%.2f "
      "xiaomi_age_ms=%llu xiaomi_packets=%u xiaomi_accepted=%u xiaomi_rejected=%u "
      "runtime_status=%u runtime_mode=%u rule_arb=%u rule_safety=%u "
      "requested_fan=%.3f requested_humidifier=%.3f "
      "applied_heater=%.3f applied_cooler=%.3f applied_fan=%.3f applied_humidifier=%.3f "
      "applied_dehumidifier=%.3f applied_co2=%.3f "
      "output_v=%u supervisor_mode=%u transport_active=%d lifecycle_active=%d "
      "lifecycle_event=%u automation_requested=%d safety_latched=%d safety_reason=%u "
      "storage_backend=%s storage_sd_mounted=%d storage_flash_mounted=%d "
      "storage_sd_mount_errors=%u storage_flash_mount_errors=%u storage_write_errors=%u "
      "storage_queue_drops=%u storage_records_written=%u storage_records_skipped=%u "
      "storage_fallbacks=%u storage_sd_recoveries=%u storage_last_write_ms=%llu",
      GROWBOX_FIRMWARE_GIT_SHA, static_cast<unsigned long long>(snapshot.uptime_ms),
      snapshot.reset_reason, snapshot.input_sampled, snapshot.io_status, snapshot.heap_internal,
      snapshot.heap_internal_min, snapshot.heap_internal_largest, snapshot.heap_psram,
      snapshot.heap_psram_min, snapshot.heap_psram_largest, snapshot.stack_free,
      snapshot.scd_available, snapshot.scd_sample, static_cast<double>(snapshot.scd_temperature_c),
      static_cast<double>(snapshot.scd_humidity_pct), static_cast<double>(snapshot.scd_co2_ppm),
      static_cast<unsigned long long>(snapshot.scd_age_ms), snapshot.scd_read_errors,
      snapshot.scd_invalid, snapshot.scd_samples, snapshot.rtc_available, snapshot.rtc_trusted,
      snapshot.rtc_reads, snapshot.rtc_read_errors, snapshot.rtc_untrusted,
      static_cast<unsigned long long>(snapshot.rtc_last_success_ms),
      static_cast<unsigned long long>(snapshot.rtc_last_trusted_ms),
      static_cast<unsigned long long>(snapshot.unix_time_s), snapshot.ble_scanning,
      snapshot.ble_scan_starts, snapshot.ble_scan_errors, snapshot.ble_scan_restarts,
      snapshot.ble_scan_completes, snapshot.ble_adv_lock_drops, snapshot.tp_sample,
      static_cast<double>(snapshot.tp_temperature_c), static_cast<double>(snapshot.tp_humidity_pct),
      static_cast<unsigned long long>(snapshot.tp_age_ms), snapshot.tp_packets,
      snapshot.tp_accepted, snapshot.tp_rejected, snapshot.xiaomi_sample,
      static_cast<double>(snapshot.xiaomi_temperature_c),
      static_cast<double>(snapshot.xiaomi_humidity_pct),
      static_cast<unsigned long long>(snapshot.xiaomi_age_ms), snapshot.xiaomi_packets,
      snapshot.xiaomi_accepted, snapshot.xiaomi_rejected, snapshot.runtime_status,
      snapshot.runtime_mode, snapshot.rule_arbitration_interventions,
      snapshot.rule_safety_interventions, static_cast<double>(snapshot.requested_exhaust_fan),
      static_cast<double>(snapshot.requested_humidifier),
      static_cast<double>(snapshot.applied_heater), static_cast<double>(snapshot.applied_cooler),
      static_cast<double>(snapshot.applied_exhaust_fan),
      static_cast<double>(snapshot.applied_humidifier),
      static_cast<double>(snapshot.applied_dehumidifier),
      static_cast<double>(snapshot.applied_co2_doser), snapshot.output.version,
      static_cast<unsigned>(snapshot.output.mode), snapshot.output.transport_active,
      snapshot.output.lifecycle_active, static_cast<unsigned>(snapshot.output.lifecycle_event),
      snapshot.output.automation_requested, snapshot.output.safety_latched,
      snapshot.output.safety_reason_code,
      storage::stage27StorageBackendName(storage_status.active_backend), storage_status.sd_mounted,
      storage_status.flash_mounted, storage_status.sd_mount_errors,
      storage_status.flash_mount_errors, storage_status.write_errors, storage_status.queue_drops,
      storage_status.records_written, storage_status.records_skipped,
      storage_status.fallback_activations, storage_status.sd_recoveries,
      static_cast<unsigned long long>(storage_status.last_write_ms));
}

} // namespace growbox::app::climate_io::runtime
'''
reporter_cpp.write_text(prefix + replacement)

# Stage27 telemetry snapshot now embeds the explicit output snapshot.
telemetry_h = Path('src/climate/telemetry/Stage27Telemetry.h')
text = telemetry_h.read_text()
text = text.replace('#pragma once\n\n', '#pragma once\n\n#include "climate/output/OutputExecutionTelemetry.h"\n\n', 1)
text, count = re.subn(
    r'''  // Physical-output observability\..*?  std::uint32_t arbiter_safety_override_count = 0U;\n''',
    '  ::growbox::app::output::OutputExecutionTelemetrySnapshot output{};\n',
    text,
    count=1,
    flags=re.S,
)
if count != 1:
    raise SystemExit('Stage27Telemetry.h: legacy physical telemetry block mismatch')
telemetry_h.write_text(text)

# Replace the Stage27 NDJSON formatter with schema v3 + explicit output v2 block.
Path('src/climate/telemetry/Stage27LogFormat.cpp').write_text(r'''#include "climate/telemetry/Stage27LogFormat.h"

#include <cinttypes>
#include <cstdarg>
#include <cstdio>

namespace growbox::app::climate_io::telemetry {
namespace {

std::size_t checkedLength(char* buffer, std::size_t buffer_size, int written) noexcept {
  if (buffer == nullptr || buffer_size == 0U || written < 0 ||
      static_cast<std::size_t>(written) >= buffer_size) {
    if (buffer != nullptr && buffer_size > 0U) {
      buffer[0] = '\0';
    }
    return 0U;
  }
  return static_cast<std::size_t>(written);
}

int flag(bool value) noexcept { return value ? 1 : 0; }

bool appendFormat(char*& cursor, std::size_t& remaining, const char* format, ...) noexcept {
  if (cursor == nullptr || remaining == 0U) {
    return false;
  }
  va_list args;
  va_start(args, format);
  const int written = std::vsnprintf(cursor, remaining, format, args);
  va_end(args);
  if (written < 0 || static_cast<std::size_t>(written) >= remaining) {
    cursor[0] = '\0';
    return false;
  }
  cursor += static_cast<std::size_t>(written);
  remaining -= static_cast<std::size_t>(written);
  return true;
}

bool formatOutputJson(char* buffer, std::size_t buffer_size,
                      const ::growbox::app::output::OutputExecutionTelemetrySnapshot& output) noexcept {
  if (buffer == nullptr || buffer_size == 0U ||
      output.endpoint_count > output.endpoints.size()) {
    return false;
  }
  char* cursor = buffer;
  std::size_t remaining = buffer_size;
  if (!appendFormat(cursor, remaining,
                    "{\"v\":%u,\"m\":%u,\"ta\":%d,\"la\":%d,\"le\":%u,\"ae\":%d,"
                    "\"sl\":%d,\"sr\":%" PRIu32 ",\"ep\":[",
                    output.version, static_cast<unsigned>(output.mode), flag(output.transport_active),
                    flag(output.lifecycle_active), static_cast<unsigned>(output.lifecycle_event),
                    flag(output.automation_requested), flag(output.safety_latched),
                    output.safety_reason_code)) {
    return false;
  }
  for (std::size_t index = 0U; index < output.endpoint_count; ++index) {
    const auto& endpoint = output.endpoints[index];
    if (index != 0U && !appendFormat(cursor, remaining, ",")) {
      return false;
    }
    if (!appendFormat(
            cursor, remaining,
            "[%u,%d,%.3f,%d,%.3f,%d,%.3f,%d,%u,%u,%d,%.3f,%u,%u,%d,%u,%d,%d,%d,"
            "%d,%d,%u,%u,%u,%u,%u,%d,%u,%u,%u,%u,%d]",
            static_cast<unsigned>(endpoint.endpoint), flag(endpoint.control.active),
            static_cast<double>(endpoint.control.level), flag(endpoint.schedule.active),
            static_cast<double>(endpoint.schedule.level), flag(endpoint.manual.active),
            static_cast<double>(endpoint.manual.level), flag(endpoint.safety_active),
            static_cast<unsigned>(endpoint.safety_constraint),
            static_cast<unsigned>(endpoint.safety_reason), flag(endpoint.selected),
            static_cast<double>(endpoint.selected_level),
            static_cast<unsigned>(endpoint.selected_source),
            static_cast<unsigned>(endpoint.selected_reason), flag(endpoint.resolved),
            static_cast<unsigned>(endpoint.resolved_state), flag(endpoint.held_by_dwell),
            flag(endpoint.safety_override), flag(endpoint.inhibited), flag(endpoint.attempt_known),
            flag(endpoint.attempted_this_cycle), static_cast<unsigned>(endpoint.attempt_state),
            static_cast<unsigned>(endpoint.attempt_source),
            static_cast<unsigned>(endpoint.attempt_reason),
            static_cast<unsigned>(endpoint.transport_status),
            static_cast<unsigned>(endpoint.transport_error), flag(endpoint.last_command_known),
            static_cast<unsigned>(endpoint.last_command_state),
            static_cast<unsigned>(endpoint.last_command_source),
            static_cast<unsigned>(endpoint.last_command_reason),
            static_cast<unsigned>(endpoint.physical_state), flag(endpoint.physical_independent))) {
      return false;
    }
  }
  return appendFormat(cursor, remaining, "]}");
}

} // namespace

std::size_t formatStage27SessionNdjson(char* buffer, std::size_t buffer_size,
                                       const Stage27LogSessionMetadata& session) noexcept {
  if (buffer == nullptr || buffer_size == 0U) {
    return 0U;
  }
  const auto sample_interval_ms = storage::stage27SampleIntervalMs(session.backend);
  const auto health_interval_ms = storage::stage27HealthIntervalMs(session.backend);
  const int written = std::snprintf(
      buffer, buffer_size,
      "{\"t\":\"session\",\"schema\":\"growbox-log-v3\",\"out_v\":2,\"fw\":\"%s\","
      "\"sid\":\"%08" PRIx32 "\",\"backend\":\"%s\",\"reset\":%" PRId32
      ",\"u0\":%" PRIu64 ",\"x0\":%" PRIu64 ",\"rtc\":%d,\"sample_ms\":%" PRIu64
      ",\"health_ms\":%" PRIu64 "}",
      session.firmware_sha != nullptr ? session.firmware_sha : "unknown", session.session_id,
      storage::stage27StorageBackendName(session.backend), session.reset_reason,
      session.start_uptime_ms, session.start_unix_time_s, flag(session.rtc_trusted),
      sample_interval_ms, health_interval_ms);
  return checkedLength(buffer, buffer_size, written);
}

std::size_t formatStage27SampleNdjson(char* buffer, std::size_t buffer_size,
                                      const Stage27TelemetrySnapshot& snapshot) noexcept {
  if (buffer == nullptr || buffer_size == 0U) {
    return 0U;
  }
  char output_json[640]{};
  if (!formatOutputJson(output_json, sizeof(output_json), snapshot.output)) {
    return 0U;
  }
  const int written = std::snprintf(
      buffer, buffer_size,
      "{\"t\":\"s\",\"v\":3,\"u\":%" PRIu64 ",\"x\":%" PRIu64 ",\"i\":[%d,%" PRIu32
      "],\"scd\":[%d,%d,%.2f,%.2f,%.0f,%" PRIu64 "],"
      "\"tp\":[%d,%.2f,%.2f,%" PRIu64 "],\"xm\":[%d,%.2f,%.2f,%" PRIu64 "],"
      "\"out\":%s,"
      "\"c\":[%" PRIu32 ",%" PRIu32 ",%" PRIu32 ",%" PRIu32 ",%.3f,%.3f,%.3f,%.3f,%.3f,%.3f]}",
      snapshot.uptime_ms, snapshot.unix_time_s, flag(snapshot.input_sampled), snapshot.io_status,
      flag(snapshot.scd_sample), flag(snapshot.scd_available),
      static_cast<double>(snapshot.scd_temperature_c),
      static_cast<double>(snapshot.scd_humidity_pct), static_cast<double>(snapshot.scd_co2_ppm),
      snapshot.scd_age_ms, flag(snapshot.tp_sample), static_cast<double>(snapshot.tp_temperature_c),
      static_cast<double>(snapshot.tp_humidity_pct), snapshot.tp_age_ms,
      flag(snapshot.xiaomi_sample), static_cast<double>(snapshot.xiaomi_temperature_c),
      static_cast<double>(snapshot.xiaomi_humidity_pct), snapshot.xiaomi_age_ms, output_json,
      snapshot.runtime_status, snapshot.runtime_mode, snapshot.rule_arbitration_interventions,
      snapshot.rule_safety_interventions, static_cast<double>(snapshot.applied_heater),
      static_cast<double>(snapshot.applied_cooler), static_cast<double>(snapshot.applied_exhaust_fan),
      static_cast<double>(snapshot.applied_humidifier),
      static_cast<double>(snapshot.applied_dehumidifier),
      static_cast<double>(snapshot.applied_co2_doser));
  return checkedLength(buffer, buffer_size, written);
}

std::size_t formatStage27HealthNdjson(char* buffer, std::size_t buffer_size,
                                      const Stage27TelemetrySnapshot& snapshot,
                                      const storage::Stage27StorageStatus& storage_status) noexcept {
  if (buffer == nullptr || buffer_size == 0U) {
    return 0U;
  }
  char output_json[640]{};
  if (!formatOutputJson(output_json, sizeof(output_json), snapshot.output)) {
    return 0U;
  }
  const int written = std::snprintf(
      buffer, buffer_size,
      "{\"t\":\"h\",\"v\":3,\"u\":%" PRIu64 ","
      "\"sys\":[%" PRIu32 ",%" PRIu32 ",%" PRIu32 ",%" PRIu32 ",%" PRIu32 ",%" PRIu32 ",%" PRIu32
      "],\"scd\":[%d,%" PRIu32 ",%" PRIu32 ",%" PRIu32 "],"
      "\"rtc\":[%d,%d,%" PRIu32 ",%" PRIu32 ",%" PRIu32 ",%" PRIu64 ",%" PRIu64 "],"
      "\"ble\":[%d,%" PRIu32 ",%" PRIu32 ",%" PRIu32 ",%" PRIu32 ",%" PRIu32 "],"
      "\"tp\":[%" PRIu32 ",%" PRIu32 ",%" PRIu32 "],"
      "\"xm\":[%" PRIu32 ",%" PRIu32 ",%" PRIu32 "],\"out\":%s,"
      "\"st\":[\"%s\",%d,%d,%" PRIu32 ",%" PRIu32 ",%" PRIu32 ",%" PRIu32 ",%" PRIu32 ",%" PRIu32
      ",%" PRIu32 ",%" PRIu32 ",%" PRIu64 "]}",
      snapshot.uptime_ms, snapshot.heap_internal, snapshot.heap_internal_min,
      snapshot.heap_internal_largest, snapshot.heap_psram, snapshot.heap_psram_min,
      snapshot.heap_psram_largest, snapshot.stack_free, flag(snapshot.scd_available),
      snapshot.scd_read_errors, snapshot.scd_invalid, snapshot.scd_samples,
      flag(snapshot.rtc_available), flag(snapshot.rtc_trusted), snapshot.rtc_reads,
      snapshot.rtc_read_errors, snapshot.rtc_untrusted, snapshot.rtc_last_success_ms,
      snapshot.rtc_last_trusted_ms, flag(snapshot.ble_scanning), snapshot.ble_scan_starts,
      snapshot.ble_scan_errors, snapshot.ble_scan_restarts, snapshot.ble_scan_completes,
      snapshot.ble_adv_lock_drops, snapshot.tp_packets, snapshot.tp_accepted, snapshot.tp_rejected,
      snapshot.xiaomi_packets, snapshot.xiaomi_accepted, snapshot.xiaomi_rejected, output_json,
      storage::stage27StorageBackendName(storage_status.active_backend),
      flag(storage_status.sd_mounted), flag(storage_status.flash_mounted),
      storage_status.sd_mount_errors, storage_status.flash_mount_errors,
      storage_status.write_errors, storage_status.queue_drops, storage_status.records_written,
      storage_status.records_skipped, storage_status.fallback_activations,
      storage_status.sd_recoveries, storage_status.last_write_ms);
  return checkedLength(buffer, buffer_size, written);
}

} // namespace growbox::app::climate_io::telemetry
''')

# Runtime: remove the old command-as-physical adapter and build honest output telemetry.
runtime_path = 'src/climate/ClimateV6RealInputRuntime.cpp'
replace_once(
    runtime_path,
    '#include "climate/output/OutputExecutionProjection.h"\n' if Path(runtime_path).read_text().count('#include "climate/output/OutputExecutionProjection.h"\n') else '#include "climate/output/ClimateOutputSupervisorSink.h"\n',
    ('#include "climate/output/OutputExecutionProjection.h"\n#include "climate/output/OutputExecutionTelemetry.h"\n'
     if Path(runtime_path).read_text().count('#include "climate/output/OutputExecutionProjection.h"\n')
     else '#include "climate/output/ClimateOutputSupervisorSink.h"\n#include "climate/output/OutputExecutionTelemetry.h"\n'),
)
sub_once(
    runtime_path,
    r'''bool commandStateKnown\(.*?\n\}\n\nbool commandStateOn\(.*?\n\}\n\nruntime::Stage27PhysicalOutputSnapshot physicalOutputSnapshot\(.*?\n\}\n\n(?=class RuntimeIoOwner)''',
    '',
    flags=re.S,
)
old_telemetry = r'''      const auto physical_outputs = physicalOutputSnapshot(
          output_state_store, real_output_ready, lamp_decision, exhaust_policy, humidifier_policy);
      telemetry_reporter.record(now_ms, loop_result, decision, physical_outputs);
      ESP_LOGI(kTag,
               "stage28d_output real=%d lamp_known=%d lamp_on=%d fan_known=%d fan_on=%d "
               "humidifier_known=%d humidifier_on=%d safety_latched=%d force_fan=%d "
               "safety_reason=%u supervisor_mode=%u automation_requested=%d lifecycle_active=%d "
               "requested_fan=%.3f requested_humidifier=%.3f "
               "applied_fan=%.3f applied_humidifier=%.3f arbiter_transitions=%lu "
               "arbiter_dwell_holds=%lu arbiter_safety_overrides=%lu tx=%lu tx_errors=%lu",
               real_output_ready,
               commandStateKnown(output_state_store, stage28d::kScheduledLightEndpoint),
               commandStateOn(output_state_store, stage28d::kScheduledLightEndpoint),
               commandStateKnown(output_state_store, stage28d::kExhaustFanEndpoint),
               commandStateOn(output_state_store, stage28d::kExhaustFanEndpoint),
               commandStateKnown(output_state_store, stage28d::kHumidifierEndpoint),
               commandStateOn(output_state_store, stage28d::kHumidifierEndpoint),
               lamp_decision.thermal_latched, lamp_decision.force_exhaust_on,
               static_cast<unsigned>(lamp_decision.reason),
               static_cast<unsigned>(output_lifecycle.mode()), automation_control.requestedEnabled(),
               automation_control.transitionActive(),
               static_cast<double>(decision.rule.safe.exhaust_fan),
               static_cast<double>(decision.rule.safe.humidifier),
               static_cast<double>(decision.applied.exhaust_fan),
               static_cast<double>(decision.applied.humidifier),
               static_cast<unsigned long>(exhaust_policy.transitionCount() +
                                                  humidifier_policy.transitionCount()),
               static_cast<unsigned long>(exhaust_policy.dwellHoldCount() +
                                                  humidifier_policy.dwellHoldCount()),
               static_cast<unsigned long>(exhaust_policy.overrideCount() +
                                                  humidifier_policy.overrideCount()),
               static_cast<unsigned long>(supervisor_transport.transmitCount()),
               static_cast<unsigned long>(supervisor_transport.transmitErrorCount()));
'''
new_telemetry = r'''      output::OutputSupervisorCycleInput telemetry_cycle{};
      telemetry_cycle.mode = output_lifecycle.mode();
      telemetry_cycle.monotonic_ms = now_ms;
      telemetry_cycle.control = supervisor_sink.lastControlIntent();
      telemetry_cycle.schedule = schedule_intent;
      telemetry_cycle.manual = manual_intent;
      telemetry_cycle.safety = safety_snapshot.envelope;

      const auto lifecycle_report = lifecycle_executor.report();
      output::OutputExecutionTelemetrySnapshot output_telemetry{};
      const bool output_telemetry_ready = output::buildOutputExecutionTelemetry(
          telemetry_cycle, supervisor_sink.lastResolution(), output_state_store,
          real_transport_available, lifecycle_report.active, lifecycle_report.event,
          automation_control.requestedEnabled(), output_telemetry);
      output_telemetry.safety_latched = lamp_decision.thermal_latched;
      output_telemetry.safety_reason_code = static_cast<std::uint32_t>(lamp_decision.reason);
      if (!output_telemetry_ready) {
        ESP_LOGE(kTag, "Output execution telemetry snapshot build failed");
      }
      telemetry_reporter.record(now_ms, loop_result, decision, output_telemetry);
      ESP_LOGI(kTag,
               "output_exec_v=2 supervisor_mode=%u transport_active=%d lifecycle_active=%d "
               "lifecycle_event=%u automation_requested=%d safety_latched=%d safety_reason=%u "
               "tx=%lu tx_errors=%lu",
               static_cast<unsigned>(output_telemetry.mode), output_telemetry.transport_active,
               output_telemetry.lifecycle_active,
               static_cast<unsigned>(output_telemetry.lifecycle_event),
               output_telemetry.automation_requested, output_telemetry.safety_latched,
               output_telemetry.safety_reason_code,
               static_cast<unsigned long>(supervisor_transport.transmitCount()),
               static_cast<unsigned long>(supervisor_transport.transmitErrorCount()));
      for (std::size_t index = 0U; index < output_telemetry.endpoint_count; ++index) {
        const auto& endpoint = output_telemetry.endpoints[index];
        ESP_LOGI(
            kTag,
            "output_endpoint endpoint=%u control=%d/%.3f schedule=%d/%.3f manual=%d/%.3f "
            "safety=%d/%u/%u selected=%d/%.3f/%u/%u resolved=%d/%u dwell=%d "
            "override=%d inhibited=%d attempt=%d current=%d state=%u source=%u reason=%u "
            "transport=%u error=%u last_command=%d/%u/%u/%u physical_state=%u independent=%d",
            static_cast<unsigned>(endpoint.endpoint), endpoint.control.active,
            static_cast<double>(endpoint.control.level), endpoint.schedule.active,
            static_cast<double>(endpoint.schedule.level), endpoint.manual.active,
            static_cast<double>(endpoint.manual.level), endpoint.safety_active,
            static_cast<unsigned>(endpoint.safety_constraint),
            static_cast<unsigned>(endpoint.safety_reason), endpoint.selected,
            static_cast<double>(endpoint.selected_level),
            static_cast<unsigned>(endpoint.selected_source),
            static_cast<unsigned>(endpoint.selected_reason), endpoint.resolved,
            static_cast<unsigned>(endpoint.resolved_state), endpoint.held_by_dwell,
            endpoint.safety_override, endpoint.inhibited, endpoint.attempt_known,
            endpoint.attempted_this_cycle, static_cast<unsigned>(endpoint.attempt_state),
            static_cast<unsigned>(endpoint.attempt_source),
            static_cast<unsigned>(endpoint.attempt_reason),
            static_cast<unsigned>(endpoint.transport_status),
            static_cast<unsigned>(endpoint.transport_error), endpoint.last_command_known,
            static_cast<unsigned>(endpoint.last_command_state),
            static_cast<unsigned>(endpoint.last_command_source),
            static_cast<unsigned>(endpoint.last_command_reason),
            static_cast<unsigned>(endpoint.physical_state), endpoint.physical_independent);
      }
'''
replace_once(runtime_path, old_telemetry, new_telemetry)

# Host test target for the pure telemetry builder.
host_cmake = Path('test/host/CMakeLists.txt')
text = host_cmake.read_text()
anchor = 'add_executable(\n  output_persistence_schema_tests\n'
if text.count(anchor) != 1:
    raise SystemExit('test/host/CMakeLists.txt: output persistence anchor mismatch')
block = r'''add_executable(
  output_execution_telemetry_tests
  "${PROJECT_ROOT}/test/test_output_execution_telemetry/test_main.cpp"
  "${PROJECT_ROOT}/src/climate/output/OutputExecutionTelemetry.cpp"
  "${PROJECT_ROOT}/src/climate/output/OutputStateStore.cpp"
)
target_include_directories(output_execution_telemetry_tests PRIVATE "${PROJECT_ROOT}/src")
target_compile_features(output_execution_telemetry_tests PRIVATE cxx_std_17)
target_compile_options(output_execution_telemetry_tests PRIVATE -Wall -Wextra -Wpedantic)

'''
text = text.replace(anchor, block + anchor, 1)
add_test_anchor = 'add_test(NAME output_execution_projection_tests COMMAND output_execution_projection_tests)\n'
if text.count(add_test_anchor) != 1:
    raise SystemExit('test/host/CMakeLists.txt: output execution projection test anchor mismatch')
text = text.replace(add_test_anchor, add_test_anchor + 'add_test(NAME output_execution_telemetry_tests COMMAND output_execution_telemetry_tests)\n', 1)
host_cmake.write_text(text)

Path('test/test_output_execution_telemetry').mkdir(parents=True, exist_ok=True)
Path('test/test_output_execution_telemetry/test_main.cpp').write_text(r'''#include "climate/output/OutputExecutionTelemetry.h"

#include <array>
#include <cassert>

namespace output = growbox::app::output;

namespace {
constexpr output::OutputEndpointId kFan = 1U;
constexpr output::OutputEndpointId kLamp = 2U;
constexpr output::OutputEndpointId kHumidifier = 3U;

output::OutputStateStore makeStore() {
  output::OutputStateStore store;
  const std::array<output::OutputEndpointId, output::kOutputEndpointCapacity> endpoints{
      kFan, kLamp, kHumidifier};
  assert(store.configure(endpoints, endpoints.size()));
  return store;
}

void testSnapshotKeepsIntentResolutionTransportAndPhysicalTruthSeparate() {
  auto store = makeStore();

  output::OutputCommand fan_attempt{};
  fan_attempt.endpoint = kFan;
  fan_attempt.state = output::BinaryOutputState::On;
  fan_attempt.source = output::OutputSource::Safety;
  fan_attempt.reason = output::OutputReason::ThermalSafety;
  assert(store.recordAttempt(fan_attempt, 500U,
                             {output::TransportStatus::Completed, output::TransportError::None}));
  assert(store.recordPhysicalObservation(kFan, output::PhysicalOutputState::Off, 490U, 7U));

  output::OutputSupervisorCycleInput cycle{};
  cycle.mode = output::SupervisorMode::Automatic;
  cycle.monotonic_ms = 500U;
  assert(output::setEndpointIntent(cycle.control.endpoints[0], kFan, 0.2F));
  assert(output::setEndpointIntent(cycle.schedule.endpoints[0], kLamp, 1.0F));
  assert(output::setEndpointIntent(cycle.manual.endpoints[0], kHumidifier, 1.0F));
  assert(output::setSafetyConstraint(cycle.safety.endpoints[0], kFan,
                                     output::SafetyConstraint::ForceOn,
                                     output::OutputReason::ThermalSafety));

  output::OutputSupervisorResolution resolution{};
  resolution.endpoint_count = 3U;
  resolution.endpoints[0].endpoint = kFan;
  resolution.endpoints[0].has_selected_input = true;
  resolution.endpoints[0].requested_level = 1.0F;
  resolution.endpoints[0].source = output::OutputSource::Safety;
  resolution.endpoints[0].reason = output::OutputReason::ThermalSafety;
  resolution.endpoints[0].has_resolved_state = true;
  resolution.endpoints[0].resolved_state = output::BinaryOutputState::On;
  resolution.endpoints[0].safety_override = true;
  resolution.endpoints[1].endpoint = kLamp;
  resolution.endpoints[1].has_selected_input = true;
  resolution.endpoints[1].requested_level = 1.0F;
  resolution.endpoints[1].source = output::OutputSource::Schedule;
  resolution.endpoints[1].reason = output::OutputReason::ScheduleRequest;
  resolution.endpoints[1].has_resolved_state = true;
  resolution.endpoints[1].resolved_state = output::BinaryOutputState::On;
  resolution.endpoints[2].endpoint = kHumidifier;
  resolution.endpoints[2].has_selected_input = true;
  resolution.endpoints[2].requested_level = 1.0F;
  resolution.endpoints[2].source = output::OutputSource::Manual;
  resolution.endpoints[2].reason = output::OutputReason::ManualRequest;
  resolution.endpoints[2].has_resolved_state = true;
  resolution.endpoints[2].resolved_state = output::BinaryOutputState::On;
  resolution.endpoints[2].held_by_dwell = true;

  output::OutputExecutionTelemetrySnapshot snapshot{};
  assert(output::buildOutputExecutionTelemetry(
      cycle, resolution, store, true, true, output::OutputLifecycleEvent::Recovery, true,
      snapshot));
  assert(snapshot.version == 2U);
  assert(snapshot.mode == output::SupervisorMode::Automatic);
  assert(snapshot.transport_active);
  assert(snapshot.lifecycle_active);
  assert(snapshot.lifecycle_event == output::OutputLifecycleEvent::Recovery);
  assert(snapshot.automation_requested);
  assert(snapshot.endpoint_count == 3U);

  const auto& fan = snapshot.endpoints[0];
  assert(fan.control.active && fan.control.level == 0.2F);
  assert(fan.safety_active);
  assert(fan.safety_constraint == output::SafetyConstraint::ForceOn);
  assert(fan.selected_source == output::OutputSource::Safety);
  assert(fan.resolved && fan.resolved_state == output::BinaryOutputState::On);
  assert(fan.attempt_known && fan.attempted_this_cycle);
  assert(fan.transport_status == output::TransportStatus::Completed);
  assert(fan.last_command_known && fan.last_command_state == output::BinaryOutputState::On);
  assert(fan.physical_state == output::PhysicalOutputState::Off);
  assert(fan.physical_independent);

  const auto& lamp = snapshot.endpoints[1];
  assert(lamp.schedule.active && lamp.schedule.level == 1.0F);
  assert(!lamp.attempt_known);
  assert(!lamp.last_command_known);
  assert(lamp.physical_state == output::PhysicalOutputState::Unknown);
  assert(!lamp.physical_independent);

  const auto& humidifier = snapshot.endpoints[2];
  assert(humidifier.manual.active && humidifier.manual.level == 1.0F);
  assert(humidifier.held_by_dwell);
}

void testFailedHistoricalAttemptIsNotCurrentAndDoesNotInventCommandOrPhysicalTruth() {
  auto store = makeStore();
  output::OutputCommand command{};
  command.endpoint = kLamp;
  command.state = output::BinaryOutputState::Off;
  command.source = output::OutputSource::Lifecycle;
  command.reason = output::OutputReason::LifecyclePolicy;
  assert(store.recordAttempt(command, 100U,
                             {output::TransportStatus::Failed, output::TransportError::IoFailure}));

  output::OutputSupervisorCycleInput cycle{};
  cycle.mode = output::SupervisorMode::FaultLocked;
  cycle.monotonic_ms = 200U;
  output::OutputSupervisorResolution resolution{};
  resolution.endpoint_count = 1U;
  resolution.endpoints[0].endpoint = kLamp;

  output::OutputExecutionTelemetrySnapshot snapshot{};
  assert(output::buildOutputExecutionTelemetry(
      cycle, resolution, store, false, false, output::OutputLifecycleEvent::Fault, false,
      snapshot));
  const auto& lamp = snapshot.endpoints[0];
  assert(lamp.attempt_known);
  assert(!lamp.attempted_this_cycle);
  assert(lamp.transport_status == output::TransportStatus::Failed);
  assert(!lamp.last_command_known);
  assert(lamp.physical_state == output::PhysicalOutputState::Unknown);
  assert(!lamp.physical_independent);
}

} // namespace

int main() {
  testSnapshotKeepsIntentResolutionTransportAndPhysicalTruthSeparate();
  testFailedHistoricalAttemptIsNotCurrentAndDoesNotInventCommandOrPhysicalTruth();
  return 0;
}
''')

# Rewrite focused Stage27 serialization fixture for schema v3/output v2.
Path('test/test_stage27_telemetry/test_main.cpp').write_text(r'''#include "climate/storage/Stage27StorageTypes.h"
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
  const auto session_length = formatStage27SessionNdjson(session_buffer, sizeof(session_buffer), session);
  assert(session_length > 0U && session_length < 360U);
  assert(std::strstr(session_buffer, "\"schema\":\"growbox-log-v3\"") != nullptr);
  assert(std::strstr(session_buffer, "\"out_v\":2") != nullptr);

  char sample_buffer[1024]{};
  const auto sample_length = formatStage27SampleNdjson(sample_buffer, sizeof(sample_buffer), snapshot);
  assert(sample_length > 0U && sample_length < sizeof(sample_buffer));
  assert(std::strstr(sample_buffer, "\"t\":\"s\",\"v\":3") != nullptr);
  assert(std::strstr(sample_buffer, "\"out\":{\"v\":2,\"m\":2,\"ta\":1") != nullptr);
  assert(std::strstr(sample_buffer, "\"ep\":[[2,0,0.000,1,1.000") != nullptr);
  assert(std::strstr(sample_buffer, "\"physical_light\"") == nullptr);

  Stage27StorageStatus storage{};
  storage.active_backend = Stage27StorageBackendKind::Flash;
  storage.flash_mounted = true;
  storage.sd_mount_errors = 2U;
  storage.records_written = 7U;
  storage.fallback_activations = 1U;
  storage.last_write_ms = 123000U;

  char health_buffer[1024]{};
  const auto health_length = formatStage27HealthNdjson(health_buffer, sizeof(health_buffer), snapshot, storage);
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
''')

# Exact scope and static honesty guards before compilation.
run(['git', 'add', '-N', 'src/climate/output/OutputExecutionTelemetry.cpp',
     'src/climate/output/OutputExecutionTelemetry.h',
     'test/test_output_execution_telemetry/test_main.cpp'])
run(['git', 'diff', '--check'])
changed = sorted(out(['git', 'diff', '--name-only']).splitlines())
if changed != EXPECTED:
    raise SystemExit(f'A11_3_SCOPE_FAIL changed={changed!r}')

runtime_text = Path(runtime_path).read_text()
for forbidden in ['physical_light=', 'physical_fan=', 'physical_humidifier=', 'stage28d_output real=']:
    if forbidden in runtime_text:
        raise SystemExit(f'A11_3_STATIC_FAIL ambiguous runtime telemetry remains: {forbidden}')
telemetry_text = Path('src/climate/telemetry/Stage27Telemetry.h').read_text()
for forbidden in ['physical_light_on', 'physical_exhaust_on', 'physical_humidifier_on']:
    if forbidden in telemetry_text:
        raise SystemExit(f'A11_3_STATIC_FAIL ambiguous snapshot field remains: {forbidden}')

# Focused host tests only; no full software gate here.
build_dir = '/tmp/growbox-a11-3-host'
run(['cmake', '-S', 'test/host', '-B', build_dir])
run(['cmake', '--build', build_dir, '--target',
     'output_execution_telemetry_tests',
     'stage27_telemetry_tests',
     'climate_output_supervisor_sink_tests',
     'output_supervisor_resolver_tests',
     'output_supervisor_executor_tests',
     '-j4'])
for target in [
    'output_execution_telemetry_tests',
    'stage27_telemetry_tests',
    'climate_output_supervisor_sink_tests',
    'output_supervisor_resolver_tests',
    'output_supervisor_executor_tests',
]:
    run([f'{build_dir}/{target}'])

# Production real-input build because reporter/runtime serialization changed.
fw_dir = '/tmp/growbox-a11-3-fw'
env = os.environ.copy()
env.update({
    'STAGE27C_BUILD_DIR': fw_dir,
    'STAGE27C_SDKCONFIG': f'{fw_dir}/sdkconfig',
    'GROWBOX_RF433_LOOPBACK_ENABLED': '1',
    'GROWBOX_STAGE28_REAL_OUTPUTS_ENABLED': '1',
    'GROWBOX_RF433_LOOPBACK_AUTO_SMOKE': '0',
    'GROWBOX_RF433_REMOTE_CAPTURE_ENABLED': '0',
})
run(['bash', 'scripts/stage27c_crowpanel.sh', 'build'], env=env)

run(['git', 'diff', '--check'])
changed = sorted(out(['git', 'diff', '--name-only']).splitlines())
if changed != EXPECTED:
    raise SystemExit(f'A11_3_FINAL_SCOPE_FAIL changed={changed!r}')
run(['git', 'add', *EXPECTED])
run(['git', 'commit', '-m', 'Report honest output execution telemetry'])
commit = out(['git', 'rev-parse', 'HEAD'])
run(['git', 'push', 'origin', f'HEAD:{BRANCH}'])
run(['git', 'fetch', '-q', 'origin', BRANCH])
if out(['git', 'rev-parse', 'FETCH_HEAD']) != commit:
    raise SystemExit('A11_3_PUSH_VERIFY_FAIL')
print(f'A11_3_PASS commit={commit}')
