#!/usr/bin/env bash
set -euo pipefail

EXPECTED=3dfc4b552f669f628d5c9bee455a34666915088c
BRANCH=mvp/environment-controller
ACTIVE_BUILD=build/idf-gate7-physical-closed-loop
SAFE_BUILD=build/idf-gate7-safe-return
ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

heartbeat() {
  while true; do
    echo "GATE7_HEARTBEAT epoch=$(date +%s)"
    sleep 30
  done
}
heartbeat &
HB_PID=$!
trap 'kill "$HB_PID" >/dev/null 2>&1 || true' EXIT

git fetch -q origin "$BRANCH"
git reset --hard "$EXPECTED" >/dev/null
test "$(git rev-parse HEAD)" = "$EXPECTED"
test "$(git rev-parse origin/$BRANCH)" = "$EXPECTED"
test -z "$(git status --porcelain)"
export CMAKE_BUILD_PARALLEL_LEVEL=1

# Build both images before touching physical outputs.
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

# Preflight: master ON, all controlled loads physically OFF, stable baseline.
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
    rpc('Switch.Set',{'id':0,'on':bool(on),'tag':'growbox-gate7-preflight'}); time.sleep(1)
def collect(h,d):
    end=time.monotonic()+d; parts=[]
    while time.monotonic()<end:
        b=h.read(4096)
        if b: parts.append(b)
    return b''.join(parts).decode(errors='replace')
def send(h,cmd):
    h.write(cmd.encode()+b'\n'); h.flush(); return collect(h,2.2)
def sample():
    vals=[]
    for _ in range(9): vals.append(float(get_status()['apower'])); time.sleep(.4)
    return statistics.median(vals)

s=get_status()
if not bool(s.get('output',False)): set_master(True)
p=sample()
if p > 8.0:
    port=detect_ch340_port()
    if not port:
        set_master(False); raise SystemExit('Gate7 preflight high power and no serial port; master cutoff applied')
    with serial.Serial(port,115200,timeout=.12,write_timeout=1) as h:
        try: h.dtr=False; h.rts=False
        except Exception: pass
        time.sleep(1); h.reset_input_buffer()
        for cmd in ('rf lamp off','rf fan off','rf humidifier off'): send(h,cmd)
    time.sleep(20); p=sample()
if p > 8.0:
    set_master(False); raise SystemExit(f'Gate7 preflight unsafe baseline {p:.3f}W; master cutoff applied')
open('/tmp/growbox_gate7_baseline.json','w').write(json.dumps({'power_w':p}))
print(f'GATE7_PREFLIGHT_PASS baseline_w={p:.3f} master=on')
PY

# Flash normal real-input closed-loop: real outputs ON, deterministic thermal test OFF.
GROWBOX_RF433_LOOPBACK_ENABLED=1 \
GROWBOX_STAGE28_REAL_OUTPUTS_ENABLED=1 \
GROWBOX_STAGE28_THERMAL_TEST_SEQUENCE_ENABLED=0 \
GROWBOX_FIRMWARE_GIT_SHA="$EXPECTED" \
STAGE27C_BUILD_DIR="$ACTIVE_BUILD" \
bash scripts/stage27c_crowpanel.sh flash

set +e
"$PY" - "$EXPECTED" <<'PY'
import json, math, re, statistics, sys, time, urllib.request
from pathlib import Path
import serial
from tools.stage27c_soak import detect_ch340_port

EXPECTED=sys.argv[1]
SHELLY='http://192.168.0.16'
DURATION_S=600.0
BASELINE=float(json.loads(Path('/tmp/growbox_gate7_baseline.json').read_text())['power_w'])
LOAD={'lamp':97.0,'fan':2.9,'humidifier':15.75}

def get_status():
    with urllib.request.urlopen(SHELLY+'/rpc/Switch.GetStatus?id=0',timeout=5) as r:
        return json.loads(r.read().decode())
def rpc(method,params):
    body=json.dumps({'id':1,'method':method,'params':params}).encode()
    req=urllib.request.Request(SHELLY+'/rpc',data=body,headers={'Content-Type':'application/json'},method='POST')
    with urllib.request.urlopen(req,timeout=5) as r: return json.loads(r.read().decode())
def cutoff():
    try: rpc('Switch.Set',{'id':0,'on':False,'tag':'growbox-gate7-monitor-fallback'})
    except Exception: pass

def expected_power(lamp,fan,humidifier):
    return BASELINE + LOAD['lamp']*lamp + LOAD['fan']*fan + LOAD['humidifier']*humidifier

port=detect_ch340_port()
if not port:
    cutoff(); raise SystemExit('Gate7 monitor serial port missing; master cutoff applied')

