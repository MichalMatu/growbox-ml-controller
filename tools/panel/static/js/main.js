function bindFormInputRoot(root) {
  if (!root) return;
  root.addEventListener("change", (event) => {
    if (event.target?.id === "f-pseudo_lights_active") syncLightsActiveDisplay();
    collectScenario();
  });
  root.addEventListener("input", (event) => {
    if (event.target && event.target.type === "number") collectScenario();
  });
}

function bindFormSync() {
  bindFormInputRoot(document.getElementById("form-sections"));
  bindFormInputRoot(document.getElementById("setup-modal-body"));
  const toolbar = document.getElementById("panel-toolbar");
  const onSeedChange = (event) => {
    if (event.target?.id === "seed") collectScenario();
  };
  toolbar?.addEventListener("change", onSeedChange);
  toolbar?.addEventListener("input", onSeedChange);
}

async function init() {
  panelSchema = await api("/api/schema");
  await refreshPorts();
  await refreshState();
  if (lastState?.connected) {
    if (!await requestDeviceScenario()) {
      scenario = sanitizeScenarioNumeric(loadScenarioDraft(panelSchema) || panelSchema.default_scenario);
    }
  } else {
    scenario = sanitizeScenarioNumeric(loadScenarioDraft(panelSchema) || panelSchema.default_scenario);
  }
  renderForm();
  bindFormSync();
  setInterval(() => refreshState(), 900);
  refreshState();
}
function bindToolbar() {
  document.addEventListener("click", async (event) => {
    const btn = event.target.closest("button");
    if (!btn) return;
    const scope = btn.closest("[data-panel-toolbar]") || btn.closest(".top-bar");
    if (!scope) return;

    if (btn.id === "btn-refresh-ports") {
      event.preventDefault();
      try { await runAction(refreshPorts, btn); } catch (_) { /* btn flash */ }
      return;
    }
    if (btn.id === "btn-connect") {
      event.preventDefault();
      closePortPickerMenu();
      const port = getSelectedPortDevice();
      if (!port) {
        setConnectFailure("Wybierz port", resolveConnectError("port must not be empty"));
        return;
      }
      if (isSelectedPortUnlikely()) {
        const portLabel = formatPortOption(getSelectedPort()).replace(/\s*⚠\s*$/, "").trim();
        const proceed = await openConfirm({
          title: "Nietypowy port",
          html: `<p>Port <code>${escapeHtml(portLabel)}</code> nie wygląda na ESP32-S3.</p>
            <p>Prawdopodobnie to Bluetooth lub inne urządzenie — połączenie się nie uda.</p>`,
          okLabel: "Połącz mimo to",
          cancelLabel: "Anuluj",
        });
        if (!proceed) return;
      }
      try {
        setConnectFailure(null);
        deviceScenarioSynced = false;
        lastRenderedDecisionStep = null;
        await runAction(() => api("/api/connect", {
          method: "POST",
          body: JSON.stringify({
            port,
            baud: 115200,
          }),
        }), btn);
        await refreshState();
        if (!await waitForDeviceHandshake()) {
          throw new Error(
            "Połączono z portem, ale płytka nie odpowiedziała jak growbox ML — sprawdź port lub zresetuj ESP32-S3"
          );
        }
        if (!await requestDeviceScenario()) {
          throw new Error(
            "Płytka nie zwróciła scenariusza — upewnij się, że to growbox ML na ESP32-S3"
          );
        }
        setConnectFailure(null);
        updateToolbarState(lastState);
        renderTopBarMessages(lastState);
      } catch (err) {
        const errInfo = resolveConnectError(err.message);
        setConnectFailure(errInfo.short, errInfo);
        await refreshState();
      }
      return;
    }
    if (btn.id === "btn-disconnect") {
      event.preventDefault();
      try {
        setConnectFailure(null);
        await runAction(() => api("/api/disconnect", { method: "POST", body: "{}" }), btn);
        lastRenderedDecisionStep = null;
        deviceScenarioSynced = false;
        await refreshState();
      } catch (_) { /* btn flash */ }
      return;
    }
    if (btn.dataset.cmd) {
      event.preventDefault();
      if (btn.classList.contains("state-disabled")) return;
      try {
        await runAction(() => api("/api/command", {
          method: "POST",
          body: btn.dataset.cmd,
        }), btn);
        const cmdBody = btn.dataset.cmd;
        applyCommandOptimistic(cmdBody);
        updateToolbarState(lastState);
        setTimeout(async () => {
          await refreshState();
          if (cmdBody.includes('"status"')) {
            tryApplyScenarioFromDevice(lastState, { force: true });
          }
        }, 280);
      } catch (_) { /* btn flash */ }
      return;
    }
    if (btn.id === "btn-defaults") {
      event.preventDefault();
      try {
        await runAction(async () => {
          const data = await api("/api/defaults", {
            method: "POST",
            body: JSON.stringify({
              seed: normalizeSeed(document.getElementById("seed").value),
            }),
          });
          scenario = sanitizeScenarioNumeric(data.scenario);
          if (!panelSchema) throw new Error("Schemat panelu niezaładowany — odśwież stronę");
          clearScenarioDraft();
          saveScenarioDraft();
          deviceScenarioSynced = false;
          renderForm();
        }, btn);
      } catch (_) { /* btn flash */ }
      return;
    }
    if (btn.id === "btn-load") {
      event.preventDefault();
      if (btn.classList.contains("state-disabled")) return;
      try {
        await runAction(async () => {
          const payload = collectScenario();
          const { seed, ...body } = payload;
          await api("/api/load_scenario", {
            method: "POST",
            body: JSON.stringify({ seed, scenario: body }),
          });
          patchLocalScenarioStatus(payload);
          patchLocalTransportStatus({ command: "load_scenario" });
          deviceScenarioSynced = true;
          updateScenarioSyncBadge();
          updatePlayPauseBtn(true, Boolean(lastState?.connected));
        }, btn);
        clearLivePreview(0);
        setTimeout(async () => {
          await refreshState();
          updateScenarioSyncBadge();
          updateToolbarState(lastState);
        }, 280);
      } catch (_) { /* btn flash */ }
      return;
    }
    if (btn.id === "btn-step") {
      event.preventDefault();
      if (btn.classList.contains("state-disabled")) return;
      try {
        await runAction(async () => {
          collectScenario();
          await api("/api/step", { method: "POST", body: "{}" });
        }, btn);
        setTimeout(refreshState, 300);
      } catch (_) { /* btn flash */ }
    }
  });
}
bindToolbar();
document.getElementById("btn-export").onclick = () => {
  const blob = new Blob([JSON.stringify(collectScenario(), null, 2)], { type: "application/json" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "scenario.json";
  a.click();
};
document.getElementById("btn-json-scenario").onclick = () => { collectScenario(); openModal("scenario"); };
document.getElementById("btn-json-decision").onclick = () => openModal("decision");
document.getElementById("btn-json-history").onclick = () => openModal("history");
document.getElementById("btn-json-device").onclick = () => openModal("device");
document.getElementById("btn-json-diagnostics").onclick = () => openDiagnosticsModal();
document.getElementById("modal-refresh").onclick = () => refreshDiagnosticsView(true);
document.getElementById("modal-close").onclick = closeModal;
document.getElementById("modal-backdrop").onclick = (e) => { if (e.target.id === "modal-backdrop") closeModal(); };
document.addEventListener("click", (e) => {
  const btn = e.target.closest("[data-help]");
  if (!btn) return;
  e.preventDefault();
  openHelp(btn.dataset.help);
});
document.getElementById("help-modal-close").onclick = closeHelp;
document.getElementById("help-modal-close-2").onclick = closeHelp;
document.getElementById("help-modal-backdrop").onclick = (e) => {
  if (e.target.id === "help-modal-backdrop") closeHelp();
};
document.getElementById("setup-modal-close").onclick = closeSetup;
document.getElementById("setup-modal-backdrop").onclick = (e) => {
  if (e.target.id === "setup-modal-backdrop") closeSetup();
};
document.getElementById("setup-modal-tabs")?.addEventListener("click", (e) => {
  const btn = e.target.closest("[data-setup-tab]");
  if (!btn) return;
  e.preventDefault();
  switchSetupTab(btn.dataset.setupTab);
});
document.addEventListener("click", (e) => {
  const btn = e.target.closest("[data-setup-open]");
  if (!btn) return;
  e.preventDefault();
  openSetup(btn.dataset.setupOpen);
});

document.getElementById("modal-copy").onclick = async () => {
  await navigator.clipboard.writeText(document.getElementById("modal-content").value);
};

if (location.protocol === "file:") {
  setLiveStepBadge(null);
  document.getElementById("decision-summary").textContent =
    "Otwórz panel przez serwer: http://127.0.0.1:8765 (make panel)";
}

updateToolbarState({ connected: false });

init().catch(err => {
  setLiveStepBadge(null);
  document.getElementById("decision-summary").textContent =
    "Błąd API: " + friendlyError(err.message);
});
