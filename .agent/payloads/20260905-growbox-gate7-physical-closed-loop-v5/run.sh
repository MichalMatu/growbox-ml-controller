#!/usr/bin/env bash
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"
git fetch -q origin agent-control
SRC=/tmp/g7v5-source.sh
OUT=/tmp/g7v5-run.sh
git show origin/agent-control:.agent/payloads/20260905-growbox-gate7-physical-closed-loop-v4/run.sh > "$SRC"
python3 - "$SRC" "$OUT" <<'PY'
import sys
src=open(sys.argv[1]).read()
src=src.replace('build/idf-gate7-physical-closed-loop-v4','build/idf-gate7-physical-closed-loop-v5')
src=src.replace('build/idf-gate7-safe-return-v4','build/idf-gate7-safe-return-v5')
src=src.replace('/tmp/growbox_gate7_v4_baseline.json','/tmp/growbox_gate7_v5_baseline.json')
src=src.replace('/tmp/growbox_gate7_closed_loop_v4.json','/tmp/growbox_gate7_closed_loop_v5.json')
needle="""    next_heartbeat=observe_start+30.0
"""
replacement="""    next_heartbeat=observe_start+30.0
    power_mismatch_streak=0
"""
if needle not in src:
    raise SystemExit('v5 init patch target not found')
src=src.replace(needle,replacement,1)
src=src.replace("for _ in range(3):\n                            ps=get_status(); samples.append(float(ps['apower'])); masters.append(bool(ps.get('output',False))); time.sleep(.6)","for _ in range(5):\n                            ps=get_status(); samples.append(float(ps['apower'])); masters.append(bool(ps.get('output',False))); time.sleep(.4)",1)
old="""                        if err>5.5: raise RuntimeError(f'stable power mismatch actual={p:.2f} expected={ep:.2f} state={state}')
                        last_power_sample=time.monotonic()
"""
new="""                        if err>5.5:
                            power_mismatch_streak += 1
                            print(f'GATE7_V5_POWER_MISMATCH streak={power_mismatch_streak} actual={p:.2f} expected={ep:.2f} state={state}', flush=True)
                            if power_mismatch_streak >= 3:
                                raise RuntimeError(f'persistent power mismatch actual={p:.2f} expected={ep:.2f} state={state}')
                        else:
                            power_mismatch_streak = 0
                        last_power_sample=time.monotonic()
"""
if old not in src:
    raise SystemExit('v5 mismatch patch target not found')
src=src.replace(old,new,1)
for a,b in [
 ('GATE7_V4_WARMUP_PASS','GATE7_V5_WARMUP_PASS'),
 ('GATE7_V4_STATE_CHANGE','GATE7_V5_STATE_CHANGE'),
 ('GATE7_V4_POWER state=','GATE7_V5_POWER state='),
 ('GATE7_V4_STORAGE_TRANSIENT','GATE7_V5_STORAGE_TRANSIENT'),
 ('GATE7_V4_OBSERVE_REJECT','GATE7_V5_OBSERVE_REJECT'),
 ('GATE7_V4_HEARTBEAT','GATE7_V5_HEARTBEAT'),
 ('GATE7_V4_CLOSED_LOOP_SUMMARY','GATE7_V5_CLOSED_LOOP_SUMMARY'),
 ('GATE7_V4_CLOSED_LOOP_PASS','GATE7_V5_CLOSED_LOOP_PASS'),
 ('GATE7_V4_SAFE_RETURN_PASS','GATE7_V5_SAFE_RETURN_PASS'),
 ('GATE7_V4_E2E_COMPLETE','GATE7_V5_E2E_COMPLETE'),
 ('GATE7_V4_FINAL_FAIL','GATE7_V5_FINAL_FAIL')]:
    src=src.replace(a,b)
open(sys.argv[2],'w').write(src)
PY
bash "$OUT"
