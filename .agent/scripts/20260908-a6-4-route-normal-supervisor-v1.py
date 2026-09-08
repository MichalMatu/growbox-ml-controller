from pathlib import Path
import re

path = Path('src/climate/ClimateV6RealInputRuntime.cpp')
text = path.read_text()


def replace_once(old: str, new: str) -> None:
    global text
    count = text.count(old)
    assert count == 1, f'expected exactly one match, got {count}: {old[:80]!r}'
    text = text.replace(old, new, 1)

# Includes: the runtime no longer owns a normal-path Stage28d binary arbiter.
text = text.replace('#include "climate/Stage28dBinaryRoleArbiter.h"\n', '')
replace_once(
    '#include "climate/Stage28dRfOutputEndpoint.h"\n',
    '#include "climate/Stage28dRfOutputEndpoint.h"\n'
    '#include "climate/output/BinaryActuatorPolicy.h"\n'
    '#include "climate/output/ClimateOutputSupervisorSink.h"\n'
    '#include "climate/output/OutputSupervisorExecutor.h"\n'
    '#include "climate/output/OutputSupervisorResolver.h"\n'
)
replace_once(
    '#include "climate/runtime/Stage27RuntimeAdapters.h"\n',
    '#include "climate/runtime/Stage27RuntimeAdapters.h"\n'
    '#include "climate/runtime/Stage27ScheduleIntentAdapter.h"\n'
)

replace_once(
    "constexpr unsigned kSafeStateAttempts = 3U;\n",
    "constexpr unsigned kSafeStateAttempts = 3U;\n"
    "constexpr output::BinaryActuatorPolicyConfig kExhaustPolicyConfig{0.10F, 0.03F, 120'000U,\n"
    "                                                                  120'000U};\n"
    "constexpr output::BinaryActuatorPolicyConfig kHumidifierPolicyConfig{0.10F, 0.03F, 180'000U,\n"
    "                                                                      180'000U};\n"
)

replace_once(
    '};\n\nbool forceSafeStateWithRetries(stage28d::Stage28dRfOutputEndpoint& endpoint,\n',
    '''};

class RuntimeOutputTransport final : public output::OutputTransport {
public:
  RuntimeOutputTransport(output::OutputTransport& real_transport,
                         const bool& real_enabled) noexcept
      : real_transport_(real_transport), real_enabled_(real_enabled) {}

  output::TxResult send(const output::OutputCommand& command) noexcept override {
    if (!real_enabled_) {
      return {output::TransportStatus::Completed, output::TransportError::None};
    }
    const auto result = real_transport_.send(command);
    if (result.status == output::TransportStatus::Completed) {
      ++transmit_count_;
    } else {
      ++transmit_error_count_;
    }
    return result;
  }

  std::uint32_t transmitCount() const noexcept { return transmit_count_; }
  std::uint32_t transmitErrorCount() const noexcept { return transmit_error_count_; }

private:
  output::OutputTransport& real_transport_;
  const bool& real_enabled_;
  std::uint32_t transmit_count_{0U};
  std::uint32_t transmit_error_count_{0U};
};

std::uint64_t nextOutputIntentSequence(std::uint64_t& sequence) noexcept {
  ++sequence;
  if (sequence == 0U) {
    ++sequence;
  }
  return sequence;
}

bool commandStateKnown(const output::OutputStateStore& store,
                       output::OutputEndpointId endpoint) noexcept {
  const auto* state = store.find(endpoint);
  return state != nullptr && state->has_successful_command;
}

bool commandStateOn(const output::OutputStateStore& store,
                    output::OutputEndpointId endpoint) noexcept {
  const auto* state = store.find(endpoint);
  return state != nullptr && state->has_successful_command &&
         state->last_successful_command.state == output::BinaryOutputState::On;
}

void synchronizeSupervisorPoliciesSafeOff(output::BinaryActuatorPolicy& exhaust_policy,
                                          output::BinaryActuatorPolicy& humidifier_policy,
                                          std::uint64_t monotonic_ms) noexcept {
  exhaust_policy.synchronize(output::BinaryOutputState::Off, monotonic_ms);
  humidifier_policy.synchronize(output::BinaryOutputState::Off, monotonic_ms);
}

bool forceSafeStateWithRetries(stage28d::Stage28dRfOutputEndpoint& endpoint,
'''
)

