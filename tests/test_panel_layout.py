"""Panel UI layout contracts and anti-patterns.

Mini-cards (donice, aktuary, cele) keep parameter fields in a horizontal row.
Stacking label+input blocks vertically inside a single pot/zone card is an
anti-pattern — it wastes vertical space and breaks visual parity with Czujniki
and Aktuary.
"""

from __future__ import annotations

import re
from pathlib import Path

PANEL_STATIC = Path(__file__).resolve().parents[1] / "tools" / "panel" / "static"
FORM_JS = PANEL_STATIC / "js" / "form.js"
PANEL_CSS = PANEL_STATIC / "panel.css"


def _extract_js_function(source: str, name: str) -> str:
    match = re.search(rf"function {re.escape(name)}\([^)]*\)\s*\{{", source)
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


def test_cultivation_pot_fields_are_horizontal_not_stacked():
    form_js = FORM_JS.read_text(encoding="utf-8")
    render_fn = _extract_js_function(form_js, "renderZoneCultivationCard")
    assert render_fn, "renderZoneCultivationCard must exist"
    assert "compact-row" in render_fn
    assert "field-stack" not in render_fn


def test_cultivation_pot_css_does_not_column_stack_mini_cells():
    panel_css = PANEL_CSS.read_text(encoding="utf-8")
    assert ".cultivation-pot-card .field-stack" not in panel_css
    assert not re.search(
        r"\.cultivation-pot-card[^{]*\{[^}]*flex-direction:\s*column",
        panel_css,
    )
    assert ".cultivation-pot-card > .compact-row" in panel_css
    compact_rule = re.search(
        r"\.cultivation-pot-card\s*>\s*\.compact-row\s*\{[^}]+\}",
        panel_css,
    )
    assert compact_rule, "cultivation compact-row rule required"
    assert "flex-wrap: nowrap" in compact_rule.group(0)


def test_sensor_pot_fields_use_horizontal_layout_reference():
    """Positive reference: czujniki donic keep Wilg. + Gleba T side by side."""
    panel_css = PANEL_CSS.read_text(encoding="utf-8")
    assert ".pot-card-sensors" in panel_css
    assert "grid-template-columns: 1fr 1fr" in panel_css
