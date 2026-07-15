function shortLabel(name) {
  if (LABEL_MAP[name]) return LABEL_MAP[name];
  if (typeof OUTPUT_LABELS !== "undefined" && OUTPUT_LABELS[name]) return OUTPUT_LABELS[name];
  const zoneTarget = name.match(/^zone_(\d+)_target_soil_moisture_pct$/);
  if (zoneTarget) return `Donica ${zoneTarget[1]}`;
  const zoneAvail = name.match(/^zone_(\d+)_available$/);
  if (zoneAvail) return `Donica ${zoneAvail[1]}`;
  const zonePrev = name.match(/^zone_(\d+)_previous_irrigation$/);
  if (zonePrev) return `Pompa ${zonePrev[1]}`;
  const zoneIrr = name.match(/^zone_\d+_irrigation_(.+)$/);
  if (zoneIrr) {
    const baseKey = `irrigation_${zoneIrr[1]}`;
    if (LABEL_MAP[baseKey]) return LABEL_MAP[baseKey];
  }
  const zoneCult = name.match(/^zone_\d+_(pot_volume_l|substrate_water_capacity_ml|transpiration_factor)$/);
  if (zoneCult && LABEL_MAP[zoneCult[1]]) return LABEL_MAP[zoneCult[1]];
  return name.replace(/_/g, " ");
}

function syncPreviousFormInputs() {
  document.querySelectorAll("#previous-section [data-path]").forEach((el) => {
    const path = el.dataset.path;
    if (!path) return;
    const value = getNested(scenario, path);
    if (el.type === "checkbox") {
      el.checked = Boolean(value);
      return;
    }
    if (el.tagName === "SELECT") {
      el.value = value ?? "";
      return;
    }
    el.value = formatFieldNumber(value ?? 0, path);
  });
}

function formatEnumOptionLabel(value) {
  if (value === "binary") return "bin";
  if (value === "pwm") return "pwm";
  return value;
}

const FIELD_CONTROL_CLASS = "field-control";

function fieldHint(name) {
  if (FIELD_HINTS[name]) return FIELD_HINTS[name];
  if (/^zone_\d+_target_soil_moisture_pct$/.test(name)) {
    return FIELD_HINTS.target_soil_moisture_pct || "";
  }
  if (/^soil_moisture_zone_\d+_pct$/.test(name)) {
    return FIELD_HINTS.soil_moisture_pct || "";
  }
  if (/^soil_temperature_zone_\d+_c$/.test(name)) {
    return FIELD_HINTS.soil_temperature_c || "";
  }
  if (/^zone_\d+_previous_irrigation$/.test(name)) {
    return FIELD_HINTS.previous_irrigation || "";
  }
  const zoneIrr = name.match(/^zone_\d+_irrigation_(.+)$/);
  if (zoneIrr) {
    const baseKey = `irrigation_${zoneIrr[1]}`;
    if (FIELD_HINTS[baseKey]) return FIELD_HINTS[baseKey];
  }
  const zoneCult = name.match(/^zone_\d+_(pot_volume_l|substrate_water_capacity_ml|transpiration_factor)$/);
  if (zoneCult && FIELD_HINTS[zoneCult[1]]) return FIELD_HINTS[zoneCult[1]];
  return "";
}

function fieldHintAttr(name) {
  const hint = fieldHint(name);
  return hint ? ` title="${hint}"` : "";
}

function fieldControlClassAttr() {
  return ` class="${FIELD_CONTROL_CLASS}"`;
}

function fieldByName(name, sectionId = null) {
  for (const section of panelSchema.sections) {
    if (sectionId && section.id !== sectionId) continue;
    const hit = section.fields.find(f => f.name === name);
    if (hit) return hit;
  }
  return null;
}

function sectionById(id) {
  return panelSchema.sections.find(section => section.id === id) || null;
}

