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

function formatPreviousDisplayValue(path) {
  const value = getNested(scenario, path);
  const pct = typeof formatOutputPct === "function"
    ? formatOutputPct(value)
    : Math.min(100, Math.max(0, Math.round((Number(value) || 0) * 100)));
  return `${pct}%`;
}

function syncPreviousDisplay() {
  document.querySelectorAll("#previous-section [data-previous-path]").forEach((el) => {
    const path = el.dataset.previousPath;
    if (!path) return;
    el.innerHTML = `<strong>${formatPreviousDisplayValue(path)}</strong>`;
  });
}

function renderPreviousRow(field) {
  const hint = fieldHint(field.name);
  const hintAttr = hint ? ` title="${escapeHtml(hint)}"` : "";
  const value = formatPreviousDisplayValue(field.path);
  return `<tr>
    <th scope="row"${hintAttr}>${shortLabel(field.name)}</th>
    <td class="num" data-previous-path="${field.path}"><strong>${value}</strong></td>
  </tr>`;
}

function renderPreviousGroupTable(title, fields) {
  if (!fields.length) return "";
  const rows = fields.map(renderPreviousRow).join("");
  return `<div class="live-sensor-col">
    <div class="live-sensor-col-head">${title}</div>
    <div class="live-data-table-wrap">
      <table class="live-data-table previous-data-table" aria-label="${title}">
        <colgroup>
          <col class="sensor-col" />
          <col class="reading-col" />
        </colgroup>
        <thead>
          <tr>
            <th scope="col" class="sensor-col"></th>
            <th scope="col" class="num">Wyjście</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </div>
  </div>`;
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
  const glyphs = [...suffix].length;
  if (glyphs >= 7) return " suffix-long";
  if (glyphs >= 3) return " suffix-med";
  if (glyphs === 2) return " suffix-pad-2";
  return " suffix-pad-1";
}

/** Węższe wrapy: s (aktuary), ppm (−1ch), % (−3ch), °C (−2ch). */
function fieldSuffixWidthClass(suffix) {
  if (suffix === "s") return " suffix-w-s";
  if (suffix === "ppm") return " suffix-w-ppm";
  if (suffix === "%") return " suffix-w-pct";
  if (suffix === "°C") return " suffix-w-temp";
  if (suffix === "L") return " suffix-w-pct";
  if (suffix === "mL") return " suffix-w-ppm";
  if (suffix === "×") return " suffix-w-s";
  return "";
}

function fieldMiniCellWidthClass(field) {
  const zoneCult = field.name.match(/^zone_\d+_(pot_volume_l|substrate_water_capacity_ml|transpiration_factor)$/);
  if (zoneCult) {
    if (zoneCult[1] === "pot_volume_l") return " mini-cell-pct";
    if (zoneCult[1] === "substrate_water_capacity_ml") return " mini-cell-ppm";
    return " mini-cell-factor";
  }
  if (isWideField(field)) return " wide";
  if (isPreviousRatioPath(field.path)) return " mini-cell-prev";
  const suffix = fieldUnitSuffix(field);
  if (suffix === "%") return " mini-cell-pct";
  if (suffix === "°C") return " mini-cell-temp";
  if (suffix === "ppm") return " mini-cell-ppm";
  return "";
}

function renderWrappedNumberInput(field, opts = {}) {
  const id = opts.id || `f-${field.path.replaceAll(".", "_")}`;
  const disabled = Boolean(opts.disabled);
  const hintAttr = opts.hintAttr ?? (disabled ? inactiveZoneDependentHintAttr() : fieldHintAttr(field.name));
  const ariaLabel = opts.ariaLabel ?? escapeHtml(shortLabel(field.name));
  const displayValue = opts.displayValue
    ?? formatFieldNumber(getNested(scenario, field.path) ?? field.default, field.path);
  const suffix = fieldUnitSuffix(field);
  const suffixClass = fieldSuffixSizeClass(suffix) + fieldSuffixWidthClass(suffix);
  const wrapClass = opts.wrapClass || "field-input-wrap";
  const suffixClassName = opts.suffixClass || "field-input-suffix";
  const disabledAttr = disabled ? " disabled" : "";
  const suffixMarkup = suffix
    ? `<span class="${suffixClassName}" aria-hidden="true">${escapeHtml(suffix)}</span>`
    : "";
  return `<div class="${wrapClass}${suffixClass}">
    <input type="number"${fieldControlClassAttr()} data-path="${field.path}" id="${id}"${hintAttr}${disabledAttr}
      aria-label="${ariaLabel}" min="${field.minimum}" max="${field.maximum}" step="${fieldStep(field)}"
      value="${displayValue}" />
    ${suffixMarkup}
  </div>`;
}

