#!/usr/bin/env bash
set -euo pipefail

EXPECTED=fd4c16c7f3ae454d50d1ce3bd7bc6b9daddf1f3e
BRANCH=mvp/environment-controller

git fetch -q origin "$BRANCH"
git reset --hard "$EXPECTED"
test "$(git rev-parse HEAD)" = "$EXPECTED"
test "$(git rev-parse origin/$BRANCH)" = "$EXPECTED"
test -z "$(git status --porcelain)"

python3 - <<'PY'
from pathlib import Path

p = Path("src/climate/runtime/Stage28ServiceConsole.cpp")
s = p.read_text()
s = s.replace('#include <driver/usb_serial_jtag.h>\n', '')
s = s.replace('#include <cstring>\n', '#include <cstring>\n#include <unistd.h>\n', 1)
old = '''  if (!usb_serial_jtag_is_driver_installed()) {\n    usb_serial_jtag_driver_config_t driver_config = USB_SERIAL_JTAG_DRIVER_CONFIG_DEFAULT();\n    driver_config.tx_buffer_size = 4096U;\n    driver_config.rx_buffer_size = 4096U;\n    if (usb_serial_jtag_driver_install(&driver_config) != ESP_OK) {\n      return false;\n    }\n  }\n\n  std::uint8_t discard[128]{};\n  while (usb_serial_jtag_read_bytes(discard, sizeof(discard), 0U) > 0) {\n  }\n\n'''
new = '''  // Use the ESP-IDF primary standard-I/O console. On the qualified CrowPanel\n  // build this is the CH340-backed UART console, so logs and service commands\n  // share the same physical serial monitor. The default UART VFS read path is\n  // non-blocking, which keeps this poll-driven console bounded.\n  std::array<std::uint8_t, 128U> discard{};\n  while (::read(STDIN_FILENO, discard.data(), discard.size()) > 0) {\n  }\n\n'''
if old not in s:
    raise SystemExit("service console begin transport block missing")
s = s.replace(old, new, 1)
old = '''  std::uint8_t buffer[96]{};\n  const int received = usb_serial_jtag_read_bytes(buffer, sizeof(buffer), 0U);\n  if (received <= 0) {\n    return;\n  }\n\n  for (int index = 0; index < received; ++index) {\n'''
new = '''  std::array<std::uint8_t, 96U> buffer{};\n  const ssize_t received = ::read(STDIN_FILENO, buffer.data(), buffer.size());\n  if (received <= 0) {\n    return;\n  }\n\n  for (ssize_t index = 0; index < received; ++index) {\n'''
if old not in s:
    raise SystemExit("service console poll transport block missing")
s = s.replace(old, new, 1)
old = '''  static_cast<void>(usb_serial_jtag_write_bytes(text, std::strlen(text), pdMS_TO_TICKS(50)));\n'''
new = '''  const std::size_t length = std::strlen(text);\n  std::size_t offset = 0U;\n  while (offset < length) {\n    const ssize_t written = ::write(STDOUT_FILENO, text + offset, length - offset);\n    if (written <= 0) {\n      break;\n    }\n    offset += static_cast<std::size_t>(written);\n  }\n'''
if old not in s:
    raise SystemExit("service console write transport block missing")
s = s.replace(old, new, 1)
p.write_text(s)

for filename in ["README.md", "docs/RF433_DEVICE_CODES.md", "docs/CURRENT_STATUS.md", "docs/CONTINUATION_PLAN.md", "continuation.md"]:
    p = Path(filename)
    s = p.read_text()
    s = s.replace("bounded USB service console", "bounded primary-serial service console")
    s = s.replace("USB service console", "primary-serial service console")
    p.write_text(s)

p = Path("docs/CURRENT_STATUS.md")
s = p.read_text()
needle = '''The real-input runtime now includes a bounded primary-serial service console'''
if needle not in s:
    raise SystemExit("CURRENT_STATUS console marker missing")
s = s.replace(
    needle,
    needle + " on the same ESP-IDF primary stdio/UART interface used by the normal CrowPanel CH340 monitor",
    1,
)
p.write_text(s)

