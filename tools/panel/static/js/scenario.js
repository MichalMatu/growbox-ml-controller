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

function scenarioSyncPayload(doc) {
  return scenarioPayloadForKeys(doc, SCENARIO_SYNC_KEYS);
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

function scenarioSyncFingerprint(doc) {
  return stableStringify(scenarioSyncPayload(doc));
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
    if (!zone.irrigation || typeof zone.irrigation !== "object") zone.irrigation = {};
    zone.irrigation.available = false;
  }
  return doc;
}

function readScenarioFromForm(base = scenario) {
  const next = sanitizeScenarioNumeric(cloneScenarioDoc(base));
  const seedEl = document.getElementById("seed");
  if (seedEl) next.seed = normalizeSeed(seedEl.value);
  forEachScenarioField(el => {
    const path = el.dataset.path;
    if (!path) return;
    if (el.classList?.contains("control-type-toggle")) {
      setNested(next, path, normalizeControlType(el.dataset.value));
      return;
    }
    let value;
    if (el.type === "checkbox") value = el.checked;
    else if (el.tagName === "SELECT") {
      value = el.dataset.bool !== undefined ? el.value === "true" : el.value;
    } else value = normalizeFieldNumber(Number(el.value), path);
    setNested(next, path, value);
  });
  return applyInactiveZonePolicy(next);
}

function setDeviceScenarioBaseline(doc) {
  const source = doc ?? readScenarioFromForm(scenario);
  deviceScenarioBaseline = scenarioSyncFingerprint(source);
}

function clearDeviceScenarioBaseline() {
  deviceScenarioBaseline = null;
}

function scenarioFormRoots() {
  return [
    document.getElementById("form-sections"),
    document.getElementById("setup-modal-body"),
    document.getElementById("previous-section"),
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
  const synced = scenarioSyncFingerprint(readScenarioFromForm(scenario)) === deviceScenarioBaseline;
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

function collectScenario() {
  scenario = readScenarioFromForm(scenario);
  syncInactiveZoneDependentInputs();
  saveScenarioDraft();
  updateScenarioSyncBadge();
  if (lastDecision) renderOutputs(lastDecision, { force: true });
  return scenario;
}
