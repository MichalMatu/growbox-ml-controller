#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# shellcheck disable=SC1091
source "$ROOT/scripts/source_idf.sh"

COMMAND="${1:-build}"
BUILD_DIR="${STAGE27C_BUILD_DIR:-build/idf-stage27c-crowpanel}"
SDKCONFIG_PATH="${STAGE27C_SDKCONFIG:-${BUILD_DIR}/sdkconfig}"
BLE_TP357_MAC="${GROWBOX_BLE_TP357_MAC:-F7:5F:8D:0F:76:20}"
BLE_XIAOMI_MAC="${GROWBOX_BLE_XIAOMI_MAC:-A4:C1:38:4F:24:CD}"
FIRMWARE_GIT_SHA="${GROWBOX_FIRMWARE_GIT_SHA:-$(git rev-parse HEAD)}"
SD_ENABLED="${GROWBOX_STAGE27_SD_ENABLED:-1}"
FLASH_FALLBACK_ENABLED="${GROWBOX_STAGE27_FLASH_FALLBACK_ENABLED:-1}"
SD_CMD0_PRECONDITION="${GROWBOX_SD_CMD0_PRECONDITION:-0}"
RF433_LOOPBACK_ENABLED="${GROWBOX_RF433_LOOPBACK_ENABLED:-0}"
RF433_LOOPBACK_AUTO_SMOKE="${GROWBOX_RF433_LOOPBACK_AUTO_SMOKE:-0}"
RF433_REMOTE_CAPTURE_ENABLED="${GROWBOX_RF433_REMOTE_CAPTURE_ENABLED:-0}"
RF433_LOOPBACK_SMOKE_CODE="${GROWBOX_RF433_LOOPBACK_SMOKE_CODE:-0xA55A}"
RF433_LOOPBACK_SMOKE_BITS="${GROWBOX_RF433_LOOPBACK_SMOKE_BITS:-16}"
RF433_LOOPBACK_SMOKE_PROTOCOL="${GROWBOX_RF433_LOOPBACK_SMOKE_PROTOCOL:-1}"
RF433_LOOPBACK_SMOKE_REPEAT="${GROWBOX_RF433_LOOPBACK_SMOKE_REPEAT:-3}"
RF433_LOOPBACK_SMOKE_PULSE_US="${GROWBOX_RF433_LOOPBACK_SMOKE_PULSE_US:-0}"
RF433_TX_GPIO="${GROWBOX_RF433_TX_GPIO:-8}"
RF433_RX_GPIO="${GROWBOX_RF433_RX_GPIO:-14}"
SERVICE_CONSOLE_ENABLED="${GROWBOX_STAGE28_SERVICE_CONSOLE_ENABLED:-1}"
REAL_OUTPUTS_ENABLED="${GROWBOX_STAGE28_REAL_OUTPUTS_ENABLED:-0}"
THERMAL_TEST_SEQUENCE_ENABLED="${GROWBOX_STAGE28_THERMAL_TEST_SEQUENCE_ENABLED:-0}"
BREADCRUMB_RESTART_SELFTEST="${GROWBOX_STAGE28E_BREADCRUMB_RESTART_SELFTEST:-0}"

case "$REAL_OUTPUTS_ENABLED" in
  0|1) ;;
  *) echo "GROWBOX_STAGE28_REAL_OUTPUTS_ENABLED must be 0 or 1" >&2; exit 2 ;;
esac
case "$THERMAL_TEST_SEQUENCE_ENABLED" in
  0|1) ;;
  *) echo "GROWBOX_STAGE28_THERMAL_TEST_SEQUENCE_ENABLED must be 0 or 1" >&2; exit 2 ;;
esac
case "$BREADCRUMB_RESTART_SELFTEST" in
  0|1) ;;
  *) echo "GROWBOX_STAGE28E_BREADCRUMB_RESTART_SELFTEST must be 0 or 1" >&2; exit 2 ;;
esac
if [[ "$THERMAL_TEST_SEQUENCE_ENABLED" == "1" && "$REAL_OUTPUTS_ENABLED" != "1" ]]; then
  echo "Thermal test sequence requires GROWBOX_STAGE28_REAL_OUTPUTS_ENABLED=1" >&2
  exit 2
