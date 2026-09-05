#!/usr/bin/env bash
set -euo pipefail

EXPECTED=dfc6dc86a47ad2158e36bb0d5241b0153dbce387
BRANCH=mvp/environment-controller
ACTIVE_BUILD=build/idf-fan-short-diagnostic-v1
SAFE_BUILD=build/idf-fan-short-safe-return-v1
ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

git fetch -q origin "$BRANCH"
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

# Preflight the currently installed fake-locked image and establish all-loads-OFF power.
"$PY" <<'PY'
import json, statistics, time, urllib.request
import serial
from tools.stage27c_soak import detect_ch340_port
SHELLY='http://192.168.0.16'

def status():
    with urllib.request.urlopen(SHELLY+'/rpc/Switch.GetStatus?id=0',timeout=5) as r:
        return json.loads(r.read().decode())
def rpc(method,params):
    body=json.dumps({'id':1,'method':method,'params':params}).encode()
    req=urllib.request.Request(SHELLY+'/rpc',data=body,headers={'Content-Type':'application/json'},method='POST')
    with urllib.request.urlopen(req,timeout=5) as r: return json.loads(r.read().decode())
def set_master(on):
    rpc('Switch.Set',{'id':0,'on':bool(on),'tag':'fan-short-diagnostic-preflight'}); time.sleep(1)
def collect(h,seconds):
    end=time.monotonic()+seconds; out=[]
    while time.monotonic()<end:
        b=h.read(4096)
        if b: out.append(b)
    return b''.join(out).decode(errors='replace')
def send(h,cmd):
    h.write(cmd.encode()+b'\n'); h.flush(); return collect(h,2.0)

def median_power(n=9):
    vals=[]
    for _ in range(n): vals.append(float(status()['apower'])); time.sleep(.4)
    return statistics.median(vals)

if not bool(status().get('output',False)): set_master(True)
port=detect_ch340_port()
if not port:
    set_master(False); raise SystemExit('FAN_DIAG preflight serial missing; Shelly master OFF')
with serial.Serial(port,115200,timeout=.12,write_timeout=1) as h:
    try: h.dtr=False; h.rts=False
    except Exception: pass
    time.sleep(1); h.reset_input_buffer()
    text=''
    for _ in range(5):
        text += send(h,'status')
        if 'outputs=fake-locked' in text and 'rf_ready=1' in text: break
    if 'outputs=fake-locked' not in text or 'rf_ready=1' not in text:
        set_master(False); raise SystemExit('FAN_DIAG installed image is not fake-locked/rf-ready; Shelly master OFF')
    for cmd in ('rf lamp off','rf fan off','rf humidifier off'):
        send(h,cmd)
time.sleep(15)
p=median_power()
if p>8.0:
    set_master(False); raise SystemExit(f'FAN_DIAG unsafe preflight baseline {p:.3f}W; Shelly master OFF')
open('/tmp/growbox_fan_short_baseline.json','w').write(json.dumps({'power_w':p}))
print(f'FAN_DIAG_PREFLIGHT_PASS baseline_w={p:.3f} master=on',flush=True)
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
OBSERVE_S=300.0
FRESH_MS=30_000
POST_DWELL_UPTIME_MS=180_000
BASELINE=float(json.loads(Path('/tmp/growbox_fan_short_baseline.json').read_text())['power_w'])
LOAD={'lamp':97.0,'fan':2.9,'humidifier':15.75}

def shelly_status():
    with urllib.request.urlopen(SHELLY+'/rpc/Switch.GetStatus?id=0',timeout=5) as r:
        return json.loads(r.read().decode())
def rpc(method,params):
    body=json.dumps({'id':1,'method':method,'params':params}).encode()
    req=urllib.request.Request(SHELLY+'/rpc',data=body,headers={'Content-Type':'application/json'},method='POST')
    with urllib.request.urlopen(req,timeout=5) as r: return json.loads(r.read().decode())
def cutoff():
    try: rpc('Switch.Set',{'id':0,'on':False,'tag':'fan-short-diagnostic-hard-fallback'})
    except Exception: pass

