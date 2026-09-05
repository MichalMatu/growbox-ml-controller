#!/usr/bin/env bash
set -euo pipefail

EXPECTED=dfc6dc86a47ad2158e36bb0d5241b0153dbce387
PORT=/dev/cu.usbserial-1130
BUILD_DIR=build/idf-current-safe-ah-observe-v1
ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

git fetch -q origin mvp/environment-controller
test "$(git rev-parse HEAD)" = "$EXPECTED"
test "$(git rev-parse origin/mvp/environment-controller)" = "$EXPECTED"
test -z "$(git status --porcelain)"
export CMAKE_BUILD_PARALLEL_LEVEL=1

GROWBOX_RF433_LOOPBACK_ENABLED=1 \
GROWBOX_RF433_LOOPBACK_AUTO_SMOKE=0 \
GROWBOX_STAGE28_REAL_OUTPUTS_ENABLED=0 \
GROWBOX_STAGE28_THERMAL_TEST_SEQUENCE_ENABLED=0 \
GROWBOX_FIRMWARE_GIT_SHA="$EXPECTED" \
STAGE27C_BUILD_DIR="$BUILD_DIR" \
PORT="$PORT" \
bash scripts/stage27c_crowpanel.sh flash

grep -q '^GROWBOX_STAGE28_REAL_OUTPUTS_ENABLED:STRING=0$' "$BUILD_DIR/CMakeCache.txt"
grep -q '^GROWBOX_STAGE28_THERMAL_TEST_SEQUENCE_ENABLED:STRING=0$' "$BUILD_DIR/CMakeCache.txt"
grep -q '^GROWBOX_RF433_LOOPBACK_ENABLED:STRING=1$' "$BUILD_DIR/CMakeCache.txt"

PY="$ROOT/.venv/bin/python"
if [[ ! -x "$PY" ]]; then PY="$(command -v python3)"; fi

"$PY" - "$EXPECTED" "$PORT" <<'PY'
import json,re,sys,time
import serial

EXPECTED=sys.argv[1]
PORT=sys.argv[2]
DURATION_S=180.0

h=serial.Serial(port=None,baudrate=115200,timeout=.08,write_timeout=1)
h.dtr=False; h.rts=False; h.port=PORT; h.open()
records=[]; lines=[]; buf=''
try:
    start=time.monotonic(); next_status=start+10.0; deadline=start+DURATION_S
    while time.monotonic()<deadline:
        now=time.monotonic()
        if now>=next_status:
            h.write(b'status\n'); h.flush(); next_status+=20.0
        b=h.read(4096)
        if not b: continue
        buf += b.decode(errors='replace')
        while '\n' in buf:
            line,buf=buf.split('\n',1); line=line.strip()
            if not line: continue
            if 'status firmware_sha=' in line or 'Stage27 real-input runtime:' in line:
                lines.append(line)
            if 'soak_v=2 ' not in line: continue
            def f(key,cast,default):
                m=re.search(r'(?:^|\s)'+re.escape(key)+r'=([^\s]+)',line)
                if not m: return default
                try: return cast(m.group(1))
                except Exception: return default
            r={
              'sha':f('firmware_sha',str,''),'uptime':f('uptime_ms',int,0),'mode':f('outputs',str,''),
              'storage':f('storage_backend',str,''),'we':f('storage_write_errors',int,0),'qd':f('storage_queue_drops',int,0),
              'xiaomi_sample':f('xiaomi_sample',int,0),'xiaomi_age':f('xiaomi_age_ms',int,0),
              'xiaomi_packets':f('xiaomi_packets',int,0),'xiaomi_accepted':f('xiaomi_accepted',int,0),'xiaomi_rejected':f('xiaomi_rejected',int,0),
              'xiaomi_t':f('xiaomi_t',float,0.0),'xiaomi_rh':f('xiaomi_rh',float,0.0),
              'tp_sample':f('tp_sample',int,0),'tp_t':f('tp_t',float,0.0),'tp_rh':f('tp_rh',float,0.0),
              'requested_fan':f('requested_fan',float,0.0),'requested_humidifier':f('requested_humidifier',float,0.0),
              'physical_fan':f('physical_fan',int,0),'real':f('outputs',str,'')=='real-bounded',
              'ble_scan_errors':f('ble_scan_errors',int,0),'ble_lock_drops':f('ble_adv_lock_drops',int,0)}
            if r['sha']!=EXPECTED:
                raise RuntimeError(f'unexpected firmware sha {r["sha"]}')
            if r['mode']!='fake-locked':
                raise RuntimeError(f'outputs unexpectedly not fake-locked: {r["mode"]}')
            if r['physical_fan']!=0:
                raise RuntimeError('physical fan unexpectedly on in fake-locked observation')
            if r['we']!=0 or r['qd']!=0:
                raise RuntimeError('storage error/drop during observation')
            records.append(r)
finally:
    h.close()

if len(records)<10:
    raise RuntimeError(f'insufficient telemetry records={len(records)}')
first,last=records[0],records[-1]
fresh=[r for r in records if r['xiaomi_sample'] and r['xiaomi_age']<=30000]
post120=[r for r in records if r['uptime']>=120000]
post120_req=[r for r in post120 if r['requested_fan']>=0.10]
summary={
 'sha':EXPECTED,'records':len(records),'first_uptime_ms':first['uptime'],'last_uptime_ms':last['uptime'],
 'max_requested_fan':max(r['requested_fan'] for r in records),
 'records_requested_fan_ge_010':sum(r['requested_fan']>=0.10 for r in records),
 'post120_records':len(post120),'post120_requested_fan_ge_010':len(post120_req),
 'fresh_xiaomi_records':len(fresh),'max_xiaomi_age_ms':max((r['xiaomi_age'] for r in records if r['xiaomi_sample']),default=None),
 'xiaomi_packet_delta':max(0,last['xiaomi_packets']-first['xiaomi_packets']),
 'xiaomi_accepted_delta':max(0,last['xiaomi_accepted']-first['xiaomi_accepted']),
 'xiaomi_rejected_delta':max(0,last['xiaomi_rejected']-first['xiaomi_rejected']),
 'ble_scan_errors_max':max(r['ble_scan_errors'] for r in records),'ble_lock_drops_max':max(r['ble_lock_drops'] for r in records),
 'first_tp':[first['tp_t'],first['tp_rh']],'last_tp':[last['tp_t'],last['tp_rh']],
 'first_xiaomi':[first['xiaomi_t'],first['xiaomi_rh']],'last_xiaomi':[last['xiaomi_t'],last['xiaomi_rh']],
 'status_lines':lines[-20:]}
print('CURRENT_SAFE_AH_OBSERVE_SUMMARY '+json.dumps(summary,sort_keys=True,separators=(',',':')),flush=True)
print('CURRENT_SAFE_AH_OBSERVE_PASS outputs=fake-locked rf_auto_tx=0 port='+PORT,flush=True)
PY
