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
  const zoneIrr = name.match(/^zone_\d+_irrigation_(.+)$/);
  if (zoneIrr) {
    const baseKey = `irrigation_${zoneIrr[1]}`;
    if (FIELD_HINTS[baseKey]) return FIELD_HINTS[baseKey];
  }
  const zoneCult = name.match(/^zone_\d+_(pot_volume_l|substrate_water_capacity_ml|transpiration_factor)$/);
  if (zoneCult && FIELD_HINTS[zoneCult[1]]) return FIELD_HINTS[zoneCult[1]];
  return "";
}

function fieldControlClassAttr() {
  return ` class="${FIELD_CONTROL_CLASS}"`;
}

function fieldByName(name) {
  for (const section of panelSchema.sections) {
    const hit = section.fields.find(f => f.name === name);
    if (hit) return hit;
  }
  return null;
}

function sectionById(id) {
  return panelSchema.sections.find(section => section.id === id) || null;
}

function renderNumberField(field, extraClass = "field-num") {
  const id = `f-${field.path.replaceAll(".", "_")}`;
  const value = getNested(scenario, field.path);
  const step = fieldStep(field);
  const wide = field.path.includes("thermal_mass") || field.path.includes("substrate_water");
  const displayValue = formatFieldNumber(value ?? field.default, field.path);
  return `<label class="${wide ? "field-wide" : extraClass}">
    <span class="lbl">${shortLabel(field.name)}</span>
    <input type="number"${fieldControlClassAttr()} data-path="${field.path}" id="${id}"
      min="${field.minimum}" max="${field.maximum}" step="${step}"
      value="${displayValue}" />
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

function renderPathSensorMiniCell(sensorField, validityField, displayLabel) {
  if (!sensorField) return "";
  const sensorPath = sensorField.path;
  const sId = `f-${sensorPath.replaceAll(".", "_")}`;
  const sVal = getNested(scenario, sensorPath);
  const step = fieldStepForPath(sensorPath);
  const displayValue = formatFieldNumber(sVal ?? sensorField.default, sensorPath);
  const hint = fieldHint(sensorField.name);
  const hintAttr = hint ? ` title="${hint}"` : "";
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
  return `<div class="mini-cell">
    <div class="head-row">
      <span class="name"${hintAttr}>${displayLabel || shortLabel(sensorField.name)}</span>
      ${validityControl}
    </div>
    <input type="number"${fieldControlClassAttr()} data-path="${sensorPath}" id="${sId}"${hintAttr}
      min="${sensorField.minimum}" max="${sensorField.maximum}" step="${step}" value="${displayValue}" />
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
  const hint = fieldHint(field.name);
  const hintAttr = hint ? ` title="${hint}"` : "";
  const label = `<div class="label-row"><span class="name"${hint ? ` title="${hint}"` : ""}>${shortLabel(field.name)}</span></div>`;

  if (field.type === "enum") {
    const opts = (field.options || []).map(o =>
      `<option value="${o.value}" ${value === o.value ? "selected" : ""}>${formatEnumOptionLabel(o.value)}</option>`
    ).join("");
    return `${label}<select${fieldControlClassAttr()} data-path="${field.path}" id="${id}"${hintAttr}>${opts}</select>`;
  }
  const displayValue = formatFieldNumber(value ?? field.default, field.path);
  return `${label}<input type="number"${fieldControlClassAttr()} data-path="${field.path}" id="${id}"${hintAttr}
    min="${field.minimum}" max="${field.maximum}" step="${fieldStep(field)}" value="${displayValue}" />`;
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
    return `<div class="mini-cell bool-only${wide}">
      <div class="head-row">
        <span class="name">${shortLabel(field.name)}</span>
        <input type="checkbox" data-path="${field.path}" id="${id}" ${value ? "checked" : ""} />
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
  return `<div class="sub-card">${renderSectionHead(title, helpTopic, "h3")}<div class="compact-row">${cells}</div></div>`;
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

function renderGrowboxPanel() {
  const env = panelSchema.sections.find(s => s.id === "environment");
  const zonesSection = sectionById("zones");
  if (!env && !zonesSection) return "";
  const obudowa = env ? renderSubCard("Obudowa", env.fields, "environment") : "";
  const donice = zonesSection ? renderGrowboxCultivationSubCard(zonesSection) : "";
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

function renderActuatorParamField(field) {
  const id = `f-${field.path.replaceAll(".", "_")}`;
  const value = getNested(scenario, field.path);
  const hint = fieldHint(field.name);
  const hintAttr = hint ? ` title="${hint}"` : "";
  const label = `<span class="name"${hint ? ` title="${hint}"` : ""}>${shortLabel(field.name)}</span>`;
  let control;
  if (field.type === "enum") {
    const opts = (field.options || []).map(o =>
      `<option value="${o.value}" ${value === o.value ? "selected" : ""}>${formatEnumOptionLabel(o.value)}</option>`
    ).join("");
    control = `<select${fieldControlClassAttr()} data-path="${field.path}" id="${id}"${hintAttr}>${opts}</select>`;
  } else {
    const displayValue = formatFieldNumber(value ?? field.default, field.path);
    control = `<input type="number"${fieldControlClassAttr()} data-path="${field.path}" id="${id}"${hintAttr}
      min="${field.minimum}" max="${field.maximum}" step="${fieldStep(field)}" value="${displayValue}" />`;
  }
  const wideClass = isWideField(field) ? " wide-param" : "";
  return `<div class="actuator-param${wideClass}">${label}${control}</div>`;
}

function renderActuatorGroupCell(title, names) {
  const availableName = names.find(n => n.endsWith("_available"));
  const availableField = availableName ? fieldByName(availableName) : null;
  const paramFields = names.filter(n => n !== availableName).map(n => fieldByName(n)).filter(Boolean);
  const wide = paramFields.some(isWideField) ? " wide" : "";
  const availId = availableField ? `f-${availableField.path.replaceAll(".", "_")}` : "";
  const availVal = availableField ? getNested(scenario, availableField.path) : false;
  const availHint = availableField ? fieldHint(availableField.name) : "";
  const availHintAttr = availHint ? ` title="${availHint}"` : "";
  const stack = `<div class="field-stack">${paramFields.map(renderActuatorParamField).join("")}</div>`;
  return `<div class="mini-cell actuator-cell${wide}">
    <div class="head-row">
      <span class="name">${title}</span>
      ${availableField ? `<input type="checkbox" data-path="${availableField.path}" id="${availId}"${availHintAttr} ${availVal ? "checked" : ""} />` : ""}
    </div>
    ${stack}
  </div>`;
}

function renderActuatorRow(groups) {
  return groups.map(([title, names]) => renderActuatorGroupCell(title, names)).join("");
}

function renderActuatorBlock() {
  const climate = renderActuatorRow(ACTUATOR_CLIMATE_GROUPS);
  const pumps = renderActuatorRow(ACTUATOR_PUMP_GROUPS);
  return `<div class="actuators-split">
    <div class="sub-card"><div class="card-head"><h3>Klimat</h3></div><div class="compact-row">${climate}</div></div>
    <div class="sub-card"><div class="card-head"><h3>Pompy</h3></div><div class="compact-row">${pumps}</div></div>
  </div>`;
}

function renderSafetyParamCell(title, fieldNames) {
  const paramFields = fieldNames.map(name => fieldByName(name)).filter(Boolean);
  const wide = paramFields.some(isWideField) ? " wide" : "";
  const stack = `<div class="field-stack">${paramFields.map(renderActuatorParamField).join("")}</div>`;
  return `<div class="mini-cell actuator-cell${wide}">
    <div class="head-row"><span class="name">${title}</span></div>
    ${stack}
  </div>`;
}

function renderSafetyFieldsSubCard(title, fieldNames) {
  const cells = fieldNames.map(name => fieldByName(name)).filter(Boolean).map(renderMiniCell).join("");
  if (!cells) return "";
  return `<div class="sub-card"><div class="card-head"><h3>${title}</h3></div><div class="compact-row">${cells}</div></div>`;
}

function renderSafetyBlock() {
  const temperature = renderSafetyFieldsSubCard("Temperatura", SAFETY_TEMPERATURE_FIELDS);
  const rules = renderSafetyFieldsSubCard("Reguły", SAFETY_RULE_FIELDS);
  const co2 = renderSafetyFieldsSubCard("CO₂", SAFETY_CO2_FIELDS);
  const irrigation = renderSafetyFieldsSubCard("Podlewanie", SAFETY_IRRIGATION_FIELDS);
  const antiflapCells = SAFETY_ANTIFLAP_GROUPS.map(([title, names]) =>
    renderSafetyParamCell(title, names)
  ).join("");
  const antiflap = `<div class="sub-card"><div class="card-head"><h3>Anty-flapping</h3></div><div class="compact-row">${antiflapCells}</div></div>`;
  return `<div class="card safety-panel">${renderSectionHead("Limity safety", "safety")}
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
  root.innerHTML += renderGrowboxPanel();
  root.innerHTML += renderTargetsBlock();
  root.innerHTML += `<div class="card actuators-panel">${renderSectionHead("Aktuary", "actuators")}${renderActuatorBlock()}</div>`;
  const previousRoot = document.getElementById("previous-section");
  const safetyRoot = document.getElementById("safety-section");
  if (previousRoot) {
    previousRoot.innerHTML = renderPreviousBlock();
  }
  if (safetyRoot) {
    safetyRoot.innerHTML = "";
    const safetySection = sectionById("safety");
    if (safetySection) {
      safetyRoot.innerHTML = renderSafetyBlock();
    }
  }
  syncLightsActiveDisplay();
}
