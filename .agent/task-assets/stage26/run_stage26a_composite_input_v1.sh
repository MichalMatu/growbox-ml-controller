#!/usr/bin/env bash
set -euo pipefail

MODE="${1:?mode required}"
EXPECTED="${2:-}"
ASSET='.agent/task-assets/stage26/apply_stage26a_composite_input_v1.py'

case "$MODE" in
  apply)
    test -n "$EXPECTED"
    git fetch origin mvp/environment-controller agent-control
    git reset --hard origin/mvp/environment-controller
    git clean -fd
    test "$(git rev-parse HEAD)" = "$EXPECTED"
    test -z "$(git status --porcelain)"

    git show "origin/agent-control:$ASSET" > /tmp/stage26a-apply.py
    .venv/bin/python /tmp/stage26a-apply.py

    .venv/bin/pre-commit run clang-format --files \
      src/climate/ClimateCompositeInput.h \
      src/climate/ClimateCompositeInput.cpp \
      test/test_climate_composite_input/test_main.cpp || true
    .venv/bin/pre-commit run clang-format --files \
      src/climate/ClimateCompositeInput.h \
      src/climate/ClimateCompositeInput.cpp \
      test/test_climate_composite_input/test_main.cpp

    git diff --check
    test -z "$(git diff --name-only "$EXPECTED" -- \
      lib/environment_control \
      src/main.cpp \
      src/climate/ClimateApplication.cpp \
      src/climate/ClimateApplication.h \
      src/climate/ClimateIoAdapters.cpp \
      src/climate/ClimateIoAdapters.h \
      src/climate/ClimateV6FakeRuntime.cpp)"
    ! grep -E -i '#include .*driver|gpio_|i2c_|nimble|ble_|scd4|ds3231|pcf8563|shelly|mqtt|modbus' \
      src/climate/ClimateCompositeInput.h src/climate/ClimateCompositeInput.cpp
    grep -F 'class CompositeClimateSnapshotProvider final' src/climate/ClimateCompositeInput.h
    grep -F 'climate_composite_input_tests' test/host/CMakeLists.txt
    grep -F 'Stage26A completed — hardware-ready composite input layer' docs/CONTINUATION_PLAN.md
    git status --short
    ;;

  focused)
    cmake -S test/host -B build/host-tests
    cmake --build build/host-tests --target climate_composite_input_tests --parallel
    ctest --test-dir build/host-tests -R '^climate_composite_input_tests$' --output-on-failure
    .venv/bin/pre-commit run --files \
      src/climate/ClimateCompositeInput.h \
      src/climate/ClimateCompositeInput.cpp \
      src/CMakeLists.txt \
      test/test_climate_composite_input/test_main.cpp \
      test/host/CMakeLists.txt \
      scripts/run_clang_tidy_host.sh \
      docs/CURRENT_STATUS.md \
      docs/CONTINUATION_PLAN.md
    grep -F 'Stage26A adds a hardware-neutral composite input layer' docs/CURRENT_STATUS.md
    grep -F '### Stage26A completed — hardware-ready composite input layer' docs/CONTINUATION_PLAN.md
    git diff --check
    ;;

  full)
    test -n "$EXPECTED"
    git add -A
    .venv/bin/pre-commit run --all-files
    .venv/bin/python -m pytest -q -m 'not hardware'
    bash scripts/check_schema.sh
    cmake -S test/host -B build/host-tests
    cmake --build build/host-tests --parallel
    ctest --test-dir build/host-tests --output-on-failure
    bash scripts/run_clang_tidy_host.sh

    unset VIRTUAL_ENV CONDA_PREFIX PYTHONHOME || true
    export PATH='/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin'
    if [ ! -x "$HOME/.espressif/python_env/idf5.5_py3.14_env/bin/python" ]; then
      env -u VIRTUAL_ENV -u CONDA_PREFIX -u PYTHONHOME PATH='/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin' \
        bash "$HOME/esp/esp-idf/install.sh" esp32s3
    fi
    source "$HOME/esp/esp-idf/export.sh"
    idf.py --version | grep -F 'ESP-IDF v5.5.4'
    test "$(git -C "$HOME/esp/esp-idf" describe --tags --exact-match HEAD)" = 'v5.5.4'

    rm -rf build/idf-gate-stage26a-legacy build/idf-gate-stage26a-fake
    IDF_GATE_BUILD_DIR=build/idf-gate-stage26a-legacy \
      IDF_GATE_APP_MODE=legacy bash scripts/idf_gate_build.sh
    IDF_GATE_BUILD_DIR=build/idf-gate-stage26a-fake \
      IDF_GATE_APP_MODE=climate-v6-fake bash scripts/idf_gate_build.sh

    git diff --check
    test -z "$(git diff --name-only "$EXPECTED" -- \
      lib/environment_control \
      src/main.cpp \
      src/climate/ClimateApplication.cpp \
      src/climate/ClimateApplication.h \
      src/climate/ClimateIoAdapters.cpp \
      src/climate/ClimateIoAdapters.h \
      src/climate/ClimateV6FakeRuntime.cpp)"
    git add -A
    git diff --cached --check
    git commit -m 'Add hardware-neutral composite climate input layer'
    git push origin HEAD:mvp/environment-controller
    test -z "$(git status --porcelain)"
    printf 'PUBLISHED_HEAD=%s\n' "$(git rev-parse HEAD)"
    ;;

  *)
    echo "Unknown mode: $MODE" >&2
    exit 2
    ;;
esac
