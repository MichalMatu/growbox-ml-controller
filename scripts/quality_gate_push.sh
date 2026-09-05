#!/usr/bin/env bash
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

PY="${ROOT}/.venv/bin/python"
if [[ ! -x "$PY" ]]; then
  PY="$(command -v python3)"
fi

echo "==> pytest"
# Hardware board E2E needs a matching flashed firmware; exclude from pre-push.
"$PY" -m pytest -q -m "not hardware"

echo "==> host C++ tests"
cmake -S test/host -B build/host-tests -DCMAKE_EXPORT_COMPILE_COMMANDS=ON
cmake --build build/host-tests --parallel
ctest --test-dir build/host-tests --output-on-failure

echo "==> Stage28D bounded-output regression tests"
HOST_CXX="${CXX:-c++}"
"$HOST_CXX" -std=c++17 -Wall -Wextra -Wpedantic \
  -Isrc -Ilib/environment_control/src \
  test/test_stage28d_rf_output_endpoint/test_main.cpp \
  src/climate/Stage28dRfOutputEndpoint.cpp \
  src/climate/Stage28dOutputBindings.cpp \
  src/climate/ClimateSemanticOutput.cpp \
  src/climate/rf433/ClimateRf433EndpointRegistry.cpp \
  -o /tmp/stage28d_rf_output_endpoint_tests
/tmp/stage28d_rf_output_endpoint_tests
"$HOST_CXX" -std=c++17 -Wall -Wextra -Wpedantic \
  -Isrc \
  test/test_stage28d_thermal_sequence/test_main.cpp \
  src/climate/Stage28dThermalTestSequence.cpp \
  -o /tmp/stage28d_thermal_sequence_tests
/tmp/stage28d_thermal_sequence_tests

if [[ "${SKIP_CLANG_TIDY:-}" != "1" ]]; then
  bash "${ROOT}/scripts/run_clang_tidy_host.sh"
else
  echo "==> host clang-tidy skipped (SKIP_CLANG_TIDY=1)"
fi

if [[ "${SKIP_IDF_BUILD:-}" != "1" ]]; then
  bash "${ROOT}/scripts/idf_gate_build.sh"
  IDF_GATE_BUILD_DIR="build/idf-gate-real-inputs" \
    IDF_GATE_APP_MODE="climate-v6-real-inputs" \
    bash "${ROOT}/scripts/idf_gate_build.sh"
else
  echo "==> idf builds skipped (SKIP_IDF_BUILD=1)"
fi

echo "quality gate (pre-push): OK"