function fieldUnitSuffix(field) {
  const suffixByName = {
    heater_max_power_w: "W",
    heater_efficiency: "η",
    fan_max_airflow_m3_h: "m³/h",
    fan_minimum_command: "min",
    humidifier_max_output_g_h: "g/h",
    dehumidifier_max_removal_g_h: "g/h",
    cooler_max_cooling_w: "W",
    co2_doser_dose_ppm_per_full_pulse: "ppm",
    co2_doser_maximum_pulse_s: "s",
    growbox_volume_m3: "m³",
    thermal_mass_j_per_k: "J/K",
    heat_loss_w_per_k: "W/K",
    air_leak_rate_ach: "1/h",
    pot_volume_l: "L",
    substrate_water_capacity_ml: "mL",
    transpiration_factor: "×",
    irrigation_flow_ml_s: "mL/s",
    irrigation_maximum_pulse_s: "s",
    irrigation_minimum_interval_s: "s",
    binary_threshold: "0–1",
    alarm_minimum_fan: "min",
    fan_venting_co2_threshold: "ppm",
  };
  if (suffixByName[field.name]) return suffixByName[field.name];
  const zoneIrr = field.name.match(/^zone_\d+_irrigation_(flow_ml_s|maximum_pulse_s|minimum_interval_s)$/);
  if (zoneIrr) {
    if (zoneIrr[1] === "flow_ml_s") return "mL/s";
    return "s";
  }
  const zoneCult = field.name.match(/^zone_\d+_(pot_volume_l|substrate_water_capacity_ml|transpiration_factor)$/);
  if (zoneCult) {
    if (zoneCult[1] === "pot_volume_l") return "L";
    if (zoneCult[1] === "substrate_water_capacity_ml") return "mL";
    return "×";
  }
  const name = field.name;
  const path = field.path || "";
  if (name.endsWith("_temperature_c") || path.includes("temperature_c")) return "°C";
  if (name.endsWith("_pct") || path.includes("_pct")) return "%";
  if (name.includes("co2") && (name.includes("ppm") || path.includes("co2"))) return "ppm";
  if (name.endsWith("_s") || path.endsWith("_s")) return "s";
  if (name.startsWith("previous_") || name.includes("previous_irrigation")) return "0–1";
  return "";
}

function fieldSuffixSizeClass(suffix) {
  if (!suffix) return "";
  if (suffix.length >= 7) return " suffix-long";
  if (suffix.length >= 3) return " suffix-med";
  return " suffix-short";
}

function renderWrappedNumberInput(field, opts = {}) {
  const id = opts.id || `f-${field.path.replaceAll(".", "_")}`;
  const hintAttr = opts.hintAttr ?? fieldHintAttr(field.name);
  const ariaLabel = opts.ariaLabel ?? escapeHtml(shortLabel(field.name));
  const displayValue = opts.displayValue
    ?? formatFieldNumber(getNested(scenario, field.path) ?? field.default, field.path);
  const suffix = fieldUnitSuffix(field);
  const suffixClass = fieldSuffixSizeClass(suffix);
  const wrapClass = opts.wrapClass || "field-input-wrap";
  const suffixClassName = opts.suffixClass || "field-input-suffix";
  const suffixMarkup = suffix
    ? `<span class="${suffixClassName}" aria-hidden="true">${escapeHtml(suffix)}</span>`
    : "";
  return `<div class="${wrapClass}${suffixClass}">
    <input type="number"${fieldControlClassAttr()} data-path="${field.path}" id="${id}"${hintAttr}
      aria-label="${ariaLabel}" min="${field.minimum}" max="${field.maximum}" step="${fieldStep(field)}"
      value="${displayValue}" />
    ${suffixMarkup}
  </div>`;
}

function renderNumberField(field, extraClass = "field-num") {
  const id = `f-${field.path.replaceAll(".", "_")}`;
  const wide = field.path.includes("thermal_mass") || field.path.includes("substrate_water");
  const hintAttr = fieldHintAttr(field.name);
  return `<label class="${wide ? "field-wide" : extraClass}">
    <span class="lbl"${hintAttr}>${shortLabel(field.name)}</span>
    ${renderWrappedNumberInput(field, { id })}
  </label>`;
}

function renderBoolField(field) {
  const id = `f-${field.path.replaceAll(".", "_")}`;
  const value = getNested(scenario, field.path);
  if (isAvailabilityField(field.name)) {
    return `<label class="field-bool">
      <input type="checkbox" data-path="${field.path}" id="${id}" ${value ? "checked" : ""} />
    </label>`;
  }
  return `<label class="field-bool">
    <input type="checkbox" data-path="${field.path}" id="${id}" ${value ? "checked" : ""} />
    <span class="lbl">${shortLabel(field.name)}</span>
  </label>`;
}

