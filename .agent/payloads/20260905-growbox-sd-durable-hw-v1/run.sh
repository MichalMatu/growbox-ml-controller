#!/usr/bin/env bash
set -euo pipefail

EXPECTED=905327a740dd2a55820725faa2e6628256799289
BRANCH=mvp/environment-controller
ROOT="$(pwd)"

cleanup() {
  true
}
trap cleanup EXIT

git fetch -q origin "$BRANCH"
git reset --hard "$EXPECTED" >/dev/null
test "$(git rev-parse HEAD)" = "$EXPECTED"
test "$(git rev-parse origin/$BRANCH)" = "$EXPECTED"
test -z "$(git status --porcelain)"

export STAGE27C_BUILD_DIR=build/idf-sd-durable-hw-v1
export GROWBOX_STAGE27_SD_ENABLED=1
export GROWBOX_STAGE27_FLASH_FALLBACK_ENABLED=1
export GROWBOX_SD_CMD0_PRECONDITION=0
export GROWBOX_RF433_LOOPBACK_ENABLED=0
export GROWBOX_RF433_LOOPBACK_AUTO_SMOKE=0
export GROWBOX_RF433_REMOTE_CAPTURE_ENABLED=0
export GROWBOX_STAGE28_SERVICE_CONSOLE_ENABLED=1
export GROWBOX_STAGE28_REAL_OUTPUTS_ENABLED=0
export GROWBOX_STAGE28_THERMAL_TEST_SEQUENCE_ENABLED=0
export GROWBOX_FIRMWARE_GIT_SHA="$EXPECTED"

PY="$ROOT/.venv/bin/python"
if [[ ! -x "$PY" ]]; then PY="$(command -v python3)"; fi

# Resolve the same CH340-backed CrowPanel port used by the established Stage27C workflow.
PORT="$($PY -c 'from tools.stage27c_soak import detect_ch340_port; print(detect_ch340_port())')"
if [[ -z "$PORT" ]]; then
  echo "SD_HW_FAIL reason=no_crowpanel_port"
  exit 2
fi
echo "SD_HW_PORT=$PORT"

# Safe diagnostic firmware only: real outputs OFF, RF transport OFF, thermal sequence OFF.
PORT="$PORT" scripts/stage27c_crowpanel.sh flash

cat > /tmp/growbox_sd_hw_probe.py <<'PY'
import base64
import hashlib
import os
import re
import sys
import time
import zlib

import serial

port=sys.argv[1]
out_dir=sys.argv[2]
os.makedirs(out_dir, exist_ok=True)

STATUS_RE=re.compile(r"sdlog_status available=1 active=(\S+) sd_mounted=(\d+) sd_mount_errors=(\d+) write_errors=(\d+) queue_drops=(\d+) records_written=(\d+) records_skipped=(\d+) sd_recoveries=(\d+) last_write_ms=(\d+)")
FILE_RE=re.compile(r"sdlog_file name=([0-9A-Fa-f]{8}\.JL) size=(\d+)")
CHUNK_RE=re.compile(r"sdlog_chunk name=([0-9A-Fa-f]{8}\.JL) offset=(\d+) size=(\d+) file_size=(\d+) eof=(\d) crc32=([0-9A-Fa-f]{8}) b64=(\S*)")

