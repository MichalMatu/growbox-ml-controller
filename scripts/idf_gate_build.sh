#!/usr/bin/env bash
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

# shellcheck disable=SC1091
source "${ROOT}/scripts/source_idf.sh"

BUILD_DIR="${IDF_GATE_BUILD_DIR:-build/idf-gate}"
SDKCONFIG="${IDF_GATE_SDKCONFIG:-sdkconfig.defaults}"
PROFILE="${IDF_GATE_PROFILE:-esp32s3-devkitc1-n8}"

echo "==> idf.py build (${PROFILE}, ${BUILD_DIR})"
idf.py -B "${BUILD_DIR}" \
  -D "SDKCONFIG_DEFAULTS=${SDKCONFIG}" \
  -D "GROWBOX_BOARD_PROFILE=${PROFILE}" \
  build
