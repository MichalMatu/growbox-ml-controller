#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# App mode belongs to the project root so every ESP-IDF component sees the same value.
top = ROOT / "CMakeLists.txt"
t = top.read_text()
needle = 'set(IDF_TARGET "esp32s3" CACHE STRING "ESP-IDF target")\n'
assert t.count(needle) == 1
insert = needle + '''\nset(GROWBOX_APP_MODE "legacy" CACHE STRING "Growbox application runtime")\nset_property(\n  CACHE GROWBOX_APP_MODE\n  PROPERTY STRINGS "legacy" "climate-v6-fake" "climate-v6-real-inputs"\n)\nset(GROWBOX_VALID_APP_MODES "legacy" "climate-v6-fake" "climate-v6-real-inputs")\nif(NOT GROWBOX_APP_MODE IN_LIST GROWBOX_VALID_APP_MODES)\n  message(FATAL_ERROR "Unsupported GROWBOX_APP_MODE: ${GROWBOX_APP_MODE}")\nendif()\n'''
top.write_text(t.replace(needle, insert, 1))

# Move the legacy implementation out of the shared entrypoint.
main_path = ROOT / "src/main.cpp"
main = main_path.read_text()
legacy_guard = '#if !GROWBOX_APP_CLIMATE_V6_FAKE && !GROWBOX_APP_CLIMATE_V6_REAL_INPUTS\n'
legacy_start = main.index(legacy_guard)
legacy_end_marker = '#endif\n\nextern "C" void app_main()'
legacy_end = main.index(legacy_end_marker, legacy_start)
legacy_inner = main[legacy_start + len(legacy_guard) : legacy_end]

app_start = main.index('extern "C" void app_main()')
else_pos = main.index('\n#else\n', app_start)
endif_pos = main.index('\n#endif\n}', else_pos)
legacy_run_body = main[else_pos + len('\n#else\n') : endif_pos]

legacy_dir = ROOT / "src/legacy"
legacy_dir.mkdir(parents=True, exist_ok=True)
(legacy_dir / "LegacyRuntime.h").write_text('''#pragma once\n\nnamespace growbox::app::legacy {\n\n[[noreturn]] void runLegacyRuntime() noexcept;\n\n} // namespace growbox::app::legacy\n''')
legacy_cpp = '#include "legacy/LegacyRuntime.h"\n\n' + legacy_inner.rstrip() + '''\n\nnamespace growbox::app::legacy {\n\n[[noreturn]] void runLegacyRuntime() noexcept {\n''' + legacy_run_body + '''}\n\n} // namespace growbox::app::legacy\n'''
(legacy_dir / "LegacyRuntime.cpp").write_text(legacy_cpp)

main = main[:legacy_start] + main[legacy_end + len('#endif\n\n') :]
old_includes = '#include "climate/ClimateV6FakeRuntime.h"\n#include "climate/ClimateV6RealInputRuntime.h"\n'
new_includes = '''#if GROWBOX_APP_CLIMATE_V6_FAKE\n#include "climate/ClimateV6FakeRuntime.h"\n#elif GROWBOX_APP_CLIMATE_V6_REAL_INPUTS\n#include "climate/ClimateV6RealInputRuntime.h"\n#else\n#include "legacy/LegacyRuntime.h"\n#endif\n'''
assert main.count(old_includes) == 1
main = main.replace(old_includes, new_includes, 1)
app_start = main.index('extern "C" void app_main()')
else_pos = main.index('\n#else\n', app_start)
endif_pos = main.index('\n#endif\n}', else_pos)
main = main[: else_pos + len('\n#else\n')] + '  growbox::app::legacy::runLegacyRuntime();' + main[endif_pos:]
main_path.write_text(main)

