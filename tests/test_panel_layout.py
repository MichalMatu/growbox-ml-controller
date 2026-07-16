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
    assert "pot-card-cultivation" in render_fn
    assert "field-stack" not in render_fn


def test_cultivation_pot_css_uses_tokenized_grid_like_sensors():
    panel_css = PANEL_CSS.read_text(encoding="utf-8")
    form_js = FORM_JS.read_text(encoding="utf-8")
    cell_fn = _extract_js_function(form_js, "fieldMiniCellWidthClass")
    assert ".pot-card-cultivation" in panel_css
    assert "--pot-cult-vol-w: var(--cell-w-pct)" in panel_css
    assert "--pot-cult-water-w: var(--cell-w-ppm)" in panel_css
    assert "--pot-cult-factor-w: var(--cell-w-factor)" in panel_css
    assert "calc(6ch + var(--field-suffix-pad-1))" in panel_css
    assert "minmax(0, var(--pot-cult-vol-w))" in panel_css
    assert "minmax(0, var(--pot-cult-water-w))" in panel_css
    assert "minmax(0, var(--pot-cult-factor-w))" in panel_css
    assert ".mini-cell.mini-cell-factor" in panel_css
    assert cell_fn
    assert '" mini-cell-pct"' in cell_fn
    assert '" mini-cell-ppm"' in cell_fn
    assert '" mini-cell-factor"' in cell_fn
    assert '" mini-cell-s"' in cell_fn
    assert "pot_volume_l" in cell_fn
    assert "substrate_water_capacity_ml" in cell_fn
    assert "transpiration_factor" in cell_fn
    width_fn = _extract_js_function(form_js, "fieldSuffixWidthClass")
    assert width_fn
    assert '" suffix-w-pct"' in width_fn
    assert '" suffix-w-ppm"' in width_fn
    assert '" suffix-w-s"' in width_fn
    assert '" suffix-w-factor"' in width_fn
    assert width_fn.count('" suffix-w-s"') == 1
    assert '"×"' in width_fn
    assert "--field-input-w-pct:" in panel_css
    assert "--field-input-w-ppm:" in panel_css
    assert "--field-input-w-factor:" in panel_css
    assert ".pot-card .mini-cell.mini-cell-pct" in panel_css


def test_cultivation_pots_match_sensor_pot_card_width():
    panel_css = PANEL_CSS.read_text(encoding="utf-8")
    form_js = FORM_JS.read_text(encoding="utf-8")
    render_fn = _extract_js_function(form_js, "renderZoneCultivationCard")
    assert render_fn
    assert "pot-card cultivation-pot-card" in render_fn
    assert "--pot-sensor-card-w: calc(" in panel_css
    assert "--pot-card-w: calc(" in panel_css
    pot_rule = re.search(r"\.pot-card\s*\{[^}]+\}", panel_css)
    assert pot_rule
    assert "min-width: 0" in pot_rule.group(0)
    assert "width: auto" in pot_rule.group(0)
    assert "flex: 0 1 auto" in pot_rule.group(0)
    assert "width: var(--pot-sensor-card-w)" not in pot_rule.group(0)


def test_sensor_pot_fields_use_horizontal_layout_reference():
    """Positive reference: czujniki donic keep Wilg. + Gleba T side by side."""
    panel_css = PANEL_CSS.read_text(encoding="utf-8")
    assert ".pot-card-sensors" in panel_css
    assert "grid-template-columns: var(--pot-sensor-w) var(--pot-sensor-w-temp)" in panel_css
    assert "--pot-sensor-w: var(--cell-w-pct)" in panel_css
    assert "--pot-sensor-card-w: calc(" in panel_css
    assert "--pot-card-w: calc(" in panel_css
    assert "--pot-cult-vol-w:" in panel_css
    assert re.search(
        r"\.compact-row\.pots-row\s*\{[^}]*flex-wrap:\s*nowrap",
        panel_css,
    )


def test_zone_soil_target_labels_use_donica_names():
    constants_js = (PANEL_STATIC / "js" / "constants.js").read_text(encoding="utf-8")
    form_js = FORM_JS.read_text(encoding="utf-8")
    for index in range(1, 5):
        assert f'zone_{index}_target_soil_moisture_pct: "Donica {index}"' in constants_js
    assert "zone_(\\d+)_target_soil_moisture_pct" in form_js


def test_diagnostics_modal_uses_live_data_tables_like_previous():
    diagnostics_js = (PANEL_STATIC / "js" / "diagnostics.js").read_text(encoding="utf-8")
    panel_css = PANEL_CSS.read_text(encoding="utf-8")
    assert "function renderDiagTable" in diagnostics_js
    assert "live-sensors-split diag-split" in diagnostics_js
    assert 'live-table-group-head">${escapeHtml(title)}</th>' in diagnostics_js
    assert "diag-row" not in diagnostics_js
    assert ".diag-split .live-data-table col.sensor-col { width: 42%; }" in panel_css
    assert "overflow: visible" in panel_css.split(".diag-split .live-data-table tbody th")[1]
    assert 'label: "malloc→PSRAM"' in diagnostics_js
    assert "diag-meter-head--solo" in diagnostics_js
    assert "showLabel: false" in diagnostics_js
    assert "return `${formatBytes(used)} / ${formatBytes(total)}`;" in diagnostics_js
    assert "formatUsagePct" not in diagnostics_js
    assert "diag-meter-pct" not in panel_css


