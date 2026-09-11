from pathlib import Path
import re

root = Path(".")
cmake = root / "src/CMakeLists.txt"
runtime = root / "src/climate/ClimateV6RealInputRuntime.cpp"
crowpanel = root / "scripts/stage27c_crowpanel.sh"
quality = root / "scripts/quality_gate_push.sh"

text = cmake.read_text()
pattern = re.compile(
    r'if\(NOT DEFINED GROWBOX_BOARD_PROFILE\)\n.*?\n(?=target_compile_definitions\()',
    re.S,
)
replacement = """get_filename_component(GROWBOX_PROJECT_ROOT "${CMAKE_CURRENT_LIST_DIR}/.." ABSOLUTE)
include("${GROWBOX_PROJECT_ROOT}/config/runtime/GrowboxRuntimeConfig.cmake")

set(GROWBOX_GENERATED_INCLUDE_DIR "${CMAKE_CURRENT_BINARY_DIR}/generated")
file(MAKE_DIRECTORY "${GROWBOX_GENERATED_INCLUDE_DIR}/climate/runtime")
configure_file(
  "${CMAKE_CURRENT_LIST_DIR}/climate/runtime/RuntimeBuildConfig.h.in"
  "${GROWBOX_GENERATED_INCLUDE_DIR}/climate/runtime/RuntimeBuildConfig.h"
  @ONLY
)
target_include_directories(${COMPONENT_LIB} PRIVATE "${GROWBOX_GENERATED_INCLUDE_DIR}")

"""
text2, count = pattern.subn(replacement, text, count=1)
if count != 1:
    raise SystemExit(f"src/CMakeLists.txt config block replacement count={count}")
cmake.write_text(text2)

text = runtime.read_text()
include_anchor = '#include "climate/runtime/Stage28ePlatformDiagnostics.h"\n'
generated_include = '#include "climate/runtime/RuntimeBuildConfig.h"\n'
if generated_include not in text:
    if include_anchor not in text:
        raise SystemExit("runtime include anchor missing")
    text = text.replace(include_anchor, include_anchor + generated_include, 1)

start = text.find("#ifndef GROWBOX_I2C_SDA_GPIO")
end = text.find("namespace growbox::app::climate_io {")
if start < 0 or end < 0 or end <= start:
    raise SystemExit("runtime fallback macro block not found")
text = text[:start] + text[end:]

replacements = {
    "GROWBOX_I2C_SDA_GPIO": "runtime_config::kI2cSdaGpio",
    "GROWBOX_I2C_SCL_GPIO": "runtime_config::kI2cSclGpio",
    "GROWBOX_BLE_TP357_MAC": "runtime_config::kBleTp357Mac",
    "GROWBOX_BLE_XIAOMI_MAC": "runtime_config::kBleXiaomiMac",
    "GROWBOX_FIRMWARE_GIT_SHA": "runtime_config::kFirmwareGitSha",
    "GROWBOX_STAGE27_SD_ENABLED": "runtime_config::kStage27SdEnabled",
    "GROWBOX_STAGE27_FLASH_FALLBACK_ENABLED": "runtime_config::kStage27FlashFallbackEnabled",
    "GROWBOX_SD_CMD0_PRECONDITION": "runtime_config::kSdCmd0Precondition",
    "GROWBOX_SD_MOSI_GPIO": "runtime_config::kSdMosiGpio",
    "GROWBOX_SD_MISO_GPIO": "runtime_config::kSdMisoGpio",
    "GROWBOX_SD_SCLK_GPIO": "runtime_config::kSdSclkGpio",
    "GROWBOX_SD_CS_GPIO": "runtime_config::kSdCsGpio",
    "GROWBOX_SD_POWER_GPIO": "runtime_config::kSdPowerGpio",
    "GROWBOX_RF433_LOOPBACK_ENABLED": "runtime_config::kRf433LoopbackEnabled",
    "GROWBOX_RF433_REMOTE_CAPTURE_ENABLED": "runtime_config::kRf433RemoteCaptureEnabled",
    "GROWBOX_RF433_TX_GPIO": "runtime_config::kRf433TxGpio",
    "GROWBOX_RF433_RX_GPIO": "runtime_config::kRf433RxGpio",
    "GROWBOX_STAGE28_SERVICE_CONSOLE_ENABLED": "runtime_config::kServiceConsoleEnabled",
    "GROWBOX_STAGE28_REAL_OUTPUTS_ENABLED": "runtime_config::kRealOutputsEnabled",
    "GROWBOX_STAGE28_THERMAL_TEST_SEQUENCE_ENABLED": "runtime_config::kThermalTestSequenceEnabled",
}
for old, new in replacements.items():
    text = text.replace(old, new)