def field(line,key,cast=str,default=None):
    m=re.search(r'(?:^|\\s)'+re.escape(key)+r'=([^\\s]+)',line)
    if not m: return default
    try: return cast(m.group(1))
    except Exception: return default

def parse_soak(line,elapsed):
    if 'soak_v=2 ' not in line: return None
    return {
      't':elapsed,
      'sha':field(line,'firmware_sha',str,''), 'uptime':field(line,'uptime_ms',int,0),
      'io':field(line,'io_status',int,0),
      'tp_sample':field(line,'tp_sample',int,0),'tp_t':field(line,'tp_t',float,0.0),'tp_rh':field(line,'tp_rh',float,0.0),
      'xiaomi_sample':field(line,'xiaomi_sample',int,0),'xiaomi_t':field(line,'xiaomi_t',float,0.0),'xiaomi_rh':field(line,'xiaomi_rh',float,0.0),
      'xiaomi_age':field(line,'xiaomi_age_ms',int,0),'xiaomi_packets':field(line,'xiaomi_packets',int,0),
      'xiaomi_accepted':field(line,'xiaomi_accepted',int,0),'xiaomi_rejected':field(line,'xiaomi_rejected',int,0),
      'ble_scanning':field(line,'ble_scanning',int,0),'ble_scan_errors':field(line,'ble_scan_errors',int,0),
      'ble_scan_restarts':field(line,'ble_scan_restarts',int,0),'ble_scan_completes':field(line,'ble_scan_completes',int,0),
      'ble_lock_drops':field(line,'ble_adv_lock_drops',int,0),
      'requested_fan':field(line,'requested_fan',float,0.0),'applied_fan':field(line,'applied_fan',float,0.0),
      'physical_light':field(line,'physical_light',int,0),'physical_fan':field(line,'physical_fan',int,0),
      'physical_hum':field(line,'physical_humidifier',int,0),'thermal':field(line,'thermal_latched',int,0),
      'force_fan':field(line,'force_fan',int,0),'transitions':field(line,'arbiter_transitions',int,0),
      'dwell':field(line,'arbiter_dwell_holds',int,0),'safety_overrides':field(line,'arbiter_safety_overrides',int,0),
      'storage':field(line,'storage_backend',str,''),'we':field(line,'storage_write_errors',int,0),
      'qd':field(line,'storage_queue_drops',int,0),'mode':field(line,'outputs',str,'')}

def expected_power(r):
    return BASELINE + LOAD['lamp']*r['physical_light'] + LOAD['fan']*r['physical_fan'] + LOAD['humidifier']*r['physical_hum']

port=detect_ch340_port()
if not port:
    cutoff(); raise SystemExit('FAN_DIAG monitor serial missing; Shelly master OFF')

