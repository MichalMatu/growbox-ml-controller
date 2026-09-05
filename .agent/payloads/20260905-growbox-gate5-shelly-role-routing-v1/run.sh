#!/usr/bin/env bash
set -euo pipefail

EXPECTED=8710bf127ad895e262f604e1b4c59ea11b760667
BRANCH=mvp/environment-controller
SETTLE=20

git fetch -q origin "$BRANCH"
git reset --hard "$EXPECTED"
test "$(git rev-parse HEAD)" = "$EXPECTED"
test "$(git rev-parse origin/$BRANCH)" = "$EXPECTED"
test -z "$(git status --porcelain)"

PY="$(git rev-parse --show-toplevel)/.venv/bin/python"
if [[ ! -x "$PY" ]]; then PY="$(command -v python3)"; fi

"$PY" - "$EXPECTED" "$SETTLE" <<'PY'
import json
import statistics
import sys
import time
import urllib.request
from pathlib import Path
import serial
from tools.stage27c_soak import detect_ch340_port

expected=sys.argv[1]
settle=float(sys.argv[2])
SHELLY='http://192.168.0.16'
port=detect_ch340_port()
if not port: raise SystemExit('CrowPanel CH340 serial port was not detected')
print('GATE5_PORT',port)

def get_status():
    with urllib.request.urlopen(SHELLY+'/rpc/Switch.GetStatus?id=0',timeout=5) as r:
        return json.loads(r.read().decode())

def rpc(method,params):
    body=json.dumps({'id':1,'method':method,'params':params}).encode()
    req=urllib.request.Request(SHELLY+'/rpc',data=body,headers={'Content-Type':'application/json'},method='POST')
    with urllib.request.urlopen(req,timeout=5) as r: return json.loads(r.read().decode())

def set_master(on):
    rpc('Switch.Set',{'id':0,'on':bool(on),'tag':'growbox-gate5'})
    time.sleep(1)
    s=get_status()
    if bool(s['output']) != bool(on): raise RuntimeError('master readback mismatch')
    return s

def sample(n=9,interval=.5):
    rows=[]
    for _ in range(n):
        rows.append(get_status()); time.sleep(interval)
    p=[float(x['apower']) for x in rows]
    return {'p':statistics.median(p),'min':min(p),'max':max(p),'v':statistics.median(float(x['voltage']) for x in rows),'i':statistics.median(float(x['current']) for x in rows)}

def collect(h,d):
    end=time.monotonic()+d; out=[]
    while time.monotonic()<end:
        b=h.read(4096)
        if b: out.append(b)
    return b''.join(out).decode(errors='replace')

def cmd(h,t,d=2):
    h.write(t.encode()+b'\n'); h.flush(); return collect(h,d)

def ready(h):
    text=''
    for _ in range(5):
        text+=cmd(h,'status')
        if f'status firmware_sha={expected}' in text and 'outputs=fake-locked' in text and 'rf_ready=1' in text: return True
    return False

def tx(h,dev,state,code):
    text=''
    for _ in range(3):
        text+=cmd(h,f'rf {dev} {state}',2.5)
        if f'manual_rf_tx device={dev} state={state} code={code}' in text and 'tx_queued=1 tx_started=1 tx_completed=1' in text: return text
    raise RuntimeError(f'RF evidence missing {dev} {state}')

def all_off(h):
    errs=[]
    for dev,code in [('lamp',16926208),('fan',1040336384),('humidifier',771900928)]:
        try: tx(h,dev,'off',code)
        except Exception as e: errs.append(f'{dev}:{e}')
    return errs

ranges={'lamp':(90.0,105.0),'fan':(2.0,4.5),'humidifier':(13.0,18.5)}
codes={'lamp':(235030016,16926208),'fan':(906118656,1040336384),'humidifier':(637683200,771900928)}
results={}
unsafe=False
initial=get_status()
if not initial['output']: set_master(True)
with serial.Serial(port,115200,timeout=.12,write_timeout=1) as h:
    try: h.dtr=False; h.rts=False
    except Exception: pass
    time.sleep(1); h.reset_input_buffer(); cmd(h,'',.5)
    if not ready(h): raise SystemExit('firmware identity/safety status failed')
    try:
        errs=all_off(h)
        if errs: raise RuntimeError('initial all-off failed '+','.join(errs))
        time.sleep(settle)
        baseline=sample(); results['baseline']=baseline
        print(f'GATE5_BASELINE power_w={baseline["p"]:.3f} voltage_v={baseline["v"]:.2f}')
        for dev in ('lamp','fan','humidifier'):
            pre=sample(); oncode,offcode=codes[dev]
            tx(h,dev,'on',oncode); time.sleep(settle); on=sample()
            tx(h,dev,'off',offcode); time.sleep(settle); off=sample()
            don=on['p']-pre['p']; doff=on['p']-off['p']; lo,hi=ranges[dev]
            passed=lo <= don <= hi and lo <= doff <= hi and abs(don-doff) <= max(0.6,(hi-lo)*0.25)
            results[dev]={'pre':pre,'on':on,'off':off,'delta_on':don,'delta_off':doff,'pass':passed}
            print(f'GATE5_SIGNATURE device={dev} pre_w={pre["p"]:.3f} on_w={on["p"]:.3f} off_w={off["p"]:.3f} delta_on_w={don:.3f} delta_off_w={doff:.3f} pass={int(passed)}')
            if not passed: raise RuntimeError(f'{dev} Shelly signature outside qualified range')
    finally:
        errs=all_off(h); time.sleep(settle); final=sample(); results['final']=final
        ref=results.get('baseline',final)['p']; diff=abs(final['p']-ref)
        print(f'GATE5_FINAL power_w={final["p"]:.3f} baseline_delta_w={diff:.3f} cleanup_errors={len(errs)}')
        unsafe=bool(errs) or diff>3.0
    if not ready(h): unsafe=True

if unsafe:
    print('GATE5_CLEANUP_UNCERTAIN master_cutoff=1')
    set_master(False)
    raise SystemExit('Gate5 cleanup uncertain; master cutoff applied')
Path('/tmp/growbox_gate5_shelly_role_routing_v1.json').write_text(json.dumps(results,indent=2,sort_keys=True))
print('GATE5_ROLE_ROUTING_PASS sha='+expected+' lamp=pass fan=pass humidifier=pass final=all_off master=on')
PY

test -z "$(git status --porcelain)"
