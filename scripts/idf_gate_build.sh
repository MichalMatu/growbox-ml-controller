#!/usr/bin/env bash
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

# shellcheck disable=SC1091
source "${ROOT}/scripts/source_idf.sh"

BUILD_DIR="${IDF_GATE_BUILD_DIR:-build/idf-gate}"
SDKCONFIG_DEFAULTS="${IDF_GATE_SDKCONFIG:-config/idf/sdkconfig.defaults}"
SDKCONFIG_PATH="${IDF_GATE_SDKCONFIG_PATH:-${BUILD_DIR}/sdkconfig}"
PROFILE="${IDF_GATE_PROFILE:-esp32s3-devkitc1-n8}"
APP_MODE="${IDF_GATE_APP_MODE:-legacy}"

mkdir -p "${BUILD_DIR}"

echo "==> idf.py build (${PROFILE}, ${BUILD_DIR}, app=${APP_MODE})"
idf.py -B "${BUILD_DIR}" \
  -D "SDKCONFIG=${SDKCONFIG_PATH}" \
  -D "SDKCONFIG_DEFAULTS=${SDKCONFIG_DEFAULTS}" \
  -D "GROWBOX_BOARD_PROFILE=${PROFILE}" \
  -D "GROWBOX_APP_MODE=${APP_MODE}" \
  build