function renderEnumField(field) {
  const id = `f-${field.path.replaceAll(".", "_")}`;
  const value = getNested(scenario, field.path);
  const opts = (field.options || []).map(o =>
    `<option value="${o.value}" ${value === o.value ? "selected" : ""}>${formatEnumOptionLabel(o.value)}</option>`
  ).join("");
  return `<label class="field-num">
    <span class="lbl">${shortLabel(field.name)}</span>
    <select${fieldControlClassAttr()} data-path="${field.path}" id="${id}">${opts}</select>
  </label>`;
}

function renderField(field) {
  if (field.type === "boolean") return renderBoolField(field);
  if (field.type === "enum") return renderEnumField(field);
  return renderNumberField(field);
}

function renderHelpBtn(topic) {
  const meta = HELP_TOPICS[topic];
  const label = meta ? meta.title : "Pomoc";
  return `<button type="button" class="help-btn" data-help="${topic}" aria-label="Pomoc — ${label}">?</button>`;
}

function renderSectionHead(title, helpTopic, tag = "h2") {
  return `<div class="card-head"><${tag}>${title}</${tag}>${renderHelpBtn(helpTopic)}</div>`;
}

function updateModalLock() {
  const locked = document.querySelector(".modal-backdrop.open") !== null;
  document.body.classList.toggle("modal-open", locked);
}

function openHelp(topic) {
  const meta = HELP_TOPICS[topic];
  if (!meta) return;
  const backdrop = document.getElementById("help-modal-backdrop");
  helpReturnFocus = document.activeElement;
  document.getElementById("help-modal-title").textContent = meta.title;
  document.getElementById("help-modal-content").innerHTML = meta.html;
  backdrop.classList.add("open");
  backdrop.removeAttribute("inert");
  backdrop.setAttribute("aria-hidden", "false");
  updateModalLock();
  document.getElementById("help-modal-close").focus();
}

function closeHelp() {
  const backdrop = document.getElementById("help-modal-backdrop");
  const returnTo = helpReturnFocus;
  helpReturnFocus = null;
  restoreFocusFromDialog(backdrop, returnTo, "#btn-connect");
  backdrop.classList.remove("open");
  backdrop.setAttribute("inert", "");
  backdrop.setAttribute("aria-hidden", "true");
  updateModalLock();
}

let setupReturnFocus = null;

const SETUP_TAB_LABELS = {
  growbox: "Parametry growboxa",
  safety: "Limity safety",
};

const SETUP_TAB_HELP = {
  growbox: "environment",
  safety: "safety",
};

function switchSetupTab(tabId) {
  const tab = SETUP_TAB_LABELS[tabId] ? tabId : "growbox";
  document.querySelectorAll("#setup-modal-tabs [data-setup-tab]").forEach((btn) => {
    const active = btn.dataset.setupTab === tab;
    btn.classList.toggle("active", active);
    btn.setAttribute("aria-selected", active ? "true" : "false");
  });
  document.querySelectorAll(".setup-pane").forEach((pane) => {
    const active = pane.id === `setup-pane-${tab}`;
    pane.classList.toggle("active", active);
    pane.hidden = !active;
  });
  document.getElementById("setup-modal-title").textContent = SETUP_TAB_LABELS[tab];
  const helpBtn = document.getElementById("setup-modal-help");
  if (helpBtn) {
    const topic = SETUP_TAB_HELP[tab];
    helpBtn.dataset.help = topic;
    helpBtn.setAttribute("aria-label", `Pomoc — ${SETUP_TAB_LABELS[tab]}`);
  }
}

function openSetup(tabId = "growbox") {
  const backdrop = document.getElementById("setup-modal-backdrop");
  if (!backdrop) return;
  if (!backdrop.classList.contains("open")) {
    setupReturnFocus = document.activeElement;
    backdrop.classList.add("open");
    backdrop.removeAttribute("inert");
    backdrop.setAttribute("aria-hidden", "false");
    updateModalLock();
  }
  const tab = SETUP_TAB_LABELS[tabId] ? tabId : "growbox";
  switchSetupTab(tab);
  document.getElementById(`setup-tab-${tab}`)?.focus();
}

function closeSetup() {
  const backdrop = document.getElementById("setup-modal-backdrop");
  if (!backdrop?.classList.contains("open")) return;
  const returnTo = setupReturnFocus;
  setupReturnFocus = null;
  restoreFocusFromDialog(backdrop, returnTo, "#btn-setup-growbox");
  backdrop.classList.remove("open");
  backdrop.setAttribute("inert", "");
  backdrop.setAttribute("aria-hidden", "true");
  updateModalLock();
}

