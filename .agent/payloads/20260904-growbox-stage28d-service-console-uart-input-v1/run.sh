#!/usr/bin/env bash
set -euo pipefail

EXPECTED=c8141d8b4a0c0d4bce5d330c2e65225ce93f4220
BRANCH=mvp/environment-controller
TASK=20260904-growbox-stage28d-service-console-uart-input-v1

git fetch -q origin "$BRANCH"
git reset --hard "$EXPECTED"
test "$(git rev-parse HEAD)" = "$EXPECTED"
test "$(git rev-parse origin/$BRANCH)" = "$EXPECTED"
test -z "$(git status --porcelain)"

IDF_ROOT="${IDF_PATH:-$HOME/esp/esp-idf}"
test -d "$IDF_ROOT/components"
UART_HEADER="$IDF_ROOT/components/esp_driver_uart/include/driver/uart.h"
test -f "$UART_HEADER"
grep -q 'uart_driver_install' "$UART_HEADER"
grep -q 'uart_is_driver_installed' "$UART_HEADER"
grep -q 'uart_read_bytes' "$UART_HEADER"
printf 'IDF_UART_INPUT_API_OK path=%s\n' "$UART_HEADER"

grep -R -n -m1 'config ESP_CONSOLE_UART_NUM' "$IDF_ROOT/components" || {
  echo 'ESP_CONSOLE_UART_NUM Kconfig definition not found in local ESP-IDF' >&2
  exit 2
}
for cfg in build/idf-stage28d-service-console-hw-smoke-v2/sdkconfig \
           build/idf-stage28d-service-console-stdio-crowpanel/sdkconfig; do
  if [[ -f "$cfg" ]]; then
    printf 'EXISTING_CONSOLE_CONFIG %s ' "$cfg"
    grep -E '^CONFIG_ESP_CONSOLE_(UART|UART_NUM)' "$cfg" | tr '\n' ' '
    printf '\n'
  fi
done

python3 - <<'PY'
from pathlib import Path

p = Path('src/climate/runtime/Stage28ServiceConsole.cpp')
s = p.read_text()

old = '''#include "climate/rf433/Rf433HardwareConfig.h"\n\n#include <esp_heap_caps.h>\n'''
new = '''#include "climate/rf433/Rf433HardwareConfig.h"\n\n#include <driver/uart.h>\n#include <esp_heap_caps.h>\n#include <sdkconfig.h>\n'''
if old not in s:
    raise SystemExit('service console include anchor missing')
s = s.replace(old, new, 1)

anchor = '''constexpr std::array<KnownRfDevice, 3U> kKnownRfDevices{{\n    {ServiceConsoleRfDevice::Lamp, "lamp", &rf433::kRemoteSocket2,\n     "captured-profile; physical socket validation pending"},\n    {ServiceConsoleRfDevice::Fan, "fan", &rf433::kRemoteSocket1,\n     "physically validated at 575us/repeat10"},\n    {ServiceConsoleRfDevice::Humidifier, "humidifier", &rf433::kRemoteSocket3,\n     "captured-profile; physical socket validation pending"},\n}};\n\n'''
insert = anchor + '''#if !defined(CONFIG_ESP_CONSOLE_UART_NUM)\n#error "Stage28 service console requires an ESP-IDF UART primary console"\n#endif\n\nconstexpr uart_port_t kServiceConsoleUart =\n    static_cast<uart_port_t>(CONFIG_ESP_CONSOLE_UART_NUM);\nconstexpr int kServiceConsoleRxBufferBytes = 1024;\n\n'''
if anchor not in s:
    raise SystemExit('known-device anchor missing')
s = s.replace(anchor, insert, 1)

old = '''  // Use the ESP-IDF primary standard-I/O console. On the qualified CrowPanel\n  // build this is the CH340-backed UART console, so logs and service commands\n  // share the same physical serial monitor. The default UART VFS read path is\n  // non-blocking, which keeps this poll-driven console bounded.\n  std::array<std::uint8_t, 128U> discard{};\n  while (::read(STDIN_FILENO, discard.data(), discard.size()) > 0) {\n  }\n\n'''
new = '''  // Keep output on ESP-IDF primary stdio, but receive commands through the\n  // primary console UART driver. The default stdin VFS path did not consume\n  // CH340 RX bytes on the qualified CrowPanel hardware. Direct non-blocking\n  // uart_read_bytes() keeps the service path bounded without changing logs.\n  if (!uart_is_driver_installed(kServiceConsoleUart)) {\n    const esp_err_t install_result =\n        uart_driver_install(kServiceConsoleUart, kServiceConsoleRxBufferBytes, 0, 0, nullptr, 0);\n    if (install_result != ESP_OK) {\n      return false;\n    }\n  }\n  if (uart_flush_input(kServiceConsoleUart) != ESP_OK) {\n    return false;\n  }\n\n'''
if old not in s:
    raise SystemExit('service console stdin begin block missing')
s = s.replace(old, new, 1)