records=[]; power=[]; rejected=[]; event_logs=[]
buf=''; last_serial=time.monotonic(); stable_sd=0; startup_real=False; warm_ready=False
with serial.Serial(port,115200,timeout=.08,write_timeout=1) as h:
    try: h.dtr=False; h.rts=False
    except Exception: pass
    time.sleep(1); h.reset_input_buffer(); h.write(b'status\n'); h.flush()
    warm_start=time.monotonic(); warm_deadline=warm_start+WARMUP_S
    while time.monotonic()<warm_deadline and not warm_ready:
        chunk=h.read(4096)
        if chunk:
            last_serial=time.monotonic(); buf += chunk.decode(errors='replace')
            while '\n' in buf:
                line,buf=buf.split('\n',1); line=line.strip()
                if not line: continue
                if EXPECTED in line and 'outputs=real-bounded' in line: startup_real=True
                if 'Real-output initialization failed' in line:
                    cutoff(); raise RuntimeError('real-output initialization failed during warm-up')
                r=parse_soak(line,time.monotonic()-warm_start)
                if r:
                    ok=(r['sha']==EXPECTED and r['storage']=='sd' and r['we']==0 and r['qd']==0 and r['mode']=='real-bounded')
                    if ok: stable_sd += 1
                    else:
                        stable_sd=0; rejected.append(r)
                        print('FAN_DIAG_WARMUP_REJECT '+json.dumps(r,sort_keys=True,separators=(',',':')),flush=True)
                    if startup_real and stable_sd>=3: warm_ready=True; break
        if time.monotonic()-last_serial>45:
            cutoff(); raise RuntimeError('serial silent >45s during warm-up')
    if not warm_ready:
        cutoff(); raise RuntimeError('warm-up never reached exact-SHA real-bounded + 3 healthy SD records')
    print(f'FAN_DIAG_WARMUP_PASS stable_sd_records={stable_sd} rejected={len(rejected)}',flush=True)

    observe_start=time.monotonic(); deadline=observe_start+OBSERVE_S
    last_power_sample=0.0; mismatch_streak=0; thermal_abort=False; next_heartbeat=observe_start+30.0
    while time.monotonic()<deadline:
        chunk=h.read(4096)
        if chunk:
            last_serial=time.monotonic(); buf += chunk.decode(errors='replace')
            while '\n' in buf:
                line,buf=buf.split('\n',1); line=line.strip()
                if not line: continue
                if 'Real-output initialization failed' in line:
                    raise RuntimeError('real output initialization failure during observation')
                if 'stage28d_output ' in line:
                    te=field(line,'tx_errors',int,0)
                    if te: raise RuntimeError(f'RF tx_errors={te}')
                    if 'output fault' in line.lower() or 'apply failed' in line.lower(): event_logs.append(line)
                r=parse_soak(line,time.monotonic()-observe_start)
                if not r: continue
                if r['sha']!=EXPECTED or r['we']!=0 or r['qd']!=0 or r['mode']!='real-bounded':
                    print('FAN_DIAG_OBSERVE_REJECT '+json.dumps(r,sort_keys=True,separators=(',',':')),flush=True)
                    raise RuntimeError('telemetry integrity/mode gate failed')
                if r['storage'] not in ('sd','none','flash'): raise RuntimeError('unexpected storage backend '+r['storage'])
                if r['tp_sample'] and r['tp_t']>=31.0: raise RuntimeError(f'authoritative temperature unsafe {r["tp_t"]:.2f}C')
                if r['applied_fan'] not in (0.0,1.0): raise RuntimeError('applied_fan not binary')
                if int(r['applied_fan'])!=r['physical_fan']: raise RuntimeError('applied_fan disagrees with physical endpoint state')
                records.append(r)
                if r['thermal'] or r['force_fan']:
                    thermal_abort=True
                    print('FAN_DIAG_THERMAL_ABORT '+json.dumps(r,sort_keys=True,separators=(',',':')),flush=True)
                    break
                now=time.monotonic()
                if now-last_power_sample>=8.0:
                    vals=[]; masters=[]
                    for _ in range(5):
                        s=shelly_status(); vals.append(float(s['apower'])); masters.append(bool(s.get('output',False))); time.sleep(.4)
                    if not all(masters): raise RuntimeError('Shelly master unexpectedly OFF')
                    p=statistics.median(vals); ep=expected_power(r); err=abs(p-ep)
                    power.append({'t':r['t'],'p':p,'expected':ep,'error':err,'state':[r['physical_light'],r['physical_fan'],r['physical_hum']]})
                    print(f'FAN_DIAG_POWER state={(r["physical_light"],r["physical_fan"],r["physical_hum"])} actual={p:.2f} expected={ep:.2f} error={err:.2f}',flush=True)
                    if p>130.0: raise RuntimeError(f'unsafe power {p:.2f}W')
                    tolerance=2.2 if r['physical_fan'] else 5.5
                    if err>tolerance:
                        mismatch_streak += 1
                        if mismatch_streak>=3: raise RuntimeError(f'persistent power mismatch actual={p:.2f} expected={ep:.2f}')
                    else: mismatch_streak=0
                    last_power_sample=time.monotonic()
            if thermal_abort: break
        now=time.monotonic()
        if now>=next_heartbeat:
            print(f'FAN_DIAG_HEARTBEAT elapsed_s={now-observe_start:.1f} records={len(records)} power_samples={len(power)}',flush=True)
            next_heartbeat=now+30.0
        if now-last_serial>45: raise RuntimeError('serial telemetry silent >45s during observation')

