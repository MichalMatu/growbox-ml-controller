#!/usr/bin/env bash
set -euo pipefail

EXPECTED=ae07bcef787b298ddb44d1d7d271c236565b6c47
test "$(git rev-parse HEAD)" = "$EXPECTED"
test "$(git rev-parse origin/mvp/environment-controller)" = "$EXPECTED"
test -z "$(git status --porcelain)"

python3 /tmp/a5_1_edit.py

git add -N \
  src/CMakeLists.txt \
  src/climate/runtime/Stage27RuntimeAdapters.cpp \
  src/climate/runtime/Stage27ScheduleProfile.cpp \
  src/climate/runtime/Stage27ScheduleProfile.h \
  src/climate/runtime/Stage27ScheduleIntentAdapter.cpp \
  src/climate/runtime/Stage27ScheduleIntentAdapter.h \
  test/host/CMakeLists.txt \
  test/test_stage27_schedule_intent/test_main.cpp

git diff --check

grep -q 'resolveMintScheduleProfile(clock, output)' src/climate/runtime/Stage27RuntimeAdapters.cpp
! grep -q 'resolveEuropeWarsawLocalTime' src/climate/runtime/Stage27RuntimeAdapters.cpp
grep -q 'buildStage27ScheduleIntent' src/climate/runtime/Stage27ScheduleIntentAdapter.cpp
grep -q 'OutputSource::Schedule' src/climate/runtime/Stage27ScheduleIntentAdapter.cpp
grep -q 'OutputReason::ScheduleRequest' src/climate/runtime/Stage27ScheduleIntentAdapter.cpp
grep -q 'kScheduledLightEndpoint' src/climate/runtime/Stage27ScheduleIntentAdapter.cpp
! git diff --name-only | grep -q '^src/climate/ClimateV6RealInputRuntime.cpp$'
echo A5_1_STATIC_PASS

cmake -S test/host -B build/host-tests-a5-1-v1
cmake --build build/host-tests-a5-1-v1 --parallel --target \
  stage27_schedule_profile_tests stage27_schedule_intent_tests europe_warsaw_time_tests output_intents_tests
ctest --test-dir build/host-tests-a5-1-v1 \
  -R '^(stage27_schedule_profile_tests|stage27_schedule_intent_tests|europe_warsaw_time_tests|output_intents_tests)$' \
  --output-on-failure
echo A5_1_FOCUSED_PASS

STAGE27C_BUILD_DIR=build/idf-a5-1-v1 \
STAGE27C_SDKCONFIG=build/idf-a5-1-v1/sdkconfig \
GROWBOX_RF433_LOOPBACK_ENABLED=1 \
GROWBOX_STAGE28_REAL_OUTPUTS_ENABLED=1 \
GROWBOX_RF433_LOOPBACK_AUTO_SMOKE=0 \
GROWBOX_RF433_REMOTE_CAPTURE_ENABLED=0 \
bash scripts/stage27c_crowpanel.sh build
echo A5_1_CANONICAL_RF_BUILD_PASS

actual=$(git diff --name-only | sort)
expected=$(printf '%s\n' \
  src/CMakeLists.txt \
  src/climate/runtime/Stage27RuntimeAdapters.cpp \
  src/climate/runtime/Stage27ScheduleIntentAdapter.cpp \
  src/climate/runtime/Stage27ScheduleIntentAdapter.h \
  src/climate/runtime/Stage27ScheduleProfile.cpp \
  src/climate/runtime/Stage27ScheduleProfile.h \
  test/host/CMakeLists.txt \
  test/test_stage27_schedule_intent/test_main.cpp | sort)
test "$actual" = "$expected"
git diff --check

git add \
  src/CMakeLists.txt \
  src/climate/runtime/Stage27RuntimeAdapters.cpp \
  src/climate/runtime/Stage27ScheduleIntentAdapter.cpp \
  src/climate/runtime/Stage27ScheduleIntentAdapter.h \
  src/climate/runtime/Stage27ScheduleProfile.cpp \
  src/climate/runtime/Stage27ScheduleProfile.h \
  test/host/CMakeLists.txt \
  test/test_stage27_schedule_intent/test_main.cpp
git diff --cached --check
git commit -m 'Add scheduled-light output intent'
NEW=$(git rev-parse HEAD)
git push origin HEAD:mvp/environment-controller
test -z "$(git status --porcelain)"
echo A5_1_PASS commit=$NEW
