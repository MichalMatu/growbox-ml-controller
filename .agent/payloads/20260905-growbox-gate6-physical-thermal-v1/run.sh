#!/usr/bin/env bash
set -euo pipefail

EXPECTED=d9d6b40038129e6499d0fd092b628f31f867e20b
BRANCH=mvp/environment-controller
BOUNDED_BUILD=build/idf-gate6-physical-bounded
SAFE_BUILD=build/idf-gate6-safe-return

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"
git fetch -q origin "$BRANCH"
git reset --hard "$EXPECTED" >/dev/null
test "$(git rev-parse HEAD)" = "$EXPECTED"
test "$(git rev-parse origin/$BRANCH)" = "$EXPECTED"
test -z "$(git status --porcelain)"

export CMAKE_BUILD_PARALLEL_LEVEL=1

# Build both artifacts before any physical action. The safe-return image is
# deliberately fake-locked so that a later reboot cannot repeat Gate6.
GROWBOX_RF433_LOOPBACK_ENABLED=1 \
GROWBOX_STAGE28_REAL_OUTPUTS_ENABLED=1 \
GROWBOX_STAGE28_THERMAL_TEST_SEQUENCE_ENABLED=1 \
GROWBOX_FIRMWARE_GIT_SHA="$EXPECTED" \
STAGE27C_BUILD_DIR="$BOUNDED_BUILD" \
bash scripts/stage27c_crowpanel.sh build

grep -q '^GROWBOX_STAGE28_REAL_OUTPUTS_ENABLED:STRING=1$' "$BOUNDED_BUILD/CMakeCache.txt"
grep -q '^GROWBOX_STAGE28_THERMAL_TEST_SEQUENCE_ENABLED:STRING=1$' "$BOUNDED_BUILD/CMakeCache.txt"
grep -q '^GROWBOX_RF433_LOOPBACK_ENABLED:STRING=1$' "$BOUNDED_BUILD/CMakeCache.txt"

GROWBOX_RF433_LOOPBACK_ENABLED=1 \
GROWBOX_STAGE28_REAL_OUTPUTS_ENABLED=0 \
GROWBOX_STAGE28_THERMAL_TEST_SEQUENCE_ENABLED=0 \
GROWBOX_FIRMWARE_GIT_SHA="$EXPECTED" \
STAGE27C_BUILD_DIR="$SAFE_BUILD" \
bash scripts/stage27c_crowpanel.sh build

grep -q '^GROWBOX_STAGE28_REAL_OUTPUTS_ENABLED:STRING=0$' "$SAFE_BUILD/CMakeCache.txt"
grep -q '^GROWBOX_STAGE28_THERMAL_TEST_SEQUENCE_ENABLED:STRING=0$' "$SAFE_BUILD/CMakeCache.txt"
grep -q '^GROWBOX_RF433_LOOPBACK_ENABLED:STRING=1$' "$SAFE_BUILD/CMakeCache.txt"

PY="$ROOT/.venv/bin/python"
if [[ ! -x "$PY" ]]; then PY="$(command -v python3)"; fi

# Preflight Shelly and force a known physical OFF state using the currently
# installed fake-locked service firmware only when the measured baseline is high.
"$PY" - "$EXPECTED" <<'PY'
import json
import statistics
import sys
import time
import urllib.request
from pathlib import Path
import serial
from tools.stage27c_soak import detect_ch340_port

expected=sys.argv[1]
SHELLY='http://192.168.0.16'

def get_status():
    with urllib.request.urlopen(SHELLY+'/rpc/Switch.GetStatus?id=0',timeout=5) as r:
        return json.loads(r.read().decode())

def rpc(method,params):
    body=json.dumps({'id':1,'method':method,'params':params}).encode()
    req=urllib.request.Request(SHELLY+'/rpc',data=body,headers={'Content-Type':'application/json'},method='POST')
    with urllib.request.urlopen(req,timeout=5) as r:
        return json.loads(r.read().decode())

def set_master(on):
    rpc('Switch.Set',{'id':0,'on':bool(on),'tag':'growbox-gate6-preflight'})
    time.sleep(1)
    s=get_status()
    if bool(s['output']) != bool(on):
        raise RuntimeError('Shelly master readback mismatch')

