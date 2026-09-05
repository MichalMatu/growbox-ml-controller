#!/usr/bin/env bash
set -euo pipefail

EXPECTED_HEAD="87e700a5688051bdc6a95cad722b60334319f76d"
BRANCH="mvp/environment-controller"
ROOT="$(pwd)"

# Keep the workspace on the exact reviewed head. This task does not modify source or flash firmware.
git fetch -q origin "$BRANCH"
git reset --hard "$EXPECTED_HEAD" >/dev/null
test "$(git rev-parse HEAD)" = "$EXPECTED_HEAD"
test "$(git rev-parse origin/$BRANCH)" = "$EXPECTED_HEAD"

# shellcheck disable=SC1091
source "$ROOT/scripts/source_idf.sh"
PY="$ROOT/.venv/bin/python"
if [[ ! -x "$PY" ]]; then PY="$(command -v python3)"; fi
PORT="$($PY -c 'from tools.stage27c_soak import detect_ch340_port; print(detect_ch340_port())')"
if [[ -z "$PORT" ]]; then
  echo "SD_REBOOT_FAIL reason=no_crowpanel_port"
  exit 2
fi
echo "SD_REBOOT_PORT=$PORT"

# Proven lower bounds from the successful USB export immediately before this task.
# After a reset these existing durable files must never shrink or disappear.
cat > /tmp/growbox_sd_reboot_probe.py <<'PY'
import base64, hashlib, json, os, re, sys, time, zlib
import serial

port=sys.argv[1]
out=sys.argv[2]
os.makedirs(out, exist_ok=True)
BASELINE={
  'CC6D2B5D.JL':16107,
  'B805E252.JL':884,
  '693DD8B7.JL':14407,
  'BA3FF450.JL':4006,
  '1575EF88.JL':644,
}
FILE_RE=re.compile(r"sdlog_file name=([0-9A-Fa-f]{8}\.JL) size=(\d+)")
STATUS_RE=re.compile(r"sdlog_status available=1 active=(\S+) sd_mounted=(\d+) sd_mount_errors=(\d+) write_errors=(\d+) queue_drops=(\d+) records_written=(\d+) records_skipped=(\d+) sd_recoveries=(\d+) last_write_ms=(\d+)")
CHUNK_RE=re.compile(r"sdlog_chunk name=([0-9A-Fa-f]{8}\.JL) offset=(\d+) size=(\d+) file_size=(\d+) eof=(\d) crc32=([0-9A-Fa-f]{8}) b64=(\S*)")

