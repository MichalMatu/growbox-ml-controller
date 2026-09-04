#!/usr/bin/env bash
set -euo pipefail

# Reuse the already-proven scanner TX harness, only changing:
# - macOS-compatible lowercasing
# - RF repeat from 3 to 10
# - ON/OFF cycle count from 1 to 3

git fetch -q origin agent-control
git show origin/agent-control:.agent/payloads/20260904-growbox-stage28c-scanner-tx-onoff-v1/run.sh |
python3 -c 'import sys
s=sys.stdin.read()
s=s.replace("  local build_dir=\"build/idf-stage28c-scanner-tx-${label,,}-v1\"\n  local out=\"/tmp/stage28c-scanner-tx-${label,,}-v1\"", "  local lower_label\n  lower_label=\"$(printf %s \\\"$label\\\" | tr \\\"[:upper:]\\\" \\\"[:lower:]\\\")\"\n  local build_dir=\"build/idf-stage28c-scanner-tx-${lower_label}-repeat10-v1\"\n  local out=\"/tmp/stage28c-scanner-tx-${lower_label}-repeat10-v1\"")
s=s.replace("}, 3U, 575U};", "}, 10U, 575U};")
s=s.replace("repeat=3", "repeat=10")
s=s.replace("requested_repeat\x27], 0) == 3", "requested_repeat\x27], 0) == 10")
s=s.replace("run_one ON 906118656\nrun_one OFF 1040336384", "for cycle in 1 2 3; do\n  echo STAGE28C_SCANNER_TX_CYCLE=$cycle\n  run_one ON 906118656\n  sleep 2\n  run_one OFF 1040336384\n  sleep 2\ndone")
s=s.replace("STAGE28C_SCANNER_TX_ONOFF_DONE", "STAGE28C_SCANNER_TX_ONOFF_REPEAT10X3_DONE")
sys.stdout.write(s)' > /tmp/stage28c-scanner-tx-onoff-repeat10x3-v1.sh

bash /tmp/stage28c-scanner-tx-onoff-repeat10x3-v1.sh
