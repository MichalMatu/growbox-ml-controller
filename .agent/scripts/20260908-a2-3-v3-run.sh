#!/usr/bin/env bash
set -euo pipefail

EXPECTED=e3b57528fd13a83a5408ba8df2bbe54be87a8394
test "$(git rev-parse HEAD)" = "$EXPECTED"
test "$(git rev-parse origin/mvp/environment-controller)" = "$EXPECTED"
test -z "$(git status --porcelain)"

python3 /tmp/a2_3_v3.py
git diff --check

grep -q 'OutputTransport& transport_' src/climate/Stage28dRfOutputEndpoint.h
grep -q 'transport_.send(command)' src/climate/Stage28dRfOutputEndpoint.cpp
! grep -q 'RfCommandTransmitter' src/climate/Stage28dRfOutputEndpoint.h
! grep -q 'findClimateRf433Endpoint' src/climate/Stage28dRfOutputEndpoint.cpp
! grep -q 'DiagnosticsRfTransmitter' src/climate/ClimateV6RealInputRuntime.cpp
! grep -q 'manualTransmit' src/climate/ClimateV6RealInputRuntime.cpp
grep -q 'Rf433RmtFrameSender rf_frame_sender' src/climate/ClimateV6RealInputRuntime.cpp
grep -q 'Rf433OutputTransport rf_output_transport' src/climate/ClimateV6RealInputRuntime.cpp
echo A2_3_V3_R1_STATIC_PASS

cmake -S test/host -B build/host-tests-a2-3-v3
cmake --build build/host-tests-a2-3-v3 --parallel --target stage28d_rf_output_endpoint_tests rf433_output_transport_tests
ctest --test-dir build/host-tests-a2-3-v3 -R '^(stage28d_rf_output_endpoint_tests|rf433_output_transport_tests)$' --output-on-failure
echo A2_3_V3_FOCUSED_PASS

STAGE27C_BUILD_DIR=build/idf-a2-3-v3 \
STAGE27C_SDKCONFIG=build/idf-a2-3-v3/sdkconfig \
GROWBOX_RF433_LOOPBACK_ENABLED=1 \
GROWBOX_STAGE28_REAL_OUTPUTS_ENABLED=1 \
GROWBOX_RF433_LOOPBACK_AUTO_SMOKE=0 \
GROWBOX_RF433_REMOTE_CAPTURE_ENABLED=0 \
bash scripts/stage27c_crowpanel.sh build
echo A2_3_V3_CANONICAL_RF_BUILD_PASS

actual=$(git diff --name-only | sort)
expected=$(printf '%s\n' \
  src/climate/ClimateV6RealInputRuntime.cpp \
  src/climate/Stage28dRfOutputEndpoint.cpp \
  src/climate/Stage28dRfOutputEndpoint.h \
  test/host/CMakeLists.txt \
  test/test_stage28d_rf_output_endpoint/test_main.cpp | sort)
test "$actual" = "$expected"
git diff --check

git add \
  src/climate/ClimateV6RealInputRuntime.cpp \
  src/climate/Stage28dRfOutputEndpoint.cpp \
  src/climate/Stage28dRfOutputEndpoint.h \
  test/host/CMakeLists.txt \
  test/test_stage28d_rf_output_endpoint/test_main.cpp
git diff --cached --check
git commit -m 'Route legacy output endpoint through RF433 transport'
NEW=$(git rev-parse HEAD)
git push origin HEAD:mvp/environment-controller
test -z "$(git status --porcelain)"
echo A2_3_V3_PASS commit=$NEW