function isZoneActive(zoneIndex) {
  return Boolean(getNested(scenario, `zones.${zoneIndex}.available`));
}

function inactiveZoneDependentHintAttr() {
  const hint = typeof INACTIVE_ZONE_DEPENDENT_HINT === "string" ? INACTIVE_ZONE_DEPENDENT_HINT : "";
  return hint ? ` title="${hint}"` : "";
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
  document.getElementById("help-modal-close")?.focus({ preventScroll: true });
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
  const widthClass = fieldMiniCellWidthClass(wrappedSensor);
  return `<div class="mini-cell${widthClass}">
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
  return field.path.includes("thermal_mass") || field.path.includes("substrate_water");
}

function isHumidityPctPath(path) {
  return path.includes("humidity_pct") || path.includes("soil_moisture_pct");
}

function isCo2PpmPath(path) {
  return path.endsWith("co2_ppm") || path.includes("dose_ppm_per_full_pulse");
}

function isTemperatureCPath(path) {
  return path.includes("temperature_c");
}

function isPreviousRatioPath(path) {
  return path.startsWith("previous.") || path.includes(".previous.");
}

function fieldStep(field) {
  if (isHumidityPctPath(field.path)) return "1";
  if (isCo2PpmPath(field.path)) return "1";
  if (isTemperatureCPath(field.path)) return "1";
  if (field.path.includes("pct") || field.path.includes("ratio")) return "0.1";
  if (field.path.endsWith("_s")) return "1";
  return "0.01";
}

function fieldStepForPath(path) {
  if (isHumidityPctPath(path)) return "1";
  if (isCo2PpmPath(path)) return "1";
  if (isTemperatureCPath(path)) return "1";
  if (path.startsWith("safety.")) {
    if (path.endsWith("_s")) return "1";
    if (path.includes("threshold") || path.includes("minimum_fan")) return "0.01";
    return "0.1";
  }
  if (path.startsWith("sensors.") || (path.includes("zones.") && path.includes(".sensors."))) {
    return isCo2PpmPath(path) ? "1" : "0.1";
  }
  if (path.includes("zones.") && path.includes(".targets.")) return "0.1";
  if (path.startsWith("previous.")) return "0.001";
  if (path.includes("pct") || path.includes("ratio") || path.includes("efficiency") || path.includes("minimum_command") || path.includes("transpiration")) {
    return "0.01";
  }
  if (path.endsWith("_s") || path.includes("thermal_mass") || path.includes("substrate_water") || path.includes("minimum_interval")) {
    return "1";
  }
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

function clampFieldNumber(value, path, el) {
  let normalized = normalizeFieldNumber(value, path);
  if (typeof normalized !== "number" || !Number.isFinite(normalized)) return normalized;
  const min = el?.min !== "" && el?.min != null ? Number(el.min) : NaN;
  const max = el?.max !== "" && el?.max != null ? Number(el.max) : NaN;
  if (Number.isFinite(min)) normalized = Math.max(min, normalized);
  if (Number.isFinite(max)) normalized = Math.min(max, normalized);
  return normalizeFieldNumber(normalized, path);
}

function isIncompleteNumberInput(raw) {
  const text = String(raw).trim();
  if (text === "" || text === "-" || text === "." || text === "-." || text === "+") return true;
  return /[.,]$/.test(text);
}

function parseScenarioNumberInput(el) {
  if (!el || el.type !== "number" || !el.dataset.path) return undefined;
  const raw = String(el.value).trim();
  if (isIncompleteNumberInput(raw)) return null;
  const num = Number(raw);
  if (!Number.isFinite(num)) return null;
  return clampFieldNumber(num, el.dataset.path, el);
}

function formatScenarioNumberInput(el) {
  if (!el || el.type !== "number" || !el.dataset.path) return;
  const value = parseScenarioNumberInput(el);
  if (value === null || value === undefined || !Number.isFinite(value)) return;
  el.value = formatFieldNumber(value, el.dataset.path);
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
  const widthClass = field.type === "boolean"
    ? (isWideField(field) ? " wide" : "")
    : fieldMiniCellWidthClass(field);

  if (field.type === "boolean") {
    const id = `f-${field.path.replaceAll(".", "_")}`;
    const value = getNested(scenario, field.path);
    if (isAvailabilityField(field.name)) {
      const hint = fieldHint(field.name);
      const hintAttr = hint ? ` title="${hint}"` : "";
      return `<div class="mini-cell bool-only${widthClass}">
        <div class="head-row tick-only">
          <input type="checkbox" data-path="${field.path}" id="${id}"${hintAttr} ${value ? "checked" : ""} />
        </div>
      </div>`;
    }
    const hintAttr = fieldHintAttr(field.name);
    return `<div class="mini-cell bool-only${widthClass}">
      <div class="head-row">
        <span class="name"${hintAttr}>${shortLabel(field.name)}</span>
        <input type="checkbox" data-path="${field.path}" id="${id}"${hintAttr} ${value ? "checked" : ""} />
      </div>
    </div>`;
  }
  return `<div class="mini-cell${widthClass}">${renderMiniCellInput(field)}</div>`;
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

function controlTypeFieldFromGroup(names, sectionId) {
  const controlTypeName = names.find(name => name.endsWith("_control_type"));
  return controlTypeName ? fieldByName(controlTypeName, sectionId) : null;
}

function renderGrowboxActuatorTypeSelect(field, title, { disabled = false } = {}) {
  if (!field || field.type !== "enum") return "";
  const value = normalizeControlType(getNested(scenario, field.path) ?? field.default);
  const id = `f-setup-${field.path.replaceAll(".", "_")}`;
  const hintAttr = disabled ? inactiveZoneDependentHintAttr() : fieldHintAttr(field.name);
  const disabledAttr = disabled ? " disabled" : "";
  const opts = (field.options || []).map(o =>
    `<option value="${o.value}" ${value === o.value ? "selected" : ""}>${formatEnumOptionLabel(o.value)}</option>`
  ).join("");
  return `<select class="field-control setup-control-type-select" data-path="${field.path}" id="${id}"${hintAttr}${disabledAttr}
    aria-label="Typ sterowania ${escapeHtml(title)}">${opts}</select>`;
}

function renderGrowboxActuatorTypeCard(title, names, sectionId) {
  const controlTypeField = controlTypeFieldFromGroup(names, sectionId);
  if (!controlTypeField) return "";
  const zoneIndex = zoneIndexFromPumpGroup(names);
  const zonePumpInactive = zoneIndex !== null && !isZoneActive(zoneIndex);
  const inactiveClass = zonePumpInactive ? " inactive-zone-pump" : "";
  const titleHintAttr = zonePumpInactive ? inactiveZoneDependentHintAttr() : "";
  return `<div class="pot-card setup-actuator-type-card${inactiveClass}">
    <div class="head-row"><span class="name"${titleHintAttr}>${title}</span></div>
    ${renderGrowboxActuatorTypeSelect(controlTypeField, title, { disabled: zonePumpInactive })}
  </div>`;
}

function renderGrowboxActuatorTypeRow(groups, sectionId) {
  return groups.map(([title, names]) => renderGrowboxActuatorTypeCard(title, names, sectionId)).join("");
}

function renderGrowboxActuatorsSubCard() {
  const climate = renderGrowboxActuatorTypeRow(ACTUATOR_CLIMATE_GROUPS, "actuators");
  const pumps = renderGrowboxActuatorTypeRow(ACTUATOR_PUMP_GROUPS, "zones");
  if (!climate && !pumps) return "";
  return `<div class="sub-card setup-actuators-block">
    <div class="card-head"><h3>Aktuary</h3></div>
    <div class="setup-actuators-groups">
      <div class="sub-card"><div class="card-head"><h3>Klimat</h3></div><div class="compact-row actuators-type-row">${climate}</div></div>
      <div class="sub-card"><div class="card-head"><h3>Pompy</h3></div><div class="compact-row actuators-type-row">${pumps}</div></div>
    </div>
  </div>`;
}

function renderGrowboxPanel(inSetup = false) {
  const env = panelSchema.sections.find(s => s.id === "environment");
  const zonesSection = sectionById("zones");
  if (!env && !zonesSection) return "";
  const obudowa = env ? renderSubCard("Obudowa", env.fields, inSetup ? null : "environment") : "";
  const donice = zonesSection ? renderGrowboxCultivationSubCard(zonesSection) : "";
  if (inSetup) {
    const aktuary = renderGrowboxActuatorsSubCard();
    return `<div class="setup-growbox-body">${obudowa}${donice}${aktuary}</div>`;
  }
  return `<div class="card growbox-panel environment-panel">${renderSectionHead("Parametry growboxa", "environment")}${obudowa}${donice}</div>`;
}

function isZoneSoilTargetActive(field) {
  const match = field.name.match(/^zone_(\d+)_target_soil_moisture_pct$/);
  if (!match) return true;
  return isZoneActive(Number(match[1]) - 1);
}

function renderSoilTargetMiniCell(field) {
  const active = isZoneSoilTargetActive(field);
  const inactiveHint = inactiveZoneDependentHintAttr();
  if (!active) {
    const id = `f-${field.path.replaceAll(".", "_")}`;
    const value = getNested(scenario, field.path);
    const displayValue = formatFieldNumber(value ?? field.default, field.path);
    const label = `<div class="label-row"><span class="name"${inactiveHint}>${shortLabel(field.name)}</span></div>`;
    const widthClass = fieldMiniCellWidthClass(field);
    return `<div class="mini-cell inactive-zone-target${widthClass}">
      ${label}
      ${renderWrappedNumberInput(field, { id, displayValue, disabled: true })}
    </div>`;
  }
  return renderMiniCell(field);
}

function syncInactiveZoneTargetInputs() {
  for (let index = 0; index < 4; index += 1) {
    const field = fieldByName(zoneTargetFieldName(index));
    if (!field) continue;
    const active = isZoneActive(index);
    const el = document.getElementById(`f-${field.path.replaceAll(".", "_")}`);
    if (!el || el.type !== "number") continue;
    const cell = el.closest(".mini-cell");
    if (cell) cell.classList.toggle("inactive-zone-target", !active);
    el.disabled = !active;
    el.title = active ? (fieldHint(field.name) || "") : INACTIVE_ZONE_DEPENDENT_HINT;
    const nameEl = cell?.querySelector(".name");
    if (nameEl) {
      if (!active) nameEl.setAttribute("title", INACTIVE_ZONE_DEPENDENT_HINT);
      else nameEl.removeAttribute("title");
    }
  }
}

function zoneIndexFromPumpGroup(names) {
  const availableName = names.find(name => /^zone_\d+_irrigation_available$/.test(name));
  if (!availableName) return null;
  const match = availableName.match(/^zone_(\d+)_irrigation_available$/);
  return match ? Number(match[1]) - 1 : null;
}

function syncInactiveZonePumpInputs() {
  for (let index = 0; index < 4; index += 1) {
    const field = fieldByName(`zone_${index + 1}_irrigation_available`, "zones");
    if (!field) continue;
    const active = isZoneActive(index);
    const availEl = document.getElementById(`f-${field.path.replaceAll(".", "_")}`);
    const cell = availEl?.closest(".mini-cell.actuator-cell");
    if (cell) cell.classList.toggle("inactive-zone-pump", !active);
    if (availEl) {
      availEl.disabled = !active;
      if (!active) availEl.checked = false;
      availEl.title = active ? (fieldHint(field.name) || "") : INACTIVE_ZONE_DEPENDENT_HINT;
    }
    const controlField = fieldByName(`zone_${index + 1}_irrigation_control_type`, "zones");
    if (controlField) {
      const selectEl = document.querySelector(`select.setup-control-type-select[data-path="${controlField.path}"]`);
      const typeCard = selectEl?.closest(".setup-actuator-type-card");
      if (typeCard) typeCard.classList.toggle("inactive-zone-pump", !active);
      if (selectEl) {
        selectEl.disabled = !active;
        selectEl.title = active ? (fieldHint(controlField.name) || "") : INACTIVE_ZONE_DEPENDENT_HINT;
      }
    }
    if (!cell) continue;
    cell.querySelectorAll("input.field-control, select.field-control").forEach(el => {
      el.disabled = !active;
    });
    const titleEl = cell.querySelector(".head-row .name");
    if (titleEl) {
      if (!active) titleEl.setAttribute("title", INACTIVE_ZONE_DEPENDENT_HINT);
      else titleEl.removeAttribute("title");
    }
  }
}

function syncInactiveZoneDependentInputs() {
  syncInactiveZoneTargetInputs();
  syncInactiveZonePumpInputs();
}

function renderTargetsBlock() {
  const airFields = TARGET_AIR_FIELDS.map(name => fieldByName(name)).filter(Boolean);
  const soilFields = TARGET_SOIL_FIELDS.map(name => fieldByName(name)).filter(Boolean);
  const airCells = airFields.map(renderMiniCell).join("");
  const soilCells = soilFields.map(renderSoilTargetMiniCell).join("");
  return `<div class="card targets-panel">${renderSectionHead("Cele", "targets")}
    <div class="targets-split">
      <div class="sub-card"><div class="card-head"><h3>Powietrze</h3></div><div class="compact-row">${airCells}</div></div>
      <div class="sub-card"><div class="card-head"><h3>Donice</h3></div><div class="compact-row">${soilCells}</div></div>
    </div></div>`;
}

function renderPreviousBlock() {
  const globalFields = PREVIOUS_GLOBAL_FIELDS.map(name => fieldByName(name)).filter(Boolean);
  const pumpFields = PREVIOUS_PUMP_FIELDS.map(name => fieldByName(name)).filter(Boolean);
  const climate = renderPreviousGroupTable("Klimat", globalFields);
  const pumps = renderPreviousGroupTable("Pompy", pumpFields);
  return `<div class="card previous-panel">${renderSectionHead("Poprzedni stan aktuatorów", "previous")}
    <div class="live-sensors-split previous-split" aria-label="Poprzedni stan aktuatorów">${climate}${pumps}</div></div>`;
}

function renderZoneCultivationCard(fields, index) {
  if (!fields.length) return "";
  const cells = fields.map(renderMiniCell).join("");
  return `<div class="pot-card cultivation-pot-card"><div class="head-row"><span class="name">Donica ${index + 1}</span></div><div class="pot-card-cultivation">${cells}</div></div>`;
}

function syncControlTypeField(path, value) {
  if (!path) return;
  const normalized = normalizeControlType(value);
  document.querySelectorAll(`select.setup-control-type-select[data-path="${path}"]`).forEach(el => {
    el.value = normalized;
  });
}

function renderActuatorParamField(field, { disabled = false } = {}) {
  const id = `f-${field.path.replaceAll(".", "_")}`;
  const value = getNested(scenario, field.path);
  const hintAttr = disabled ? inactiveZoneDependentHintAttr() : fieldHintAttr(field.name);
  const ariaLabel = escapeHtml(shortLabel(field.name));
  const disabledAttr = disabled ? " disabled" : "";
  let control;
  if (field.type === "enum") {
    const opts = (field.options || []).map(o =>
      `<option value="${o.value}" ${value === o.value ? "selected" : ""}>${formatEnumOptionLabel(o.value)}</option>`
    ).join("");
    control = `<select${fieldControlClassAttr()} data-path="${field.path}" id="${id}"${hintAttr}${disabledAttr}
      aria-label="${ariaLabel}">${opts}</select>`;
  } else {
    control = renderWrappedNumberInput(field, {
      id,
      hintAttr,
      ariaLabel,
      disabled,
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
  const availableField = availableName ? field(availableName) : null;
  const paramFields = names
    .filter(n => n !== availableName && !n.endsWith("_control_type"))
    .map(n => field(n))
    .filter(Boolean);
  const zoneIndex = zoneIndexFromPumpGroup(names);
  const zonePumpInactive = zoneIndex !== null && !isZoneActive(zoneIndex);
  const wide = paramFields.some(isWideField) ? " wide" : "";
  const availId = availableField ? `f-${availableField.path.replaceAll(".", "_")}` : "";
  const availVal = zonePumpInactive
    ? false
    : (availableField ? getNested(scenario, availableField.path) : false);
  const availHintAttr = zonePumpInactive
    ? inactiveZoneDependentHintAttr()
    : (availableField ? fieldHintAttr(availableField.name) : "");
  const disabledAttr = zonePumpInactive ? " disabled" : "";
  const inactiveClass = zonePumpInactive ? " inactive-zone-pump" : "";
  const titleHintAttr = zonePumpInactive ? inactiveZoneDependentHintAttr() : "";
  const stack = `<div class="field-stack">${paramFields
    .map(f => renderActuatorParamField(f, { disabled: zonePumpInactive }))
    .join("")}</div>`;
  return `<div class="mini-cell actuator-cell${wide}${inactiveClass}">
    <div class="head-row">
      <span class="name"${titleHintAttr}>${title}</span>
      <div class="actuator-head-actions">
        ${availableField ? `<input type="checkbox" data-path="${availableField.path}" id="${availId}"${availHintAttr}${disabledAttr} ${availVal ? "checked" : ""} />` : ""}
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
  syncInactiveZoneDependentInputs();
}
