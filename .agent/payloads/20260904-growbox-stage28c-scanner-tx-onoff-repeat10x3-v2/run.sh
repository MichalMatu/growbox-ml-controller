#!/usr/bin/env bash
set -euo pipefail

EXPECTED=00cc0137adb7aeaa6d69bb6781ac97cb0784c5ab
SRC=src/climate/ClimateV6RealInputRuntime.cpp
ORIG=/tmp/stage28c-repeat10x3-v2.orig.cpp
TEST_BUILD=build/idf-stage28c-repeat10x3-v2
SAFE_BUILD=build/idf-stage28c-repeat10x3-v2-safe
OUT=/tmp/stage28c-repeat10x3-v2

restore_source() {
  if [[ -f "$ORIG" ]]; then
    cp "$ORIG" "$SRC"
  fi
}
trap restore_source EXIT

test "$(git rev-parse HEAD)" = "$EXPECTED"
git fetch -q origin mvp/environment-controller
test "$(git rev-parse origin/mvp/environment-controller)" = "$EXPECTED"
test -z "$(git status --porcelain)"
cp "$SRC" "$ORIG"

PORT=$(.venv/bin/python -c 'from tools.stage27c_soak import detect_ch340_port; print(detect_ch340_port())')
echo "STAGE28C_REPEAT10X3_PORT=$PORT"

.venv/bin/python - "$SRC" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text(encoding='utf-8')

old_decl = '''  bool rf_smoke_attempted = false;\n  bool rf_capture_ready_logged = false;'''
new_decl = '''  std::uint8_t rf_smoke_sequence_index = 0U;\n  std::uint64_t rf_smoke_next_ms = 3'000U;\n  bool rf_capture_ready_logged = false;'''
assert old_decl in text
text = text.replace(old_decl, new_decl, 1)

old_head = '''    if (rf_loopback_ready && GROWBOX_RF433_LOOPBACK_AUTO_SMOKE != 0 &&\n        GROWBOX_RF433_REMOTE_CAPTURE_ENABLED == 0 && !rf_smoke_attempted &&\n        now_ms >= 3'000U) {\n      rf_smoke_attempted = true;\n      rf433::LoopbackEvidence evidence{};\n      const rf433::FrameConfig smoke{{0xA55AU, 16U, 1U}, 3U, 0U};\n      const bool passed = rf_loopback.transmitAndReceive(smoke, 1'500U, evidence);'''
new_head = '''    if (rf_loopback_ready && GROWBOX_RF433_LOOPBACK_AUTO_SMOKE != 0 &&\n        GROWBOX_RF433_REMOTE_CAPTURE_ENABLED == 0 && rf_smoke_sequence_index < 6U &&\n        now_ms >= rf_smoke_next_ms) {\n      const std::uint32_t code = (rf_smoke_sequence_index % 2U) == 0U\n                                     ? 906118656U\n                                     : 1040336384U;\n      rf433::LoopbackEvidence evidence{};\n      const rf433::FrameConfig smoke{{code, 32U, 2U}, 10U, 575U};\n      const bool passed = rf_loopback.transmitAndReceive(smoke, 1'500U, evidence);'''
assert old_head in text
text = text.replace(old_head, new_head, 1)

needle = '''          static_cast<unsigned long>(rf_diag.rx_interference));\n    }'''
replacement = '''          static_cast<unsigned long>(rf_diag.rx_interference));\n      ++rf_smoke_sequence_index;\n      rf_smoke_next_ms = now_ms + 2'000U;\n    }'''
assert needle in text
text = text.replace(needle, replacement, 1)
path.write_text(text, encoding='utf-8')
PY

export PORT
export GROWBOX_FIRMWARE_GIT_SHA="$EXPECTED"
export GROWBOX_STAGE27_SD_ENABLED=1
export GROWBOX_STAGE27_FLASH_FALLBACK_ENABLED=1
export GROWBOX_SD_CMD0_PRECONDITION=0
export GROWBOX_RF433_LOOPBACK_ENABLED=1
export GROWBOX_RF433_LOOPBACK_AUTO_SMOKE=1
export GROWBOX_RF433_REMOTE_CAPTURE_ENABLED=0
export GROWBOX_RF433_TX_GPIO=8
export GROWBOX_RF433_RX_GPIO=14
export STAGE27C_BUILD_DIR="$TEST_BUILD"

echo "STAGE28C_REPEAT10X3_FLASH_TEST sequence=ON,OFF,ON,OFF,ON,OFF repeat=10"
scripts/stage27c_crowpanel.sh flash

rm -rf "$OUT"
.venv/bin/python tools/stage27c_soak.py \
  --port "$PORT" \
  --output-dir "$OUT" \
  --duration 24 \
  --progress-seconds 6 \
  --expected-sha "$EXPECTED"

.venv/bin/python - "$OUT" <<'PY'
from pathlib import Path
import sys

out = Path(sys.argv[1])
lines = []
for path in sorted(out.glob('raw-*.log')):
    for line in path.read_text(encoding='utf-8', errors='replace').splitlines():
        if 'rf433_loopback_v=1 ' in line:
            lines.append(line)

assert len(lines) == 6, f'expected 6 TX lines, got {len(lines)}'
expected = [906118656, 1040336384] * 3
for index, (line, code) in enumerate(zip(lines, expected), 1):
    fields = {}
    for token in line.split('rf433_loopback_v=1 ', 1)[1].split():
        if '=' in token:
            k, v = token.split('=', 1)
            fields[k] = v
    assert int(fields['requested_code'], 0) == code, (index, fields)
    assert int(fields['requested_bits'], 0) == 32, fields
    assert int(fields['requested_protocol'], 0) == 2, fields
    assert int(fields['requested_repeat'], 0) == 10, fields
    assert int(fields['requested_pulse_us'], 0) == 575, fields
    assert int(fields['tx_queued'], 0) == 1, fields
    assert int(fields['tx_started'], 0) == 1, fields
    assert int(fields['tx_completed'], 0) == 1, fields
    assert fields.get('outputs') == 'fake-locked', fields
    print(f'STAGE28C_REPEAT10X3_SENT index={index} code={code} repeat=10 tx_completed=1')
print('STAGE28C_REPEAT10X3_TX_PASS')
PY

restore_source
trap - EXIT
test -z "$(git status --porcelain)"

# Restore the exact source firmware in passive RX-only mode so a later reboot cannot replay the test sequence.
export GROWBOX_RF433_LOOPBACK_AUTO_SMOKE=0
export GROWBOX_RF433_REMOTE_CAPTURE_ENABLED=1
export STAGE27C_BUILD_DIR="$SAFE_BUILD"
echo "STAGE28C_REPEAT10X3_RESTORE_SAFE_FIRMWARE"
scripts/stage27c_crowpanel.sh flash

test -z "$(git status --porcelain)"
printf 'STAGE28C_REPEAT10X3_DONE sha=%s sequence=ON,OFF,ON,OFF,ON,OFF repeat=10 safe_firmware_restored=1\n' "$EXPECTED"
