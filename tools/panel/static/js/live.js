function formatLiveSensorValue(value, decimals) {
  if (typeof value !== "number" || !Number.isFinite(value)) return "—";
  return decimals > 0 ? value.toFixed(decimals) : String(Math.round(value));
}

function formatLiveTargetValue(value, decimals, unit) {
  if (typeof value !== "number" || !Number.isFinite(value)) return "—";
  const formatted = decimals > 0 ? value.toFixed(decimals) : String(Math.round(value));
  return `${formatted}${unit}`;
}

function setLiveStepBadge(step) {
  const el = document.getElementById("live-step-badge");
  if (step === null || step === undefined) {
    if (el) el.hidden = true;
    if (typeof refreshModalStepBadge === "function") refreshModalStepBadge();
    return;
  }
  const label = `Krok ${step}`;
  if (el) {
    el.hidden = false;
    el.textContent = label;
  }
  if (typeof refreshModalStepBadge === "function") refreshModalStepBadge();
}

function previousStepForDisplay() {
  if (typeof lastRenderedPreviousStep === "number" && Number.isFinite(lastRenderedPreviousStep)) {
    return lastRenderedPreviousStep;
  }
  return null;
}

function snapshotPreviousActuators() {
  const pots = Array.isArray(scenario.pots) ? scenario.pots : [];
  return {
    previous: { ...(scenario.previous || {}) },
    pots: pots.map((pot) => ({
      ...(pot || {}),
      previous: { ...(pot?.previous || { irrigation: 0 }) },
    })),
  };
}

function capturePreviousDisplay(decision) {
  const step = decision?.step;
  if (typeof step !== "number" || !Number.isFinite(step)) {
    lastRenderedPreviousStep = null;
    previousDisplaySnapshot = null;
    return;
  }
  previousDisplaySnapshot = snapshotPreviousActuators();
  lastRenderedPreviousStep = Math.max(0, step - 1);
}

function setLiveInferenceMeta(decision) {
  const el = document.getElementById("live-inference-meta");
  if (!el) return;
  const diag = decision?.diagnostics;
  if (!diag) {
    el.hidden = true;
    el.innerHTML = "";
    return;
  }
  const parts = [];
  const reason = diag.safety_reason || "none";
  if (reason !== "none") {
    parts.push(`Kod: <code>${reason}</code>`);
  }
  if (diag.inference_us !== undefined && diag.inference_us !== null) {
    parts.push(`inferencja ${diag.inference_us} µs`);
  }
  if (!parts.length) {
    el.hidden = true;
    el.innerHTML = "";
    return;
  }
  el.hidden = false;
  el.innerHTML = parts.join(" · ");
}

function sensorFieldMeta(sensorKey) {
  return fieldByName(sensorKey) || SIMULATION_SENSOR_FIELDS[sensorKey] || null;
}

function liveNoTargetHint(metric) {
  if (metric.simulationOnly) return "Brak celu — parametr symulacji";
  return "Brak celu — warunki zewnętrzne";
}

function renderLiveMetricRow(metric, decision) {
  const sensors = decision?.sensors || {};
  const targets = decision?.targets || {};
  const validity = decision?.validity || {};
  if (metric.kind === "pseudo") {
    const active = Boolean(decision?.pseudo?.[metric.key]);
    const label = metric.label || shortLabel(metric.key);
    return `<tr class="env-row">
      <th scope="row">${label}</th>
      <td class="num"><strong>${active ? "ON" : "OFF"}</strong></td>
      <td class="num"><span class="live-no-target" title="Brak celu — stan symulacji">—</span></td>
    </tr>`;
  }
  const valueText = formatLiveSensorValue(sensors[metric.key], metric.decimals);
  const valid = validity[metric.key] !== false;
  const targetText = metric.targetKey
    ? formatLiveTargetValue(targets[metric.targetKey], metric.decimals, metric.unit)
    : `<span class="live-no-target" title="${liveNoTargetHint(metric)}">—</span>`;
  const invalidMark = valid ? "" : '<span class="live-invalid" title="Czujnik nieważny">⊘</span>';
  const envClass = metric.targetKey ? "" : " env-row";
  const invalidClass = valid ? "" : " invalid";
  const label = metric.label || shortLabel(metric.key);
  return `<tr class="${envClass}${invalidClass}">
    <th scope="row">${label}${invalidMark}</th>
    <td class="num"><strong>${valueText}${metric.unit}</strong></td>
    <td class="num">${targetText}</td>
  </tr>`;
}

