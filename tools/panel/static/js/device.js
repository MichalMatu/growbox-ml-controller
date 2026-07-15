function isGrowboxHandshake(state) {
  const startup = state?.last_startup;
  if (startup?.type === "startup" && startup.framework === "esp-idf" && startup.schema_hash) {
    return true;
  }
  const status = state?.last_status;
  return Boolean(
    status?.type === "status"
    && status.schema_hash
    && (status.mode === "replay" || status.mode === "closed_loop")
  );
}

function buildCompatibilityAlerts(state) {
  const alerts = [];
  if (!state?.connected || !panelSchema) return alerts;
  const startup = state.last_startup;
  const status = state.last_status;
  const deviceHash = (startup?.type === "startup" ? startup.schema_hash : null)
    || (status?.type === "status" ? status.schema_hash : null);
  const panelHash = panelSchema.schema_hash;
  if (deviceHash && panelHash && deviceHash !== panelHash) {
    alerts.push({
      level: "danger",
      short: "Kontrakt ≠",
      detail: {
        title: "Niezgodny kontrakt scenariusza",
        html: `<p>Płytka <code>${escapeHtml(deviceHash)}</code>, panel <code>${escapeHtml(panelHash)}</code>.</p>
          <h4>Co zrobić?</h4>
          <ul><li>Zaktualizuj firmware lub panel do tej samej wersji kontraktu</li></ul>`,
      },
    });
  }
  if (startup?.type === "startup" && startup.model_compatible === false) {
    const modelHash = startup.model_schema_hash || "?";
    alerts.push({
      level: "warn",
      short: "Model ≠",
      detail: {
        title: "Model niezgodny z kontraktem",
        html: `<p>Hash modelu na płytce: <code>${escapeHtml(modelHash)}</code>.</p>
          <h4>Co zrobić?</h4>
          <ul><li>Wgraj model zgodny z aktualnym kontraktem przed inferencją</li></ul>`,
      },
    });
  }
  return alerts;
}

function shortenPortDescription(description) {
  if (!description || description === "n/a") return "";
  const lower = description.toLowerCase();
  if (lower.includes("jtag")) return "JTAG";
  if (lower.includes("espressif")) return "ESP";
  if (lower.includes("serial")) return "USB";
  if (description.length > 10) return `${description.slice(0, 8)}…`;
  return description;
}

function formatPortOption(port) {
  const name = port.device.replace("/dev/cu.", "");
  if (!port.recommended) return `${name} ⚠`;
  const hint = shortenPortDescription(port.description);
  return hint ? `${name} · ${hint}` : name;
}

function setConnectFailure(message, detail) {
  connectFailureMessage = message || null;
  connectFailureDetail = detail || (message ? resolveConnectError(message) : null);
  renderTopBarMessages(lastState);
}

function renderTopBarMessages(state = lastState) {
  const el = document.getElementById("top-messages");
  if (!el) return;
  const items = [];
  if (connectFailureMessage) {
    items.push({
      level: "danger",
      short: connectFailureMessage,
      detail: connectFailureDetail,
    });
  }
  for (const alert of buildCompatibilityAlerts(state)) {
    items.push({
      level: alert.level,
      short: alert.short,
      detail: alert.detail,
    });
  }
  const fwErr = state?.last_firmware_error;
  if (state?.connected && fwErr && typeof fwErr === "object") {
    const code = fwErr.code || "?";
    const message = fwErr.message || "nieznany błąd";
    items.push({
      level: "danger",
      short: `Błąd ${code}`,
      detail: {
        title: "Błąd płytki",
        body: message,
        instructions: "<ul><li>Sprawdź log serial i spróbuj zresetować płytkę</li></ul>",
      },
    });
  }
  topBarMessageItems = items;
  if (!items.length) {
    el.hidden = true;
    el.innerHTML = "";
    return;
  }
  el.hidden = false;
  el.innerHTML = items.map((item, index) =>
    `<button type="button" class="top-message top-message-${item.level}" data-msg-idx="${index}" title="Szczegóły">${escapeHtml(item.short)}</button>`
  ).join("");
}