def sample(n=9,interval=.4):
    p=[]
    for _ in range(n):
        p.append(float(get_status()['apower']))
        time.sleep(interval)
    return statistics.median(p)

def collect(h,d):
    end=time.monotonic()+d
    out=[]
    while time.monotonic()<end:
        b=h.read(4096)
        if b: out.append(b)
    return b''.join(out).decode(errors='replace')

def send(h,text):
    h.write(text.encode()+b'\n'); h.flush(); return collect(h,2.2)

s=get_status()
if not s.get('output',False):
    set_master(True)
p=sample()
if p > 8.0:
    port=detect_ch340_port()
    if not port:
        set_master(False)
        raise SystemExit('Gate6 preflight high power and no serial port; master cutoff applied')
    with serial.Serial(port,115200,timeout=.12,write_timeout=1) as h:
        try: h.dtr=False; h.rts=False
        except Exception: pass
        time.sleep(1); h.reset_input_buffer(); send(h,'status')
        for cmd in ('rf lamp off','rf fan off','rf humidifier off'):
            send(h,cmd)
    time.sleep(20)
    p=sample()
if p > 8.0:
    set_master(False)
    raise SystemExit(f'Gate6 preflight unsafe baseline {p:.3f}W; master cutoff applied')
Path('/tmp/growbox_gate6_baseline.json').write_text(json.dumps({'power_w':p},sort_keys=True))
print(f'GATE6_PREFLIGHT_PASS baseline_w={p:.3f} master=on')
PY

# Flash the exact bounded image. This starts the deterministic 27.5 -> 28 ->
# 29 -> 27 -> 26 C sequence. Firmware itself locks outputs and forces OFF at end.
GROWBOX_RF433_LOOPBACK_ENABLED=1 \
GROWBOX_STAGE28_REAL_OUTPUTS_ENABLED=1 \
GROWBOX_STAGE28_THERMAL_TEST_SEQUENCE_ENABLED=1 \
GROWBOX_FIRMWARE_GIT_SHA="$EXPECTED" \
STAGE27C_BUILD_DIR="$BOUNDED_BUILD" \
bash scripts/stage27c_crowpanel.sh flash

set +e
"$PY" - "$EXPECTED" <<'PY'
import json
import re
import statistics
import sys
import time
import urllib.request
from pathlib import Path
import serial
from tools.stage27c_soak import detect_ch340_port

expected=sys.argv[1]
SHELLY='http://192.168.0.16'
baseline=float(json.loads(Path('/tmp/growbox_gate6_baseline.json').read_text())['power_w'])

def get_status():
    with urllib.request.urlopen(SHELLY+'/rpc/Switch.GetStatus?id=0',timeout=5) as r:
        return json.loads(r.read().decode())

def rpc(method,params):
    body=json.dumps({'id':1,'method':method,'params':params}).encode()
    req=urllib.request.Request(SHELLY+'/rpc',data=body,headers={'Content-Type':'application/json'},method='POST')
    with urllib.request.urlopen(req,timeout=5) as r:
        return json.loads(r.read().decode())

def set_master(on):
    rpc('Switch.Set',{'id':0,'on':bool(on),'tag':'growbox-gate6-fallback'})
    time.sleep(1)

def zone(power):
    d=power-baseline
    if abs(d) <= 1.2: return 'off'
    if 2.0 <= d <= 4.5: return 'fan'
    if 13.0 <= d <= 18.5: return 'humidifier'
    if 90.0 <= d <= 105.0: return 'lamp'
    return 'other'

port=detect_ch340_port()
if not port:
    set_master(False)
    raise SystemExit('Gate6 monitor could not detect CrowPanel serial; master cutoff applied')

samples=[]
phase_times={}
log_lines=[]
abort=False
complete=False
complete_seen_at=None
start=time.monotonic()
line_buffer=''