def test_nutrient_soil_delta_field_has_celsius_suffix():
    form_js = FORM_JS.read_text(encoding="utf-8")
    suffix_fn = _extract_js_function(form_js, "fieldUnitSuffix")
    assert 'maximum_nutrient_soil_delta_c: "°C"' in suffix_fn


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
    assert 'renderSafetyParamCell("CO₂", SAFETY_CO2_FIELDS)' in render_fn
    assert 'renderSafetyFieldsSubCard("CO₂"' not in render_fn


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
    # Legacy multi-column / zone-card grids removed in favor of card-stack + pots-row
    assert ".zones-grid" not in panel_css
    assert ".section-grid" not in panel_css
    assert "growbox-params-split" not in panel_css


def test_main_page_keeps_two_column_layout():
    panel_css = PANEL_CSS.read_text(encoding="utf-8")
    html = INDEX_HTML.read_text(encoding="utf-8")
    assert "left-panel" in html
    assert "right-panel" in html
    assert re.search(
        r"main\s*\{[^}]*grid-template-columns:\s*minmax\(280px,\s*1\.15fr\)\s*minmax\(260px,\s*0\.85fr\)",
        panel_css,
    )


def test_suffix_padding_scales_with_unit_length():
    form_js = FORM_JS.read_text(encoding="utf-8")
    panel_css = PANEL_CSS.read_text(encoding="utf-8")
    wrap_fn = _extract_js_function(form_js, "renderWrappedNumberInput")
    wide_fn = _extract_js_function(form_js, "isWideField")
    size_fn = _extract_js_function(form_js, "fieldSuffixSizeClass")
    width_fn = _extract_js_function(form_js, "fieldSuffixWidthClass")
    assert size_fn
    assert '" suffix-pad-1"' in size_fn
    assert '" suffix-pad-2"' in size_fn
    assert "suffix-short" not in size_fn
    assert width_fn
    assert '" suffix-w-s"' in width_fn
    assert "fieldSuffixWidthClass(suffix)" in wrap_fn
    assert "minimum_interval" not in wide_fn
    assert "--field-suffix-pad-1:" in panel_css
    assert "--field-suffix-pad-2:" in panel_css
    assert "--field-suffix-pad-med:" in panel_css
    assert ".suffix-pad-1 .field-control" in panel_css
    assert "padding-right: var(--field-suffix-pad-med)" in panel_css
    assert "suffix-short" not in panel_css
    assert "--actuator-input-w-s:" in panel_css
    assert ".pot-card .mini-cell .field-input-wrap" in panel_css
    assert ".mini-cell .field-input-wrap" in panel_css


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
    assert "--actuator-input-w: var(--cell-w-pct)" in panel_css


def test_watt_fields_use_one_ch_narrower_width_than_pct():
    form_js = FORM_JS.read_text(encoding="utf-8")
    panel_css = PANEL_CSS.read_text(encoding="utf-8")
    width_fn = _extract_js_function(form_js, "fieldSuffixWidthClass")
    assert '"W"' in width_fn
    assert '" suffix-w-w"' in width_fn
    assert "--cell-w-w: calc(var(--cell-w-pct) - 1ch)" in panel_css
    assert "--actuator-input-w-w: var(--cell-w-w)" in panel_css
    assert ".actuator-input-wrap.suffix-w-w" in panel_css


def test_zone_heat_mat_max_power_uses_in_input_w_suffix():
    form_js = FORM_JS.read_text(encoding="utf-8")
    suffix_fn = _extract_js_function(form_js, "fieldUnitSuffix")
    assert "zone_\\d+_heat_mat_" in suffix_fn
    assert "heat_mat_${zoneHeatMat[1]}" in suffix_fn or "heat_mat_" in suffix_fn
    assert 'heat_mat_max_power_w: "W"' in suffix_fn


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
    soil_fn = _extract_js_function(form_js, "renderSoilTargetMiniCell")
    assert "fieldMiniCellWidthClass(field)" in soil_fn
    assert "syncInactiveZoneDependentInputs" in form_js
    assert "syncInactiveZonePumpInputs" in form_js
    assert "zoneIndexFromPumpGroup" in form_js
    assert "inactive-zone-pump" in cell_fn
    assert "inactive-zone-target" in panel_css
    assert "inactive-zone-pump" in panel_css


def test_ppm_cells_use_one_ch_narrower_width():
    form_js = FORM_JS.read_text(encoding="utf-8")
    panel_css = PANEL_CSS.read_text(encoding="utf-8")
    width_fn = _extract_js_function(form_js, "fieldSuffixWidthClass")
    cell_fn = _extract_js_function(form_js, "fieldMiniCellWidthClass")
    assert width_fn
    assert cell_fn
    assert '"ppm"' in width_fn
    assert '" suffix-w-ppm"' in width_fn
    assert '" mini-cell-ppm"' in cell_fn
    assert "--cell-w-ppm:" in panel_css
    assert "--actuator-input-w-ppm: var(--cell-w-ppm)" in panel_css
    assert "--cell-w-ppm: calc(var(--cell-w) - 2ch)" in panel_css
    assert ".mini-cell.mini-cell-ppm" in panel_css
    assert ".actuator-input-wrap.suffix-w-ppm" in panel_css


