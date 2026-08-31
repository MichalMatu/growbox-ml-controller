#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# shellcheck disable=SC1091
source "$ROOT/scripts/source_idf.sh"

COMMAND="${1:-build}"
BUILD_DIR="${STAGE27C_BUILD_DIR:-build/idf-stage27c-crowpanel}"
SDKCONFIG_PATH="${STAGE27C_SDKCONFIG:-${BUILD_DIR}/sdkconfig}"
BLE_OUTSIDE_MAC="${GROWBOX_BLE_OUTSIDE_MAC:-A4:C1:38:4F:24:CD}"

idf_args=(
  -B "$BUILD_DIR"
  -D "SDKCONFIG=$SDKCONFIG_PATH"
  -D "SDKCONFIG_DEFAULTS=config/idf/sdkconfig.defaults;config/idf/sdkconfig.defaults.n8r8;config/idf/sdkconfig.defaults.stage27"
  -D "GROWBOX_BOARD_PROFILE=crowpanel-esp32s3-2_9-n8r8"
  -D "GROWBOX_APP_MODE=climate-v6-real-inputs"
  -D "GROWBOX_I2C_SDA_GPIO=21"
  -D "GROWBOX_I2C_SCL_GPIO=38"
  -D "GROWBOX_BLE_OUTSIDE_MAC=$BLE_OUTSIDE_MAC"
)

port_args=()
if [[ -n "${PORT:-}" ]]; then
  port_args=(-p "$PORT")
fi

case "$COMMAND" in
  build)
    idf.py "${idf_args[@]}" build
    ;;
  flash)
    idf.py "${idf_args[@]}" "${port_args[@]}" build flash
    ;;
  monitor)
    idf.py -B "$BUILD_DIR" "${port_args[@]}" monitor
    ;;
  flash-monitor)
    idf.py "${idf_args[@]}" "${port_args[@]}" build flash monitor
    ;;
  clean)
    rm -rf "$BUILD_DIR"
    ;;
  *)
    echo "Usage: $0 {build|flash|monitor|flash-monitor|clean}" >&2
    exit 2
    ;;
esac