function renderSetupPanes() {
  const growbox = document.getElementById("setup-pane-growbox");
  const safety = document.getElementById("setup-pane-safety");
  if (growbox) growbox.innerHTML = renderGrowboxPanel(true);
  if (safety) {
    const safetySection = sectionById("safety");
    safety.innerHTML = safetySection ? renderSafetyBlock(true) : "";
  }
}

function renderPathSensorMiniCell(sensorField, validityField, displayLabel) {
  if (!sensorField) return "";
  const sensorPath = sensorField.path;
  const sId = `f-${sensorPath.replaceAll(".", "_")}`;
  const sVal = getNested(scenario, sensorPath);
  const displayValue = formatFieldNumber(sVal ?? sensorField.default, sensorPath);
  const hintAttr = fieldHintAttr(sensorField.name);
  const validityControl = validityField
    ? (() => {
        const vId = `f-${validityField.path.replaceAll(".", "_")}`;
        const vVal = getNested(scenario, validityField.path);
        const vHint = validityField.path.startsWith("validity.")
          ? validityHint(validityField.path.slice("validity.".length))
          : "Odznaczony = odczyt nieważny (ML i safety ignorują)";
        return `<input type="checkbox" data-path="${validityField.path}" id="${vId}" title="${vHint}" ${vVal ? "checked" : ""} />`;
      })()
    : "";
  const wrappedSensor = {
    path: sensorPath,
    name: sensorField.name,
    minimum: sensorField.minimum,
    maximum: sensorField.maximum,
    default: sensorField.default,
  };
  return `<div class="mini-cell">
    <div class="head-row">
      <span class="name"${hintAttr}>${displayLabel || shortLabel(sensorField.name)}</span>
      ${validityControl}
    </div>
    ${renderWrappedNumberInput(wrappedSensor, { id: sId, displayValue })}
  </div>`;
}

function renderSensorMiniCell(sensorKey, validityKey) {
  const sensorField = sensorFieldMeta(sensorKey);
  if (!sensorField) return "";
  const sensorPath = `sensors.${sensorKey}`;
  const wrappedSensor = {
    path: sensorPath,
    name: sensorKey,
    minimum: sensorField.minimum,
    maximum: sensorField.maximum,
    default: sensorField.default,
  };
  const wrappedValidity = validityKey ? { path: `validity.${validityKey}`, name: validityKey } : null;
  return renderPathSensorMiniCell(wrappedSensor, wrappedValidity, shortLabel(sensorKey));
}

function renderZoneAvailableTick(featureName) {
  const field = fieldByName(featureName);
  if (!field) return "";
  const id = `f-${field.path.replaceAll(".", "_")}`;
  const value = getNested(scenario, field.path);
  return `<input type="checkbox" data-path="${field.path}" id="${id}" title="Odznaczone = donica wyłączona w profilu" ${value ? "checked" : ""} />`;
}

function renderPotCard(row) {
  const moisture = renderPathSensorMiniCell(
    fieldByName(row.moisture),
    fieldByName(row.moistureValid),
    "Wilg."
  );
  const temp = renderPathSensorMiniCell(
    fieldByName(row.temp),
    fieldByName(row.tempValid),
    "Gleba T"
  );
  return `<div class="pot-card">
    <div class="head-row">
      <span class="name">${row.title}</span>
      <span class="pot-card-avail" title="Donica w profilu">${renderZoneAvailableTick(row.zoneAvailable)}</span>
    </div>
    <div class="pot-card-sensors">${moisture}${temp}</div>
  </div>`;
}

function renderPotsSubCard() {
  const cards = POT_SENSOR_ROWS.map(renderPotCard).join("");
  return `<div class="sub-card pots-block"><div class="card-head"><h3>Donice</h3></div><div class="compact-row pots-row">${cards}</div></div>`;
}

function syncLightsActiveDisplay() {
  const checkbox = document.getElementById("f-pseudo_lights_active");
  const display = document.getElementById("f-pseudo_lights_active_display");
  if (!checkbox || !display) return;
  display.value = checkbox.checked ? "ON" : "OFF";
}

