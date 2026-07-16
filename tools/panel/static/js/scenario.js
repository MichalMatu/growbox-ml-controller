function scenarioStorageKey(schemaHash) {
  return `growbox-panel-scenario:${schemaHash}`;
}

function deepMergeScenario(base, overlay) {
  if (Array.isArray(base) && Array.isArray(overlay)) {
    const length = Math.max(base.length, overlay.length);
    const merged = [];
    for (let index = 0; index < length; index += 1) {
      const left = base[index];
      const right = overlay[index];
      if (left !== undefined && right !== undefined
          && left !== null && right !== null
          && typeof left === "object" && typeof right === "object"
          && !Array.isArray(left) && !Array.isArray(right)) {
        merged[index] = deepMergeScenario(left, right);
      } else if (right !== undefined) {
        merged[index] = right;
      } else {
        merged[index] = left;
      }
    }
    return merged;
  }
  const merged = Array.isArray(base) ? [...base] : { ...base };
  for (const [key, value] of Object.entries(overlay || {})) {
    if (Array.isArray(value) && Array.isArray(merged[key])) {
      merged[key] = deepMergeScenario(merged[key], value);
    } else if (value !== null && typeof value === "object" && !Array.isArray(value)
        && merged[key] !== null && typeof merged[key] === "object" && !Array.isArray(merged[key])) {
      merged[key] = deepMergeScenario(merged[key], value);
    } else if (value !== undefined) {
      merged[key] = value;
    }
  }
  return merged;
}

function saveScenarioDraft() {
  if (!panelSchema) return;
  try {
    localStorage.setItem(
      scenarioStorageKey(panelSchema.schema_hash),
      JSON.stringify({ v: SCENARIO_DRAFT_VERSION, scenario }),
    );
  } catch (_) { /* private mode / quota */ }
}

function loadScenarioDraft(schema) {
  try {
    const raw = localStorage.getItem(scenarioStorageKey(schema.schema_hash));
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed || parsed.v !== SCENARIO_DRAFT_VERSION || typeof parsed.scenario !== "object") {
      return null;
    }
    return sanitizeScenarioNumeric(deepMergeScenario(schema.default_scenario, parsed.scenario));
  } catch (_) {
    return null;
  }
}

function clearScenarioDraft() {
  if (!panelSchema) return;
  try {
    localStorage.removeItem(scenarioStorageKey(panelSchema.schema_hash));
  } catch (_) { /* ignore */ }
}
function patchLocalTransportStatus(cmd) {
  if (!lastState) lastState = {};
  if (!lastState.last_status || typeof lastState.last_status !== "object") {
    lastState.last_status = {};
  }
  const status = lastState.last_status;
  if (cmd.command === "pause") status.paused = true;
  else if (cmd.command === "resume") status.paused = false;
  else if (cmd.command === "reset") {
    status.step = 0;
    status.paused = true;
  } else if (cmd.command === "load_scenario") {
    status.step = 0;
    status.paused = true;
  } else if (cmd.command === "mode") {
    status.mode = cmd.value;
    if (cmd.value === "replay") status.paused = true;
  }
}

function patchLocalScenarioStatus(scenarioDoc) {
  if (!lastState) lastState = {};
  if (!lastState.last_status || typeof lastState.last_status !== "object") {
    lastState.last_status = {};
  }
  const status = lastState.last_status;
  const snap = {};
  for (const key of SCENARIO_SYNC_KEYS) {
    if (scenarioDoc?.[key] !== undefined) snap[key] = cloneScenarioDoc(scenarioDoc[key]);
  }
  if (Object.keys(snap).length > 0) status.scenario = snap;
  if (scenarioDoc?.seed !== undefined) status.seed = scenarioDoc.seed;
}

