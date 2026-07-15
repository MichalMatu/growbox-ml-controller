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
SCENARIO_JS = PANEL_STATIC / "js" / "scenario.js"
UTIL_JS = PANEL_STATIC / "js" / "util.js"
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


def test_actuator_param_fields_use_in_input_unit_suffixes():
    form_js = FORM_JS.read_text(encoding="utf-8")
    panel_css = PANEL_CSS.read_text(encoding="utf-8")
    render_fn = _extract_js_function(form_js, "renderActuatorParamField")
    wrap_fn = _extract_js_function(form_js, "renderWrappedNumberInput")
    assert render_fn
    assert wrap_fn
    assert "renderWrappedNumberInput" in render_fn
    assert "actuator-input-wrap" in render_fn
    assert "actuator-input-suffix" in render_fn
    assert "fieldUnitSuffix" in form_js
    assert ".actuator-input-wrap" in panel_css
    assert ".actuator-input-suffix" in panel_css
    assert ".field-input-wrap" in panel_css
    assert ".field-input-suffix" in panel_css
    assert "--climate-input-w:" in panel_css


def test_inactive_zone_dependents_are_linked_to_zone_available():
    form_js = FORM_JS.read_text(encoding="utf-8")
    scenario_js = SCENARIO_JS.read_text(encoding="utf-8")
    panel_css = PANEL_CSS.read_text(encoding="utf-8")
    read_fn = _extract_js_function(scenario_js, "readScenarioFromForm")
    cell_fn = _extract_js_function(form_js, "renderActuatorGroupCell")
    assert "applyInactiveZonePolicy" in scenario_js
    assert "applyInactiveZonePolicy(next)" in read_fn
    assert "zone.irrigation.available = false" in scenario_js
    assert "renderSoilTargetMiniCell" in form_js
    assert "syncInactiveZoneDependentInputs" in form_js
    assert "syncInactiveZonePumpInputs" in form_js
    assert "zoneIndexFromPumpGroup" in form_js
    assert "inactive-zone-pump" in cell_fn
    assert "inactive-zone-target" in panel_css
    assert "inactive-zone-pump" in panel_css


def test_mini_cell_number_fields_use_in_input_unit_suffixes_and_hints():
    form_js = FORM_JS.read_text(encoding="utf-8")
    mini_fn = _extract_js_function(form_js, "renderMiniCellInput")
    sensor_fn = _extract_js_function(form_js, "renderPathSensorMiniCell")
    wrap_fn = _extract_js_function(form_js, "renderWrappedNumberInput")
    assert mini_fn
    assert sensor_fn
    assert wrap_fn
    assert "renderWrappedNumberInput" in mini_fn
    assert "renderWrappedNumberInput" in sensor_fn
    assert "fieldHintAttr" in mini_fn
    assert "fieldHintAttr" in sensor_fn
    assert "field-input-wrap" in wrap_fn
    assert "field-input-suffix" in wrap_fn
    assert "fieldUnitSuffix" in wrap_fn


def test_main_actuator_cells_have_no_control_type_toggle():
    form_js = FORM_JS.read_text(encoding="utf-8")
    panel_css = PANEL_CSS.read_text(encoding="utf-8")
    cell_fn = _extract_js_function(form_js, "renderActuatorGroupCell")
    assert cell_fn
    assert "control-type-toggle" not in cell_fn
    assert "renderControlTypeToggle" not in form_js
    assert "toggleControlType" not in form_js
    assert ".control-type-toggle" not in panel_css
    assert "_control_type" in cell_fn


def test_collect_scenario_reads_control_type_from_setup_selects():
    scenario_js = SCENARIO_JS.read_text(encoding="utf-8")
    form_js = FORM_JS.read_text(encoding="utf-8")
    read_fn = _extract_js_function(scenario_js, "readScenarioFromForm")
    collect_fn = _extract_js_function(scenario_js, "collectScenario")
    badge_fn = _extract_js_function(scenario_js, "updateScenarioSyncBadge")
    select_fn = _extract_js_function(form_js, "renderGrowboxActuatorTypeSelect")
    assert read_fn
    assert collect_fn
    assert badge_fn
    assert select_fn
    assert "control-type-toggle" not in read_fn
    assert 'el.tagName === "SELECT"' in read_fn
    assert "setup-control-type-select" in select_fn
    assert "readScenarioFromForm(scenario)" in collect_fn
    assert "wyślij zmiany" in badge_fn
    assert '"lokalne"' not in badge_fn


def test_normalize_control_type_coerces_encoded_defaults():
    util_js = UTIL_JS.read_text(encoding="utf-8")
    fn = _extract_js_function(util_js, "normalizeControlType")
    assert fn
    assert 'return "pwm"' in fn
    assert 'return "binary"' in fn


