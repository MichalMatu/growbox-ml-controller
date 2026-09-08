import os
import re
import shutil
import subprocess
from pathlib import Path

BASE = '7cbaede370432ad6e1b1120bec0715b90145888b'
BRANCH = 'mvp/environment-controller'
EXPECTED = ['src/climate/ClimateV6RealInputRuntime.cpp']
BEFORE_DIR = Path('build/stage27c-a11-5-before')
AFTER_DIR = Path('build/stage27c-a11-5-after')
HOST_DIR = Path('build/host-a11-5')


def run(cmd, env=None):
    print('+', ' '.join(str(x) for x in cmd), flush=True)
    subprocess.run([str(x) for x in cmd], check=True, env=env)


def out(cmd, env=None):
    return subprocess.check_output([str(x) for x in cmd], text=True, env=env).strip()


def shell_out(command):
    return subprocess.check_output(['bash', '-lc', command], text=True).strip()


def canonical_env(build_dir):
    env = os.environ.copy()
    env.update({
        'STAGE27C_BUILD_DIR': str(build_dir),
        'STAGE27C_SDKCONFIG': str(build_dir / 'sdkconfig'),
        'GROWBOX_RF433_LOOPBACK_ENABLED': '1',
        'GROWBOX_STAGE28_REAL_OUTPUTS_ENABLED': '1',
        'GROWBOX_STAGE28_THERMAL_TEST_SEQUENCE_ENABLED': '0',
        'GROWBOX_RF433_REMOTE_CAPTURE_ENABLED': '0',
    })
    return env


def build_canonical(build_dir):
    shutil.rmtree(build_dir, ignore_errors=True)
    run(['bash', 'scripts/stage27c_crowpanel.sh', 'build'], env=canonical_env(build_dir))


def parse_int(value):
    return int(value, 0)


def build_metrics(build_dir):
    elf_files = list(build_dir.glob('*.elf'))
    if len(elf_files) != 1:
        raise SystemExit(f'A11_5_METRIC_FAIL expected one ELF in {build_dir}, found {elf_files!r}')
    elf = elf_files[0]
    size_text = shell_out(
        f'source scripts/source_idf.sh >/dev/null 2>&1; '
        f'xtensa-esp32s3-elf-size "{elf}"'
    )
    rows = [line.split() for line in size_text.splitlines() if line.strip()]
    if len(rows) < 2 or len(rows[-1]) < 6:
        raise SystemExit(f'A11_5_METRIC_FAIL unexpected size output: {size_text!r}')
    text_size = parse_int(rows[-1][0])
    data_size = parse_int(rows[-1][1])
    bss_size = parse_int(rows[-1][2])

    disassembly = shell_out(
        f'source scripts/source_idf.sh >/dev/null 2>&1; '
        f'xtensa-esp32s3-elf-objdump -d -C "{elf}"'
    )
    marker = 'growbox::app::climate_io::runClimateV6RealInputRuntime()'
    pos = disassembly.find(marker)
    if pos < 0:
        raise SystemExit('A11_5_STACK_FAIL runtime function symbol missing from objdump')
    window = disassembly[pos:pos + 2500]
    match = re.search(r'\bentry\s+a1,\s*(0x[0-9a-fA-F]+|\d+)', window)
    if match is None:
        raise SystemExit(f'A11_5_STACK_FAIL unable to parse Xtensa entry frame: {window[:600]!r}')
    frame_bytes = int(match.group(1), 0)

    sdkconfig = (build_dir / 'sdkconfig').read_text()
    stack_match = re.search(r'^CONFIG_ESP_MAIN_TASK_STACK_SIZE=(\d+)$', sdkconfig, flags=re.M)
    if stack_match is None:
        raise SystemExit('A11_5_STACK_FAIL main task stack config missing')
    main_stack = int(stack_match.group(1))
    return {
        'text': text_size,
        'data': data_size,
        'bss': bss_size,
        'static_dram': data_size + bss_size,
        'frame': frame_bytes,
        'main_stack': main_stack,
    }


run(['git', 'fetch', '-q', 'origin', BRANCH])
if out(['git', 'rev-parse', 'HEAD']) != BASE:
    raise SystemExit('A11_5_IDENTITY_FAIL local HEAD mismatch')
if out(['git', 'rev-parse', 'FETCH_HEAD']) != BASE:
    raise SystemExit('A11_5_IDENTITY_FAIL remote branch mismatch')