# src component: only selected runtime/demo sources are compiled.
src = ROOT / "src/CMakeLists.txt"
s = src.read_text()
default_block = '''set(GROWBOX_APP_MODE "legacy" CACHE STRING "Growbox application runtime")\nset_property(\n  CACHE GROWBOX_APP_MODE\n  PROPERTY STRINGS "legacy" "climate-v6-fake" "climate-v6-real-inputs"\n)\n'''
assert s.count(default_block) == 1
s = s.replace(default_block, '', 1)
mode_sources = [
    '    "climate/ClimateDeterministicFake.cpp"\n',
    '    "climate/ClimateDiagnostics.cpp"\n',
    '    "climate/ClimateV6FakeRuntime.cpp"\n',
    '    "demo/DummyEnvironmentSimulator.cpp"\n',
    '    "demo/SerialJsonProtocol.cpp"\n',
    '    "demo/protocol/JsonLineWriter.cpp"\n',
    '    "demo/protocol/ScenarioWireCodec.cpp"\n',
    '    "demo/protocol/DecisionWireCodec.cpp"\n',
    '    "demo/protocol/DiagnosticsWireCodec.cpp"\n',
    '    "demo/protocol/HeapDiagnostics.cpp"\n',
    '    "demo/protocol/StatusWireCodec.cpp"\n',
]
for line in mode_sources:
    assert s.count(line) == 1, line
    s = s.replace(line, '', 1)
legacy_marker = '''if(GROWBOX_APP_MODE STREQUAL "legacy")\n  set(GROWBOX_APP_CLIMATE_V6_FAKE 0)\n  set(GROWBOX_APP_CLIMATE_V6_REAL_INPUTS 0)\n'''
legacy_sources = '''if(GROWBOX_APP_MODE STREQUAL "legacy")\n  set(GROWBOX_APP_CLIMATE_V6_FAKE 0)\n  set(GROWBOX_APP_CLIMATE_V6_REAL_INPUTS 0)\n  target_sources(\n    ${COMPONENT_LIB}\n    PRIVATE\n      "legacy/LegacyRuntime.cpp"\n      "demo/DummyEnvironmentSimulator.cpp"\n      "demo/SerialJsonProtocol.cpp"\n      "demo/protocol/JsonLineWriter.cpp"\n      "demo/protocol/ScenarioWireCodec.cpp"\n      "demo/protocol/DecisionWireCodec.cpp"\n      "demo/protocol/DiagnosticsWireCodec.cpp"\n      "demo/protocol/HeapDiagnostics.cpp"\n      "demo/protocol/StatusWireCodec.cpp"\n  )\n'''
assert s.count(legacy_marker) == 1
s = s.replace(legacy_marker, legacy_sources, 1)
fake_marker = '''elseif(GROWBOX_APP_MODE STREQUAL "climate-v6-fake")\n  set(GROWBOX_APP_CLIMATE_V6_FAKE 1)\n  set(GROWBOX_APP_CLIMATE_V6_REAL_INPUTS 0)\n'''
fake_sources = '''elseif(GROWBOX_APP_MODE STREQUAL "climate-v6-fake")\n  set(GROWBOX_APP_CLIMATE_V6_FAKE 1)\n  set(GROWBOX_APP_CLIMATE_V6_REAL_INPUTS 0)\n  target_sources(\n    ${COMPONENT_LIB}\n    PRIVATE\n      "climate/ClimateV6FakeRuntime.cpp"\n      "climate/ClimateDeterministicFake.cpp"\n      "climate/ClimateDiagnostics.cpp"\n      "demo/protocol/JsonLineWriter.cpp"\n  )\n'''
assert s.count(fake_marker) == 1
s = s.replace(fake_marker, fake_sources, 1)
src.write_text(s)

