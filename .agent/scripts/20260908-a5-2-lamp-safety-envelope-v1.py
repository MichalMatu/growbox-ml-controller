from pathlib import Path

header = Path('src/climate/Stage28dLampSafety.h')
text = header.read_text()
text = text.replace(
    '#include "climate/ClimateTypes.h"\n',
    '#include "climate/ClimateTypes.h"\n#include "climate/output/OutputIntents.h"\n',
)
old = '''struct LampSafetyDecision {\n  bool schedule_requests_lamp_on{false};\n  bool effective_lamp_on{false};\n  bool force_exhaust_on{false};\n  bool thermal_latched{false};\n  LampSafetyReason reason{LampSafetyReason::Safe};\n};\n\nbool validateLampSafetyConfig(const LampSafetyConfig& config) noexcept;\n'''
new = '''struct LampSafetyDecision {\n  bool schedule_requests_lamp_on{false};\n  bool effective_lamp_on{false};\n  bool force_exhaust_on{false};\n  bool thermal_latched{false};\n  bool recovery_running{false};\n  std::uint64_t recovery_started_ms{0U};\n  LampSafetyReason reason{LampSafetyReason::Safe};\n};\n\nstruct LampSafetyEnvelopeSnapshot {\n  ::growbox::app::output::SafetyEnvelope envelope{};\n  LampSafetyReason reason{LampSafetyReason::Safe};\n  bool thermal_latched{false};\n  bool recovery_running{false};\n  std::uint64_t recovery_started_ms{0U};\n  std::uint64_t evidence_monotonic_ms{0U};\n  std::uint64_t temperature_age_ms{0U};\n};\n\nbool buildLampSafetyEnvelope(const LampSafetyInput& input, const LampSafetyDecision& decision,\n                             std::uint64_t sequence,\n                             LampSafetyEnvelopeSnapshot& output) noexcept;\n\nbool validateLampSafetyConfig(const LampSafetyConfig& config) noexcept;\n'''
assert old in text
text = text.replace(old, new)
header.write_text(text)

source = Path('src/climate/Stage28dLampSafety.cpp')
text = source.read_text()
text = text.replace(
    '#include "climate/Stage28dLampSafety.h"\n',
    '#include "climate/Stage28dLampSafety.h"\n\n#include "climate/Stage28dOutputBindings.h"\n',
)
old = '''LampSafetyDecision LampSafetyController::evaluate(const LampSafetyInput& input) noexcept {\n  LampSafetyDecision output{};\n  output.schedule_requests_lamp_on = input.scheduled_light_level >= config_.light_on_threshold;\n'''
new = '''LampSafetyDecision LampSafetyController::evaluate(const LampSafetyInput& input) noexcept {\n  LampSafetyDecision output{};\n  output.schedule_requests_lamp_on = input.scheduled_light_level >= config_.light_on_threshold;\n  const auto attach_recovery_metadata = [&]() noexcept {\n    output.recovery_running = recovery_running_;\n    output.recovery_started_ms = recovery_running_ ? recovery_started_ms_ : 0U;\n  };\n'''
assert old in text
text = text.replace(old, new)
text = text.replace(
    '''    output.reason = LampSafetyReason::InvalidConfig;\n    return output;\n''',
    '''    output.reason = LampSafetyReason::InvalidConfig;\n    attach_recovery_metadata();\n    return output;\n''',
)
text = text.replace(
    '''    output.reason = LampSafetyReason::TemperatureUnavailable;\n    return output;\n''',
    '''    output.reason = LampSafetyReason::TemperatureUnavailable;\n    attach_recovery_metadata();\n    return output;\n''',
)
text = text.replace(
    '''    output.reason = temperature.value >= config_.trip_temperature_c\n                        ? LampSafetyReason::OverTemperature\n                        : LampSafetyReason::RecoveryHold;\n    return output;\n''',
    '''    output.reason = temperature.value >= config_.trip_temperature_c\n                        ? LampSafetyReason::OverTemperature\n                        : LampSafetyReason::RecoveryHold;\n    attach_recovery_metadata();\n    return output;\n''',
)
text = text.replace(
    '''  output.reason = output.schedule_requests_lamp_on ? LampSafetyReason::Safe\n                                                   : LampSafetyReason::TimerOff;\n  return output;\n}\n\n} // namespace growbox::app::climate_io::stage28d\n''',
    '''  output.reason = output.schedule_requests_lamp_on ? LampSafetyReason::Safe\n                                                   : LampSafetyReason::TimerOff;\n  attach_recovery_metadata();\n  return output;\n}\n\nbool buildLampSafetyEnvelope(const LampSafetyInput& input, const LampSafetyDecision& decision,\n                             std::uint64_t sequence,\n                             LampSafetyEnvelopeSnapshot& output) noexcept {\n  output = {};\n  output.reason = decision.reason;\n  output.thermal_latched = decision.thermal_latched;\n  output.recovery_running = decision.recovery_running;\n  output.recovery_started_ms = decision.recovery_started_ms;\n  output.evidence_monotonic_ms = input.monotonic_ms;\n  output.temperature_age_ms = input.inside_temperature_c.age_ms;\n  output.envelope.metadata.sequence = sequence;\n  output.envelope.metadata.monotonic_ms = input.monotonic_ms;\n  output.envelope.metadata.source = ::growbox::app::output::OutputSource::Safety;\n\n  if (!decision.thermal_latched) {\n    return true;\n  }\n\n  output.envelope.metadata.reason = ::growbox::app::output::OutputReason::ThermalSafety;\n  if (!::growbox::app::output::setSafetyConstraint(\n          output.envelope.endpoints[0], kScheduledLightEndpoint,\n          ::growbox::app::output::SafetyConstraint::ForceOff,\n          ::growbox::app::output::OutputReason::ThermalSafety)) {\n    output = {};\n    return false;\n  }\n\n  if (decision.force_exhaust_on &&\n      !::growbox::app::output::setSafetyConstraint(\n          output.envelope.endpoints[1], kExhaustFanEndpoint,\n          ::growbox::app::output::SafetyConstraint::ForceOn,\n          ::growbox::app::output::OutputReason::ThermalSafety)) {\n    output = {};\n    return false;\n  }\n  return true;\n}\n\n} // namespace growbox::app::climate_io::stage28d\n''',
)
source.write_text(text)

