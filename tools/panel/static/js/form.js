function shortLabel(name) {
  return LABEL_MAP[name] || name.replace(/_/g, " ");
}

function formatEnumOptionLabel(value) {
  if (value === "binary") return "bin";
  if (value === "pwm") return "pwm";
  return value;
}

const FIELD_CONTROL_CLASS = "field-control";

function fieldHint(name) {
  return FIELD_HINTS[name] || "";
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

function renderSensorMiniCell(sensorKey, validityKey) {
  const sensorField = sensorFieldMeta(sensorKey);
  if (!sensorField) return "";
  const sId = `f-sensors_${sensorKey}`;
  const sVal = getNested(scenario, `sensors.${sensorKey}`);
  const sensorPath = `sensors.${sensorKey}`;
  const step = fieldStepForPath(sensorPath);
  const displayValue = formatFieldNumber(sVal ?? sensorField.default, sensorPath);
  const hint = fieldHint(sensorKey);
  const hintAttr = hint ? ` title="${hint}"` : "";
  const validityControl = validityKey
    ? (() => {
        const vId = `f-validity_${validityKey}`;
        const vVal = getNested(scenario, `validity.${validityKey}`);
        const vHint = validityHint(validityKey);
        return `<input type="checkbox" data-path="validity.${validityKey}" id="${vId}" title="${vHint}" ${vVal ? "checked" : ""} />`;
      })()
    : "";
  return `<div class="mini-cell">
    <div class="head-row">
      <span class="name"${hintAttr}>${shortLabel(sensorKey)}</span>
      ${validityControl}
    </div>
    <input type="number"${fieldControlClassAttr()} data-path="${sensorPath}" id="${sId}"${hintAttr}
      min="${sensorField.minimum}" max="${sensorField.maximum}" step="${step}" value="${displayValue}" />
  </div>`;
}

function renderSensorSubCard(title, sensors) {
  const cells = sensors.map(([sensorKey, validityKey]) =>
    renderSensorMiniCell(sensorKey, validityKey)
  ).join("");
  return `<div class="sub-card"><div class="card-head"><h3>${title}</h3></div><div class="compact-row">${cells}</div></div>`;
}

function renderSensorBlock() {
  const left = renderSensorSubCard(SENSOR_GROUPS[0].title, SENSOR_GROUPS[0].sensors);
  const right = renderSensorSubCard(SENSOR_GROUPS[1].title, SENSOR_GROUPS[1].sensors);
  return `<div class="card growbox-panel">${renderSectionHead("Czujniki", "sensors")}<div class="growbox-split">${left}${right}</div></div>`;
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
  if (path.startsWith("sensors.")) {
    return path.includes("co2") ? "1" : "0.1";
  }
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

function renderGrowboxPanel() {
  const env = panelSchema.sections.find(s => s.id === "environment");
  if (!env) return "";
  return `<div class="card growbox-panel">${renderSubCard(env.title, env.fields, "environment")}</div>`;
}

function renderZonesBlock(section) {
  const zones = [[], [], [], []];
  for (const field of section.fields) {
    const match = field.path.match(/^zones\.(\d+)\./);
    if (match) zones[Number(match[1])].push(field);
  }
  const cards = zones.map((fields, index) => {
    if (!fields.length) return "";
    const cells = fields.map(renderMiniCell).join("");
    return `<div class="sub-card zone-card"><div class="card-head"><h3>Strefa ${index + 1}</h3></div><div class="compact-row">${cells}</div></div>`;
  }).join("");
  return `<div class="card zones-panel">${renderSectionHead(section.title, "zones")}<div class="zones-grid">${cards}</div></div>`;
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

function renderActuatorGroupCell(title, names, byName) {
  const availableName = names.find(n => n.endsWith("_available"));
  const availableField = availableName ? byName[availableName] : null;
  const paramFields = names.filter(n => n !== availableName).map(n => byName[n]).filter(Boolean);
  const isIrrigation = title === "Pompa";
  const wide = paramFields.some(isWideField) || isIrrigation ? " wide" : "";
  const availId = availableField ? `f-${availableField.path.replaceAll(".", "_")}` : "";
  const availVal = availableField ? getNested(scenario, availableField.path) : false;
  const availHint = availableField ? fieldHint(availableField.name) : "";
  const availHintAttr = availHint ? ` title="${availHint}"` : "";
  const stack = `<div class="field-stack">${paramFields.map(renderActuatorParamField).join("")}</div>`;
  return `<div class="mini-cell actuator-cell${wide}${isIrrigation ? " actuator-cell-irrigation" : ""}">
    <div class="head-row">
      <span class="name">${title}</span>
      ${availableField ? `<input type="checkbox" data-path="${availableField.path}" id="${availId}"${availHintAttr} ${availVal ? "checked" : ""} />` : ""}
    </div>
    ${stack}
  </div>`;
}

function renderActuatorBlock(section) {
  const byName = Object.fromEntries(section.fields.map(f => [f.name, f]));
  const cells = ACTUATOR_GROUPS.map(([title, names]) => renderActuatorGroupCell(title, names, byName)).join("");
  return `<div class="compact-row">${cells}</div>`;
}

function renderForm() {
  if (!panelSchema) return;
  const root = document.getElementById("form-sections");
  const safetyRoot = document.getElementById("safety-section");
  root.innerHTML = renderSensorBlock();
  updateSeedInput();
  root.innerHTML += renderGrowboxPanel();
  if (safetyRoot) safetyRoot.innerHTML = "";
  for (const section of panelSchema.sections) {
    if (section.id === "sensors" || section.id === "validity"
        || section.id === "environment" || section.id === "cultivation"
        || section.id === "previous") continue;
    if (section.id === "zones") {
      root.innerHTML += renderZonesBlock(section);
      continue;
    }
    const card = document.createElement("div");
    card.className = "card";
    card.innerHTML = `<h2>${section.title}</h2>`;
    if (section.id === "actuators") {
      root.innerHTML += `<div class="card">${renderSectionHead(section.title, "actuators")}${renderActuatorBlock(section)}</div>`;
    } else if (section.id === "safety") {
      if (safetyRoot) {
        safetyRoot.innerHTML = renderFieldsSubCard(section, section.id);
      }
    } else if (section.id === "targets") {
      root.innerHTML += renderFieldsSubCard(section, section.id);
    } else {
      const grid = document.createElement("div");
      grid.className = "section-grid";
      grid.innerHTML = section.fields.map(renderField).join("");
      card.appendChild(grid);
      root.appendChild(card);
    }
  }
}
