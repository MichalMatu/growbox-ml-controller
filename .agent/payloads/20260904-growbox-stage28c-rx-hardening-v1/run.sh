#!/usr/bin/env bash
set -euo pipefail

EXPECTED=00cc0137adb7aeaa6d69bb6781ac97cb0784c5ab

test "$(git rev-parse HEAD)" = "$EXPECTED"
git fetch -q origin agent-control mvp/environment-controller
test "$(git rev-parse origin/mvp/environment-controller)" = "$EXPECTED"
test -z "$(git status --porcelain)"

python3 - <<'PY'
from pathlib import Path

# 1) Port the proven RX acquisition envelope from the known-working RF433 receiver:
#    100 kHz timing, 10 us hardware glitch rejection, 300 ms idle termination.
path = Path('src/climate/rf433/Rf433RmtLoopback.cpp')
text = path.read_text(encoding='utf-8')
old = '''constexpr std::size_t kRmtMemorySymbols = 64U;\nconstexpr std::uint32_t kRxMinimumSignalNs = 1'250U;\nconstexpr std::uint32_t kRxMaximumSignalNs = 12'000'000U;\nconstexpr std::uint32_t kRxResolutionHz = 1'000'000U;\nconstexpr std::uint32_t kRxToCodecTickRatio = kRxResolutionHz / kRmtResolutionHz;\n'''
new = '''constexpr std::size_t kRmtMemorySymbols = 64U;\n// Stage28C RX hardening mirrors the proven receiver envelope from the same RF433\n// hardware: reject sub-10 us chatter and keep one burst open across repeat gaps.\nconstexpr std::uint32_t kRxMinimumSignalNs = 10'000U;\nconstexpr std::uint32_t kRxMaximumSignalNs = 300'000'000U;\nconstexpr std::uint32_t kRxResolutionHz = kRmtResolutionHz;\nconstexpr std::uint32_t kRxToCodecTickRatio = kRxResolutionHz / kRmtResolutionHz;\nstatic_assert(kRxResolutionHz % kRmtResolutionHz == 0U);\n'''
if old not in text:
    raise SystemExit('Rf433RmtLoopback.cpp RX constants anchor not found')
path.write_text(text.replace(old, new, 1), encoding='utf-8')

# 2) Make the existing diagnostic loopback frame configurable at build time so
#    hardware qualification can exercise the already-proven socket ON/OFF codes
#    without adding semantic device roles.
path = Path('src/climate/ClimateV6RealInputRuntime.cpp')
text = path.read_text(encoding='utf-8')
anchor = '''#ifndef GROWBOX_RF433_REMOTE_CAPTURE_ENABLED\n#define GROWBOX_RF433_REMOTE_CAPTURE_ENABLED 0\n#endif\n'''
extra = '''#ifndef GROWBOX_RF433_LOOPBACK_SMOKE_CODE\n#define GROWBOX_RF433_LOOPBACK_SMOKE_CODE 0xA55A\n#endif\n#ifndef GROWBOX_RF433_LOOPBACK_SMOKE_BITS\n#define GROWBOX_RF433_LOOPBACK_SMOKE_BITS 16\n#endif\n#ifndef GROWBOX_RF433_LOOPBACK_SMOKE_PROTOCOL\n#define GROWBOX_RF433_LOOPBACK_SMOKE_PROTOCOL 1\n#endif\n#ifndef GROWBOX_RF433_LOOPBACK_SMOKE_REPEAT\n#define GROWBOX_RF433_LOOPBACK_SMOKE_REPEAT 3\n#endif\n#ifndef GROWBOX_RF433_LOOPBACK_SMOKE_PULSE_US\n#define GROWBOX_RF433_LOOPBACK_SMOKE_PULSE_US 0\n#endif\n'''
if anchor not in text:
    raise SystemExit('runtime remote-capture macro anchor not found')
text = text.replace(anchor, anchor + extra, 1)
text = text.replace('''      if (rf_loopback.receiveOnce(250U, capture)) {\n''', '''      if (rf_loopback.receiveOnce(750U, capture)) {\n''', 1)
old = '''      const rf433::FrameConfig smoke{{0xA55AU, 16U, 1U}, 3U, 0U};\n'''
new = '''      const rf433::FrameConfig smoke{\n          {static_cast<std::uint32_t>(GROWBOX_RF433_LOOPBACK_SMOKE_CODE),\n           static_cast<std::uint8_t>(GROWBOX_RF433_LOOPBACK_SMOKE_BITS),\n           static_cast<std::uint8_t>(GROWBOX_RF433_LOOPBACK_SMOKE_PROTOCOL)},\n          static_cast<std::uint8_t>(GROWBOX_RF433_LOOPBACK_SMOKE_REPEAT),\n          static_cast<std::uint16_t>(GROWBOX_RF433_LOOPBACK_SMOKE_PULSE_US)};\n'''
if old not in text:
    raise SystemExit('runtime smoke frame anchor not found')
