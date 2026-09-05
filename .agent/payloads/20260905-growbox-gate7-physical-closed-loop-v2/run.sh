#!/usr/bin/env bash
set -euo pipefail

EXPECTED=3dfc4b552f669f628d5c9bee455a34666915088c
BRANCH=mvp/environment-controller
ACTIVE_BUILD=build/idf-gate7-physical-closed-loop-v2
SAFE_BUILD=build/idf-gate7-safe-return-v2
ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

heartbeat() {
  while true; do
    echo "GATE7_V2_HEARTBEAT epoch=$(date +%s)"
    sleep 30
  done
}
heartbeat &
HB_PID=$!
cleanup_heartbeat() {
  kill "$HB_PID" >/dev/null 2>&1 || true
  wait "$HB_PID" >/dev/null 2>&1 || true
}
trap cleanup_heartbeat EXIT INT TERM

git fetch -q origin "$BRANCH"
git reset --hard "$EXPECTED" >/dev/null
test "$(git rev-parse HEAD)" = "$EXPECTED"
test "$(git rev-parse origin/$BRANCH)" = "$EXPECTED"
test -z "$(git status --porcelain)"
export CMAKE_BUILD_PARALLEL_LEVEL=1

GROWBOX_RF433_LOOPBACK_ENABLED=1 \
GROWBOX_STAGE28_REAL_OUTPUTS_ENABLED=1 \
GROWBOX_STAGE28_THERMAL_TEST_SEQUENCE_ENABLED=0 \
GROWBOX_FIRMWARE_GIT_SHA="$EXPECTED" \
STAGE27C_BUILD_DIR="$ACTIVE_BUILD" \
bash scripts/stage27c_crowpanel.sh build

grep -q '^GROWBOX_STAGE28_REAL_OUTPUTS_ENABLED:STRING=1$' "$ACTIVE_BUILD/CMakeCache.txt"
grep -q '^GROWBOX_STAGE28_THERMAL_TEST_SEQUENCE_ENABLED:STRING=0$' "$ACTIVE_BUILD/CMakeCache.txt"
grep -q '^GROWBOX_RF433_LOOPBACK_ENABLED:STRING=1$' "$ACTIVE_BUILD/CMakeCache.txt"

GROWBOX_RF433_LOOPBACK_ENABLED=1 \
GROWBOX_STAGE28_REAL_OUTPUTS_ENABLED=0 \
GROWBOX_STAGE28_THERMAL_TEST_SEQUENCE_ENABLED=0 \
GROWBOX_FIRMWARE_GIT_SHA="$EXPECTED" \
STAGE27C_BUILD_DIR="$SAFE_BUILD" \
bash scripts/stage27c_crowpanel.sh build

grep -q '^GROWBOX_STAGE28_REAL_OUTPUTS_ENABLED:STRING=0$' "$SAFE_BUILD/CMakeCache.txt"
grep -q '^GROWBOX_STAGE28_THERMAL_TEST_SEQUENCE_ENABLED:STRING=0$' "$SAFE_BUILD/CMakeCache.txt"

PY="$ROOT/.venv/bin/python"
if [[ ! -x "$PY" ]]; then PY="$(command -v python3)"; fi

# Preflight from the installed fake-locked image. Restore Shelly master only long
# enough to prove all controlled RF loads are OFF and establish a baseline.
"$PY" <<'PY'
import json, statistics, time, urllib.request
import serial
from tools.stage27c_soak import detect_ch340_port
SHELLY='http://192.168.0.16'

def get_status():
    with urllib.request.urlopen(SHELLY+'/rpc/Switch.GetStatus?id=0',timeout=5) as r:
        return json.loads(r.read().decode())
def rpc(method,params):
    body=json.dumps({'id':1,'method':method,'params':params}).encode()
    req=urllib.request.Request(SHELLY+'/rpc',data=body,headers={'Content-Type':'application/json'},method='POST')
    with urllib.request.urlopen(req,timeout=5) as r: return json.loads(r.read().decode())
def set_master(on):
    rpc('Switch.Set',{'id':0,'on':bool(on),'tag':'growbox-gate7-v2-preflight'}); time.sleep(1)