test = Path('test/test_stage28d_lamp_safety/test_main.cpp')
text = test.read_text()
text = text.replace(
    '''using growbox::app::climate_io::stage28d::LampSafetyDecision;\n''',
    '''using growbox::app::climate_io::stage28d::LampSafetyDecision;\n'''
    if 'using growbox::app::climate_io::stage28d::LampSafetyDecision;' in text else '',
)
marker = '''using growbox::app::climate_io::stage28d::LampSafetyReason;\nusing growbox::app::climate_io::stage28d::validateLampSafetyConfig;\n'''
replacement = '''using growbox::app::climate_io::stage28d::LampSafetyEnvelopeSnapshot;\nusing growbox::app::climate_io::stage28d::LampSafetyReason;\nusing growbox::app::climate_io::stage28d::buildLampSafetyEnvelope;\nusing growbox::app::climate_io::stage28d::kExhaustFanEndpoint;\nusing growbox::app::climate_io::stage28d::kScheduledLightEndpoint;\nusing growbox::app::climate_io::stage28d::validateLampSafetyConfig;\nnamespace output = growbox::app::output;\n'''
assert marker in text
text = text.replace(marker, replacement)
insert = '''\nvoid testEnvelopeLeavesScheduleAuthorityUnconstrainedWhenThermallySafe() {\n  LampSafetyController controller;\n  const auto sample = input(0.0F, 24.0F, true, 77U, 2'000U);\n  const auto decision = controller.evaluate(sample);\n  LampSafetyEnvelopeSnapshot snapshot{};\n  assert(buildLampSafetyEnvelope(sample, decision, 9U, snapshot));\n  assert(snapshot.reason == LampSafetyReason::TimerOff);\n  assert(!snapshot.thermal_latched);\n  assert(!snapshot.recovery_running);\n  assert(snapshot.evidence_monotonic_ms == 2'000U);\n  assert(snapshot.temperature_age_ms == 77U);\n  assert(snapshot.envelope.metadata.sequence == 9U);\n  assert(snapshot.envelope.metadata.monotonic_ms == 2'000U);\n  assert(snapshot.envelope.metadata.source == output::OutputSource::Safety);\n  assert(snapshot.envelope.metadata.reason == output::OutputReason::None);\n  for (const auto& constraint : snapshot.envelope.endpoints) {\n    assert(!output::safetyConstraintActive(constraint));\n  }\n}\n\nvoid testEnvelopeMapsThermalLatchToLampOffAndFanOn() {\n  LampSafetyController controller;\n  const auto sample = input(1.0F, 28.0F, true, 321U, 10'000U);\n  const auto decision = controller.evaluate(sample);\n  LampSafetyEnvelopeSnapshot snapshot{};\n  assert(buildLampSafetyEnvelope(sample, decision, 55U, snapshot));\n  assert(snapshot.reason == LampSafetyReason::OverTemperature);\n  assert(snapshot.thermal_latched);\n  assert(!snapshot.recovery_running);\n  assert(snapshot.evidence_monotonic_ms == 10'000U);\n  assert(snapshot.temperature_age_ms == 321U);\n  assert(snapshot.envelope.metadata.reason == output::OutputReason::ThermalSafety);\n  assert(output::safetyConstraintActive(snapshot.envelope.endpoints[0]));\n  assert(snapshot.envelope.endpoints[0].endpoint == kScheduledLightEndpoint);\n  assert(snapshot.envelope.endpoints[0].constraint == output::SafetyConstraint::ForceOff);\n  assert(snapshot.envelope.endpoints[0].reason == output::OutputReason::ThermalSafety);\n  assert(output::safetyConstraintActive(snapshot.envelope.endpoints[1]));\n  assert(snapshot.envelope.endpoints[1].endpoint == kExhaustFanEndpoint);\n  assert(snapshot.envelope.endpoints[1].constraint == output::SafetyConstraint::ForceOn);\n  assert(!output::safetyConstraintActive(snapshot.envelope.endpoints[2]));\n}\n\nvoid testEnvelopePreservesRecoveryMetadata() {\n  LampSafetyController controller;\n  (void)controller.evaluate(input(1.0F, 29.0F, true, 0U, 0U));\n  const auto sample = input(1.0F, 26.0F, true, 10U, 10'000U);\n  const auto decision = controller.evaluate(sample);\n  assert(decision.recovery_running);\n  assert(decision.recovery_started_ms == 10'000U);\n\n  LampSafetyEnvelopeSnapshot snapshot{};\n  assert(buildLampSafetyEnvelope(sample, decision, 3U, snapshot));\n  assert(snapshot.reason == LampSafetyReason::RecoveryHold);\n  assert(snapshot.thermal_latched);\n  assert(snapshot.recovery_running);\n  assert(snapshot.recovery_started_ms == 10'000U);\n  assert(snapshot.envelope.endpoints[0].constraint == output::SafetyConstraint::ForceOff);\n  assert(snapshot.envelope.endpoints[1].constraint == output::SafetyConstraint::ForceOn);\n\n  const auto recovered_sample = input(1.0F, 25.9F, true, 0U, 610'000U);\n  const auto recovered = controller.evaluate(recovered_sample);\n  assert(!recovered.thermal_latched);\n  assert(!recovered.recovery_running);\n  assert(recovered.recovery_started_ms == 0U);\n  assert(buildLampSafetyEnvelope(recovered_sample, recovered, 4U, snapshot));\n  for (const auto& constraint : snapshot.envelope.endpoints) {\n    assert(!output::safetyConstraintActive(constraint));\n  }\n}\n\nvoid testEnvelopeDoesNotInventUnavailableFan() {\n  LampSafetyController controller;\n  const auto sample = input(1.0F, 28.5F, true, 0U, 1U, false);\n  const auto decision = controller.evaluate(sample);\n  LampSafetyEnvelopeSnapshot snapshot{};\n  assert(buildLampSafetyEnvelope(sample, decision, 1U, snapshot));\n  assert(snapshot.thermal_latched);\n  assert(snapshot.envelope.endpoints[0].endpoint == kScheduledLightEndpoint);\n  assert(snapshot.envelope.endpoints[0].constraint == output::SafetyConstraint::ForceOff);\n  assert(!output::safetyConstraintActive(snapshot.envelope.endpoints[1]));\n}\n'''
closing = '''\n} // namespace\n\nint main() {\n'''
assert closing in text
text = text.replace(closing, insert + closing)
text = text.replace(
    '''  testInvalidConfigFailsClosed();\n  return 0;\n''',
    '''  testInvalidConfigFailsClosed();\n  testEnvelopeLeavesScheduleAuthorityUnconstrainedWhenThermallySafe();\n  testEnvelopeMapsThermalLatchToLampOffAndFanOn();\n  testEnvelopePreservesRecoveryMetadata();\n  testEnvelopeDoesNotInventUnavailableFan();\n  return 0;\n''',
)
test.write_text(text)
