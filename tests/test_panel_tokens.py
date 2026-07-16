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


def _css_outside_root(source: str) -> str:
    root = _root_block(source)
    if not root:
        return source
    return source.replace(root, "", 1)


def test_chip_tokens_declared_in_root():
    css = PANEL_CSS.read_text(encoding="utf-8")
    root = _root_block(css)
    assert root
    for token in (
        "--chip-pad:",
        "--chip-pad-y:",
        "--chip-pad-x:",
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
    assert "--gap-" in header
    assert "--shadow-" in header


def test_top_message_uses_chip_tokens():
    css = PANEL_CSS.read_text(encoding="utf-8")
    rule = _extract_css_rule(css, ".top-message")
    assert rule
    assert "border-radius: var(--chip-radius)" in rule
    assert "border: var(--chip-border)" in rule
    assert "font-size: var(--chip-font-compact)" in rule
    assert "font-weight: var(--chip-weight)" in rule
    assert "padding: 0 var(--chip-pad-x)" in rule


def test_panel_css_avoids_banned_raw_font_sizes_outside_root():
    css = PANEL_CSS.read_text(encoding="utf-8")
    outside = _css_outside_root(css)
    banned = (
        "font-size: 0.58rem",
        "font-size: 0.48rem",
        "font-size: 0.65rem",
        "font-size: 0.68rem",
        "font-size: 0.72rem",
    )
    for pattern in banned:
        assert pattern not in outside, pattern


def test_inset_and_surface_pad_tokens_declared_in_root():
    css = PANEL_CSS.read_text(encoding="utf-8")
    root = _root_block(css)
    assert root
    for token in (
        "--inset-pad-compact:",
        "--inset-pad-actuator:",
        "--inset-pad-setup-actuator:",
        "--top-card-pad:",
        "--surface-pad-zone:",
        "--surface-pad-actuator-card:",
        "--surface-pad-empty:",
        "--modal-foot-pad:",
        "--live-row-pad-y:",
        "--gap-xl:",
        "--gap-2xl:",
        "--gap-snug:",
        "--gap-compact:",
        "--radius-sm:",
        "--radius-checkbox:",
        "--shadow-modal:",
        "--danger-bg-message:",
    ):
        assert token in root, token


def test_pot_card_mini_cells_use_inset_pad_token():
    css = PANEL_CSS.read_text(encoding="utf-8")
    rule = _extract_css_rule(css, ".pot-card .mini-cell")
    assert rule
    assert "padding: var(--inset-pad-compact)" in rule


def test_panel_css_avoids_banned_raw_padding_outside_root():
    css = PANEL_CSS.read_text(encoding="utf-8")
    outside = _css_outside_root(css)
    matches = re.findall(r"padding:\s*0\.[0-9]+rem", outside)
    assert not matches, f"raw padding outside :root: {matches}"


def test_panel_css_avoids_raw_gap_and_radius_outside_root():
    css = PANEL_CSS.read_text(encoding="utf-8")
    outside = _css_outside_root(css)
    raw_gaps = re.findall(r"(?:^|[^-])(?:gap|row-gap|column-gap):\s*[0-9]", outside)
    # gap: 0 is allowed (explicit none)
    raw_gaps = [
        g
        for g in re.findall(r"(?:gap|row-gap|column-gap):\s*([^;]+)", outside)
        if g.strip() not in {"0", "var(--gap-0)"} and "var(" not in g
    ]
    assert not raw_gaps, f"raw gap outside :root: {raw_gaps}"
    raw_radii = re.findall(r"border-radius:\s*[0-9]", outside)
    assert not raw_radii, f"raw border-radius outside :root: {raw_radii}"


def test_panel_css_avoids_raw_colors_outside_root():
    css = PANEL_CSS.read_text(encoding="utf-8")
    outside = _css_outside_root(css)
    # data-URI SVG for checkbox may embed hex — strip url(...) first
    scrubbed = re.sub(r"url\([^)]+\)", "url()", outside)
    hexes = re.findall(r"#[0-9a-fA-F]{3,8}", scrubbed)
    rgbas = re.findall(r"rgba?\([^)]+\)", scrubbed)
    assert not hexes, f"raw hex outside :root: {hexes}"
    assert not rgbas, f"raw rgba outside :root: {rgbas}"


def test_dead_layout_classes_removed():
    css = PANEL_CSS.read_text(encoding="utf-8")
    for dead in (
        ".zones-grid",
        ".zone-card",
        ".zone-subgroup",
        ".section-grid",
        ".subhead",
        ".live-sensor-col-head",
        ".group-row",
        ".modal-tabs",
        ".help-btn-top",
        "body.modal-open",
    ):
        assert dead not in css, dead


def test_modal_and_menu_use_shadow_tokens():
    css = PANEL_CSS.read_text(encoding="utf-8")
    assert "box-shadow: var(--shadow-menu)" in css
    assert "box-shadow: var(--shadow-modal)" in css
    assert "var(--shadow-modal-focus)" in css
    assert "background: var(--danger-bg-message)" in css
