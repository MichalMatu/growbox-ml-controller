#!/usr/bin/env bash
set -euo pipefail
EXPECTED=00cc0137adb7aeaa6d69bb6781ac97cb0784c5ab

test "$(git rev-parse HEAD)" = "$EXPECTED"
git fetch -q origin mvp/environment-controller
test "$(git rev-parse origin/mvp/environment-controller)" = "$EXPECTED"
test -z "$(git status --porcelain)"

PORT=$(.venv/bin/python -c 'from tools.stage27c_soak import detect_ch340_port; print(detect_ch340_port())')
echo "STAGE28C_MANUAL_CAPTURE_PORT=$PORT"

OUT=/tmp/stage28c-manual-onoff-capture-v1
rm -rf "$OUT"
mkdir -p "$OUT"

.venv/bin/python tools/stage27c_soak.py \
  --port "$PORT" \
  --output-dir "$OUT" \
  --duration 120 \
  --progress-seconds 15 \
  --expected-sha "$EXPECTED"

.venv/bin/python - "$OUT" <<'PY'
from collections import Counter
from pathlib import Path
import json
import sys

out = Path(sys.argv[1])
headers = []
symbols = {}
for path in sorted(out.glob('raw-*.log')):
    for line in path.read_text(encoding='utf-8', errors='replace').splitlines():
        if 'rf433_remote_capture_v=1 ' in line:
            payload = line.split('rf433_remote_capture_v=1 ', 1)[1]
            fields = {}
            for token in payload.split():
                if '=' in token:
                    k, v = token.split('=', 1)
                    fields[k] = v
            headers.append(fields)
        elif 'rf433_remote_symbol_v=1 ' in line:
            payload = line.split('rf433_remote_symbol_v=1 ', 1)[1]
            fields = {}
            for token in payload.split():
                if '=' in token:
                    k, v = token.split('=', 1)
                    fields[k] = v
            cid = fields.get('capture_id')
            if cid is not None:
                symbols.setdefault(cid, []).append(fields)

print(f'STAGE28C_MANUAL_CAPTURE_HEADERS count={len(headers)}')
keys = [
    'capture_id','rx_start_ms','rx_finish_ms','symbol_count','overflow','decode_status',
    'decoded_code','decoded_bits','decoded_protocol','estimated_pulse_us',
    'observed_repeats','candidate_count','outputs'
]
for h in headers:
    compact = {k: h.get(k) for k in keys}
    cid = h.get('capture_id')
    compact['raw_symbol_lines'] = len(symbols.get(cid, []))
    print('STAGE28C_CAPTURE ' + json.dumps(compact, sort_keys=True))

identity_counts = Counter()
for h in headers:
    ident = (
        h.get('decode_status'), h.get('decoded_code'), h.get('decoded_bits'),
        h.get('decoded_protocol'), h.get('estimated_pulse_us'), h.get('observed_repeats'),
        h.get('candidate_count'), h.get('overflow')
    )
    identity_counts[ident] += 1
print('STAGE28C_IDENTITY_COUNTS ' + json.dumps([
    {
        'decode_status': ident[0], 'decoded_code': ident[1], 'decoded_bits': ident[2],
        'decoded_protocol': ident[3], 'estimated_pulse_us': ident[4],
        'observed_repeats': ident[5], 'candidate_count': ident[6], 'overflow': ident[7],
        'count': count,
    }
    for ident, count in identity_counts.items()
], sort_keys=True))

assert all(h.get('outputs') == 'fake-locked' for h in headers), 'outputs escaped fake-locked'
print(f'STAGE28C_MANUAL_CAPTURE_DONE captures={len(headers)} unique_identities={len(identity_counts)} sha={"00cc0137adb7aeaa6d69bb6781ac97cb0784c5ab"}')
PY

test -z "$(git status --porcelain)"