def test_humidity_pct_cells_use_three_ch_narrower_width():
    form_js = FORM_JS.read_text(encoding="utf-8")
    panel_css = PANEL_CSS.read_text(encoding="utf-8")
    width_fn = _extract_js_function(form_js, "fieldSuffixWidthClass")
    cell_fn = _extract_js_function(form_js, "fieldMiniCellWidthClass")
    assert width_fn
    assert cell_fn
    assert '"%"' in width_fn
    assert '" suffix-w-pct"' in width_fn
    assert '" mini-cell-pct"' in cell_fn
    assert "--cell-w-pct:" in panel_css
    assert "calc(var(--cell-w) - 3ch)" in panel_css
    assert ".mini-cell.mini-cell-pct" in panel_css


def test_temperature_sensor_cells_render_wrapped_with_narrower_mini_cell():
    form_js = FORM_JS.read_text(encoding="utf-8")
    panel_css = PANEL_CSS.read_text(encoding="utf-8")
    sensor_fn = _extract_js_function(form_js, "renderPathSensorMiniCell")
    width_fn = _extract_js_function(form_js, "fieldSuffixWidthClass")
    cell_fn = _extract_js_function(form_js, "fieldMiniCellWidthClass")
    wrap_fn = _extract_js_function(form_js, "renderWrappedNumberInput")
    assert sensor_fn
    assert cell_fn
    assert width_fn
    assert "fieldMiniCellWidthClass(wrappedSensor)" in sensor_fn
    assert '"°C"' in width_fn
    assert '" suffix-w-temp"' in width_fn
    assert '" mini-cell-temp"' in cell_fn
    assert "renderWrappedNumberInput" in sensor_fn
    assert "field-input-wrap" in wrap_fn
    assert "field-input-suffix" in wrap_fn
    assert "--cell-w-temp:" in panel_css
    assert ".mini-cell.mini-cell-temp" in panel_css
    assert "calc(var(--cell-w) - 2ch)" in panel_css


def test_previous_actuators_use_readonly_live_style_two_column_tables():
    form_js = FORM_JS.read_text(encoding="utf-8")
    panel_css = PANEL_CSS.read_text(encoding="utf-8")
    main_js = (PANEL_STATIC / "js" / "main.js").read_text(encoding="utf-8")
    scenario_js = (PANEL_STATIC / "js" / "scenario.js").read_text(encoding="utf-8")
    prev_block = _extract_js_function(form_js, "renderPreviousBlock")
    prev_group = _extract_js_function(form_js, "renderPreviousGroupTable")
    prev_row = _extract_js_function(form_js, "renderPreviousRow")
    sync_fn = _extract_js_function(form_js, "syncPreviousDisplay")
    assert prev_block
    assert prev_group
    assert prev_row
    assert sync_fn
    assert "live-sensors-split" in prev_block
    assert "previous-split" in prev_block
    assert "renderPreviousGroupTable" in prev_block
    assert "live-data-table" in prev_group
    assert "live-sensor-col-head" not in prev_group
    assert 'live-table-group-head">${title}</th>' in prev_group
    assert "data-previous-path" in prev_row
    assert "renderMiniCell" not in prev_block
    assert "targets-split" not in prev_block
    assert "#setup-pane-previous [data-previous-path]" in sync_fn
    assert "renderPreviousBlock(true)" in form_js
    assert 'id="previous-section"' not in INDEX_HTML.read_text(encoding="utf-8")
    assert 'bindFormInputRoot(document.getElementById("previous-section"))' not in main_js
    assert 'document.getElementById("previous-section")' not in scenario_js
    assert ".previous-split .live-data-table col.sensor-col" in panel_css


def test_lights_cell_is_two_ch_narrower_without_separate_display_width():
    form_js = FORM_JS.read_text(encoding="utf-8")
    panel_css = PANEL_CSS.read_text(encoding="utf-8")
    lights_fn = _extract_js_function(form_js, "renderLightsActiveCell")
    sync_fn = _extract_js_function(form_js, "syncLightsActiveDisplay")
    assert lights_fn
    assert sync_fn
    assert "pseudo-lights-cell" in lights_fn
    assert 'type="text"' in lights_fn
    assert "display.value" in sync_fn
    assert "--cell-w-lights:" in panel_css
    assert "calc(var(--cell-w) - 2ch)" in panel_css
    assert ".sensors-panel .mini-cell.pseudo-lights-cell" in panel_css
    assert "--lights-display-w:" not in panel_css
    assert ".pseudo-lights-display" not in panel_css


def test_temperature_fields_use_integer_precision():
    form_js = FORM_JS.read_text(encoding="utf-8")
    step_fn = _extract_js_function(form_js, "fieldStep")
    step_path_fn = _extract_js_function(form_js, "fieldStepForPath")
    temp_fn = _extract_js_function(form_js, "isTemperatureCPath")
    assert temp_fn
    assert "temperature_c" in temp_fn
    assert "isTemperatureCPath" in step_fn
    assert "isTemperatureCPath(path)" in step_path_fn
    assert step_fn.index("isTemperatureCPath") < step_fn.index('return "0.1"')


