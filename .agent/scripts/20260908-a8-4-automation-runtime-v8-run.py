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
    raise SystemExit('A8_4_V8_IDENTITY_FAIL local HEAD mismatch')
if out(['git', 'rev-parse', 'FETCH_HEAD']) != BASE:
    raise SystemExit('A8_4_V8_IDENTITY_FAIL remote branch mismatch')
if out(['git', 'status', '--porcelain']):
    raise SystemExit('A8_4_V8_IDENTITY_FAIL worktree not clean')
print('A8_4_V8_IDENTITY_PASS')

run(['git', 'fetch', '-q', 'origin', 'agent-control'])

# A8.3 changed only three CMake anchors used by the already-reviewed A8.4 v1
# generator. Temporarily remove those A8.3 registrations from the worktree,
# run the unchanged A8.4 generator, then restore the exact A8.3 registrations
# before any diff checks or tests. No production behavior is dropped.
src_path = Path('src/CMakeLists.txt')
src = src_path.read_text()
executor_src_line = '    "climate/output/OutputLifecycleExecutor.cpp"\n'
if src.count(executor_src_line) != 1:
    raise SystemExit('A8_4_V8_SHIM_FAIL src executor registration')
src_path.write_text(src.replace(executor_src_line, '', 1))

host_path = Path('test/host/CMakeLists.txt')
host = host_path.read_text()
executor_start_marker = 'add_executable(\n  output_lifecycle_executor_tests\n'
executor_end_marker = 'target_compile_options(output_lifecycle_executor_tests PRIVATE -Wall -Wextra -Wpedantic)\n'
start = host.find(executor_start_marker)
if start < 0:
    raise SystemExit('A8_4_V8_SHIM_FAIL host executor target start')
end_start = host.find(executor_end_marker, start)
if end_start < 0:
    raise SystemExit('A8_4_V8_SHIM_FAIL host executor target end')
end = end_start + len(executor_end_marker)
executor_block = host[start:end].strip('\n')
host = host[:start] + host[end:]

supervisor_compile = 'target_compile_options(output_supervisor_lifecycle_tests PRIVATE -Wall -Wextra -Wpedantic)'
semantic_target = 'add_executable(\n  climate_semantic_output_tests'
supervisor_pos = host.find(supervisor_compile)
semantic_pos = host.find(semantic_target, supervisor_pos)
if supervisor_pos < 0 or semantic_pos < 0:
    raise SystemExit('A8_4_V8_SHIM_FAIL host old target anchor')
segment_end = supervisor_pos + len(supervisor_compile)
if host[segment_end:semantic_pos].strip():
    raise SystemExit('A8_4_V8_SHIM_FAIL unexpected host text between anchors')
host = host[:segment_end] + '\n\n' + host[semantic_pos:]

executor_test_line = 'add_test(NAME output_lifecycle_executor_tests COMMAND output_lifecycle_executor_tests)\n'
if host.count(executor_test_line) != 1:
    raise SystemExit('A8_4_V8_SHIM_FAIL host executor add_test')
host = host.replace(executor_test_line, '', 1)
host_path.write_text(host)
print('A8_4_V8_PRE_SHIM_PASS')

Path('/tmp/a8_4_edit_v8.py').write_text(
    out(['git', 'show', 'FETCH_HEAD:.agent/scripts/20260908-a8-4-automation-runtime-v1.py']) + '\n')
Path('/tmp/a8_4_fix_v8.py').write_text(
    out(['git', 'show', 'FETCH_HEAD:.agent/scripts/20260908-a8-4-automation-runtime-v1-fix.py']) + '\n')
run(['python3', '/tmp/a8_4_edit_v8.py'])
run(['python3', '/tmp/a8_4_fix_v8.py'])

# Restore A8.3 registrations around the new A8.4 registrations.
src = src_path.read_text()
src_anchor = ('    "climate/output/OutputSupervisorLifecycle.cpp"\n'
              '    "climate/output/OutputAutomationControl.cpp"\n')
src_restored = ('    "climate/output/OutputSupervisorLifecycle.cpp"\n'
                '    "climate/output/OutputLifecycleExecutor.cpp"\n'
                '    "climate/output/OutputAutomationControl.cpp"\n')
if src.count(src_anchor) != 1:
    raise SystemExit('A8_4_V8_RESTORE_FAIL src anchor')
src_path.write_text(src.replace(src_anchor, src_restored, 1))

host = host_path.read_text()
automation_target = 'add_executable(\n  output_automation_control_tests\n'
supervisor_pos = host.find(supervisor_compile)
automation_pos = host.find(automation_target, supervisor_pos)
if supervisor_pos < 0 or automation_pos < 0:
    raise SystemExit('A8_4_V8_RESTORE_FAIL host automation target anchor')
segment_end = supervisor_pos + len(supervisor_compile)
if host[segment_end:automation_pos].strip():
    raise SystemExit('A8_4_V8_RESTORE_FAIL unexpected host text before automation target')
host = (host[:segment_end] + '\n\n' + executor_block + '\n\n' +
        host[automation_pos:])

supervisor_test = 'add_test(NAME output_supervisor_lifecycle_tests COMMAND output_supervisor_lifecycle_tests)\n'
automation_test = 'add_test(NAME output_automation_control_tests COMMAND output_automation_control_tests)\n'
add_test_anchor = supervisor_test + automation_test
if host.count(add_test_anchor) != 1:
    raise SystemExit('A8_4_V8_RESTORE_FAIL host add_test anchor')
host = host.replace(add_test_anchor, supervisor_test + executor_test_line + automation_test, 1)
host_path.write_text(host)
print('A8_4_V8_POST_SHIM_PASS')

# Reuse the already-reviewed v4 verification/build/commit suffix. Only labels and
# isolated build-directory names are updated; execution semantics are unchanged.
v4_runner = out(['git', 'show', 'FETCH_HEAD:.agent/scripts/20260908-a8-4-automation-runtime-v4-run.py']) + '\n'
marker = "\nrun(['git', 'add', '-N', 'src/climate/output/OutputAutomationControl.cpp',"
marker_pos = v4_runner.find(marker)
if marker_pos < 0:
    raise SystemExit('A8_4_V8_VERIFY_SUFFIX_FAIL marker')
suffix = v4_runner[marker_pos:]
suffix = suffix.replace('A8_4_V4', 'A8_4_V8').replace('a8-4-v4', 'a8-4-v8')
exec(compile(suffix, '/tmp/a8_4_v8_verify_suffix.py', 'exec'), globals(), globals())
