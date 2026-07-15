#!/usr/bin/env bash
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

# ESP-IDF export sets CC/CXX to cross-compilers — host tidy must use the native toolchain.
unset CC CXX CPP LD AR AS NM RANLIB OBJCOPY OBJDUMP READELF
unset IDF_PATH IDF_PYTHON_ENV_PATH IDF_DEACTIVATE_FILE_PATH

pick_clang_tidy() {
  if [[ -n "${CLANG_TIDY:-}" ]]; then
    echo "${CLANG_TIDY}"
    return
  fi
  local candidate
  for candidate in \
    /opt/homebrew/opt/llvm/bin/clang-tidy \
    /usr/local/opt/llvm/bin/clang-tidy \
    /usr/bin/clang-tidy; do
    if [[ -x "${candidate}" ]]; then
      echo "${candidate}"
      return
    fi
  done
  command -v clang-tidy
}

CLANG_TIDY_BIN="$(pick_clang_tidy || true)"
if [[ -z "${CLANG_TIDY_BIN}" || ! -x "${CLANG_TIDY_BIN}" ]]; then
  echo "host clang-tidy not found — install LLVM (macOS: brew install llvm, Ubuntu: apt install clang-tidy)" >&2
  echo "Do not use esp-clang tidy for host analysis; set CLANG_TIDY if needed." >&2
  exit 1
fi
if [[ "${CLANG_TIDY_BIN}" == *espressif* ]] || [[ "${CLANG_TIDY_BIN}" == *esp-clang* ]]; then
  echo "refusing esp-clang tidy for host analysis: ${CLANG_TIDY_BIN}" >&2
  echo "Install host LLVM (brew install llvm) or set CLANG_TIDY." >&2
  exit 1
fi

BUILD_DIR="${HOST_TIDY_BUILD_DIR:-build/host-tidy}"
SOURCES=(
  lib/environment_control/src/EnvironmentController.cpp
  lib/environment_control/src/FeatureEncoder.cpp
  lib/environment_control/src/SafetySupervisor.cpp
  lib/environment_control/src/ModelRuntime.cpp
)

CMAKE_ARGS=(-S test/host -B "${BUILD_DIR}" -DCMAKE_EXPORT_COMPILE_COMMANDS=ON -DCMAKE_BUILD_TYPE=Debug)
EXTRA_TIDY_ARGS=()

if [[ "$(uname -s)" == "Darwin" ]]; then
  SDK="$(xcrun --show-sdk-path)"
  CMAKE_ARGS+=(
    "-DCMAKE_CXX_COMPILER=$(xcrun --find clang++)"
    "-DCMAKE_CXX_FLAGS=-isysroot ${SDK}"
  )
  EXTRA_TIDY_ARGS+=(--extra-arg=-isysroot --extra-arg="${SDK}")
else
  CMAKE_ARGS+=(-DCMAKE_CXX_COMPILER=g++)
fi

echo "==> host clang-tidy (${BUILD_DIR})"
rm -rf "${BUILD_DIR}"
cmake "${CMAKE_ARGS[@]}"
cmake --build "${BUILD_DIR}" --parallel

for file in "${SOURCES[@]}"; do
  echo "clang-tidy: ${file}"
  "${CLANG_TIDY_BIN}" -p "${BUILD_DIR}" "${file}" --quiet "${EXTRA_TIDY_ARGS[@]}"
done
