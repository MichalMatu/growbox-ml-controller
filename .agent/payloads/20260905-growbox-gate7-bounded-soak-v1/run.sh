#!/usr/bin/env bash
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"
git fetch -q origin agent-control
SRC=/tmp/g7-soak-v1-source.sh
OUT=/tmp/g7-soak-v1-run.sh
git show origin/agent-control:.agent/payloads/20260905-growbox-gate7-physical-closed-loop-v6/run.sh > "$SRC"
python3 - "$SRC" "$OUT" <<'PY'
import pathlib,sys
src=pathlib.Path(sys.argv[1]).read_text()
# Reuse the already-passed v6 harness, but extend only the observation window.
# The exact firmware SHA, fail-closed power checks, SD health checks and safe-return
# behavior remain unchanged.
src=src.rsplit('\nbash "$FINAL"\n',1)[0]+'\n'
pathlib.Path('/tmp/g7-soak-v1-generator.sh').write_text(src)
PY
bash /tmp/g7-soak-v1-generator.sh
cp /tmp/g7v6-run.sh "$OUT"
python3 - "$OUT" <<'PY'
import pathlib,sys
p=pathlib.Path(sys.argv[1])
s=p.read_text()
s=s.replace('build/idf-gate7-physical-closed-loop-v6','build/idf-gate7-bounded-soak-v1')
s=s.replace('build/idf-gate7-safe-return-v6','build/idf-gate7-bounded-soak-safe-v1')
s=s.replace('/tmp/growbox_gate7_v6_baseline.json','/tmp/growbox_gate7_soak_v1_baseline.json')
s=s.replace('/tmp/growbox_gate7_closed_loop_v6.json','/tmp/growbox_gate7_soak_v1.json')
if 'OBSERVE_S=600.0' not in s:
    raise SystemExit('soak observation patch target not found')
s=s.replace('OBSERVE_S=600.0','OBSERVE_S=1800.0',1)
s=s.replace('GATE7_V6_','GATE7_SOAK_V1_')
p.write_text(s)
PY
bash -n "$OUT"
bash "$OUT"