old = '''  std::array<std::uint8_t, 96U> buffer{};\n  const ssize_t received = ::read(STDIN_FILENO, buffer.data(), buffer.size());\n  if (received <= 0) {\n    return;\n  }\n\n  for (ssize_t index = 0; index < received; ++index) {\n'''
new = '''  std::array<std::uint8_t, 96U> buffer{};\n  const int received =\n      uart_read_bytes(kServiceConsoleUart, buffer.data(), buffer.size(), 0U);\n  if (received <= 0) {\n    return;\n  }\n\n  for (int index = 0; index < received; ++index) {\n'''
if old not in s:
    raise SystemExit('service console stdin poll block missing')
s = s.replace(old, new, 1)
p.write_text(s)

p = Path('src/CMakeLists.txt')
s = p.read_text()
old = '''    esp_driver_rmt\n    nvs_flash\n'''
new = '''    esp_driver_rmt\n    esp_driver_uart\n    nvs_flash\n'''
if old not in s:
    raise SystemExit('src CMake driver dependency anchor missing')
s = s.replace(old, new, 1)
s = s.replace(
    'set(GROWBOX_STAGE28_SERVICE_CONSOLE_ENABLED "1" CACHE STRING "Enable Stage28 USB service console")',
    'set(GROWBOX_STAGE28_SERVICE_CONSOLE_ENABLED "1" CACHE STRING "Enable Stage28 primary-serial service console")',
    1,
)
p.write_text(s)

p = Path('docs/CURRENT_STATUS.md')
s = p.read_text()
needle = '''The real-input runtime now includes a bounded primary-serial service console on the same ESP-IDF primary stdio/UART interface used by the normal CrowPanel CH340 monitor'''
if needle not in s:
    raise SystemExit('CURRENT_STATUS console transport sentence missing')
s = s.replace(
    needle,
    needle + '. Output remains on primary stdio; command input uses the ESP-IDF driver for the configured primary console UART so CH340 RX is consumed non-blockingly',
    1,
)
p.write_text(s)

p = Path('continuation.md')
s = p.read_text()
old = '''It deliberately uses ESP-IDF primary stdin/stdout instead of opening a separate USB Serial/JTAG channel, so the qualified CrowPanel uses the same CH340 serial monitor for logs and commands.'''
new = '''It keeps output on ESP-IDF primary stdout and consumes command input directly from the ESP-IDF driver for the configured primary console UART, so the qualified CrowPanel uses the same CH340 serial monitor for logs and commands without a separate USB Serial/JTAG channel.'''
if old not in s:
    raise SystemExit('continuation transport sentence missing')
s = s.replace(old, new, 1)
p.write_text(s)
PY

git diff --check
PC="$(git rev-parse --show-toplevel)/.venv/bin/pre-commit"
test -x "$PC"
set +e
"$PC" run --files \
  src/climate/runtime/Stage28ServiceConsole.cpp src/CMakeLists.txt \
  docs/CURRENT_STATUS.md continuation.md
FIRST_RC=$?
set -e
if [[ "$FIRST_RC" -ne 0 ]]; then
  "$PC" run --files \
    src/climate/runtime/Stage28ServiceConsole.cpp src/CMakeLists.txt \
    docs/CURRENT_STATUS.md continuation.md
fi

git diff --check
export CMAKE_BUILD_PARALLEL_LEVEL=1
cmake -S test/host -B build/host-stage28d-service-console-uart-input -DCMAKE_BUILD_TYPE=Debug >/tmp/stage28d-console-uart-host-cmake.log
cmake --build build/host-stage28d-service-console-uart-input --target stage28_service_console_tests rf433_protocol_tests --parallel 1
./build/host-stage28d-service-console-uart-input/stage28_service_console_tests
./build/host-stage28d-service-console-uart-input/rf433_protocol_tests

GROWBOX_RF433_LOOPBACK_ENABLED=1 \
GROWBOX_RF433_LOOPBACK_AUTO_SMOKE=0 \
GROWBOX_RF433_REMOTE_CAPTURE_ENABLED=0 \
GROWBOX_STAGE28_SERVICE_CONSOLE_ENABLED=1 \
STAGE27C_BUILD_DIR=build/idf-stage28d-service-console-uart-input-crowpanel \
  bash scripts/stage27c_crowpanel.sh build

SDKCONFIG=build/idf-stage28d-service-console-uart-input-crowpanel/sdkconfig
test -f "$SDKCONFIG"
grep -q '^CONFIG_ESP_CONSOLE_UART=y' "$SDKCONFIG"
grep -q '^CONFIG_ESP_CONSOLE_UART_NUM=0' "$SDKCONFIG"
printf 'CROWPANEL_CONSOLE_CONFIG '
grep -E '^CONFIG_ESP_CONSOLE_(UART|UART_NUM)' "$SDKCONFIG" | tr '\n' ' '
printf '\n'

git add src/climate/runtime/Stage28ServiceConsole.cpp src/CMakeLists.txt \
        docs/CURRENT_STATUS.md continuation.md
git commit -m "Fix Stage28D CH340 service console input"
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
TIDY_COPY=/tmp/run_clang_tidy_host_stage28d_console_uart_input_v1.sh
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

printf 'STAGE28D_SERVICE_CONSOLE_UART_INPUT_READY commit=%s parent=%s parser_tests=pass rf_tests=pass crowpanel_build=pass quality_gate=pass console_output=primary_stdio console_input=primary_uart_driver uart_num=0 runtime_outputs=fake-locked automatic_rf_tx=0\n' "$NEW" "$EXPECTED"
