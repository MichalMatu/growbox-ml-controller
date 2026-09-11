#include "climate/runtime/RealInputRuntimeCoordinator.h"

#include "climate/Stage28dOutputBindings.h"
#include "climate/output/OutputExecutionTelemetry.h"
#include "climate/runtime/Stage27ScheduleIntentAdapter.h"

#include <esp_log.h>
#include <esp_timer.h>

#include <cstddef>

namespace growbox::app::climate_io::runtime {
namespace {

constexpr char kTag[] = "climate_stage27";

} // namespace

void RealInputRuntimeCoordinator::tick(std::uint64_t loop_started_us) noexcept {
  const std::uint64_t now_ms = loop_started_us / 1000U;

  const std::uint64_t console_started_us = static_cast<std::uint64_t>(esp_timer_get_time());
  services_.service_console.poll(now_ms);
  services_.runtime_timing.service_console.observe(
      static_cast<std::uint64_t>(esp_timer_get_time()) - console_started_us);

  const std::uint64_t rf_started_us = static_cast<std::uint64_t>(esp_timer_get_time());
  services_.rf_diagnostics.tick(now_ms);
  services_.runtime_timing.rf_tick.observe(static_cast<std::uint64_t>(esp_timer_get_time()) -
                                           rf_started_us);

  ::growbox::climate::ClimateLoopResult loop_result{};
  ::growbox::climate::ClimateRuntimeDecision decision{};
  stage28d::LampSafetyDecision lamp_decision{};

  const std::uint64_t control_started_us = static_cast<std::uint64_t>(esp_timer_get_time());
  const bool real_transport_active_this_cycle = services_.execution_status.transport_available;

  ClimateWallClockSnapshot rtc_snapshot{};
  native::BleClimateReading tp357{};
  const bool rtc_sampled = services_.clock.sample(now_ms, rtc_snapshot) && rtc_snapshot.valid;
  const bool tp357_sampled = services_.ble.sampleTp357(now_ms, tp357);

  output::ScheduleIntent schedule_intent{};
  const std::uint64_t schedule_sequence = cycle_state_.nextOutputIntentSequence();
  const bool schedule_intent_ready =
      rtc_sampled &&
      buildStage27ScheduleIntent(now_ms, rtc_snapshot, schedule_sequence, schedule_intent);
  if (!schedule_intent_ready) {
    schedule_intent = {};
    schedule_intent.metadata.sequence = schedule_sequence;
    schedule_intent.metadata.monotonic_ms = now_ms;
    schedule_intent.metadata.source = output::OutputSource::Schedule;
    schedule_intent.metadata.reason = output::OutputReason::ScheduleRequest;
    (void)output::setEndpointIntent(schedule_intent.endpoints[0], stage28d::kScheduledLightEndpoint,
                                    0.0F);
  }

  ::growbox::climate::MeasuredValue safety_temperature{};
  if (tp357_sampled) {
    safety_temperature = {tp357.temperature_c, true, tp357.age_ms};
  }
  const float scheduled_light = output::endpointIntentActive(schedule_intent.endpoints[0])
                                    ? schedule_intent.endpoints[0].level
                                    : 0.0F;
  const stage28d::LampSafetyInput lamp_safety_input{scheduled_light, safety_temperature,
                                                    services_.output_bindings_valid, now_ms};
  lamp_decision = services_.lamp_safety.evaluate(lamp_safety_input);

  stage28d::LampSafetyEnvelopeSnapshot safety_snapshot{};
  const bool safety_envelope_ready = stage28d::buildLampSafetyEnvelope(
      lamp_safety_input, lamp_decision, cycle_state_.nextOutputIntentSequence(), safety_snapshot);
  if (!safety_envelope_ready && services_.execution_status.transport_available &&
      services_.output_lifecycle.mode() != output::SupervisorMode::FaultLocked) {
    ESP_LOGE(kTag, "Lamp safety envelope build failed; requesting supervisor fault containment");
    if (!services_.runtime_lifecycle.requestFault(now_ms, schedule_intent)) {
      ESP_LOGE(kTag, "Supervisor fault request failed; disabling physical transport");
      services_.execution_status.transport_available = false;
    }
    services_.execution_status.output_ready = false;
  } else if (safety_envelope_ready &&
             services_.output_lifecycle.mode() == output::SupervisorMode::BootLocked &&
             !services_.runtime_lifecycle.transitionActive()) {
    if (!services_.runtime_lifecycle.beginBoot(now_ms, schedule_intent)) {
      ESP_LOGE(kTag, "Supervisor boot plan failed to start; disabling physical transport");
      services_.execution_status.transport_available = false;
      services_.execution_status.output_ready = false;
    }
  }

  // Runtime boot/recovery/fault owns the lifecycle executor only while its own transition is
  // active. Automation/maintenance retain executor ownership outside those windows. Hard safety
  // defers lifecycle TX and remains executable by the supervisor resolver below.
  (void)services_.runtime_lifecycle.tick(now_ms, safety_snapshot.envelope);
  if (!services_.runtime_lifecycle.transitionActive()) {
    (void)services_.automation_control.tick(now_ms, schedule_intent, safety_snapshot.envelope);
    (void)services_.maintenance_control.tick(now_ms, safety_snapshot.envelope);
  }

  services_.execution_status.output_ready =
      services_.execution_status.transport_available &&
      services_.runtime_lifecycle.bootCompleted() &&
      services_.output_lifecycle.mode() != output::SupervisorMode::FaultLocked;

  output::ManualIntent manual_intent{};
  (void)services_.manual_control.consume(manual_intent);

  ClimateOutputSupervisorCycleContext supervisor_context{};
  supervisor_context.mode = services_.output_lifecycle.mode();
  supervisor_context.schedule = schedule_intent;
  supervisor_context.manual = manual_intent;
  supervisor_context.safety = safety_snapshot.envelope;
  services_.supervisor_sink.setCycleContext(supervisor_context);

  loop_result = services_.application.tick(now_ms, decision);
  if (services_.execution_status.transport_available && !loop_result.command_applied &&
      services_.output_lifecycle.mode() != output::SupervisorMode::FaultLocked) {
    ESP_LOGE(kTag, "Supervisor output apply failed; requesting lifecycle fault containment");
    if (!services_.runtime_lifecycle.requestFault(now_ms, schedule_intent)) {
      ESP_LOGE(kTag, "Lifecycle fault containment failed to start; disabling physical transport");
      services_.execution_status.transport_available = false;
    }
    services_.execution_status.output_ready = false;
  }

  if (services_.output_persistence.valid()) {
    const auto persistence_status = services_.output_persistence.syncFromStateStore(
        services_.output_state_store, real_transport_active_this_cycle);
    if (persistence_status == output::OutputPersistenceCoordinatorStatus::InvalidPolicy ||
        persistence_status == output::OutputPersistenceCoordinatorStatus::InvalidStateStore) {
      ESP_LOGE(kTag, "Output persistence synchronization invalid status=%u",
               static_cast<unsigned>(persistence_status));
    }
  }
  services_.runtime_timing.control_cycle.observe(static_cast<std::uint64_t>(esp_timer_get_time()) -
                                                 control_started_us);

  if (cycle_state_.telemetryDue()) {
    const std::uint64_t telemetry_started_us = static_cast<std::uint64_t>(esp_timer_get_time());
    output::OutputSupervisorCycleInput telemetry_cycle{};
    telemetry_cycle.mode = services_.output_lifecycle.mode();
    telemetry_cycle.monotonic_ms = now_ms;
    telemetry_cycle.control = services_.supervisor_sink.lastControlIntent();
    telemetry_cycle.schedule = schedule_intent;
    telemetry_cycle.manual = manual_intent;
    telemetry_cycle.safety = safety_snapshot.envelope;

    const auto lifecycle_report = services_.lifecycle_executor.report();
    output::OutputExecutionTelemetrySnapshot output_telemetry{};
    const bool output_telemetry_ready = output::buildOutputExecutionTelemetry(
        telemetry_cycle, services_.supervisor_sink.lastResolution(), services_.output_state_store,
        services_.execution_status.transport_available, lifecycle_report.active,
        lifecycle_report.event, services_.automation_control.requestedEnabled(), output_telemetry);
    output_telemetry.safety_latched = lamp_decision.thermal_latched;
    output_telemetry.safety_reason_code = static_cast<std::uint32_t>(lamp_decision.reason);
    if (!output_telemetry_ready) {
      ESP_LOGE(kTag, "Output execution telemetry snapshot build failed");
    }

    services_.telemetry_reporter.record(now_ms, loop_result, decision, output_telemetry);
    ESP_LOGI(kTag,
             "output_exec_v=2 supervisor_mode=%u transport_active=%d lifecycle_active=%d "
             "lifecycle_event=%u automation_requested=%d safety_latched=%d safety_reason=%u "
             "tx=%lu tx_errors=%lu",
             static_cast<unsigned>(output_telemetry.mode), output_telemetry.transport_active,
             output_telemetry.lifecycle_active,
             static_cast<unsigned>(output_telemetry.lifecycle_event),
             output_telemetry.automation_requested, output_telemetry.safety_latched,
             output_telemetry.safety_reason_code,
             static_cast<unsigned long>(services_.supervisor_transport.transmitCount()),
             static_cast<unsigned long>(services_.supervisor_transport.transmitErrorCount()));

    for (std::size_t index = 0U; index < output_telemetry.endpoint_count; ++index) {
      const auto& endpoint = output_telemetry.endpoints[index];
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

    services_.runtime_timing.telemetry.observe(static_cast<std::uint64_t>(esp_timer_get_time()) -
                                               telemetry_started_us);
  }

  services_.runtime_timing.loop_active.observe(static_cast<std::uint64_t>(esp_timer_get_time()) -
                                               loop_started_us);
}

} // namespace growbox::app::climate_io::runtime
