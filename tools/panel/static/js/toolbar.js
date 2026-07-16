function toolbarBtn(ui) {
  return document.querySelector(`[data-panel-toolbar] [data-ui="${ui}"], .top-bar [data-ui="${ui}"]`);
}

function clearToolbarStates() {
  document.querySelectorAll("[data-panel-toolbar] .badge-btn[data-ui], .top-bar .badge-btn[data-ui]").forEach(btn => {
    btn.classList.remove(...TOOLBAR_STATE_CLASSES);
  });
}

function setToolbarBtn(ui, stateClass) {
  const btn = toolbarBtn(ui);
  if (btn) btn.classList.add(stateClass);
}

function setBtnHint(ui, title) {
  const btn = toolbarBtn(ui);
  if (btn) btn.title = title;
}

function resolvePaused(state) {
  if (state?.last_status?.paused !== undefined) {
    return Boolean(state.last_status.paused);
  }
  if (state?.connected && state?.last_decision) {
    return false;
  }
  return true;
}

function hasDeviceStatus(state) {
  return state?.last_status?.paused !== undefined && Boolean(state?.last_status?.mode);
}

function resolveMode(state) {
  if (state?.last_status?.mode) return state.last_status.mode;
  return "closed_loop";
}

function resolveDisplayStep(state) {
  const decisionStep = state?.last_decision?.step;
  if (decisionStep !== undefined && decisionStep !== null) {
    return decisionStep;
  }
  if (state?.last_status?.step !== undefined) {
    return state.last_status.step;
  }
  return 0;
}
function updateTopStatusBadge(state = lastState) {
  const el = document.getElementById("top-status-badge");
  if (!el) return;
  if (!state?.connected) {
    el.hidden = false;
    el.textContent = "podłącz płytkę";
    el.title = "Wybierz port USB i kliknij Połącz";
    el.classList.remove("live");
    el.classList.add("disconnected");
    return;
  }
  const step = resolveDisplayStep(state);
  const mode = resolveMode(state);
  const paused = resolvePaused(state);
  const modeLabel = mode === "replay" ? "replay" : "loop";
  const runLabel = paused ? "pauza" : "działa";
  el.hidden = false;
  el.classList.remove("disconnected");
  el.classList.add("live");
  el.textContent = `krok ${step} · ${modeLabel} · ${runLabel}`;
  el.title = `Połączono — krok ${step}, tryb ${modeLabel}, ${paused ? "w pauzie" : "symulacja działa"}`;
}

function updateToolbarState(state = lastState) {
  clearToolbarStates();
  updateTopStatusBadge(state);
  updateScenarioSyncBadge();
  const connected = Boolean(state?.connected);
  const mode = resolveMode(state);
  const paused = resolvePaused(state);

  if (connected) {
    setToolbarBtn("disconnect", "state-on-danger");
    setToolbarBtn("connect", "state-off");
    setBtnHint("disconnect", "Rozłącz port USB");
    setBtnHint("connect", "Połączono");

    setToolbarBtn("playpause", paused ? "state-play" : "state-stop");
    updatePlayPauseBtn(paused, true);

    if (mode === "replay") {
      setToolbarBtn("mode-replay", "state-on-accent");
      setBtnHint("mode-replay", "Tryb: REPLAY — ręcznie: Wyślij → ▶ → Krok");
      setBtnHint("mode-loop", "Przełącz na LOOP — automatyczne krokowanie");
    } else {
      setToolbarBtn("mode-loop", "state-on-accent");
      setBtnHint("mode-loop", "Tryb: LOOP — ▶ krokowanie automatyczne");
      setBtnHint("mode-replay", "Przełącz na REPLAY — tylko ręczny Krok");
      setBtnHint("playpause", paused ? "Start — wznów (auto Loop)" : "Stop — zatrzymaj sterowanie");
    }

    setBtnHint("reset", "Reset symulacji na urządzeniu");
    setBtnHint("status", "Odśwież status i scenariusz z płytki (nadpisuje formularz)");
    setBtnHint("load", "Wyślij cały scenariusz z formularza na płytkę");
    setBtnHint("step", "Jeden krok inferencji (najpierw Wyślij + ▶ w replay)");
    setBtnHint("defaults", "Przywróć domyślny scenariusz (czyści zapis w przeglądarce)");
  } else {
    setToolbarBtn("connect", "state-on-accent");
    setToolbarBtn("disconnect", "state-off");
    setBtnHint("connect", "Połącz z portem USB (usbmodem)");
    setBtnHint("disconnect", "Brak połączenia");
    updatePlayPauseBtn(true, false);
    document.querySelectorAll("[data-panel-toolbar] .badge-btn[data-ui]").forEach(btn => {
      btn.classList.add("state-disabled");
      btn.title = "Najpierw Połącz urządzenie";
    });
  }
}
async function postTransportCommand(command) {
  await api("/api/command", {
    method: "POST",
    body: JSON.stringify(command),
  });
  applyCommandOptimistic(JSON.stringify(command));
}

async function ensureClosedLoopMode() {
  if (resolveMode(lastState) !== "closed_loop") {
    await postTransportCommand({ command: "mode", value: "closed_loop" });
  }
}

/** ▶ — always run automatic loop stepping (Replay + ▶ alone does not infer). */
async function startSimulationTransport() {
  await ensureClosedLoopMode();
  await postTransportCommand({ command: "resume" });
}

function applyCommandOptimistic(cmdJson) {
  try {
    const cmd = JSON.parse(cmdJson);
    if (cmd.command === "pause" || cmd.command === "resume" || cmd.command === "mode") {
      patchLocalTransportStatus(cmd);
    } else if (cmd.command === "reset") {
      patchLocalTransportStatus(cmd);
      clearLivePreview(0);
    } else if (cmd.command === "load_scenario") {
      patchLocalTransportStatus(cmd);
      clearLivePreview(0);
    }
  } catch (_) { /* ignore */ }
  updateToolbarState(lastState);
}