function updatePlayPauseBtn(paused, connected) {
  const btn = toolbarBtn("playpause");
  if (!btn) return;
  const icon = btn.querySelector(".playpause-icon");
  if (paused) {
    if (icon) icon.textContent = "▶";
    btn.dataset.cmd = '{"command":"resume"}';
    btn.setAttribute("aria-label", "Start");
    setBtnHint("playpause", connected ? "Start — wznów sterowanie" : "Najpierw Połącz urządzenie");
  } else {
    if (icon) icon.textContent = "■";
    btn.dataset.cmd = '{"command":"pause"}';
    btn.setAttribute("aria-label", "Stop");
    setBtnHint("playpause", connected ? "Stop — zatrzymaj sterowanie" : "Najpierw Połącz urządzenie");
  }
}

function scenarioPayloadForKeys(doc, keys) {
  const payload = { seed: doc?.seed ?? 101 };
  for (const key of keys) {
    if (doc?.[key] !== undefined) payload[key] = doc[key];
  }
  return sanitizeScenarioNumeric(payload);
}

function scenarioBadgePayload(doc) {
  const payload = scenarioPayloadForKeys(doc, SCENARIO_BADGE_KEYS);
  if (Array.isArray(payload.zones)) {
    payload.zones = payload.zones.map((zone) => {
      if (!zone || typeof zone !== "object" || Array.isArray(zone)) return zone;
      const { previous, ...rest } = zone;
      return rest;
    });
  }
  return payload;
}

function stableStringify(value) {
  if (Array.isArray(value)) {
    return `[${value.map(stableStringify).join(",")}]`;
  }
  if (value && typeof value === "object") {
    const keys = Object.keys(value).sort();
    return `{${keys.map(key => `${JSON.stringify(key)}:${stableStringify(value[key])}`).join(",")}}`;
  }
  return JSON.stringify(value);
}

function scenarioBadgeFingerprint(doc) {
  return stableStringify(scenarioBadgePayload(doc));
}

function cloneScenarioDoc(doc) {
  return JSON.parse(JSON.stringify(doc));
}

function zoneTargetFieldName(zoneIndex) {
  return `zone_${zoneIndex + 1}_target_soil_moisture_pct`;
}

const INACTIVE_ZONE_DEPENDENT_HINT =
  "Donica wyłączona w Czujnikach — ustawienie ignorowane przez model i safety";

function applyInactiveZonePolicy(doc) {
  if (!doc?.zones || !Array.isArray(doc.zones)) return doc;
  for (let index = 0; index < doc.zones.length; index += 1) {
    const zone = doc.zones[index];
    if (!zone || zone.available) continue;
    const targetField = fieldByName(zoneTargetFieldName(index));
    const fallback = targetField?.default ?? 50;
    if (!zone.targets || typeof zone.targets !== "object") zone.targets = {};
    zone.targets.soil_moisture_pct = fallback;
    const tempField = fieldByName(`zone_${index + 1}_target_soil_temperature_c`);
    zone.targets.soil_temperature_c = tempField?.default ?? 20;
    if (!zone.irrigation || typeof zone.irrigation !== "object") zone.irrigation = {};
    zone.irrigation.available = false;
    if (!zone.heat_mat || typeof zone.heat_mat !== "object") zone.heat_mat = {};
    zone.heat_mat.available = false;
  }
  return doc;
}

function scenarioFieldElement(path) {
  if (!path) return null;
  if (path === "seed") return document.getElementById("seed");
  for (const root of scenarioFormRoots()) {
    const el = root.querySelector(`[data-path="${path}"]`);
    if (el) return el;
  }
  return document.querySelector(`[data-path="${path}"]`);
}

function isScenarioNumberInputEligible(el) {
  return Boolean(
    el
    && el.type === "number"
    && (el.dataset.path || el.id === "seed")
    && !el.disabled
    && !el.readOnly,
  );
}

function clearScenarioFieldInvalid(el) {
  if (!isScenarioNumberInputEligible(el)) return;
  if (!validateScenarioNumberInput(el)) {
    applyFieldInvalidState(el, null);
  }
}

function pushScenarioValidationError(errors, path, message, el = null) {
  errors.push({
    path: path || "",
    label: path ? scenarioFieldLabel(path) : "Formularz",
    message,
    el: el ?? (path ? scenarioFieldElement(path) : null),
  });
}

