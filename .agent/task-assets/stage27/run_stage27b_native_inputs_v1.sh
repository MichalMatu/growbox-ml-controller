#!/usr/bin/env bash
set -euo pipefail

MODE="${1:?mode required}"
EXPECTED="${2:?expected source sha required}"
SCD4X_SHA='b52cebe1bb1b7050feaac75d7cd33e56c6a8a4e9'

vendor_scd4x() {
  local tmp
  tmp="$(mktemp -d)"
  git clone -q https://github.com/Sensirion/embedded-i2c-scd4x.git "$tmp/scd4x"
  git -C "$tmp/scd4x" checkout -q "$SCD4X_SHA"
  local dst='components/sensirion_scd4x'
  mkdir -p "$dst"
  for file in scd4x_i2c.c scd4x_i2c.h sensirion_common.c sensirion_common.h sensirion_config.h sensirion_i2c.c sensirion_i2c.h sensirion_i2c_hal.h LICENSE; do
    cp "$tmp/scd4x/$file" "$dst/$file"
  done
  rm -rf "$tmp"
}

host_stage27_test() {
  c++ -std=c++17 -Wall -Wextra -Wpedantic -Werror \
    -Isrc \
    test/test_stage27_native_inputs/test_main.cpp \
    src/climate/native/BthomeV2Decoder.cpp \
    src/climate/native/Ds3231Codec.cpp \
    -o /tmp/growbox-stage27-native-tests
  /tmp/growbox-stage27-native-tests
}

assert_native_only() {
  if grep -R -n -E 'Arduino\.h|NimBLE-Arduino|GxEPD2|#include[[:space:]]*[<\"]Wire\.h' src components/sensirion_scd4x; then
    echo 'Arduino dependency detected in Stage27 native source' >&2
    exit 1
  fi
}

source_idf() {
  unset VIRTUAL_ENV CONDA_PREFIX PYTHONHOME || true
  export PATH='/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin'
  source "$HOME/esp/esp-idf/export.sh"
  idf.py --version | grep -F 'ESP-IDF v5.5.4'
  test "$(git -C "$HOME/esp/esp-idf" describe --tags --exact-match HEAD)" = 'v5.5.4'
}

build_real() {
  rm -rf build/idf-gate-stage27-real
  idf.py -B build/idf-gate-stage27-real \
    -D 'SDKCONFIG_DEFAULTS=config/idf/sdkconfig.defaults;config/idf/sdkconfig.defaults.stage27' \
    -D 'GROWBOX_BOARD_PROFILE=esp32s3-devkitc1-n16r8' \
    -D 'GROWBOX_APP_MODE=climate-v6-real-inputs' \
    build
}

case "$MODE" in
  apply)
    git fetch origin mvp/environment-controller agent-control
    git reset --hard origin/mvp/environment-controller
    git clean -fd
    test "$(git rev-parse HEAD)" = "$EXPECTED"
    test -z "$(git status --porcelain)"
    vendor_scd4x
    host_stage27_test
    assert_native_only
    git diff --check
    git status --short
    ;;

  focused)
    test "$(git rev-parse HEAD)" = "$EXPECTED"
    host_stage27_test
    assert_native_only
    .venv/bin/pre-commit run --files \
      src/main.cpp src/CMakeLists.txt \
      src/climate/ClimateV6RealInputRuntime.cpp \
      src/climate/ClimateV6RealInputRuntime.h \
      src/climate/native/BthomeV2Decoder.cpp \
      src/climate/native/BthomeV2Decoder.h \
      src/climate/native/Ds3231Codec.cpp \
      src/climate/native/Ds3231Codec.h \
      src/climate/native/NativeI2cBus.cpp \
      src/climate/native/NativeI2cBus.h \
      src/climate/native/Scd41InsideSource.cpp \
      src/climate/native/Scd41InsideSource.h \
      src/climate/native/Ds3231ClockSource.cpp \
      src/climate/native/Ds3231ClockSource.h \
      src/climate/native/BleOutsideSource.cpp \
      src/climate/native/BleOutsideSource.h \
      test/test_stage27_native_inputs/test_main.cpp \
      config/idf/sdkconfig.defaults.stage27 \
      components/sensirion_scd4x/CMakeLists.txt \
      components/sensirion_scd4x/README.growbox.md \
      components/sensirion_scd4x/growbox_sensirion_i2c_hal.h \
      components/sensirion_scd4x/sensirion_i2c_hal.c
    host_stage27_test
    source_idf
    build_real
    git diff --check
    ;;

  full)
    test "$(git rev-parse HEAD)" = "$EXPECTED"
    assert_native_only
    host_stage27_test
    .venv/bin/pre-commit run --all-files
    .venv/bin/python -m pytest -q -m 'not hardware'
    bash scripts/check_schema.sh
    cmake -S test/host -B build/host-tests
    cmake --build build/host-tests --parallel
    ctest --test-dir build/host-tests --output-on-failure
    bash scripts/run_clang_tidy_host.sh
    source_idf
    rm -rf build/idf-gate-stage27-legacy build/idf-gate-stage27-fake
    IDF_GATE_BUILD_DIR=build/idf-gate-stage27-legacy IDF_GATE_APP_MODE=legacy bash scripts/idf_gate_build.sh
    IDF_GATE_BUILD_DIR=build/idf-gate-stage27-fake IDF_GATE_APP_MODE=climate-v6-fake bash scripts/idf_gate_build.sh
    build_real
    assert_native_only
    git diff --check
    git add -A
    git diff --cached --check
    git fetch origin mvp/environment-controller
    test "$(git rev-parse origin/mvp/environment-controller)" = "$EXPECTED"
    test "$(git rev-parse HEAD)" = "$EXPECTED"
    git commit -m 'Add native Stage27 real input bundle'
    git push origin HEAD:mvp/environment-controller
    test -z "$(git status --porcelain)"
    printf 'PUBLISHED_HEAD=%s\n' "$(git rev-parse HEAD)"
    ;;

  *)
    echo "Unknown mode: $MODE" >&2
    exit 2
    ;;
esac
