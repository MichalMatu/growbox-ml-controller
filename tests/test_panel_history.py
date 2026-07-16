"""Panel history modal formatting contracts."""

from __future__ import annotations

from pathlib import Path

PANEL_STATIC = Path(__file__).resolve().parents[1] / "tools" / "panel" / "static"
MODAL_JS = PANEL_STATIC / "js" / "modal.js"
PANEL_CSS = PANEL_STATIC / "panel.css"


def _extract_js_function(source: str, name: str) -> str:
    marker = f"function {name}"
    start = source.find(marker)
    if start < 0:
        return ""
    brace = source.find("{", start)
    if brace < 0:
        return ""
    depth = 0
    for index in range(brace, len(source)):
        char = source[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source[start : index + 1]
    return ""


def test_history_modal_uses_html_renderer_not_compact_json():
    modal_js = MODAL_JS.read_text(encoding="utf-8")
    history_block = modal_js.split("history:", 1)[1].split("device:", 1)[0]
    assert 'type: "html"' in history_block
    assert "getHtml:" in history_block
    assert "formatHistoryHtml" in modal_js
    assert "JSON.stringify(h.payload)" not in modal_js


def test_history_html_pretty_prints_payload():
    modal_js = MODAL_JS.read_text(encoding="utf-8")
    payload_fn = _extract_js_function(modal_js, "formatHistoryPayload")
    assert "JSON.stringify(payload, null, 2)" in payload_fn


def test_history_html_has_syntax_highlight_and_entry_chrome():
    modal_js = MODAL_JS.read_text(encoding="utf-8")
    panel_css = PANEL_CSS.read_text(encoding="utf-8")
    assert "highlightJson" in modal_js
    assert "history-entry--${meta.className}" in modal_js
    assert 'className: "tx"' in modal_js
    assert 'className: "rx"' in modal_js
    assert ".history-json .json-key" in panel_css
    assert ".history-entry--tx" in panel_css