out_re=re.compile(
 r'stage28d_output real=(?P<real>[01]) lamp_known=(?P<lk>[01]) lamp_on=(?P<lamp>[01]) '
 r'fan_known=(?P<fk>[01]) fan_on=(?P<fan>[01]) humidifier_known=(?P<hk>[01]) humidifier_on=(?P<hum>[01]) '
 r'safety_latched=(?P<latched>[01]) force_fan=(?P<force>[01]) safety_reason=(?P<reason>\d+) '
 r'requested_fan=(?P<rf>[0-9.]+) requested_humidifier=(?P<rh>[0-9.]+) '
 r'applied_fan=(?P<af>[0-9.]+) applied_humidifier=(?P<ah>[0-9.]+) '
 r'arbiter_transitions=(?P<tr>\d+) arbiter_dwell_holds=(?P<dh>\d+) arbiter_safety_overrides=(?P<so>\d+) '
 r'tx=(?P<tx>\d+) tx_errors=(?P<te>\d+)')
soak_re=re.compile(r'soak_v=2 firmware_sha=(?P<sha>[0-9a-f]+).*?tp_sample=(?P<tp>[01]) tp_t=(?P<t>-?[0-9.]+) tp_rh=(?P<rh>-?[0-9.]+).*?storage_backend=(?P<st>[a-z-]+).*?storage_write_errors=(?P<we>\d+).*?storage_queue_drops=(?P<qd>\d+).*?outputs=(?P<mode>[a-z-]+)')

records=[]; soak=[]; power=[]; logs=[]
startup_ok=False; last_line_time=time.monotonic(); start=time.monotonic(); buf=''

with serial.Serial(port,115200,timeout=.08,write_timeout=1) as h:
    try: h.dtr=False; h.rts=False
    except Exception: pass
    time.sleep(1); h.reset_input_buffer()
    h.write(b'status\n'); h.flush()
    deadline=start+DURATION_S
    while time.monotonic()<deadline:
        chunk=h.read(4096)
        if chunk:
            last_line_time=time.monotonic(); buf += chunk.decode(errors='replace')
            while '\n' in buf:
                line,buf=buf.split('\n',1); line=line.strip()
                if not line: continue
                if EXPECTED in line and ('real_outputs_requested=1' in line or 'status firmware_sha=' in line) and 'outputs=real-bounded' in line:
                    startup_ok=True
                if 'Real-output initialization failed' in line or 'outputs=fake-locked' in line and 'status firmware_sha=' in line:
                    cutoff(); raise RuntimeError('real output mode unexpectedly unavailable')
                if 'output fault' in line.lower() or 'apply failed' in line.lower() or 'tx_errors=' in line and not line.endswith('tx_errors=0'):
                    logs.append(line)
                m=out_re.search(line)
                if m:
                    r={k:int(m.group(k)) for k in ('real','lk','lamp','fk','fan','hk','hum','latched','force','reason','tr','dh','so','tx','te')}
                    r.update({k:float(m.group(k)) for k in ('rf','rh','af','ah')})
                    r['t']=time.monotonic()-start
                    if r['real']!=1 or r['te']!=0: raise RuntimeError('real mode lost or RF TX error')
                    if r['lk']!=1 or r['fk']!=1 or r['hk']!=1: raise RuntimeError('endpoint state became unknown')
                    if r['af'] not in (0.0,1.0) or r['ah'] not in (0.0,1.0): raise RuntimeError('applied binary state is not 0/1')
                    if int(r['af'])!=r['fan'] or int(r['ah'])!=r['hum']: raise RuntimeError('applied state disagrees with RF endpoint state')
                    s=get_status(); p=float(s['apower']); master=bool(s.get('output',False))
                    if not master: raise RuntimeError('Shelly master unexpectedly OFF')
                    ep=expected_power(r['lamp'],r['fan'],r['hum'])
                    delta=abs(p-ep)
                    power.append({'t':r['t'],'p':p,'expected':ep,'error':delta,'lamp':r['lamp'],'fan':r['fan'],'hum':r['hum']})
                    if p > 130.0: raise RuntimeError(f'unsafe power {p:.2f}W')
                    if delta > 5.5: raise RuntimeError(f'power signature mismatch actual={p:.2f} expected={ep:.2f}')
                    records.append(r)
                s=soak_re.search(line)
                if s:
                    q={'t':time.monotonic()-start,'sha':s.group('sha'),'tp':int(s.group('tp')),'temp':float(s.group('t')),'rh':float(s.group('rh')),'storage':s.group('st'),'we':int(s.group('we')),'qd':int(s.group('qd')),'mode':s.group('mode')}
                    if q['sha']!=EXPECTED or q['storage']!='sd' or q['we']!=0 or q['qd']!=0 or q['mode']!='real-bounded':
                        raise RuntimeError('telemetry/storage/mode gate failed')
                    if q['tp'] and q['temp'] >= 31.0: raise RuntimeError(f'authoritative temperature unsafe {q["temp"]:.2f}C')
                    soak.append(q)
        if time.monotonic()-last_line_time > 45.0:
            raise RuntimeError('serial telemetry silent for >45s')