function validateScenarioNumberInput(el) {
  if (!el || el.type !== "number") return null;
  const raw = String(el.value).trim();
  if (raw === "") return "Pole puste — wpisz liczbę";
  if (isIncompleteNumberInput(raw)) return "Niepełna liczba — dokończ wpisywanie";
  const num = Number(raw.replace(",", "."));
  if (!Number.isFinite(num)) return "Nieprawidłowa liczba";
  const min = el.min !== "" && el.min != null ? Number(el.min) : NaN;
  const max = el.max !== "" && el.max != null ? Number(el.max) : NaN;
  if (Number.isFinite(min) && num < min) return `Poniżej minimum (${min})`;
  if (Number.isFinite(max) && num > max) return `Powyżej maksimum (${max})`;
  return null;
}

/** Paths stored as checkbox booleans even when the contract encodes them as 0/1. */
function isScenarioBooleanPath(path) {
  if (!path) return false;
  return (
    path.endsWith(".available")
    || path.startsWith("validity.")
    || path.includes(".validity.")
    || path.endsWith(".lights_active")
    || path === "pseudo.lights_active"
  );
}

/** Cross-check document values against /api/schema field bounds (FE↔BE contract). */
function validateScenarioAgainstSchema(doc) {
  const errors = [];
  if (!panelSchema?.sections || !doc || typeof doc !== "object") return errors;
  for (const section of panelSchema.sections) {
    for (const field of section.fields || []) {
      if (!field.path) continue;
      // Booleans / checkbox flags are not continuous numbers.
      if (field.type === "boolean" || field.type === "enum" || isScenarioBooleanPath(field.path)) {
        continue;
      }
      if (field.type !== "number") continue;
      const value = getNested(doc, field.path);
      if (value === undefined || value === null || value === "") continue;
      // Defensive: checkbox-backed values may still be boolean in the draft.
      if (typeof value === "boolean") continue;
      if (typeof value !== "number" || !Number.isFinite(value)) {
        pushScenarioValidationError(errors, field.path, "Nieprawidłowa liczba");
        continue;
      }
      const min = Number(field.minimum);
      const max = Number(field.maximum);
      if (Number.isFinite(min) && value < min) {
        pushScenarioValidationError(errors, field.path, `Poniżej minimum (${min})`);
      } else if (Number.isFinite(max) && value > max) {
        pushScenarioValidationError(errors, field.path, `Powyżej maksimum (${max})`);
      }
    }
  }
  return errors;
}

function validateScenarioLogicalRules(doc) {
  const errors = [];
  const safety = doc?.safety;
  if (safety && typeof safety === "object") {
    const tMax = safety.maximum_air_temperature_c;
    const tAlarm = safety.alarm_air_temperature_c;
    if (Number.isFinite(tMax) && Number.isFinite(tAlarm) && tAlarm > tMax) {
      pushScenarioValidationError(
        errors,
        "safety.alarm_air_temperature_c",
        "Alarm T nie może być wyższy niż T max (grzałka)",
      );
    }
    const fanMin = safety.alarm_minimum_fan;
    if (Number.isFinite(fanMin) && (fanMin < 0 || fanMin > 1)) {
      pushScenarioValidationError(
        errors,
        "safety.alarm_minimum_fan",
        "Fan min musi być w zakresie 0–1",
      );
    }
    const binary = safety.binary_threshold;
    if (Number.isFinite(binary) && (binary < 0 || binary > 1)) {
      pushScenarioValidationError(
        errors,
        "safety.binary_threshold",
        "Próg bin musi być w zakresie 0–1",
      );
    }
    const vent = safety.fan_venting_co2_threshold;
    if (Number.isFinite(vent) && (vent < 0 || vent > 1)) {
      pushScenarioValidationError(
        errors,
        "safety.fan_venting_co2_threshold",
        "Fan CO₂ musi być w zakresie 0–1",
      );
    }
  }

  const targetAir = doc?.targets?.air_temperature_c;
  const safetyMax = safety?.maximum_air_temperature_c;
  if (Number.isFinite(targetAir) && Number.isFinite(safetyMax) && targetAir > safetyMax) {
    pushScenarioValidationError(
      errors,
      "targets.air_temperature_c",
      "Cel T powietrza nie może być wyższy niż T max safety",
    );
  }

  const fanMinCmd = doc?.actuators?.fan?.minimum_command;
  if (Number.isFinite(fanMinCmd) && (fanMinCmd < 0 || fanMinCmd > 1)) {
    pushScenarioValidationError(
      errors,
      "actuators.fan.minimum_command",
      "Fan min (PWM) musi być w zakresie 0–1",
    );
  }

  const co2SafetyPulse = safety?.co2_doser_maximum_pulse_s;
  const co2ActuatorPulse = doc?.actuators?.co2_doser?.maximum_pulse_s;
  if (
    doc?.actuators?.co2_doser?.available
    && Number.isFinite(co2SafetyPulse)
    && Number.isFinite(co2ActuatorPulse)
    && co2SafetyPulse > co2ActuatorPulse
  ) {
    pushScenarioValidationError(
      errors,
      "safety.co2_doser_maximum_pulse_s",
      "Impuls safety CO₂ nie może być dłuższy niż impuls aktuatora",
    );
  }

  const zones = Array.isArray(doc?.zones) ? doc.zones : [];
  for (let index = 0; index < zones.length; index += 1) {
    const zone = zones[index];
    if (!zone?.available || !zone.irrigation?.available) continue;
    const pulse = zone.irrigation.maximum_pulse_s;
    const interval = zone.irrigation.minimum_interval_s;
    if (Number.isFinite(pulse) && Number.isFinite(interval) && pulse > interval) {
      const path = `zones.${index}.irrigation.maximum_pulse_s`;
      pushScenarioValidationError(
        errors,
        path,
        "Impuls podlewania nie może być dłuższy niż przerwa min.",
      );
    }
  }

  return errors;
}

