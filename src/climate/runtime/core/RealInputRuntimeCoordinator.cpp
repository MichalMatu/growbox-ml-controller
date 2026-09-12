#include "climate/runtime/core/RealInputRuntimeCoordinator.h"

#include "climate/application/ClimateApplication.h"
#include "climate/input/ble/BleClimateScanner.h"
#include "climate/input/rtc/Ds3231ClockSource.h"
#include "climate/output/LampSafety.h"
#include "climate/output/OutputBindings.h"
#include "climate/output/OutputExecutionTelemetry.h"
#include "climate/output/OutputStateStore.h"
#include "climate/output/control/OutputAutomationControl.h"
#include "climate/output/control/OutputMaintenanceControl.h"
#include "climate/output/control/OutputManualControl.h"
#include "climate/output/lifecycle/OutputLifecycleExecutor.h"
#include "climate/output/lifecycle/OutputRuntimeLifecycleControl.h"
#include "climate/output/lifecycle/OutputSupervisorLifecycle.h"
#include "climate/output/persistence/OutputPersistenceCoordinator.h"
#include "climate/output/supervisor/ClimateOutputSupervisorSink.h"
#include "climate/runtime/console/Stage28ServiceConsole.h"
#include "climate/runtime/core/RuntimeOutputTransport.h"
#include "climate/runtime/diagnostics/RfDiagnostics.h"
#include "climate/runtime/diagnostics/Stage28eDiagnosticsCore.h"
#include "climate/runtime/schedule/ScheduleIntentAdapter.h"
#include "climate/runtime/telemetry/RuntimeOutputTelemetryLog.h"
#include "climate/runtime/telemetry/TelemetryReporter.h"

#include <esp_log.h>
#include <esp_timer.h>

namespace growbox::app::climate_io::runtime {
namespace {

constexpr char kTag[] = "climate_stage27";

} // namespace

void RealInputRuntimeCoordinator::tick(std::uint64_t loop_started_us) noexcept {
  const std::uint64_t now_ms = loop_started_us / 1000U;

  const std::uint64_t console_started_us = static_cast<std::uint64_t>(esp_timer_get_time());
  services_.support.service_console.poll(now_ms);
  services_.support.timing.service_console.observe(
      static_cast<std::uint64_t>(esp_timer_get_time()) - console_started_us);

  const std::uint64_t rf_started_us = static_cast<std::uint64_t>(esp_timer_get_time());
  services_.support.rf_diagnostics.tick(now_ms);
  services_.support.timing.rf_tick.observe(static_cast<std::uint64_t>(esp_timer_get_time()) -
                                           rf_started_us);

  ::growbox::climate::ClimateLoopResult loop_result{};
  ::growbox::climate::ClimateRuntimeDecision decision{};
  stage28d::LampSafetyDecision lamp_decision{};

  const std::uint64_t control_started_us = static_cast<std::uint64_t>(esp_timer_get_time());
  const bool real_transport_active_this_cycle =
      services_.outputs.execution_status.transport_available;

  ClimateWallClockSnapshot rtc_snapshot{};
  native::BleClimateReading tp357{};
  const bool rtc_sampled =
      services_.inputs.clock.sample(now_ms, rtc_snapshot) && rtc_snapshot.valid;
  const bool tp357_sampled = services_.inputs.ble.sampleTp357(now_ms, tp357);

  output::ScheduleIntent schedule_intent{};
  const std::uint64_t schedule_sequence = cycle_state_.nextOutputIntentSequence();
  const bool schedule_intent_ready =
      rtc_sampled && buildScheduleIntent(now_ms, rtc_snapshot, schedule_sequence, schedule_intent);
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
                                                    services_.outputs.bindings_valid, now_ms};
  lamp_decision = services_.outputs.lamp_safety.evaluate(lamp_safety_input);

  stage28d::LampSafetyEnvelopeSnapshot safety_snapshot{};
  const bool safety_envelope_ready = stage28d::buildLampSafetyEnvelope(
      lamp_safety_input, lamp_decision, cycle_state_.nextOutputIntentSequence(), safety_snapshot);
  if (!safety_envelope_ready && services_.outputs.execution_status.transport_available &&
      services_.outputs.lifecycle.mode() != output::SupervisorMode::FaultLocked) {
    ESP_LOGE(kTag, "Lamp safety envelope build failed; requesting supervisor fault containment");
    if (!services_.outputs.runtime_lifecycle.requestFault(now_ms, schedule_intent)) {
      ESP_LOGE(kTag, "Supervisor fault request failed; disabling physical transport");
      services_.outputs.execution_status.transport_available = false;
    }
    services_.outputs.execution_status.output_ready = false;
  } else if (safety_envelope_ready &&
             services_.outputs.lifecycle.mode() == output::SupervisorMode::BootLocked &&
             !services_.outputs.runtime_lifecycle.transitionActive()) {
    if (!services_.outputs.runtime_lifecycle.beginBoot(now_ms, schedule_intent)) {
      ESP_LOGE(kTag, "Supervisor boot plan failed to start; disabling physical transport");
      services_.outputs.execution_status.transport_available = false;
      services_.outputs.execution_status.output_ready = false;
    }
  }