def test_co2_ppm_fields_use_integer_precision():
    form_js = FORM_JS.read_text(encoding="utf-8")
    step_fn = _extract_js_function(form_js, "fieldStep")
    step_path_fn = _extract_js_function(form_js, "fieldStepForPath")
    co2_fn = _extract_js_function(form_js, "isCo2PpmPath")
    assert co2_fn
    assert "co2_ppm" in co2_fn
    assert "dose_ppm_per_full_pulse" in co2_fn
    assert "isCo2PpmPath" in step_fn
    assert "isCo2PpmPath(path)" in step_path_fn
    assert step_fn.index("isCo2PpmPath") < step_fn.index('return "0.1"')


def test_number_input_does_not_coerce_incomplete_typing_to_zero():
    form_js = FORM_JS.read_text(encoding="utf-8")
    scenario_js = SCENARIO_JS.read_text(encoding="utf-8")
    parse_fn = _extract_js_function(form_js, "parseScenarioNumberInput")
    read_fn = _extract_js_function(scenario_js, "readScenarioFromForm")
    main_js = (PANEL_STATIC / "js" / "main.js").read_text(encoding="utf-8")
    assert parse_fn
    assert "isIncompleteNumberInput" in form_js
    assert "return null" in parse_fn
    assert "formatNumbers = true" in read_fn
    assert "parsed === null" in read_fn
    assert "formatNumbers: false" in main_js


def test_humidity_fields_use_integer_precision_and_clamp():
    form_js = FORM_JS.read_text(encoding="utf-8")
    scenario_js = SCENARIO_JS.read_text(encoding="utf-8")
    step_fn = _extract_js_function(form_js, "fieldStep")
    step_path_fn = _extract_js_function(form_js, "fieldStepForPath")
    humidity_fn = _extract_js_function(form_js, "isHumidityPctPath")
    clamp_fn = _extract_js_function(form_js, "clampFieldNumber")
    read_fn = _extract_js_function(scenario_js, "readScenarioFromForm")
    assert humidity_fn
    assert "humidity_pct" in humidity_fn
    assert "soil_moisture_pct" in humidity_fn
    assert "isHumidityPctPath" in step_fn
    assert 'return "1"' in step_fn
    assert "isHumidityPctPath(path)" in step_path_fn
    assert clamp_fn
    assert "formatScenarioNumberInput" in form_js
    assert "parseScenarioNumberInput" in read_fn


def test_transpiration_factor_uses_two_decimal_precision_and_input_guard():
    form_js = FORM_JS.read_text(encoding="utf-8")
    main_js = (PANEL_STATIC / "js" / "main.js").read_text(encoding="utf-8")
    step_fn = _extract_js_function(form_js, "fieldStep")
    step_path_fn = _extract_js_function(form_js, "fieldStepForPath")
    transpiration_fn = _extract_js_function(form_js, "isTranspirationFactorPath")
    enforce_fn = _extract_js_function(form_js, "enforceMaxDecimalPlaces")
    assert transpiration_fn
    assert "transpiration_factor" in transpiration_fn
    assert "isTranspirationFactorPath" in step_fn
    assert "isTranspirationFactorPath(path)" in step_path_fn
    assert 'return "0.01"' in step_fn
    assert enforce_fn
    assert "enforceMaxDecimalPlaces" in main_js
    assert "isTranspirationFactorPath" in main_js


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
    assert "readScenarioFromForm(scenario, opts)" in collect_fn
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
    assert "scenarioBadgeFingerprint(readScenarioFromForm(scenario))" in badge_fn
    assert "deviceScenarioBaseline" in state_js
    assert "setDeviceScenarioBaseline" in scenario_js
    assert "scenarioBadgeFingerprint" in scenario_js
    assert "SCENARIO_BADGE_KEYS" in (PANEL_STATIC / "js" / "constants.js").read_text(
        encoding="utf-8"
    )
    assert "deviceScenarioBaseline === null" in badge_fn
    assert 'bindFormInputRoot(document.getElementById("previous-section"))' not in main_js
    assert "cloneScenarioDoc(base)" in read_fn
    assert "forEachScenarioField" in read_fn
    assert 'document.querySelectorAll("[data-path]")' not in read_fn


def test_play_and_load_force_closed_loop_transport():
    main_js = (PANEL_STATIC / "js" / "main.js").read_text(encoding="utf-8")
    toolbar_js = (PANEL_STATIC / "js" / "toolbar.js").read_text(encoding="utf-8")
    assert "startSimulationTransport" in toolbar_js
    assert "ensureClosedLoopMode" in toolbar_js
    assert "startSimulationTransport()" in main_js
    load_block = main_js.split('if (btn.id === "btn-load")', 1)[1].split(
        'if (btn.id === "btn-step")', 1
    )[0]
    assert "postTransportCommand" in load_block
    assert "closed_loop" in load_block


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
    assert "--pump-input-w:" not in panel_css
    assert "--climate-input-w:" not in panel_css
    assert "--actuator-input-w: var(--cell-w-pct)" in panel_css
    assert re.search(
        r"\.actuators-panel\s+\.actuators-(?:climate|pumps|heat-mats)-block\s+\.mini-cell\.actuator-cell\s*\{[^}]*flex:\s*0\s+1\s+auto",
        panel_css,
    )
    assert re.search(
        r"\.actuator-param\s+\.actuator-input-wrap\s*\{[^}]*width:\s*var\(--actuator-input-w\)",
        panel_css,
    )