function validateScenarioForm() {
  const errors = [];
  let editableCount = 0;
  const seedEl = document.getElementById("seed");
  if (seedEl && !seedEl.disabled && !seedEl.readOnly) {
    editableCount += 1;
    const seedErr = validateScenarioNumberInput(seedEl);
    if (seedErr) {
      errors.push({ path: "seed", label: "Seed", message: seedErr, el: seedEl });
    }
  }
  forEachScenarioField(el => {
    if (!isScenarioNumberInputEligible(el)) return;
    editableCount += 1;
    const message = validateScenarioNumberInput(el);
    if (message) {
      errors.push({
        path: el.dataset.path,
        label: scenarioFieldLabel(el.dataset.path),
        message,
        el,
      });
    }
  });
  if (editableCount === 0) {
    return {
      ok: false,
      errors: [{ path: "", label: "Formularz", message: "Brak pól do wysłania", el: null }],
    };
  }
  if (errors.length === 0) {
    const draft = readScenarioFromForm(scenario, { formatNumbers: false });
    errors.push(...validateScenarioAgainstSchema(draft));
    if (errors.length === 0) {
      errors.push(...validateScenarioLogicalRules(draft));
    }
  }
  return { ok: errors.length === 0, errors };
}

function applyFieldInvalidState(el, message) {
  if (!el) return;
  const invalid = Boolean(message);
  el.classList.toggle("field-invalid", invalid);
  el.setAttribute("aria-invalid", invalid ? "true" : "false");
  if (invalid) {
    el.title = message;
    el.setAttribute("data-validation-error", message);
  } else {
    el.removeAttribute("data-validation-error");
  }
}

function syncScenarioFieldValidityMarks(validation = null) {
  const errorByPath = new Map();
  for (const item of validation?.errors || []) {
    if (item.path) errorByPath.set(item.path, item.message);
  }
  const seedEl = document.getElementById("seed");
  if (seedEl) {
    const seedErr = errorByPath.get("seed") || (isScenarioNumberInputEligible(seedEl)
      ? validateScenarioNumberInput(seedEl)
      : null);
    applyFieldInvalidState(seedEl, seedErr);
  }
  forEachScenarioField(el => {
    if (!isScenarioNumberInputEligible(el)) {
      // Logical/schema errors may still target non-number controls; clear only if no map hit.
      const pathErr = el.dataset.path ? errorByPath.get(el.dataset.path) : null;
      if (pathErr) {
        applyFieldInvalidState(el, pathErr);
      } else {
        el.classList.remove("field-invalid");
        el.removeAttribute("aria-invalid");
        el.removeAttribute("data-validation-error");
      }
      return;
    }
    const err = errorByPath.get(el.dataset.path) || validateScenarioNumberInput(el);
    applyFieldInvalidState(el, err);
  });
  // Mark elements referenced by errors that are outside the number-input loop (e.g. focus targets).
  for (const item of validation?.errors || []) {
    if (item.el && item.message) applyFieldInvalidState(item.el, item.message);
  }
}