ser=serial.Serial(port, baudrate=115200, timeout=0.2, write_timeout=2)
try:
    # Avoid intentional line toggles after open where pyserial/platform permits it.
    try:
        ser.dtr=False
        ser.rts=False
    except Exception:
        pass

    def read_for(seconds, label):
        end=time.monotonic()+seconds
        lines=[]
        while time.monotonic()<end:
            raw=ser.readline()
            if not raw:
                continue
            line=raw.decode('utf-8','replace').rstrip('\r\n')
            print(f"{label} {line}")
            lines.append(line)
        return lines

    # Opening the CH340 may reset the target. Capture the resulting boot/logger diagnostics.
    boot=read_for(12.0, 'BOOT')

    def command(command, terminal_prefix, timeout=6.0, allow_error=False):
        ser.write((command+'\n').encode('ascii'))
        ser.flush()
        end=time.monotonic()+timeout
        lines=[]
        while time.monotonic()<end:
            raw=ser.readline()
            if not raw:
                continue
            line=raw.decode('utf-8','replace').strip()
            print(f"CMD[{command}] {line}")
            lines.append(line)
            if line.startswith(terminal_prefix):
                return lines
            if (line.startswith('sdlog_error') or line.startswith('sdlog_selftest ok=0')) and not allow_error:
                raise RuntimeError(line)
        raise TimeoutError(f"timeout waiting for {terminal_prefix!r} after {command!r}")

    def status():
        lines=command('sdlog status','sdlog_status')
        for line in reversed(lines):
            m=STATUS_RE.fullmatch(line)
            if m:
                return {
                    'active':m.group(1),'sd_mounted':int(m.group(2)),'sd_mount_errors':int(m.group(3)),
                    'write_errors':int(m.group(4)),'queue_drops':int(m.group(5)),
                    'records_written':int(m.group(6)),'records_skipped':int(m.group(7)),
                    'sd_recoveries':int(m.group(8)),'last_write_ms':int(m.group(9)),
                }
        raise RuntimeError('missing parseable sdlog_status')

    first=status()
    print('STATUS1', first)

    # If first session write caused deactivation, capture the intended 60 s retry rather than rebooting.
    if not first['sd_mounted']:
        print('SD_RETRY_OBSERVE start=1 seconds=65')
        read_for(65.0, 'RETRY')
        second=status()
        print('STATUS2', second)
    else:
        second=first

    if not second['sd_mounted']:
        raise RuntimeError(f"sd remained unmounted after retry observation: {second}")

    selftest_lines=command('sdlog selftest','sdlog_selftest', allow_error=True)
    selftest=[x for x in selftest_lines if x.startswith('sdlog_selftest')]
    if not selftest or 'ok=1' not in selftest[-1] or 'readback=1' not in selftest[-1] or 'cleanup=1' not in selftest[-1]:
        raise RuntimeError('SD durable selftest failed: '+(selftest[-1] if selftest else 'missing result'))

    # Give normal 10 s telemetry cadence a chance to append after boot/retry.
    read_for(12.0, 'POSTSELF')
    third=status()
    print('STATUS3', third)

    lines=command('sdlog list','sdlog_list_end')
    files=[]
    for line in lines:
        m=FILE_RE.fullmatch(line)
        if m:
            files.append((m.group(1),int(m.group(2))))
    print('FILES', files)
    nonzero=[x for x in files if x[1]>0]
    if not nonzero:
        raise RuntimeError('no non-zero GBLOG session after durable selftest and telemetry window')

    def chunk(name, offset, length):
        lines=command(f'sdlog read {name} {offset} {length}','sdlog_chunk')
        for line in reversed(lines):
            m=CHUNK_RE.fullmatch(line)
            if not m:
                continue
            data=base64.b64decode(m.group(7),validate=True)
            if int(m.group(2)) != offset:
                raise RuntimeError('chunk offset mismatch')
            if len(data) != int(m.group(3)):
                raise RuntimeError('chunk size mismatch')
            if (zlib.crc32(data)&0xffffffff) != int(m.group(6),16):
                raise RuntimeError('chunk CRC mismatch')
            return data,int(m.group(4)),bool(int(m.group(5)))
        raise RuntimeError('missing chunk response')

    pulled=[]
    for name, expected_size in nonzero:
        path=os.path.join(out_dir,name)
        offset=0
        digest=hashlib.sha256()
        with open(path,'wb') as f:
            while offset<expected_size:
                data,file_size,eof=chunk(name,offset,min(384,expected_size-offset))
                if file_size<expected_size:
                    raise RuntimeError(f'{name}: board file shrank')
                if not data:
                    raise RuntimeError(f'{name}: empty chunk at {offset}')
                f.write(data)
                digest.update(data)
                offset += len(data)
            f.flush(); os.fsync(f.fileno())
        if offset != expected_size:
            raise RuntimeError(f'{name}: pulled size {offset} != listed {expected_size}')
        sha=digest.hexdigest()
        print(f'PULLED name={name} size={offset} sha256={sha}')
        # JL/NDJSON invariant: complete stored records are newline-delimited JSON text.
        raw=open(path,'rb').read()
        if not raw.endswith(b'\n'):
            raise RuntimeError(f'{name}: does not end in newline')
        for idx,line in enumerate(raw.splitlines(),1):
            if not line.strip().startswith(b'{') or not line.strip().endswith(b'}'):
                raise RuntimeError(f'{name}: line {idx} is not a JSON object envelope')
        pulled.append((name,offset,sha,len(raw.splitlines())))

    if third['write_errors'] != 0:
        raise RuntimeError(f'logger still reports write_errors={third["write_errors"]}')
    if third['records_written'] == 0:
        raise RuntimeError('logger reports zero records_written')

    print('SD_HW_PASS', {'status':third,'selftest':selftest[-1],'pulled':pulled})
finally:
    ser.close()
PY

OUT="$ROOT/.agent-hw-artifacts/sd-durable-hw-v1"
rm -rf "$OUT"
mkdir -p "$OUT"
set +e
"$PY" /tmp/growbox_sd_hw_probe.py "$PORT" "$OUT" | tee "$OUT/probe.log"
PROBE_RC=${PIPESTATUS[0]}
set -e

# Report hashes for any extracted logs and keep firmware in the safe fake-output configuration.
find "$OUT" -maxdepth 1 -type f -print0 | sort -z | xargs -0 shasum -a 256 || true

echo "SD_HW_FINAL commit=$EXPECTED real_outputs=0 rf_transport=0 thermal_test=0 probe_rc=$PROBE_RC"
exit "$PROBE_RC"
