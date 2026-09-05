#!/usr/bin/env bash
set -euo pipefail

EXPECTED=d9d6b40038129e6499d0fd092b628f31f867e20b
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
import json
import math
import re
import statistics
import sys
import time
import urllib.request
from pathlib import Path
import serial
from tools.stage27c_soak import detect_ch340_port

EXPECTED=sys.argv[1]
SHELLY='http://192.168.0.16'
BASELINE_S=300.0
FAN_ON_S=600.0
RECOVERY_S=300.0
POWER_INTERVAL_S=5.0
SERIAL_TIMEOUT=0.08

telemetry_re=re.compile(
    r'soak_v=2 firmware_sha=(?P<sha>[0-9a-f]+).*?'
    r'scd_sample=(?P<scd_valid>[01]) scd_t=(?P<scd_t>-?[0-9.]+) scd_rh=(?P<scd_rh>-?[0-9.]+) scd_co2=(?P<co2>-?[0-9.]+).*?'
    r'tp_sample=(?P<tp_valid>[01]) tp_t=(?P<tp_t>-?[0-9.]+) tp_rh=(?P<tp_rh>-?[0-9.]+).*?'
    r'xiaomi_sample=(?P<xm_valid>[01]) xiaomi_t=(?P<xm_t>-?[0-9.]+) xiaomi_rh=(?P<xm_rh>-?[0-9.]+).*?'
    r'storage_backend=(?P<storage>[a-z-]+).*?storage_write_errors=(?P<write_errors>\d+).*?storage_queue_drops=(?P<queue_drops>\d+).*?outputs=(?P<outputs>[a-z-]+)'
)

def get_status():
    with urllib.request.urlopen(SHELLY+'/rpc/Switch.GetStatus?id=0',timeout=5) as r:
        return json.loads(r.read().decode())

def rpc(method,params):
    body=json.dumps({'id':1,'method':method,'params':params}).encode()
    req=urllib.request.Request(SHELLY+'/rpc',data=body,headers={'Content-Type':'application/json'},method='POST')
    with urllib.request.urlopen(req,timeout=5) as r:
        return json.loads(r.read().decode())

def set_master(on):
    rpc('Switch.Set',{'id':0,'on':bool(on),'tag':'growbox-vent-id'})
    time.sleep(1)
    s=get_status()
    if bool(s.get('output',False)) != bool(on):
        raise RuntimeError('Shelly master readback mismatch')

def collect(h,d):
    end=time.monotonic()+d
    out=[]
    while time.monotonic()<end:
        b=h.read(4096)
        if b: out.append(b)
    return b''.join(out).decode(errors='replace')

def send(h,text,d=2.2):
    h.write(text.encode()+b'\n'); h.flush(); return collect(h,d)

def require_manual_tx(text,dev,state,code):
    needle=f'manual_rf_tx device={dev} state={state} code={code}'
    return needle in text and 'tx_queued=1 tx_started=1 tx_completed=1' in text

def tx(h,dev,state,code):
    text=''
    for _ in range(3):
        text += send(h,f'rf {dev} {state}',2.5)
        if require_manual_tx(text,dev,state,code): return
    raise RuntimeError(f'RF evidence missing {dev} {state}')

def all_off(h):
    errors=[]
    for dev,code in [('lamp',16926208),('fan',1040336384),('humidifier',771900928)]:
        try: tx(h,dev,'off',code)
        except Exception as e: errors.append(f'{dev}:{e}')
    return errors

def dewpoint_c(t,rh):
    if rh <= 0: return float('nan')
    a=17.62; b=243.12
    g=(a*t/(b+t))+math.log(rh/100.0)
    return b*g/(a-g)

def abs_humidity_gm3(t,rh):
    # 216.7 * vapor pressure(hPa) / Kelvin
    es=6.112*math.exp((17.67*t)/(t+243.5))
    e=es*rh/100.0
    return 216.7*e/(273.15+t)

def vpd_kpa(t,rh):
    es=0.6108*math.exp((17.27*t)/(t+237.3))
    return es*(1.0-rh/100.0)

def med(rows,key):
    vals=[r[key] for r in rows if r.get(key) is not None and math.isfinite(r[key])]
    return statistics.median(vals) if vals else float('nan')

def slope_per_min(rows,key):
    pts=[(r['t'],r[key]) for r in rows if r.get(key) is not None and math.isfinite(r[key])]
    if len(pts)<3: return float('nan')
    t0=statistics.mean(x for x,_ in pts); y0=statistics.mean(y for _,y in pts)
    den=sum((x-t0)**2 for x,_ in pts)
    if den<=0: return float('nan')
    s=sum((x-t0)*(y-y0) for x,y in pts)/den
    return s*60.0

