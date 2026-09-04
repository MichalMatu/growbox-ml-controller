#!/usr/bin/env bash
set -euo pipefail

EXPECTED=2cb4b8dffb0835460a9e9ba920d9bd888c99d992

test "$(git rev-parse HEAD)" = "$EXPECTED"
git fetch -q origin mvp/environment-controller
test "$(git rev-parse origin/mvp/environment-controller)" = "$EXPECTED"
test -z "$(git status --porcelain)"

cat > src/climate/rf433/Rf433HardwareConfig.h <<'EOF'
#pragma once

#include "climate/rf433/Rf433ProtocolCodec.h"

namespace growbox::app::climate_io::rf433 {

struct RemoteSocketHardwareConfig {
  const char* label;
  FrameConfig on;
  FrameConfig off;
};

// Stage28C freeze for exactly one learned original remote/socket pair.
// The label is intentionally neutral: semantic actuator roles belong above the
// hardware/config layer and are not assigned here.
inline constexpr char kRemoteSocket1Label[] = "remote_socket_1";

// repeat=10 is the physically validated transmit repeat count for reliable
// control with this hardware. It is not claimed to be a measured exact repeat
// count emitted by the original handheld remote.
inline constexpr FrameConfig kRemoteSocket1On{{906118656U, 32U, 2U}, 10U, 575U};
inline constexpr FrameConfig kRemoteSocket1Off{{1040336384U, 32U, 2U}, 10U, 575U};

inline constexpr RemoteSocketHardwareConfig kRemoteSocket1{
    kRemoteSocket1Label,
    kRemoteSocket1On,
    kRemoteSocket1Off,
};

}  // namespace growbox::app::climate_io::rf433
EOF

python3 - <<'PY'
from pathlib import Path
p = Path('test/test_rf433_protocol/test_main.cpp')
s = p.read_text(encoding='utf-8')
inc = '#include "climate/rf433/Rf433HardwareConfig.h"\n'
if inc not in s:
    anchor = '#include "climate/rf433/Rf433ProtocolCodec.h"\n'
    assert anchor in s
    s = s.replace(anchor, inc + anchor, 1)
if '#include <string_view>\n' not in s:
    anchor = '#include <cstdint>\n'
    assert anchor in s
    s = s.replace(anchor, anchor + '#include <string_view>\n', 1)
method = r'''
void testFrozenRemoteSocketHardwareConfig() {
  static_assert(kRemoteSocket1On.key.code == 906118656U);
  static_assert(kRemoteSocket1Off.key.code == 1040336384U);
  static_assert(kRemoteSocket1On.key.bit_length == 32U);
  static_assert(kRemoteSocket1Off.key.bit_length == 32U);
  static_assert(kRemoteSocket1On.key.protocol == 2U);
  static_assert(kRemoteSocket1Off.key.protocol == 2U);
  static_assert(kRemoteSocket1On.pulse_us == 575U);
  static_assert(kRemoteSocket1Off.pulse_us == 575U);
  static_assert(kRemoteSocket1On.repeat == 10U);
  static_assert(kRemoteSocket1Off.repeat == 10U);

  assert(std::string_view(kRemoteSocket1.label) == "remote_socket_1");
  assert(validateFrameConfig(kRemoteSocket1.on) == CodecStatus::Ok);
  assert(validateFrameConfig(kRemoteSocket1.off) == CodecStatus::Ok);
}

'''
if 'void testFrozenRemoteSocketHardwareConfig()' not in s:
    anchor = 'void testValidationBounds() {\n'
    assert anchor in s
    s = s.replace(anchor, method + anchor, 1)
call = '  testFrozenRemoteSocketHardwareConfig();\n'
if call not in s:
    anchor = '  testKnownRemoteSocketPairCodec();\n'
    assert anchor in s
    s = s.replace(anchor, anchor + call, 1)
p.write_text(s, encoding='utf-8')
PY

cat > docs/STAGE28C_FINAL_EVIDENCE.md <<'EOF'
# Stage28C final evidence — one learned RF433 remote/socket pair

Stage28C is frozen for exactly one original remote/socket pair under the neutral hardware label `remote_socket_1`.

## Frozen hardware identity

| command | decimal code | hex code | bits | protocol | pulse | validated TX repeat |
| --- | ---: | --- | ---: | ---: | ---: | ---: |
| ON | 906118656 | `0x36024600` | 32 | 2 | 575 us | 10 |
| OFF | 1040336384 | `0x3E024600` | 32 | 2 | 575 us | 10 |

`repeat=10` is the physically validated transmit setting that reliably controls the paired socket. It is deliberately recorded as an effective TX setting; Stage28C does not claim that the exact repeat count emitted by the original handheld remote was measured.

## Receiver hardening and physical evidence

Hardware-qualified source before this freeze: `2cb4b8dffb0835460a9e9ba920d9bd888c99d992`.

The final hardware recheck on that exact source required, independently for ON and OFF:

- TX queued, started and completed;
- RX capture completed without timeout;
- decoded code exactly matched the requested code;
- 32 bits and protocol 2 matched exactly;
- at least one repeat was observed;
- temporal classification was `SelfTx` for the local TX→RX qualification;
- output path remained `fake-locked`.

The task completed with marker:

`STAGE28C_FINAL_KNOWNPAIR_DONE sha=2cb4b8dffb0835460a9e9ba920d9bd888c99d992 on=906118656 off=1040336384 bits=32 protocol=2 pulse_us=575 tx_repeat=10 safe_rx_restored=1`

The board was finally reflashed into passive RX-only diagnostics with auto-transmit disabled.

## Boundary

The frozen identity is hardware/config only. No semantic role (for example `exhaust_fan`) is assigned here, no Rule/ML mapping is introduced, and this freeze is not physical socket-state acknowledgement. Stage28C does not authorize unattended mains-load control.
EOF

if command -v clang-format >/dev/null 2>&1; then
  clang-format -i src/climate/rf433/Rf433HardwareConfig.h test/test_rf433_protocol/test_main.cpp
fi

git diff --check
! grep -R --line-number --fixed-string 'exhaust_fan' src/climate/rf433/Rf433HardwareConfig.h docs/STAGE28C_FINAL_EVIDENCE.md

cmake -S test/host -B build/host-stage28c-freeze-knownpair-v1
cmake --build build/host-stage28c-freeze-knownpair-v1 -j2
ctest --test-dir build/host-stage28c-freeze-knownpair-v1 --output-on-failure

export GROWBOX_FIRMWARE_GIT_SHA="$EXPECTED"
export GROWBOX_RF433_LOOPBACK_ENABLED=1
export GROWBOX_RF433_LOOPBACK_AUTO_SMOKE=0
export GROWBOX_RF433_REMOTE_CAPTURE_ENABLED=0
export STAGE27C_BUILD_DIR=build/idf-stage28c-freeze-knownpair-v1
scripts/stage27c_crowpanel.sh build

git diff --check
git status --short

git add src/climate/rf433/Rf433HardwareConfig.h test/test_rf433_protocol/test_main.cpp docs/STAGE28C_FINAL_EVIDENCE.md
git commit -m 'Freeze Stage28C RF433 socket identity'
NEW_SHA="$(git rev-parse HEAD)"

git fetch -q origin mvp/environment-controller
test "$(git rev-parse origin/mvp/environment-controller)" = "$EXPECTED"
git push origin HEAD:mvp/environment-controller

printf 'STAGE28C_KNOWNPAIR_FROZEN commit=%s label=remote_socket_1 on=%s off=%s bits=32 protocol=2 pulse_us=575 tx_repeat=10\n' "$NEW_SHA" 906118656 1040336384