if out(['git', 'status', '--porcelain']):
    raise SystemExit('A11_5_IDENTITY_FAIL worktree not clean')
print('A11_5_IDENTITY_PASS')

# Software-only baseline evidence before touching source.
build_canonical(BEFORE_DIR)
before = build_metrics(BEFORE_DIR)
print('A11_5_BEFORE ' + ' '.join(f'{k}={v}' for k, v in before.items()))
if before['main_stack'] != 16384:
    raise SystemExit(f"A11_5_STACK_FAIL RF baseline main stack changed: {before['main_stack']}")

path = Path('src/climate/ClimateV6RealInputRuntime.cpp')
text = path.read_text()

old = '''        rf_radio_(rf433::Rf433RmtLoopback::Config{rf_diagnostics_config_.tx_gpio,
                                                  rf_diagnostics_config_.rx_gpio}),
        rf_diagnostics_(rf_diagnostics_config_, rf_radio_) {}
'''
new = '''        rf_radio_(rf433::Rf433RmtLoopback::Config{rf_diagnostics_config_.tx_gpio,
                                                  rf_diagnostics_config_.rx_gpio}),
        rf_diagnostics_(rf_diagnostics_config_, rf_radio_), rf_frame_sender_(rf_radio_),
        rf_output_transport_(rf_frame_sender_) {}
'''
if text.count(old) != 1:
    raise SystemExit(f'A11_5_PATCH_FAIL RuntimeIoOwner initializer count={text.count(old)}')
text = text.replace(old, new, 1)

old = '''  rf433::Rf433RmtLoopback& rfRadio() noexcept {
    return rf_radio_;
  }

private:
'''
new = '''  rf433::Rf433RmtLoopback& rfRadio() noexcept {
    return rf_radio_;
  }

  rf433::Rf433OutputTransport& rfOutputTransport() noexcept {
    return rf_output_transport_;
  }

private:
'''
if text.count(old) != 1:
    raise SystemExit('A11_5_PATCH_FAIL RuntimeIoOwner getter anchor mismatch')
text = text.replace(old, new, 1)

old = '''  rf433::Rf433RmtLoopback rf_radio_;
  runtime::Stage28RfDiagnostics rf_diagnostics_;
};
'''
new = '''  rf433::Rf433RmtLoopback rf_radio_;
  runtime::Stage28RfDiagnostics rf_diagnostics_;
  rf433::Rf433RmtFrameSender rf_frame_sender_;
  rf433::Rf433OutputTransport rf_output_transport_;
};
'''
if text.count(old) != 1:
    raise SystemExit('A11_5_PATCH_FAIL RuntimeIoOwner field anchor mismatch')
text = text.replace(old, new, 1)

insert_marker = '\n} // namespace\n\n[[noreturn]] void runClimateV6RealInputRuntime() noexcept {'
if text.count(insert_marker) != 1:
    raise SystemExit('A11_5_PATCH_FAIL anonymous namespace close anchor mismatch')
