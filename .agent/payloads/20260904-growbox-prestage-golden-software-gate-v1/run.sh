#!/usr/bin/env bash
set -euo pipefail

EXPECTED=484a7dfa262165fc3e61716cc162a49d61a2ee8a
BRANCH=mvp/environment-controller

git fetch -q origin "$BRANCH"
test "$(git rev-parse HEAD)" = "$EXPECTED"
test "$(git rev-parse origin/$BRANCH)" = "$EXPECTED"
test -z "$(git status --porcelain)"

git diff --check

# Full repository software gate: pre-commit, pytest (non-hardware), host C++ tests,
# clang-tidy and the repository ESP-IDF gate build.
bash scripts/quality_gate.sh

# Re-run the exact CrowPanel real-input build on the current source with RF transport
# initialized but all automatic/passive RF activity disabled. No board access here.
export GROWBOX_FIRMWARE_GIT_SHA="$EXPECTED"
export GROWBOX_RF433_LOOPBACK_ENABLED=1
export GROWBOX_RF433_LOOPBACK_AUTO_SMOKE=0
export GROWBOX_RF433_REMOTE_CAPTURE_ENABLED=0
export STAGE27C_BUILD_DIR=build/idf-prestage-golden-software-gate-v1
scripts/stage27c_crowpanel.sh build 2>&1 | tee /tmp/prestage-golden-crowpanel-build.log

if grep -q "unknown kconfig symbol" /tmp/prestage-golden-crowpanel-build.log; then
  echo "unknown Kconfig warning returned" >&2
  exit 1
fi

git diff --check
test -z "$(git status --porcelain)"
test "$(git rev-parse HEAD)" = "$EXPECTED"
test "$(git rev-parse origin/$BRANCH)" = "$EXPECTED"

printf 'PRESTAGE_GOLDEN_SOFTWARE_GATE_PASS sha=%s outputs=fake-locked rf_auto_tx=0\n' "$EXPECTED"
