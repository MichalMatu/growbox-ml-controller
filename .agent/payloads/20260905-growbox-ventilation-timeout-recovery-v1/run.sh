#!/usr/bin/env bash
set -euo pipefail
EXPECTED=d9d6b40038129e6499d0fd092b628f31f867e20b
ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"
PY="$ROOT/.venv/bin/python"
if [[ ! -x "$PY" ]]; then PY="$(command -v python3)"; fi
"$PY" - "$EXPECTED" <<'PY'
import json, statistics, sys, time, urllib.request
import serial
from tools.stage27c_soak import detect_ch340_port
EXPECTED=sys.argv[1]
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
    try:
        rpc('Switch.Set',{'id':0,'on':False,'tag':'growbox-vent-timeout-recovery'})
    except Exception:
        pass

def collect(h,d):
    end=time.monotonic()+d; out=[]
    while time.monotonic()<end:
        b=h.read(4096)
        if b: out.append(b)
    return b''.join(out).decode(errors='replace')

def send(h,text,d=2.2):
    h.write(text.encode()+b'\n'); h.flush(); return collect(h,d)

def tx(h,dev,state,code):
    text=''
    for _ in range(3):
        text += send(h,f'rf {dev} {state}',2.5)
        if f'manual_rf_tx device={dev} state={state} code={code}' in text and 'tx_queued=1 tx_started=1 tx_completed=1' in text:
            return
    raise RuntimeError(f'RF evidence missing {dev} {state}')

s=get_status()
if not bool(s.get('output',False)):
    print('VENT_TIMEOUT_RECOVERY_MASTER_ALREADY_OFF safe=1', flush=True)
    raise SystemExit(0)
port=detect_ch340_port()
if not port:
    cutoff(); raise SystemExit('Vent timeout recovery: serial missing; master cutoff applied')
with serial.Serial(port,115200,timeout=.12,write_timeout=1) as h:
    try: h.dtr=False; h.rts=False
    except Exception: pass
    time.sleep(1); h.reset_input_buffer()
    status=''
    for _ in range(5):
        status += send(h,'status',2.0)
        if f'status firmware_sha={EXPECTED}' in status and 'outputs=fake-locked' in status and 'rf_ready=1' in status:
            break
    else:
        cutoff(); raise SystemExit('Vent timeout recovery: exact-SHA/fake-lock/rf-ready status failed; master cutoff applied')
    for dev,code in [('fan',1040336384),('lamp',16926208),('humidifier',771900928)]:
        tx(h,dev,'off',code)
        print(f'VENT_TIMEOUT_RECOVERY_OFF device={dev}', flush=True)

time.sleep(20)
vals=[]
for _ in range(9):
    st=get_status()
    if not bool(st.get('output',False)):
        raise SystemExit('Vent timeout recovery: master changed OFF unexpectedly')
    vals.append(float(st['apower']))
    time.sleep(.4)
p=statistics.median(vals)
if p>8.0:
    cutoff(); raise SystemExit(f'Vent timeout recovery: high final power {p:.3f}W; master cutoff applied')
print(f'VENT_TIMEOUT_RECOVERY_PASS sha={EXPECTED} power_w={p:.3f} all_rf_off=1 master=on', flush=True)
PY
