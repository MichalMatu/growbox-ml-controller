#!/usr/bin/env bash
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

PY="${ROOT}/.venv/bin/python"
if [[ ! -x "$PY" ]]; then
  PY="$(command -v python3)"
fi

HOST_BUILD_JOBS="${HOST_BUILD_JOBS:-2}"
if [[ ! "${HOST_BUILD_JOBS}" =~ ^[1-9][0-9]*$ ]]; then
  echo "HOST_BUILD_JOBS must be a positive integer, got: ${HOST_BUILD_JOBS}" >&2
  exit 2
fi
export HOST_BUILD_JOBS

echo "==> output execution ownership"
"$PY" "${ROOT}/scripts/check_output_rf_ownership.py"

echo "==> runtime configuration SSOT"
"$PY" "${ROOT}/scripts/check_runtime_config_ssot.py"

echo "==> runtime composition boundaries"
"$PY" "${ROOT}/scripts/check_runtime_boundaries.py"

echo "==> service console boundaries"
"$PY" "${ROOT}/scripts/check_service_console_boundaries.py"

echo "==> app-mode build boundaries"
"$PY" "${ROOT}/scripts/check_app_mode_boundaries.py"

echo "==> pytest"
# Hardware board E2E needs a matching flashed firmware; exclude from pre-push.
"$PY" -m pytest -q -m "not hardware"

echo "==> host C++ tests (jobs=${HOST_BUILD_JOBS})"
cmake -S test/host -B build/host-tests -DCMAKE_EXPORT_COMPILE_COMMANDS=ON
cmake --build build/host-tests --parallel "${HOST_BUILD_JOBS}"
ctest --test-dir build/host-tests --output-on-failure

echo "==> Stage28D bounded-output regression tests"
HOST_CXX="${CXX:-c++}"
"$HOST_CXX" -std=c++17 -Wall -Wextra -Wpedantic \
  -Isrc -Ilib/environment_control/src \
  test/test_stage28d_rf_output_endpoint/test_main.cpp \
  src/climate/compatibility/stage28d/Stage28dRfOutputEndpoint.cpp \
  src/climate/OutputBindings.cpp \
  src/climate/application/ClimateSemanticOutput.cpp \
  src/climate/output/policy/OutputPolicyConfig.cpp \
  src/climate/output/OutputStateStore.cpp \
  src/climate/rf433/ClimateRf433EndpointRegistry.cpp \
  -o /tmp/stage28d_rf_output_endpoint_tests
/tmp/stage28d_rf_output_endpoint_tests
"$HOST_CXX" -std=c++17 -Wall -Wextra -Wpedantic \
  -Isrc -Ilib/environment_control/src \
  test/test_stage28d_binary_role_arbiter/test_main.cpp \
  src/climate/compatibility/stage28d/Stage28dBinaryRoleArbiter.cpp \
  src/climate/output/policy/BinaryActuatorPolicy.cpp \
  -o /tmp/stage28d_binary_role_arbiter_tests
/tmp/stage28d_binary_role_arbiter_tests

if [[ "${SKIP_CLANG_TIDY:-}" != "1" ]]; then
  bash "${ROOT}/scripts/run_clang_tidy_host.sh"
else
  echo "==> host clang-tidy skipped (SKIP_CLANG_TIDY=1)"
fi

if [[ "${SKIP_IDF_BUILD:-}" != "1" ]]; then
  bash "${ROOT}/scripts/idf_gate_build.sh"
  IDF_GATE_BUILD_DIR="build/idf-gate-v6-fake" IDF_GATE_APP_MODE="climate-v6-fake" \
    bash "${ROOT}/scripts/idf_gate_build.sh"
  # The real-input runtime requires the Stage27C BLE/NimBLE sdkconfig and actual
  # CrowPanel board profile. A generic legacy sdkconfig does not expose NimBLE headers.
  STAGE27C_BUILD_DIR="build/idf-gate-real-inputs-crowpanel" \
    GROWBOX_RF433_LOOPBACK_ENABLED=0 \
    GROWBOX_STAGE28_REAL_OUTPUTS_ENABLED=0 \
    GROWBOX_STAGE28_THERMAL_TEST_SEQUENCE_ENABLED=0 \
    bash "${ROOT}/scripts/stage27c_crowpanel.sh" build
else
  echo "==> idf builds skipped (SKIP_IDF_BUILD=1)"
fi

echo "quality gate (pre-push): OK"