old_snapshot = '''runtime::Stage27PhysicalOutputSnapshot physicalOutputSnapshot(
    const stage28d::Stage28dRfOutputEndpoint& endpoint, bool real_active,
    const stage28d::LampSafetyDecision& lamp_decision,
    const stage28d::Stage28dBinaryRoleArbiter& binary_arbiter) noexcept {
  runtime::Stage27PhysicalOutputSnapshot snapshot{};
  snapshot.real_outputs_active = real_active;
  snapshot.light_on = endpoint.stateOn(stage28d::kScheduledLightEndpoint);
  snapshot.exhaust_on = endpoint.stateOn(stage28d::kExhaustFanEndpoint);
  snapshot.humidifier_on = endpoint.stateOn(stage28d::kHumidifierEndpoint);
  snapshot.thermal_safety_latched = lamp_decision.thermal_latched;
  snapshot.safety_force_exhaust = lamp_decision.force_exhaust_on;
  snapshot.safety_reason = static_cast<std::uint32_t>(lamp_decision.reason);
  snapshot.arbiter_transition_count = binary_arbiter.transitionCount();
  snapshot.arbiter_dwell_hold_count = binary_arbiter.dwellHoldCount();
  snapshot.arbiter_safety_override_count = binary_arbiter.safetyOverrideCount();
  return snapshot;
}
'''
new_snapshot = '''runtime::Stage27PhysicalOutputSnapshot physicalOutputSnapshot(
    const output::OutputStateStore& state_store, bool real_active,
    const stage28d::LampSafetyDecision& lamp_decision,
    const output::BinaryActuatorPolicy& exhaust_policy,
    const output::BinaryActuatorPolicy& humidifier_policy) noexcept {
  // Stage27 telemetry keeps its historical field names here. These ON/OFF values are
  // supervisor last-commanded truth, not independent physical acknowledgement.
  runtime::Stage27PhysicalOutputSnapshot snapshot{};
  snapshot.real_outputs_active = real_active;
  snapshot.light_on = commandStateOn(state_store, stage28d::kScheduledLightEndpoint);
  snapshot.exhaust_on = commandStateOn(state_store, stage28d::kExhaustFanEndpoint);
  snapshot.humidifier_on = commandStateOn(state_store, stage28d::kHumidifierEndpoint);
  snapshot.thermal_safety_latched = lamp_decision.thermal_latched;
  snapshot.safety_force_exhaust = lamp_decision.force_exhaust_on;
  snapshot.safety_reason = static_cast<std::uint32_t>(lamp_decision.reason);
  snapshot.arbiter_transition_count =
      exhaust_policy.transitionCount() + humidifier_policy.transitionCount();
  snapshot.arbiter_dwell_hold_count =
      exhaust_policy.dwellHoldCount() + humidifier_policy.dwellHoldCount();
  snapshot.arbiter_safety_override_count =
      exhaust_policy.overrideCount() + humidifier_policy.overrideCount();
  return snapshot;
}
'''
replace_once(old_snapshot, new_snapshot)

