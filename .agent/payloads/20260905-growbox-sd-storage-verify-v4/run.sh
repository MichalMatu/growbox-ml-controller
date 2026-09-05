#!/usr/bin/env bash
set -euo pipefail
BASE=905327a740dd2a55820725faa2e6628256799289
BRANCH=mvp/environment-controller
ROOT="$(pwd)"

git fetch -q origin "$BRANCH"
git reset --hard "$BASE" >/dev/null
test "$(git rev-parse HEAD)" = "$BASE"
test "$(git rev-parse origin/$BRANCH)" = "$BASE"
test -z "$(git status --porcelain)"

python3 - <<'PY'
from pathlib import Path
p=Path('src/climate/runtime/Stage28ServiceConsole.cpp')
s=p.read_text()
old='constexpr char kSdSelfTestPath[] = "/sdcard/GBLOG/.SELFTEST";'
new='constexpr char kSdSelfTestPath[] = "/sdcard/GBLOG/STEST.TMP";'
if old not in s:
    raise SystemExit('selftest path target missing')
p.write_text(s.replace(old,new,1))
PY

git diff --check
export STAGE27C_BUILD_DIR=build/idf-sd-storage-verify-v4
export GROWBOX_STAGE27_SD_ENABLED=1
export GROWBOX_STAGE27_FLASH_FALLBACK_ENABLED=1
export GROWBOX_SD_CMD0_PRECONDITION=0
export GROWBOX_RF433_LOOPBACK_ENABLED=0
export GROWBOX_RF433_LOOPBACK_AUTO_SMOKE=0
export GROWBOX_RF433_REMOTE_CAPTURE_ENABLED=0
export GROWBOX_STAGE28_SERVICE_CONSOLE_ENABLED=1
export GROWBOX_STAGE28_REAL_OUTPUTS_ENABLED=0
export GROWBOX_STAGE28_THERMAL_TEST_SEQUENCE_ENABLED=0
scripts/stage27c_crowpanel.sh build

git add src/climate/runtime/Stage28ServiceConsole.cpp
git commit -m "Use FAT-compatible SD self-test filename"
NEW_SHA="$(git rev-parse HEAD)"
git push origin HEAD:"$BRANCH"
test "$(git rev-parse origin/$BRANCH)" = "$NEW_SHA" || git fetch -q origin "$BRANCH"
test "$(git rev-parse origin/$BRANCH)" = "$NEW_SHA"
export GROWBOX_FIRMWARE_GIT_SHA="$NEW_SHA"

PY="$ROOT/.venv/bin/python"
if [[ ! -x "$PY" ]]; then PY="$(command -v python3)"; fi
PORT="$($PY -c 'from tools.stage27c_soak import detect_ch340_port; print(detect_ch340_port())')"
if [[ -z "$PORT" ]]; then echo "SD_V4_FAIL reason=no_crowpanel_port"; exit 2; fi
echo "SD_V4_PORT=$PORT"
PORT="$PORT" scripts/stage27c_crowpanel.sh flash