const LIVE_SOIL_TARGET_HINT = "Cel z formularza — na płytce po Wyślij";

function isLiveZoneActive(decision, zoneIndex) {
  const fromDecision = decision?.pots?.[zoneIndex]?.available;
  if (typeof fromDecision === "boolean") return fromDecision;
  return isZoneActive(zoneIndex);
}

function liveZoneSoilTarget(zoneIndex, decision) {
  const fromDecision = decision?.pots?.[zoneIndex]?.targets?.soil_moisture_pct;
  if (typeof fromDecision === "number" && Number.isFinite(fromDecision)) {
    return { value: fromDecision, hint: "" };
  }
  const field = fieldByName(`zone_${zoneIndex + 1}_target_soil_moisture_pct`);
  const value = field
    ? getNested(scenario, field.path)
    : getNested(scenario, `pots.${zoneIndex}.targets.soil_moisture_pct`);
  return { value, hint: LIVE_SOIL_TARGET_HINT };
}

function liveZoneSoilTempTarget(zoneIndex, decision) {
  const fromDecision = decision?.pots?.[zoneIndex]?.targets?.soil_temperature_c;
  if (typeof fromDecision === "number" && Number.isFinite(fromDecision)) {
    return { value: fromDecision, hint: "" };
  }
  const field = fieldByName(`zone_${zoneIndex + 1}_target_soil_temperature_c`);
  const value = field
    ? getNested(scenario, field.path)
    : getNested(scenario, `pots.${zoneIndex}.targets.soil_temperature_c`);
  return { value, hint: LIVE_SOIL_TARGET_HINT };
}

function renderLivePotMetricRow(label, value, decimals, unit, targetValue, targetDecimals, targetUnit, valid, {
  targetHint = "",
} = {}) {
  const valueText = formatLiveSensorValue(value, decimals);
  const targetText = typeof targetValue === "number" && Number.isFinite(targetValue)
    ? formatLiveTargetValue(targetValue, targetDecimals, targetUnit)
    : `<span class="live-no-target" title="Brak celu — temperatura gleby bez targetu">—</span>`;
  const invalidMark = valid ? "" : '<span class="live-invalid" title="Czujnik nieważny">⊘</span>';
  const invalidClass = valid ? "" : " invalid";
  const targetAttr = targetHint ? ` title="${escapeHtml(targetHint)}"` : "";
  return `<tr class="${invalidClass}">
    <th scope="row">${label}${invalidMark}</th>
    <td class="num"><strong>${valueText}${unit}</strong></td>
    <td class="num"${targetAttr}>${targetText}</td>
  </tr>`;
}

function renderLivePotGroupTable(decision) {
  const rowParts = POT_SENSOR_ROWS.flatMap((_pot, index) => {
    if (!isLiveZoneActive(decision, index)) return [];
    const pot = decision?.pots?.[index] || {};
    const sensors = pot.sensors || {};
    const validity = pot.validity || {};
    const { value: moistureTarget, hint: moistureHint } = liveZoneSoilTarget(index, decision);
    const { value: tempTarget, hint: tempHint } = liveZoneSoilTempTarget(index, decision);
    const potNo = index + 1;
    return [
      renderLivePotMetricRow(
        `${potNo} Wilg.`,
        sensors.soil_moisture_pct,
        0,
        "%",
        moistureTarget,
        0,
        "%",
        validity.soil_moisture_pct !== false,
        { targetHint: moistureHint },
      ),
      renderLivePotMetricRow(
        `${potNo} Gleba T`,
        sensors.soil_temperature_c,
        1,
        "°C",
        tempTarget,
        1,
        "°C",
        validity.soil_temperature_c !== false,
        { targetHint: tempHint },
      ),
    ];
  });
  const rows = rowParts.length
    ? rowParts.join("")
    : `<tr><td colspan="3" class="live-empty">Brak aktywnych donic w profilu.</td></tr>`;
  return `<div class="live-sensor-col live-sensor-col-pots">
    <div class="live-data-table-wrap">
      <table class="live-data-table" aria-label="Donice">
        <colgroup>
          <col class="sensor-col" />
          <col class="reading-col" />
          <col class="target-col" />
        </colgroup>
        <thead>
          <tr>
            <th scope="col" class="sensor-col live-table-group-head">Donice</th>
            <th scope="col" class="num">Odczyt</th>
            <th scope="col" class="num">Cel</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </div>
  </div>`;
}

