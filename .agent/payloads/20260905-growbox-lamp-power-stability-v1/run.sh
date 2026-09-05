#!/usr/bin/env bash
set -euo pipefail
EXPECTED=3dfc4b552f669f628d5c9bee455a34666915088c
BRANCH=mvp/environment-controller
ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"
git fetch -q origin "$BRANCH"
git reset --hard "$EXPECTED" >/dev/null
test "$(git rev-parse HEAD)" = "$EXPECTED"
test "$(git rev-parse origin/$BRANCH)" = "$EXPECTED"
test -z "$(git status --porcelain)"
PY="$ROOT/.venv/bin/python"
if [[ ! -x "$PY" ]]; then PY="$(command -v python3)"; fi
"$PY" - "$EXPECTED" <<'PY'
import json,re,statistics,sys,time,urllib.request
from pathlib import Path
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
    with urllib.request.urlopen(req,timeout=5) as r: return json.loads(r.read().decode())
def set_master(on,tag):
    rpc('Switch.Set',{'id':0,'on':bool(on),'tag':tag}); time.sleep(1)
    if bool(get_status().get('output',False)) != bool(on): raise RuntimeError('Shelly master readback mismatch')
def collect(h,d):
    end=time.monotonic()+d; out=[]
    while time.monotonic()<end:
        b=h.read(4096)
        if b: out.append(b)
    return b''.join(out).decode(errors='replace')
def send(h,cmd,d=2.4):
    h.write(cmd.encode()+b'\n'); h.flush(); return collect(h,d)
def median_power(n=7,dt=.35):
    vals=[]; volts=[]
    for _ in range(n):
        s=get_status(); vals.append(float(s['apower'])); volts.append(float(s.get('voltage',0.0))); time.sleep(dt)
    return statistics.median(vals),statistics.median(volts)
def cutoff():
    try: set_master(False,'growbox-lamp-stability-fallback')
    except Exception: pass

port=detect_ch340_port()
if not port:
    cutoff(); raise SystemExit('LAMP_STABILITY_FAIL serial_missing master=off')
if not bool(get_status().get('output',False)):
    set_master(True,'growbox-lamp-stability-preflight')

samples=[]; temps=[]; persistent_drop=False; reference=None; consecutive_drop=0
try:
    with serial.Serial(port,115200,timeout=.12,write_timeout=1) as h:
        try: h.dtr=False; h.rts=False
        except Exception: pass
        time.sleep(1); h.reset_input_buffer()
        status=''
        for _ in range(5):
            status += send(h,'status')
            if f'status firmware_sha={EXPECTED}' in status and 'outputs=fake-locked' in status and 'rf_ready=1' in status: break
        if f'status firmware_sha={EXPECTED}' not in status or 'outputs=fake-locked' not in status or 'rf_ready=1' not in status:
            raise RuntimeError('installed firmware identity/mode gate failed')
        for cmd in ('rf lamp off','rf fan off','rf humidifier off'):
            txt=send(h,cmd)
            if 'tx_completed=1' not in txt: raise RuntimeError('preflight RF OFF transmit not completed')
        time.sleep(15)
        baseline,base_v=median_power()
        if baseline>8.0: raise RuntimeError(f'unsafe baseline {baseline:.2f}W')
        print(f'LAMP_STABILITY_BASELINE power_w={baseline:.2f} voltage_v={base_v:.1f}',flush=True)
        txt=send(h,'rf lamp on')
        if 'tx_completed=1' not in txt: raise RuntimeError('lamp ON transmit not completed')
        start=time.monotonic(); next_sample=start+15; next_sensor=start+10; end=start+195
        while time.monotonic()<end:
            now=time.monotonic()
            if now>=next_sensor:
                text=send(h,'sensors',1.6)
                m=re.search(r'tp357 temp_c=([0-9.]+).*?age_ms=(\d+)',text)
                if not m: raise RuntimeError('TP357 safety sample unavailable')
                temp=float(m.group(1)); age=int(m.group(2)); temps.append(temp)
                if age>30000: raise RuntimeError(f'TP357 safety sample stale age_ms={age}')
                if temp>=28.0: raise RuntimeError(f'TP357 thermal limit reached temp_c={temp:.2f}')
                next_sensor=now+10
            if now>=next_sample:
                p,v=median_power(7,.25); t=now-start
                samples.append({'t_s':round(t,1),'power_w':p,'voltage_v':v})
                if reference is None and t>=20:
                    reference=p
                if reference is not None:
                    drop=reference-p
                    if drop>=20.0: consecutive_drop += 1
                    else: consecutive_drop=0
                    if consecutive_drop>=3: persistent_drop=True
                print(f'LAMP_STABILITY_SAMPLE t_s={t:.1f} power_w={p:.2f} voltage_v={v:.1f} reference_w={reference if reference is not None else -1:.2f} consecutive_drop={consecutive_drop}',flush=True)
                next_sample=now+10
            time.sleep(.1)
        txt=send(h,'rf lamp off')
        if 'tx_completed=1' not in txt: raise RuntimeError('lamp OFF transmit not completed')
        for cmd in ('rf fan off','rf humidifier off'):
            send(h,cmd)
        time.sleep(20)
        final,final_v=median_power()
        if abs(final-baseline)>2.0: raise RuntimeError(f'final baseline mismatch final={final:.2f} baseline={baseline:.2f}')
        result={'sha':EXPECTED,'baseline_w':baseline,'final_w':final,'reference_w':reference,'persistent_drop':persistent_drop,'samples':samples,'min_temp_c':min(temps) if temps else None,'max_temp_c':max(temps) if temps else None}
        Path('/tmp/growbox_lamp_power_stability_v1.json').write_text(json.dumps(result,indent=2,sort_keys=True))
        if persistent_drop:
            print('LAMP_STABILITY_DROOP '+json.dumps(result,sort_keys=True,separators=(',',':')),flush=True)
            raise SystemExit(2)
        print('LAMP_STABILITY_PASS '+json.dumps(result,sort_keys=True,separators=(',',':')),flush=True)
except BaseException:
    try:
        with serial.Serial(port,115200,timeout=.12,write_timeout=1) as h:
            try: h.dtr=False; h.rts=False
            except Exception: pass
            time.sleep(.5); h.reset_input_buffer()
            for cmd in ('rf lamp off','rf fan off','rf humidifier off'): send(h,cmd,1.8)
        time.sleep(15)
        p,_=median_power()
        if p<=8.0:
            print(f'LAMP_STABILITY_CLEANUP power_w={p:.2f} master=on',flush=True)
        else:
            cutoff(); print(f'LAMP_STABILITY_CLEANUP_UNSAFE power_w={p:.2f} master=off',flush=True)
    except Exception:
        cutoff(); print('LAMP_STABILITY_CLEANUP_UNCONFIRMED master=off',flush=True)
    raise
PY
