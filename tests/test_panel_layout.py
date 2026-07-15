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
INDEX_HTML = PANEL_STATIC / "index.html"


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


def test_cultivation_pot_css_uses_horizontal_grid_not_column_stack():
    panel_css = PANEL_CSS.read_text(encoding="utf-8")
    assert ".cultivation-pot-card .field-stack" not in panel_css
    assert not re.search(
        r"\.cultivation-pot-card[^{]*\{[^}]*flex-direction:\s*column",
        panel_css,
    )
    grid_rule = re.search(
        r"\.cultivation-pot-card\s*>\s*\.compact-row\s*\{[^}]+\}",
        panel_css,
    )
    assert grid_rule, "cultivation compact-row rule required"
    rule = grid_rule.group(0)
    assert "grid-template-columns" in rule
    assert "repeat(3" in rule


def test_cultivation_pots_match_sensor_pot_card_width():
    panel_css = PANEL_CSS.read_text(encoding="utf-8")
    assert re.search(
        r"\.pot-card\.cultivation-pot-card\s*\{[^}]*width:\s*var\(--pot-card-w\)",
        panel_css,
    )


def test_sensor_pot_fields_use_horizontal_layout_reference():
    """Positive reference: czujniki donic keep Wilg. + Gleba T side by side."""
    panel_css = PANEL_CSS.read_text(encoding="utf-8")
    assert ".pot-card-sensors" in panel_css
    assert "grid-template-columns: 1fr 1fr" in panel_css


def test_zone_soil_target_labels_use_donica_names():
    constants_js = (PANEL_STATIC / "js" / "constants.js").read_text(encoding="utf-8")
    form_js = FORM_JS.read_text(encoding="utf-8")
    for index in range(1, 5):
        assert f'zone_{index}_target_soil_moisture_pct: "Donica {index}"' in constants_js
    assert "zone_(\\d+)_target_soil_moisture_pct" in form_js


def test_safety_section_uses_sub_cards_and_polish_labels():
    constants_js = (PANEL_STATIC / "js" / "constants.js").read_text(encoding="utf-8")
    form_js = FORM_JS.read_text(encoding="utf-8")
    assert "SAFETY_TEMPERATURE_FIELDS" in constants_js
    assert "SAFETY_ANTIFLAP_GROUPS" in constants_js
    assert 'dehumidifier_minimum_on_s: "ON s"' in constants_js
    assert 'fan_venting_co2_threshold: "Fan CO₂"' in constants_js
    render_fn = _extract_js_function(form_js, "renderSafetyBlock")
    assert "Temperatura" in render_fn
    assert "Anty-flapping" in render_fn
    assert "targets-split" in render_fn


def test_page_avoids_broken_multi_column_form_grids():
    """Cards of different heights must not sit in a 2-col page grid (empty gaps)."""
    html = INDEX_HTML.read_text(encoding="utf-8")
    panel_css = PANEL_CSS.read_text(encoding="utf-8")
    form_js = FORM_JS.read_text(encoding="utf-8")
    assert 'id="form-sections" class="card-stack"' in html
    assert "form-grid" not in html
    assert ".form-grid" not in panel_css
    assert "growbox-params-split" not in form_js
    assert ".growbox-params-split" not in panel_css


def test_main_page_keeps_two_column_layout():
    panel_css = PANEL_CSS.read_text(encoding="utf-8")
    html = INDEX_HTML.read_text(encoding="utf-8")
    assert "left-panel" in html
    assert "right-panel" in html
    assert re.search(
        r"main\s*\{[^}]*grid-template-columns:\s*minmax\(280px,\s*1\.15fr\)\s*minmax\(260px,\s*0\.85fr\)",
        panel_css,
    )


def test_actuators_main_page_use_compact_climate_and_pump_rows():
    form_js = FORM_JS.read_text(encoding="utf-8")
    panel_css = PANEL_CSS.read_text(encoding="utf-8")
    render_fn = _extract_js_function(form_js, "renderForm")
    block_fn = _extract_js_function(form_js, "renderActuatorBlock")
    assert render_fn
    assert block_fn
    assert "renderActuatorPanel()" in render_fn
    assert "actuators-climate-block" in block_fn
    assert "actuators-pumps-block" in block_fn
    assert ".actuators-panel .actuators-climate-block .compact-row" in panel_css
    assert ".actuators-panel .actuators-pumps-block .compact-row" in panel_css
    assert "--pump-input-w:" in panel_css
    assert "--climate-input-w:" in panel_css


def test_growbox_setup_cultivation_fields_use_compact_widths():
    panel_css = PANEL_CSS.read_text(encoding="utf-8")
    assert "--cultivation-input-w:" in panel_css
    assert "#setup-pane-growbox .cultivation-pot-card > .compact-row" in panel_css
    assert "display: flex" in panel_css
    assert "#setup-pane-growbox .pots-row" in panel_css


def test_growbox_setup_modal_has_single_help_entry_point():
    form_js = FORM_JS.read_text(encoding="utf-8")
    growbox_fn = _extract_js_function(form_js, "renderGrowboxPanel")
    setup_fn = _extract_js_function(form_js, "renderSetupPanes")
    html = INDEX_HTML.read_text(encoding="utf-8")
    assert growbox_fn
    assert setup_fn
    assert "renderGrowboxPanel(true)" in setup_fn
    assert 'inSetup ? null : "environment"' in growbox_fn
    assert 'id="setup-modal-help"' in html
    assert "SETUP_TAB_HELP" in form_js


def test_toolbar_has_no_scenario_preset_selector():
    html = INDEX_HTML.read_text(encoding="utf-8")
    form_js = (PANEL_STATIC / "js" / "main.js").read_text(encoding="utf-8")
    assert "scenario-preset" not in html
    assert "populatePresetSelect" not in form_js
    assert "btn-defaults" in html


def test_infrequent_settings_live_in_setup_modal_not_inline_form():
    html = INDEX_HTML.read_text(encoding="utf-8")
    form_js = FORM_JS.read_text(encoding="utf-8")
    render_fn = _extract_js_function(form_js, "renderForm")
    assert render_fn
    assert 'id="setup-modal-backdrop"' in html
    assert 'data-setup-open="growbox"' in html
    assert 'data-setup-open="safety"' in html
    assert 'data-setup-open="actuators"' not in html
    assert "renderGrowboxPanel()" not in render_fn
    assert "renderActuatorPanel()" in render_fn
    assert "renderSafetyBlock()" not in render_fn
    assert "renderSetupPanes()" in render_fn
    assert 'id="safety-section"' not in html
    assert 'data-setup-tab="actuators"' not in html
