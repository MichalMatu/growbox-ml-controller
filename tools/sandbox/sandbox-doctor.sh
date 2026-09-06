#!/usr/bin/env bash
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT"

fail() { echo "FAIL: $*" >&2; exit 1; }
ok() { echo "OK: $*"; }

[[ "$(uname -s)" == "Linux" ]] || fail "sandbox packs support Linux only"
[[ "$(uname -m)" == "x86_64" ]] || fail "sandbox packs support x86_64 only"
command -v cmake >/dev/null || fail "cmake missing"
command -v zstd >/dev/null || fail "zstd missing"
ok "platform $(uname -m)-$(uname -s)"

if [[ -n "${GROWBOX_SANDBOX_HOST_PACK:-}" ]]; then
  python - <<'PY'
import sys
assert sys.version_info[:2] == (3, 11), sys.version
import numpy, tensorflow, pytest
print("Python", sys.version.split()[0], "TensorFlow", tensorflow.__version__)
PY
  command -v clang-format >/dev/null || fail "clang-format missing"
  command -v clang-tidy >/dev/null || fail "clang-tidy missing"
  clang-format --version
  clang-tidy --version | head -3
  EXPECTED="$(tools/sandbox/dependency-key.sh host)"
  [[ "$(cat "$GROWBOX_SANDBOX_HOST_PACK/.dependency-key")" == "$EXPECTED" ]] || fail "host key mismatch"
  ok "host pack"
fi

if [[ -n "${GROWBOX_SANDBOX_WEB_PACK:-}" ]]; then
  [[ "$(node -p 'process.versions.node.split(".")[0]')" == "22" ]] || fail "Node 22 required"
  [[ "$(pnpm --version)" == "11.10.0" ]] || fail "pnpm 11.10.0 required"
  EXPECTED="$(tools/sandbox/dependency-key.sh web)"
  [[ "$(cat "$GROWBOX_SANDBOX_WEB_PACK/.dependency-key")" == "$EXPECTED" ]] || fail "web key mismatch"
  ok "web pack"
fi

if [[ -n "${GROWBOX_SANDBOX_IDF_PACK:-}" ]]; then
  # shellcheck disable=SC1090
  source "${IDF_EXPORT_SH:?IDF_EXPORT_SH missing}"
  idf.py --version | grep -E 'v?5\.5\.4' >/dev/null || fail "ESP-IDF 5.5.4 required"
  command -v xtensa-esp32s3-elf-gcc >/dev/null || fail "ESP32-S3 GCC missing"
  command -v clang >/dev/null || fail "esp-clang missing"
  EXPECTED="$(tools/sandbox/dependency-key.sh idf)"
  [[ "$(cat "$GROWBOX_SANDBOX_IDF_PACK/.dependency-key")" == "$EXPECTED" ]] || fail "idf key mismatch"
  ok "ESP-IDF 5.5.4 / esp32s3"
fi

if [[ -f .sandbox-snapshot/git-sha.txt ]]; then
  ok "source snapshot $(cat .sandbox-snapshot/git-sha.txt)"
fi

echo "sandbox doctor: OK"