path.write_text(text.replace(old, new, 1), encoding='utf-8')

# 3) Expose smoke-frame parameters through ESP-IDF CMake.
path = Path('src/CMakeLists.txt')
text = path.read_text(encoding='utf-8')
anchor = '''set(GROWBOX_RF433_REMOTE_CAPTURE_ENABLED "0" CACHE STRING "Enable Stage28C passive remote capture diagnostics")\n'''
extra = '''set(GROWBOX_RF433_LOOPBACK_SMOKE_CODE "0xA55A" CACHE STRING "Stage28 RF433 loopback smoke code")\nset(GROWBOX_RF433_LOOPBACK_SMOKE_BITS "16" CACHE STRING "Stage28 RF433 loopback smoke bit length")\nset(GROWBOX_RF433_LOOPBACK_SMOKE_PROTOCOL "1" CACHE STRING "Stage28 RF433 loopback smoke protocol")\nset(GROWBOX_RF433_LOOPBACK_SMOKE_REPEAT "3" CACHE STRING "Stage28 RF433 loopback smoke repeat count")\nset(GROWBOX_RF433_LOOPBACK_SMOKE_PULSE_US "0" CACHE STRING "Stage28 RF433 loopback smoke pulse length; 0 uses protocol default")\n'''
if anchor not in text:
    raise SystemExit('CMake remote-capture option anchor not found')
text = text.replace(anchor, anchor + extra, 1)
anchor = '''    GROWBOX_RF433_REMOTE_CAPTURE_ENABLED=${GROWBOX_RF433_REMOTE_CAPTURE_ENABLED}\n'''
extra = '''    GROWBOX_RF433_LOOPBACK_SMOKE_CODE=${GROWBOX_RF433_LOOPBACK_SMOKE_CODE}\n    GROWBOX_RF433_LOOPBACK_SMOKE_BITS=${GROWBOX_RF433_LOOPBACK_SMOKE_BITS}\n    GROWBOX_RF433_LOOPBACK_SMOKE_PROTOCOL=${GROWBOX_RF433_LOOPBACK_SMOKE_PROTOCOL}\n    GROWBOX_RF433_LOOPBACK_SMOKE_REPEAT=${GROWBOX_RF433_LOOPBACK_SMOKE_REPEAT}\n    GROWBOX_RF433_LOOPBACK_SMOKE_PULSE_US=${GROWBOX_RF433_LOOPBACK_SMOKE_PULSE_US}\n'''
if anchor not in text:
    raise SystemExit('CMake RF compile-definition anchor not found')
path.write_text(text.replace(anchor, anchor + extra, 1), encoding='utf-8')

# 4) Pass the diagnostic frame parameters through the established CrowPanel wrapper.
path = Path('scripts/stage27c_crowpanel.sh')
text = path.read_text(encoding='utf-8')
anchor = '''RF433_REMOTE_CAPTURE_ENABLED="${GROWBOX_RF433_REMOTE_CAPTURE_ENABLED:-0}"\n'''
extra = '''RF433_LOOPBACK_SMOKE_CODE="${GROWBOX_RF433_LOOPBACK_SMOKE_CODE:-0xA55A}"\nRF433_LOOPBACK_SMOKE_BITS="${GROWBOX_RF433_LOOPBACK_SMOKE_BITS:-16}"\nRF433_LOOPBACK_SMOKE_PROTOCOL="${GROWBOX_RF433_LOOPBACK_SMOKE_PROTOCOL:-1}"\nRF433_LOOPBACK_SMOKE_REPEAT="${GROWBOX_RF433_LOOPBACK_SMOKE_REPEAT:-3}"\nRF433_LOOPBACK_SMOKE_PULSE_US="${GROWBOX_RF433_LOOPBACK_SMOKE_PULSE_US:-0}"\n'''
if anchor not in text:
    raise SystemExit('build wrapper remote-capture env anchor not found')
