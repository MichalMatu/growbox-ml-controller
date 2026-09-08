#!/usr/bin/env bash
set -euo pipefail

EXPECTED=06bec4f1811957dcc773fc2a457e2c457906db58
test "$(git rev-parse HEAD)" = "$EXPECTED"
test "$(git rev-parse origin/mvp/environment-controller)" = "$EXPECTED"
test -z "$(git status --porcelain)"

git show FETCH_HEAD:.agent/scripts/20260908-a6-1-supervisor-resolver-v1.py > /tmp/a6_1_edit.py
python3 /tmp/a6_1_edit.py

git add -N \
  src/CMakeLists.txt \
  src/climate/output/OutputSupervisorResolver.cpp \
  src/climate/output/OutputSupervisorResolver.h \
  test/host/CMakeLists.txt \
  test/test_output_supervisor_resolver/test_main.cpp

git diff --check

grep -q 'class OutputSupervisorResolver' src/climate/output/OutputSupervisorResolver.h
grep -q 'ManualIntent' src/climate/output/OutputSupervisorResolver.h
grep -q 'SafetyEnvelope' src/climate/output/OutputSupervisorResolver.h
grep -q 'binary_policy->propose' src/climate/output/OutputSupervisorResolver.cpp
! grep -q 'commit(' src/climate/output/OutputSupervisorResolver.cpp
! grep -q 'OutputTransport' src/climate/output/OutputSupervisorResolver.h
! grep -q 'OutputTransport' src/climate/output/OutputSupervisorResolver.cpp
! git diff --name-only | grep -q '^src/climate/ClimateV6RealInputRuntime.cpp$'
! git diff --name-only | grep -q '^src/climate/rf433/'
echo A6_1_STATIC_PASS

cmake -S test/host -B build/host-tests-a6-1-v1
cmake --build build/host-tests-a6-1-v1 --parallel --target \
  output_supervisor_resolver_tests output_intents_tests
ctest --test-dir build/host-tests-a6-1-v1 \
  -R '^(output_supervisor_resolver_tests|output_intents_tests)$' \
  --output-on-failure
echo A6_1_FOCUSED_PASS

actual=$(git diff --name-only | sort)
expected=$(printf '%s\n' \
  src/CMakeLists.txt \
  src/climate/output/OutputSupervisorResolver.cpp \
  src/climate/output/OutputSupervisorResolver.h \
  test/host/CMakeLists.txt \
  test/test_output_supervisor_resolver/test_main.cpp | sort)
test "$actual" = "$expected"
git diff --check

git add \
  src/CMakeLists.txt \
  src/climate/output/OutputSupervisorResolver.cpp \
  src/climate/output/OutputSupervisorResolver.h \
  test/host/CMakeLists.txt \
  test/test_output_supervisor_resolver/test_main.cpp
git diff --cached --check
git commit -m 'Add output supervisor resolver'
NEW=$(git rev-parse HEAD)
git push origin HEAD:mvp/environment-controller
test -z "$(git status --porcelain)"
echo A6_1_PASS commit=$NEW