  // Runtime boot/recovery/fault owns the lifecycle executor only while its own transition is
  // active. Automation/maintenance retain executor ownership outside those windows. Hard safety
  // defers lifecycle TX and remains executable by the supervisor resolver below.
  bool control_services_valid = true;
  const auto runtime_report =
      services_.outputs.runtime_lifecycle.tick(now_ms, safety_snapshot.envelope);
  if (runtime_report.status == output::OutputRuntimeLifecycleStatus::Invalid) {
    control_services_valid = false;
  }
  if (!services_.outputs.runtime_lifecycle.transitionActive()) {
    const auto automation_report = services_.outputs.automation_control.tick(
        now_ms, schedule_intent, safety_snapshot.envelope);
    const auto maintenance_report =
        services_.outputs.maintenance_control.tick(now_ms, safety_snapshot.envelope);
    if (automation_report.status == output::OutputAutomationControlStatus::Invalid ||
        maintenance_report.status == output::OutputMaintenanceStatus::Invalid) {
      control_services_valid = false;
    }
  }
  if (!control_services_valid) {
    ESP_LOGE(kTag, "Output control service invalid; disabling physical transport");
    services_.outputs.execution_status.transport_available = false;
    services_.outputs.execution_status.output_ready = false;
  }

  services_.outputs.execution_status.output_ready =
      services_.outputs.execution_status.transport_available &&
      services_.outputs.runtime_lifecycle.bootCompleted() &&
      services_.outputs.lifecycle.mode() != output::SupervisorMode::FaultLocked;

  output::ManualIntent manual_intent{};
  (void)services_.outputs.manual_control.consume(manual_intent);

  ClimateOutputSupervisorCycleContext supervisor_context{};
  supervisor_context.mode = services_.outputs.lifecycle.mode();
  supervisor_context.schedule = schedule_intent;
  supervisor_context.manual = manual_intent;
  supervisor_context.safety = safety_snapshot.envelope;
  services_.outputs.supervisor_sink.setCycleContext(supervisor_context);

  loop_result = services_.application.tick(now_ms, decision);
  if (services_.outputs.execution_status.transport_available && !loop_result.command_applied &&
      services_.outputs.lifecycle.mode() != output::SupervisorMode::FaultLocked) {
    ESP_LOGE(kTag, "Supervisor output apply failed; requesting lifecycle fault containment");
    if (!services_.outputs.runtime_lifecycle.requestFault(now_ms, schedule_intent)) {
      ESP_LOGE(kTag, "Lifecycle fault containment failed to start; disabling physical transport");
      services_.outputs.execution_status.transport_available = false;
    }
    services_.outputs.execution_status.output_ready = false;
  }

  if (services_.outputs.persistence.valid()) {
    const auto persistence_status = services_.outputs.persistence.syncFromStateStore(
        services_.outputs.state_store, real_transport_active_this_cycle);
    if (persistence_status == output::OutputPersistenceCoordinatorStatus::InvalidPolicy ||
        persistence_status == output::OutputPersistenceCoordinatorStatus::InvalidStateStore) {
      ESP_LOGE(kTag, "Output persistence synchronization invalid status=%u",
               static_cast<unsigned>(persistence_status));
    }
  }
  services_.support.timing.control_cycle.observe(static_cast<std::uint64_t>(esp_timer_get_time()) -
                                                 control_started_us);

  if (cycle_state_.telemetryDue()) {
    const std::uint64_t telemetry_started_us = static_cast<std::uint64_t>(esp_timer_get_time());
    output::OutputSupervisorCycleInput telemetry_cycle{};
    telemetry_cycle.mode = services_.outputs.lifecycle.mode();
    telemetry_cycle.monotonic_ms = now_ms;
    telemetry_cycle.control = services_.outputs.supervisor_sink.lastControlIntent();
    telemetry_cycle.schedule = schedule_intent;
    telemetry_cycle.manual = manual_intent;
    telemetry_cycle.safety = safety_snapshot.envelope;

    const auto lifecycle_report = services_.outputs.lifecycle_executor.report();
    output::OutputExecutionTelemetrySnapshot output_telemetry{};
    const bool output_telemetry_ready = output::buildOutputExecutionTelemetry(
        telemetry_cycle, services_.outputs.supervisor_sink.lastResolution(),
        services_.outputs.state_store, services_.outputs.execution_status.transport_available,
        lifecycle_report.active, lifecycle_report.event,
        services_.outputs.automation_control.requestedEnabled(), output_telemetry);
    output_telemetry.safety_latched = lamp_decision.thermal_latched;
    output_telemetry.safety_reason_code = static_cast<std::uint32_t>(lamp_decision.reason);
    if (!output_telemetry_ready) {
      ESP_LOGE(kTag, "Output execution telemetry snapshot build failed");
    }

    services_.support.telemetry_reporter.record(now_ms, loop_result, decision, output_telemetry);
    logOutputExecutionTelemetry(output_telemetry, services_.outputs.transport.transmitCount(),
                                services_.outputs.transport.transmitErrorCount());

    services_.support.timing.telemetry.observe(static_cast<std::uint64_t>(esp_timer_get_time()) -
                                               telemetry_started_us);
  }

  services_.support.timing.loop_active.observe(static_cast<std::uint64_t>(esp_timer_get_time()) -
                                               loop_started_us);
}

} // namespace growbox::app::climate_io::runtime
