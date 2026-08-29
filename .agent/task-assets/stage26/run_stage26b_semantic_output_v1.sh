#!/usr/bin/env bash
set -euo pipefail

MODE="${1:?mode required}"
EXPECTED="${2:-}"
ASSET='.agent/task-assets/stage26/apply_stage26b_semantic_output_v1.py'

assert_scope() {
  local unexpected
  unexpected="$(git diff --name-only "$EXPECTED" | grep -Ev '^(src/climate/ClimateSemanticOutput\.(h|cpp)|src/CMakeLists\.txt|test/host/CMakeLists\.txt|test/test_climate_semantic_output/test_main\.cpp|scripts/run_clang_tidy_host\.sh|docs/CONTINUATION_PLAN\.md|docs/CURRENT_STATUS\.md)$' || true)"
  if [[ -n "$unexpected" ]]; then
    echo "Unexpected Stage26B paths:" >&2
    echo "$unexpected" >&2
    exit 1
  fi
}

case "$MODE" in
  apply)
    test -n "$EXPECTED"
    git fetch origin mvp/environment-controller agent-control
    git reset --hard origin/mvp/environment-controller
    git clean -fd
    test "$(git rev-parse HEAD)" = "$EXPECTED"
    test -z "$(git status --porcelain)"

    git show "origin/agent-control:$ASSET" > /tmp/stage26b-apply.py
    .venv/bin/python /tmp/stage26b-apply.py

    .venv/bin/pre-commit run clang-format --files \
      src/climate/ClimateSemanticOutput.h \
      src/climate/ClimateSemanticOutput.cpp \
      test/test_climate_semantic_output/test_main.cpp || true
    .venv/bin/pre-commit run clang-format --files \
      src/climate/ClimateSemanticOutput.h \
      src/climate/ClimateSemanticOutput.cpp \
      test/test_climate_semantic_output/test_main.cpp

    git diff --check
    assert_scope
    test -z "$(git diff --name-only "$EXPECTED" -- src/main.cpp src/climate/ClimateIoAdapters.h src/climate/ClimateIoAdapters.cpp src/climate/ClimateApplication.cpp lib/environment_control)"
    ! grep -E -i '\b(gpio|pwm|relay|shelly|modbus|i2c|ble|scd41)\b' \
      src/climate/ClimateSemanticOutput.h src/climate/ClimateSemanticOutput.cpp
    grep -F 'class MappedClimateRoleDriver final : public ClimateRoleDriver' src/climate/ClimateSemanticOutput.h
    grep -F 'class ClimateOutputEndpoint' src/climate/ClimateSemanticOutput.h
    grep -F '### Stage26B completed — hardware-ready semantic output layer' docs/CONTINUATION_PLAN.md
    git status --short
    ;;

  focused)
    test -n "$EXPECTED"
    cmake -S test/host -B build/host-tests
    cmake --build build/host-tests --target climate_semantic_output_tests --parallel
    ctest --test-dir build/host-tests -R '^climate_semantic_output_tests$' --output-on-failure
    .venv/bin/pre-commit run --files \
      src/climate/ClimateSemanticOutput.h \
      src/climate/ClimateSemanticOutput.cpp \
      test/test_climate_semantic_output/test_main.cpp \
      src/CMakeLists.txt \
      test/host/CMakeLists.txt \
      scripts/run_clang_tidy_host.sh \
      docs/CURRENT_STATUS.md \
      docs/CONTINUATION_PLAN.md
    git diff --check
    assert_scope
    test -z "$(git diff --name-only "$EXPECTED" -- src/main.cpp src/climate/ClimateIoAdapters.h src/climate/ClimateIoAdapters.cpp src/climate/ClimateApplication.cpp lib/environment_control)"
    ;;

  full)
    test -n "$EXPECTED"
    test "$(git rev-parse HEAD)" = "$EXPECTED"
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

    rm -rf build/idf-gate-stage26b-legacy build/idf-gate-stage26b-fake
    IDF_GATE_BUILD_DIR=build/idf-gate-stage26b-legacy \
      IDF_GATE_APP_MODE=legacy bash scripts/idf_gate_build.sh
    IDF_GATE_BUILD_DIR=build/idf-gate-stage26b-fake \
      IDF_GATE_APP_MODE=climate-v6-fake bash scripts/idf_gate_build.sh

    git diff --check
    assert_scope
    test -z "$(git diff --name-only "$EXPECTED" -- src/main.cpp src/climate/ClimateIoAdapters.h src/climate/ClimateIoAdapters.cpp src/climate/ClimateApplication.cpp lib/environment_control)"
    git fetch origin mvp/environment-controller
    test "$(git rev-parse origin/mvp/environment-controller)" = "$EXPECTED"

    git add -A
    git diff --cached --check
    git commit -m 'Add hardware-neutral semantic climate output mapping'
    git push origin HEAD:mvp/environment-controller
    test -z "$(git status --porcelain)"
    printf 'PUBLISHED_HEAD=%s\n' "$(git rev-parse HEAD)"
    ;;

  *)
    echo "Unknown mode: $MODE" >&2
    exit 2
    ;;
esac
