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
needle = "constexpr std::uint32_t kRxMaximumSignalNs = 300'000'000U;"
replacement = "constexpr std::uint32_t kRxMaximumSignalNs = 20'000'000U;\nconstexpr std::uint32_t kRxResolutionHz = 1'000'000U;\nconstexpr std::uint32_t kRxToCodecTickRatio = kRxResolutionHz / kRmtResolutionHz;"
if needle not in s:
    raise SystemExit('RX constant anchor missing')
s = s.replace(needle, replacement, 1)
old = """  rmt_rx_channel_config_t rx_config{};
  rx_config.gpio_num = static_cast<gpio_num_t>(config_.rx_gpio);
  rx_config.clk_src = RMT_CLK_SRC_DEFAULT;
  rx_config.resolution_hz = kRmtResolutionHz;
  rx_config.mem_block_symbols = kRmtMemorySymbols;
"""
new = """  rmt_rx_channel_config_t rx_config{};
  rx_config.gpio_num = static_cast<gpio_num_t>(config_.rx_gpio);
  rx_config.clk_src = RMT_CLK_SRC_DEFAULT;
  rx_config.resolution_hz = kRxResolutionHz;
  rx_config.mem_block_symbols = kRmtMemorySymbols;
"""
if old not in s:
    raise SystemExit('RX resolution anchor missing')
s = s.replace(old, new, 1)
old2 = """    captured[i] = PulseSymbol{
        static_cast<std::uint16_t>(input.duration0),
        static_cast<std::uint16_t>(input.duration1),
        input.level0 != 0U,
        input.level1 != 0U,
    };
"""
new2 = """    captured[i] = PulseSymbol{
        static_cast<std::uint16_t>((input.duration0 + (kRxToCodecTickRatio / 2U)) / kRxToCodecTickRatio),
        static_cast<std::uint16_t>((input.duration1 + (kRxToCodecTickRatio / 2U)) / kRxToCodecTickRatio),
        input.level0 != 0U,
        input.level1 != 0U,
    };
"""
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
export STAGE27C_BUILD_DIR=build/idf-stage28b-rf-rx-1mhz-probe-v2
scripts/stage27c_crowpanel.sh flash
OUT=/tmp/stage28b-rf-rx-1mhz-probe-v2
rm -rf "$OUT"
.venv/bin/python tools/stage27c_soak.py --port "$PORT" --output-dir "$OUT" --duration 90 --progress-seconds 30 --expected-sha "$EXPECTED" --require-sd --strict
.venv/bin/python - "$OUT" <<'PY'
from pathlib import Path
import sys
out = Path(sys.argv[1])
rf = []
for p in sorted(out.glob('raw-*.log')):
    for line in p.read_text(encoding='utf-8', errors='replace').splitlines():
        if 'rf433_loopback_v=1 ' in line:
            rf.append(line)
assert rf, 'no RF loopback evidence'
print('STAGE28B_RX_1MHZ_RF_RESULT', rf[-1])
fields = {}
for tok in rf[-1].split('rf433_loopback_v=1 ', 1)[1].split():
    if '=' in tok:
        k, v = tok.split('=', 1)
        fields[k] = v
def iv(k):
    return int(fields[k], 0)
assert iv('rx_arm_errors') == 0, fields
assert iv('tx_queued') == 1 and iv('tx_started') == 1 and iv('tx_completed') == 1, fields
print('STAGE28B_RX_1MHZ_ARM_OK')
if iv('pass') == 1:
    assert iv('rx_captured') == 1
    assert iv('decode_status') == 0
    assert iv('decoded_code') == 0xA55A
    assert iv('decoded_bits') == 16
    assert iv('decoded_protocol') == 1
    assert iv('classification') == 1
    print('STAGE28B_RX_1MHZ_LOOPBACK_PASS')
else:
    print('STAGE28B_RX_1MHZ_LOOPBACK_NOT_YET_PASS', fields)
PY
printf 'STAGE28B_RF_RX_1MHZ_PROBE_OK\n'