def collect(h,d):
    end=time.monotonic()+d; parts=[]
    while time.monotonic()<end:
        b=h.read(4096)
        if b: parts.append(b)
    return b''.join(parts).decode(errors='replace')
def send(h,cmd):
    h.write(cmd.encode()+b'\n'); h.flush(); return collect(h,2.5)
def median_power(n=9):
    vals=[]
    for _ in range(n): vals.append(float(get_status()['apower'])); time.sleep(.4)
    return statistics.median(vals)

if not bool(get_status().get('output',False)):
    set_master(True)
port=detect_ch340_port()
if not port:
    set_master(False); raise SystemExit('Gate7 v2 preflight: serial missing; master cutoff applied')
with serial.Serial(port,115200,timeout=.12,write_timeout=1) as h:
    try: h.dtr=False; h.rts=False
    except Exception: pass
    time.sleep(1); h.reset_input_buffer()
    status=''
    for _ in range(5):
        status += send(h,'status')
        if 'outputs=fake-locked' in status and 'rf_ready=1' in status: break
    if 'outputs=fake-locked' not in status or 'rf_ready=1' not in status:
        set_master(False); raise SystemExit('Gate7 v2 preflight: installed image not fake-locked/rf-ready')
    for cmd in ('rf lamp off','rf fan off','rf humidifier off'):
        send(h,cmd)
time.sleep(20)
p=median_power()
if p > 8.0:
    set_master(False); raise SystemExit(f'Gate7 v2 preflight unsafe baseline {p:.3f}W; master cutoff applied')
open('/tmp/growbox_gate7_v2_baseline.json','w').write(json.dumps({'power_w':p}))
print(f'GATE7_V2_PREFLIGHT_PASS baseline_w={p:.3f} master=on')
PY

GROWBOX_RF433_LOOPBACK_ENABLED=1 \
GROWBOX_STAGE28_REAL_OUTPUTS_ENABLED=1 \
GROWBOX_STAGE28_THERMAL_TEST_SEQUENCE_ENABLED=0 \
GROWBOX_FIRMWARE_GIT_SHA="$EXPECTED" \
STAGE27C_BUILD_DIR="$ACTIVE_BUILD" \
bash scripts/stage27c_crowpanel.sh flash

set +e
"$PY" - "$EXPECTED" <<'PY'
import json, re, statistics, sys, time, urllib.request
from pathlib import Path
import serial
from tools.stage27c_soak import detect_ch340_port

EXPECTED=sys.argv[1]
SHELLY='http://192.168.0.16'
WARMUP_S=90.0
OBSERVE_S=600.0
BASELINE=float(json.loads(Path('/tmp/growbox_gate7_v2_baseline.json').read_text())['power_w'])
LOAD={'lamp':97.0,'fan':2.9,'humidifier':15.75}

def get_status():
    with urllib.request.urlopen(SHELLY+'/rpc/Switch.GetStatus?id=0',timeout=5) as r:
        return json.loads(r.read().decode())
def rpc(method,params):
    body=json.dumps({'id':1,'method':method,'params':params}).encode()
    req=urllib.request.Request(SHELLY+'/rpc',data=body,headers={'Content-Type':'application/json'},method='POST')
    with urllib.request.urlopen(req,timeout=5) as r: return json.loads(r.read().decode())
def cutoff():
    try: rpc('Switch.Set',{'id':0,'on':False,'tag':'growbox-gate7-v2-monitor-fallback'})
    except Exception: pass

def expected_power(lamp,fan,hum):
    return BASELINE + LOAD['lamp']*lamp + LOAD['fan']*fan + LOAD['humidifier']*hum

port=detect_ch340_port()
if not port:
    cutoff(); raise SystemExit('Gate7 v2 monitor serial missing; master cutoff applied')

