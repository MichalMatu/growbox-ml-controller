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
  if (!el) return;
  if (step === null || step === undefined) {
    el.hidden = true;
    return;
  }
  el.hidden = false;
  el.textContent = `Krok ${step}`;
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

function renderLiveMetricRow(metric, sensors, targets, validity) {
  const valueText = formatLiveSensorValue(sensors[metric.key], metric.decimals);
  const valid = validity[metric.key] !== false;
  const targetText = metric.targetKey
    ? formatLiveTargetValue(targets[metric.targetKey], metric.decimals, metric.unit)
    : `<span class="live-no-target" title="${liveNoTargetHint(metric)}">—</span>`;
  const invalidMark = valid ? "" : '<span class="live-invalid" title="Czujnik nieważny">⊘</span>';
  const envClass = metric.targetKey ? "" : " env-row";
  const invalidClass = valid ? "" : " invalid";
  return `<tr class="${envClass}${invalidClass}">
    <th scope="row">${shortLabel(metric.key)}${invalidMark}</th>
    <td class="num"><strong>${valueText}${metric.unit}</strong></td>
    <td class="num">${targetText}</td>
  </tr>`;
}

function renderLiveSensorGroupTable(group, sensors, targets, validity) {
  const rows = group.metrics.map(metric =>
    renderLiveMetricRow(metric, sensors, targets, validity)
  ).join("");
  return `<div class="live-sensor-col">
    <div class="live-sensor-col-head">${group.title}</div>
    <div class="live-data-table-wrap">
      <table class="live-data-table" aria-label="${group.title}">
        <colgroup>
          <col class="sensor-col" />
          <col class="reading-col" />
          <col class="target-col" />
        </colgroup>
        <thead>
          <tr>
            <th scope="col" class="sensor-col"></th>
            <th scope="col" class="num">Odczyt</th>
            <th scope="col" class="num">Cel</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </div>
  </div>`;
}

function renderLiveMetricsTable(decision) {
  const sensors = decision?.sensors || {};
  const targets = decision?.targets || {};
  const validity = decision?.validity || {};
  const cols = LIVE_SENSOR_GROUPS.map(group =>
    renderLiveSensorGroupTable(group, sensors, targets, validity)
  ).join("");
  return `<div class="live-sensors-split" aria-label="Czujniki i cele">${cols}</div>`;
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

const ACTUATOR_NAMES = ["heater", "fan", "humidifier", "irrigation"];
const PREVIOUS_LABELS = {
  heater: "Grzałka",
  fan: "Fan",
  humidifier: "Nawilż.",
  irrigation: "Pompa",
};

function renderPreviousLive(decision = lastDecision) {
  const el = document.getElementById("previous-live");
  if (!el) return;
  const prev = scenario.previous || { heater: 0, fan: 0, humidifier: 0, irrigation: 0 };
  const visible = ACTUATOR_NAMES.filter(name => resolveActuatorAvailability(name, decision));
  if (!visible.length) {
    el.innerHTML = '<span class="previous-live-empty">Brak aktywnych aktuatorów w scenariuszu</span>';
    return;
  }
  el.innerHTML = visible.map(name => {
    const pct = formatOutputPct(prev[name]);
    return `<div class="previous-live-item">
      <span class="previous-live-label">${PREVIOUS_LABELS[name]}</span>
      <span class="previous-live-pct">${pct}%</span>
    </div>`;
  }).join("");
}

function syncPreviousActuators(safe, decision = lastDecision) {
  if (!safe || typeof safe !== "object") return;
  if (!scenario.previous) scenario.previous = {};
  for (const name of ACTUATOR_NAMES) {
    scenario.previous[name] = resolveActuatorAvailability(name, decision)
      ? (Number(safe[name]) || 0)
      : 0;
  }
  renderPreviousLive(decision);
  saveScenarioDraft();
}

function clearPreviousActuators() {
  syncPreviousActuators({ heater: 0, fan: 0, humidifier: 0, irrigation: 0 });
}

function clearLivePreview(step = 0) {
  lastRenderedDecisionStep = null;
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
  lastRenderedDecisionStep = step;
  lastDecision = decision;
  const names = ["heater", "fan", "humidifier", "irrigation"];
  const labels = { heater: "Grzałka", fan: "Fan", humidifier: "Nawilżacz", irrigation: "Pompa" };
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
      renderActuatorCard(labels[name], raw[name], safe[name], { available: true })
    ).join("");
  }

  setLiveStepBadge(decision.step ?? "?");
  if (lastState) updateTopStatusBadge(lastState);
  document.getElementById("decision-summary").innerHTML = renderLiveMetricsTable(decision);
  setLiveInferenceMeta(decision);
  syncPreviousActuators(safe, decision);
}
