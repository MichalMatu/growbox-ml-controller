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


def test_json_modals_share_textarea_renderer():
    modal_js = MODAL_JS.read_text(encoding="utf-8")
    for key in ("scenario", "decision", "history", "device"):
        block = modal_js.split(f"{key}:", 1)[1].split("\n  },", 1)[0]
        assert 'type: "json"' in block, key
        assert "get:" in block, key
        assert "getHtml:" not in block, key


def test_history_pretty_prints_payload_like_device_modal():
    modal_js = MODAL_JS.read_text(encoding="utf-8")
    history_fn = _extract_js_function(modal_js, "formatHistory")
    if "function formatHistory(state)" in modal_js:
        history_fn = modal_js.split("function formatHistory(state)", 1)[1].split("\nfunction ", 1)[
            0
        ]
    payload_fn = _extract_js_function(modal_js, "formatHistoryPayload")
    device_fn = _extract_js_function(modal_js, "formatDevice")
    assert "===" in history_fn
    assert "JSON.stringify(payload, null, 2)" in payload_fn
    assert "JSON.stringify(state.last_startup, null, 2)" in device_fn
    assert "formatHistoryHtml" not in modal_js
    assert "highlightJson" not in modal_js


def test_history_has_no_separate_modal_css():
    panel_css = PANEL_CSS.read_text(encoding="utf-8")
    assert ".history-" not in panel_css