def test_field_by_name_supports_section_scope_for_duplicate_names():
    form_js = FORM_JS.read_text(encoding="utf-8")
    cell_fn = _extract_js_function(form_js, "renderActuatorGroupCell")
    block_fn = _extract_js_function(form_js, "renderActuatorBlock")
    safety_fn = _extract_js_function(form_js, "renderSafetyFieldsSubCard")
    by_name_fn = _extract_js_function(form_js, "fieldByName")
    assert by_name_fn
    assert "sectionId && section.id !== sectionId" in by_name_fn
    assert "fieldByName(name, sectionId)" in cell_fn
    assert 'renderActuatorRow(ACTUATOR_CLIMATE_GROUPS, "actuators")' in block_fn
    assert 'renderActuatorRow(ACTUATOR_PUMP_GROUPS, "zones")' in block_fn
    assert 'fieldByName(name, "safety")' in safety_fn


def test_for_each_scenario_field_dedupes_duplicate_data_paths():
    scenario_js = SCENARIO_JS.read_text(encoding="utf-8")
    fn = _extract_js_function(scenario_js, "forEachScenarioField")
    assert fn
    assert "seen.has(path)" in fn
    assert "seen.add(path)" in fn


def test_scenario_sync_uses_baseline_fingerprint():
    scenario_js = SCENARIO_JS.read_text(encoding="utf-8")
    main_js = (PANEL_STATIC / "js" / "main.js").read_text(encoding="utf-8")
    state_js = (PANEL_STATIC / "js" / "state.js").read_text(encoding="utf-8")
    badge_fn = _extract_js_function(scenario_js, "updateScenarioSyncBadge")
    read_fn = _extract_js_function(scenario_js, "readScenarioFromForm")
    assert badge_fn
    assert read_fn
    assert "deviceScenarioFromState" not in scenario_js
    assert "scenarioSyncFingerprint(readScenarioFromForm(scenario))" in badge_fn
    assert "deviceScenarioBaseline" in state_js
    assert "setDeviceScenarioBaseline" in scenario_js
    assert "deviceScenarioBaseline === null" in badge_fn
    assert 'bindFormInputRoot(document.getElementById("previous-section"))' in main_js
    assert "cloneScenarioDoc(base)" in read_fn
    assert "forEachScenarioField" in read_fn
    assert 'document.querySelectorAll("[data-path]")' not in read_fn


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
    actuator_rows = re.search(
        r"\.actuators-panel\s+\.actuators-climate-block\s+\.compact-row,\s*"
        r"\.actuators-panel\s+\.actuators-pumps-block\s+\.compact-row\s*\{[^}]+\}",
        panel_css,
    )
    assert actuator_rows
    rule = actuator_rows.group(0)
    assert "flex-wrap: wrap" in rule
    assert "flex-wrap: nowrap" not in rule
    assert not re.search(
        r"\.actuators-panel\s+\.actuators-(?:climate|pumps)-block[^{]*\{[^}]*overflow-x:\s*auto",
        panel_css,
    )
    assert "--pump-input-w:" in panel_css
    assert "--climate-input-w:" in panel_css
    assert re.search(
        r"\.actuators-panel\s+\.actuators-climate-block\s+\.mini-cell\.actuator-cell\s*\{[^}]*flex:\s*0\s+0\s+auto",
        panel_css,
    )
    assert re.search(
        r"\.actuators-panel\s+\.actuators-climate-block\s+\.actuator-input-wrap\s*\{[^}]*width:\s*var\(--climate-input-w\)",
        panel_css,
    )


def test_growbox_setup_cultivation_fields_use_compact_widths():
    panel_css = PANEL_CSS.read_text(encoding="utf-8")
    assert "--cultivation-input-w:" in panel_css
    assert "#setup-pane-growbox .cultivation-pot-card > .compact-row" in panel_css
    assert "display: flex" in panel_css
    assert "#setup-pane-growbox .pots-row" in panel_css


def test_growbox_setup_has_actuator_control_type_selects():
    form_js = FORM_JS.read_text(encoding="utf-8")
    panel_css = PANEL_CSS.read_text(encoding="utf-8")
    main_js = (PANEL_STATIC / "js" / "main.js").read_text(encoding="utf-8")
    growbox_fn = _extract_js_function(form_js, "renderGrowboxPanel")
    actuators_fn = _extract_js_function(form_js, "renderGrowboxActuatorsSubCard")
    card_fn = _extract_js_function(form_js, "renderGrowboxActuatorTypeCard")
    select_fn = _extract_js_function(form_js, "renderGrowboxActuatorTypeSelect")
    sync_fn = _extract_js_function(form_js, "syncControlTypeField")
    assert growbox_fn
    assert actuators_fn
    assert card_fn
    assert select_fn
    assert sync_fn
    assert "renderGrowboxActuatorsSubCard()" in growbox_fn
    assert "setup-actuator-type-card" in card_fn
    assert "setup-control-type-select" in select_fn
    assert "formatEnumOptionLabel" in select_fn
    assert "field-stack" not in card_fn
    assert "renderControlTypeToggle" not in card_fn
    assert "setup-actuators-block" in actuators_fn
    assert "actuators-type-row" in actuators_fn
    assert "#setup-pane-growbox .setup-actuator-type-card" in panel_css
    assert "#setup-pane-growbox .actuators-type-row" in panel_css
    assert "select.setup-control-type-select[data-path]" in main_js
    assert "syncControlTypeField" in main_js


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
