#!/usr/bin/env bash
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

# shellcheck disable=SC1091
source "${ROOT}/scripts/source_idf.sh"

BUILD_DIR="${IDF_GATE_BUILD_DIR:-build/idf-gate}"
SDKCONFIG_DEFAULTS="${IDF_GATE_SDKCONFIG:-config/idf/sdkconfig.defaults}"
SDKCONFIG_PATH="${IDF_GATE_SDKCONFIG_PATH:-${BUILD_DIR}/sdkconfig}"
PROFILE="${IDF_GATE_PROFILE:-}"
APP_MODE="${IDF_GATE_APP_MODE:-}"

# Gate builds must not inherit cached CMake values from an earlier profile/app-mode run.
# Canonical defaults are resolved by the project CMake configuration on every invocation.
if [[ -z "${BUILD_DIR}" || "${BUILD_DIR}" == "/" ]]; then
  echo "Refusing unsafe IDF gate build directory: '${BUILD_DIR}'" >&2
  exit 2
fi
rm -rf "${BUILD_DIR}"
mkdir -p "${BUILD_DIR}"

CMAKE_ARGS=(
  -D "SDKCONFIG=${SDKCONFIG_PATH}"
  -D "SDKCONFIG_DEFAULTS=${SDKCONFIG_DEFAULTS}"
)
if [[ -n "${PROFILE}" ]]; then
  CMAKE_ARGS+=( -D "GROWBOX_BOARD_PROFILE=${PROFILE}" )
fi
if [[ -n "${APP_MODE}" ]]; then
  CMAKE_ARGS+=( -D "GROWBOX_APP_MODE=${APP_MODE}" )
fi

echo "==> idf.py build (${PROFILE:-canonical-board}, ${BUILD_DIR}, app=${APP_MODE:-canonical-app})"
idf.py -B "${BUILD_DIR}" "${CMAKE_ARGS[@]}" build
