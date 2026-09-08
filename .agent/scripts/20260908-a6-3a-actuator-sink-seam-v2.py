from pathlib import Path
import re

header = Path('src/climate/ClimateApplication.h')
text = header.read_text()
if '#include <optional>\n' not in text:
    text = text.replace('#include <cstdint>\n', '#include <cstdint>\n#include <optional>\n', 1)
pattern = re.compile(
    r'(  ClimateApplication\(::growbox::climate::ClimateRuntimeController& runtime,\n'
    r'                     ClimateSnapshotProvider& snapshot_provider,\n'
    r'                     ClimateRoleDriver& role_driver\) noexcept;\n)'
)
replacement = (
    r'\1'
    '  ClimateApplication(::growbox::climate::ClimateRuntimeController& runtime,\n'
    '                     ClimateSnapshotProvider& snapshot_provider,\n'
    '                     ::growbox::climate::ClimateActuatorSink& actuator_sink) noexcept;\n'
)
text, count = pattern.subn(replacement, text, count=1)
assert count == 1
text, count = re.subn(
    r'  ClimateActuatorAdapter actuator_adapter_;\n',
    '  std::optional<ClimateActuatorAdapter> actuator_adapter_;\n',
    text,
    count=1,
)
assert count == 1
header.write_text(text)

source = Path('src/climate/ClimateApplication.cpp')
text = source.read_text()
pattern = re.compile(
    r'(ClimateApplication::ClimateApplication\(::growbox::climate::ClimateRuntimeController& runtime,\n'
    r'                                       ClimateSnapshotProvider& snapshot_provider,\n'
    r'                                       ClimateRoleDriver& role_driver\) noexcept\n)'
    r'    : input_adapter_\(snapshot_provider\), actuator_adapter_\(role_driver\),\n'
    r'      control_loop_\(runtime, input_adapter_, actuator_adapter_\) \{\}\n'
)
replacement = (
    r'\1'
    '    : input_adapter_(snapshot_provider), actuator_adapter_(std::in_place, role_driver),\n'
    '      control_loop_(runtime, input_adapter_, *actuator_adapter_) {}\n\n'
    'ClimateApplication::ClimateApplication(\n'
    '    ::growbox::climate::ClimateRuntimeController& runtime,\n'
    '    ClimateSnapshotProvider& snapshot_provider,\n'
    '    ::growbox::climate::ClimateActuatorSink& actuator_sink) noexcept\n'
    '    : input_adapter_(snapshot_provider), actuator_adapter_(std::nullopt),\n'
    '      control_loop_(runtime, input_adapter_, actuator_sink) {}\n'
)
text, count = pattern.subn(replacement, text, count=1)
assert count == 1
source.write_text(text)

test = Path('test/test_climate_application_composition/test_main.cpp')
text = test.read_text()
marker = '''class CountingRoleDriver final : public ClimateRoleDriver {\npublic:\n  bool apply(ClimateActuatorRole, float, std::uint64_t) noexcept override {\n    ++calls;\n    return true;\n  }\n\n  std::size_t calls = 0U;\n};\n\n'''
assert marker in text
addition = marker + '''class RecordingActuatorSink final : public ClimateActuatorSink {\npublic:\n  bool apply(const ClimatePolicyRequest& request, std::uint64_t monotonic_ms) noexcept override {\n    ++calls;\n    last_request = request;\n    last_monotonic_ms = monotonic_ms;\n    return true;\n  }\n\n  std::size_t calls = 0U;\n  ClimatePolicyRequest last_request{};\n  std::uint64_t last_monotonic_ms = 0U;\n};\n\n'''
text = text.replace(marker, addition, 1)

marker = '''void testProviderAndDriverImplementationsAreReplaceableAtCompositionBoundary() {\n  ConstantSnapshotProvider provider(snapshotFor(20.0F));\n  CountingRoleDriver driver{};\n  ClimateRuntimeController runtime{};\n  ClimateApplication application(runtime, provider, driver);\n  ClimateRuntimeDecision decision{};\n\n  const auto result = application.tick(500'000U, decision);\n  assert(result.io_status == ClimateLoopIoStatus::Ok);\n  assert(result.input_sampled);\n  assert(result.command_applied);\n  assert(provider.calls == 1U);\n  assert(driver.calls == kRoleCount);\n  assert(decision.applied.heater > 0.0F);\n}\n\n'''
assert marker in text
addition = marker + '''void testCompleteActuatorSinkCanBeInjectedWithoutRoleFanout() {\n  ConstantSnapshotProvider provider(snapshotFor(20.0F));\n  RecordingActuatorSink sink{};\n  ClimateRuntimeController runtime{};\n  ClimateApplication application(runtime, provider, static_cast<ClimateActuatorSink&>(sink));\n  ClimateRuntimeDecision decision{};\n\n  const auto result = application.tick(510'000U, decision);\n  assert(result.io_status == ClimateLoopIoStatus::Ok);\n  assert(result.input_sampled);\n  assert(result.command_applied);\n  assert(provider.calls == 1U);\n  assert(sink.calls == 1U);\n  assert(sink.last_monotonic_ms == 510'000U);\n  assert(same(sink.last_request, decision.rule.safe));\n  assert(same(sink.last_request, decision.applied));\n  assert(samePrevious(application.previousApplied(), sink.last_request));\n}\n\n'''
text = text.replace(marker, addition, 1)
old = '''  testDoubleFailureLatchesSkipsNormalControlAndResetRestoresOperation();\n  testProviderAndDriverImplementationsAreReplaceableAtCompositionBoundary();\n  return 0;\n}\n'''
new = '''  testDoubleFailureLatchesSkipsNormalControlAndResetRestoresOperation();\n  testProviderAndDriverImplementationsAreReplaceableAtCompositionBoundary();\n  testCompleteActuatorSinkCanBeInjectedWithoutRoleFanout();\n  return 0;\n}\n'''
assert old in text
text = text.replace(old, new, 1)
test.write_text(text)
