#!/usr/bin/env bash
set -euo pipefail

EXPECTED=92ac5b5f4477da9bcc1fafeb824954b8e15b41d2
test "$(git rev-parse HEAD)" = "$EXPECTED"
test "$(git rev-parse origin/mvp/environment-controller)" = "$EXPECTED"
test -z "$(git status --porcelain)"

python3 /tmp/a4_2_edit.py
git diff --check

grep -q 'BinaryActuatorPolicy& policy' src/climate/Stage28dBinaryRoleArbiter.h
grep -q 'policy.propose' src/climate/Stage28dBinaryRoleArbiter.cpp
grep -q 'policy.commit(proposal, false)' src/climate/Stage28dBinaryRoleArbiter.cpp
grep -q 'policy.commit(proposal, true)' src/climate/Stage28dBinaryRoleArbiter.cpp
! grep -q 'elapsed_ms' src/climate/Stage28dBinaryRoleArbiter.cpp
! grep -q 'request >= config.on_threshold' src/climate/Stage28dBinaryRoleArbiter.cpp
echo A4_2_STATIC_PASS

cmake -S test/host -B build/host-tests-a4-2-v1
cmake --build build/host-tests-a4-2-v1 --parallel --target \
  stage28d_binary_role_arbiter_tests binary_actuator_policy_tests
ctest --test-dir build/host-tests-a4-2-v1 \
  -R '^(stage28d_binary_role_arbiter_tests|binary_actuator_policy_tests)$' --output-on-failure
echo A4_2_FOCUSED_PASS

STAGE27C_BUILD_DIR=build/idf-a4-2-v1 \
STAGE27C_SDKCONFIG=build/idf-a4-2-v1/sdkconfig \
GROWBOX_RF433_LOOPBACK_ENABLED=1 \
GROWBOX_STAGE28_REAL_OUTPUTS_ENABLED=1 \
GROWBOX_RF433_LOOPBACK_AUTO_SMOKE=0 \
GROWBOX_RF433_REMOTE_CAPTURE_ENABLED=0 \
bash scripts/stage27c_crowpanel.sh build
echo A4_2_CANONICAL_RF_BUILD_PASS

actual=$(git diff --name-only | sort)
expected=$(printf '%s\n' \
  src/climate/Stage28dBinaryRoleArbiter.cpp \
  src/climate/Stage28dBinaryRoleArbiter.h \
  test/host/CMakeLists.txt | sort)
test "$actual" = "$expected"
git diff --check

git add \
  src/climate/Stage28dBinaryRoleArbiter.cpp \
  src/climate/Stage28dBinaryRoleArbiter.h \
  test/host/CMakeLists.txt
git diff --cached --check
git commit -m 'Delegate legacy binary arbiter to policy'
NEW=$(git rev-parse HEAD)
git push origin HEAD:mvp/environment-controller
test -z "$(git status --porcelain)"
echo A4_2_PASS commit=$NEW