old_composition = '''  runtime::Stage27InsideSource inside(ble, scd41);
  runtime::Stage27NearbySource outside(ble);
  runtime::FixedStage27ScheduleConfigSource schedule_config;
  CompositeClimateSnapshotProvider composite(inside, outside, clock, schedule_config);
  runtime::LockedFakeRoleDriver fake_output_driver;
  MappedClimateRoleDriver mapped_output_driver(semantic_output_config, physical_endpoint);
  stage28d::Stage28dBinaryRoleArbiter binary_arbiter(mapped_output_driver);
  if (real_output_ready) {
    binary_arbiter.synchronizeSafeOff(monotonicMilliseconds());
  }
  SwitchableRoleDriver output_driver(fake_output_driver, binary_arbiter, real_output_ready);
  static RuntimeControlOwner runtime_control_owner;
  auto& runtime_controller = runtime_control_owner.runtimeController();
  ClimateApplication application(runtime_controller, composite, output_driver);
'''
new_composition = '''  runtime::Stage27InsideSource inside(ble, scd41);
  runtime::Stage27NearbySource outside(ble);
  runtime::FixedStage27ScheduleConfigSource schedule_config;
  CompositeClimateSnapshotProvider composite(inside, outside, clock, schedule_config);

  // Legacy role transport remains only as an exceptional fail-safe path until A11.
  // Normal climate and schedule execution below is supervisor-owned.
  runtime::LockedFakeRoleDriver fake_output_driver;
  MappedClimateRoleDriver mapped_output_driver(semantic_output_config, physical_endpoint);
  SwitchableRoleDriver fail_safe_output_driver(fake_output_driver, mapped_output_driver,
                                                real_output_ready);
  ClimateActuatorAdapter fail_safe_actuator_adapter(fail_safe_output_driver);

  output::BinaryActuatorPolicy exhaust_policy(kExhaustPolicyConfig);
  output::BinaryActuatorPolicy humidifier_policy(kHumidifierPolicyConfig);
  if (real_output_ready) {
    synchronizeSupervisorPoliciesSafeOff(exhaust_policy, humidifier_policy,
                                         monotonicMilliseconds());
  }

  output::OutputSupervisorResolverConfig supervisor_config{};
  supervisor_config.endpoints[0] = {stage28d::kScheduledLightEndpoint, nullptr};
  supervisor_config.endpoints[1] = {stage28d::kExhaustFanEndpoint, &exhaust_policy};
  supervisor_config.endpoints[2] = {stage28d::kHumidifierEndpoint, &humidifier_policy};
  supervisor_config.count = 3U;

  RuntimeOutputTransport supervisor_transport(rf_output_transport, real_output_ready);
  output::OutputSupervisorResolver supervisor_resolver(supervisor_config);
  output::OutputSupervisorExecutor supervisor_executor(supervisor_transport, output_state_store,
                                                       supervisor_config);
  ClimateOutputSupervisorSink supervisor_sink(semantic_output_config, supervisor_resolver,
                                              supervisor_executor, output_state_store,
                                              &fail_safe_actuator_adapter);
  if (!supervisor_sink.valid()) {
    ESP_LOGE(kTag, "Output supervisor composition invalid; real outputs remain locked");
    if (real_output_ready) {
      const std::uint64_t safe_ms = monotonicMilliseconds();
      const bool safe_off = forceSafeStateWithRetries(physical_endpoint, safe_ms);
      if (safe_off) {
        synchronizeSupervisorPoliciesSafeOff(exhaust_policy, humidifier_policy, safe_ms);
      }
      fail_safe_output_driver.disableReal();
      real_output_ready = false;
      ESP_LOGE(kTag, "Output supervisor composition fault safe_off=%d outputs=fake-locked",
               safe_off);
    }
  }

  static RuntimeControlOwner runtime_control_owner;
  auto& runtime_controller = runtime_control_owner.runtimeController();
  ClimateApplication application(runtime_controller, composite, supervisor_sink);
'''
replace_once(old_composition, new_composition)

replace_once(
    '  std::uint32_t diagnostic_tick = 0U;\n',
    '  std::uint32_t diagnostic_tick = 0U;\n  std::uint64_t output_intent_sequence = 0U;\n'
)