def test_growbox_setup_cultivation_fields_use_shared_pot_layout():
    panel_css = PANEL_CSS.read_text(encoding="utf-8")
    assert ".pot-card-cultivation" in panel_css
    assert ".pot-card .mini-cell .field-input-wrap" in panel_css
    assert "container-type: inline-size" in panel_css
    assert ".setup-growbox-body" in panel_css
    assert "--cultivation-input-w:" not in panel_css
    assert "#setup-pane-growbox .cultivation-pot-card" not in panel_css
    assert "--setup-obudowa-cell-w:" not in panel_css
    assert "#setup-pane-growbox .sub-card:not(.pots-block)" not in panel_css
    safety_tail = panel_css.split("#setup-pane-safety", 1)[-1].split(".help-modal-body", 1)[0]
    assert "--cell-w:" not in safety_tail
    pots_rule = re.search(
        r"#setup-pane-growbox\s+\.pots-row\s*\{[^}]+\}",
        panel_css,
    )
    assert pots_rule
    assert "flex-wrap: wrap" in pots_rule.group(0)


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
    assert "--actuator-select-w: calc(2.35rem + 3ch)" in panel_css
    assert "select.setup-control-type-select[data-path]" in main_js
    assert "syncControlTypeField" in main_js


def test_panel_docs_and_help_match_current_ui():
    agents_md = (Path(__file__).resolve().parents[1] / "AGENTS.md").read_text(encoding="utf-8")
    constants_js = (PANEL_STATIC / "js" / "constants.js").read_text(encoding="utf-8")
    assert "setup-modal-backdrop" not in agents_md
    assert "#modal-backdrop" in agents_md
    assert "panel-modal" in agents_md
    assert "Konfig." not in agents_md.split("Układ strony", 1)[1].split("Antywzorzec", 1)[0]
    assert "JSON decyzji" not in constants_js
    assert "<strong>Decyzja</strong>" in constants_js
    assert "jeden przesuwalny modal" in constants_js
    assert "tylko odczyt" in constants_js
    assert "btn-panel-scenario" in INDEX_HTML.read_text(encoding="utf-8")


def test_panel_legacy_cleanup_removes_dead_code_and_renames_helpers():
    html = INDEX_HTML.read_text(encoding="utf-8")
    panel_css = PANEL_CSS.read_text(encoding="utf-8")
    form_js = FORM_JS.read_text(encoding="utf-8")
    live_js = (PANEL_STATIC / "js" / "live.js").read_text(encoding="utf-8")
    diagnostics_js = (PANEL_STATIC / "js" / "diagnostics.js").read_text(encoding="utf-8")
    assert ".previous-live" not in panel_css
    assert "syncPreviousFormInputs" not in form_js
    assert "syncPreviousDisplay" in form_js
    assert "syncPreviousDisplay" in live_js
    assert "openDiagnosticsModal" not in diagnostics_js
    assert "btn-json-scenario" not in html
    assert 'id="btn-panel-scenario"' in html


def test_live_section_includes_pots_lights_and_zone_readings():
    live_js = (PANEL_STATIC / "js" / "live.js").read_text(encoding="utf-8")
    constants_js = (PANEL_STATIC / "js" / "constants.js").read_text(encoding="utf-8")
    panel_css = PANEL_CSS.read_text(encoding="utf-8")
    metrics_fn = _extract_js_function(live_js, "renderLiveMetricsTable")
    climate_fn = _extract_js_function(live_js, "renderLiveClimateColumn")
    group_fn = _extract_js_function(live_js, "renderLiveSensorGroupBlock")
    pots_fn = _extract_js_function(live_js, "renderLivePotGroupTable")
    assert metrics_fn
    assert climate_fn
    assert group_fn
    assert pots_fn
    assert "renderLiveClimateColumn(decision)" in metrics_fn
    assert "renderLivePotGroupTable(decision)" in metrics_fn
    assert "live-sensor-col-climate" in climate_fn
    assert "LIVE_SENSOR_GROUPS.map" in climate_fn
    assert "POT_SENSOR_ROWS" in pots_fn
    assert "${potNo} Wilg." in pots_fn
    assert "live-sensor-col-head" not in group_fn
    assert "live-sensor-col-head" not in pots_fn
    assert 'live-table-group-head">${group.title}</th>' in group_fn
    assert 'live-table-group-head">Donice</th>' in pots_fn
    assert "Donica" not in pots_fn
    assert ".live-table-group-head" in panel_css
    assert 'kind: "pseudo"' in constants_js
    assert 'label: "Lampa"' in constants_js
    assert "isLiveZoneActive(decision, index)" in pots_fn
    assert "liveZoneSoilTarget" in live_js
    assert "LIVE_SOIL_TARGET_HINT" in live_js
    assert re.search(r"\.live-sensors-split\s*\{[^}]*grid-template-columns:\s*1fr\s+1fr", panel_css)
    assert ".live-sensor-col-climate" in panel_css


