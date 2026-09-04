#!/usr/bin/env bash
set -euo pipefail
EXPECTED=56813b27f6dc1f93d4899974ffd47a1528d8b6b8
test "$(git rev-parse HEAD)" = "$EXPECTED"
git fetch -q origin mvp/environment-controller
test "$(git rev-parse origin/mvp/environment-controller)" = "$EXPECTED"
test -z "$(git status --porcelain)"
trap 'git reset --hard "$EXPECTED" >/dev/null 2>&1 || true' EXIT
python3 - <<'PY'
from pathlib import Path
p = Path('src/climate/rf433/Rf433RmtLoopback.cpp')
s = p.read_text(encoding='utf-8')
s = s.replace("constexpr std::uint32_t kRxMinimumSignalNs = 20'000U;", "constexpr std::uint32_t kRxMinimumSignalNs = 1'250U;", 1)
s = s.replace("constexpr std::uint32_t kRxMaximumSignalNs = 300'000'000U;", "constexpr std::uint32_t kRxMaximumSignalNs = 12'000'000U;\nconstexpr std::uint32_t kRxResolutionHz = 1'000'000U;\nconstexpr std::uint32_t kRxToCodecTickRatio = kRxResolutionHz / kRmtResolutionHz;", 1)
old = '''  rmt_rx_channel_config_t rx_config{};\n  rx_config.gpio_num = static_cast<gpio_num_t>(config_.rx_gpio);\n  rx_config.clk_src = RMT_CLK_SRC_DEFAULT;\n  rx_config.resolution_hz = kRmtResolutionHz;\n  rx_config.mem_block_symbols = kRmtMemorySymbols;\n'''
new = '''  rmt_rx_channel_config_t rx_config{};\n  rx_config.gpio_num = static_cast<gpio_num_t>(config_.rx_gpio);\n  rx_config.clk_src = RMT_CLK_SRC_DEFAULT;\n  rx_config.resolution_hz = kRxResolutionHz;\n  rx_config.mem_block_symbols = kRmtMemorySymbols;\n'''
if old not in s:
    raise SystemExit('rx resolution anchor missing')
s = s.replace(old, new, 1)
old2 = '''    captured[i] = PulseSymbol{\n        static_cast<std::uint16_t>(input.duration0),\n        static_cast<std::uint16_t>(input.duration1),\n        input.level0 != 0U,\n        input.level1 != 0U,\n    };\n'''
new2 = '''    captured[i] = PulseSymbol{\n        static_cast<std::uint16_t>((input.duration0 + (kRxToCodecTickRatio / 2U)) / kRxToCodecTickRatio),\n        static_cast<std::uint16_t>((input.duration1 + (kRxToCodecTickRatio / 2U)) / kRxToCodecTickRatio),\n        input.level0 != 0U,\n        input.level1 != 0U,\n    };\n'''
if old2 not in s:
    raise SystemExit('RX duration conversion anchor missing')
s = s.replace(old2, new2, 1)
p.write_text(s, encoding='utf-8')
PY
git diff --check
PORT=$(.venv/bin/python -c 'from tools.stage27c_soak import detect_ch340_port; print(detect_ch340_port())')
echo "STAGE28B_PORT=$PORT"
export PORT
export GROWBOX_FIRMWARE_GIT_SHA="$EXPECTED"
export GROWBOX_STAGE27_SD_ENABLED=1
export GROWBOX_STAGE27_FLASH_FALLBACK_ENABLED=1
export GROWBOX_SD_CMD0_PRECONDITION=0
export GROWBOX_RF433_LOOPBACK_ENABLED=1
export GROWBOX_RF433_LOOPBACK_AUTO_SMOKE=1
export GROWBOX_RF433_TX_GPIO=8
export GROWBOX_RF433_RX_GPIO=14
export STAGE27C_BUILD_DIR=build/idf-stage28b-rx-glitch-probe-v1
scripts/stage27c_crowpanel.sh flash
OUT=/tmp/stage28b-rx-glitch-probe-v1
rm -rf "$OUT"
.venv/bin/python tools/stage27c_soak.py --port "$PORT" --output-dir "$OUT" --duration 90 --progress-seconds 30 --expected-sha "$EXPECTED" --require-sd --strict
.venv/bin/python - "$OUT" <<'PY'
from pathlib import Path
import sys
out = Path(sys.argv[1])
rf=[]
for p in sorted(out.glob('raw-*.log')):
    for line in p.read_text(encoding='utf-8', errors='replace').splitlines():
        if 'rf433_loopback_v=1 ' in line:
            rf.append(line)
assert rf, 'no RF loopback evidence'
line = rf[-1]
print('STAGE28B_RX_GLITCH_RF_RESULT', line)
fields={}
for tok in line.split('rf433_loopback_v=1 ',1)[1].split():
    if '=' in tok:
        k,v=tok.split('=',1); fields[k]=v
def iv(k): return int(fields[k],0)
assert iv('rx_arm_errors') == 0, fields
assert iv('tx_queued') == 1 and iv('tx_started') == 1 and iv('tx_completed') == 1, fields
print('STAGE28B_RX_GLITCH_ARM_OK')
if iv('pass') == 1:
    assert iv('rx_captured') == 1
    assert iv('decode_status') == 0
    assert iv('decoded_code') == 0xA55A
    assert iv('decoded_bits') == 16
    assert iv('decoded_protocol') == 1
    assert iv('classification') == 1
    print('STAGE28B_RX_GLITCH_LOOPBACK_PASS')
else:
    print('STAGE28B_RX_GLITCH_LOOPBACK_NOT_YET_PASS', fields)
PY
printf 'STAGE28B_RF_RX_GLITCH_FILTER_PROBE_OK\n'