def summarize(rows):
    return {
      'n':len(rows),
      'tp_t_med':med(rows,'tp_t'),'tp_rh_med':med(rows,'tp_rh'),'tp_ah_med':med(rows,'tp_ah'),'tp_vpd_med':med(rows,'tp_vpd'),
      'xm_t_med':med(rows,'xm_t'),'xm_rh_med':med(rows,'xm_rh'),'xm_ah_med':med(rows,'xm_ah'),
      'scd_t_med':med(rows,'scd_t'),'scd_rh_med':med(rows,'scd_rh'),'co2_med':med(rows,'co2'),
      'tp_t_slope_per_min':slope_per_min(rows,'tp_t'),'tp_ah_slope_per_min':slope_per_min(rows,'tp_ah'),
      'co2_slope_per_min':slope_per_min(rows,'co2')
    }

s=get_status()
if not bool(s.get('output',False)):
    set_master(True)

port=detect_ch340_port()
if not port:
    set_master(False)
    raise SystemExit('Ventilation identification: CrowPanel serial port missing; master cutoff applied')
print('VENT_ID_PORT',port)

rows=[]; power=[]; raw_markers=[]
unsafe=False
fan_commanded=False
start=time.monotonic()
phase='preflight'
line_buffer=''

with serial.Serial(port,115200,timeout=SERIAL_TIMEOUT,write_timeout=1) as h:
    try: h.dtr=False; h.rts=False
    except Exception: pass
    time.sleep(1); h.reset_input_buffer()
    status=''
    for _ in range(5):
        status += send(h,'status',2.0)
        if f'status firmware_sha={EXPECTED}' in status and 'outputs=fake-locked' in status and 'rf_ready=1' in status:
            break
    else:
        set_master(False)
        raise SystemExit('Ventilation identification: exact-SHA/fake-lock/rf-ready preflight failed; master cutoff applied')

    errs=all_off(h)
    if errs:
        set_master(False)
        raise SystemExit('Ventilation identification: initial all-off failed '+','.join(errs))
    time.sleep(20)
    p0=float(get_status()['apower'])
    if p0 > 8.0:
        set_master(False)
        raise SystemExit(f'Ventilation identification: unsafe baseline {p0:.3f}W; master cutoff applied')

    # Confirm SD-backed 10 s telemetry before perturbing the environment.
    pre=''
    end=time.monotonic()+35.0
    while time.monotonic()<end:
        pre += collect(h,1.0)
        if 'storage_backend=sd' in pre and 'storage_write_errors=0' in pre and 'storage_queue_drops=0' in pre:
            break
    if 'storage_backend=sd' not in pre or 'storage_write_errors=0' not in pre or 'storage_queue_drops=0' not in pre:
        raise SystemExit('Ventilation identification: SD telemetry not healthy; no physical pulse performed')
    print(f'VENT_ID_PREFLIGHT_PASS sha={EXPECTED} baseline_w={p0:.3f} storage=sd outputs=fake-locked')

    phase='baseline'
    phase_start=time.monotonic()
    fan_on_at=phase_start+BASELINE_S
    fan_off_at=fan_on_at+FAN_ON_S
    done_at=fan_off_at+RECOVERY_S
    next_power=0.0

    try:
        while time.monotonic() < done_at:
            now=time.monotonic()
            if not fan_commanded and now >= fan_on_at:
                tx(h,'fan','on',906118656)
                fan_commanded=True; phase='fan_on'; raw_markers.append({'t':now-start,'event':'fan_on'})
                print('VENT_ID_FAN_ON')
            if fan_commanded and phase=='fan_on' and now >= fan_off_at:
                tx(h,'fan','off',1040336384)
                phase='recovery'; raw_markers.append({'t':now-start,'event':'fan_off'})
                print('VENT_ID_FAN_OFF')

            chunk=h.read(4096)
            if chunk:
                line_buffer += chunk.decode(errors='replace')
                while '\n' in line_buffer:
                    line,line_buffer=line_buffer.split('\n',1)
                    m=telemetry_re.search(line)
                    if not m: continue
                    if m.group('sha') != EXPECTED: continue
                    if m.group('outputs') != 'fake-locked':
                        raise RuntimeError('unexpected real output mode during ventilation identification')
                    row={'t':time.monotonic()-start,'phase':phase}
                    for key in ('scd_t','scd_rh','co2','tp_t','tp_rh','xm_t','xm_rh'):
                        row[key]=float(m.group(key))
                    row['storage']=m.group('storage')
                    row['write_errors']=int(m.group('write_errors')); row['queue_drops']=int(m.group('queue_drops'))
                    row['tp_ah']=abs_humidity_gm3(row['tp_t'],row['tp_rh'])
                    row['xm_ah']=abs_humidity_gm3(row['xm_t'],row['xm_rh'])
                    row['tp_dp']=dewpoint_c(row['tp_t'],row['tp_rh'])
                    row['xm_dp']=dewpoint_c(row['xm_t'],row['xm_rh'])
                    row['tp_vpd']=vpd_kpa(row['tp_t'],row['tp_rh'])
                    row['moisture_gradient']=row['tp_ah']-row['xm_ah']
                    rows.append(row)
                    if row['storage']!='sd' or row['write_errors']!=0 or row['queue_drops']!=0:
                        raise RuntimeError('SD telemetry degraded during ventilation identification')
                    if row['tp_t'] >= 28.0:
                        raise RuntimeError(f'authoritative TP357 temperature reached {row["tp_t"]:.2f}C')

            if now >= next_power:
                s=get_status(); p=float(s['apower']); master=bool(s.get('output',False))
                power.append({'t':now-start,'phase':phase,'p':p,'master':master})
                if not master: raise RuntimeError('Shelly master unexpectedly OFF')
                delta=p-p0
                if phase=='fan_on':
                    if delta > 8.0 or delta < -1.5:
                        raise RuntimeError(f'unexpected power while fan ON delta={delta:.3f}W')
                else:
                    if delta > 8.0:
                        raise RuntimeError(f'unexpected high power while fan OFF delta={delta:.3f}W')
                next_power=now+POWER_INTERVAL_S
    except Exception:
        unsafe=True
        raise
    finally:
        try: tx(h,'fan','off',1040336384)
        except Exception: unsafe=True
        try: tx(h,'lamp','off',16926208)
        except Exception: unsafe=True
        try: tx(h,'humidifier','off',771900928)
        except Exception: unsafe=True

