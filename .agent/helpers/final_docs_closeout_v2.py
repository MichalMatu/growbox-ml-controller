from pathlib import Path

QUAL_SHA = "e03763d019af405087a5fa9c6713a7165d2e623f"


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"expected text not found in {path}: {old[:120]!r}")
    text = text.replace(old, new, 1)
    p.write_text(text, encoding="utf-8")


# CURRENT_STATUS
replace_once(
    "docs/CURRENT_STATUS.md",
    "The exact acceptance identity is intentionally not duplicated in this status file because the firmware embeds the Git SHA. Final closeout requires the same exact `main` commit to pass the repository guards, host/Python tests, clang-tidy, ESP-IDF builds, canonical GitHub checks and the bounded hardware task `20260912-final-main-hardware-qualification-v1`. The terminal task evidence is authoritative for physical qualification.",
    f"Final release-readiness hardening is closed on code-bearing executable `{QUAL_SHA}`. That exact identity passed repository guards, host/Python tests, clang-tidy, ESP-IDF builds, canonical GitHub checks and bounded hardware task `20260912-final-main-hardware-qualification-v1`. The strict 120 s `soak_v=3` run completed with zero violations, and the first valid SCD41 sample released startup fail-closed state immediately (`safety_latched=0`, `safety_reason=0`) instead of entering the historical false recovery hold.",
)
replace_once(
    "docs/CURRENT_STATUS.md",
    "`0a7097a30280ec0f7bb408799c07093761d63e88` is the software-verified structural-cleanup baseline. Current `main` adds the final release-readiness hardening above. Treat the current executable as hardware-qualified only when `20260912-final-main-hardware-qualification-v1` is terminal PASS on that exact same commit; do not infer qualification from an ancestor or a documentation-only descendant.",
    f"`0a7097a30280ec0f7bb408799c07093761d63e88` is the structural-cleanup baseline. Final code-bearing hardening identity `{QUAL_SHA}` is hardware-qualified: Local Agent task `20260912-final-main-hardware-qualification-v1` finished PASS on `/dev/cu.usbserial-1130`, with real inputs and physical outputs/RF loopback/thermal-test sequence disabled. GitHub CI #865 and Sandbox Pack #63 also passed on the same code-bearing SHA. A later documentation-only descendant does not change firmware source and does not replace the exact executable qualification identity above.",
)
replace_once(
    "docs/CURRENT_STATUS.md",
    "## Immediate next work\n\nAfter the exact current `main` commit has green canonical checks and terminal PASS from `20260912-final-main-hardware-qualification-v1`, resume normal product development from `docs/PROJECT_ROADMAP.md`. The cleanup/hardening line is closed at that point; avoid another broad architecture rewrite unless concrete evidence exposes a new responsibility or ownership problem.",
    "## Immediate next work\n\nThe cleanup/hardening line is closed. The next selected product task is **Controller behavior quality**. First, build a replay/telemetry baseline from real growbox data and identify one measurable tuning improvement in temperature/humidity interaction, absolute-humidity ventilation, targets, deadbands, hysteresis or dwell. Define baseline metrics and acceptance criteria before changing production behavior. Avoid another broad architecture rewrite unless concrete evidence exposes a new responsibility or ownership problem.",
)

# CHANGELOG
replace_once(
    "docs/CHANGELOG.md",
    "- Confirmed the intended long-lived remote branches are only `main`, `agent-control` and `gh-pages`; the latter two are required control/publishing branches, not cleanup candidates.",
    f"- Confirmed the intended long-lived remote branches are only `main`, `agent-control` and `gh-pages`; the latter two are required control/publishing branches, not cleanup candidates.\n- Final code-bearing hardening identity: `{QUAL_SHA}`. Local verification passed 500 Python tests (12 hardware/visual skips), all 50 host C++ tests, five architecture/config ownership guards, host clang-tidy and three ESP-IDF builds.\n- Canonical GitHub verification passed CI #865 and Sandbox Pack #63 on the same code-bearing SHA.\n- Bounded current-board qualification `20260912-final-main-hardware-qualification-v1` passed on `/dev/cu.usbserial-1130`: strict 120 s `soak_v=3` reported zero violations, no reset/disconnect/SHA mismatch, and the first valid SCD41 sample cleared startup fail-closed state without a false `RecoveryHold`.\n- Closeout leaves product development ready to move to the roadmap's first priority: evidence-backed controller behavior quality using real telemetry/replay baselines before tuning production behavior.",
)