# Qualification-only Gate6 can keep direct endpoint ownership. Keep its one safety flag copy there,
# but replace the old normal-output switch object with the fail-safe-only compatibility driver.
text = text.replace(
    '        output_driver.disableReal();\n        real_output_ready = false;\n',
    '        if (safe_off) {\n'
    '          synchronizeSupervisorPoliciesSafeOff(exhaust_policy, humidifier_policy, now_ms);\n'
    '        }\n'
    '        fail_safe_output_driver.disableReal();\n'
    '        real_output_ready = false;\n'
)

normal_pattern = re.compile(
    r'''    \} else if \(GROWBOX_STAGE28_THERMAL_TEST_SEQUENCE_ENABLED == 0\) \{\n.*?\n    \}\n    runtime_timing\.control_cycle\.observe\(''',
    re.S,
)
normal_replacement = '''    } else if (GROWBOX_STAGE28_THERMAL_TEST_SEQUENCE_ENABLED == 0) {
      ClimateWallClockSnapshot rtc_snapshot{};
      native::BleClimateReading tp357{};
      const bool rtc_sampled = clock.sample(now_ms, rtc_snapshot) && rtc_snapshot.valid;
      const bool tp357_sampled = ble.sampleTp357(now_ms, tp357);

      output::ScheduleIntent schedule_intent{};
      const std::uint64_t schedule_sequence = nextOutputIntentSequence(output_intent_sequence);
      const bool schedule_intent_ready =
          rtc_sampled &&
          runtime::buildStage27ScheduleIntent(now_ms, rtc_snapshot, schedule_sequence,
                                              schedule_intent);
      if (!schedule_intent_ready) {
        schedule_intent = {};
        schedule_intent.metadata.sequence = schedule_sequence;
        schedule_intent.metadata.monotonic_ms = now_ms;
        schedule_intent.metadata.source = output::OutputSource::Schedule;
        schedule_intent.metadata.reason = output::OutputReason::ScheduleRequest;
        (void)output::setEndpointIntent(schedule_intent.endpoints[0],
                                        stage28d::kScheduledLightEndpoint, 0.0F);
      }

      ::growbox::climate::MeasuredValue safety_temperature{};
      if (tp357_sampled) {
        safety_temperature = {tp357.temperature_c, true, tp357.age_ms};
      }
      const float scheduled_light =
          output::endpointIntentActive(schedule_intent.endpoints[0])
              ? schedule_intent.endpoints[0].level
              : 0.0F;
      const stage28d::LampSafetyInput lamp_safety_input{
          scheduled_light, safety_temperature, output_bindings_valid, now_ms};
      lamp_decision = lamp_safety.evaluate(lamp_safety_input);

      stage28d::LampSafetyEnvelopeSnapshot safety_snapshot{};
      const bool safety_envelope_ready = stage28d::buildLampSafetyEnvelope(
          lamp_safety_input, lamp_decision, nextOutputIntentSequence(output_intent_sequence),
          safety_snapshot);
      if (!safety_envelope_ready && fail_safe_output_driver.realEnabled()) {
        ESP_LOGE(kTag, "Lamp safety envelope build failed; forcing safe state and locking outputs");
        const bool safe_off = forceSafeStateWithRetries(physical_endpoint, now_ms);
        if (safe_off) {
          synchronizeSupervisorPoliciesSafeOff(exhaust_policy, humidifier_policy, now_ms);
        }
        fail_safe_output_driver.disableReal();
        real_output_ready = false;
        ESP_LOGE(kTag, "Lamp safety envelope fault safe_off=%d outputs=fake-locked", safe_off);
      }

      ClimateOutputSupervisorCycleContext supervisor_context{};
      supervisor_context.mode = output::SupervisorMode::Automatic;
      supervisor_context.schedule = schedule_intent;
      supervisor_context.safety = safety_snapshot.envelope;
      supervisor_sink.setCycleContext(supervisor_context);

      loop_result = application.tick(now_ms, decision);
      if (fail_safe_output_driver.realEnabled() && !loop_result.command_applied) {
        ESP_LOGE(kTag, "Supervisor output apply failed; forcing safe state and locking real outputs");
        const bool safe_off = forceSafeStateWithRetries(physical_endpoint, now_ms);
        if (safe_off) {
          synchronizeSupervisorPoliciesSafeOff(exhaust_policy, humidifier_policy, now_ms);
        }
        fail_safe_output_driver.disableReal();
        real_output_ready = false;
        ESP_LOGE(kTag, "Supervisor output fault safe_off=%d outputs=fake-locked", safe_off);
      }
    }
    runtime_timing.control_cycle.observe('''
