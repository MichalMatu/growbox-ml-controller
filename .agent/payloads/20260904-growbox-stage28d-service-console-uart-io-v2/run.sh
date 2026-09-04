#!/usr/bin/env bash
set -euo pipefail

EXPECTED=8f14d766ff2ce1f40d4c66e332c105a3ca94bd61
BRANCH=mvp/environment-controller
TASK=20260904-growbox-stage28d-service-console-uart-io-v2

git fetch -q origin "$BRANCH"
git reset --hard "$EXPECTED"
test "$(git rev-parse HEAD)" = "$EXPECTED"
test "$(git rev-parse origin/$BRANCH)" = "$EXPECTED"
test -z "$(git status --porcelain)"

IDF_ROOT="${IDF_PATH:-$HOME/esp/esp-idf}"
UART_HEADER="$IDF_ROOT/components/esp_driver_uart/include/driver/uart.h"
test -f "$UART_HEADER"
grep -q 'uart_write_bytes' "$UART_HEADER"
grep -q 'uart_read_bytes' "$UART_HEADER"
grep -q 'uart_driver_install' "$UART_HEADER"
printf 'IDF_UART_IO_API_OK path=%s\n' "$UART_HEADER"

python3 - <<'PY'
from pathlib import Path

p = Path('src/climate/runtime/Stage28ServiceConsole.cpp')
s = p.read_text()

old = '#include <cstring>\n#include <unistd.h>\n'
if old not in s:
    raise SystemExit('unistd include anchor missing')
s = s.replace(old, '#include <cstring>\n', 1)

old = '''constexpr uart_port_t kServiceConsoleUart = static_cast<uart_port_t>(CONFIG_ESP_CONSOLE_UART_NUM);\nconstexpr int kServiceConsoleRxBufferBytes = 1024;\n'''
new = '''constexpr uart_port_t kServiceConsoleUart = static_cast<uart_port_t>(CONFIG_ESP_CONSOLE_UART_NUM);\nconstexpr int kServiceConsoleRxBufferBytes = 1024;\nconstexpr int kServiceConsoleTxBufferBytes = 2048;\n'''
if old not in s:
    raise SystemExit('UART buffer constants anchor missing')
s = s.replace(old, new, 1)

old = '''  // Keep output on ESP-IDF primary stdio, but receive commands through the\n  // primary console UART driver. The default stdin VFS path did not consume\n  // CH340 RX bytes on the qualified CrowPanel hardware. Direct non-blocking\n  // uart_read_bytes() keeps the service path bounded without changing logs.\n  if (!uart_is_driver_installed(kServiceConsoleUart)) {\n    const esp_err_t install_result =\n        uart_driver_install(kServiceConsoleUart, kServiceConsoleRxBufferBytes, 0, 0, nullptr, 0);\n'''
new = '''  // Use the configured primary console UART driver for service-console RX/TX.\n  // Normal ESP-IDF logging remains on its existing primary logger transport.\n  // Direct UART I/O avoids relying on newlib stdin/stdout routing on CrowPanel.\n  if (!uart_is_driver_installed(kServiceConsoleUart)) {\n    const esp_err_t install_result = uart_driver_install(\n        kServiceConsoleUart, kServiceConsoleRxBufferBytes, kServiceConsoleTxBufferBytes, 0, nullptr, 0);\n'''
if old not in s:
    raise SystemExit('UART install block anchor missing')
s = s.replace(old, new, 1)

old = '''  const std::size_t length = std::strlen(text);\n  std::size_t offset = 0U;\n  while (offset < length) {\n    const ssize_t written = ::write(STDOUT_FILENO, text + offset, length - offset);\n    if (written <= 0) {\n      break;\n    }\n    offset += static_cast<std::size_t>(written);\n  }\n'''
new = '''  const std::size_t length = std::strlen(text);\n  std::size_t offset = 0U;\n  while (offset < length) {\n    const int written = uart_write_bytes(kServiceConsoleUart, text + offset, length - offset);\n    if (written <= 0) {\n      break;\n    }\n    offset += static_cast<std::size_t>(written);\n  }\n'''
if old not in s:
    raise SystemExit('stdout write block anchor missing')
s = s.replace(old, new, 1)
p.write_text(s)
PY

