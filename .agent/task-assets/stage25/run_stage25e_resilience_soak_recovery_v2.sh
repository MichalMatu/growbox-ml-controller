#!/usr/bin/env bash
set -euo pipefail

MODE="${1:?mode required}"
EXPECTED="${2:-}"
ORIGINAL='.agent/task-assets/stage25/run_stage25e_fault_soak_v1.sh'

load_original() {
  git fetch origin agent-control
  git show "origin/agent-control:$ORIGINAL" > /tmp/stage25e-original.sh
}

case "$MODE" in
  apply)
    test -n "$EXPECTED"
    load_original
    bash /tmp/stage25e-original.sh apply "$EXPECTED"

    .venv/bin/python - <<'PY'
from pathlib import Path
p = Path('test/test_climate_fault_soak/test_main.cpp')
s = p.read_text()
s = s.replace(
'''      assert(off(decision.applied));
      assert((decision.rule.safety_interventions & RequiredSensorUnusable) != 0U);''',
'''      assert(off(decision.rule.raw));
      assert(off(decision.rule.arbitrated));
      assert(off(decision.rule.safe));
      assert(off(decision.applied));''')
s = s.replace(
'''    } else if (phase == 2U || phase == 3U) {
      assert((decision.rule.safety_interventions & RequiredSensorUnusable) != 0U);
      assert(off(decision.applied));
    } else if (phase == 5U) {
      assert((decision.rule.arbitration_interventions & UnavailableHeater) != 0U);
      assert((decision.rule.arbitration_interventions & UnavailableCo2Doser) != 0U);
      assert(near(decision.applied.heater, 0.0F));
      assert(near(decision.applied.co2_doser, 0.0F));''',
'''    } else if (phase == 2U || phase == 3U) {
      assert(off(decision.rule.raw));
      assert(off(decision.rule.arbitrated));
      assert(off(decision.rule.safe));
      assert(off(decision.applied));
    } else if (phase == 5U) {
      assert(near(decision.rule.raw.heater, 0.0F));
      assert(near(decision.rule.raw.co2_doser, 0.0F));
      assert(near(decision.applied.heater, 0.0F));
      assert(near(decision.applied.co2_doser, 0.0F));''')
p.write_text(s)
PY

    .venv/bin/pre-commit run clang-format --files test/test_climate_fault_soak/test_main.cpp || true
    .venv/bin/pre-commit run clang-format --files test/test_climate_fault_soak/test_main.cpp
    git diff --check
    test -z "$(git diff --name-only "$EXPECTED" -- src lib/environment_control)"
    ! grep -F 'RequiredSensorUnusable) != 0U' test/test_climate_fault_soak/test_main.cpp
    ! grep -F 'UnavailableHeater) != 0U' test/test_climate_fault_soak/test_main.cpp
    ! grep -F 'UnavailableCo2Doser) != 0U' test/test_climate_fault_soak/test_main.cpp
    git status --short
    ;;

  focused)
    load_original
    bash /tmp/stage25e-original.sh focused
    ;;

  full)
    test -n "$EXPECTED"
    load_original
    bash /tmp/stage25e-original.sh full "$EXPECTED"
    ;;

  *)
    echo "Unknown mode: $MODE" >&2
    exit 2
    ;;
esac
