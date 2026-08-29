#!/usr/bin/env bash
set -euo pipefail

MODE="${1:?mode required}"
EXPECTED="${2:-}"
V1='.agent/task-assets/stage25/run_stage25b_runtime_boundary_v1.sh'

load_v1() {
  git fetch origin agent-control
  git show "origin/agent-control:${V1}" > /tmp/stage25b-v1.sh
  chmod +x /tmp/stage25b-v1.sh
}

case "$MODE" in
  apply)
    test -n "$EXPECTED"
    load_v1

    set +e
    bash /tmp/stage25b-v1.sh apply "$EXPECTED"
    rc=$?
    set -e

    # v1 is expected to stop when clang-format modifies newly generated sources.
    test "$rc" -eq 1
    test "$(git rev-parse HEAD)" = "$EXPECTED"
    test -f src/climate/ClimateV6FakeRuntime.h
    test -f src/climate/ClimateV6FakeRuntime.cpp
    grep -F 'GROWBOX_APP_CLIMATE_V6_FAKE' src/main.cpp >/dev/null
    grep -F 'set(GROWBOX_APP_MODE "legacy" CACHE STRING' src/CMakeLists.txt >/dev/null
    grep -F 'IDF_GATE_APP_MODE' scripts/idf_gate_build.sh >/dev/null

    # Formatting is an editing operation here; validate it only after applying fixes.
    .venv/bin/pre-commit run clang-format --files \
      src/main.cpp \
      src/climate/ClimateV6FakeRuntime.h \
      src/climate/ClimateV6FakeRuntime.cpp

    git diff --check
    ! grep -E -i 'gpio_set|gpio_config|i2c_|scd4|nimble|ble_|ds3231|pcf8563|shelly|mqtt|modbus' \
      src/climate/ClimateV6FakeRuntime.cpp src/climate/ClimateV6FakeRuntime.h
    git status --short
    ;;

  focused)
    load_v1
    bash /tmp/stage25b-v1.sh focused
    ;;

  full)
    test -n "$EXPECTED"
    load_v1
    bash /tmp/stage25b-v1.sh full "$EXPECTED"
    ;;

  *)
    echo "Unknown mode: $MODE" >&2
    exit 2
    ;;
esac
