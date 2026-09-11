#include "climate/runtime/telemetry/RuntimeOutputTelemetryLog.h"

#include <esp_log.h>

#include <cstddef>

namespace growbox::app::climate_io::runtime {
namespace {

constexpr char kTag[] = "climate_stage27";

} // namespace

void logOutputExecutionTelemetry(const output::OutputExecutionTelemetrySnapshot& snapshot,
                                 std::uint32_t transmit_count,
                                 std::uint32_t transmit_error_count) noexcept {
  ESP_LOGI(kTag,
           "output_exec_v=2 supervisor_mode=%u transport_active=%d lifecycle_active=%d "
           "lifecycle_event=%u automation_requested=%d safety_latched=%d safety_reason=%u "
           "tx=%lu tx_errors=%lu",
           static_cast<unsigned>(snapshot.mode), snapshot.transport_active,
           snapshot.lifecycle_active, static_cast<unsigned>(snapshot.lifecycle_event),
           snapshot.automation_requested, snapshot.safety_latched, snapshot.safety_reason_code,
           static_cast<unsigned long>(transmit_count),
           static_cast<unsigned long>(transmit_error_count));

  for (std::size_t index = 0U; index < snapshot.endpoint_count; ++index) {
    const auto& endpoint = snapshot.endpoints[index];
    ESP_LOGI(kTag,
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
}

} // namespace growbox::app::climate_io::runtime
