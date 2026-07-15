function buildCompatibilityAlerts(state) {
  const alerts = [];
  if (!state?.connected || !panelSchema) return alerts;
  const startup = state.last_startup;
  if (!startup || typeof startup !== "object") return alerts;
  const deviceHash = startup.schema_hash;
  const panelHash = panelSchema.schema_hash;
  if (deviceHash && panelHash && deviceHash !== panelHash) {
    alerts.push({
      level: "danger",
      html: `Niezgodny kontrakt scenariusza: płytka <code>${escapeHtml(deviceHash)}</code>, panel <code>${escapeHtml(panelHash)}</code>. Zaktualizuj firmware lub panel przed pracą.`,
    });
  }
  if (startup.model_compatible === false) {
    const modelHash = startup.model_schema_hash || "?";
    alerts.push({
      level: "warn",
      html: `Model na płytce niezgodny z kontraktem (<code>${escapeHtml(modelHash)}</code>). Inferencja może być błędna.`,
    });
  }
  return alerts;
}

function updatePanelAlerts(state = lastState) {
  const el = document.getElementById("panel-alerts");
  if (!el) return;
  const parts = buildCompatibilityAlerts(state).map(alert =>
    `<div class="panel-alert panel-alert-${alert.level}">${alert.html}</div>`
  );
  const err = state?.last_firmware_error;
  if (state?.connected && err && typeof err === "object") {
    const code = escapeHtml(err.code || "?");
    const message = escapeHtml(err.message || "nieznany błąd");
    parts.push(
      `<div class="panel-alert panel-alert-danger"><strong>Błąd płytki:</strong> ${message} <span class="panel-alert-code">(${code})</span></div>`
    );
  }
  if (!parts.length) {
    el.hidden = true;
    el.innerHTML = "";
    return;
  }
  el.hidden = false;
  el.innerHTML = parts.join("");
}

async function refreshPorts() {
  const data = await api("/api/ports");
  const select = document.getElementById("port-select");
  const prev = select.value;
  select.innerHTML = "";
  const ports = (data.ports || []).slice().sort((a, b) => {
    const score = (p) => (p.device.includes("usbmodem") ? 0 : p.device.includes("usbserial") ? 1 : 2);
    return score(a) - score(b);
  });
  for (const p of ports) {
    const opt = document.createElement("option");
    opt.value = p.device;
    opt.textContent = p.device.replace("/dev/cu.", "");
    select.appendChild(opt);
  }
  const preferred = ports.find(p => p.device.includes("usbmodem"));
  if (prev && ports.some(p => p.device === prev)) select.value = prev;
  else if (preferred) select.value = preferred.device;
}

async function refreshState(options = {}) {
  try {
    lastState = await api("/api/state");
  } catch (err) {
    setLiveStepBadge(null);
    document.getElementById("decision-summary").textContent = "Błąd API: " + err.message;
    return;
  }
      updateToolbarState(lastState);
  updatePanelAlerts(lastState);
  if (lastState?.connected && lastState.last_diagnostics) {
    diagnosticsSnapshot = {
      connected: lastState.connected,
      port: lastState.port,
      device: lastState.last_diagnostics,
      startup: lastState.last_startup,
    };
  }
  if (lastState.last_error) {
    const errBtn = lastState.connected ? toolbarBtn("disconnect") : toolbarBtn("connect");
    if (errBtn) {
      errBtn.classList.add("state-error");
      setTimeout(() => errBtn.classList.remove("state-error"), 1600);
    }
  }
  if (lastState.last_decision) {
    renderOutputs(lastState.last_decision);
  } else if (lastState.last_status?.step !== undefined) {
    clearLivePreview(lastState.last_status.step);
  }
  if (document.getElementById("modal-backdrop").classList.contains("open")) {
    refreshModalContent();
  }
}

function tryApplyScenarioFromDevice(state, { force = false } = {}) {
  const snap = state?.last_status?.scenario;
  if (!state?.connected || !snap || typeof snap !== "object") return false;
  if (!force && deviceScenarioSynced) return false;
  scenario = sanitizeScenarioNumeric(deepMergeScenario(panelSchema.default_scenario, {
    seed: state.last_status.seed ?? panelSchema.default_scenario.seed,
    sensors: snap.sensors,
    validity: snap.validity,
    environment: snap.environment,
    cultivation: snap.cultivation,
    actuators: snap.actuators,
    targets: snap.targets,
    safety: snap.safety,
    previous: snap.previous,
  }));
  renderForm();
  renderPreviousLive();
  saveScenarioDraft();
  deviceScenarioSynced = true;
  updateScenarioSyncBadge();
  return true;
}

async function waitForDeviceStartup(maxAttempts = 20) {
  if (!lastState?.connected) return false;
  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    if (lastState?.last_startup?.schema_hash) return true;
    await new Promise(resolve => setTimeout(resolve, 100));
    await refreshState();
  }
  return Boolean(lastState?.last_startup);
}

async function requestDeviceStatus(maxAttempts = 10) {
  if (!lastState?.connected) return false;
  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    await api("/api/command", { method: "POST", body: '{"command":"status"}' });
    await new Promise(resolve => setTimeout(resolve, 140));
    await refreshState();
    if (hasDeviceStatus(lastState)) return true;
  }
  return hasDeviceStatus(lastState);
}

function hasDeviceScenario(state) {
  return Boolean(state?.last_status?.scenario?.actuators);
}

async function requestDeviceScenario() {
  if (!lastState?.connected) return false;
  const ok = await requestDeviceStatus();
  updateToolbarState(lastState);
  if (!ok) return false;
  for (let attempt = 0; attempt < 10; attempt++) {
    await api("/api/command", { method: "POST", body: '{"command":"get_scenario"}' });
    await new Promise(resolve => setTimeout(resolve, 140));
    await refreshState();
    if (hasDeviceScenario(lastState)) {
      return tryApplyScenarioFromDevice(lastState, { force: true });
    }
  }
  return tryApplyScenarioFromDevice(lastState, { force: true });
}