p = Path("continuation.md")
s = p.read_text()
needle = '''A bounded primary-serial service console is now integrated into the real-input runtime.'''
if needle not in s:
    raise SystemExit("continuation console marker missing")
s = s.replace(
    needle,
    needle + " It deliberately uses ESP-IDF primary stdin/stdout instead of opening a separate USB Serial/JTAG channel, so the qualified CrowPanel uses the same CH340 serial monitor for logs and commands.",
    1,
)
p.write_text(s)
PY

git diff --check
PC="$(git rev-parse --show-toplevel)/.venv/bin/pre-commit"
if [[ ! -x "$PC" ]]; then
  echo "pre-commit missing" >&2
  exit 2
fi
set +e
"$PC" run --files \
  src/climate/runtime/Stage28ServiceConsole.cpp \
  README.md docs/RF433_DEVICE_CODES.md docs/CURRENT_STATUS.md docs/CONTINUATION_PLAN.md continuation.md
FIRST_RC=$?
set -e
if [[ "$FIRST_RC" -ne 0 ]]; then
  "$PC" run --files \
    src/climate/runtime/Stage28ServiceConsole.cpp \
    README.md docs/RF433_DEVICE_CODES.md docs/CURRENT_STATUS.md docs/CONTINUATION_PLAN.md continuation.md
fi

git diff --check
export CMAKE_BUILD_PARALLEL_LEVEL=1
cmake -S test/host -B build/host-stage28d-service-console-stdio -DCMAKE_BUILD_TYPE=Debug >/tmp/stage28d-console-stdio-cmake.log
cmake --build build/host-stage28d-service-console-stdio --target stage28_service_console_tests rf433_protocol_tests --parallel 1
./build/host-stage28d-service-console-stdio/stage28_service_console_tests
./build/host-stage28d-service-console-stdio/rf433_protocol_tests

GROWBOX_RF433_LOOPBACK_ENABLED=1 GROWBOX_RF433_LOOPBACK_AUTO_SMOKE=0 GROWBOX_RF433_REMOTE_CAPTURE_ENABLED=0 \
  STAGE27C_BUILD_DIR=build/idf-stage28d-service-console-stdio-crowpanel \
  bash scripts/stage27c_crowpanel.sh build

git add src/climate/runtime/Stage28ServiceConsole.cpp \
        README.md docs/RF433_DEVICE_CODES.md docs/CURRENT_STATUS.md docs/CONTINUATION_PLAN.md continuation.md
git commit -m "Use primary serial console for Stage28D service commands"
NEW=$(git rev-parse HEAD)

PYTHON_BIN="$(git rev-parse --show-toplevel)/.venv/bin/python"
if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="$(command -v python3)"
fi

echo "==> pytest"
"$PYTHON_BIN" -m pytest -q -m "not hardware"

echo "==> host C++ tests"
cmake -S test/host -B build/host-tests -DCMAKE_EXPORT_COMPILE_COMMANDS=ON
cmake --build build/host-tests --parallel 1
ctest --test-dir build/host-tests --output-on-failure

echo "==> host clang-tidy"
TIDY_COPY=/tmp/run_clang_tidy_host_stage28d_console_stdio_v1.sh
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

echo "==> ESP-IDF gate"
bash scripts/idf_gate_build.sh

git diff --check
test -z "$(git status --porcelain)"
git fetch -q origin "$BRANCH"
test "$(git rev-parse origin/$BRANCH)" = "$EXPECTED"
git push origin HEAD:"$BRANCH"
git fetch -q origin "$BRANCH"
test "$(git rev-parse origin/$BRANCH)" = "$NEW"

printf 'STAGE28D_SERVICE_CONSOLE_STDIO_READY commit=%s parent=%s parser_tests=pass rf_tests=pass crowpanel_build=pass quality_gate=pass console_transport=primary_stdio runtime_outputs=fake-locked automatic_rf_tx=0\n' "$NEW" "$EXPECTED"
