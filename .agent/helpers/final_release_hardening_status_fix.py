from pathlib import Path

path = Path("docs/CURRENT_STATUS.md")
text = path.read_text(encoding="utf-8")
old = """## Immediate next work

The next release-readiness step is bounded physical qualification of the current `main` firmware on `/dev/cu.usbserial-1130`. Build/flash the current tree, record the exact code-bearing identity above, and only promote that identity to hardware-qualified after the physical checks pass.

After hardware qualification, resume normal product development from `docs/PROJECT_ROADMAP.md`. Avoid another broad architecture rewrite unless concrete evidence exposes a new responsibility or ownership problem.
"""
if text.count(old) != 1:
    raise RuntimeError(f"expected one stale Immediate next work section, found {text.count(old)}")
path.write_text(text.replace(old, "", 1), encoding="utf-8")
print("FINAL_RELEASE_HARDENING_STATUS_FIX_APPLIED")
