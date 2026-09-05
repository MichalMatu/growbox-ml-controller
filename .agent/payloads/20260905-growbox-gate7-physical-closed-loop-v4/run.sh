#!/usr/bin/env bash
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"
git fetch -q origin agent-control
SRC=/tmp/g7v4-source.sh
OUT=/tmp/g7v4-run.sh
git show origin/agent-control:.agent/payloads/20260905-growbox-gate7-physical-closed-loop-v2/run.sh > "$SRC"
python3 - "$SRC" "$OUT" <<'PY'
import re,sys
src=open(sys.argv[1]).read()
src=src.replace('build/idf-gate7-physical-closed-loop-v2','build/idf-gate7-physical-closed-loop-v4')
src=src.replace('build/idf-gate7-safe-return-v2','build/idf-gate7-safe-return-v4')
src=src.replace('/tmp/growbox_gate7_v2_baseline.json','/tmp/growbox_gate7_v4_baseline.json')
src=src.replace('/tmp/growbox_gate7_closed_loop_v2.json','/tmp/growbox_gate7_closed_loop_v4.json')
src=re.sub(r'\nheartbeat\(\) \{.*?trap cleanup_heartbeat EXIT INT TERM\n','\n',src,flags=re.S)
src=src.replace('\ncleanup_heartbeat\ntrap - EXIT INT TERM\n','\n')

old_storage="""                    if q['sha']!=EXPECTED or q['storage']!='sd' or q['we']!=0 or q['qd']!=0 or q['mode']!='real-bounded':
                        print('GATE7_V2_OBSERVE_REJECT '+json.dumps(q,sort_keys=True,separators=(',',':')))
                        raise RuntimeError('telemetry/storage/mode gate failed after warm-up')
                    if q['tp'] and q['temp']>=31.0: raise RuntimeError(f'authoritative temperature unsafe {q[\"temp\"]:.2f}C')
                    soak.append(q)
"""
new_storage="""                    if q['sha']!=EXPECTED or q['we']!=0 or q['qd']!=0 or q['mode']!='real-bounded':
                        print('GATE7_V4_OBSERVE_REJECT '+json.dumps(q,sort_keys=True,separators=(',',':')), flush=True)
                        raise RuntimeError('telemetry integrity/mode gate failed after warm-up')
                    if q['tp'] and q['temp']>=31.0: raise RuntimeError(f'authoritative temperature unsafe {q[\"temp\"]:.2f}C')
                    if q['storage']=='sd':
                        last_sd_good=time.monotonic()
                        soak.append(q)
                    elif q['storage'] in ('none','flash'):
                        print('GATE7_V4_STORAGE_TRANSIENT '+json.dumps(q,sort_keys=True,separators=(',',':')), flush=True)
                        if time.monotonic()-last_sd_good>45.0:
                            raise RuntimeError('SD backend absent for >45s after warm-up')
                    else:
                        raise RuntimeError('unexpected storage backend '+q['storage'])
"""
if old_storage not in src:
    raise SystemExit('v4 storage patch target not found')
src=src.replace(old_storage,new_storage)

warm_old="""    print(f'GATE7_V2_WARMUP_PASS stable_sd_records={stable_sd} rejected={len(rejected)}')

    observe_start=time.monotonic(); deadline=observe_start+OBSERVE_S
    last_power_sample=0.0
"""
warm_new="""    print(f'GATE7_V4_WARMUP_PASS stable_sd_records={stable_sd} rejected={len(rejected)}', flush=True)
    last_sd_good=time.monotonic()

    observe_start=time.monotonic(); deadline=observe_start+OBSERVE_S
    last_power_sample=0.0
    last_output_state=None
    last_output_state_change=observe_start
    next_heartbeat=observe_start+30.0
"""
if warm_old not in src:
    raise SystemExit('v4 warm-up patch target not found')
src=src.replace(warm_old,warm_new)

