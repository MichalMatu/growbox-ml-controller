"""Panel CSS token contracts — chip/badge family and forbidden raw values."""

from __future__ import annotations

import re
from pathlib import Path

PANEL_CSS = Path(__file__).resolve().parents[1] / "tools" / "panel" / "static" / "panel.css"


def _extract_css_rule(source: str, selector: str) -> str:
    match = re.search(rf"{re.escape(selector)}\s*\{{", source)
    if not match:
        return ""
    start = match.end() - 1
    depth = 0
    for index in range(start, len(source)):
        char = source[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source[match.start() : index + 1]
    return ""


def _root_block(source: str) -> str:
    match = re.search(r":root\s*\{", source)
    if not match:
        return ""
    return _extract_css_rule(source, ":root")


def test_chip_tokens_declared_in_root():
    css = PANEL_CSS.read_text(encoding="utf-8")
    root = _root_block(css)
    assert root
    for token in (
        "--chip-pad:",
        "--chip-font:",
        "--chip-font-compact:",
        "--chip-font-toolbar:",
        "--chip-font-mono:",
        "--chip-radius:",
        "--chip-border:",
        "--chip-bg:",
        "--chip-bg-muted:",
        "--chip-color:",
        "--chip-weight:",
        "--chip-btn-pad:",
        "--chip-btn-font:",
        "--chip-btn-radius:",
        "--chip-btn-line:",
    ):
        assert token in root, token


def test_readonly_chip_family_shares_base_selector():
    css = PANEL_CSS.read_text(encoding="utf-8")
    assert re.search(
        r"\.badge,\s*\n\.sync-badge,\s*\n\.pill\s*\{[^}]*padding:\s*var\(--chip-pad\)",
        css,
    )
    assert re.search(
        r"\.badge,\s*\n\.sync-badge,\s*\n\.pill\s*\{[^}]*border-radius:\s*var\(--chip-radius\)",
        css,
    )
    assert re.search(
        r"\.badge,\s*\n\.sync-badge,\s*\n\.pill\s*\{[^}]*font-size:\s*var\(--chip-font\)",
        css,
    )


def test_badge_btn_uses_chip_button_tokens():
    css = PANEL_CSS.read_text(encoding="utf-8")
    rule = _extract_css_rule(css, ".badge-btn")
    assert rule
    assert "padding: var(--chip-btn-pad)" in rule
    assert "font-size: var(--chip-btn-font)" in rule
    assert "border-radius: var(--chip-btn-radius)" in rule
    assert "line-height: var(--chip-btn-line)" in rule


def test_chip_surfaces_avoid_raw_padding_and_radius():
    css = PANEL_CSS.read_text(encoding="utf-8")
    badge = _extract_css_rule(css, ".badge")
    sync = _extract_css_rule(css, ".sync-badge")
    pill = _extract_css_rule(css, ".pill")
    assert badge and sync and pill
    for rule in (badge, sync, pill):
        assert "padding:" not in rule or "var(--chip-pad)" in rule
        assert "border-radius:" not in rule or "var(--chip-radius)" in rule
    assert "0.06rem" not in sync
    assert "0.1rem 0.4rem" not in pill


def test_panel_css_documents_chip_token_layer():
    css = PANEL_CSS.read_text(encoding="utf-8")
    header = css.split(":root {", 1)[0]
    assert "--chip-" in header
    assert ".sync-badge" in header