function getSelectedPort() {
  return portCatalog.find(port => port.device === selectedPortDevice) || null;
}

function getSelectedPortDevice() {
  return selectedPortDevice;
}

function isSelectedPortUnlikely() {
  const port = getSelectedPort();
  return Boolean(port && !port.recommended);
}

function closePortPickerMenu() {
  const menu = document.getElementById("port-picker-menu");
  const trigger = document.getElementById("port-picker-trigger");
  if (!menu || menu.hidden) return;
  menu.hidden = true;
  trigger?.setAttribute("aria-expanded", "false");
}

function renderPortPicker() {
  const label = document.getElementById("port-picker-label");
  const menu = document.getElementById("port-picker-menu");
  const picker = document.getElementById("port-picker");
  const selected = getSelectedPort();
  if (!label || !menu) return;

  if (!portCatalog.length) {
    label.textContent = "brak portu";
    menu.innerHTML = "";
    menu.hidden = true;
    selectedPortDevice = "";
    picker?.classList.remove("port-picker-warn");
    return;
  }

  label.textContent = selected ? formatPortOption(selected) : "wybierz port";
  picker?.classList.toggle("port-picker-warn", Boolean(selected && !selected.recommended));
  menu.innerHTML = portCatalog.map(port => {
    const active = port.device === selectedPortDevice;
    const unlikely = !port.recommended ? " port-unlikely" : "";
    return `<button type="button" class="port-picker-item${active ? " active" : ""}${unlikely}" role="option" aria-selected="${active}" data-port="${escapeHtml(port.device)}" title="${escapeHtml(port.recommended ? "ESP32-S3 (USB)" : "Prawdopodobnie nie ESP32")}">
      <span class="port-picker-check" aria-hidden="true">${active ? "✓" : ""}</span>
      <span class="port-picker-item-label">${escapeHtml(formatPortOption(port))}</span>
    </button>`;
  }).join("");
}

function selectPortDevice(device) {
  if (!portCatalog.some(port => port.device === device)) return;
  selectedPortDevice = device;
  renderPortPicker();
  closePortPickerMenu();
}

function togglePortPickerMenu() {
  const menu = document.getElementById("port-picker-menu");
  const trigger = document.getElementById("port-picker-trigger");
  if (!menu || !portCatalog.length) return;
  const open = menu.hidden;
  menu.hidden = !open;
  trigger?.setAttribute("aria-expanded", String(open));
  if (open) menu.querySelector(".port-picker-item.active")?.focus();
}

function initPortPicker() {
  document.getElementById("port-picker-trigger")?.addEventListener("click", (event) => {
    event.stopPropagation();
    togglePortPickerMenu();
  });
  document.getElementById("port-picker-menu")?.addEventListener("click", (event) => {
    const item = event.target.closest("[data-port]");
    if (!item) return;
    selectPortDevice(item.dataset.port);
  });
  document.addEventListener("click", (event) => {
    if (!event.target.closest("#port-picker")) closePortPickerMenu();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closePortPickerMenu();
  });
}

async function refreshPorts() {
  const data = await api("/api/ports");
  const ports = data.ports || [];
  const prev = selectedPortDevice;
  portCatalog = ports;
  const preferred = ports.find(port => port.recommended);
  if (prev && ports.some(port => port.device === prev)) selectedPortDevice = prev;
  else selectedPortDevice = preferred?.device || ports[0]?.device || "";
  renderPortPicker();
}

initPortPicker();

async function refreshState(options = {}) {
  try {
    lastState = await api("/api/state");
  } catch (err) {
    setLiveStepBadge(null);
    document.getElementById("decision-summary").textContent = "Błąd API: " + err.message;
    return;
  }
      updateToolbarState(lastState);
  renderTopBarMessages(lastState);
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
    zones: snap.zones,
    pseudo: snap.pseudo,
    environment: snap.environment,
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

async function waitForDeviceHandshake(maxAttempts = 20) {
  if (!lastState?.connected) return false;
  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    if (isGrowboxHandshake(lastState)) return true;
    await new Promise(resolve => setTimeout(resolve, 100));
    await refreshState();
  }
  return isGrowboxHandshake(lastState);
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
