#!/usr/bin/env bash
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"
git fetch -q origin agent-control
BASE=/tmp/growbox-fan-short-diagnostic-v1-base.sh
FINAL=/tmp/growbox-fan-short-diagnostic-v2-final.sh
git show origin/agent-control:.agent/payloads/20260905-growbox-fan-short-diagnostic-v1/run.sh > "$BASE"
python3 - "$BASE" "$FINAL" <<'PY'
import pathlib,sys
src=pathlib.Path(sys.argv[1]).read_text()
src=src.replace('idf-fan-short-diagnostic-v1','idf-fan-short-diagnostic-v2')
src=src.replace('idf-fan-short-safe-return-v1','idf-fan-short-safe-return-v2')
helper='''import glob\ndef detect_ch340_port():\n    matches=[]\n    for port in sorted(set(glob.glob('/dev/cu.usbserial-*'))):\n        text=''\n        try:\n            with serial.Serial(port,115200,timeout=.08,write_timeout=1) as probe:\n                try: probe.dtr=False; probe.rts=False\n                except Exception: pass\n                time.sleep(.4); probe.reset_input_buffer(); probe.write(b'status\\n'); probe.flush()\n                end=time.monotonic()+2.0\n                while time.monotonic()<end:\n                    chunk=probe.read(4096)\n                    if chunk: text += chunk.decode(errors='replace')\n            if 'firmware_sha=' in text and ('outputs=' in text or 'rf_ready=1' in text):\n                matches.append(port)\n        except Exception:\n            pass\n    if len(matches)!=1:\n        raise RuntimeError('growbox serial selection expected exactly one matching adapter, got: '+', '.join(matches))\n    print('FAN_DIAG_PORT_SELECTED '+matches[0],flush=True)\n    return matches[0]\n'''
needle='from tools.stage27c_soak import detect_ch340_port\n'
count=src.count(needle)
if count!=3:
    raise SystemExit(f'expected 3 serial helper imports, got {count}')
src=src.replace(needle,helper)
pathlib.Path(sys.argv[2]).write_text(src)
PY
bash -n "$FINAL"
exec "$FINAL"
