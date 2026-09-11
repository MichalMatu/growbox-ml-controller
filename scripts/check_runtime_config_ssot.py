#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "src/climate/ClimateV6RealInputRuntime.cpp"
CMAKE = ROOT / "src/CMakeLists.txt"
CROWPANEL = ROOT / "scripts/stage27c_crowpanel.sh"


def fail(message: str) -> None:
    print(f"RUNTIME_CONFIG_SSOT_FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


runtime_text = RUNTIME.read_text(encoding="utf-8")
cmake_text = CMAKE.read_text(encoding="utf-8")
crowpanel_text = CROWPANEL.read_text(encoding="utf-8")

for forbidden in ("#ifndef GROWBOX_", "#define GROWBOX_"):
    if forbidden in runtime_text:
        fail(f"{RUNTIME.relative_to(ROOT)} contains fallback macro '{forbidden}'")

if '"climate/runtime/RuntimeBuildConfig.h"' not in runtime_text:
    fail("real-input runtime does not consume the generated RuntimeBuildConfig")

if "config/runtime/GrowboxRuntimeConfig.cmake" not in cmake_text:
    fail("src/CMakeLists.txt does not include canonical GrowboxRuntimeConfig.cmake")
if "RuntimeBuildConfig.h.in" not in cmake_text or "configure_file" not in cmake_text:
    fail("src/CMakeLists.txt does not generate RuntimeBuildConfig.h")

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
    ROOT / "src/climate/runtime/RuntimeBuildConfig.h.in",
)
for path in required_files:
    if not path.is_file():
        fail(f"missing canonical config input {path.relative_to(ROOT)}")

print("RUNTIME_CONFIG_SSOT_PASS")
