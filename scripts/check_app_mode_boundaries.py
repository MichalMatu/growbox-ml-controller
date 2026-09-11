#!/usr/bin/env python3
from pathlib import Path
import sys
root = Path(__file__).resolve().parents[1]
top = (root / "CMakeLists.txt").read_text()
src = (root / "src/CMakeLists.txt").read_text()
env = (root / "lib/environment_control/CMakeLists.txt").read_text()
main = (root / "src/main.cpp").read_text()
legacy = (root / "src/legacy/LegacyRuntime.cpp").read_text()
errors = []
if top.count('set(GROWBOX_APP_MODE "legacy" CACHE STRING') != 1:
    errors.append("app-mode-default-not-project-owned")
if 'set(ENV{GROWBOX_APP_MODE} "${GROWBOX_APP_MODE}")' not in top:
    errors.append("app-mode-not-exported-to-idf-components")
for name, text in (("src", src), ("environment_control", env)):
    if 'set(GROWBOX_APP_MODE "$ENV{GROWBOX_APP_MODE}")' not in text:
        errors.append(f"app-mode-component-bridge-missing:{name}")
if 'set(GROWBOX_APP_MODE "legacy" CACHE STRING' in src:
    errors.append("src-duplicates-app-mode-default")
for token in ("EnvironmentController.h", "ModelRuntime.h", "DummyEnvironmentSimulator", "SerialJsonProtocol"):
    if token in main:
        errors.append(f"legacy-leak-main:{token}")
    if token not in legacy:
        errors.append(f"legacy-runtime-missing:{token}")
base = src.split('if(GROWBOX_APP_MODE STREQUAL "legacy")', 1)[0]
for token in ("demo/DummyEnvironmentSimulator.cpp", "demo/SerialJsonProtocol.cpp", "climate/ClimateV6FakeRuntime.cpp"):
    if token in base:
        errors.append(f"mode-source-in-common-list:{token}")
legacy_block, rest = env.split('elseif(', 1)
for token in ("src/EnvironmentController.cpp", "src/EnvironmentTypes.cpp", "src/FeatureEncoder.cpp", "src/ModelRuntime.cpp", "src/SafetySupervisor.cpp"):
    if token not in legacy_block:
        errors.append(f"legacy-source-not-gated:{token}")
    if token in rest:
        errors.append(f"legacy-source-visible-in-v6:{token}")
if errors:
    print("APP_MODE_BOUNDARY_FAIL " + ",".join(errors), file=sys.stderr)
    raise SystemExit(1)
print("APP_MODE_BOUNDARY_PASS")
