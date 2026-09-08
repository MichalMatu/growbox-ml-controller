from pathlib import Path

BASE = '76886b7224fbdbd4807d09562590585b8e51ed3d'


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text()
    count = text.count(old)
    assert count == 1, f'{path}: expected one match, got {count}'
    p.write_text(text.replace(old, new, 1))

# ClimateControlLoop public seam and storage.
replace_once(
    'lib/environment_control/src/climate/ClimateControlLoop.h',
    '''  ClimateLoopResult tick(std::uint64_t monotonic_ms, ClimateRuntimeDecision& decision) noexcept;\n  void reset() noexcept;\n\n  bool actuatorFaultLatched() const noexcept {\n''',
    '''  ClimateLoopResult tick(std::uint64_t monotonic_ms, ClimateRuntimeDecision& decision) noexcept;\n\n  // Optional migration seam: known roles from external execution truth override\n  // the compatibility previous_applied_ snapshot used for the next controller input.\n  void setPreviousExecutionFeedback(const ClimateExecutionProjection& feedback) noexcept;\n  void clearPreviousExecutionFeedback() noexcept;\n  bool hasExternalPreviousExecutionFeedback() const noexcept {\n    return has_external_previous_execution_;\n  }\n\n  void reset() noexcept;\n\n  bool actuatorFaultLatched() const noexcept {\n''')
replace_once(
    'lib/environment_control/src/climate/ClimateControlLoop.h',
    '''private:\n  static PreviousClimateActions previousFromRequest(const ClimatePolicyRequest& request) noexcept;\n  static bool isOff(const ClimatePolicyRequest& request) noexcept;\n\n  ClimateRuntimeController& runtime_;\n''',
    '''private:\n  static PreviousClimateActions previousFromRequest(const ClimatePolicyRequest& request) noexcept;\n  PreviousClimateActions previousForInput() const noexcept;\n  static bool isOff(const ClimatePolicyRequest& request) noexcept;\n\n  ClimateRuntimeController& runtime_;\n''')
replace_once(
    'lib/environment_control/src/climate/ClimateControlLoop.h',
    '''  ClimateActuatorSink& actuator_sink_;\n  PreviousClimateActions previous_applied_{};\n  bool actuator_fault_latched_ = false;\n''',
    '''  ClimateActuatorSink& actuator_sink_;\n  PreviousClimateActions previous_applied_{};\n  ClimateExecutionProjection external_previous_execution_{};\n  bool has_external_previous_execution_ = false;\n  bool actuator_fault_latched_ = false;\n''')

# ClimateControlLoop implementation.
replace_once(
    'lib/environment_control/src/climate/ClimateControlLoop.cpp',
    '#include "ClimateControlLoop.h"\n\nnamespace growbox::climate {\n',
    '#include "ClimateControlLoop.h"\n\n#include <cmath>\n\nnamespace growbox::climate {\nnamespace {\n\nfloat boundedPreviousLevel(float value) noexcept {\n  if (!std::isfinite(value)) {\n    return 0.0F;\n  }\n  if (value < 0.0F) {\n    return 0.0F;\n  }\n  return value > 1.0F ? 1.0F : value;\n}\n\n} // namespace\n')
replace_once(
    'lib/environment_control/src/climate/ClimateControlLoop.cpp',
    '''PreviousClimateActions\nClimateControlLoop::previousFromRequest(const ClimatePolicyRequest& request) noexcept {\n  return PreviousClimateActions{request.heater,     request.cooler,       request.exhaust_fan,\n                                request.humidifier, request.dehumidifier, request.co2_doser};\n}\n\nbool ClimateControlLoop::isOff''',
    '''PreviousClimateActions\nClimateControlLoop::previousFromRequest(const ClimatePolicyRequest& request) noexcept {\n  return PreviousClimateActions{request.heater,     request.cooler,       request.exhaust_fan,\n                                request.humidifier, request.dehumidifier, request.co2_doser};\n}\n\nvoid ClimateControlLoop::setPreviousExecutionFeedback(\n    const ClimateExecutionProjection& feedback) noexcept {\n  external_previous_execution_ = feedback;\n  has_external_previous_execution_ = true;\n}\n\nvoid ClimateControlLoop::clearPreviousExecutionFeedback() noexcept {\n  external_previous_execution_ = {};\n  has_external_previous_execution_ = false;\n}\n\nPreviousClimateActions ClimateControlLoop::previousForInput() const noexcept {\n  PreviousClimateActions previous = previous_applied_;\n  if (!has_external_previous_execution_) {\n    return previous;\n  }\n\n  const auto& feedback = external_previous_execution_;\n  if (feedback.known(ClimateExecutionKnownHeater)) {\n    previous.heater = boundedPreviousLevel(feedback.executed.heater);\n  }\n  if (feedback.known(ClimateExecutionKnownCooler)) {\n    previous.cooler = boundedPreviousLevel(feedback.executed.cooler);\n  }\n  if (feedback.known(ClimateExecutionKnownExhaustFan)) {\n    previous.exhaust_fan = boundedPreviousLevel(feedback.executed.exhaust_fan);\n  }\n  if (feedback.known(ClimateExecutionKnownHumidifier)) {\n    previous.humidifier = boundedPreviousLevel(feedback.executed.humidifier);\n  }\n  if (feedback.known(ClimateExecutionKnownDehumidifier)) {\n    previous.dehumidifier = boundedPreviousLevel(feedback.executed.dehumidifier);\n  }\n  if (feedback.known(ClimateExecutionKnownCo2Doser)) {\n    previous.co2_doser = boundedPreviousLevel(feedback.executed.co2_doser);\n  }\n  return previous;\n}\n\nbool ClimateControlLoop::isOff''')