function renderLightsActiveCell() {
  const field = fieldByName("lights_active");
  if (!field) return "";
  const id = "f-pseudo_lights_active";
  const value = getNested(scenario, field.path);
  const hint = "Harmonogram / readback przekaźnika — wpływa na termikę symulatora (wejście ML, nie czujnik)";
  const displayValue = value ? "ON" : "OFF";
  return `<div class="mini-cell pseudo-lights-cell">
    <div class="head-row">
      <span class="name" title="${hint}">${shortLabel(field.name)}</span>
      <input type="checkbox" data-path="${field.path}" id="${id}" title="${hint}" ${value ? "checked" : ""} />
    </div>
    <input type="text" class="field-control pseudo-lights-display" id="f-pseudo_lights_active_display" disabled
      value="${displayValue}" aria-hidden="true" tabindex="-1"
      title="Podgląd stanu — edycja checkboxem" />
  </div>`;
}

function renderSensorSubCard(title, sensors, extraCells = "") {
  const cells = sensors.map(([sensorKey, validityKey]) =>
    renderSensorMiniCell(sensorKey, validityKey)
  ).join("");
  return `<div class="sub-card"><div class="card-head"><h3>${title}</h3></div><div class="compact-row">${cells}${extraCells}</div></div>`;
}

function renderSensorBlock() {
  const lights = renderLightsActiveCell();
  const left = renderSensorSubCard(SENSOR_GROUPS[0].title, SENSOR_GROUPS[0].sensors, lights);
  const right = renderSensorSubCard(SENSOR_GROUPS[1].title, SENSOR_GROUPS[1].sensors);
  const pots = renderPotsSubCard();
  return `<div class="card growbox-panel sensors-panel">${renderSectionHead("Czujniki", "sensors")}<div class="growbox-split">${left}${right}</div>${pots}</div>`;
}

function updateSeedInput() {
  const el = document.getElementById("seed");
  if (!el) return;
  el.value = String(normalizeSeed(scenario.seed ?? 101));
}

function isWideField(field) {
  return field.path.includes("thermal_mass") || field.path.includes("substrate_water")
    || field.path.includes("minimum_interval");
}

function fieldStep(field) {
  if (field.path.includes("pct") || field.path.includes("ratio")) return "0.1";
  if (field.path.includes("co2")) return "1";
  return "0.01";
}

function fieldStepForPath(path) {
  if (path.startsWith("safety.")) {
    if (path.endsWith("_s")) return "1";
    if (path.includes("threshold") || path.includes("minimum_fan")) return "0.01";
    return "0.1";
  }
  if (path.startsWith("sensors.") || (path.includes("zones.") && path.includes(".sensors."))) {
    return path.includes("co2") ? "1" : "0.1";
  }
  if (path.includes("zones.") && path.includes(".targets.")) return "0.1";
  if (path.startsWith("previous.")) return "0.001";
  if (path.includes("pct") || path.includes("ratio") || path.includes("efficiency") || path.includes("minimum_command") || path.includes("transpiration")) {
    return "0.01";
  }
  if (path.includes("co2")) return "1";
  if (path.includes("thermal_mass") || path.includes("substrate_water") || path.includes("minimum_interval")) return "1";
  return "0.01";
}

function decimalPlacesFromStep(step) {
  const text = String(step);
  const dot = text.indexOf(".");
  return dot < 0 ? 0 : text.length - dot - 1;
}

function normalizeFieldNumber(value, path) {
  if (typeof value !== "number" || !Number.isFinite(value)) return value;
  if (path === "seed") return Math.round(value);
  const decimals = decimalPlacesFromStep(fieldStepForPath(path));
  const factor = 10 ** decimals;
  return Math.round(value * factor) / factor;
}

function formatFieldNumber(value, path) {
  const normalized = normalizeFieldNumber(value, path);
  if (typeof normalized !== "number" || !Number.isFinite(normalized)) {
    return normalized ?? "";
  }
  const decimals = decimalPlacesFromStep(fieldStepForPath(path));
  if (decimals === 0) return String(normalized);
  return normalized.toFixed(decimals).replace(/(\.\d*?)0+$/, "$1").replace(/\.$/, "");
}

function sanitizeScenarioNumeric(obj, pathPrefix = "") {
  if (obj === null || typeof obj !== "object" || Array.isArray(obj)) return obj;
  const out = {};
  for (const [key, value] of Object.entries(obj)) {
    const path = pathPrefix ? `${pathPrefix}.${key}` : key;
    if (typeof value === "number") {
      out[key] = normalizeFieldNumber(value, path);
    } else if (typeof value === "object" && value !== null) {
      out[key] = sanitizeScenarioNumeric(value, path);
    } else {
      out[key] = value;
    }
  }
  return out;
}