out_re=re.compile(
 r'stage28d_output real=(?P<real>[01]) lamp_known=(?P<lk>[01]) lamp_on=(?P<lamp>[01]) '
 r'fan_known=(?P<fk>[01]) fan_on=(?P<fan>[01]) humidifier_known=(?P<hk>[01]) humidifier_on=(?P<hum>[01]) '
 r'safety_latched=(?P<latched>[01]) force_fan=(?P<force>[01]) safety_reason=(?P<reason>\d+) '
 r'requested_fan=(?P<rf>[0-9.]+) requested_humidifier=(?P<rh>[0-9.]+) '
 r'applied_fan=(?P<af>[0-9.]+) applied_humidifier=(?P<ah>[0-9.]+) '
 r'arbiter_transitions=(?P<tr>\d+) arbiter_dwell_holds=(?P<dh>\d+) arbiter_safety_overrides=(?P<so>\d+) '
 r'tx=(?P<tx>\d+) tx_errors=(?P<te>\d+)')
soak_re=re.compile(
 r'soak_v=2 firmware_sha=(?P<sha>[0-9a-f]+).*?tp_sample=(?P<tp>[01]) tp_t=(?P<t>-?[0-9.]+) tp_rh=(?P<tprh>-?[0-9.]+).*?'
 r'storage_backend=(?P<st>[a-z-]+).*?storage_write_errors=(?P<we>\d+).*?storage_queue_drops=(?P<qd>\d+).*?outputs=(?P<mode>[a-z-]+)')

records=[]; soak=[]; power=[]; rejected=[]; event_logs=[]
start=time.monotonic(); buf=''; last_serial=start; stable_sd=0; startup_real=False; warm_ready=False

with serial.Serial(port,115200,timeout=.08,write_timeout=1) as h:
    try: h.dtr=False; h.rts=False
    except Exception: pass
    time.sleep(1); h.reset_input_buffer()
    h.write(b'status\n'); h.flush()

    warm_deadline=time.monotonic()+WARMUP_S
    while time.monotonic()<warm_deadline and not warm_ready:
        chunk=h.read(4096)
        if chunk:
            last_serial=time.monotonic(); buf += chunk.decode(errors='replace')
            while '\n' in buf:
                line,buf=buf.split('\n',1); line=line.strip()
                if not line: continue
                if EXPECTED in line and 'outputs=real-bounded' in line:
                    startup_real=True
                if 'Real-output initialization failed' in line:
                    cutoff(); raise RuntimeError('real-output initialization failed during warm-up')
                s=soak_re.search(line)
                if s:
                    q={'sha':s.group('sha'),'storage':s.group('st'),'we':int(s.group('we')),'qd':int(s.group('qd')),'mode':s.group('mode')}
                    ok=(q['sha']==EXPECTED and q['storage']=='sd' and q['we']==0 and q['qd']==0 and q['mode']=='real-bounded')
                    if ok:
                        stable_sd += 1
                    else:
                        stable_sd = 0
                        rejected.append(q)
                        print('GATE7_V2_WARMUP_REJECT '+json.dumps(q,sort_keys=True,separators=(',',':')))
                    if startup_real and stable_sd >= 3:
                        warm_ready=True
                        break
        if time.monotonic()-last_serial>45:
            cutoff(); raise RuntimeError('serial silent >45s during warm-up')

    if not warm_ready:
        cutoff(); raise RuntimeError('warm-up never reached exact-SHA real-bounded + 3 consecutive healthy SD records')
    print(f'GATE7_V2_WARMUP_PASS stable_sd_records={stable_sd} rejected={len(rejected)}')

    observe_start=time.monotonic(); deadline=observe_start+OBSERVE_S
    last_power_sample=0.0
    while time.monotonic()<deadline:
        chunk=h.read(4096)
        if chunk:
            last_serial=time.monotonic(); buf += chunk.decode(errors='replace')
            while '\n' in buf:
                line,buf=buf.split('\n',1); line=line.strip()
                if not line: continue
                if 'Real-output initialization failed' in line or 'outputs=fake-locked' in line and 'status firmware_sha=' in line:
                    cutoff(); raise RuntimeError('real output mode lost')
                m=out_re.search(line)
                if m:
                    r={k:int(m.group(k)) for k in ('real','lk','lamp','fk','fan','hk','hum','latched','force','reason','tr','dh','so','tx','te')}
                    r.update({k:float(m.group(k)) for k in ('rf','rh','af','ah')})
                    r['t']=time.monotonic()-observe_start
                    if r['real']!=1 or r['te']!=0: raise RuntimeError('real mode lost or RF TX error')
                    if r['lk']!=1 or r['fk']!=1 or r['hk']!=1: raise RuntimeError('endpoint state became unknown')
                    if r['af'] not in (0.0,1.0) or r['ah'] not in (0.0,1.0): raise RuntimeError('applied state not binary')
                    if int(r['af'])!=r['fan'] or int(r['ah'])!=r['hum']: raise RuntimeError('applied state disagrees with RF endpoint')
                    records.append(r)
                    if time.monotonic()-last_power_sample >= 5.0:
                        s=get_status(); p=float(s['apower']); master=bool(s.get('output',False))
                        if not master: raise RuntimeError('Shelly master unexpectedly OFF')
                        ep=expected_power(r['lamp'],r['fan'],r['hum']); err=abs(p-ep)
                        power.append({'t':r['t'],'p':p,'expected':ep,'error':err,'lamp':r['lamp'],'fan':r['fan'],'hum':r['hum']})
                        if p>130.0: raise RuntimeError(f'unsafe power {p:.2f}W')
                        if err>5.5: raise RuntimeError(f'power mismatch actual={p:.2f} expected={ep:.2f}')
                        last_power_sample=time.monotonic()
                s=soak_re.search(line)
                if s:
                    q={'t':time.monotonic()-observe_start,'sha':s.group('sha'),'tp':int(s.group('tp')),'temp':float(s.group('t')),'rh':float(s.group('tprh')),'storage':s.group('st'),'we':int(s.group('we')),'qd':int(s.group('qd')),'mode':s.group('mode')}
                    if q['sha']!=EXPECTED or q['storage']!='sd' or q['we']!=0 or q['qd']!=0 or q['mode']!='real-bounded':
                        print('GATE7_V2_OBSERVE_REJECT '+json.dumps(q,sort_keys=True,separators=(',',':')))
                        raise RuntimeError('telemetry/storage/mode gate failed after warm-up')
                    if q['tp'] and q['temp']>=31.0: raise RuntimeError(f'authoritative temperature unsafe {q["temp"]:.2f}C')
                    soak.append(q)
                if 'output fault' in line.lower() or 'apply failed' in line.lower():
                    event_logs.append(line)
        if time.monotonic()-last_serial>45:
            raise RuntimeError('serial telemetry silent >45s during observation')