def test_info_modals_use_header_zamknij_without_footer_ok():
    html = INDEX_HTML.read_text(encoding="utf-8")
    for backdrop_id in ("help-modal-backdrop", "notice-modal-backdrop"):
        block = html.split(f'id="{backdrop_id}"', 1)[1].split("</div>\n\n  <div", 1)[0]
        assert "modal-chrome-head" in block
        assert "modal-head-close" in block
        assert ">Zamknij</button>" in block
        assert "modal-foot" not in block
        assert ">OK</button>" not in block


def test_modal_windows_support_drag_resize_without_glass_overlay():
    html = INDEX_HTML.read_text(encoding="utf-8")
    panel_css = PANEL_CSS.read_text(encoding="utf-8")
    modal_window_js = (PANEL_STATIC / "js" / "modal-window.js").read_text(encoding="utf-8")
    modal_js = (PANEL_STATIC / "js" / "modal.js").read_text(encoding="utf-8")
    assert "modal-window.js" in html
    assert "backdrop-filter" not in panel_css
    assert "background: transparent" in panel_css
    assert "--surface-overlay-window: transparent" in panel_css
    assert ".modal--windowed" in panel_css
    assert ".modal--focused" in panel_css
    assert ".modal-resize-handle" in panel_css
    assert "pointer-events: none" in panel_css
    assert "#help-modal-backdrop.open { z-index:" not in panel_css
    assert "initModalWindows" in modal_window_js
    assert "raiseModalBackdrop" in modal_window_js
    assert "closeTopmostModal" in modal_window_js
    assert "topmostOpenModalBackdrop" in modal_js
    assert "modal--dragging" in modal_window_js


def test_panel_modal_unifies_all_entry_points_in_one_wide_shell():
    html = INDEX_HTML.read_text(encoding="utf-8")
    panel_css = PANEL_CSS.read_text(encoding="utf-8")
    modal_js = (PANEL_STATIC / "js" / "modal.js").read_text(encoding="utf-8")
    modal_block = html.split('id="modal-backdrop"', 1)[1].split("</div>\n\n  <script", 1)[0]
    assert 'class="modal modal--wide panel-modal"' in html
    assert "setup-modal-backdrop" not in html
    assert 'id="panel-modal-body"' in modal_block
    assert 'id="setup-pane-growbox"' in modal_block
    assert 'id="setup-pane-safety"' in modal_block
    assert 'id="modal-tabs"' not in modal_block
    assert "modal-foot" not in modal_block
    assert 'id="modal-close"' in modal_block
    assert "modal-chrome-head" in modal_block
    assert "modal-head-close" in modal_block
    assert "panelModalViews" in modal_js
    assert "syncPanelModalActions" in modal_js
    assert "renderPanelModalTabs" not in modal_js
    for key in ("scenario", "decision", "history", "device", "diagnostics", "growbox", "safety"):
        assert f"{key}:" in modal_js
    assert "--modal-w-wide:" in panel_css
    assert ".modal-chrome-head" in panel_css
    assert ".modal-head-close" in panel_css
    assert ".panel-modal-body" in panel_css
    assert ".panel-modal-body > textarea:not([hidden])" in panel_css
    assert "min-height: calc(min(var(--modal-body-min-h-wide), 58vh)" in panel_css
    assert 'data-panel-modal="scenario"' in html


def test_growbox_setup_modal_has_single_help_entry_point():
    form_js = FORM_JS.read_text(encoding="utf-8")
    modal_js = (PANEL_STATIC / "js" / "modal.js").read_text(encoding="utf-8")
    growbox_fn = _extract_js_function(form_js, "renderGrowboxPanel")
    setup_fn = _extract_js_function(form_js, "renderSetupPanes")
    html = INDEX_HTML.read_text(encoding="utf-8")
    assert growbox_fn
    assert setup_fn
    assert "renderGrowboxPanel(true)" in setup_fn
    assert "renderPreviousBlock(true)" in setup_fn
    assert 'inSetup ? null : "environment"' in growbox_fn
    assert 'id="modal-help"' not in html
    assert 'help: "environment"' in modal_js
    assert 'help: "safety"' in modal_js
    assert 'help: "previous"' in modal_js
    assert 'pane: "previous"' in modal_js


def test_panel_action_btn_tokens_and_live_zone_filter():
    html = INDEX_HTML.read_text(encoding="utf-8")
    panel_css = PANEL_CSS.read_text(encoding="utf-8")
    live_js = (PANEL_STATIC / "js" / "live.js").read_text(encoding="utf-8")
    modal_js = (PANEL_STATIC / "js" / "modal.js").read_text(encoding="utf-8")
    fixture = (
        Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "panel_decision.json"
    ).read_text(encoding="utf-8")
    pots_fn = _extract_js_function(live_js, "renderLivePotGroupTable")
    target_fn = _extract_js_function(live_js, "liveZoneSoilTarget")
    assert "ghost panel-action-btn" in html
    assert "live-panel-actions" not in html
    assert ".live-box > .panel-actions" in panel_css
    assert ".panel-action-btn" in panel_css
    assert "--panel-action-inset-top:" in panel_css
    assert "--panel-action-tab-min-w:" in panel_css
    assert "syncPanelModalActions" in modal_js
    assert "panel-action-btn" in html
    assert "isLiveZoneActive" in pots_fn
    assert '"available": false' in fixture
    assert "Brak aktywnych donic" in pots_fn
    assert target_fn
    assert "targets?.soil_moisture_pct" in target_fn
    assert "LIVE_SOIL_TARGET_HINT" in target_fn
    assert "Cel z formularza" in live_js
    assert '"targets": { "soil_moisture_pct":' in fixture