owner_code = r'''

const output::OutputPolicyConfig& safeOutputPolicy() noexcept {
  static const output::OutputPolicyConfig policy = stage28d::makeOutputPolicyConfig();
  return policy;
}

output::OutputSupervisorResolverConfig makeRuntimeSupervisorConfig(
    output::BinaryActuatorPolicy& exhaust_policy,
    output::BinaryActuatorPolicy& humidifier_policy) noexcept {
  output::OutputSupervisorResolverConfig config{};
  config.endpoints[0] = {stage28d::kScheduledLightEndpoint, nullptr};
  config.endpoints[1] = {stage28d::kExhaustFanEndpoint, &exhaust_policy};
  config.endpoints[2] = {stage28d::kHumidifierEndpoint, &humidifier_policy};
  config.count = 3U;
  return config;
}

class RuntimeOutputOwner final {
public:
  RuntimeOutputOwner(output::OutputTransport& real_transport, const bool& real_enabled,
                     runtime::Stage28RfDiagnostics& diagnostics,
                     const output::OutputPolicyConfig& policy,
                     output::OutputStateStore& state_store) noexcept
      : policy_(policy),
        semantic_output_config_(stage28d::makeClimateSemanticOutputConfig(policy_)),
        exhaust_policy_(kExhaustPolicyConfig), humidifier_policy_(kHumidifierPolicyConfig),
        supervisor_config_(makeRuntimeSupervisorConfig(exhaust_policy_, humidifier_policy_)),
        supervisor_transport_(real_transport, real_enabled), output_lifecycle_(policy_),
        lifecycle_executor_(policy_, output_lifecycle_, supervisor_transport_, state_store,
                            supervisor_config_),
        runtime_lifecycle_(output_lifecycle_, lifecycle_executor_),
        automation_control_(output_lifecycle_, lifecycle_executor_),
        manual_control_(policy_, output_lifecycle_), maintenance_rf_transport_(diagnostics),
        maintenance_control_(policy_, output_lifecycle_, automation_control_, lifecycle_executor_,
                             state_store, supervisor_config_, maintenance_rf_transport_),
        supervisor_resolver_(supervisor_config_),
        supervisor_executor_(supervisor_transport_, state_store, supervisor_config_),
        supervisor_sink_(semantic_output_config_, supervisor_resolver_, supervisor_executor_,
                         state_store) {
    bindings_valid_ = stage28d::validateOutputBindings(semantic_output_config_, policy_) ==
                      stage28d::OutputBindingStatus::Ok;
    valid_ = bindings_valid_ && output_lifecycle_.valid() && lifecycle_executor_.valid() &&
             runtime_lifecycle_.valid() && automation_control_.valid() && manual_control_.valid() &&
             maintenance_control_.valid() && supervisor_sink_.valid();
  }

  RuntimeOutputOwner(const RuntimeOutputOwner&) = delete;
  RuntimeOutputOwner& operator=(const RuntimeOutputOwner&) = delete;

  bool valid() const noexcept { return valid_; }
  bool bindingsValid() const noexcept { return bindings_valid_; }

  RuntimeOutputTransport& transport() noexcept { return supervisor_transport_; }
  output::OutputSupervisorLifecycle& lifecycle() noexcept { return output_lifecycle_; }
  output::OutputLifecycleExecutor& lifecycleExecutor() noexcept { return lifecycle_executor_; }
  output::OutputRuntimeLifecycleControl& runtimeLifecycle() noexcept { return runtime_lifecycle_; }
  output::OutputAutomationControl& automationControl() noexcept { return automation_control_; }
  output::OutputManualControl& manualControl() noexcept { return manual_control_; }
  output::OutputMaintenanceControl& maintenanceControl() noexcept { return maintenance_control_; }
  ClimateOutputSupervisorSink& supervisorSink() noexcept { return supervisor_sink_; }

private:
  output::OutputPolicyConfig policy_{};
  ClimateSemanticOutputConfig semantic_output_config_{};
  output::BinaryActuatorPolicy exhaust_policy_;
  output::BinaryActuatorPolicy humidifier_policy_;
  output::OutputSupervisorResolverConfig supervisor_config_{};
  RuntimeOutputTransport supervisor_transport_;
  output::OutputSupervisorLifecycle output_lifecycle_;
  output::OutputLifecycleExecutor lifecycle_executor_;
  output::OutputRuntimeLifecycleControl runtime_lifecycle_;
  output::OutputAutomationControl automation_control_;
  output::OutputManualControl manual_control_;
  runtime::Stage28MaintenanceRfTransport maintenance_rf_transport_;
  output::OutputMaintenanceControl maintenance_control_;
  output::OutputSupervisorResolver supervisor_resolver_;
  output::OutputSupervisorExecutor supervisor_executor_;
  ClimateOutputSupervisorSink supervisor_sink_;
  bool bindings_valid_{false};
  bool valid_{false};
};
'''
text = text.replace(insert_marker, owner_code + insert_marker, 1)

