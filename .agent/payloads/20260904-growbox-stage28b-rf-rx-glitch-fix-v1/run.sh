#!/usr/bin/env bash
set -euo pipefail
EXPECTED=56813b27f6dc1f93d4899974ffd47a1528d8b6b8
test "$(git rev-parse HEAD)" = "$EXPECTED"
git fetch -q origin mvp/environment-controller
test "$(git rev-parse origin/mvp/environment-controller)" = "$EXPECTED"
test -z "$(git status --porcelain)"
python3 - <<'PY'
from pathlib import Path
p = Path('src/climate/rf433/Rf433RmtLoopback.cpp')
s = p.read_text(encoding='utf-8')
repls = [
    ("constexpr std::uint32_t kRxMinimumSignalNs = 20'000U;", "constexpr std::uint32_t kRxMinimumSignalNs = 1'250U;"),
    ("constexpr std::uint32_t kRxMaximumSignalNs = 300'000'000U;", "constexpr std::uint32_t kRxMaximumSignalNs = 12'000'000U;\nconstexpr std::uint32_t kRxResolutionHz = 1'000'000U;\nconstexpr std::uint32_t kRxToCodecTickRatio = kRxResolutionHz / kRmtResolutionHz;"),
    ("  rx_config.resolution_hz = kRmtResolutionHz;", "  rx_config.resolution_hz = kRxResolutionHz;"),
]
for old, new in repls:
    if old not in s:
        raise SystemExit(f'missing Stage28B RX fix anchor: {old}')
    s = s.replace(old, new, 1)
old = '''    captured[i] = PulseSymbol{\n        static_cast<std::uint16_t>(input.duration0),\n        static_cast<std::uint16_t>(input.duration1),\n        input.level0 != 0U,\n        input.level1 != 0U,\n    };\n'''
new = '''    captured[i] = PulseSymbol{\n        static_cast<std::uint16_t>((input.duration0 + (kRxToCodecTickRatio / 2U)) / kRxToCodecTickRatio),\n        static_cast<std::uint16_t>((input.duration1 + (kRxToCodecTickRatio / 2U)) / kRxToCodecTickRatio),\n        input.level0 != 0U,\n        input.level1 != 0U,\n    };\n'''
if old not in s:
    raise SystemExit('missing RX duration conversion anchor')
s = s.replace(old, new, 1)
p.write_text(s, encoding='utf-8')
PY
git diff --check
cmake -S test/host -B build/host-stage28b-rx-glitch-fix-v1
cmake --build build/host-stage28b-rx-glitch-fix-v1 -j2
ctest --test-dir build/host-stage28b-rx-glitch-fix-v1 --output-on-failure
rm -rf build/idf-stage28b-rx-glitch-fix-v1
GROWBOX_RF433_LOOPBACK_ENABLED=1 \
GROWBOX_RF433_LOOPBACK_AUTO_SMOKE=0 \
GROWBOX_FIRMWARE_GIT_SHA="$EXPECTED" \
STAGE27C_BUILD_DIR=build/idf-stage28b-rx-glitch-fix-v1 \
scripts/stage27c_crowpanel.sh build
git diff --check
git add src/climate/rf433/Rf433RmtLoopback.cpp
git commit -m 'Fix RF433 RMT receive timing limits'
git fetch -q origin mvp/environment-controller
test "$(git rev-parse origin/mvp/environment-controller)" = "$EXPECTED"
git push origin HEAD:mvp/environment-controller
printf 'STAGE28B_RF_RX_GLITCH_FIX_OK commit=%s\n' "$(git rev-parse HEAD)"