text, count = normal_pattern.subn(normal_replacement, text)
assert count == 1, f'normal loop replacement count={count}'

replace_once(
    '''      const auto physical_outputs = physicalOutputSnapshot(
          physical_endpoint, output_driver.realEnabled(), lamp_decision, binary_arbiter);
''',
    '''      const auto physical_outputs = physicalOutputSnapshot(
          output_state_store, real_output_ready, lamp_decision, exhaust_policy, humidifier_policy);
'''
)

replace_once(
    '''               output_driver.realEnabled(),
               physical_endpoint.stateKnown(stage28d::kScheduledLightEndpoint),
               physical_endpoint.stateOn(stage28d::kScheduledLightEndpoint),
               physical_endpoint.stateKnown(stage28d::kExhaustFanEndpoint),
               physical_endpoint.stateOn(stage28d::kExhaustFanEndpoint),
               physical_endpoint.stateKnown(stage28d::kHumidifierEndpoint),
               physical_endpoint.stateOn(stage28d::kHumidifierEndpoint),
''',
    '''               real_output_ready,
               commandStateKnown(output_state_store, stage28d::kScheduledLightEndpoint),
               commandStateOn(output_state_store, stage28d::kScheduledLightEndpoint),
               commandStateKnown(output_state_store, stage28d::kExhaustFanEndpoint),
               commandStateOn(output_state_store, stage28d::kExhaustFanEndpoint),
               commandStateKnown(output_state_store, stage28d::kHumidifierEndpoint),
               commandStateOn(output_state_store, stage28d::kHumidifierEndpoint),
'''
)

replace_once(
    '''               static_cast<unsigned long>(binary_arbiter.transitionCount()),
               static_cast<unsigned long>(binary_arbiter.dwellHoldCount()),
               static_cast<unsigned long>(binary_arbiter.safetyOverrideCount()),
               static_cast<unsigned long>(physical_endpoint.transmitCount()),
               static_cast<unsigned long>(physical_endpoint.transmitErrorCount()));
''',
    '''               static_cast<unsigned long>(exhaust_policy.transitionCount() +
                                                  humidifier_policy.transitionCount()),
               static_cast<unsigned long>(exhaust_policy.dwellHoldCount() +
                                                  humidifier_policy.dwellHoldCount()),
               static_cast<unsigned long>(exhaust_policy.overrideCount() +
                                                  humidifier_policy.overrideCount()),
               static_cast<unsigned long>(physical_endpoint.transmitCount() +
                                                  supervisor_transport.transmitCount()),
               static_cast<unsigned long>(physical_endpoint.transmitErrorCount() +
                                                  supervisor_transport.transmitErrorCount()));
'''
)

# The only remaining direct scheduled-light write and endpoint safety flag are inside the explicit
# Gate6 qualification branch. Normal production execution must have no legacy binary arbiter.
assert 'binary_arbiter' not in text
assert 'output_driver.' not in text
assert text.count('physical_endpoint.setSafetyForceExhaust(') == 1
assert text.count('physical_endpoint.writeScheduledLight(') == 1
assert 'ClimateApplication application(runtime_controller, composite, supervisor_sink);' in text
assert 'supervisor_sink.setCycleContext(supervisor_context);' in text

path.write_text(text)