pattern = re.compile(
    r'''  const bool rf_ready = runtime_io_owner\.beginRf\(\);\n.*?'''
    r'''  runtime::Stage28ServiceConsole service_console\(''',
    flags=re.S,
)
replacement = r'''  const bool rf_ready = runtime_io_owner.beginRf();
  static output::OutputStateStore output_state_store;
  static constexpr std::array<output::OutputEndpointId, output::kOutputEndpointCapacity>
      kShadowOutputEndpoints{stage28d::kExhaustFanEndpoint, stage28d::kScheduledLightEndpoint,
                             stage28d::kHumidifierEndpoint};
  const bool output_state_store_ready =
      output_state_store.configure(kShadowOutputEndpoints, kShadowOutputEndpoints.size());
  if (!output_state_store_ready) {
    ESP_LOGE(kTag, "Output state-store shadow configuration failed");
  }

  static output::OutputNvsBackend output_nvs_backend;
  static output::OutputPersistenceStore output_persistence_store(output_nvs_backend,
                                                                 safeOutputPolicy());
  static output::OutputPersistenceCoordinator output_persistence(output_persistence_store);
  const auto persistence_init = output_state_store_ready
                                    ? output_persistence.initialize(output_state_store)
                                    : output::OutputPersistenceCoordinatorInitResult{};
  const output::OutputPolicyConfig& output_policy =
      output_persistence.valid() ? output_persistence.policy() : safeOutputPolicy();
  if (!output_persistence.valid()) {
    ESP_LOGW(kTag, "Output persistence unavailable status=%u store_status=%u; using safe policy",
             static_cast<unsigned>(persistence_init.status),
             static_cast<unsigned>(persistence_init.load.status));
  }

  static bool real_transport_available = false;
  real_transport_available = GROWBOX_STAGE28_REAL_OUTPUTS_ENABLED != 0 && rf_ready;

  // The pre-supervisor Gate6 qualification path was a direct configured-output
  // writer. Keep the build knob fail-closed until A13 defines the replacement
  // supervisor-owned hardware qualification contract.
  if (GROWBOX_STAGE28_THERMAL_TEST_SEQUENCE_ENABLED != 0) {
    ESP_LOGW(kTag,
             "Legacy Gate6 thermal qualification is retired; locking real transport until A13");
    real_transport_available = false;
  }

  static RuntimeOutputOwner runtime_output_owner(runtime_io_owner.rfOutputTransport(),
                                                 real_transport_available, rf_diagnostics,
                                                 output_policy, output_state_store);
  const bool output_bindings_valid = runtime_output_owner.bindingsValid();
  if (!output_bindings_valid) {
    real_transport_available = false;
  }

  static bool real_output_ready = false;
  real_output_ready = false;
  if (GROWBOX_STAGE28_REAL_OUTPUTS_ENABLED != 0 && !real_transport_available) {
    ESP_LOGE(kTag, "Real-output transport unavailable; automatic outputs remain fake-locked");
  }

  static runtime::RuntimeTimingMetrics runtime_timing{};
  runtime_timing.loop_active.budget_us = kTickIntervalMs * 1000U;

  runtime::Stage27InsideSource inside(ble, scd41);
  runtime::Stage27NearbySource outside(ble);
  runtime::FixedStage27ScheduleConfigSource schedule_config;
  CompositeClimateSnapshotProvider composite(inside, outside, clock, schedule_config);

  auto& supervisor_transport = runtime_output_owner.transport();
  auto& output_lifecycle = runtime_output_owner.lifecycle();
  auto& lifecycle_executor = runtime_output_owner.lifecycleExecutor();
  auto& runtime_lifecycle = runtime_output_owner.runtimeLifecycle();
  auto& automation_control = runtime_output_owner.automationControl();
  auto& manual_control = runtime_output_owner.manualControl();
  auto& maintenance_control = runtime_output_owner.maintenanceControl();
  auto& supervisor_sink = runtime_output_owner.supervisorSink();

  if (!runtime_output_owner.valid()) {
    ESP_LOGE(kTag, "Output supervisor/lifecycle composition invalid; physical execution locked");
    // There is no direct emergency writer here anymore. If the supervisor cannot
    // be composed, fail closed by disabling transport ownership for this boot.
    real_transport_available = false;
    real_output_ready = false;
  }

  runtime::Stage28ServiceConsole service_console('''
text, count = pattern.subn(replacement, text, count=1)
if count != 1:
    raise SystemExit(f'A11_5_PATCH_FAIL composition block replacements={count}')

path.write_text(text)