ser=serial.Serial(port,115200,timeout=0.2,write_timeout=2)
try:
  try:
    ser.dtr=False; ser.rts=False
  except Exception:
    pass
  time.sleep(12.0)
  ser.reset_input_buffer()

  def command(cmd, terminal, timeout=7.0):
    ser.write((cmd+'\n').encode('ascii')); ser.flush()
    end=time.monotonic()+timeout; lines=[]
    while time.monotonic()<end:
      raw=ser.readline()
      if not raw: continue
      line=raw.decode('utf-8','replace').strip()
      print('CMD',cmd,line)
      if line.startswith('sdlog_error') or line.startswith('sdlog_selftest ok=0'):
        raise RuntimeError(line)
      if line.startswith('sdlog_'): lines.append(line)
      if line.startswith(terminal): return lines
    raise TimeoutError(f'timeout after {cmd!r}')

  def status():
    for line in reversed(command('sdlog status','sdlog_status')):
      m=STATUS_RE.fullmatch(line)
      if m:
        return {'active':m.group(1),'sd_mounted':int(m.group(2)),'sd_mount_errors':int(m.group(3)),
                'write_errors':int(m.group(4)),'queue_drops':int(m.group(5)),
                'records_written':int(m.group(6)),'records_skipped':int(m.group(7)),
                'sd_recoveries':int(m.group(8)),'last_write_ms':int(m.group(9))}
    raise RuntimeError('missing status')

  def listing():
    files={}
    for line in command('sdlog list','sdlog_list_end'):
      m=FILE_RE.fullmatch(line)
      if m: files[m.group(1).upper()]=int(m.group(2))
    return files

  st1=status(); print('STATUS1',st1)
  if st1['sd_mounted']!=1 or st1['active']!='sd' or st1['write_errors']!=0:
    raise RuntimeError(f'bad post-reset status {st1}')
  first=listing(); print('LIST1',first)
  for name,minimum in BASELINE.items():
    if name not in first: raise RuntimeError(f'durable file disappeared: {name}')
    if first[name] < minimum: raise RuntimeError(f'durable file shrank: {name} {first[name]} < {minimum}')

  # New reset session must have a durable non-zero header immediately, then grow with telemetry.
  new1={k:v for k,v in first.items() if k not in BASELINE}
  if not new1 or not any(v>0 for v in new1.values()):
    raise RuntimeError(f'no non-zero post-reset session: {new1}')
  time.sleep(15.0)
  st2=status(); second=listing(); print('STATUS2',st2); print('LIST2',second)
  if st2['sd_mounted']!=1 or st2['write_errors']!=0 or st2['records_written']<2:
    raise RuntimeError(f'logger unhealthy after telemetry window: {st2}')
  for name,minimum in BASELINE.items():
    if second.get(name,-1) < minimum: raise RuntimeError(f'old file lost/shrank after telemetry: {name}')
  new2={k:v for k,v in second.items() if k not in BASELINE and v>0}
  if not new2: raise RuntimeError('no durable new session after telemetry window')

  selftest=command('sdlog selftest','sdlog_selftest')[-1]
  if 'ok=1' not in selftest or 'readback=1' not in selftest or 'cleanup=1' not in selftest:
    raise RuntimeError('selftest failed: '+selftest)

  def chunk(name,offset,length):
    last=''
    for attempt in range(1,7):
      lines=command(f'sdlog read {name} {offset} {length}','sdlog_chunk')
      for line in reversed(lines):
        m=CHUNK_RE.fullmatch(line)
        if not m: continue
        try:
          data=base64.b64decode(m.group(7),validate=True)
        except Exception as e:
          last=f'base64 {e}'; continue
        if int(m.group(2))!=offset or len(data)!=int(m.group(3)):
          last='offset/size mismatch'; continue
        if (zlib.crc32(data)&0xffffffff)!=int(m.group(6),16):
          last='crc mismatch'; continue
        if attempt>1: print(f'recovered chunk {name} offset={offset} attempt={attempt}')
        return data,int(m.group(4))
      last='missing parseable chunk'
      time.sleep(0.08)
    raise RuntimeError(f'{name} offset={offset}: {last}')

  # Pull the largest new post-reset session snapshot through the same USB protocol.
  name,expected=max(new2.items(), key=lambda kv:kv[1])
  path=os.path.join(out,name); off=0; h=hashlib.sha256()
  with open(path,'wb') as f:
    while off<expected:
      data,file_size=chunk(name,off,min(256,expected-off))
      if file_size<expected: raise RuntimeError(f'{name} shrank during pull')
      if not data: raise RuntimeError(f'{name} empty chunk at {off}')
      f.write(data); h.update(data); off+=len(data)
    f.flush(); os.fsync(f.fileno())
  raw=open(path,'rb').read()
  if len(raw)!=expected or not raw.endswith(b'\n'):
    raise RuntimeError('pulled snapshot size/newline invalid')
  rows=[json.loads(x) for x in raw.decode('utf-8').splitlines()]
  if len(rows)<2 or rows[0].get('t')!='session':
    raise RuntimeError('post-reset JL lacks session header + records')
  print(f'SD_REBOOT_PULL name={name} size={expected} lines={len(rows)} sha256={h.hexdigest()}')
  print('SD_REBOOT_PERSISTENCE_PASS',{'status':st2,'selftest':selftest,'new_files':new2})
finally:
  ser.close()
PY

OUT="$ROOT/.agent-hw-artifacts/sd-reboot-persistence-v7"
rm -rf "$OUT"; mkdir -p "$OUT"

# Non-destructive hardware reset: esptool probes the ESP32-S3 and exits with the normal hard-reset path.
# No flash write, RF command, actuator command, or SD mutation is performed here beyond normal logger writes.
esptool.py --port "$PORT" chip_id | tee "$OUT/reset-probe.log"
"$PY" /tmp/growbox_sd_reboot_probe.py "$PORT" "$OUT" | tee "$OUT/probe.log"
find "$OUT" -maxdepth 1 -type f -print0 | sort -z | xargs -0 shasum -a 256 || true

echo "SD_REBOOT_PERSISTENCE_V7_COMPLETE head=$EXPECTED_HEAD real_outputs=0 rf_transport=0 thermal_test=0 no_flash=1"