function renderMiniCellInput(field) {
  const id = `f-${field.path.replaceAll(".", "_")}`;
  const value = getNested(scenario, field.path);
  const hintAttr = fieldHintAttr(field.name);
  const label = `<div class="label-row"><span class="name"${hintAttr}>${shortLabel(field.name)}</span></div>`;

  if (field.type === "enum") {
    const opts = (field.options || []).map(o =>
      `<option value="${o.value}" ${value === o.value ? "selected" : ""}>${formatEnumOptionLabel(o.value)}</option>`
    ).join("");
    return `${label}<select${fieldControlClassAttr()} data-path="${field.path}" id="${id}"${hintAttr}>${opts}</select>`;
  }
  return `${label}${renderWrappedNumberInput(field, { id })}`;
}

function renderMiniCell(field) {
  const wide = isWideField(field) ? " wide" : "";

  if (field.type === "boolean") {
    const id = `f-${field.path.replaceAll(".", "_")}`;
    const value = getNested(scenario, field.path);
    if (isAvailabilityField(field.name)) {
      const hint = fieldHint(field.name);
      const hintAttr = hint ? ` title="${hint}"` : "";
      return `<div class="mini-cell bool-only${wide}">
        <div class="head-row tick-only">
          <input type="checkbox" data-path="${field.path}" id="${id}"${hintAttr} ${value ? "checked" : ""} />
        </div>
      </div>`;
    }
    const hintAttr = fieldHintAttr(field.name);
    return `<div class="mini-cell bool-only${wide}">
      <div class="head-row">
        <span class="name"${hintAttr}>${shortLabel(field.name)}</span>
        <input type="checkbox" data-path="${field.path}" id="${id}"${hintAttr} ${value ? "checked" : ""} />
      </div>
    </div>`;
  }
  return `<div class="mini-cell${wide}">${renderMiniCellInput(field)}</div>`;
}

function renderCompactBlock(title, fields, helpTopic) {
  const cells = fields.map(renderMiniCell).join("");
  return `<div class="card">${renderSectionHead(title, helpTopic)}<div class="compact-row">${cells}</div></div>`;
}

function renderFieldsSubCard(section, helpTopic) {
  const cells = section.fields.map(renderMiniCell).join("");
  const panelClass = section.id ? ` ${section.id}-panel` : "";
  return `<div class="card growbox-panel${panelClass}">${renderSectionHead(section.title, helpTopic)}<div class="sub-card"><div class="compact-row">${cells}</div></div></div>`;
}

function renderSubCard(title, fields, helpTopic) {
  const cells = fields.map(renderMiniCell).join("");
  const head = helpTopic
    ? renderSectionHead(title, helpTopic, "h3")
    : `<div class="card-head"><h3>${title}</h3></div>`;
  return `<div class="sub-card">${head}<div class="compact-row">${cells}</div></div>`;
}

function renderGrowboxCultivationSubCard(section) {
  const zones = [[], [], [], []];
  for (const field of section.fields) {
    const match = field.path.match(/^zones\.(\d+)\.cultivation\./);
    if (match) zones[Number(match[1])].push(field);
  }
  const cards = zones.map((fields, index) => renderZoneCultivationCard(fields, index)).join("");
  if (!cards) return "";
  return `<div class="sub-card pots-block"><div class="card-head"><h3>Donice</h3></div><div class="compact-row pots-row">${cards}</div></div>`;
}

function renderGrowboxPanel(inSetup = false) {
  const env = panelSchema.sections.find(s => s.id === "environment");
  const zonesSection = sectionById("zones");
  if (!env && !zonesSection) return "";
  const obudowa = env ? renderSubCard("Obudowa", env.fields, inSetup ? null : "environment") : "";
  const donice = zonesSection ? renderGrowboxCultivationSubCard(zonesSection) : "";
  if (inSetup) {
    return `<div class="setup-growbox-body">${obudowa}${donice}</div>`;
  }
  return `<div class="card growbox-panel environment-panel">${renderSectionHead("Parametry growboxa", "environment")}${obudowa}${donice}</div>`;
}

