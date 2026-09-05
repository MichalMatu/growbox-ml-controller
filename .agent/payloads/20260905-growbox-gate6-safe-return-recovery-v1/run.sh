#!/usr/bin/env bash
set -euo pipefail

EXPECTED=d9d6b40038129e6499d0fd092b628f31f867e20b
BRANCH=mvp/environment-controller
SAFE_BUILD=build/idf-gate6-safe-return-recovery
ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

git fetch -q origin "$BRANCH"
git reset --hard "$EXPECTED" >/dev/null
test "$(git rev-parse HEAD)" = "$EXPECTED"
test "$(git rev-parse origin/$BRANCH)" = "$EXPECTED"
test -z "$(git status --porcelain)"

export CMAKE_BUILD_PARALLEL_LEVEL=1
GROWBOX_RF433_LOOPBACK_ENABLED=1 \
GROWBOX_STAGE28_REAL_OUTPUTS_ENABLED=0 \
GROWBOX_STAGE28_THERMAL_TEST_SEQUENCE_ENABLED=0 \
GROWBOX_FIRMWARE_GIT_SHA="$EXPECTED" \
STAGE27C_BUILD_DIR="$SAFE_BUILD" \
bash scripts/stage27c_crowpanel.sh build

grep -q '^GROWBOX_STAGE28_REAL_OUTPUTS_ENABLED:STRING=0$' "$SAFE_BUILD/CMakeCache.txt"
grep -q '^GROWBOX_STAGE28_THERMAL_TEST_SEQUENCE_ENABLED:STRING=0$' "$SAFE_BUILD/CMakeCache.txt"
grep -q '^GROWBOX_RF433_LOOPBACK_ENABLED:STRING=1$' "$SAFE_BUILD/CMakeCache.txt"

GROWBOX_RF433_LOOPBACK_ENABLED=1 \
GROWBOX_STAGE28_REAL_OUTPUTS_ENABLED=0 \
GROWBOX_STAGE28_THERMAL_TEST_SEQUENCE_ENABLED=0 \
GROWBOX_FIRMWARE_GIT_SHA="$EXPECTED" \
STAGE27C_BUILD_DIR="$SAFE_BUILD" \
bash scripts/stage27c_crowpanel.sh flash

PY="$ROOT/.venv/bin/python"
if [[ ! -x "$PY" ]]; then PY="$(command -v python3)"; fi

"$PY" - "$EXPECTED" <<'PY'
import json
import statistics
import sys
import time
import urllib.request
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
    rpc('Switch.Set',{'id':0,'on':bool(on),'tag':'growbox-gate6-safe-return-recovery'})
    time.sleep(1)
    s=get_status()
    if bool(s.get('output',False)) != bool(on):
        raise RuntimeError('Shelly master readback mismatch')
    return s

def collect(h,d):
    end=time.monotonic()+d
    out=[]
    while time.monotonic()<end:
        b=h.read(4096)
        if b: out.append(b)
    return b''.join(out).decode(errors='replace')

def send(h,text,d=2.0):
    h.write(text.encode()+b'\n'); h.flush(); return collect(h,d)

port=detect_ch340_port()
if not port:
    raise SystemExit('Gate6 recovery: CrowPanel serial port missing; Shelly master remains unchanged')
print('GATE6_RECOVERY_PORT',port)

# ESP-IDF can take several seconds after reset before the UART console is ready.
status_text=''
with serial.Serial(port,115200,timeout=.12,write_timeout=1) as h:
    try: h.dtr=False; h.rts=False
    except Exception: pass
    for attempt in range(15):
        time.sleep(1.5)
        try: h.reset_input_buffer()
        except Exception: pass
        text=send(h,'status',1.5)
        status_text += text
        if f'status firmware_sha={expected}' in text and 'outputs=fake-locked' in text and 'rf_ready=1' in text:
            print(f'GATE6_SAFE_FIRMWARE_CONFIRMED attempt={attempt+1} sha={expected} outputs=fake-locked rf_ready=1')
            break
    else:
        raise SystemExit('Gate6 recovery: exact-SHA fake-locked console status not observed; master remains fail-closed')

    # Restore power only after the safe firmware identity is proven, then force all
    # known RF sockets OFF before measuring the settled Shelly baseline.
    set_master(True)
    evidence=[]
    for dev,code in [('lamp',16926208),('fan',1040336384),('humidifier',771900928)]:
        ok=False
        for _ in range(3):
            text=send(h,f'rf {dev} off',2.2)
            evidence.append(text)
            if f'manual_rf_tx device={dev} state=off code={code}' in text and 'tx_queued=1 tx_started=1 tx_completed=1' in text:
                ok=True
                break
        if not ok:
            set_master(False)
            raise SystemExit(f'Gate6 recovery: failed to confirm RF OFF transmit for {dev}; master cutoff applied')

# Allow RF sockets, loads and Shelly metering to settle fully.
time.sleep(20)
vals=[]
volts=[]
for _ in range(11):
    s=get_status()
    if not bool(s.get('output',False)):
        raise SystemExit('Gate6 recovery: Shelly master unexpectedly OFF during baseline check')
    vals.append(float(s['apower']))
    volts.append(float(s['voltage']))
    time.sleep(.5)
p=statistics.median(vals)
v=statistics.median(volts)
print(f'GATE6_RECOVERY_BASELINE power_w={p:.3f} voltage_v={v:.2f} min_w={min(vals):.3f} max_w={max(vals):.3f}')
if p > 4.0 or max(vals) > 5.0:
    set_master(False)
    raise SystemExit('Gate6 recovery: settled power above safe all-off baseline; master cutoff applied')

print(f'GATE6_SAFE_RETURN_RECOVERY_PASS sha={expected} outputs=fake-locked power_w={p:.3f} all_rf_off=1 master=on')
PY

test -z "$(git status --porcelain)"