if len(records)<15: raise RuntimeError(f'insufficient telemetry records={len(records)}')
first,last=records[0],records[-1]
packet_delta=max(0,last['xiaomi_packets']-first['xiaomi_packets'])
accepted_delta=max(0,last['xiaomi_accepted']-first['xiaomi_accepted'])
rejected_delta=max(0,last['xiaomi_rejected']-first['xiaomi_rejected'])
fresh_records=[r for r in records if r['xiaomi_sample']==1 and r['xiaomi_age']<=FRESH_MS]
max_xiaomi_age=max((r['xiaomi_age'] for r in records if r['xiaomi_sample']),default=None)
post=[r for r in records if r['uptime']>=POST_DWELL_UPTIME_MS and r['requested_fan']>=0.10 and not r['thermal'] and not r['force_fan']]
fan_on=[r for r in records if r['physical_fan']==1]
fan_power_confirmed=any(x['state'][1]==1 and x['error']<=2.2 for x in power)
xiaomi_healthy=(len(fresh_records)>=max(1,int(len(records)*0.8)) and accepted_delta>0 and max_xiaomi_age is not None and max_xiaomi_age<=FRESH_MS)
if thermal_abort:
    classification='thermal_override_abort'
    rc=0
elif post and fan_on:
    classification='normal_fan_transition_confirmed'
    rc=0
elif post and not fan_on:
    classification='post_dwell_request_not_applied'
    rc=3
elif not xiaomi_healthy:
    classification='xiaomi_freshness_or_decode_problem'
    rc=4
else:
    classification='no_post_dwell_request_xiaomi_fresh'
    rc=0
summary={
 'sha':EXPECTED,'duration_s':OBSERVE_S,'records':len(records),'classification':classification,
 'min_uptime_ms':min(r['uptime'] for r in records),'max_uptime_ms':max(r['uptime'] for r in records),
 'max_requested_fan':max(r['requested_fan'] for r in records),'post_dwell_request_records':len(post),
 'fan_on_records':len(fan_on),'fan_power_confirmed':fan_power_confirmed,
 'arbiter_transitions_max':max(r['transitions'] for r in records),'arbiter_dwell_holds_max':max(r['dwell'] for r in records),
 'xiaomi_fresh_records':len(fresh_records),'xiaomi_total_records':len(records),'max_xiaomi_age_ms':max_xiaomi_age,
 'xiaomi_packet_delta':packet_delta,'xiaomi_accepted_delta':accepted_delta,'xiaomi_rejected_delta':rejected_delta,
 'ble_scan_errors_max':max(r['ble_scan_errors'] for r in records),'ble_lock_drops_max':max(r['ble_lock_drops'] for r in records),
 'min_tp357_c':min((r['tp_t'] for r in records if r['tp_sample']),default=None),
 'max_tp357_c':max((r['tp_t'] for r in records if r['tp_sample']),default=None),
 'power_samples':len(power),'max_power_error_w':max((x['error'] for x in power),default=None),'event_logs':event_logs[-20:]}
Path('/tmp/growbox_fan_short_result.json').write_text(json.dumps(summary,indent=2,sort_keys=True))
print('FAN_DIAG_SUMMARY '+json.dumps(summary,sort_keys=True,separators=(',',':')),flush=True)
print(f'FAN_DIAG_CLASSIFICATION {classification}',flush=True)
raise SystemExit(rc)
PY
TEST_RC=$?
set -e