fi
if [[ "$REAL_OUTPUTS_ENABLED" == "1" && "$RF433_LOOPBACK_ENABLED" != "1" ]]; then
  echo "Real RF outputs require GROWBOX_RF433_LOOPBACK_ENABLED=1" >&2
  exit 2
fi

STAGE27C_PYTHON="${STAGE27C_PYTHON:-$ROOT/.venv/bin/python}"
if [[ ! -x "$STAGE27C_PYTHON" ]]; then
  STAGE27C_PYTHON="$(command -v python3)"
fi

idf_args=(
  -B "$BUILD_DIR"
  -D "SDKCONFIG=$SDKCONFIG_PATH"
  -D "SDKCONFIG_DEFAULTS=config/idf/sdkconfig.defaults;config/idf/sdkconfig.defaults.n8r8;config/idf/sdkconfig.defaults.stage27;config/idf/sdkconfig.defaults.stage27c"
  -D "GROWBOX_BOARD_PROFILE=crowpanel-esp32s3-2_9-n8r8"
  -D "GROWBOX_APP_MODE=climate-v6-real-inputs"
  -D "GROWBOX_I2C_SDA_GPIO=21"
  -D "GROWBOX_I2C_SCL_GPIO=38"
  -D "GROWBOX_BLE_TP357_MAC=$BLE_TP357_MAC"
  -D "GROWBOX_BLE_XIAOMI_MAC=$BLE_XIAOMI_MAC"
  -D "GROWBOX_FIRMWARE_GIT_SHA=$FIRMWARE_GIT_SHA"
  -D "GROWBOX_STAGE27_SD_ENABLED=$SD_ENABLED"
  -D "GROWBOX_STAGE27_FLASH_FALLBACK_ENABLED=$FLASH_FALLBACK_ENABLED"
  -D "GROWBOX_SD_CMD0_PRECONDITION=$SD_CMD0_PRECONDITION"
  -D "GROWBOX_SD_MOSI_GPIO=40"
  -D "GROWBOX_SD_MISO_GPIO=13"
  -D "GROWBOX_SD_SCLK_GPIO=39"
  -D "GROWBOX_SD_CS_GPIO=10"
  -D "GROWBOX_SD_POWER_GPIO=42"
  -D "GROWBOX_RF433_LOOPBACK_ENABLED=$RF433_LOOPBACK_ENABLED"
  -D "GROWBOX_RF433_LOOPBACK_AUTO_SMOKE=$RF433_LOOPBACK_AUTO_SMOKE"
  -D "GROWBOX_RF433_REMOTE_CAPTURE_ENABLED=$RF433_REMOTE_CAPTURE_ENABLED"
  -D "GROWBOX_RF433_LOOPBACK_SMOKE_CODE=$RF433_LOOPBACK_SMOKE_CODE"
  -D "GROWBOX_RF433_LOOPBACK_SMOKE_BITS=$RF433_LOOPBACK_SMOKE_BITS"
  -D "GROWBOX_RF433_LOOPBACK_SMOKE_PROTOCOL=$RF433_LOOPBACK_SMOKE_PROTOCOL"
  -D "GROWBOX_RF433_LOOPBACK_SMOKE_REPEAT=$RF433_LOOPBACK_SMOKE_REPEAT"
  -D "GROWBOX_RF433_LOOPBACK_SMOKE_PULSE_US=$RF433_LOOPBACK_SMOKE_PULSE_US"
  -D "GROWBOX_RF433_TX_GPIO=$RF433_TX_GPIO"
  -D "GROWBOX_RF433_RX_GPIO=$RF433_RX_GPIO"
  -D "GROWBOX_STAGE28_SERVICE_CONSOLE_ENABLED=$SERVICE_CONSOLE_ENABLED"
  -D "GROWBOX_STAGE28_REAL_OUTPUTS_ENABLED=$REAL_OUTPUTS_ENABLED"
  -D "GROWBOX_STAGE28_THERMAL_TEST_SEQUENCE_ENABLED=$THERMAL_TEST_SEQUENCE_ENABLED"
  -D "GROWBOX_STAGE28E_BREADCRUMB_RESTART_SELFTEST=$BREADCRUMB_RESTART_SELFTEST"
)

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