cat >/tmp/growbox_sd_v4_probe.py <<'PY'
import base64, hashlib, os, re, sys, time, zlib
import serial
port,outdir=sys.argv[1:3]
os.makedirs(outdir,exist_ok=True)
STATUS_RE=re.compile(r"sdlog_status available=1 active=(\S+) sd_mounted=(\d+) sd_mount_errors=(\d+) write_errors=(\d+) queue_drops=(\d+) records_written=(\d+) records_skipped=(\d+) sd_recoveries=(\d+) last_write_ms=(\d+)")
FILE_RE=re.compile(r"sdlog_file name=([0-9A-Fa-f]{8}\.JL) size=(\d+)")
CHUNK_RE=re.compile(r"sdlog_chunk name=([0-9A-Fa-f]{8}\.JL) offset=(\d+) size=(\d+) file_size=(\d+) eof=(\d) crc32=([0-9A-Fa-f]{8}) b64=(\S*)")
ser=serial.Serial(port,115200,timeout=0.2,write_timeout=2)
try:
    try: ser.dtr=False; ser.rts=False
    except Exception: pass
    def read_for(sec,label):
        end=time.monotonic()+sec
        while time.monotonic()<end:
            raw=ser.readline()
            if raw: print(label,raw.decode('utf-8','replace').rstrip())
    def cmd(text,terminal,timeout=7):
        ser.write((text+'\n').encode()); ser.flush(); end=time.monotonic()+timeout; lines=[]
        while time.monotonic()<end:
            raw=ser.readline()
            if not raw: continue
            line=raw.decode('utf-8','replace').strip(); print('CMD',text,line); lines.append(line)
            if line.startswith(terminal): return lines
            if line.startswith('sdlog_error'): raise RuntimeError(line)
        raise TimeoutError(text)
    read_for(12,'BOOT')
    sl=cmd('sdlog status','sdlog_status')
    m=next((STATUS_RE.fullmatch(x) for x in reversed(sl) if STATUS_RE.fullmatch(x)),None)
    if not m: raise RuntimeError('unparseable status')
    status=dict(active=m.group(1),sd_mounted=int(m.group(2)),sd_mount_errors=int(m.group(3)),write_errors=int(m.group(4)),queue_drops=int(m.group(5)),records_written=int(m.group(6)),records_skipped=int(m.group(7)),sd_recoveries=int(m.group(8)),last_write_ms=int(m.group(9)))
    print('STATUS',status)
    if not status['sd_mounted'] or status['write_errors'] or status['records_written']==0: raise RuntimeError(f'bad logger status {status}')
    st=cmd('sdlog selftest','sdlog_selftest')[-1]
    if 'ok=1' not in st or 'readback=1' not in st or 'cleanup=1' not in st: raise RuntimeError('selftest failed '+st)
    read_for(12,'POST')
    lines=cmd('sdlog list','sdlog_list_end')
    files=[]
    for x in lines:
        mm=FILE_RE.fullmatch(x)
        if mm: files.append((mm.group(1),int(mm.group(2))))
    nonzero=[x for x in files if x[1]>0]
    print('FILES',files)
    if not nonzero: raise RuntimeError('no nonzero JL files')
    name,expected=max(nonzero,key=lambda x:x[1])
    path=os.path.join(outdir,name); off=0; h=hashlib.sha256()
    with open(path,'wb') as f:
        while off<expected:
            n=min(384,expected-off)
            ls=cmd(f'sdlog read {name} {off} {n}','sdlog_chunk')
            mm=next((CHUNK_RE.fullmatch(x) for x in reversed(ls) if CHUNK_RE.fullmatch(x)),None)
            if not mm: raise RuntimeError('missing chunk')
            data=base64.b64decode(mm.group(7),validate=True)
            if int(mm.group(2))!=off or len(data)!=int(mm.group(3)): raise RuntimeError('chunk geometry')
            if (zlib.crc32(data)&0xffffffff)!=int(mm.group(6),16): raise RuntimeError('crc mismatch')
            if not data: raise RuntimeError('empty chunk')
            f.write(data); h.update(data); off+=len(data)
        f.flush(); os.fsync(f.fileno())
    raw=open(path,'rb').read()
    if off!=expected or not raw.endswith(b'\n'): raise RuntimeError('snapshot invariant')
    for i,line in enumerate(raw.splitlines(),1):
        t=line.strip()
        if not (t.startswith(b'{') and t.endswith(b'}')): raise RuntimeError(f'line {i} envelope')
    print(f'PULLED name={name} size={off} sha256={h.hexdigest()} lines={len(raw.splitlines())}')
    print('SD_V4_PASS')
finally:
    ser.close()
PY
OUT="$ROOT/.agent-hw-artifacts/sd-storage-verify-v4"
rm -rf "$OUT"; mkdir -p "$OUT"
set +e
"$PY" /tmp/growbox_sd_v4_probe.py "$PORT" "$OUT" | tee "$OUT/probe.log"
RC=${PIPESTATUS[0]}
set -e
find "$OUT" -maxdepth 1 -type f -print0 | sort -z | xargs -0 shasum -a 256 || true
echo "SD_V4_FINAL commit=$NEW_SHA real_outputs=0 rf_transport=0 thermal_test=0 rc=$RC"
exit "$RC"
