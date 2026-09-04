#!/usr/bin/env bash
set -euo pipefail

EXPECTED=6a5c3e1d4d016a515962bd39a2ac52a9477354c9

test "$(git rev-parse HEAD)" = "$EXPECTED"
git fetch -q origin agent-control mvp/environment-controller
test "$(git rev-parse origin/mvp/environment-controller)" = "$EXPECTED"
test -z "$(git status --porcelain)"

python3 - <<'PY'
from pathlib import Path
p = Path('src/climate/rf433/Rf433RmtLoopback.cpp')
s = p.read_text(encoding='utf-8')
old = '''// Stage28C RX hardening mirrors the proven receiver envelope from the same RF433
// hardware: reject sub-10 us chatter and keep one burst open across repeat gaps.
constexpr std::uint32_t kRxMinimumSignalNs = 10'000U;
constexpr std::uint32_t kRxMaximumSignalNs = 300'000'000U;
'''
new = '''// Stage28C RX hardening: reject sub-10 us chatter. A 20 ms idle threshold is
// hardware-qualified with the known 32-bit protocol-2 ON/OFF pair at repeat=10;
// 300 ms did not terminate capture reliably on this receiver in the same setup.
constexpr std::uint32_t kRxMinimumSignalNs = 10'000U;
constexpr std::uint32_t kRxMaximumSignalNs = 20'000'000U;
'''
if s.count(old) != 1:
    raise SystemExit('expected Stage28C RX hardening block not found exactly once')
p.write_text(s.replace(old, new, 1), encoding='utf-8')
PY

if command -v clang-format >/dev/null 2>&1; then
  clang-format -i src/climate/rf433/Rf433RmtLoopback.cpp
fi

git diff --check

cmake -S test/host -B build/host-stage28c-rx-idle20-freeze-v1
cmake --build build/host-stage28c-rx-idle20-freeze-v1 -j2
ctest --test-dir build/host-stage28c-rx-idle20-freeze-v1 --output-on-failure

export GROWBOX_FIRMWARE_GIT_SHA="$EXPECTED"
export GROWBOX_RF433_LOOPBACK_ENABLED=1
export GROWBOX_RF433_LOOPBACK_AUTO_SMOKE=0
export GROWBOX_RF433_REMOTE_CAPTURE_ENABLED=0
export STAGE27C_BUILD_DIR=build/idf-stage28c-rx-idle20-freeze-v1
scripts/stage27c_crowpanel.sh build

git diff --check
git status --short

git add src/climate/rf433/Rf433RmtLoopback.cpp
git commit -m 'Tune Stage28C RF433 receive idle threshold'
NEW_SHA="$(git rev-parse HEAD)"

git fetch -q origin mvp/environment-controller
test "$(git rev-parse origin/mvp/environment-controller)" = "$EXPECTED"
git push origin HEAD:mvp/environment-controller

printf 'STAGE28C_RX_IDLE20_FROZEN commit=%s\n' "$NEW_SHA"