git diff --check
PC="$(git rev-parse --show-toplevel)/.venv/bin/pre-commit"
test -x "$PC"
set +e
"$PC" run --files src/climate/runtime/Stage28ServiceConsole.cpp
FIRST_RC=$?
set -e
if [[ "$FIRST_RC" -ne 0 ]]; then
  "$PC" run --files src/climate/runtime/Stage28ServiceConsole.cpp
fi

git diff --check
export CMAKE_BUILD_PARALLEL_LEVEL=1
cmake -S test/host -B build/host-stage28d-service-console-uart-io-v2 -DCMAKE_BUILD_TYPE=Debug >/tmp/stage28d-console-uart-io-v2-host-cmake.log
cmake --build build/host-stage28d-service-console-uart-io-v2 --target stage28_service_console_tests rf433_protocol_tests --parallel 1
./build/host-stage28d-service-console-uart-io-v2/stage28_service_console_tests
./build/host-stage28d-service-console-uart-io-v2/rf433_protocol_tests

GROWBOX_RF433_LOOPBACK_ENABLED=1 \
GROWBOX_RF433_LOOPBACK_AUTO_SMOKE=0 \
GROWBOX_RF433_REMOTE_CAPTURE_ENABLED=0 \
GROWBOX_STAGE28_SERVICE_CONSOLE_ENABLED=1 \
STAGE27C_BUILD_DIR=build/idf-stage28d-service-console-uart-io-v2-crowpanel \
  bash scripts/stage27c_crowpanel.sh build

SDKCONFIG=build/idf-stage28d-service-console-uart-io-v2-crowpanel/sdkconfig
test -f "$SDKCONFIG"
grep -q '^CONFIG_ESP_CONSOLE_UART=y' "$SDKCONFIG"
grep -q '^CONFIG_ESP_CONSOLE_UART_NUM=0' "$SDKCONFIG"
printf 'CROWPANEL_CONSOLE_CONFIG '
grep -E '^CONFIG_ESP_CONSOLE_(UART|UART_NUM)' "$SDKCONFIG" | tr '\n' ' '
printf '\n'

git add src/climate/runtime/Stage28ServiceConsole.cpp
git commit -m "Use UART driver for Stage28D service console IO"
NEW=$(git rev-parse HEAD)

PYTHON_BIN="$(git rev-parse --show-toplevel)/.venv/bin/python"
if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="$(command -v python3)"
fi

echo '==> pytest'
"$PYTHON_BIN" -m pytest -q -m 'not hardware'

echo '==> host C++ tests'
cmake -S test/host -B build/host-tests -DCMAKE_EXPORT_COMPILE_COMMANDS=ON
cmake --build build/host-tests --parallel 1
ctest --test-dir build/host-tests --output-on-failure

echo '==> host clang-tidy'
TIDY_COPY=/tmp/run_clang_tidy_host_stage28d_console_uart_io_v2.sh
cp scripts/run_clang_tidy_host.sh "$TIDY_COPY"
python3 - "$TIDY_COPY" <<'PYTIDY'
from pathlib import Path
import sys
p = Path(sys.argv[1])
s = p.read_text()
old = 'cmake --build "${BUILD_DIR}" --parallel\n'
if old not in s:
    raise SystemExit('clang-tidy build marker missing')
p.write_text(s.replace(old, 'cmake --build "${BUILD_DIR}" --parallel 1\n', 1))
PYTIDY
bash "$TIDY_COPY"

echo '==> ESP-IDF gate'
bash scripts/idf_gate_build.sh

git diff --check
test -z "$(git status --porcelain)"
git fetch -q origin "$BRANCH"
test "$(git rev-parse origin/$BRANCH)" = "$EXPECTED"
git push origin HEAD:"$BRANCH"
git fetch -q origin "$BRANCH"
test "$(git rev-parse origin/$BRANCH)" = "$NEW"

printf 'STAGE28D_SERVICE_CONSOLE_UART_IO_READY commit=%s parent=%s parser_tests=pass rf_tests=pass crowpanel_build=pass quality_gate=pass console_output=primary_uart_driver console_input=primary_uart_driver uart_num=0 runtime_outputs=fake-locked automatic_rf_tx=0\n' "$NEW" "$EXPECTED"