for name in (
    "kStage27SdEnabled",
    "kStage27FlashFallbackEnabled",
    "kSdCmd0Precondition",
    "kRf433LoopbackEnabled",
    "kRf433RemoteCaptureEnabled",
    "kServiceConsoleEnabled",
    "kRealOutputsEnabled",
    "kThermalTestSequenceEnabled",
):
    text = text.replace(f"runtime_config::{name} != 0", f"runtime_config::{name}")
runtime.write_text(text)

text = crowpanel.read_text()
start = text.find('BLE_TP357_MAC=')
end_marker = 'BREADCRUMB_RESTART_SELFTEST="${GROWBOX_STAGE28E_BREADCRUMB_RESTART_SELFTEST:-0}"\n'
end = text.find(end_marker)
if start < 0 or end < 0:
    raise SystemExit("CrowPanel defaults block not found")
end += len(end_marker)
text = text[:start] + 'RUNTIME_PROFILE="${GROWBOX_RUNTIME_PROFILE:-stage27c-crowpanel}"\n' + text[end:]

validation_start = text.find('case "$REAL_OUTPUTS_ENABLED" in')
python_anchor = 'STAGE27C_PYTHON="${STAGE27C_PYTHON:-$ROOT/.venv/bin/python}"'
validation_end = text.find(python_anchor)
if validation_start < 0 or validation_end < 0:
    raise SystemExit("CrowPanel validation block not found")
text = text[:validation_start] + text[validation_end:]

text = text.replace('if [[ "$RF433_LOOPBACK_ENABLED" == "1" ]]; then',
                    'if [[ "${GROWBOX_RF433_LOOPBACK_ENABLED:-0}" == "1" ]]; then')

idf_start = text.find('idf_args=(\n')
idf_end = text.find(')\n\nresolved_port=""', idf_start)
if idf_start < 0 or idf_end < 0:
    raise SystemExit("CrowPanel idf_args block not found")
idf_end += 2
new_args = """idf_args=(
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

for name in \
  GROWBOX_BLE_TP357_MAC \
  GROWBOX_BLE_XIAOMI_MAC \
  GROWBOX_FIRMWARE_GIT_SHA \
  GROWBOX_STAGE27_SD_ENABLED \
  GROWBOX_STAGE27_FLASH_FALLBACK_ENABLED \
  GROWBOX_SD_CMD0_PRECONDITION \
  GROWBOX_RF433_LOOPBACK_ENABLED \
  GROWBOX_RF433_REMOTE_CAPTURE_ENABLED \
  GROWBOX_RF433_TX_GPIO \
  GROWBOX_RF433_RX_GPIO \
  GROWBOX_STAGE28_SERVICE_CONSOLE_ENABLED \
  GROWBOX_STAGE28_REAL_OUTPUTS_ENABLED \
  GROWBOX_STAGE28_THERMAL_TEST_SEQUENCE_ENABLED \
  GROWBOX_STAGE28E_BREADCRUMB_RESTART_SELFTEST; do
  append_env_override "$name"
done
"""
text = text[:idf_start] + new_args + text[idf_end:]
crowpanel.write_text(text)

text = quality.read_text()
anchor = 'echo "==> pytest"\n'
insert = 'echo "==> runtime configuration SSOT"\n"$PY" "${ROOT}/scripts/check_runtime_config_ssot.py"\n\n'
if insert not in text:
    if anchor not in text:
        raise SystemExit("quality gate anchor missing")
    text = text.replace(anchor, insert + anchor, 1)
quality.write_text(text)
