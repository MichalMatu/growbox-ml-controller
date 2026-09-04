#!/usr/bin/env bash
set -euo pipefail

git fetch -q origin agent-control
BASE=/tmp/growbox-stage28d-service-console-v1-base.sh
git show origin/agent-control:.agent/payloads/20260904-growbox-stage28d-service-console-v1/run.sh > "$BASE"

python3 - "$BASE" <<'PY'
from pathlib import Path
import sys
p = Path(sys.argv[1])
s = p.read_text()

# Remove the unused forward declaration that produced the only project warning in the first firmware compile.
s = s.replace('''void printMeasuredValue(Stage28ServiceConsole& console, const char* name,\n                        const ::growbox::climate::MeasuredValue& value) noexcept;\n\n''', '', 1)

# Replace the broad quality-gate invocation with the same gate stages but an explicit single-job host build.
old = '''export CMAKE_BUILD_PARALLEL_LEVEL=2\nbash scripts/quality_gate_push.sh\n'''
new = r'''export CMAKE_BUILD_PARALLEL_LEVEL=1
PYTHON_BIN="$(git rev-parse --show-toplevel)/.venv/bin/python"
if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="$(command -v python3)"
fi

echo "==> pytest"
"$PYTHON_BIN" -m pytest -q -m "not hardware"

echo "==> host C++ tests (bounded single-job build)"
cmake -S test/host -B build/host-tests -DCMAKE_EXPORT_COMPILE_COMMANDS=ON
cmake --build build/host-tests --parallel 1
ctest --test-dir build/host-tests --output-on-failure

echo "==> host clang-tidy (bounded single-job build)"
TIDY_COPY=/tmp/run_clang_tidy_host_stage28d_service_console_v2.sh
cp scripts/run_clang_tidy_host.sh "$TIDY_COPY"
python3 - "$TIDY_COPY" <<'PYTIDY'
from pathlib import Path
import sys
p = Path(sys.argv[1])
s = p.read_text()
old = 'cmake --build "${BUILD_DIR}" --parallel\n'
new = 'cmake --build "${BUILD_DIR}" --parallel 1\n'
if old not in s:
    raise SystemExit('clang-tidy build command marker missing')
p.write_text(s.replace(old, new, 1))
PYTIDY
bash "$TIDY_COPY"

echo "==> ESP-IDF gate"
bash scripts/idf_gate_build.sh

echo "quality gate (memory-bounded equivalent): OK"
'''
if old not in s:
    raise SystemExit('quality gate invocation marker missing')
s = s.replace(old, new, 1)

s = s.replace('git commit -m "Add Stage28D USB service console"',
              'git commit -m "Add Stage28D USB service console"', 1)
s = s.replace('STAGE28D_SERVICE_CONSOLE_READY commit=%s parent=%s parser_tests=pass rf_tests=pass crowpanel_build=pass quality_gate=pass runtime_outputs=fake-locked automatic_rf_tx=0',
              'STAGE28D_SERVICE_CONSOLE_READY commit=%s parent=%s parser_tests=pass rf_tests=pass crowpanel_build=pass quality_gate=pass quality_gate_jobs=1 runtime_outputs=fake-locked automatic_rf_tx=0', 1)
p.write_text(s)
PY

bash "$BASE"
