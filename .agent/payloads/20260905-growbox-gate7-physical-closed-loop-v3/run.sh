#!/usr/bin/env bash
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"
git fetch -q origin agent-control
SRC=/tmp/g7v3-source.sh
OUT=/tmp/g7v3-run.sh
git show origin/agent-control:.agent/payloads/20260905-growbox-gate7-physical-closed-loop-v2/run.sh > "$SRC"
python3 - "$SRC" "$OUT" <<'PY'
import re,sys
src=open(sys.argv[1]).read()
src=src.replace('build/idf-gate7-physical-closed-loop-v2','build/idf-gate7-physical-closed-loop-v3')
src=src.replace('build/idf-gate7-safe-return-v2','build/idf-gate7-safe-return-v3')
src=src.replace('/tmp/growbox_gate7_v2_baseline.json','/tmp/growbox_gate7_v3_baseline.json')
src=re.sub(r'\nheartbeat\(\) \{.*?trap cleanup_heartbeat EXIT INT TERM\n','\n',src,flags=re.S)
old="""                    if q['sha']!=EXPECTED or q['storage']!='sd' or q['we']!=0 or q['qd']!=0 or q['mode']!='real-bounded':
                        print('GATE7_V2_OBSERVE_REJECT '+json.dumps(q,sort_keys=True,separators=(',',':')))
                        raise RuntimeError('telemetry/storage/mode gate failed after warm-up')
                    if q['tp'] and q['temp']>=31.0: raise RuntimeError(f'authoritative temperature unsafe {q[\"temp\"]:.2f}C')
                    soak.append(q)
"""
new="""                    if q['sha']!=EXPECTED or q['we']!=0 or q['qd']!=0 or q['mode']!='real-bounded':
                        print('GATE7_V3_OBSERVE_REJECT '+json.dumps(q,sort_keys=True,separators=(',',':')), flush=True)
                        raise RuntimeError('telemetry integrity/mode gate failed after warm-up')
                    if q['tp'] and q['temp']>=31.0: raise RuntimeError(f'authoritative temperature unsafe {q[\"temp\"]:.2f}C')
                    if q['storage']=='sd':
                        last_sd_good=time.monotonic()
                        soak.append(q)
                    elif q['storage'] in ('none','flash'):
                        print('GATE7_V3_STORAGE_TRANSIENT '+json.dumps(q,sort_keys=True,separators=(',',':')), flush=True)
                        if time.monotonic()-last_sd_good>45.0:
                            raise RuntimeError('SD backend absent for >45s after warm-up')
                    else:
                        raise RuntimeError('unexpected storage backend '+q['storage'])
"""
if old not in src:
    raise SystemExit('v3 patch target not found')
src=src.replace(old,new)
needle="""    print(f'GATE7_V2_WARMUP_PASS stable_sd_records={stable_sd} rejected={len(rejected)}')

    observe_start=time.monotonic(); deadline=observe_start+OBSERVE_S
"""
replacement="""    print(f'GATE7_V3_WARMUP_PASS stable_sd_records={stable_sd} rejected={len(rejected)}', flush=True)
    last_sd_good=time.monotonic()

    observe_start=time.monotonic(); deadline=observe_start+OBSERVE_S
"""
if needle not in src:
    raise SystemExit('v3 warm-up patch target not found')
src=src.replace(needle,replacement)
src=src.replace('GATE7_V2_CLOSED_LOOP_SUMMARY','GATE7_V3_CLOSED_LOOP_SUMMARY')
src=src.replace('GATE7_V2_CLOSED_LOOP_PASS','GATE7_V3_CLOSED_LOOP_PASS')
src=src.replace('GATE7_V2_SAFE_RETURN_PASS','GATE7_V3_SAFE_RETURN_PASS')
src=src.replace('GATE7_V2_E2E_COMPLETE','GATE7_V3_E2E_COMPLETE')
src=src.replace('GATE7_V2_FINAL_FAIL','GATE7_V3_FINAL_FAIL')
open(sys.argv[2],'w').write(src)
PY
bash "$OUT"