function renderLiveSensorGroupBlock(group, decision) {
  const rows = group.metrics.map(metric =>
    renderLiveMetricRow(metric, decision)
  ).join("");
  return `<div class="live-sensor-block">
    <div class="live-data-table-wrap">
      <table class="live-data-table" aria-label="${group.title}">
        <colgroup>
          <col class="sensor-col" />
          <col class="reading-col" />
          <col class="target-col" />
        </colgroup>
        <thead>
          <tr>
            <th scope="col" class="sensor-col live-table-group-head">${group.title}</th>
            <th scope="col" class="num">Odczyt</th>
            <th scope="col" class="num">Cel</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </div>
  </div>`;
}

function renderLiveClimateColumn(decision) {
  const blocks = LIVE_SENSOR_GROUPS.map(group =>
    renderLiveSensorGroupBlock(group, decision)
  ).join("");
  return `<div class="live-sensor-col live-sensor-col-climate" aria-label="Klimat">${blocks}</div>`;
}

function renderLiveMetricsTable(decision) {
  const climate = renderLiveClimateColumn(decision);
  const pots = renderLivePotGroupTable(decision);
  return `<div class="live-sensors-split" aria-label="Czujniki i cele">${climate}${pots}</div>`;
}
function formatOutputPct(value) {
  const n = Number(value) || 0;
  return Math.min(100, Math.max(0, Math.round(n * 100)));
}
function isActuatorAvailable(name) {
  const path = ACTUATOR_AVAILABILITY_PATHS[name];
  return path ? Boolean(getNested(scenario, path)) : true;
}
function actuatorAvailabilityFromSnapshot(actuators, name) {
  const entry = actuators?.[name];
  if (entry && typeof entry.available === "boolean") return entry.available;
  return undefined;
}

function isUnavailableFromDecisionReason(decision, name) {
  const mask = decision?.diagnostics?.output_reason_masks?.[name];
  if (typeof mask !== "number") return undefined;
  return (mask & SAFETY_REASON_ACTUATOR_UNAVAILABLE) !== 0;
}

/** Wyjścia Na żywo — stan z płytki (decyzja / status), nie lokalny formularz. */
function resolveActuatorAvailability(name, decision) {
  const fromDecision = actuatorAvailabilityFromSnapshot(decision?.actuators, name);
  if (fromDecision !== undefined) return fromDecision;
  const fromReason = isUnavailableFromDecisionReason(decision, name);
  if (fromReason === true) return false;
  const fromDevice = actuatorAvailabilityFromSnapshot(
    lastState?.last_status?.scenario?.actuators,
    name,
  );
  if (fromDevice !== undefined) return fromDevice;
  if (lastState?.connected) return true;
  return isActuatorAvailable(name);
}

