#!/usr/bin/env bash
set -euo pipefail

EXPECTED=2c1d4a701e46240f722fe7d9dc4d8b741c8fdcd5
test "$(git rev-parse HEAD)" = "$EXPECTED"
test "$(git rev-parse origin/mvp/environment-controller)" = "$EXPECTED"
test -z "$(git status --porcelain)"

python3 /tmp/a3_2_edit.py
git diff --check

python3 - <<'PY'
from pathlib import Path
h = Path('src/climate/Stage28dRfOutputEndpoint.h').read_text()
c = Path('src/climate/Stage28dRfOutputEndpoint.cpp').read_text()
r = Path('src/climate/ClimateV6RealInputRuntime.cpp').read_text()
t = Path('test/test_stage28d_rf_output_endpoint/test_main.cpp').read_text()
assert 'OutputStateStore* shadow_state_store' in h
assert 'recordDesired' in c and 'recordResolved' in c and 'recordAttempt' in c
assert 'recordPhysicalObservation' not in c
assert c.index('recordAttempt(command, monotonic_ms, result)') < c.index('result.status !=')
assert 'OutputStateStore output_state_store' in r
assert 'kShadowOutputEndpoints' in r
assert '&output_state_store' in r
assert 'recordPhysicalObservation' not in r
assert 'desired.state == output::BinaryOutputState::Off' in t
assert 'resolved.state == output::BinaryOutputState::On' in t
assert 'last_transport.status == output::TransportStatus::Failed' in t
assert 'physical.state == output::PhysicalOutputState::Unknown' in t
print('A3_2_STATIC_PASS')
PY

cmake -S test/host -B build/host-tests-a3-2-v1
cmake --build build/host-tests-a3-2-v1 --parallel --target \
  stage28d_rf_output_endpoint_tests output_state_store_tests rf433_output_transport_tests
ctest --test-dir build/host-tests-a3-2-v1 \
  -R '^(stage28d_rf_output_endpoint_tests|output_state_store_tests|rf433_output_transport_tests)$' \
  --output-on-failure
echo A3_2_FOCUSED_PASS

STAGE27C_BUILD_DIR=build/idf-a3-2-v1 \
STAGE27C_SDKCONFIG=build/idf-a3-2-v1/sdkconfig \
GROWBOX_RF433_LOOPBACK_ENABLED=1 \
GROWBOX_STAGE28_REAL_OUTPUTS_ENABLED=1 \
GROWBOX_RF433_LOOPBACK_AUTO_SMOKE=0 \
GROWBOX_RF433_REMOTE_CAPTURE_ENABLED=0 \
bash scripts/stage27c_crowpanel.sh build
echo A3_2_CANONICAL_RF_BUILD_PASS

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
git commit -m 'Mirror legacy output execution into state store'
NEW=$(git rev-parse HEAD)
git push origin HEAD:mvp/environment-controller
test -z "$(git status --porcelain)"
echo A3_2_PASS commit=$NEW