with serial.Serial(port,115200,timeout=.05,write_timeout=1) as h:
    try: h.dtr=False; h.rts=False
    except Exception: pass
    last_power=0.0
    deadline=start+735.0
    while time.monotonic()<deadline:
        chunk=h.read(4096)
        if chunk:
            line_buffer += chunk.decode(errors='replace')
            while '\n' in line_buffer:
                line,line_buffer=line_buffer.split('\n',1)
                line=line.strip()
                if not line: continue
                if 'GATE6_' in line or 'stage28d_output' in line or 'soak_v=2' in line:
                    log_lines.append(line)
                    if 'GATE6_' in line:
                        print(line)
                m=re.search(r'GATE6_THERMAL_PHASE phase=([a-z-]+)',line)
                if m and m.group(1) not in phase_times:
                    phase_times[m.group(1)]=time.monotonic()-start
                if 'GATE6_THERMAL_ABORT' in line:
                    abort=True
                if 'GATE6_THERMAL_SEQUENCE_COMPLETE safe_off=1' in line:
                    complete=True
                    complete_seen_at=time.monotonic()
        now=time.monotonic()
        if now-last_power >= 1.0:
            s=get_status()
            p=float(s['apower'])
            samples.append({'t':now-start,'p':p,'zone':zone(p),'master':bool(s['output'])})
            last_power=now
        if complete and complete_seen_at is not None and time.monotonic()-complete_seen_at >= 22.0:
            break

# Persist the complete host-side trace for the Local Agent result environment.
trace={'baseline_w':baseline,'phases':phase_times,'abort':abort,'complete':complete,'samples':samples,'logs':log_lines}
Path('/tmp/growbox_gate6_physical_thermal_v1.json').write_text(json.dumps(trace,indent=2,sort_keys=True))

if not samples:
    set_master(False)
    raise SystemExit('Gate6 produced no Shelly samples; master cutoff applied')
if abort or not complete:
    set_master(False)
    raise SystemExit(f'Gate6 firmware abort/incomplete abort={abort} complete={complete}; master cutoff applied')

required=('trip','hot','recovery-above','recovery-hold')
missing=[x for x in required if x not in phase_times]
if missing:
    set_master(False)
    raise SystemExit('Gate6 missing serial phases: '+','.join(missing))

# Validate the physical power sequence. The recovery hold is intentionally 610 s:
# after >=600 s at <=26 C the lamp must briefly resume before final scheduled OFF.
lamp_early=[s for s in samples if s['t'] < 35.0 and s['zone']=='lamp']
fan_mid=[s for s in samples if 20.0 < s['t'] < 660.0 and s['zone']=='fan']
lamp_recovered=[s for s in samples if s['t'] > 645.0 and s['zone']=='lamp']
humidifier=[s for s in samples if s['zone']=='humidifier']
final_window=samples[-10:] if len(samples)>=10 else samples
final_median=statistics.median(s['p'] for s in final_window)
final_delta=final_median-baseline
masters_ok=all(s['master'] for s in samples)

print(f'GATE6_POWER_EVIDENCE early_lamp_samples={len(lamp_early)} fan_samples={len(fan_mid)} recovered_lamp_samples={len(lamp_recovered)} humidifier_signature_samples={len(humidifier)} final_w={final_median:.3f} final_delta_w={final_delta:.3f} master_all_on={int(masters_ok)}')

if len(lamp_early) < 3:
    set_master(False); raise SystemExit('Gate6 did not physically confirm initial scheduled lamp ON')
if len(fan_mid) < 100:
    set_master(False); raise SystemExit('Gate6 did not physically confirm sustained thermal exhaust ON')
if len(lamp_recovered) < 3:
    set_master(False); raise SystemExit('Gate6 did not confirm lamp recovery after 10 minute hysteresis hold')
if humidifier:
    set_master(False); raise SystemExit('Gate6 observed unexpected humidifier-like power signature')
if abs(final_delta) > 1.5:
    set_master(False); raise SystemExit('Gate6 final power did not return to baseline')
if not masters_ok:
    raise SystemExit('Shelly master unexpectedly changed state during Gate6')

# Verify the firmware switched itself back to fake-locked after completion.
with serial.Serial(port,115200,timeout=.12,write_timeout=1) as h:
    try: h.dtr=False; h.rts=False
    except Exception: pass
    h.reset_input_buffer(); h.write(b'status\n'); h.flush(); time.sleep(2)
    text=h.read(8192).decode(errors='replace')
