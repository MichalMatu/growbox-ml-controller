#!/usr/bin/env bash
set -euo pipefail

EXPECTED=bf37191e76a1bb2242338cc11599d3ee047087a9
test "$(git rev-parse HEAD)" = "$EXPECTED"
test "$(git rev-parse origin/mvp/environment-controller)" = "$EXPECTED"
test -z "$(git status --porcelain)"

git fetch -q origin agent-control
git show FETCH_HEAD:.agent/scripts/20260908-a5-2-lamp-safety-envelope-v1.py > /tmp/a5_2_edit.py
git show FETCH_HEAD:.agent/scripts/20260908-a5-2-lamp-safety-envelope-v1-fix.py > /tmp/a5_2_fix.py
python3 /tmp/a5_2_edit.py
python3 /tmp/a5_2_fix.py

git diff --check
actual=$(git diff --name-only | sort)
expected=$(printf '%s\n' \
  src/climate/Stage28dLampSafety.cpp \
  src/climate/Stage28dLampSafety.h \
  test/test_stage28d_lamp_safety/test_main.cpp | sort)
test "$actual" = "$expected"
grep -q 'buildLampSafetyEnvelope' src/climate/Stage28dLampSafety.cpp
grep -q 'SafetyConstraint::ForceOff' src/climate/Stage28dLampSafety.cpp
grep -q 'SafetyConstraint::ForceOn' src/climate/Stage28dLampSafety.cpp
grep -q 'recovery_running' src/climate/Stage28dLampSafety.h
! grep -Eq 'Rf433|OutputTransport|manualTransmit|rmt_transmit' src/climate/Stage28dLampSafety.cpp src/climate/Stage28dLampSafety.h
! git diff --name-only | grep -q '^src/climate/ClimateV6RealInputRuntime.cpp$'
echo A5_2_STATIC_PASS

cmake -S test/host -B build/host-tests-a5-2-v1
cmake --build build/host-tests-a5-2-v1 --parallel --target \
  stage28d_lamp_safety_tests output_intents_tests
ctest --test-dir build/host-tests-a5-2-v1 \
  -R '^(stage28d_lamp_safety_tests|output_intents_tests)$' \
  --output-on-failure
echo A5_2_FOCUSED_PASS

STAGE27C_BUILD_DIR=build/idf-a5-2-v1 \
STAGE27C_SDKCONFIG=build/idf-a5-2-v1/sdkconfig \
GROWBOX_RF433_LOOPBACK_ENABLED=1 \
GROWBOX_STAGE28_REAL_OUTPUTS_ENABLED=1 \
GROWBOX_RF433_LOOPBACK_AUTO_SMOKE=0 \
GROWBOX_RF433_REMOTE_CAPTURE_ENABLED=0 \
bash scripts/stage27c_crowpanel.sh build
echo A5_2_CANONICAL_RF_BUILD_PASS

git diff --check
git add \
  src/climate/Stage28dLampSafety.cpp \
  src/climate/Stage28dLampSafety.h \
  test/test_stage28d_lamp_safety/test_main.cpp
git diff --cached --check
git commit -m 'Expose lamp thermal safety as safety envelope'
NEW=$(git rev-parse HEAD)
git push origin HEAD:mvp/environment-controller
test -z "$(git status --porcelain)"
echo A5_2_PASS commit=$NEW
