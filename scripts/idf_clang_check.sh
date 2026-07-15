#!/usr/bin/env bash
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

# shellcheck disable=SC1091
source "${ROOT}/scripts/source_idf.sh"

BUILD_DIR="${IDF_GATE_BUILD_DIR:-build/idf-gate}"

if ! python "${IDF_PATH}/tools/idf_tools.py" list 2>/dev/null | grep -q 'esp-clang.*installed'; then
  echo "==> installing esp-clang (one-time, required for idf clang-check)"
  python "${IDF_PATH}/tools/idf_tools.py" install esp-clang
fi

if [[ ! -f "${BUILD_DIR}/compile_commands.json" ]]; then
  echo "compile_commands missing — run idf_gate_build first" >&2
  exit 1
fi

echo "==> idf.py clang-check (src/, ${BUILD_DIR})"
idf.py -B "${BUILD_DIR}" clang-check --exit-code src
