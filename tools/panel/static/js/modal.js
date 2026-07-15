const modalViews = {
  scenario: { title: "Scenariusz (payload)", get: () => JSON.stringify(collectScenario(), null, 2) },
  decision: { title: "Ostatnia decyzja", get: () => lastDecision ? JSON.stringify(lastDecision, null, 2) : "Brak decyzji." },
  history: { title: "Historia serial", get: () => formatHistory(lastState) },
  device: { title: "Startup / status", get: () => formatDevice(lastState) },
  diagnostics: { title: "Zasoby (heap / PSRAM)", html: true },
};

function formatHistory(state) {
  if (!state?.history?.length) return "Brak historii.";
  return state.history.slice(0, 20).map(h =>
    `${h.direction}: ${JSON.stringify(h.payload)}`
  ).join("\n\n");
}

function formatDevice(state) {
  if (!state) return "Brak danych.";
  const parts = [];
  if (state.last_startup) parts.push("=== startup ===\n" + JSON.stringify(state.last_startup, null, 2));
  if (state.last_status) parts.push("=== status ===\n" + JSON.stringify(state.last_status, null, 2));
  if (state.last_firmware_error) parts.push("=== error ===\n" + JSON.stringify(state.last_firmware_error, null, 2));
  return parts.length ? parts.join("\n\n") : "Brak startup/status.";
}

function openModal(view) {
  activeModal = view;
  const backdrop = document.getElementById("modal-backdrop");
  modalReturnFocus = document.activeElement;
  backdrop.classList.add("open");
  backdrop.removeAttribute("inert");
  backdrop.setAttribute("aria-hidden", "false");
  updateModalLock();
  renderModalTabs();
  refreshModalContent();
  document.getElementById("modal-close").focus();
}

function closeModal() {
  const backdrop = document.getElementById("modal-backdrop");
  const returnTo = modalReturnFocus;
  modalReturnFocus = null;
  const focused = document.activeElement;
  if (returnTo && typeof returnTo.focus === "function") {
    returnTo.focus();
  } else if (focused && backdrop.contains(focused) && typeof focused.blur === "function") {
    focused.blur();
  }
  backdrop.classList.remove("open");
  backdrop.setAttribute("inert", "");
  backdrop.setAttribute("aria-hidden", "true");
  updateModalLock();
}

function renderModalTabs() {
  const tabs = document.getElementById("modal-tabs");
  tabs.innerHTML = Object.entries(modalViews).map(([key, meta]) =>
    `<button type="button" data-tab="${key}" class="${key === activeModal ? "active" : ""}">${meta.title.split(" ")[0]}</button>`
  ).join("");
  tabs.querySelectorAll("[data-tab]").forEach(btn => {
    btn.onclick = () => { activeModal = btn.dataset.tab; renderModalTabs(); refreshModalContent(); };
  });
}

function refreshModalContent() {
  const meta = modalViews[activeModal];
  const textarea = document.getElementById("modal-content");
  const panel = document.getElementById("modal-content-panel");
  const copyBtn = document.getElementById("modal-copy");
  const refreshBtn = document.getElementById("modal-refresh");
  document.getElementById("modal-title").textContent = meta.title;
  const isHtml = Boolean(meta.html);
  textarea.hidden = isHtml;
  panel.hidden = !isHtml;
  copyBtn.hidden = isHtml;
  if (refreshBtn) refreshBtn.hidden = !isHtml;
  if (isHtml) {
    panel.innerHTML = formatDiagnosticsHtml(diagnosticsSnapshot);
  } else {
    textarea.value = meta.get();
  }
}