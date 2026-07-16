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

if [[ "${SKIP_CLANG_TIDY:-}" != "1" ]]; then
  bash "${ROOT}/scripts/run_clang_tidy_host.sh"
else
  echo "==> host clang-tidy skipped (SKIP_CLANG_TIDY=1)"
fi

if [[ "${SKIP_IDF_BUILD:-}" != "1" ]]; then
  bash "${ROOT}/scripts/idf_gate_build.sh"
else
  echo "==> idf build skipped (SKIP_IDF_BUILD=1)"
fi

echo "quality gate (pre-push): OK"
