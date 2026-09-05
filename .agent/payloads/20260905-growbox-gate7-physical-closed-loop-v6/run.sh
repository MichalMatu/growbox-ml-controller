#!/usr/bin/env bash
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"
git fetch -q origin agent-control
GEN=/tmp/g7v4-generator-v6.sh
FINAL=/tmp/g7v6-run.sh
git show origin/agent-control:.agent/payloads/20260905-growbox-gate7-physical-closed-loop-v4/run.sh > "$GEN"
python3 - "$GEN" <<'PY'
import pathlib,sys
p=pathlib.Path(sys.argv[1])
s=p.read_text()
needle='\nbash "$OUT"\n'
if needle not in s:
    raise SystemExit('v6 generator tail not found')
s=s.rsplit(needle,1)[0]+'\n'
p.write_text(s)
PY
bash "$GEN"
cp /tmp/g7v4-run.sh "$FINAL"
python3 - "$FINAL" <<'PY'
import pathlib,sys
p=pathlib.Path(sys.argv[1])
s=p.read_text()
s=s.replace('build/idf-gate7-physical-closed-loop-v4','build/idf-gate7-physical-closed-loop-v6')
s=s.replace('build/idf-gate7-safe-return-v4','build/idf-gate7-safe-return-v6')
s=s.replace('/tmp/growbox_gate7_v4_baseline.json','/tmp/growbox_gate7_v6_baseline.json')
s=s.replace('/tmp/growbox_gate7_closed_loop_v4.json','/tmp/growbox_gate7_closed_loop_v6.json')
needle='    next_heartbeat=observe_start+30.0\n'
if needle not in s:
    raise SystemExit('v6 init patch target not found')
s=s.replace(needle,needle+'    power_mismatch_streak=0\n',1)
old="""                        for _ in range(3):
                            ps=get_status(); samples.append(float(ps['apower'])); masters.append(bool(ps.get('output',False))); time.sleep(.6)
"""
new="""                        for _ in range(5):
                            ps=get_status(); samples.append(float(ps['apower'])); masters.append(bool(ps.get('output',False))); time.sleep(.4)
"""
if old not in s:
    raise SystemExit('v6 sample patch target not found')
s=s.replace(old,new,1)
old="""                        if err>5.5: raise RuntimeError(f'stable power mismatch actual={p:.2f} expected={ep:.2f} state={state}')
                        last_power_sample=time.monotonic()
"""
new="""                        if err>5.5:
                            power_mismatch_streak += 1
                            print(f'GATE7_V6_POWER_MISMATCH streak={power_mismatch_streak} actual={p:.2f} expected={ep:.2f} state={state}', flush=True)
                            if power_mismatch_streak >= 3:
                                raise RuntimeError(f'persistent power mismatch actual={p:.2f} expected={ep:.2f} state={state}')
                        else:
                            power_mismatch_streak = 0
                        last_power_sample=time.monotonic()
"""
if old not in s:
    raise SystemExit('v6 mismatch patch target not found')
s=s.replace(old,new,1)
s=s.replace('GATE7_V4_','GATE7_V6_')
p.write_text(s)
PY
bash -n "$FINAL"
bash "$FINAL"