def test_decision_wire_includes_zone_soil_targets():
    codec = (
        Path(__file__).resolve().parents[1] / "src" / "demo" / "protocol" / "ScenarioWireCodec.cpp"
    ).read_text(encoding="utf-8")
    start = codec.index("void addDecisionContext")
    end = codec.index("bool parseLoadScenario", start)
    fn = codec[start:end]
    assert "zone_targets" in fn
    assert "target_soil_moisture_pct" in fn


def test_panel_action_buttons_share_ghost_style_tokens():
    html = INDEX_HTML.read_text(encoding="utf-8")
    panel_css = PANEL_CSS.read_text(encoding="utf-8")
    main_js = (PANEL_STATIC / "js" / "main.js").read_text(encoding="utf-8")
    assert 'class="panel-actions btn-row"' in html
    assert "setup-actions" not in html
    assert "json-actions" not in html
    assert "toolbar-setup-row" not in html
    assert 'data-panel-modal="growbox"' in html
    assert 'data-panel-modal="safety"' in html
    assert 'data-panel-modal="previous"' in html
    assert 'data-panel-modal="scenario"' in html
    assert 'data-panel-modal="device">Status</button>' in html
    assert "Startup / status" not in html
    assert 'class="ghost panel-action-btn"' in html
    assert "data-setup-open" not in html
    assert "[data-panel-modal]" in main_js
    assert html.index("btn-panel-diagnostics") < html.index("btn-setup-growbox")
    assert "--panel-action-pad:" in panel_css
    assert "--panel-action-font:" in panel_css
    assert "--panel-action-gap:" in panel_css
    assert ".panel-action-btn.active" in panel_css


def test_previous_modal_shows_step_badge_one_before_live():
    html = INDEX_HTML.read_text(encoding="utf-8")
    live_js = (PANEL_STATIC / "js" / "live.js").read_text(encoding="utf-8")
    modal_js = (PANEL_STATIC / "js" / "modal.js").read_text(encoding="utf-8")
    form_js = FORM_JS.read_text(encoding="utf-8")
    constants_js = (PANEL_STATIC / "js" / "constants.js").read_text(encoding="utf-8")
    panel_css = PANEL_CSS.read_text(encoding="utf-8")
    render_fn = _extract_js_function(live_js, "renderOutputs")
    assert 'id="modal-step-badge"' in html
    assert "modal-head-title-wrap" in html
    assert "refreshModalStepBadge" in modal_js
    assert "previousStepForDisplay" in modal_js
    assert "previousStepForDisplay" in live_js
    assert "capturePreviousDisplay(decision)" in render_fn
    assert "capturePreviousDisplay(decision);" in render_fn.split("syncPreviousActuators", 1)[0]
    assert "lastRenderedPreviousStep = Math.max(0, step - 1)" in live_js
    assert "previousDisplaySnapshot" in live_js
    assert "previousDisplaySnapshot || scenario" in form_js
    assert "Krok N−1" in constants_js
    assert ".modal-step-badge" in panel_css
    assert ".pill[hidden]" in panel_css
    assert "display: none !important" in panel_css.split(".pill[hidden]", 1)[1]


def test_toolbar_has_no_scenario_preset_selector():
    html = INDEX_HTML.read_text(encoding="utf-8")
    form_js = (PANEL_STATIC / "js" / "main.js").read_text(encoding="utf-8")
    assert "scenario-preset" not in html
    assert "populatePresetSelect" not in form_js
    assert "btn-defaults" in html


def test_v3_nutrient_heater_in_climate_actuator_groups():
    constants_js = (PANEL_STATIC / "js" / "constants.js").read_text(encoding="utf-8")
    form_js = FORM_JS.read_text(encoding="utf-8")
    assert "ACTUATOR_HEAT_MAT_GROUPS" in constants_js
    assert "nutrient_heater_available" in constants_js
    assert "Grzałka roztworu" in constants_js
    block_fn = _extract_js_function(form_js, "renderActuatorBlock")
    assert block_fn
    assert "ACTUATOR_HEAT_MAT_GROUPS" in block_fn
    assert "actuators-heat-mats-block" in block_fn
    cell_fn = _extract_js_function(form_js, "renderActuatorGroupCell")
    assert "field-stack" in cell_fn
    assert "flex-direction: column" not in cell_fn


