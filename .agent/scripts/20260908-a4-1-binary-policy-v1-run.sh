#!/usr/bin/env bash
set -euo pipefail

EXPECTED=feb5104eb8d9a2d4aefff7503bb0c19b20b8a01e
test "$(git rev-parse HEAD)" = "$EXPECTED"
test "$(git rev-parse origin/mvp/environment-controller)" = "$EXPECTED"
test -z "$(git status --porcelain)"

python3 /tmp/a4_1_edit.py

git add -N \
  src/CMakeLists.txt \
  src/climate/output/BinaryActuatorPolicy.cpp \
  src/climate/output/BinaryActuatorPolicy.h \
  test/host/CMakeLists.txt \
  test/test_binary_actuator_policy/test_main.cpp

git diff --check

! grep -q 'ClimateRoleDriver' src/climate/output/BinaryActuatorPolicy.h src/climate/output/BinaryActuatorPolicy.cpp
! grep -q 'OutputTransport' src/climate/output/BinaryActuatorPolicy.h src/climate/output/BinaryActuatorPolicy.cpp
grep -q 'BinaryActuatorProposal propose' src/climate/output/BinaryActuatorPolicy.h
grep -q 'bool commit' src/climate/output/BinaryActuatorPolicy.h
grep -q 'proposal.generation != generation_' src/climate/output/BinaryActuatorPolicy.cpp
grep -q 'if (!command_completed)' src/climate/output/BinaryActuatorPolicy.cpp
echo A4_1_STATIC_PASS

cmake -S test/host -B build/host-tests-a4-1-v1
cmake --build build/host-tests-a4-1-v1 --parallel --target \
  binary_actuator_policy_tests stage28d_binary_role_arbiter_tests
ctest --test-dir build/host-tests-a4-1-v1 \
  -R '^(binary_actuator_policy_tests|stage28d_binary_role_arbiter_tests)$' --output-on-failure
echo A4_1_FOCUSED_PASS

actual=$(git diff --name-only | sort)
expected=$(printf '%s\n' \
  src/CMakeLists.txt \
  src/climate/output/BinaryActuatorPolicy.cpp \
  src/climate/output/BinaryActuatorPolicy.h \
  test/host/CMakeLists.txt \
  test/test_binary_actuator_policy/test_main.cpp | sort)
test "$actual" = "$expected"
git diff --check

git add \
  src/CMakeLists.txt \
  src/climate/output/BinaryActuatorPolicy.cpp \
  src/climate/output/BinaryActuatorPolicy.h \
  test/host/CMakeLists.txt \
  test/test_binary_actuator_policy/test_main.cpp
git diff --cached --check
git commit -m 'Extract transport-free binary actuator policy'
NEW=$(git rev-parse HEAD)
git push origin HEAD:mvp/environment-controller
test -z "$(git status --porcelain)"
echo A4_1_PASS commit=$NEW