if f'status firmware_sha={expected}' not in text or 'outputs=fake-locked' not in text:
    set_master(False)
    raise SystemExit('Gate6 post-sequence status did not confirm exact SHA fake-lock')
print('GATE6_PHYSICAL_THERMAL_PASS sha='+expected+' thermal_trip=pass hysteresis_10m=pass final=all_off master=on')
PY
TEST_RC=$?
set -e

# Always replace the self-running Gate6 image with the safe-return image.
GROWBOX_RF433_LOOPBACK_ENABLED=1 \
GROWBOX_STAGE28_REAL_OUTPUTS_ENABLED=0 \
GROWBOX_STAGE28_THERMAL_TEST_SEQUENCE_ENABLED=0 \
GROWBOX_FIRMWARE_GIT_SHA="$EXPECTED" \
STAGE27C_BUILD_DIR="$SAFE_BUILD" \
bash scripts/stage27c_crowpanel.sh flash

# Safe-return smoke. If anything is physically uncertain, cut the Shelly master.
set +e
"$PY" - "$EXPECTED" "$TEST_RC" <<'PY'
import json
import statistics
import sys
import time
import urllib.request
import serial
from tools.stage27c_soak import detect_ch340_port

expected=sys.argv[1]
test_rc=int(sys.argv[2])
SHELLY='http://192.168.0.16'

def get_status():
    with urllib.request.urlopen(SHELLY+'/rpc/Switch.GetStatus?id=0',timeout=5) as r:
        return json.loads(r.read().decode())

def rpc(method,params):
    body=json.dumps({'id':1,'method':method,'params':params}).encode()
    req=urllib.request.Request(SHELLY+'/rpc',data=body,headers={'Content-Type':'application/json'},method='POST')
    with urllib.request.urlopen(req,timeout=5) as r:
        return json.loads(r.read().decode())

def cutoff():
    try: rpc('Switch.Set',{'id':0,'on':False,'tag':'growbox-gate6-safe-return-fallback'})
    except Exception: pass

port=detect_ch340_port()
if not port:
    cutoff(); raise SystemExit('Safe-return firmware serial port missing; master cutoff applied')
time.sleep(2)
with serial.Serial(port,115200,timeout=.12,write_timeout=1) as h:
    try: h.dtr=False; h.rts=False
    except Exception: pass
    h.reset_input_buffer(); h.write(b'status\n'); h.flush(); time.sleep(2)
    text=h.read(8192).decode(errors='replace')
if f'status firmware_sha={expected}' not in text or 'outputs=fake-locked' not in text or 'rf_ready=1' not in text:
    cutoff(); raise SystemExit('Safe-return exact-SHA/fake-lock smoke failed; master cutoff applied')

s=get_status()
if test_rc == 0:
    if not bool(s.get('output',False)):
        raise SystemExit('Gate6 passed but Shelly master is unexpectedly OFF')
    vals=[]
    for _ in range(9):
        vals.append(float(get_status()['apower'])); time.sleep(.4)
    p=statistics.median(vals)
    if p > 8.0:
        cutoff(); raise SystemExit(f'Safe-return power is unexpectedly high ({p:.3f}W); master cutoff applied')
    print(f'GATE6_SAFE_RETURN_PASS sha={expected} outputs=fake-locked power_w={p:.3f} master=on')
else:
    # A failed physical gate remains fail-closed. Keep an already-cut master OFF.
    if bool(s.get('output',False)):
        cutoff()
    raise SystemExit('Gate6 physical validation failed; safe-return firmware flashed and master left OFF')
PY
SAFE_RC=$?
set -e

if [[ "$TEST_RC" -ne 0 || "$SAFE_RC" -ne 0 ]]; then
  echo "GATE6_FINAL_FAIL test_rc=$TEST_RC safe_rc=$SAFE_RC"
  exit 1
fi

test -z "$(git status --porcelain)"
echo "GATE6_E2E_COMPLETE sha=$EXPECTED bounded_test=pass safe_return=pass final=all_off master=on"
