#!/usr/bin/env bash
set -euo pipefail
EXPECTED=82d92fa0e4c9423a4dd0b3b00ea924d168401f41
BRANCH=mvp/environment-controller

test "$(git rev-parse HEAD)" = "$EXPECTED"
git fetch -q origin "$BRANCH"
test "$(git rev-parse origin/$BRANCH)" = "$EXPECTED"
test -z "$(git status --porcelain)"

python3 - <<'PY'
from pathlib import Path
p = Path('config/idf/sdkconfig.defaults.stage27')
text = p.read_text(encoding='utf-8')
old = '''# Match the ESP-IDF v5.5.4 NimBLE BLE-only host configuration used by the official blecent example.\nCONFIG_BT_ENABLED=y\nCONFIG_BTDM_CTRL_MODE_BLE_ONLY=y\nCONFIG_BTDM_CTRL_MODE_BR_EDR_ONLY=n\nCONFIG_BTDM_CTRL_MODE_BTDM=n\nCONFIG_BT_BLUEDROID_ENABLED=n\nCONFIG_BT_NIMBLE_ENABLED=y\n'''
new = '''# ESP32-S3 uses the NimBLE BLE-only host. ESP-IDF 5.5 no longer exposes the\n# legacy BTDM_CTRL_MODE_* choices for this target; keep only supported host\n# selections so sdkconfig generation is warning-free.\nCONFIG_BT_ENABLED=y\nCONFIG_BT_BLUEDROID_ENABLED=n\nCONFIG_BT_NIMBLE_ENABLED=y\n'''
if old not in text:
    raise SystemExit('expected Stage27 BLE config block not found')
p.write_text(text.replace(old, new, 1), encoding='utf-8')
PY

git diff --check

cmake -S test/host -B build/host-prestage-kconfig-cleanup-v1
cmake --build build/host-prestage-kconfig-cleanup-v1 -j2
ctest --test-dir build/host-prestage-kconfig-cleanup-v1 --output-on-failure
if [[ -x .venv/bin/python ]]; then
  .venv/bin/python -m pytest tests/test_panel_layout.py -q
fi

export GROWBOX_FIRMWARE_GIT_SHA="$EXPECTED"
export GROWBOX_RF433_LOOPBACK_ENABLED=1
export GROWBOX_RF433_LOOPBACK_AUTO_SMOKE=0
export GROWBOX_RF433_REMOTE_CAPTURE_ENABLED=1
export STAGE27C_BUILD_DIR=build/idf-prestage-kconfig-cleanup-v1
set -o pipefail
scripts/stage27c_crowpanel.sh build 2>&1 | tee /tmp/prestage-kconfig-cleanup-build.log

if grep -F "warning: unknown kconfig symbol" /tmp/prestage-kconfig-cleanup-build.log; then
  echo 'unknown Kconfig symbols remain' >&2
  exit 1
fi

git diff --check
git add config/idf/sdkconfig.defaults.stage27
git commit -m "Remove obsolete ESP-IDF Bluetooth Kconfig choices"
git push origin HEAD:"$BRANCH"
NEW=$(git rev-parse HEAD)
test "$(git rev-parse origin/$BRANCH)" = "$NEW"
test -z "$(git status --porcelain)"
printf 'PRESTAGE_KCONFIG_CLEANUP_READY commit=%s unknown_kconfig_warnings=0\n' "$NEW"
