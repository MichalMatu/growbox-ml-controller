import os
import subprocess
from pathlib import Path

BASE = 'bee217ce60afff93a965ee53d08176792c0f0178'
BRANCH = 'mvp/environment-controller'
EXPECTED = sorted([
    'src/CMakeLists.txt',
    'src/climate/ClimateV6RealInputRuntime.cpp',
    'src/climate/output/OutputAutomationControl.cpp',
    'src/climate/output/OutputAutomationControl.h',
    'src/climate/runtime/Stage28ServiceConsole.cpp',
    'src/climate/runtime/Stage28ServiceConsole.h',
    'src/climate/runtime/Stage28ServiceConsoleCommand.cpp',
    'src/climate/runtime/Stage28ServiceConsoleCommand.h',
    'test/host/CMakeLists.txt',
    'test/test_output_automation_control/test_main.cpp',
    'test/test_stage28_service_console/test_main.cpp',
])


def run(cmd, env=None):
    print('+', ' '.join(cmd), flush=True)
    subprocess.run(cmd, check=True, env=env)


def out(cmd):
    return subprocess.check_output(cmd, text=True).strip()

run(['git', 'fetch', '-q', 'origin', BRANCH])
if out(['git', 'rev-parse', 'HEAD']) != BASE:
    raise SystemExit('A8_4_V3_IDENTITY_FAIL local HEAD mismatch')
if out(['git', 'rev-parse', 'FETCH_HEAD']) != BASE:
    raise SystemExit('A8_4_V3_IDENTITY_FAIL remote branch mismatch')
if out(['git', 'status', '--porcelain']):
    raise SystemExit('A8_4_V3_IDENTITY_FAIL worktree not clean')
print('A8_4_V3_IDENTITY_PASS')

run(['git', 'fetch', '-q', 'origin', 'agent-control'])
generator = out(['git', 'show', 'FETCH_HEAD:.agent/scripts/20260908-a8-4-automation-runtime-v1.py']) + '\n'
old_helper = '''def replace_once(path: str, old: str, new: str) -> None:\n    p = ROOT / path\n    text = p.read_text()\n    if text.count(old) != 1:\n        raise SystemExit(f'{path}: expected one replacement, found {text.count(old)}')\n    p.write_text(text.replace(old, new, 1))\n'''
new_helper = r'''def normalize_replace_text(value: str) -> str:
    marker = '\x00A8_4_CRLF\x00'
    return value.replace('\\r\\n', marker).replace('\\n', '\n').replace(marker, '\\r\\n')


def replace_once(path: str, old: str, new: str) -> None:
    p = ROOT / path
    text = p.read_text()
    old = normalize_replace_text(old)
    new = normalize_replace_text(new)
    if text.count(old) != 1:
        raise SystemExit(f'{path}: expected one replacement, found {text.count(old)}')
    p.write_text(text.replace(old, new, 1))
'''
if generator.count(old_helper) != 1:
    raise SystemExit(f'A8_4_V3_GENERATOR_FIX_FAIL helper_matches={generator.count(old_helper)}')
generator = generator.replace(old_helper, new_helper, 1)
Path('/tmp/a8_4_edit_v3.py').write_text(generator)
Path('/tmp/a8_4_fix.py').write_text(
    out(['git', 'show', 'FETCH_HEAD:.agent/scripts/20260908-a8-4-automation-runtime-v1-fix.py']) + '\n')
print('A8_4_V3_GENERATOR_FIX_PASS')
run(['python3', '/tmp/a8_4_edit_v3.py'])
run(['python3', '/tmp/a8_4_fix.py'])

run(['git', 'add', '-N', 'src/climate/output/OutputAutomationControl.cpp',
     'src/climate/output/OutputAutomationControl.h',
     'test/test_output_automation_control/test_main.cpp'])
run(['git', 'diff', '--check'])
changed = sorted(filter(None, out(['git', 'diff', '--name-only']).splitlines()))
if changed != EXPECTED:
    raise SystemExit(f'A8_4_V3_ALLOWLIST_FAIL changed={changed!r}')

