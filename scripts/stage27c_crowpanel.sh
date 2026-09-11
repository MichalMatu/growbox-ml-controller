#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# shellcheck disable=SC1091
source "$ROOT/scripts/source_idf.sh"

COMMAND="${1:-build}"
BUILD_DIR="${STAGE27C_BUILD_DIR:-build/idf-stage27c-crowpanel}"
SDKCONFIG_PATH="${STAGE27C_SDKCONFIG:-${BUILD_DIR}/sdkconfig}"
RUNTIME_PROFILE="${GROWBOX_RUNTIME_PROFILE:-stage27c-crowpanel}"

STAGE27C_PYTHON="${STAGE27C_PYTHON:-$ROOT/.venv/bin/python}"
if [[ ! -x "$STAGE27C_PYTHON" ]]; then
  STAGE27C_PYTHON="$(command -v python3)"
fi

SDKCONFIG_DEFAULTS="config/idf/sdkconfig.defaults;config/idf/sdkconfig.defaults.n8r8;config/idf/sdkconfig.defaults.stage27;config/idf/sdkconfig.defaults.stage27c"
if [[ "${GROWBOX_RF433_LOOPBACK_ENABLED:-0}" == "1" ]]; then
  SDKCONFIG_DEFAULTS+=";config/idf/sdkconfig.defaults.stage28rf"
fi

idf_args=(
  -B "$BUILD_DIR"
  -D "SDKCONFIG=$SDKCONFIG_PATH"
  -D "SDKCONFIG_DEFAULTS=$SDKCONFIG_DEFAULTS"
  -D "GROWBOX_BOARD_PROFILE=crowpanel-esp32s3-2_9-n8r8"
  -D "GROWBOX_RUNTIME_PROFILE=$RUNTIME_PROFILE"
  -D "GROWBOX_APP_MODE=climate-v6-real-inputs"
)

append_env_override() {
  local name="$1"
  if printenv "$name" >/dev/null 2>&1; then
    idf_args+=(-D "${name}=${!name}")
  fi
}

for name in   GROWBOX_BLE_TP357_MAC   GROWBOX_BLE_XIAOMI_MAC   GROWBOX_FIRMWARE_GIT_SHA   GROWBOX_STAGE27_SD_ENABLED   GROWBOX_STAGE27_FLASH_FALLBACK_ENABLED   GROWBOX_SD_CMD0_PRECONDITION   GROWBOX_RF433_LOOPBACK_ENABLED   GROWBOX_RF433_REMOTE_CAPTURE_ENABLED   GROWBOX_RF433_TX_GPIO   GROWBOX_RF433_RX_GPIO   GROWBOX_STAGE28_SERVICE_CONSOLE_ENABLED   GROWBOX_STAGE28_REAL_OUTPUTS_ENABLED   GROWBOX_STAGE28_THERMAL_TEST_SEQUENCE_ENABLED   GROWBOX_STAGE28E_BREADCRUMB_RESTART_SELFTEST; do
  append_env_override "$name"
done

resolved_port=""
resolve_crowpanel_port() {
  if [[ -n "${PORT:-}" ]]; then
    resolved_port="$PORT"
  else
    resolved_port="$($STAGE27C_PYTHON -c 'from tools.stage27c_soak import detect_ch340_port; print(detect_ch340_port())')"
  fi
  if [[ -z "$resolved_port" ]]; then
    echo "Unable to resolve CrowPanel serial port" >&2
    exit 2
  fi
  echo "CrowPanel serial port: $resolved_port" >&2
}

verify_esp32s3_port() {
  local probe
  if ! probe="$(esptool.py --port "$resolved_port" chip_id 2>&1)"; then
    echo "$probe" >&2
    echo "Unable to identify chip on $resolved_port; refusing to flash" >&2
    exit 2
  fi
  echo "$probe" >&2
  if ! grep -q "ESP32-S3" <<<"$probe"; then
    echo "Port $resolved_port is not ESP32-S3; refusing to flash" >&2
    exit 2
  fi
}

case "$COMMAND" in
  build)
    idf.py "${idf_args[@]}" build
    ;;
  flash)
    resolve_crowpanel_port
    verify_esp32s3_port
    idf.py "${idf_args[@]}" -p "$resolved_port" build flash
    ;;
  monitor)
    resolve_crowpanel_port
    idf.py -B "$BUILD_DIR" -p "$resolved_port" monitor
    ;;
  flash-monitor)
    resolve_crowpanel_port
    verify_esp32s3_port
    idf.py "${idf_args[@]}" -p "$resolved_port" build flash monitor
    ;;
  clean)
    rm -rf "$BUILD_DIR"
    ;;
  *)
    echo "Usage: $0 {build|flash|monitor|flash-monitor|clean}" >&2
    exit 2
    ;;
esac
