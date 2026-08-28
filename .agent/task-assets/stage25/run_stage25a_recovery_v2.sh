#!/usr/bin/env bash
set -euo pipefail

MODE="${1:?mode required}"
EXPECTED="${2:-}"
ASSET='.agent/task-assets/stage25/apply_stage25a_ipo_fake_composition.py'

case "$MODE" in
  apply)
    test -n "$EXPECTED"
    git fetch origin mvp/environment-controller agent-control
    git reset --hard origin/mvp/environment-controller
    git clean -fd
    test "$(git rev-parse HEAD)" = "$EXPECTED"
    test -z "$(git status --porcelain)"

    git show "origin/agent-control:$ASSET" > /tmp/stage25a-raw.py
    python3 - <<'PY'
from pathlib import Path
src = Path('/tmp/stage25a-raw.py')
lines = src.read_text(encoding='utf-8').splitlines()
assert lines[-2].startswith('status = ROOT /')
assert lines[-1].startswith('status_text =')
Path('/tmp/stage25a-apply.py').write_text('\n'.join(lines[:-2]) + '\n', encoding='utf-8')
PY
    .venv/bin/python /tmp/stage25a-apply.py

    .venv/bin/python - <<'PY'
from pathlib import Path

status = Path('docs/CURRENT_STATUS.md')
text = status.read_text(encoding='utf-8')
anchor = "`ClimateControlLoop` owns confirmed previous actions. `ClimateRuntimeController` owns trends and\nestimated effective actions. Hardware providers must not duplicate those states.\n"
insert = anchor + "\nStage25A adds `ClimateApplication`, a deliberately small constructor-injected composition root around the existing input adapter, control loop and actuator adapter. Host tests now exercise the complete `ClimateSnapshotProvider -> ClimateInputAdapter -> ClimateControlLoop -> ClimateActuatorAdapter -> ClimateRoleDriver` path across multiple ticks, including stale/invalid/unavailable input, ML shadow isolation, rejected commands with OFF recovery, fault latching/reset, confirmed applied feedback and all six semantic actuator roles. Fake providers and drivers remain test-only implementations of the same public interfaces intended for future hardware.\n"
assert anchor in text
assert 'Stage25A adds `ClimateApplication`' not in text
text = text.replace(anchor, insert, 1)
status.write_text(text, encoding='utf-8')

plan = Path('docs/CONTINUATION_PLAN.md')
text = plan.read_text(encoding='utf-8')
start_heading = '## Immediate next stage: Stage25A — IPO composition with fake providers\n'
next_heading = '## Following stages\n'
assert start_heading in text
start = text.index(start_heading)
end = text.index(next_heading, start)
replacement = '''## Stage25A completed — strict IPO composition with fake providers\n\nStage25A proves the complete application-level path without physical hardware:\n\n`ClimateSnapshotProvider -> ClimateInputAdapter -> ClimateControlLoop -> ClimateActuatorAdapter -> ClimateRoleDriver`\n\n`ClimateApplication` is only the constructor-injected composition root. It adds no policy, hardware knowledge or duplicate runtime state. Fake providers/drivers live in host tests and use the same public interfaces intended for future real hardware. Multi-tick coverage includes nominal Rule control, changing/stale/invalid/unavailable measurements, ML shadow isolation, rejection -> OFF recovery, double-failure latch/reset, confirmed applied feedback and all six semantic role mappings. The legacy `src/main.cpp` remains unchanged and no SCD41/BLE/RTC/GPIO dependency is introduced.\n\n'''
text = text[:start] + replacement + text[end:]
plan.write_text(text, encoding='utf-8')
PY

    .venv/bin/pre-commit run clang-format --files \
      src/climate/ClimateApplication.h \
      src/climate/ClimateApplication.cpp \
      test/test_climate_application_composition/test_main.cpp
    git diff --check
    test -z "$(git diff --name-only "$EXPECTED" -- src/main.cpp)"
    git status --short
    ;;

  focused)
    cmake -S test/host -B build/host-tests
    cmake --build build/host-tests --target climate_application_composition_tests --parallel
    ctest --test-dir build/host-tests -R '^climate_application_composition_tests$' --output-on-failure
    .venv/bin/pre-commit run --files \
      src/climate/ClimateApplication.h \
      src/climate/ClimateApplication.cpp \
      src/CMakeLists.txt \
      test/test_climate_application_composition/test_main.cpp \
      test/host/CMakeLists.txt \
      scripts/run_clang_tidy_host.sh \
      docs/CURRENT_STATUS.md \
      docs/CONTINUATION_PLAN.md
    grep -F 'ClimateSnapshotProvider -> ClimateInputAdapter -> ClimateControlLoop -> ClimateActuatorAdapter -> ClimateRoleDriver' docs/CONTINUATION_PLAN.md
    grep -F 'Stage25A adds `ClimateApplication`' docs/CURRENT_STATUS.md
    git diff --check
    ;;

  full)
    test -n "$EXPECTED"
    git add -A
    .venv/bin/pre-commit run --all-files
    .venv/bin/python -m pytest -q -m 'not hardware'
    bash scripts/check_schema.sh
    cmake -S test/host -B build/host-tests
    cmake --build build/host-tests --parallel
    ctest --test-dir build/host-tests --output-on-failure
    bash scripts/run_clang_tidy_host.sh

    unset VIRTUAL_ENV CONDA_PREFIX PYTHONHOME || true
    export PATH='/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin'
    if [ ! -x "$HOME/.espressif/python_env/idf5.5_py3.14_env/bin/python" ]; then
      env -u VIRTUAL_ENV -u CONDA_PREFIX -u PYTHONHOME PATH='/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin' \
        bash "$HOME/esp/esp-idf/install.sh" esp32s3
    fi
    source "$HOME/esp/esp-idf/export.sh"
    idf.py --version | grep -F 'ESP-IDF v5.5.4'
    test "$(git -C "$HOME/esp/esp-idf" describe --tags --exact-match HEAD)" = 'v5.5.4'
    rm -rf build/idf-gate
    bash scripts/idf_gate_build.sh

    git diff --check
    test -z "$(git diff --name-only "$EXPECTED" -- src/main.cpp)"
    git add -A
    git diff --cached --check
    git commit -m 'Compose strict climate IPO application with fake providers'
    git push origin HEAD:mvp/environment-controller
    test -z "$(git status --porcelain)"
    printf 'PUBLISHED_HEAD=%s\n' "$(git rev-parse HEAD)"
    ;;

  *)
    echo "Unknown mode: $MODE" >&2
    exit 2
    ;;
esac