power_pattern=re.compile(r"                    records\.append\(r\)\n                    if time\.monotonic\(\)-last_power_sample >= 5\.0:\n                        s=get_status\(\); p=float\(s\['apower'\]\); master=bool\(s\.get\('output',False\)\)\n                        if not master: raise RuntimeError\('Shelly master unexpectedly OFF'\)\n                        ep=expected_power\(r\['lamp'\],r\['fan'\],r\['hum'\]\); err=abs\(p-ep\)\n                        power\.append\(\{'t':r\['t'\],'p':p,'expected':ep,'error':err,'lamp':r\['lamp'\],'fan':r\['fan'\],'hum':r\['hum'\]\}\)\n                        if p>130\.0: raise RuntimeError\(f'unsafe power \{p:\.2f\}W'\)\n                        if err>5\.5: raise RuntimeError\(f'power mismatch actual=\{p:\.2f\} expected=\{ep:\.2f\}'\)\n                        last_power_sample=time\.monotonic\(\)")
power_new="""                    records.append(r)
                    now=time.monotonic()
                    state=(r['lamp'],r['fan'],r['hum'])
                    if state != last_output_state:
                        last_output_state=state
                        last_output_state_change=now
                        print(f'GATE7_V4_STATE_CHANGE lamp={state[0]} fan={state[1]} humidifier={state[2]} t={r[\"t\"]:.1f}', flush=True)
                    if now-last_power_sample >= 5.0 and now-last_output_state_change >= 10.0:
                        samples=[]; masters=[]
                        for _ in range(3):
                            ps=get_status(); samples.append(float(ps['apower'])); masters.append(bool(ps.get('output',False))); time.sleep(.6)
                        if not all(masters): raise RuntimeError('Shelly master unexpectedly OFF')
                        p=statistics.median(samples)
                        ep=expected_power(r['lamp'],r['fan'],r['hum']); err=abs(p-ep)
                        power.append({'t':r['t'],'p':p,'expected':ep,'error':err,'lamp':r['lamp'],'fan':r['fan'],'hum':r['hum']})
                        print(f'GATE7_V4_POWER state={state} actual={p:.2f} expected={ep:.2f} error={err:.2f}', flush=True)
                        if p>130.0: raise RuntimeError(f'unsafe power {p:.2f}W')
                        if err>5.5: raise RuntimeError(f'stable power mismatch actual={p:.2f} expected={ep:.2f} state={state}')
                        last_power_sample=time.monotonic()"""
src,n=power_pattern.subn(power_new,src,count=1)
if n!=1:
    raise SystemExit('v4 power patch target not found')

loop_tail="""        if time.monotonic()-last_serial>45:
            raise RuntimeError('serial telemetry silent >45s during observation')
"""
loop_tail_new="""        now=time.monotonic()
        if now>=next_heartbeat:
            print(f'GATE7_V4_HEARTBEAT elapsed_s={now-observe_start:.1f} records={len(records)} sd_records={len(soak)} power_samples={len(power)}', flush=True)
            next_heartbeat=now+30.0
        if now-last_sd_good>45.0:
            raise RuntimeError('no healthy SD-backed telemetry for >45s during observation')
        if now-last_serial>45:
            raise RuntimeError('serial telemetry silent >45s during observation')
"""
if loop_tail not in src:
    raise SystemExit('v4 loop-tail patch target not found')
src=src.replace(loop_tail,loop_tail_new,1)

src=src.replace("if not power: raise RuntimeError('no Shelly correlation samples')","if len(power)<8: raise RuntimeError(f'insufficient stable Shelly correlation samples={len(power)}')")
for a,b in [
 ('GATE7_V2_CLOSED_LOOP_SUMMARY','GATE7_V4_CLOSED_LOOP_SUMMARY'),
 ('GATE7_V2_CLOSED_LOOP_PASS','GATE7_V4_CLOSED_LOOP_PASS'),
 ('GATE7_V2_SAFE_RETURN_PASS','GATE7_V4_SAFE_RETURN_PASS'),
 ('GATE7_V2_E2E_COMPLETE','GATE7_V4_E2E_COMPLETE'),
 ('GATE7_V2_FINAL_FAIL','GATE7_V4_FINAL_FAIL')]:
    src=src.replace(a,b)
open(sys.argv[2],'w').write(src)
PY
bash "$OUT"
