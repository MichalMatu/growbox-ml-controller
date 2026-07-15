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