replace_once(
    'lib/environment_control/src/climate/ClimateControlLoop.cpp',
    '  input.previous = previous_applied_;\n',
    '  input.previous = previousForInput();\n')
replace_once(
    'lib/environment_control/src/climate/ClimateControlLoop.cpp',
    '''  runtime_.reset();\n  previous_applied_ = {};\n  if (!result.fail_safe_applied) {\n''',
    '''  runtime_.reset();\n  previous_applied_ = {};\n  clearPreviousExecutionFeedback();\n  if (!result.fail_safe_applied) {\n''')
replace_once(
    'lib/environment_control/src/climate/ClimateControlLoop.cpp',
    '''void ClimateControlLoop::reset() noexcept {\n  runtime_.reset();\n  previous_applied_ = {};\n  actuator_fault_latched_ = false;\n}\n''',
    '''void ClimateControlLoop::reset() noexcept {\n  runtime_.reset();\n  previous_applied_ = {};\n  clearPreviousExecutionFeedback();\n  actuator_fault_latched_ = false;\n}\n''')

# ClimateApplication forwards the seam without changing default construction.
replace_once(
    'src/climate/ClimateApplication.h',
    '''  ::growbox::climate::ClimateLoopResult\n  tick(std::uint64_t monotonic_ms, ::growbox::climate::ClimateRuntimeDecision& decision) noexcept;\n  void reset() noexcept;\n\n  bool actuatorFaultLatched() const noexcept {\n''',
    '''  ::growbox::climate::ClimateLoopResult\n  tick(std::uint64_t monotonic_ms, ::growbox::climate::ClimateRuntimeDecision& decision) noexcept;\n\n  void setPreviousExecutionFeedback(\n      const ::growbox::climate::ClimateExecutionProjection& feedback) noexcept {\n    control_loop_.setPreviousExecutionFeedback(feedback);\n  }\n  void clearPreviousExecutionFeedback() noexcept {\n    control_loop_.clearPreviousExecutionFeedback();\n  }\n  bool hasExternalPreviousExecutionFeedback() const noexcept {\n    return control_loop_.hasExternalPreviousExecutionFeedback();\n  }\n\n  void reset() noexcept;\n\n  bool actuatorFaultLatched() const noexcept {\n''')

# Focused control-loop semantics: known roles override, unknown roles retain compatibility fallback,
# clear/reset/failure remove the external snapshot.
replace_once(
    'test/test_climate_control_loop/test_main.cpp',
    '#include "ClimateControlLoop.h"\n',
    '#include "ClimateControlLoop.h"\n#include "ClimateContract.h"\n')
replace_once(
    'test/test_climate_control_loop/test_main.cpp',
    '''class FixedInference final : public ClimateInferenceProvider {\npublic:\n  bool infer(const ClimateFeatureVector&, ClimatePolicyRequest& output) noexcept override {\n''',
    '''class RecordingInference final : public ClimateInferenceProvider {\npublic:\n  bool infer(const ClimateFeatureVector& features, ClimatePolicyRequest& output) noexcept override {\n    ++calls;\n    last_features = features;\n    output = {};\n    return true;\n  }\n\n  std::size_t calls = 0U;\n  ClimateFeatureVector last_features{};\n};\n\nclass FixedInference final : public ClimateInferenceProvider {\npublic:\n  bool infer(const ClimateFeatureVector&, ClimatePolicyRequest& output) noexcept override {\n''')
