#!/usr/bin/env bash
set -euo pipefail

EXPECTED=5e3b595853c23be9d14baf4709320fc433403924
test "$(git rev-parse HEAD)" = "$EXPECTED"
test "$(git rev-parse origin/mvp/environment-controller)" = "$EXPECTED"
test -z "$(git status --porcelain)"

python3 /tmp/a4_3_edit.py
git diff --check

! grep -q 'BinaryState' src/climate/Stage28dBinaryRoleArbiter.h src/climate/Stage28dBinaryRoleArbiter.cpp
! grep -q 'transition_count_' src/climate/Stage28dBinaryRoleArbiter.h src/climate/Stage28dBinaryRoleArbiter.cpp
! grep -q 'dwell_hold_count_' src/climate/Stage28dBinaryRoleArbiter.h src/climate/Stage28dBinaryRoleArbiter.cpp
! grep -q 'syncPolicyCounters' src/climate/Stage28dBinaryRoleArbiter.h src/climate/Stage28dBinaryRoleArbiter.cpp
grep -q 'return exhaust_policy_.on()' src/climate/Stage28dBinaryRoleArbiter.h
grep -q 'return humidifier_policy_.on()' src/climate/Stage28dBinaryRoleArbiter.h
grep -q 'exhaust_policy_.transitionCount() + humidifier_policy_.transitionCount()' src/climate/Stage28dBinaryRoleArbiter.h
grep -q 'exhaust_policy_.dwellHoldCount() + humidifier_policy_.dwellHoldCount()' src/climate/Stage28dBinaryRoleArbiter.h
grep -q 'policy.commit(proposal, false)' src/climate/Stage28dBinaryRoleArbiter.cpp
grep -q 'return policy.commit(proposal, true)' src/climate/Stage28dBinaryRoleArbiter.cpp
echo A4_3_STATIC_PASS

cmake -S test/host -B build/host-tests-a4-3-v1
cmake --build build/host-tests-a4-3-v1 --parallel --target \
  stage28d_binary_role_arbiter_tests binary_actuator_policy_tests
ctest --test-dir build/host-tests-a4-3-v1 \
  -R '^(stage28d_binary_role_arbiter_tests|binary_actuator_policy_tests)$' --output-on-failure
echo A4_3_FOCUSED_PASS

STAGE27C_BUILD_DIR=build/idf-a4-3-v1 \
STAGE27C_SDKCONFIG=build/idf-a4-3-v1/sdkconfig \
GROWBOX_RF433_LOOPBACK_ENABLED=1 \
GROWBOX_STAGE28_REAL_OUTPUTS_ENABLED=1 \
GROWBOX_RF433_LOOPBACK_AUTO_SMOKE=0 \
GROWBOX_RF433_REMOTE_CAPTURE_ENABLED=0 \
bash scripts/stage27c_crowpanel.sh build
echo A4_3_CANONICAL_RF_BUILD_PASS

actual=$(git diff --name-only | sort)
expected=$(printf '%s\n' \
  src/climate/Stage28dBinaryRoleArbiter.cpp \
  src/climate/Stage28dBinaryRoleArbiter.h | sort)
test "$actual" = "$expected"
git diff --check

git add src/climate/Stage28dBinaryRoleArbiter.cpp src/climate/Stage28dBinaryRoleArbiter.h
git diff --cached --check
git commit -m 'Remove duplicate binary arbiter state'
NEW=$(git rev-parse HEAD)
git push origin HEAD:mvp/environment-controller
test -z "$(git status --porcelain)"
echo A4_3_PASS commit=$NEW