# Structural proof: long-lived output owner objects must no longer be automatic
# locals in the non-returning runtime frame.
function_marker = '[[noreturn]] void runClimateV6RealInputRuntime() noexcept {'
function_text = text[text.index(function_marker):]
for forbidden in (
    'rf433::Rf433RmtFrameSender rf_frame_sender(',
    'rf433::Rf433OutputTransport rf_output_transport(',
    'output::BinaryActuatorPolicy exhaust_policy(',
    'output::BinaryActuatorPolicy humidifier_policy(',
    'output::OutputSupervisorLifecycle output_lifecycle(',
    'output::OutputLifecycleExecutor lifecycle_executor(',
    'output::OutputRuntimeLifecycleControl runtime_lifecycle(',
    'output::OutputAutomationControl automation_control(',
    'output::OutputManualControl manual_control(',
    'runtime::Stage28MaintenanceRfTransport maintenance_rf_transport(',
    'output::OutputMaintenanceControl maintenance_control(',
    'output::OutputSupervisorResolver supervisor_resolver(',
    'output::OutputSupervisorExecutor supervisor_executor(',
    'ClimateOutputSupervisorSink supervisor_sink(',
):
    if forbidden in function_text:
        raise SystemExit(f'A11_5_STRUCTURE_FAIL automatic long-lived owner remains: {forbidden}')
for required in (
    'class RuntimeOutputOwner final',
    'static RuntimeOutputOwner runtime_output_owner(',
    'static runtime::RuntimeTimingMetrics runtime_timing{};',
    'rf433::Rf433OutputTransport& rfOutputTransport() noexcept',
):
    if required not in text:
        raise SystemExit(f'A11_5_STRUCTURE_FAIL missing {required!r}')

run(['git', 'add', '-N', *EXPECTED])
changed = sorted(out(['git', 'diff', '--name-only']).splitlines())
if changed != EXPECTED:
    raise SystemExit(f'A11_5_SCOPE_FAIL changed={changed!r} expected={EXPECTED!r}')
run(['git', 'diff', '--check'])
run(['python3', 'scripts/check_output_rf_ownership.py'])
py = '.venv/bin/python' if Path('.venv/bin/python').exists() else 'python3'
run([py, '-m', 'pytest', 'tests/test_output_execution_ownership.py', '-q'])

shutil.rmtree(HOST_DIR, ignore_errors=True)
run(['cmake', '-S', 'test/host', '-B', HOST_DIR])
focused_targets = [
    'output_supervisor_resolver_tests',
    'output_supervisor_executor_tests',
    'climate_output_supervisor_sink_tests',
    'output_runtime_lifecycle_control_tests',
    'output_automation_control_tests',
    'output_maintenance_control_tests',
    'output_execution_telemetry_tests',
    'output_persistence_coordinator_tests',
    'output_lifecycle_executor_tests',
]
run(['cmake', '--build', HOST_DIR, '--parallel', '--target', *focused_targets])
regex = '^(' + '|'.join(focused_targets) + ')$'
run(['ctest', '--test-dir', HOST_DIR, '-R', regex, '--output-on-failure'])

build_canonical(AFTER_DIR)
after = build_metrics(AFTER_DIR)
print('A11_5_AFTER ' + ' '.join(f'{k}={v}' for k, v in after.items()))
print(
    'A11_5_DELTA '
    f"text={after['text'] - before['text']} "
    f"data={after['data'] - before['data']} "
    f"bss={after['bss'] - before['bss']} "
    f"static_dram={after['static_dram'] - before['static_dram']} "
    f"runtime_frame={after['frame'] - before['frame']} "
    f"main_stack={after['main_stack'] - before['main_stack']}"
)
if after['main_stack'] != 16384 or after['main_stack'] != before['main_stack']:
    raise SystemExit('A11_5_STACK_FAIL RF main-task stack must remain exactly 16384')
if after['frame'] > before['frame']:
    raise SystemExit(
        f"A11_5_STACK_FAIL runtime frame grew before={before['frame']} after={after['frame']}"
    )
if after['static_dram'] - before['static_dram'] > 8192:
    raise SystemExit('A11_5_MEMORY_FAIL static DRAM growth exceeds 8 KiB cleanup budget')
if after['text'] - before['text'] > 8192:
    raise SystemExit('A11_5_SIZE_FAIL .text growth exceeds 8 KiB cleanup budget')

run(['git', 'add', *EXPECTED])
run(['git', 'commit', '-m', 'Finalize output runtime composition ownership'])
commit = out(['git', 'rev-parse', 'HEAD'])
if out(['git', 'rev-parse', 'HEAD^']) != BASE:
    raise SystemExit('A11_5_PARENT_FAIL')
run(['git', 'push', 'origin', f'HEAD:{BRANCH}'])
run(['git', 'fetch', '-q', 'origin', BRANCH])
if out(['git', 'rev-parse', 'FETCH_HEAD']) != commit:
    raise SystemExit('A11_5_PUSH_VERIFY_FAIL')
print(f'A11_5_PASS commit={commit}')