function renderActuatorCard(label, rawVal, safeVal, { available = true } = {}) {
  const displayRaw = available ? rawVal : 0;
  const displaySafe = available ? safeVal : 0;
  const rPct = formatOutputPct(displayRaw);
  const sPct = formatOutputPct(displaySafe);
  const differs = available
    && Math.abs((Number(rawVal) || 0) - (Number(safeVal) || 0)) > 0.005;
  const statusBadge = available
    ? (differs
      ? '<span class="actuator-diff" title="Safety zmieniło wyjście tego aktuatora">≠</span>'
      : '<span class="actuator-same" title="Model i safety zgodne — bez korekty">bez zmian</span>')
    : '<span class="actuator-off" title="Aktuator wyłączony w scenariuszu">poza systemem</span>';
  return `<article class="actuator-card${differs ? " differs" : ""}${available ? "" : " unavailable"}">
    <div class="actuator-head">
      <span class="actuator-name">${label}</span>
      ${statusBadge}
    </div>
    <div class="output-line model">
      <span class="lane-label">Model</span>
      <div class="bar raw" title="Propozycja modelu: ${rPct}%"><span style="width:${rPct}%"></span></div>
      <span class="output-pct">${rPct}%</span>
    </div>
    <div class="output-line safety">
      <span class="lane-label">Safety</span>
      <div class="bar safe" title="Wysyłane na płytkę: ${sPct}%"><span style="width:${sPct}%"></span></div>
      <span class="output-pct">${sPct}%</span>
    </div>
  </article>`;
}

function panelOutputNames() {
  return panelSchema?.outputs || Object.keys(OUTPUT_LABELS);
}

function outputLabel(name) {
  return OUTPUT_LABELS[name] || name.replace(/_/g, " ");
}

function syncPreviousActuators(safe, decision = lastDecision) {
  if (!safe || typeof safe !== "object") return;
  if (!scenario.previous) scenario.previous = {};
  if (!Array.isArray(scenario.pots)) scenario.pots = [];
  for (const name of panelOutputNames()) {
    const value = resolveActuatorAvailability(name, decision) ? (Number(safe[name]) || 0) : 0;
    const zoneMatch = name.match(/^irrigation_pot_(\d+)$/);
    if (zoneMatch) {
      const zoneIndex = Number(zoneMatch[1]) - 1;
      if (!scenario.pots[zoneIndex]) scenario.pots[zoneIndex] = {};
      if (!scenario.pots[zoneIndex].previous) scenario.pots[zoneIndex].previous = {};
      scenario.pots[zoneIndex].previous.irrigation = value;
      continue;
    }
    scenario.previous[name] = value;
  }
  if (typeof syncPreviousDisplay === "function") {
    syncPreviousDisplay();
  }
  saveScenarioDraft();
}

function clearPreviousActuators() {
  const zero = Object.fromEntries(panelOutputNames().map(name => [name, 0]));
  syncPreviousActuators(zero);
}

function clearLivePreview(step = 0) {
  lastRenderedDecisionStep = null;
  lastRenderedPreviousStep = null;
  previousDisplaySnapshot = null;
  lastDecision = null;
  clearPreviousActuators();
  setLiveStepBadge(step);
  document.getElementById("decision-summary").innerHTML =
    `<p class="live-idle note flush">Symulacja zresetowana — uruchom <strong>Krok</strong> lub <strong>▶</strong></p>`;
  const outputsEl = document.getElementById("outputs-bars");
  outputsEl.className = "outputs-empty";
  outputsEl.innerHTML = "Uruchom <strong>Krok</strong>, aby zobaczyć wyjścia aktuatorów.";
  setLiveInferenceMeta(null);
}

function renderOutputs(decision, { force = false } = {}) {
  const step = decision?.step;
  if (!force && step !== undefined && step === lastRenderedDecisionStep) return;
  capturePreviousDisplay(decision);
  lastRenderedDecisionStep = step;
  lastDecision = decision;
  const names = panelOutputNames();
  const raw = decision.raw_output || {};
  const safe = decision.safe_output || {};
  const outputsEl = document.getElementById("outputs-bars");
  const visible = names.filter(name => resolveActuatorAvailability(name, decision));
  if (!visible.length) {
    outputsEl.className = "outputs-empty";
    outputsEl.innerHTML = "Wszystkie aktuary wyłączone w scenariuszu na płytce.";
  } else {
    outputsEl.className = "actuator-grid";
    outputsEl.innerHTML = visible.map(name =>
      renderActuatorCard(outputLabel(name), raw[name], safe[name], { available: true })
    ).join("");
  }

  setLiveStepBadge(decision.step ?? "?");
  if (lastState) updateTopStatusBadge(lastState);
  document.getElementById("decision-summary").innerHTML = renderLiveMetricsTable(decision);
  setLiveInferenceMeta(decision);
  syncPreviousActuators(safe, decision);
}