# environment_control: V6 modes no longer compile the legacy controller implementation.
env = ROOT / "lib/environment_control/CMakeLists.txt"
env.write_text('''set(GROWBOX_ENVIRONMENT_CONTROL_SRCS\n  "src/climate/ClimateControlLoop.cpp"\n  "src/climate/ClimateFeatureEncoder.cpp"\n  "src/climate/ClimateRuntimeController.cpp"\n  "src/climate/ClimateTrendEstimator.cpp"\n)\n\nif(GROWBOX_APP_MODE STREQUAL "legacy")\n  list(APPEND GROWBOX_ENVIRONMENT_CONTROL_SRCS\n    "src/EnvironmentController.cpp"\n    "src/EnvironmentTypes.cpp"\n    "src/FeatureEncoder.cpp"\n    "src/ModelRuntime.cpp"\n    "src/SafetySupervisor.cpp"\n  )\nelseif(NOT GROWBOX_APP_MODE STREQUAL "climate-v6-fake" AND\n       NOT GROWBOX_APP_MODE STREQUAL "climate-v6-real-inputs")\n  message(FATAL_ERROR "Unsupported GROWBOX_APP_MODE in environment_control: ${GROWBOX_APP_MODE}")\nendif()\n\nidf_component_register(\n  SRCS ${GROWBOX_ENVIRONMENT_CONTROL_SRCS}\n  INCLUDE_DIRS\n    "src"\n  REQUIRES\n    emlearn_runtime\n)\n\ntarget_compile_features(${COMPONENT_LIB} PUBLIC cxx_std_17)\ntarget_compile_options(${COMPONENT_LIB} PRIVATE -Wall -Wextra -Wpedantic)\n''')

# Guard the build boundary permanently.
guard = ROOT / "scripts/check_app_mode_boundaries.py"
guard.write_text('''#!/usr/bin/env python3\nfrom pathlib import Path\nimport sys\nroot = Path(__file__).resolve().parents[1]\ntop = (root / "CMakeLists.txt").read_text()\nsrc = (root / "src/CMakeLists.txt").read_text()\nenv = (root / "lib/environment_control/CMakeLists.txt").read_text()\nmain = (root / "src/main.cpp").read_text()\nlegacy = (root / "src/legacy/LegacyRuntime.cpp").read_text()\nerrors = []\nif top.count('set(GROWBOX_APP_MODE "legacy" CACHE STRING') != 1:\n    errors.append("app-mode-default-not-project-owned")\nif 'set(GROWBOX_APP_MODE "legacy" CACHE STRING' in src:\n    errors.append("src-duplicates-app-mode-default")\nfor token in ("EnvironmentController.h", "ModelRuntime.h", "DummyEnvironmentSimulator", "SerialJsonProtocol"):\n    if token in main:\n        errors.append(f"legacy-leak-main:{token}")\n    if token not in legacy:\n        errors.append(f"legacy-runtime-missing:{token}")\nbase = src.split('if(GROWBOX_APP_MODE STREQUAL "legacy")', 1)[0]\nfor token in ("demo/DummyEnvironmentSimulator.cpp", "demo/SerialJsonProtocol.cpp", "climate/ClimateV6FakeRuntime.cpp"):\n    if token in base:\n        errors.append(f"mode-source-in-common-list:{token}")\nlegacy_block, rest = env.split('elseif(', 1)\nfor token in ("src/EnvironmentController.cpp", "src/EnvironmentTypes.cpp", "src/FeatureEncoder.cpp", "src/ModelRuntime.cpp", "src/SafetySupervisor.cpp"):\n    if token not in legacy_block:\n        errors.append(f"legacy-source-not-gated:{token}")\n    if token in rest:\n        errors.append(f"legacy-source-visible-in-v6:{token}")\nif errors:\n    print("APP_MODE_BOUNDARY_FAIL " + ",".join(errors), file=sys.stderr)\n    raise SystemExit(1)\nprint("APP_MODE_BOUNDARY_PASS")\n''')

qg = ROOT / "scripts/quality_gate_push.sh"
q = qg.read_text()
needle = 'echo "==> service console boundaries"\n"$PY" "${ROOT}/scripts/check_service_console_boundaries.py"\n'
assert q.count(needle) == 1
q = q.replace(needle, needle + '\necho "==> app-mode build boundaries"\n"$PY" "${ROOT}/scripts/check_app_mode_boundaries.py"\n', 1)
legacy_build = '  bash "${ROOT}/scripts/idf_gate_build.sh"\n'
assert q.count(legacy_build) == 1
fake_build = legacy_build + '  IDF_GATE_BUILD_DIR="build/idf-gate-v6-fake" IDF_GATE_APP_MODE="climate-v6-fake" \\\n    bash "${ROOT}/scripts/idf_gate_build.sh"\n'
q = q.replace(legacy_build, fake_build, 1)
qg.write_text(q)
