#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "src/climate/ClimateV6RealInputRuntime.cpp"
CMAKE = ROOT / "src/CMakeLists.txt"
CROWPANEL = ROOT / "scripts/stage27c_crowpanel.sh"
IDF_GATE = ROOT / "scripts/idf_gate_build.sh"
BUILD_CONFIG = ROOT / "src/climate/runtime/RuntimeBuildConfig.h.in"

PREPROCESSOR_ONLY_MACROS = {
    "GROWBOX_APP_CLIMATE_V6_FAKE",
    "GROWBOX_APP_CLIMATE_V6_REAL_INPUTS",
    "GROWBOX_STAGE28E_LOG_COMPILE_LEVEL",
    "GROWBOX_STAGE28E_BREADCRUMB_RESTART_SELFTEST",
}
RUNTIME_VALUE_MACROS = (
    "GROWBOX_BOARD_PROFILE",
    "GROWBOX_I2C_SDA_GPIO",
    "GROWBOX_I2C_SCL_GPIO",
    "GROWBOX_BLE_TP357_MAC",
    "GROWBOX_BLE_XIAOMI_MAC",
    "GROWBOX_FIRMWARE_GIT_SHA",
    "GROWBOX_STAGE27_SD_ENABLED",
    "GROWBOX_STAGE27_FLASH_FALLBACK_ENABLED",
    "GROWBOX_SD_CMD0_PRECONDITION",
    "GROWBOX_SD_MOSI_GPIO",
    "GROWBOX_SD_MISO_GPIO",
    "GROWBOX_SD_SCLK_GPIO",
    "GROWBOX_SD_CS_GPIO",
    "GROWBOX_SD_POWER_GPIO",
    "GROWBOX_RF433_LOOPBACK_ENABLED",
    "GROWBOX_RF433_REMOTE_CAPTURE_ENABLED",
    "GROWBOX_RF433_TX_GPIO",
    "GROWBOX_RF433_RX_GPIO",
    "GROWBOX_STAGE28_SERVICE_CONSOLE_ENABLED",
    "GROWBOX_STAGE28_REAL_OUTPUTS_ENABLED",
    "GROWBOX_STAGE28_THERMAL_TEST_SEQUENCE_ENABLED",
)
MACRO_PATTERN = re.compile(r"\bGROWBOX_[A-Z0-9_]+\b")


def fail(message: str) -> None:
    print(f"RUNTIME_CONFIG_SSOT_FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


runtime_text = RUNTIME.read_text(encoding="utf-8")
cmake_text = CMAKE.read_text(encoding="utf-8")
crowpanel_text = CROWPANEL.read_text(encoding="utf-8")
idf_gate_text = IDF_GATE.read_text(encoding="utf-8")
build_config_text = BUILD_CONFIG.read_text(encoding="utf-8")

for path in sorted((ROOT / "src").rglob("*")):
    if path.suffix not in {".cpp", ".cc", ".h", ".hpp"}:
        continue
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.lstrip()
        if stripped.startswith("#ifndef GROWBOX_"):
            fail(f"{path.relative_to(ROOT)}:{line_number} contains a production fallback default")
        if stripped.startswith(("#if ", "#if(", "#ifdef ", "#ifndef ", "#elif ", "#elif(")):
            for token in MACRO_PATTERN.findall(stripped):
                if token not in PREPROCESSOR_ONLY_MACROS:
                    fail(
                        f"{path.relative_to(ROOT)}:{line_number} consumes runtime value macro "
                        f"{token}; use RuntimeBuildConfig instead"
                    )

if '"climate/runtime/RuntimeBuildConfig.h"' not in runtime_text:
    fail("real-input runtime does not consume the generated RuntimeBuildConfig")
for token in ("kBoardProfile", "kFirmwareGitSha"):
    if token not in build_config_text:
        fail(f"generated RuntimeBuildConfig is missing {token}")

if "config/runtime/GrowboxRuntimeConfig.cmake" not in cmake_text:
    fail("src/CMakeLists.txt does not include canonical GrowboxRuntimeConfig.cmake")
if "RuntimeBuildConfig.h.in" not in cmake_text or "configure_file" not in cmake_text:
    fail("src/CMakeLists.txt does not generate RuntimeBuildConfig.h")
for token in RUNTIME_VALUE_MACROS:
    if f"{token}=" in cmake_text:
        fail(f"src/CMakeLists.txt re-exports typed runtime value as compile definition: {token}")

# Generic gate forwards explicit overrides only. Defaults belong to canonical CMake.
if 'PROFILE="${IDF_GATE_PROFILE:-}"' not in idf_gate_text:
    fail("generic IDF gate does not defer the board default to canonical CMake")
if 'APP_MODE="${IDF_GATE_APP_MODE:-}"' not in idf_gate_text:
    fail("generic IDF gate does not defer the app-mode default to the project root")
if "esp32s3-devkitc1-n16r8" in idf_gate_text:
    fail("generic IDF gate duplicates the canonical board-profile default")

# The CrowPanel launcher may select profiles and forward explicit user overrides,
# but board pin values belong only to config/boards/*.cmake.
for forbidden in (
    "GROWBOX_I2C_SDA_GPIO=21",
    "GROWBOX_I2C_SCL_GPIO=38",
    "GROWBOX_SD_MOSI_GPIO=40",
    "GROWBOX_SD_MISO_GPIO=13",
    "GROWBOX_SD_SCLK_GPIO=39",
    "GROWBOX_SD_CS_GPIO=10",
    "GROWBOX_SD_POWER_GPIO=42",
    "GROWBOX_RF433_TX_GPIO:-8",
    "GROWBOX_RF433_RX_GPIO:-14",
):
    if forbidden in crowpanel_text:
        fail(f"CrowPanel launcher duplicates canonical hardware value: {forbidden}")

required_files = (
    ROOT / "config/boards/esp32s3-devkitc1-n16r8.cmake",
    ROOT / "config/boards/crowpanel-esp32s3-2_9-n8r8.cmake",
    ROOT / "config/runtime/profiles/generic.cmake",
    ROOT / "config/runtime/profiles/stage27c-crowpanel.cmake",
    BUILD_CONFIG,
)
for path in required_files:
    if not path.is_file():
        fail(f"missing canonical config input {path.relative_to(ROOT)}")

print("RUNTIME_CONFIG_SSOT_PASS")
