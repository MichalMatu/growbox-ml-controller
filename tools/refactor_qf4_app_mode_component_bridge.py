#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

top = ROOT / "CMakeLists.txt"
t = top.read_text()
needle = '''if(NOT GROWBOX_APP_MODE IN_LIST GROWBOX_VALID_APP_MODES)\n  message(FATAL_ERROR "Unsupported GROWBOX_APP_MODE: ${GROWBOX_APP_MODE}")\nendif()\n'''
assert t.count(needle) == 1
top.write_text(t.replace(needle, needle + 'set(ENV{GROWBOX_APP_MODE} "${GROWBOX_APP_MODE}")\n', 1))

bridge = '''if(NOT DEFINED GROWBOX_APP_MODE OR GROWBOX_APP_MODE STREQUAL "")\n  set(GROWBOX_APP_MODE "$ENV{GROWBOX_APP_MODE}")\nendif()\nif(GROWBOX_APP_MODE STREQUAL "")\n  message(FATAL_ERROR "GROWBOX_APP_MODE was not exported by the project root")\nendif()\n\n'''

src = ROOT / "src/CMakeLists.txt"
s = src.read_text()
assert s.startswith("idf_component_register(\n")
src.write_text(bridge + s)

env = ROOT / "lib/environment_control/CMakeLists.txt"
e = env.read_text()
assert e.startswith("set(GROWBOX_ENVIRONMENT_CONTROL_SRCS\n")
env.write_text(bridge + e)

guard = ROOT / "scripts/check_app_mode_boundaries.py"
g = guard.read_text()
needle = '''if top.count('set(GROWBOX_APP_MODE "legacy" CACHE STRING') != 1:\n    errors.append("app-mode-default-not-project-owned")\n'''
assert g.count(needle) == 1
replacement = needle + '''if 'set(ENV{GROWBOX_APP_MODE} "${GROWBOX_APP_MODE}")' not in top:\n    errors.append("app-mode-not-exported-to-idf-components")\nfor name, text in (("src", src), ("environment_control", env)):\n    if 'set(GROWBOX_APP_MODE "$ENV{GROWBOX_APP_MODE}")' not in text:\n        errors.append(f"app-mode-component-bridge-missing:{name}")\n'''
guard.write_text(g.replace(needle, replacement, 1))