if not startup_ok: raise RuntimeError('exact-SHA real-bounded startup/status not observed')
if len(records)<35: raise RuntimeError(f'insufficient output telemetry records={len(records)}')
if len(soak)<35: raise RuntimeError(f'insufficient SD-backed soak telemetry records={len(soak)}')
if not power: raise RuntimeError('no Shelly correlation samples')

max_power_error=max(x['error'] for x in power)
req_fan=max(r['rf'] for r in records); req_hum=max(r['rh'] for r in records)
fan_on=sum(r['fan'] for r in records); hum_on=sum(r['hum'] for r in records); lamp_on=sum(r['lamp'] for r in records)
dwell=max(r['dh'] for r in records); transitions=max(r['tr'] for r in records); overrides=max(r['so'] for r in records)
max_temp=max((q['temp'] for q in soak if q['tp']),default=float('nan'))
min_temp=min((q['temp'] for q in soak if q['tp']),default=float('nan'))
summary={'sha':EXPECTED,'duration_s':DURATION_S,'records':len(records),'soak_records':len(soak),'lamp_on_records':lamp_on,'fan_on_records':fan_on,'humidifier_on_records':hum_on,'max_requested_fan':req_fan,'max_requested_humidifier':req_hum,'arbiter_transitions':transitions,'arbiter_dwell_holds':dwell,'arbiter_safety_overrides':overrides,'max_power_error_w':max_power_error,'min_tp357_c':min_temp,'max_tp357_c':max_temp,'logs':logs[-20:]}
Path('/tmp/growbox_gate7_closed_loop_v1.json').write_text(json.dumps(summary,indent=2,sort_keys=True))
print('GATE7_CLOSED_LOOP_SUMMARY '+json.dumps(summary,sort_keys=True,separators=(',',':')))
print(f'GATE7_CLOSED_LOOP_PASS sha={EXPECTED} records={len(records)} lamp_on={lamp_on} fan_on={fan_on} humidifier_on={hum_on} dwell_holds={dwell} transitions={transitions} max_power_error_w={max_power_error:.2f}')
PY
TEST_RC=$?
set -e

# Always flash fake-locked image. Controlled RF sockets may retain their last
# state across the reboot, so immediately issue explicit OFF commands after boot.
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
    try: rpc('Switch.Set',{'id':0,'on':False,'tag':'growbox-gate7-safe-return-fallback'})
    except Exception: pass
def collect(h,d):
    end=time.monotonic()+d; p=[]
    while time.monotonic()<end:
        b=h.read(4096)
        if b: p.append(b)
    return b''.join(p).decode(errors='replace')
def send(h,cmd): h.write(cmd.encode()+b'\n'); h.flush(); return collect(h,2.5)

port=detect_ch340_port()
if not port: cutoff(); raise SystemExit('Gate7 safe-return serial port missing; master cutoff applied')
time.sleep(2)
with serial.Serial(port,115200,timeout=.12,write_timeout=1) as h:
    try: h.dtr=False; h.rts=False
    except Exception: pass
    h.reset_input_buffer(); text=''
    for _ in range(5):
        text += send(h,'status')
        if f'status firmware_sha={EXPECTED}' in text and 'outputs=fake-locked' in text and 'rf_ready=1' in text: break
    else:
        cutoff(); raise SystemExit('Gate7 safe-return exact-SHA/fake-lock status failed; master cutoff applied')
    for dev in ('lamp','fan','humidifier'):
        ok=False
        for _ in range(3):
            reply=send(h,f'rf {dev} off')
            if 'tx_queued=1 tx_started=1 tx_completed=1' in reply: ok=True; break
        if not ok:
            cutoff(); raise SystemExit(f'Gate7 safe-return {dev} OFF confirmation failed; master cutoff applied')

time.sleep(20)
vals=[]
for _ in range(9): vals.append(float(get_status()['apower'])); time.sleep(.4)
p=statistics.median(vals)
if p>8.0:
    cutoff(); raise SystemExit(f'Gate7 safe-return power high {p:.3f}W; master cutoff applied')
if TEST_RC!=0:
    cutoff(); raise SystemExit(f'Gate7 closed-loop validation failed; safe firmware and RF OFF confirmed, master cutoff applied')
print(f'GATE7_SAFE_RETURN_PASS sha={EXPECTED} outputs=fake-locked final_w={p:.3f} final=all_off master=on')
PY
SAFE_RC=$?
set -e

if [[ "$TEST_RC" -ne 0 || "$SAFE_RC" -ne 0 ]]; then
  echo "GATE7_FINAL_FAIL test_rc=$TEST_RC safe_rc=$SAFE_RC"
  exit 1
fi

test -z "$(git status --porcelain)"
echo "GATE7_PHYSICAL_CLOSED_LOOP_COMPLETE sha=$EXPECTED outputs=fake-locked final=all_off master=on"