/** Highlight invalid fields in-place — no modal. Focus first error. */
function showScenarioValidationErrors(validation, { actionLabel = "wysłania" } = {}) {
  syncScenarioFieldValidityMarks(validation);
  for (const item of validation.errors || []) {
    if (!item.el) continue;
    const detail = item.message || "Nieprawidłowa wartość";
    item.el.title = `Popraw przed ${actionLabel}: ${detail}`;
    item.el.setAttribute("data-validation-error", detail);
  }
  const focusTarget = validation.errors.find(item => item.el)?.el;
  if (focusTarget) {
    focusTarget.scrollIntoView({ block: "center", behavior: "smooth" });
    focusTarget.focus({ preventScroll: true });
  }
}

function readScenarioFromForm(base = scenario, { formatNumbers = true } = {}) {
  const next = sanitizeScenarioNumeric(cloneScenarioDoc(base));
  const seedEl = document.getElementById("seed");
  if (seedEl) next.seed = normalizeSeed(seedEl.value);
  forEachScenarioField(el => {
    const path = el.dataset.path;
    if (!path) return;
    let value;
    if (el.type === "checkbox") value = el.checked;
    else if (el.tagName === "SELECT") {
      value = el.dataset.bool !== undefined ? el.value === "true" : el.value;
    } else {
      const parsed = parseScenarioNumberInput(el);
      if (parsed === null) return;
      value = parsed;
      if (formatNumbers) formatScenarioNumberInput(el);
    }
    setNested(next, path, value);
  });
  return applyInactiveZonePolicy(next);
}

function setDeviceScenarioBaseline(doc) {
  const source = doc ?? readScenarioFromForm(scenario);
  deviceScenarioBaseline = scenarioBadgeFingerprint(source);
}

function clearDeviceScenarioBaseline() {
  deviceScenarioBaseline = null;
}

function scenarioFormRoots() {
  return [
    document.getElementById("form-sections"),
    document.getElementById("panel-modal-body"),
  ].filter(Boolean);
}

function forEachScenarioField(callback) {
  const seen = new Set();
  for (const root of scenarioFormRoots()) {
    root.querySelectorAll("[data-path]").forEach(el => {
      const path = el.dataset.path;
      if (!path || seen.has(path)) return;
      seen.add(path);
      callback(el);
    });
  }
}

function updateScenarioSyncBadge() {
  const el = document.getElementById("scenario-sync-badge");
  if (!el) return;
  if (!lastState?.connected || deviceScenarioBaseline === null) {
    el.hidden = true;
    return;
  }
  const synced = scenarioBadgeFingerprint(readScenarioFromForm(scenario)) === deviceScenarioBaseline;
  el.hidden = false;
  if (synced) {
    el.className = "sync-badge synced";
    el.textContent = "OK";
    el.title = "Formularz zgodny z ostatnim Połącz / Wyślij";
  } else {
    el.className = "sync-badge local";
    el.textContent = "wyślij zmiany";
    el.title = "Formularz zmieniony — kliknij Wyślij";
  }
}
function normalizeSeed(value) {
  const parsed = Math.round(Number(value) || 101);
  return Math.min(4294967295, Math.max(0, parsed));
}

function collectScenario(opts = {}) {
  scenario = readScenarioFromForm(scenario, opts);
  syncInactiveZoneDependentInputs();
  saveScenarioDraft();
  updateScenarioSyncBadge();
  if (lastDecision) renderOutputs(lastDecision, { force: true });
  return scenario;
}