# Always restore an exact-SHA fake-locked image after the real-output diagnostic.
set +e
GROWBOX_RF433_LOOPBACK_ENABLED=1 \
GROWBOX_STAGE28_REAL_OUTPUTS_ENABLED=0 \
GROWBOX_STAGE28_THERMAL_TEST_SEQUENCE_ENABLED=0 \
GROWBOX_FIRMWARE_GIT_SHA="$EXPECTED" \
STAGE27C_BUILD_DIR="$SAFE_BUILD" \
bash scripts/stage27c_crowpanel.sh flash
FLASH_SAFE_RC=$?
set -e
if [[ $FLASH_SAFE_RC -ne 0 ]]; then
  "$PY" - <<'PY'
import json,urllib.request
try:
    body=json.dumps({'id':1,'method':'Switch.Set','params':{'id':0,'on':False,'tag':'fan-short-safe-flash-failed'}}).encode()
    req=urllib.request.Request('http://192.168.0.16/rpc',data=body,headers={'Content-Type':'application/json'},method='POST')
    urllib.request.urlopen(req,timeout=5).read()
except Exception: pass
PY
  exit "$FLASH_SAFE_RC"
fi

"$PY" - "$EXPECTED" "$TEST_RC" <<'PY'
import json,statistics,sys,time,urllib.request
import serial
from tools.stage27c_soak import detect_ch340_port
EXPECTED=sys.argv[1]; TEST_RC=int(sys.argv[2]); SHELLY='http://192.168.0.16'
def status():
    with urllib.request.urlopen(SHELLY+'/rpc/Switch.GetStatus?id=0',timeout=5) as r: return json.loads(r.read().decode())
def rpc(method,params):
    body=json.dumps({'id':1,'method':method,'params':params}).encode(); req=urllib.request.Request(SHELLY+'/rpc',data=body,headers={'Content-Type':'application/json'},method='POST')
    with urllib.request.urlopen(req,timeout=5) as r: return json.loads(r.read().decode())
def set_master(on): rpc('Switch.Set',{'id':0,'on':bool(on),'tag':'fan-short-safe-return'}); time.sleep(1)
def collect(h,d):
    end=time.monotonic()+d; out=[]
    while time.monotonic()<end:
        b=h.read(4096)
        if b: out.append(b)
    return b''.join(out).decode(errors='replace')
def send(h,cmd): h.write(cmd.encode()+b'\n'); h.flush(); return collect(h,2.0)
if not bool(status().get('output',False)): set_master(True)
port=detect_ch340_port()
if not port:
    set_master(False); raise SystemExit('FAN_DIAG safe-return serial missing; Shelly master OFF')
with serial.Serial(port,115200,timeout=.12,write_timeout=1) as h:
    try: h.dtr=False; h.rts=False
    except Exception: pass
    time.sleep(1); h.reset_input_buffer(); text=''
    for _ in range(5):
        text += send(h,'status')
        if EXPECTED in text and 'outputs=fake-locked' in text and 'rf_ready=1' in text: break
    if EXPECTED not in text or 'outputs=fake-locked' not in text or 'rf_ready=1' not in text:
        set_master(False); raise SystemExit('FAN_DIAG safe-return exact-SHA fake-locked verification failed; Shelly master OFF')
    for cmd in ('rf lamp off','rf fan off','rf humidifier off'): send(h,cmd)
time.sleep(15)
vals=[]
for _ in range(9): vals.append(float(status()['apower'])); time.sleep(.4)
p=statistics.median(vals)
if p>8.0:
    set_master(False); raise SystemExit(f'FAN_DIAG safe-return high power {p:.3f}W; Shelly master OFF')
print(f'FAN_DIAG_SAFE_RETURN_PASS sha={EXPECTED} outputs=fake-locked power_w={p:.3f} master=on test_rc={TEST_RC}',flush=True)
if TEST_RC!=0: raise SystemExit(TEST_RC)
PY

test "$(git rev-parse HEAD)" = "$EXPECTED"
test "$(git rev-parse origin/$BRANCH)" = "$EXPECTED"
test -z "$(git status --porcelain)"
echo "FAN_DIAG_E2E_COMPLETE sha=$EXPECTED safe_return=fake-locked"
