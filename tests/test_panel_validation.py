"""Panel form validation contracts."""

from __future__ import annotations

import re
from pathlib import Path

PANEL_STATIC = Path(__file__).resolve().parents[1] / "tools" / "panel" / "static"
SCENARIO_JS = PANEL_STATIC / "js" / "scenario.js"
MAIN_JS = PANEL_STATIC / "js" / "main.js"
FORM_JS = PANEL_STATIC / "js" / "form.js"
PANEL_CSS = PANEL_STATIC / "panel.css"


def _extract_js_function(source: str, name: str) -> str:
    """Extract a function body; ignore braces in default params (opts = {})."""
    match = re.search(rf"function {re.escape(name)}\s*\([^)]*\)\s*\{{", source)
    if not match:
        # Fallback: signature may span lines or use complex defaults
        marker = f"function {name}"
        start = source.find(marker)
        if start < 0:
            return ""
        paren = source.find("(", start)
        if paren < 0:
            return ""
        depth = 0
        body_start = -1
        for index in range(paren, len(source)):
            char = source[index]
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0:
                    body_start = source.find("{", index)
                    break
        if body_start < 0:
            return ""
        depth = 0
        for index in range(body_start, len(source)):
            char = source[index]
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return source[start : index + 1]
        return ""
    start = match.start()
    brace = match.end() - 1
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


def test_validate_scenario_form_blocks_empty_number_fields():
    scenario_js = SCENARIO_JS.read_text(encoding="utf-8")
    main_js = MAIN_JS.read_text(encoding="utf-8")
    assert "function validateScenarioForm" in scenario_js
    assert 'return "Pole puste — wpisz liczbę"' in scenario_js
    assert "function showScenarioValidationErrors" in scenario_js
    assert "validateScenarioForm()" in main_js
    assert "showScenarioValidationErrors(validation" in main_js


def test_load_and_step_require_valid_form():
    main_js = MAIN_JS.read_text(encoding="utf-8")
    load_block = main_js.split('if (btn.id === "btn-load")', 1)[1].split("if (btn.id ===", 1)[0]
    step_block = main_js.split('if (btn.id === "btn-step")', 1)[1].split("if (btn.id ===", 1)[0]
    assert "validateScenarioForm()" in load_block
    assert "validateScenarioForm()" in step_block
    assert "!validation.ok" in load_block
    assert "!validation.ok" in step_block


def test_export_requires_valid_form():
    main_js = MAIN_JS.read_text(encoding="utf-8")
    export_block = main_js.split('btn-export").onclick', 1)[1].split("document.getElementById", 1)[
        0
    ]
    assert "validateScenarioForm()" in export_block
    assert 'actionLabel: "Pobierz"' in export_block


def test_fan_venting_co2_threshold_suffix_is_ratio_not_ppm():
    form_js = FORM_JS.read_text(encoding="utf-8")
    suffix_fn = _extract_js_function(form_js, "fieldUnitSuffix")
    assert 'fan_venting_co2_threshold: "0–1"' in suffix_fn


def test_safety_alarm_temperature_logical_rule():
    scenario_js = SCENARIO_JS.read_text(encoding="utf-8")
    logical_fn = _extract_js_function(scenario_js, "validateScenarioLogicalRules")
    assert "tAlarm > tMax" in logical_fn
    assert "targets.air_temperature_c" in logical_fn
    assert "maximum_pulse_s" in logical_fn
    assert "co2_doser_maximum_pulse_s" in logical_fn
    assert "binary_threshold" in logical_fn


def test_schema_bounds_validation_exists():
    scenario_js = SCENARIO_JS.read_text(encoding="utf-8")
    assert "function validateScenarioAgainstSchema" in scenario_js
    schema_fn = _extract_js_function(scenario_js, "validateScenarioAgainstSchema")
    assert "panelSchema.sections" in schema_fn
    assert "field.minimum" in schema_fn
    assert "field.maximum" in schema_fn
    form_fn = _extract_js_function(scenario_js, "validateScenarioForm")
    assert "validateScenarioAgainstSchema" in form_fn
    assert "validateScenarioLogicalRules" in form_fn


def test_invalid_fields_get_visual_markers():
    panel_css = PANEL_CSS.read_text(encoding="utf-8")
    scenario_js = SCENARIO_JS.read_text(encoding="utf-8")
    assert ".field-control.field-invalid" in panel_css
    assert "field-invalid" in scenario_js
    assert "aria-invalid" in scenario_js


def test_logical_validation_errors_attach_field_elements():
    scenario_js = SCENARIO_JS.read_text(encoding="utf-8")
    logical_fn = _extract_js_function(scenario_js, "validateScenarioLogicalRules")
    assert "pushScenarioValidationError" in logical_fn
    assert "scenarioFieldElement" in scenario_js


def test_validation_highlights_fields_without_modal():
    scenario_js = SCENARIO_JS.read_text(encoding="utf-8")
    main_js = MAIN_JS.read_text(encoding="utf-8")
    show_fn = _extract_js_function(scenario_js, "showScenarioValidationErrors")
    assert "actionLabel" in show_fn
    assert "openNotice" not in show_fn
    assert "field-invalid" in show_fn or "syncScenarioFieldValidityMarks" in show_fn
    assert "scrollIntoView" in show_fn
    assert 'actionLabel: "Wyślij"' in main_js
    assert 'actionLabel: "Krok"' in main_js
    assert 'actionLabel: "Pobierz"' in main_js


def test_schema_validation_skips_boolean_checkbox_paths():
    scenario_js = SCENARIO_JS.read_text(encoding="utf-8")
    schema_fn = _extract_js_function(scenario_js, "validateScenarioAgainstSchema")
    assert "isScenarioBooleanPath" in schema_fn
    assert 'typeof value === "boolean"' in schema_fn
    assert 'field.type === "boolean"' in schema_fn or "field.type === 'boolean'" in schema_fn


def test_ratio_field_suffixes_use_zero_one_not_min():
    form_js = FORM_JS.read_text(encoding="utf-8")
    suffix_fn = _extract_js_function(form_js, "fieldUnitSuffix")
    assert 'alarm_minimum_fan: "0–1"' in suffix_fn
    assert 'fan_minimum_command: "0–1"' in suffix_fn
    assert 'fan_minimum_command: "min"' not in suffix_fn


def test_parse_number_input_accepts_comma_decimal():
    form_js = FORM_JS.read_text(encoding="utf-8")
    parse_fn = _extract_js_function(form_js, "parseScenarioNumberInput")
    assert 'raw.replace(",", ".")' in parse_fn


def test_seed_clears_invalid_state_on_input():
    main_js = MAIN_JS.read_text(encoding="utf-8")
    assert "clearScenarioFieldInvalid" in main_js
    on_seed = main_js.split("const onSeedChange", 1)[1].split("};", 1)[0]
    assert "clearScenarioFieldInvalid(event.target)" in on_seed


def test_number_inputs_emit_min_max_from_schema():
    form_js = FORM_JS.read_text(encoding="utf-8")
    wrap_fn = _extract_js_function(form_js, "renderWrappedNumberInput")
    assert "Number.isFinite(min)" in wrap_fn
    assert "Number.isFinite(max)" in wrap_fn
    assert "minAttr" in wrap_fn
    assert "maxAttr" in wrap_fn