if len(records)<35: raise RuntimeError(f'insufficient output records={len(records)}')
if len(soak)<35: raise RuntimeError(f'insufficient SD soak records={len(soak)}')
if not power: raise RuntimeError('no Shelly correlation samples')
max_power_error=max(x['error'] for x in power)
summary={
 'sha':EXPECTED,'duration_s':OBSERVE_S,'records':len(records),'soak_records':len(soak),
 'lamp_on_records':sum(r['lamp'] for r in records),'fan_on_records':sum(r['fan'] for r in records),
 'humidifier_on_records':sum(r['hum'] for r in records),'max_requested_fan':max(r['rf'] for r in records),
 'max_requested_humidifier':max(r['rh'] for r in records),'arbiter_transitions':max(r['tr'] for r in records),
 'arbiter_dwell_holds':max(r['dh'] for r in records),'arbiter_safety_overrides':max(r['so'] for r in records),
 'max_power_error_w':max_power_error,'min_tp357_c':min((q['temp'] for q in soak if q['tp']),default=None),
 'max_tp357_c':max((q['temp'] for q in soak if q['tp']),default=None),'warmup_rejected':rejected[-20:],'logs':event_logs[-20:]}
Path('/tmp/growbox_gate7_closed_loop_v2.json').write_text(json.dumps(summary,indent=2,sort_keys=True))
print('GATE7_V2_CLOSED_LOOP_SUMMARY '+json.dumps(summary,sort_keys=True,separators=(',',':')))
print(f'GATE7_V2_CLOSED_LOOP_PASS sha={EXPECTED} records={len(records)} fan_on={summary["fan_on_records"]} hum_on={summary["humidifier_on_records"]} dwell={summary["arbiter_dwell_holds"]} transitions={summary["arbiter_transitions"]} max_power_error_w={max_power_error:.2f}')
PY
TEST_RC=$?
set -e

