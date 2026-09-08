#!/usr/bin/env bash
set -euo pipefail

EXPECTED=b41a26a1ae1380da5d3e08438a275e79a1dd9fa6
test "$(git rev-parse HEAD)" = "$EXPECTED"
test "$(git rev-parse origin/mvp/environment-controller)" = "$EXPECTED"
test -z "$(git status --porcelain)"

git fetch -q origin agent-control
git show FETCH_HEAD:.agent/scripts/20260908-a5-3-intent-parity-v1.py > /tmp/a5_3_edit.py
python3 /tmp/a5_3_edit.py

git add -N test/host/CMakeLists.txt test/test_stage28d_output_intent_parity/test_main.cpp
git diff --check
actual=$(git diff --name-only | sort)
expected=$(printf '%s\n' test/host/CMakeLists.txt test/test_stage28d_output_intent_parity/test_main.cpp | sort)
test "$actual" = "$expected"
! git diff --name-only | grep -q '^src/'
echo A5_3_STATIC_PASS

cmake -S test/host -B build/host-tests-a5-3-v1
cmake --build build/host-tests-a5-3-v1 --parallel --target \
  stage28d_output_intent_parity_tests stage27_schedule_intent_tests stage28d_lamp_safety_tests
ctest --test-dir build/host-tests-a5-3-v1 \
  -R '^(stage28d_output_intent_parity_tests|stage27_schedule_intent_tests|stage28d_lamp_safety_tests)$' \
  --output-on-failure
echo A5_3_FOCUSED_PASS

git add test/host/CMakeLists.txt test/test_stage28d_output_intent_parity/test_main.cpp
git diff --cached --check
git commit -m 'Verify schedule and safety intent parity'
NEW=$(git rev-parse HEAD)
git push origin HEAD:mvp/environment-controller
test -z "$(git status --porcelain)"
echo A5_3_PASS commit=$NEW
