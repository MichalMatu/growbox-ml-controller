#!/usr/bin/env bash
set -euo pipefail
EXPECTED=5eba9bef297bd141814eda78d8aff55dc12231dd
BRANCH=mvp/environment-controller

git fetch -q origin "$BRANCH"
git reset --hard "$EXPECTED" >/dev/null
test "$(git rev-parse HEAD)" = "$EXPECTED"
test "$(git rev-parse origin/$BRANCH)" = "$EXPECTED"
test -z "$(git status --porcelain)"

python3 - <<'PY'
from pathlib import Path
p=Path('scripts/growbox_log_pull.py')
s=p.read_text()
s=s.replace("FILE_RE=re.compile(r\"sdlog_file name=([0-9A-Fa-f]{8}\\.JL) size=(\\d+)\")\n", "FILE_RE=re.compile(r\"sdlog_file name=([0-9A-Fa-f]{8}\\.JL) size=(\\d+)\")\nCHUNK_BYTES=256\nCHUNK_RETRIES=8\n")
s=s.replace("        self.ser=serial.Serial(port, baudrate=baud, timeout=0.2, write_timeout=2)\n        self.deadline=timeout\n        time.sleep(0.25); self.ser.reset_input_buffer()\n", "        self.ser=serial.Serial()\n        self.ser.port=port; self.ser.baudrate=baud; self.ser.timeout=0.2; self.ser.write_timeout=2\n        try:\n            self.ser.dtr=False; self.ser.rts=False\n        except Exception:\n            pass\n        self.ser.open()\n        self.deadline=timeout\n        time.sleep(2.5); self.ser.reset_input_buffer()\n")
old='''    def chunk(self,name,offset,length):\n        lines=self.command_lines(f'sdlog read {name} {offset} {length}','sdlog_chunk')\n        for line in reversed(lines):\n            m=CHUNK_RE.fullmatch(line)\n            if m:\n                data=base64.b64decode(m.group(7),validate=True)\n                if len(data)!=int(m.group(3)): raise RuntimeError('chunk size mismatch')\n                if (zlib.crc32(data)&0xffffffff)!=int(m.group(6),16): raise RuntimeError('chunk CRC32 mismatch')\n                if int(m.group(2))!=offset: raise RuntimeError('chunk offset mismatch')\n                return data,int(m.group(4)),bool(int(m.group(5)))\n        raise RuntimeError('missing sdlog_chunk response')\n'''
new='''    def chunk(self,name,offset,length):\n        last_error='missing sdlog_chunk response'\n        for attempt in range(1,CHUNK_RETRIES+1):\n            try:\n                lines=self.command_lines(f'sdlog read {name} {offset} {length}','sdlog_chunk')\n            except TimeoutError as exc:\n                last_error=str(exc)\n                time.sleep(0.05)\n                continue\n            for line in reversed(lines):\n                m=CHUNK_RE.fullmatch(line)\n                if not m:\n                    continue\n                try:\n                    data=base64.b64decode(m.group(7),validate=True)\n                    if len(data)!=int(m.group(3)): raise ValueError('chunk size mismatch')\n                    if (zlib.crc32(data)&0xffffffff)!=int(m.group(6),16): raise ValueError('chunk CRC32 mismatch')\n                    if int(m.group(2))!=offset: raise ValueError('chunk offset mismatch')\n                except Exception as exc:\n                    last_error=str(exc)\n                    break\n                if attempt>1:\n                    print(f'recovered chunk {name} offset={offset} attempt={attempt}',file=sys.stderr)\n                return data,int(m.group(4)),bool(int(m.group(5)))\n            else:\n                last_error='missing/garbled sdlog_chunk response'\n            time.sleep(0.05)\n        raise RuntimeError(f'{name}: chunk offset={offset} failed after {CHUNK_RETRIES} attempts: {last_error}')\n'''
if old not in s: raise SystemExit('chunk target missing')
s=s.replace(old,new,1)
s=s.replace("            data,file_size,eof=console.chunk(name,offset,min(384,expected_size-offset))\n", "            data,file_size,eof=console.chunk(name,offset,min(CHUNK_BYTES,expected_size-offset))\n")
p.write_text(s)
PY

python3 -m py_compile scripts/growbox_log_pull.py
python3 - <<'PY'
import base64, importlib.util, zlib
spec=importlib.util.spec_from_file_location('glp','scripts/growbox_log_pull.py'); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
c=m.Console.__new__(m.Console)
payload=b'abc'; crc=zlib.crc32(payload)&0xffffffff
bad='sdlog_chunk name=ABCDEF12.JL offset=0 size=3 file_size=3 eof=1 crc32=%08X b64=YW I (123) noise' % crc
good='sdlog_chunk name=ABCDEF12.JL offset=0 size=3 file_size=3 eof=1 crc32=%08X b64=%s' % (crc,base64.b64encode(payload).decode())
responses=[[bad],[good]]; calls=[]
def fake(command,prefix): calls.append(command); return responses.pop(0)
c.command_lines=fake
out=c.chunk('ABCDEF12.JL',0,3)
assert out==(payload,3,True),out
assert len(calls)==2,calls
print('USB_RETRY_REGRESSION_PASS')
PY

git diff --check
git add scripts/growbox_log_pull.py
git commit -m 'Retry SD USB chunks when console logs interleave'
git push origin HEAD:"$BRANCH"
NEW_HEAD="$(git rev-parse HEAD)"
test "$(git rev-parse origin/$BRANCH)" = "$NEW_HEAD"

PY="$PWD/.venv/bin/python"; [[ -x "$PY" ]] || PY="$(command -v python3)"
PORT="$($PY -c 'from tools.stage27c_soak import detect_ch340_port; print(detect_ch340_port())')"
[[ -n "$PORT" ]]
OUT="$PWD/.agent-hw-artifacts/sd-usb-retry-v5"
rm -rf "$OUT"; mkdir -p "$OUT"
"$PY" scripts/growbox_log_pull.py pull-all --port "$PORT" --timeout 8 --out "$OUT" | tee "$OUT/pull.log"
python3 - "$OUT" <<'PY'
import json, os, pathlib, sys, hashlib
root=pathlib.Path(sys.argv[1])
files=[p for p in root.glob('*.JL') if p.stat().st_size>0]
assert files, 'no non-zero JL files downloaded'
validated=[]
for p in files:
    raw=p.read_bytes()
    assert raw.endswith(b'\n'), f'{p.name}: no final newline'
    lines=raw.splitlines()
    for i,line in enumerate(lines,1):
        obj=json.loads(line)
        assert isinstance(obj,dict), (p.name,i)
    validated.append((p.name,len(raw),len(lines),hashlib.sha256(raw).hexdigest()))
print('SD_USB_EXPORT_PASS',validated)
PY

echo "SD_USB_RETRY_V5_COMPLETE commit=$NEW_HEAD firmware_running=5eba9bef297bd141814eda78d8aff55dc12231dd real_outputs=0 rf_transport=0 thermal_test=0"