insert_before = '''void testHigherIntakeRhStillVentilatesWhenAbsoluteHumidityIsLower() {\n'''
new_test = '''void testExternalPreviousExecutionFeedbackOverridesOnlyKnownRoles() {\n  namespace contract = growbox::climate::contract;\n  RecordingInference inference{};\n  ClimateRuntimeConfig config{};\n  config.mode = ClimatePolicyMode::MlShadow;\n  ClimateRuntimeController runtime(&inference, config);\n  FakeInputSource source{};\n  FakeActuatorSink sink{};\n  ClimateControlLoop loop(runtime, source, sink);\n  ClimateRuntimeDecision decision{};\n\n  const auto first = loop.tick(120'000U, decision);\n  assert(first.command_applied);\n  const PreviousClimateActions internal_previous = loop.previousApplied();\n  assert(internal_previous.heater > 0.0F);\n\n  ClimateExecutionProjection feedback{};\n  feedback.executed.heater = 0.0F;\n  feedback.executed.exhaust_fan = 1.0F;\n  feedback.known_mask = ClimateExecutionKnownHeater;\n  loop.setPreviousExecutionFeedback(feedback);\n  assert(loop.hasExternalPreviousExecutionFeedback());\n\n  const auto second = loop.tick(130'000U, decision);\n  assert(second.command_applied);\n  assert(inference.calls >= 2U);\n  assert(near(inference.last_features.values[contract::index(contract::FeatureIndex::PreviousHeater)],\n              0.0F));\n  assert(near(inference.last_features.values[contract::index(contract::FeatureIndex::PreviousExhaustFan)],\n              internal_previous.exhaust_fan));\n\n  const PreviousClimateActions compatibility_after_external = loop.previousApplied();\n  loop.clearPreviousExecutionFeedback();\n  assert(!loop.hasExternalPreviousExecutionFeedback());\n  const auto third = loop.tick(140'000U, decision);\n  assert(third.command_applied);\n  assert(near(inference.last_features.values[contract::index(contract::FeatureIndex::PreviousHeater)],\n              compatibility_after_external.heater));\n\n  loop.setPreviousExecutionFeedback(feedback);\n  loop.reset();\n  assert(!loop.hasExternalPreviousExecutionFeedback());\n}\n\n'''
replace_once('test/test_climate_control_loop/test_main.cpp', insert_before, new_test + insert_before)
replace_once(
    'test/test_climate_control_loop/test_main.cpp',
    '''  ClimateControlLoop loop(runtime, source, sink);\n  ClimateRuntimeDecision decision{};\n\n  const ClimateLoopResult result = loop.tick(120'000U, decision);\n  assert(result.io_status == ClimateLoopIoStatus::ActuatorApplyFailed);\n''',
    '''  ClimateControlLoop loop(runtime, source, sink);\n  ClimateExecutionProjection stale_feedback{};\n  stale_feedback.executed.heater = 1.0F;\n  stale_feedback.known_mask = ClimateExecutionKnownHeater;\n  loop.setPreviousExecutionFeedback(stale_feedback);\n  ClimateRuntimeDecision decision{};\n\n  const ClimateLoopResult result = loop.tick(120'000U, decision);\n  assert(result.io_status == ClimateLoopIoStatus::ActuatorApplyFailed);\n''')
replace_once(
    'test/test_climate_control_loop/test_main.cpp',
    '''  assert(!loop.actuatorFaultLatched());\n  assert(near(loop.previousApplied().heater, 0.0F));\n\n  sink.outcomes.clear();\n''',
    '''  assert(!loop.actuatorFaultLatched());\n  assert(near(loop.previousApplied().heater, 0.0F));\n  assert(!loop.hasExternalPreviousExecutionFeedback());\n\n  sink.outcomes.clear();\n''')
replace_once(
    'test/test_climate_control_loop/test_main.cpp',
    '''  testConfirmedBinaryStateBecomesRuntimeTruth();\n  testHigherIntakeRhStillVentilatesWhenAbsoluteHumidityIsLower();\n''',
    '''  testConfirmedBinaryStateBecomesRuntimeTruth();\n  testExternalPreviousExecutionFeedbackOverridesOnlyKnownRoles();\n  testHigherIntakeRhStillVentilatesWhenAbsoluteHumidityIsLower();\n''')

# Application composition verifies the forwarding seam exists without changing the default path.
insert_before = '''void testFullIpoRuleSequenceHandlesChangingStaleInvalidAndUnavailableInput() {\n'''
new_app_test = '''void testApplicationForwardsExternalPreviousExecutionFeedbackSeam() {\n  ClimateRuntimeController runtime{};\n  ConstantSnapshotProvider provider(snapshotFor(20.0F));\n  RecordingActuatorSink sink{};\n  ClimateApplication application(runtime, provider, sink);\n  ClimateExecutionProjection feedback{};\n  feedback.executed.exhaust_fan = 1.0F;\n  feedback.known_mask = ClimateExecutionKnownExhaustFan;\n\n  assert(!application.hasExternalPreviousExecutionFeedback());\n  application.setPreviousExecutionFeedback(feedback);\n  assert(application.hasExternalPreviousExecutionFeedback());\n  application.clearPreviousExecutionFeedback();\n  assert(!application.hasExternalPreviousExecutionFeedback());\n}\n\n'''
replace_once('test/test_climate_application_composition/test_main.cpp', insert_before, new_app_test + insert_before)
# Add the new application test at the start of main, independent of existing test ordering.
p = Path('test/test_climate_application_composition/test_main.cpp')
text = p.read_text()
marker = 'int main() {\n'
assert text.count(marker) == 1
text = text.replace(marker, marker + '  testApplicationForwardsExternalPreviousExecutionFeedbackSeam();\n', 1)
p.write_text(text)

print('A7_3A_EDIT_PASS')
