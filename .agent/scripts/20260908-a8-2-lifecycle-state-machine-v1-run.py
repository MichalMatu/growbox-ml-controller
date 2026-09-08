import subprocess

EXPECTED = '15139db108a919cfe3de18e193499fcb6149d0d6'
FILES = sorted([
    'src/CMakeLists.txt',
    'src/climate/output/OutputSupervisorLifecycle.cpp',
    'src/climate/output/OutputSupervisorLifecycle.h',
    'test/host/CMakeLists.txt',
    'test/test_output_supervisor_lifecycle/test_main.cpp',
])


def out(cmd: str) -> str:
    return subprocess.check_output(cmd, shell=True, text=True).strip()


def run(cmd: str) -> None:
    print('+', cmd, flush=True)
    subprocess.run(cmd, shell=True, check=True)

run('git fetch -q origin mvp/environment-controller')
assert out('git rev-parse HEAD') == EXPECTED
assert out('git rev-parse FETCH_HEAD') == EXPECTED
assert not out('git status --porcelain')
print('A8_2_IDENTITY_PASS', flush=True)

run('git fetch -q origin agent-control')
run("git show FETCH_HEAD:.agent/scripts/20260908-a8-2-lifecycle-state-machine-v1.py > /tmp/a8_2_edit.py")
run('python3 /tmp/a8_2_edit.py')
run('git add -N src/climate/output/OutputSupervisorLifecycle.cpp src/climate/output/OutputSupervisorLifecycle.h test/test_output_supervisor_lifecycle/test_main.cpp')
run('git diff --check')
changed = sorted(out('git diff --name-only').splitlines())
assert changed == FILES, changed

header = open('src/climate/output/OutputSupervisorLifecycle.h').read()
source = open('src/climate/output/OutputSupervisorLifecycle.cpp').read()
assert 'OutputTransport' not in header + source
assert 'sleep' not in source.lower()
assert 'SupervisorMode::Disabled' in source
assert 'SupervisorMode::FaultLocked' in source
assert 'OutputLifecycleEvent::AutomationOff' in source
assert 'OutputLifecycleEvent::Recovery' in source
assert 'OutputLifecycleEvent::Fault' in source
print('A8_2_STATIC_PASS', flush=True)

build = 'build/host-tests-a8-2-v1'
targets = [
    'output_supervisor_lifecycle_tests',
    'output_policy_config_tests',
    'output_supervisor_resolver_tests',
]
run(f'cmake -S test/host -B {build}')
run(f"cmake --build {build} --parallel --target {' '.join(targets)}")
regex = '^(' + '|'.join(targets) + ')$'
run(f"ctest --test-dir {build} -R '{regex}' --output-on-failure")
print('A8_2_FOCUSED_PASS', flush=True)

run('git diff --check')
run('git add ' + ' '.join(FILES))
run('git diff --cached --check')
run("git commit -m 'Add output supervisor lifecycle state machine'")
new = out('git rev-parse HEAD')
run('git push origin HEAD:mvp/environment-controller')
assert not out('git status --porcelain')
print(f'A8_2_PASS commit={new}', flush=True)