text = text.replace(anchor, anchor + extra, 1)
anchor = '''  -D "GROWBOX_RF433_REMOTE_CAPTURE_ENABLED=$RF433_REMOTE_CAPTURE_ENABLED"\n'''
extra = '''  -D "GROWBOX_RF433_LOOPBACK_SMOKE_CODE=$RF433_LOOPBACK_SMOKE_CODE"\n  -D "GROWBOX_RF433_LOOPBACK_SMOKE_BITS=$RF433_LOOPBACK_SMOKE_BITS"\n  -D "GROWBOX_RF433_LOOPBACK_SMOKE_PROTOCOL=$RF433_LOOPBACK_SMOKE_PROTOCOL"\n  -D "GROWBOX_RF433_LOOPBACK_SMOKE_REPEAT=$RF433_LOOPBACK_SMOKE_REPEAT"\n  -D "GROWBOX_RF433_LOOPBACK_SMOKE_PULSE_US=$RF433_LOOPBACK_SMOKE_PULSE_US"\n'''
if anchor not in text:
    raise SystemExit('build wrapper RF CMake arg anchor not found')
path.write_text(text.replace(anchor, anchor + extra, 1), encoding='utf-8')

# 5) Lock the known neutral remote/socket fingerprints into codec regression tests only.
#    This is hardware identity evidence, not a semantic actuator mapping.
path = Path('test/test_rf433_protocol/test_main.cpp')
text = path.read_text(encoding='utf-8')
anchor = '''void testValidationBounds() {\n'''
method = r'''void testKnownRemoteSocketPairCodec() {
  constexpr std::array<std::uint32_t, 2U> codes{{906118656U, 1040336384U}};
  for (const std::uint32_t code : codes) {
    const FrameConfig config{{code, 32U, 2U}, 10U, 575U};
    EncodedFrame encoded{};
    assert(encodeFrame(config, encoded) == CodecStatus::Ok);
    assert(encoded.symbol_count == 33U);
    assert(encoded.total_ticks == encoded.frame_ticks * 10U);

    DecodeWorkspace workspace{};
    const DecodeResult decoded =
        decodeFrame(encoded.symbols.data(), encoded.symbol_count, workspace);
    assert(decoded.status == DecodeStatus::Decoded);
    assert(decoded.frame == config.key);
    assert(decoded.estimated_pulse_us == 580U);

    std::array<PulseSymbol, kRxCaptureSymbolCapacity> repeated{};
    std::size_t repeated_count = 0U;
    for (std::uint8_t repeat = 0U; repeat < 7U; ++repeat) {
      for (std::size_t i = 0U; i < encoded.symbol_count; ++i) {
        repeated[repeated_count++] = encoded.symbols[i];
      }
    }
    DecodeWorkspace repeated_workspace{};
    const DecodeResult repeated_decoded =
        decodeFrame(repeated.data(), repeated_count, repeated_workspace);
    assert(repeated_decoded.status == DecodeStatus::Decoded);
    assert(repeated_decoded.frame == config.key);
    assert(repeated_decoded.observed_repeats >= 7U);
  }
}

'''
if anchor not in text:
    raise SystemExit('RF protocol test anchor not found')
text = text.replace(anchor, method + anchor, 1)
anchor = '''  testRepeatedCapturePrefersExactFingerprint();\n'''
if anchor not in text:
    raise SystemExit('RF protocol test main anchor not found')
text = text.replace(anchor, anchor + '  testKnownRemoteSocketPairCodec();\n', 1)
path.write_text(text, encoding='utf-8')
PY

if command -v clang-format >/dev/null 2>&1; then
  clang-format -i \
    src/climate/rf433/Rf433RmtLoopback.cpp \
    src/climate/ClimateV6RealInputRuntime.cpp \
    test/test_rf433_protocol/test_main.cpp
fi

git diff --check

cmake -S test/host -B build/host-stage28c-rx-hardening-v1
cmake --build build/host-stage28c-rx-hardening-v1 -j2
ctest --test-dir build/host-stage28c-rx-hardening-v1 --output-on-failure

export GROWBOX_FIRMWARE_GIT_SHA="$EXPECTED"
export GROWBOX_RF433_LOOPBACK_ENABLED=1
export GROWBOX_RF433_LOOPBACK_AUTO_SMOKE=0
export GROWBOX_RF433_REMOTE_CAPTURE_ENABLED=0
export STAGE27C_BUILD_DIR=build/idf-stage28c-rx-hardening-v1
scripts/stage27c_crowpanel.sh build

git diff --check
git status --short

git add \
  src/climate/rf433/Rf433RmtLoopback.cpp \
  src/climate/ClimateV6RealInputRuntime.cpp \
  src/CMakeLists.txt \
  scripts/stage27c_crowpanel.sh \
  test/test_rf433_protocol/test_main.cpp

git commit -m 'Harden Stage28C RF433 receive capture'
NEW_SHA="$(git rev-parse HEAD)"

git fetch -q origin mvp/environment-controller
test "$(git rev-parse origin/mvp/environment-controller)" = "$EXPECTED"
git push origin HEAD:mvp/environment-controller

printf 'STAGE28C_RX_HARDENING_READY commit=%s\n' "$NEW_SHA"
