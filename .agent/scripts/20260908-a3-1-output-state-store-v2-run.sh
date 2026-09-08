#!/usr/bin/env bash
set -euo pipefail

python3 /tmp/a3_1_edit.py
python3 - <<'PY'
from pathlib import Path
p = Path('test/host/CMakeLists.txt')
s = p.read_text().rstrip('\n') + '\n'
p.write_text(s)
PY

git add -N \
  src/CMakeLists.txt \
  src/climate/output/OutputStateStore.h \
  src/climate/output/OutputStateStore.cpp \
  test/host/CMakeLists.txt \
  test/test_output_state_store/test_main.cpp

git diff --check

python3 - <<'PY'
from pathlib import Path
h = Path('src/climate/output/OutputStateStore.h').read_text()
c = Path('src/climate/output/OutputStateStore.cpp').read_text()
assert 'PhysicalOutputState::Unknown' in h
assert 'has_independent_feedback' in h
assert 'has_successful_command' in h
assert 'recordDesired' in h and 'recordResolved' in h and 'recordAttempt' in h
attempt = c[c.index('bool OutputStateStore::recordAttempt'):c.index('bool OutputStateStore::recordPhysicalObservation')]
assert 'physical' not in attempt
assert 'TransportStatus::Completed' in attempt
print('A3_1_V2_STATIC_PASS')
PY

cmake -S test/host -B build/host-tests-a3-1-v2
cmake --build build/host-tests-a3-1-v2 --parallel --target \
  output_state_store_tests output_execution_contract_tests
ctest --test-dir build/host-tests-a3-1-v2 \
  -R '^(output_state_store_tests|output_execution_contract_tests)$' --output-on-failure
echo A3_1_V2_FOCUSED_PASS

actual=$(git diff --name-only | sort)
expected=$(printf '%s\n' \
  src/CMakeLists.txt \
  src/climate/output/OutputStateStore.cpp \
  src/climate/output/OutputStateStore.h \
  test/host/CMakeLists.txt \
  test/test_output_state_store/test_main.cpp | sort)
test "$actual" = "$expected"
git diff --check

git add \
  src/CMakeLists.txt \
  src/climate/output/OutputStateStore.cpp \
  src/climate/output/OutputStateStore.h \
  test/host/CMakeLists.txt \
  test/test_output_state_store/test_main.cpp
git diff --cached --check
git commit -m 'Add honest output command state store'
NEW=$(git rev-parse HEAD)
git push origin HEAD:mvp/environment-controller
test -z "$(git status --porcelain)"
echo A3_1_V2_PASS commit=$NEW
