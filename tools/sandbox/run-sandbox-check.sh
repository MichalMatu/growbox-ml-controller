#!/usr/bin/env bash
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT"
PROFILE="${1:-quality}"

require_host() { [[ -n "${GROWBOX_SANDBOX_HOST_PACK:-}" ]] || { echo "host pack is not loaded" >&2; exit 1; }; }
require_web() { [[ -n "${GROWBOX_SANDBOX_WEB_PACK:-}" ]] || { echo "web pack is not loaded" >&2; exit 1; }; }
require_idf() { [[ -n "${GROWBOX_SANDBOX_IDF_PACK:-}" ]] || { echo "idf pack is not loaded" >&2; exit 1; }; }

host_fast() {
  require_host
  ruff check .
  ruff format --check .
  mapfile -t CPP < <(find src lib/environment_control/src test -type f \( -name '*.c' -o -name '*.cc' -o -name '*.cpp' -o -name '*.h' -o -name '*.hpp' \) \
    ! -path 'lib/environment_control/src/generated/*' \
    ! -name 'EnvironmentSchema*.h' | sort)
  if ((${#CPP[@]})); then
    clang-format --dry-run --Werror "${CPP[@]}"
  fi
  bash scripts/check_schema.sh
}

host_full() {
  host_fast
  python -m pytest -q -m "not hardware"
  python scripts/ml_quick_smoke.py
  cmake -S test/host -B build/sandbox-host-tests -DCMAKE_EXPORT_COMPILE_COMMANDS=ON
  cmake --build build/sandbox-host-tests --parallel
  ctest --test-dir build/sandbox-host-tests --output-on-failure
  HOST_BUILD_DIR=build/sandbox-host-tests bash scripts/run_clang_tidy_host.sh
}

web_full() {
  require_web
  pnpm --dir web gate
}

idf_full() {
  require_host
  require_idf
  # shellcheck disable=SC1090
  source "${IDF_EXPORT_SH:?IDF_EXPORT_SH missing}"
  idf.py -B build/sandbox-idf \
    -D GROWBOX_BOARD_PROFILE=esp32s3-devkitc1-n8 build
  IDF_TOOLCHAIN=clang idf.py -B build/sandbox-idf-clang \
    -D GROWBOX_BOARD_PROFILE=esp32s3-devkitc1-n8 \
    clang-check --exit-code src
}

case "$PROFILE" in
  doctor)
    tools/sandbox/sandbox-doctor.sh
    ;;
  host-fast)
    tools/sandbox/sandbox-doctor.sh
    host_fast
    ;;
  host)
    tools/sandbox/sandbox-doctor.sh
    host_full
    ;;
  web)
    tools/sandbox/sandbox-doctor.sh
    web_full
    ;;
  idf|firmware)
    tools/sandbox/sandbox-doctor.sh
    idf_full
    ;;
  quality|all)
    tools/sandbox/sandbox-doctor.sh
    host_full
    web_full
    idf_full
    ;;
  *)
    echo "usage: $0 {doctor|host-fast|host|web|idf|firmware|quality|all}" >&2
    exit 2
    ;;
esac