function renderTargetsBlock() {
  const airFields = TARGET_AIR_FIELDS.map(name => fieldByName(name)).filter(Boolean);
  const soilFields = TARGET_SOIL_FIELDS.map(name => fieldByName(name)).filter(Boolean);
  const airCells = airFields.map(renderMiniCell).join("");
  const soilCells = soilFields.map(renderMiniCell).join("");
  return `<div class="card targets-panel">${renderSectionHead("Cele", "targets")}
    <div class="targets-split">
      <div class="sub-card"><div class="card-head"><h3>Powietrze</h3></div><div class="compact-row">${airCells}</div></div>
      <div class="sub-card"><div class="card-head"><h3>Donice</h3></div><div class="compact-row">${soilCells}</div></div>
    </div></div>`;
}

function renderPreviousBlock() {
  const globalFields = PREVIOUS_GLOBAL_FIELDS.map(name => fieldByName(name)).filter(Boolean);
  const pumpFields = PREVIOUS_PUMP_FIELDS.map(name => fieldByName(name)).filter(Boolean);
  const globalCells = globalFields.map(renderMiniCell).join("");
  const pumpCells = pumpFields.map(renderMiniCell).join("");
  return `<div class="card previous-panel">${renderSectionHead("Poprzedni stan aktuatorów", "previous")}
    <div class="targets-split">
      <div class="sub-card"><div class="card-head"><h3>Klimat</h3></div><div class="compact-row">${globalCells}</div></div>
      <div class="sub-card"><div class="card-head"><h3>Pompy</h3></div><div class="compact-row">${pumpCells}</div></div>
    </div></div>`;
}

function renderZoneCultivationCard(fields, index) {
  if (!fields.length) return "";
  const cells = fields.map(renderMiniCell).join("");
  return `<div class="pot-card cultivation-pot-card"><div class="head-row"><span class="name">Donica ${index + 1}</span></div><div class="compact-row">${cells}</div></div>`;
}

function renderControlTypeToggle(field) {
  if (!field || field.type !== "enum") return "";
  const value = normalizeControlType(getNested(scenario, field.path) ?? field.default);
  const label = formatEnumOptionLabel(value);
  const hintAttr = fieldHintAttr(field.name) || ' title="Kliknij: bin ↔ pwm"';
  return `<button type="button" class="control-type-toggle" data-path="${field.path}"
    data-value="${value}"${hintAttr} aria-label="Typ sterowania: ${label}">${label}</button>`;
}

function toggleControlType(button) {
  const path = button.dataset.path;
  if (!path) return;
  const current = normalizeControlType(button.dataset.value);
  const next = current === "pwm" ? "binary" : "pwm";
  button.dataset.value = next;
  const label = formatEnumOptionLabel(next);
  button.textContent = label;
  button.setAttribute("aria-label", `Typ sterowania: ${label}`);
  collectScenario();
}

function renderActuatorParamField(field) {
  const id = `f-${field.path.replaceAll(".", "_")}`;
  const value = getNested(scenario, field.path);
  const hintAttr = fieldHintAttr(field.name);
  const ariaLabel = escapeHtml(shortLabel(field.name));
  let control;
  if (field.type === "enum") {
    const opts = (field.options || []).map(o =>
      `<option value="${o.value}" ${value === o.value ? "selected" : ""}>${formatEnumOptionLabel(o.value)}</option>`
    ).join("");
    control = `<select${fieldControlClassAttr()} data-path="${field.path}" id="${id}"${hintAttr}
      aria-label="${ariaLabel}">${opts}</select>`;
  } else {
    control = renderWrappedNumberInput(field, {
      id,
      hintAttr,
      ariaLabel,
      wrapClass: "actuator-input-wrap",
      suffixClass: "actuator-input-suffix",
    });
  }
  const wideClass = isWideField(field) ? " wide-param" : "";
  return `<div class="actuator-param${wideClass}">${control}</div>`;
}