# Always return to exact-SHA fake-locked firmware.
GROWBOX_RF433_LOOPBACK_ENABLED=1 \
GROWBOX_STAGE28_REAL_OUTPUTS_ENABLED=0 \
GROWBOX_STAGE28_THERMAL_TEST_SEQUENCE_ENABLED=0 \
GROWBOX_FIRMWARE_GIT_SHA="$EXPECTED" \
STAGE27C_BUILD_DIR="$SAFE_BUILD" \
bash scripts/stage27c_crowpanel.sh flash

set +e
"$PY" - "$EXPECTED" "$TEST_RC" <<'PY'
import json, statistics, sys, time, urllib.request
import serial
from tools.stage27c_soak import detect_ch340_port
EXPECTED=sys.argv[1]; TEST_RC=int(sys.argv[2]); SHELLY='http://192.168.0.16'
def get_status():
    with urllib.request.urlopen(SHELLY+'/rpc/Switch.GetStatus?id=0',timeout=5) as r: return json.loads(r.read().decode())
def rpc(method,params):
    body=json.dumps({'id':1,'method':method,'params':params}).encode(); req=urllib.request.Request(SHELLY+'/rpc',data=body,headers={'Content-Type':'application/json'},method='POST')
    with urllib.request.urlopen(req,timeout=5) as r: return json.loads(r.read().decode())
def cutoff():
    try: rpc('Switch.Set',{'id':0,'on':False,'tag':'growbox-gate7-v2-safe-return-fallback'})
    except Exception: pass
def collect(h,d):
    end=time.monotonic()+d; parts=[]
    while time.monotonic()<end:
        b=h.read(4096)
        if b: parts.append(b)
    return b''.join(parts).decode(errors='replace')
def send(h,cmd):
    h.write(cmd.encode()+b'\n'); h.flush(); return collect(h,2.5)

port=detect_ch340_port()
if not port:
    cutoff(); raise SystemExit('Gate7 v2 safe-return serial missing; master cutoff applied')
time.sleep(2)
with serial.Serial(port,115200,timeout=.12,write_timeout=1) as h:
    try: h.dtr=False; h.rts=False
    except Exception: pass
    status=''
    for _ in range(6):
        status += send(h,'status')
        if f'status firmware_sha={EXPECTED}' in status and 'outputs=fake-locked' in status and 'rf_ready=1' in status: break
    if f'status firmware_sha={EXPECTED}' not in status or 'outputs=fake-locked' not in status or 'rf_ready=1' not in status:
        cutoff(); raise SystemExit('Gate7 v2 safe-return exact-SHA/fake-lock smoke failed')
    for cmd in ('rf lamp off','rf fan off','rf humidifier off'):
        send(h,cmd)
time.sleep(20)
if not bool(get_status().get('output',False)):
    rpc('Switch.Set',{'id':0,'on':True,'tag':'growbox-gate7-v2-safe-return-restore'}); time.sleep(1)
vals=[]
for _ in range(9): vals.append(float(get_status()['apower'])); time.sleep(.4)
p=statistics.median(vals)
if p>8.0:
    cutoff(); raise SystemExit(f'Gate7 v2 safe-return high power {p:.3f}W; master cutoff applied')
if TEST_RC!=0:
    cutoff(); raise SystemExit(f'Gate7 v2 closed-loop failed; safe firmware/RF OFF confirmed at {p:.3f}W; master cutoff applied')
print(f'GATE7_V2_SAFE_RETURN_PASS sha={EXPECTED} outputs=fake-locked power_w={p:.3f} master=on')
PY
SAFE_RC=$?
set -e

cleanup_heartbeat
trap - EXIT INT TERM

if [[ "$TEST_RC" -ne 0 || "$SAFE_RC" -ne 0 ]]; then
  echo "GATE7_V2_FINAL_FAIL test_rc=$TEST_RC safe_rc=$SAFE_RC"
  exit 1
fi

test -z "$(git status --porcelain)"
echo "GATE7_V2_E2E_COMPLETE sha=$EXPECTED closed_loop=pass safe_return=pass final=all_off master=on"
