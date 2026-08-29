#!/usr/bin/env bash
set -euo pipefail

MODE="${1:?mode required}"
EXPECTED="${2:-}"
APPLY_ASSET='.agent/task-assets/stage26/apply_stage26c_pre_hardware_readiness_v1.py'

assert_docs_only_diff() {
  test -z "$(git status --porcelain -- src lib test)"
}

case "$MODE" in
  apply)
    test -n "$EXPECTED"
    git fetch origin mvp/environment-controller agent-control
    git reset --hard origin/mvp/environment-controller
    git clean -fd
    test "$(git rev-parse HEAD)" = "$EXPECTED"
    test -z "$(git status --porcelain)"

    git show "origin/agent-control:$APPLY_ASSET" > /tmp/stage26c-apply.py
    .venv/bin/python /tmp/stage26c-apply.py
    chmod +x scripts/check_pre_hardware_readiness.sh

    bash scripts/check_pre_hardware_readiness.sh
    .venv/bin/pre-commit run --files \
      scripts/check_pre_hardware_readiness.sh \
      docs/HARDWARE_BRINGUP_CHECKLIST.md \
      docs/CURRENT_STATUS.md \
      docs/CONTINUATION_PLAN.md
    git diff --check
    assert_docs_only_diff
    grep -F '### Stage26C completed — pre-hardware readiness gate' docs/CONTINUATION_PLAN.md
    grep -F 'Stage26C closes the software-only pre-hardware gate.' docs/CURRENT_STATUS.md
    grep -F 'outside BLE sensor/model: UNRESOLVED' docs/HARDWARE_BRINGUP_CHECKLIST.md
    git status --short
    ;;

  focused)
    test -n "$EXPECTED"
    test "$(git rev-parse HEAD)" = "$EXPECTED"
    bash scripts/check_pre_hardware_readiness.sh

    cmake -S test/host -B build/host-tests
    cmake --build build/host-tests --parallel --target \
      climate_control_loop_tests \
      climate_application_composition_tests \
      climate_deterministic_fake_runtime_tests \
      climate_diagnostics_tests \
      climate_fault_soak_tests \
      climate_composite_input_tests \
      climate_semantic_output_tests
    ctest --test-dir build/host-tests \
      -R '^(climate_control_loop_tests|climate_application_composition_tests|climate_deterministic_fake_runtime_tests|climate_diagnostics_tests|climate_fault_soak_tests|climate_composite_input_tests|climate_semantic_output_tests)$' \
      --output-on-failure

    .venv/bin/pre-commit run --files \
      scripts/check_pre_hardware_readiness.sh \
      docs/HARDWARE_BRINGUP_CHECKLIST.md \
      docs/CURRENT_STATUS.md \
      docs/CONTINUATION_PLAN.md
    git diff --check
    assert_docs_only_diff
    ;;

  full)
    test -n "$EXPECTED"
    test "$(git rev-parse HEAD)" = "$EXPECTED"

    git add -A
    .venv/bin/pre-commit run --all-files
    git diff --cached --check
    test -z "$(git diff --cached --name-only -- src lib test)"

    actual_files="$(git diff --cached --name-only | LC_ALL=C sort)"
    expected_files="$(printf '%s\n' \
      docs/CONTINUATION_PLAN.md \
      docs/CURRENT_STATUS.md \
      docs/HARDWARE_BRINGUP_CHECKLIST.md \
      scripts/check_pre_hardware_readiness.sh | LC_ALL=C sort)"
    test "$actual_files" = "$expected_files"

    bash scripts/check_pre_hardware_readiness.sh
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

    rm -rf build/idf-gate-stage26c-legacy build/idf-gate-stage26c-fake
    IDF_GATE_BUILD_DIR=build/idf-gate-stage26c-legacy \
      IDF_GATE_APP_MODE=legacy bash scripts/idf_gate_build.sh
    IDF_GATE_BUILD_DIR=build/idf-gate-stage26c-fake \
      IDF_GATE_APP_MODE=climate-v6-fake bash scripts/idf_gate_build.sh

    bash scripts/check_pre_hardware_readiness.sh
    git diff --cached --check
    test -z "$(git diff --cached --name-only -- src lib test)"

    git fetch origin mvp/environment-controller
    test "$(git rev-parse origin/mvp/environment-controller)" = "$EXPECTED"
    test "$(git rev-parse HEAD)" = "$EXPECTED"

    git commit -m 'Add pre-hardware readiness gate'
    git push origin HEAD:mvp/environment-controller
    test -z "$(git status --porcelain)"
    printf 'PUBLISHED_HEAD=%s\n' "$(git rev-parse HEAD)"
    ;;

  *)
    echo "Unknown mode: $MODE" >&2
    exit 2
    ;;
esac