function renderActuatorGroupCell(title, names, sectionId) {
  const field = name => fieldByName(name, sectionId);
  const availableName = names.find(n => n.endsWith("_available"));
  const controlTypeName = names.find(n => n.endsWith("_control_type"));
  const availableField = availableName ? field(availableName) : null;
  const controlTypeField = controlTypeName ? field(controlTypeName) : null;
  const paramFields = names
    .filter(n => n !== availableName && n !== controlTypeName)
    .map(n => field(n))
    .filter(Boolean);
  const wide = paramFields.some(isWideField) ? " wide" : "";
  const availId = availableField ? `f-${availableField.path.replaceAll(".", "_")}` : "";
  const availVal = availableField ? getNested(scenario, availableField.path) : false;
  const availHintAttr = availableField ? fieldHintAttr(availableField.name) : "";
  const stack = `<div class="field-stack">${paramFields.map(renderActuatorParamField).join("")}</div>`;
  return `<div class="mini-cell actuator-cell${wide}">
    <div class="head-row">
      <span class="name">${title}</span>
      <div class="actuator-head-actions">
        ${controlTypeField ? renderControlTypeToggle(controlTypeField) : ""}
        ${availableField ? `<input type="checkbox" data-path="${availableField.path}" id="${availId}"${availHintAttr} ${availVal ? "checked" : ""} />` : ""}
      </div>
    </div>
    ${stack}
  </div>`;
}

function renderActuatorRow(groups, sectionId) {
  return groups.map(([title, names]) => renderActuatorGroupCell(title, names, sectionId)).join("");
}

function renderActuatorBlock() {
  const climate = renderActuatorRow(ACTUATOR_CLIMATE_GROUPS, "actuators");
  const pumps = renderActuatorRow(ACTUATOR_PUMP_GROUPS, "zones");
  return `<div class="actuators-split">
    <div class="sub-card actuators-climate-block"><div class="card-head"><h3>Klimat</h3></div><div class="compact-row">${climate}</div></div>
    <div class="sub-card actuators-pumps-block"><div class="card-head"><h3>Pompy</h3></div><div class="compact-row">${pumps}</div></div>
  </div>`;
}

function renderActuatorPanel() {
  return `<div class="card actuators-panel">${renderSectionHead("Aktuary", "actuators")}${renderActuatorBlock()}</div>`;
}

function renderSafetyParamCell(title, fieldNames) {
  const paramFields = fieldNames.map(name => fieldByName(name, "safety")).filter(Boolean);
  const wide = paramFields.some(isWideField) ? " wide" : "";
  const stack = `<div class="field-stack">${paramFields.map(renderActuatorParamField).join("")}</div>`;
  return `<div class="mini-cell actuator-cell${wide}">
    <div class="head-row"><span class="name">${title}</span></div>
    ${stack}
  </div>`;
}

function renderSafetyFieldsSubCard(title, fieldNames) {
  const cells = fieldNames.map(name => fieldByName(name, "safety")).filter(Boolean).map(renderMiniCell).join("");
  if (!cells) return "";
  return `<div class="sub-card"><div class="card-head"><h3>${title}</h3></div><div class="compact-row">${cells}</div></div>`;
}

function renderSafetyBlock(inSetup = false) {
  const temperature = renderSafetyFieldsSubCard("Temperatura", SAFETY_TEMPERATURE_FIELDS);
  const rules = renderSafetyFieldsSubCard("Reguły", SAFETY_RULE_FIELDS);
  const co2 = renderSafetyFieldsSubCard("CO₂", SAFETY_CO2_FIELDS);
  const irrigation = renderSafetyFieldsSubCard("Podlewanie", SAFETY_IRRIGATION_FIELDS);
  const antiflapCells = SAFETY_ANTIFLAP_GROUPS.map(([title, names]) =>
    renderSafetyParamCell(title, names)
  ).join("");
  const antiflap = `<div class="sub-card"><div class="card-head"><h3>Anty-flapping</h3></div><div class="compact-row">${antiflapCells}</div></div>`;
  const head = inSetup ? "" : renderSectionHead("Limity safety", "safety");
  return `<div class="card safety-panel">${head}
    <div class="targets-split">${temperature}${rules}</div>
    <div class="targets-split">${co2}${irrigation}</div>
    ${antiflap}
  </div>`;
}

function renderForm() {
  if (!panelSchema) return;
  const root = document.getElementById("form-sections");
  root.innerHTML = renderSensorBlock();
  updateSeedInput();
  root.innerHTML += renderTargetsBlock();
  root.innerHTML += renderActuatorPanel();
  renderSetupPanes();
  const previousRoot = document.getElementById("previous-section");
  if (previousRoot) {
    previousRoot.innerHTML = renderPreviousBlock();
  }
  syncLightsActiveDisplay();
}
