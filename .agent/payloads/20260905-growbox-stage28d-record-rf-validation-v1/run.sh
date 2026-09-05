#!/usr/bin/env bash
set -euo pipefail

EXPECTED_HEAD=7f8ed8588408fccdfcd2ed8b3531f40f530bb02f
BRANCH=mvp/environment-controller
DOC=docs/RF433_DEVICE_CODES.md

git fetch -q origin "$BRANCH"
git reset --hard "$EXPECTED_HEAD"
test "$(git rev-parse HEAD)" = "$EXPECTED_HEAD"
test "$(git rev-parse origin/$BRANCH)" = "$EXPECTED_HEAD"
test -z "$(git status --porcelain)"

python3 - <<'PY'
from pathlib import Path

path = Path("docs/RF433_DEVICE_CODES.md")
text = path.read_text()

replacements = {
    "Updated: 2026-09-04": "Updated: 2026-09-05",
    "| lamp | `remote_socket_2` | pending | 235030016 (`0x0E024600`) | 16926208 (`0x01024600`) | 32 | 2 | 560 us | 10 | capture recorded; ESP -> socket validation pending |": "| lamp | `remote_socket_2` | pending | 235030016 (`0x0E024600`) | 16926208 (`0x01024600`) | 32 | 2 | 560 us | 10 | physically validated with 560 us / repeat 10 |",
    "| humidifier | `remote_socket_3` | pending | 637683200 (`0x26024600`) | 771900928 (`0x2E024600`) | 32 | 2 | 560 us | 10 | capture recorded; ESP -> socket validation pending |": "| humidifier | `remote_socket_3` | pending | 637683200 (`0x26024600`) | 771900928 (`0x2E024600`) | 32 | 2 | 560 us | 10 | physically validated with 560 us / repeat 10 |",
    "STATUS: pending physical ESP -> socket validation": "STATUS: physically validated with 560 us / repeat 10",
    "STATUS: ON/OFF pair and 575 us / repeat 10 physically validated in Stage28C": "STATUS: ON/OFF pair and 575 us / repeat 10 physically validated; revalidated through the Stage28D service console on 2026-09-05",
    "The real-input firmware includes a bounded primary-serial service console. The captured lamp and humidifier profiles are now also frozen in `Rf433HardwareConfig.h` for manual diagnostics, but their physical socket validation is still pending. The fan keeps the already-qualified `575 us / repeat 10` transmit profile.": "The real-input firmware includes a bounded primary-serial service console. The lamp and humidifier profiles are frozen in `Rf433HardwareConfig.h` for manual diagnostics and were physically validated on 2026-09-05 at `560 us / repeat 10`. The fan keeps the physically validated `575 us / repeat 10` transmit profile and was revalidated through the Stage28D service console on 2026-09-05.",
}

for old, new in replacements.items():
    if old not in text:
        raise SystemExit(f"expected text not found: {old}")
    text = text.replace(old, new)

old_section = """## Next physical validation\n\nThe next hardware step is a bounded manual ON/OFF test of each socket/device from the ESP32:\n\n1. lamp: verify ON and OFF;\n2. fan: recheck ON and OFF and compare 560 us against the already qualified 575 us profile;\n3. humidifier: verify ON and OFF.\n\nPhysical observation of the actual lamp/fan/humidifier state is the acceptance criterion. Local TX completion or `SelfTx` reception alone is not sufficient.\n"""
new_section = """## Stage28D physical validation completed\n\nOn 2026-09-05 the operator physically observed successful ON and OFF behavior for all three mains loads while using the bounded primary-serial service commands:\n\n- lamp / `remote_socket_2`: `560 us`, repeat `10`; local evidence task `20260905-growbox-stage28d-manual-rf-lamp-v2`; physical ON/OFF confirmed by the operator;\n- fan / `remote_socket_1`: `575 us`, repeat `10`; local evidence task `20260905-growbox-stage28d-manual-rf-fan-v1`; physical ON/OFF confirmed by the operator;\n- humidifier / `remote_socket_3`: `560 us`, repeat `10`; local evidence task `20260905-growbox-stage28d-manual-rf-humidifier-v1`; physical ON/OFF confirmed by the operator.\n\nThe final manual command for the completed fan and humidifier validation tasks was OFF. The lamp was also physically confirmed through repeated ON/OFF operation. Local TX completion and `SelfTx` remain transport evidence only; the physical operator observation is the acceptance evidence for socket/load response.\n"""
if old_section not in text:
    raise SystemExit("physical validation section anchor not found")
text = text.replace(old_section, new_section)

old_note = "The newly supplied/captured fan pulse is `560 us`. The earlier Stage28C physical ESP transmit qualification for the same ON/OFF pair used `575 us` with repeat `10` and was reliable. Keep both facts until the next bounded physical socket test decides whether the common `560 us` profile is also reliable. Do not rewrite historical Stage28C evidence."
new_note = "The captured fan pulse is `560 us`. The physically qualified ESP transmit profile remains `575 us` with repeat `10`: it was reliable in Stage28C and was physically revalidated through the Stage28D service console on 2026-09-05. Keep the captured `560 us` value as capture evidence; it is not promoted to the validated fan transmit profile. Do not rewrite historical Stage28C evidence."
if old_note not in text:
    raise SystemExit("fan pulse note anchor not found")
text = text.replace(old_note, new_note)

path.write_text(text)
PY

# The replacement above intentionally changes both pending status lines for lamp and humidifier.
# Verify all physical profiles and safety boundary are explicitly present.
grep -F 'lamp | `remote_socket_2`' "$DOC" | grep -F 'physically validated with 560 us / repeat 10'
grep -F 'fan | `remote_socket_1`' "$DOC" | grep -F 'physically validated with 575 us / repeat 10'
grep -F 'humidifier | `remote_socket_3`' "$DOC" | grep -F 'physically validated with 560 us / repeat 10'
grep -F '20260905-growbox-stage28d-manual-rf-lamp-v2' "$DOC"
grep -F '20260905-growbox-stage28d-manual-rf-fan-v1' "$DOC"
grep -F '20260905-growbox-stage28d-manual-rf-humidifier-v1' "$DOC"
grep -F 'Runtime outputs remain fake-locked' "$DOC"

git diff --check
test "$(git status --short | wc -l | tr -d ' ')" = "1"
test "$(git status --short | awk '{print $2}')" = "$DOC"

git add "$DOC"
git commit -m "Record Stage28D physical RF validation"
COMMIT="$(git rev-parse HEAD)"
test "$(git rev-parse HEAD^)" = "$EXPECTED_HEAD"
test -z "$(git status --porcelain)"

printf 'STAGE28D_RF_PHYSICAL_VALIDATION_RECORDED commit=%s parent=%s lamp=560x10 fan=575x10 humidifier=560x10 physical_observation=confirmed runtime_outputs=fake-locked\n' "$COMMIT" "$EXPECTED_HEAD"
