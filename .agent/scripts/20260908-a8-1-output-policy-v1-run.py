import subprocess

EXPECTED = 'c8e549aaac4eb94e4be89175b571a4f847b44f56'
FILES = sorted([
    'src/CMakeLists.txt',
    'src/climate/Stage28dOutputBindings.cpp',
    'src/climate/Stage28dOutputBindings.h',
    'src/climate/output/OutputPolicyConfig.cpp',
    'src/climate/output/OutputPolicyConfig.h',
    'test/host/CMakeLists.txt',
    'test/test_output_policy_config/test_main.cpp',
])


def run(cmd: str) -> None:
    print('+', cmd, flush=True)
    subprocess.run(cmd, shell=True, check=True)

run('git fetch -q origin mvp/environment-controller')
assert subprocess.check_output('git rev-parse HEAD', shell=True, text=True).strip() == EXPECTED
assert subprocess.check_output('git rev-parse FETCH_HEAD', shell=True, text=True).strip() == EXPECTED
assert not subprocess.check_output('git status --porcelain', shell=True, text=True).strip()
print('A8_1_IDENTITY_PASS', flush=True)

run('git fetch -q origin agent-control')
run("git show FETCH_HEAD:.agent/scripts/20260908-a8-1-output-policy-v1.py > /tmp/a8_1_edit.py")
run('python3 /tmp/a8_1_edit.py')
run('git add -N src/climate/output/OutputPolicyConfig.cpp src/climate/output/OutputPolicyConfig.h test/test_output_policy_config/test_main.cpp')
run('git diff --check')
changed = sorted(subprocess.check_output('git diff --name-only', shell=True, text=True).strip().splitlines())
assert changed == FILES, changed
assert 'OutputPolicyConfig' in open('src/climate/Stage28dOutputBindings.cpp').read()
assert 'ClimateV6RealInputRuntime.cpp' not in changed
print('A8_1_STATIC_PASS', flush=True)

build = 'build/host-tests-a8-1-v1'
targets = ['output_policy_config_tests', 'climate_semantic_output_tests']
run(f'cmake -S test/host -B {build}')
run(f"cmake --build {build} --parallel --target {' '.join(targets)}")
regex = '^(' + '|'.join(targets) + ')$'
run(f"ctest --test-dir {build} -R '{regex}' --output-on-failure")
print('A8_1_FOCUSED_PASS', flush=True)

run('git diff --check')
run('git add ' + ' '.join(FILES))
run('git diff --cached --check')
run("git commit -m 'Add validated output lifecycle policy'")
new = subprocess.check_output('git rev-parse HEAD', shell=True, text=True).strip()
run('git push origin HEAD:mvp/environment-controller')
assert not subprocess.check_output('git status --porcelain', shell=True, text=True).strip()
print(f'A8_1_PASS commit={new}', flush=True)