# Allow Shelly and RF loads to settle after final OFF.
time.sleep(20)
final_samples=[]
for _ in range(9):
    final_samples.append(float(get_status()['apower'])); time.sleep(.4)
final_power=statistics.median(final_samples)
if abs(final_power-p0)>2.0:
    unsafe=True

if unsafe:
    set_master(False)
    raise SystemExit(f'Ventilation identification cleanup uncertain; final={final_power:.3f}W baseline={p0:.3f}W; master cutoff applied')

baseline_rows=[r for r in rows if r['phase']=='baseline']
fan_rows=[r for r in rows if r['phase']=='fan_on']
recovery_rows=[r for r in rows if r['phase']=='recovery']
if len(baseline_rows)<15 or len(fan_rows)<30 or len(recovery_rows)<15:
    raise SystemExit(f'Ventilation identification insufficient telemetry baseline={len(baseline_rows)} fan={len(fan_rows)} recovery={len(recovery_rows)}')

sb=summarize(baseline_rows); sf=summarize(fan_rows); sr=summarize(recovery_rows)
# Approximate fan effect using slope_ON - slope_baseline. This is an effect estimate,
# not a causal claim about outside CO2 because outside CO2 is not measured.
effect={
  'tp_t_slope_effect_per_min':sf['tp_t_slope_per_min']-sb['tp_t_slope_per_min'],
  'tp_ah_slope_effect_per_min':sf['tp_ah_slope_per_min']-sb['tp_ah_slope_per_min'],
  'co2_slope_effect_ppm_per_min':sf['co2_slope_per_min']-sb['co2_slope_per_min'],
  'inside_minus_intake_ah_baseline':sb['tp_ah_med']-sb['xm_ah_med'],
  'inside_minus_intake_ah_fan':sf['tp_ah_med']-sf['xm_ah_med'],
}
summary={'sha':EXPECTED,'baseline_power_w':p0,'final_power_w':final_power,'baseline':sb,'fan_on':sf,'recovery':sr,'effect':effect,'markers':raw_markers,'telemetry_count':len(rows),'power_count':len(power)}
Path('/tmp/growbox_ventilation_identification_v1.json').write_text(json.dumps(summary,indent=2,sort_keys=True))
print('VENT_ID_SUMMARY '+json.dumps(summary,sort_keys=True,separators=(',',':')))
print(f'VENT_ID_PASS sha={EXPECTED} telemetry={len(rows)} final_w={final_power:.3f} final=all_off master=on storage=sd')
PY

test -z "$(git status --porcelain)"