# PROJECT_ROADMAP
replace_once("docs/PROJECT_ROADMAP.md", "Updated: 2026-09-11", "Updated: 2026-09-12")
replace_once(
    "docs/PROJECT_ROADMAP.md",
    "Latest code-bearing compact software verification: `1a599a58eb57841206ab92c7a5cacf50f7463f78`.\n\nHistorical full Physical H qualification remains evidence for executable `02208d23f403bca3540dbbd652eb55703a044833`; it is not automatically transferable to later refactor SHAs.",
    f"Latest code-bearing release-hardening and bounded hardware qualification identity: `{QUAL_SHA}`. It passed local guards/tests/clang-tidy/ESP-IDF builds, GitHub CI #865, Sandbox Pack #63 and `20260912-final-main-hardware-qualification-v1`.\n\nHistorical full Physical H qualification remains evidence for executable `02208d23f403bca3540dbbd652eb55703a044833`; the 2026-09-12 bounded qualification above is the current safe real-input/fake-locked evidence and must not be mislabeled as the historical full Physical H run.",
)
replace_once(
    "docs/PROJECT_ROADMAP.md",
    "## Active product roadmap\n\n### 1. Controller behavior quality",
    "## Active product roadmap\n\n### Next selected bounded task\n\nStart with **Controller behavior quality**: build a baseline from current real telemetry/replay, quantify temperature/humidity and absolute-humidity ventilation behavior, and select exactly one tuning candidate. Record baseline metrics and acceptance criteria before implementation so the change is evidence-backed and reversible.\n\n### 1. Controller behavior quality",
)

# FRESH_CHAT_BOOTSTRAP
replace_once("docs/FRESH_CHAT_BOOTSTRAP.md", "Updated: 2026-09-11", "Updated: 2026-09-12")
replace_once(
    "docs/FRESH_CHAT_BOOTSTRAP.md",
    "Architecture cleanup is complete. The active phase is normal product development.\n\nLatest code-bearing compact software verification: `1a599a58eb57841206ab92c7a5cacf50f7463f78`.\n\nDo not confuse that software verification with the historical full Physical H qualification, which belongs to exact executable `02208d23f403bca3540dbbd652eb55703a044833`.",
    f"Architecture cleanup and release-readiness hardening are complete. The active phase is normal product development, beginning with the roadmap's Controller behavior quality workstream.\n\nLatest code-bearing bounded hardware-qualified identity: `{QUAL_SHA}`. It passed local software gates, GitHub CI #865, Sandbox Pack #63 and `20260912-final-main-hardware-qualification-v1`.\n\nDo not confuse the current bounded safe real-input/fake-locked qualification with the historical full Physical H run, which remains attached to exact executable `02208d23f403bca3540dbbd652eb55703a044833`. Documentation-only descendants do not replace either executable identity.",
)

# CONTINUATION_PLAN
replace_once("docs/CONTINUATION_PLAN.md", "Updated: 2026-09-11", "Updated: 2026-09-12")
replace_once(
    "docs/CONTINUATION_PLAN.md",
    "Latest code-bearing compact software verification:\n\n`1a599a58eb57841206ab92c7a5cacf50f7463f78`\n\nIt passed architecture/config guards, the focused runtime transport truth regression, `51/51` host tests and one CrowPanel real-input ESP-IDF build.\n\nHistorical full Physical H remains frozen evidence for executable `02208d23f403bca3540dbbd652eb55703a044833`. Later refactor SHAs do not inherit that exact physical qualification.",
    f"Latest code-bearing release-hardening identity:\n\n`{QUAL_SHA}`\n\nIt passed 500 Python tests (12 hardware/visual skips), `50/50` host C++ tests, all five architecture/config ownership guards, host clang-tidy, three ESP-IDF builds, GitHub CI #865, Sandbox Pack #63 and bounded current-board qualification `20260912-final-main-hardware-qualification-v1`.\n\nHistorical full Physical H remains frozen evidence for executable `02208d23f403bca3540dbbd652eb55703a044833`. The current bounded safe real-input/fake-locked qualification is separate evidence and must not be mislabeled as full Physical H.",
)
replace_once(
    "docs/CONTINUATION_PLAN.md",
    "## Next development goal\n\nImprove the product rather than continue architecture work for its own sake. Use `docs/PROJECT_ROADMAP.md` to rank the next change. Prefer small/medium changes with high practical growbox value and software-verifiable behavior.\n\nLikely areas:\n\n- temperature/humidity control quality and tuning;\n- configuration/operator UX;\n- logging/history/explainability/replay;\n- ML-shadow data and evaluation;\n- additional devices only when a concrete use case justifies them.",
    "## Next development goal\n\nThe next selected bounded task is **Controller behavior quality**. Build a real-telemetry/replay baseline, quantify temperature/humidity interaction and absolute-humidity ventilation behavior, then choose exactly one tuning candidate. Define baseline metrics and acceptance criteria before implementation.\n\nAfter that bounded task, continue ranking work from `docs/PROJECT_ROADMAP.md` across configuration/operator UX, logging/history/explainability, ML-shadow quality and justified device expansion.",
)

print("FINAL_DOCS_CLOSEOUT_V2_APPLIED")