def test_v3_soil_temperature_targets_use_two_pot_rows():
    constants_js = (PANEL_STATIC / "js" / "constants.js").read_text(encoding="utf-8")
    form_js = FORM_JS.read_text(encoding="utf-8")
    panel_css = PANEL_CSS.read_text(encoding="utf-8")
    for index in range(1, 5):
        assert f'zone_{index}_target_soil_temperature_c: "Donica {index}"' in constants_js
    targets_fn = _extract_js_function(form_js, "renderTargetsBlock")
    assert "TARGET_SOIL_TEMPERATURE_FIELDS" in targets_fn
    assert "TARGET_SOIL_MOISTURE_FIELDS" in targets_fn
    assert "renderSoilTargetMiniCell" in targets_fn
    assert "targets-pots-grid" in targets_fn
    assert "targets-pots-row" in targets_fn
    assert "field-stack" not in targets_fn
    assert "--targets-pot-cell-w: var(--cell-w-pct)" in panel_css
    assert ".targets-pots-row .mini-cell.mini-cell-pct" in panel_css
    assert ".targets-pots-row .mini-cell.mini-cell-temp" in panel_css


def test_v3_live_tables_expose_temperature_targets():
    constants_js = (PANEL_STATIC / "js" / "constants.js").read_text(encoding="utf-8")
    live_js = (PANEL_STATIC / "js" / "live.js").read_text(encoding="utf-8")
    assert 'targetKey: "nutrient_solution_temperature_c"' in constants_js
    assert "liveZoneSoilTempTarget" in live_js
    assert "targets?.soil_temperature_c" in live_js


def test_v3_previous_outputs_include_heating_actuators():
    constants_js = (PANEL_STATIC / "js" / "constants.js").read_text(encoding="utf-8")
    form_js = FORM_JS.read_text(encoding="utf-8")
    assert "previous_nutrient_heater" in constants_js
    assert "PREVIOUS_HEAT_MAT_FIELDS" in constants_js
    prev_fn = _extract_js_function(form_js, "renderPreviousBlock")
    assert "Maty" in prev_fn
    assert "nutrient_heater:" in constants_js


def test_infrequent_settings_live_in_setup_modal_not_inline_form():
    html = INDEX_HTML.read_text(encoding="utf-8")
    form_js = FORM_JS.read_text(encoding="utf-8")
    render_fn = _extract_js_function(form_js, "renderForm")
    assert render_fn
    assert 'id="setup-pane-growbox"' in html
    assert 'id="setup-pane-previous"' in html
    assert 'data-panel-modal="growbox"' in html
    assert 'data-panel-modal="safety"' in html
    assert 'data-panel-modal="previous"' in html
    assert 'data-panel-modal="actuators"' not in html
    assert "renderGrowboxPanel()" not in render_fn
    assert "renderActuatorPanel()" in render_fn
    assert "renderSafetyBlock()" not in render_fn
    assert "renderSetupPanes()" in render_fn
    assert 'id="safety-section"' not in html
    assert 'data-setup-tab="actuators"' not in html


def test_second_fields_use_narrow_cell_s_token_not_factor():
    form_js = FORM_JS.read_text(encoding="utf-8")
    panel_css = PANEL_CSS.read_text(encoding="utf-8")
    suffix_fn = _extract_js_function(form_js, "fieldUnitSuffix")
    cell_fn = _extract_js_function(form_js, "fieldMiniCellWidthClass")
    assert '"s"' in suffix_fn
    assert 'endsWith("_s")' in suffix_fn
    assert '" mini-cell-s"' in cell_fn
    assert ".mini-cell.mini-cell-s" in panel_css
    assert "--cell-w-s: calc(4ch + var(--field-suffix-pad-s))" in panel_css
    assert ".mini-cell .field-input-wrap.suffix-w-s" in panel_css
    assert "width: var(--field-input-w-s)" in panel_css
    factor_pos = panel_css.index("--cell-w-factor:")
    s_pos = panel_css.index("--cell-w-s:")
    assert s_pos < factor_pos or panel_css.find("4ch", s_pos) >= 0


def test_co2_interval_seconds_suffix_is_s_not_ppm():
    form_js = FORM_JS.read_text(encoding="utf-8")
    suffix_fn = _extract_js_function(form_js, "fieldUnitSuffix")
    generic = suffix_fn.split("const name = field.name", 1)[-1]
    assert 'endsWith("_s")' in generic
    assert generic.index('endsWith("_s")') < generic.index('name.includes("co2")')


def test_panel_width_tokens_are_unified_without_modal_overrides():
    panel_css = PANEL_CSS.read_text(encoding="utf-8")
    assert "--actuator-input-w: var(--cell-w-pct)" in panel_css
    assert "--actuator-input-w-wide: var(--cell-w-ppm)" in panel_css
    assert "--cell-w-s:" in panel_css
    assert "--field-input-w-s: var(--cell-w-s)" in panel_css
    assert "--actuator-input-w-s: var(--cell-w-s)" in panel_css
    assert "--targets-pot-cell-w: var(--cell-w-pct)" in panel_css
    assert "--setup-obudowa-cell-w:" not in panel_css
    assert "--climate-input-w:" not in panel_css
    assert "--pump-input-w:" not in panel_css
    safety_tail = panel_css.split("#setup-pane-safety", 1)[-1].split(".help-modal-body", 1)[0]
    assert "--cell-w:" not in safety_tail
    assert re.search(r"\.card\s*\{[^}]*min-width:\s*0", panel_css)