runtime = Path('src/climate/ClimateV6RealInputRuntime.cpp').read_text()
control = Path('src/climate/output/OutputAutomationControl.cpp').read_text()
console_cmd = Path('src/climate/runtime/Stage28ServiceConsoleCommand.cpp').read_text()
if 'supervisor_context.mode = automation_report.mode;' not in runtime:
    raise SystemExit('A8_4_V3_STATIC_FAIL runtime does not use lifecycle mode')
if 'supervisor_context.mode = output::SupervisorMode::Automatic;' in runtime:
    raise SystemExit('A8_4_V3_STATIC_FAIL hard-coded automatic mode remains')
if 'automation_control.tick(now_ms, schedule_intent, safety_snapshot.envelope)' not in runtime:
    raise SystemExit('A8_4_V3_STATIC_FAIL automation tick missing')
if 'hardSafetyActive' not in control or 'SafetyDeferred' not in control:
    raise SystemExit('A8_4_V3_STATIC_FAIL safety defer missing')
if 'OutputLifecycleCommand::DisableAutomation' not in control or 'OutputLifecycleCommand::EnableAutomation' not in control:
    raise SystemExit('A8_4_V3_STATIC_FAIL lifecycle ON/OFF commands missing')
if 'equalsIgnoreCase(tokens[0],"automation")' not in console_cmd:
    raise SystemExit('A8_4_V3_STATIC_FAIL service command missing')
print('A8_4_V3_STATIC_PASS')

build = 'build/host-tests-a8-4-v3'
run(['cmake', '-S', 'test/host', '-B', build])
targets = [
    'output_automation_control_tests',
    'output_lifecycle_executor_tests',
    'output_supervisor_lifecycle_tests',
    'output_policy_config_tests',
    'output_supervisor_resolver_tests',
    'output_supervisor_executor_tests',
    'climate_output_supervisor_sink_tests',
    'climate_control_loop_tests',
    'climate_application_composition_tests',
    'stage28d_lamp_safety_tests',
    'stage28_service_console_tests',
    'climate_semantic_output_tests',
]
run(['cmake', '--build', build, '--parallel', '--target', *targets])
regex = '^(' + '|'.join(targets) + ')$'
run(['ctest', '--test-dir', build, '-R', regex, '--output-on-failure'])
print('A8_4_V3_FOCUSED_PASS')

fw_build = 'build/stage27c-a8-4-v3'
Path(fw_build).mkdir(parents=True, exist_ok=True)
env = os.environ.copy()
env.update({
    'STAGE27C_BUILD_DIR': fw_build,
    'STAGE27C_SDKCONFIG': f'{fw_build}/sdkconfig',
    'GROWBOX_RF433_LOOPBACK_ENABLED': '1',
    'GROWBOX_STAGE28_REAL_OUTPUTS_ENABLED': '1',
    'GROWBOX_RF433_LOOPBACK_AUTO_SMOKE': '0',
    'GROWBOX_RF433_REMOTE_CAPTURE_ENABLED': '0',
})
run(['bash', 'scripts/stage27c_crowpanel.sh', 'build'], env=env)
print('A8_4_V3_CANONICAL_BUILD_PASS')

run(['git', 'diff', '--check'])
run(['git', 'add', *EXPECTED])
run(['git', 'diff', '--cached', '--check'])
staged = sorted(filter(None, out(['git', 'diff', '--cached', '--name-only']).splitlines()))
if staged != EXPECTED:
    raise SystemExit(f'A8_4_V3_STAGED_ALLOWLIST_FAIL staged={staged!r}')
run(['git', 'commit', '-m', 'Add configurable automation off behavior'])
commit = out(['git', 'rev-parse', 'HEAD'])
run(['git', 'push', 'origin', f'HEAD:{BRANCH}'])
run(['git', 'fetch', '-q', 'origin', BRANCH])
if out(['git', 'rev-parse', 'FETCH_HEAD']) != commit:
    raise SystemExit('A8_4_V3_PUSH_VERIFY_FAIL')
if out(['git', 'status', '--porcelain']):
    raise SystemExit('A8_4_V3_CLEAN_FAIL')
print(f'A8_4_V3_PASS commit={commit}')
