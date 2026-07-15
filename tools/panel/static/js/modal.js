var modalRenderedKey = "";
var modalRenderedContent = "";

const panelModalViews = {
  scenario: {
    tab: "Scenariusz",
    title: "Scenariusz",
    type: "json",
    get: () => JSON.stringify(collectScenario(), null, 2),
  },
  decision: {
    tab: "Decyzja",
    title: "Decyzja",
    type: "json",
    get: () => (lastDecision ? JSON.stringify(lastDecision, null, 2) : "Brak decyzji."),
  },
  history: {
    tab: "Historia",
    title: "Historia",
    type: "json",
    get: () => formatHistory(lastState),
  },
  device: {
    tab: "Startup / status",
    title: "Startup / status",
    type: "json",
    get: () => formatDevice(lastState),
  },
  diagnostics: {
    tab: "Zasoby",
    title: "Zasoby",
    type: "html",
  },
  growbox: {
    tab: "Growbox",
    title: "Parametry growboxa",
    type: "setup",
    help: "environment",
    pane: "growbox",
  },
  safety: {
    tab: "Safety",
    title: "Limity safety",
    type: "setup",
    help: "safety",
    pane: "safety",
  },
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
  const key = panelModalViews[view] ? view : "scenario";
  activeModal = key;
  const backdrop = document.getElementById("modal-backdrop");
  modalReturnFocus = document.activeElement;
  backdrop.classList.add("open");
  backdrop.removeAttribute("inert");
  backdrop.setAttribute("aria-hidden", "false");
  updateModalLock();
  renderPanelModalTabs();
  refreshModalContent({ force: true });
  document.getElementById("modal-close")?.focus();
}

function closeModal() {
  const backdrop = document.getElementById("modal-backdrop");
  const returnTo = modalReturnFocus;
  modalReturnFocus = null;
  restoreFocusFromDialog(backdrop, returnTo, "#btn-json-scenario");
  backdrop.classList.remove("open");
  backdrop.setAttribute("inert", "");
  backdrop.setAttribute("aria-hidden", "true");
  updateModalLock();
}

function renderPanelModalTabs() {
  const tabs = document.getElementById("modal-tabs");
  if (!tabs.dataset.ready) {
    tabs.innerHTML = Object.entries(panelModalViews).map(([key, meta]) =>
      `<button type="button" role="tab" data-tab="${key}">${meta.tab}</button>`
    ).join("");
    tabs.dataset.ready = "1";
    tabs.querySelectorAll("[data-tab]").forEach(btn => {
      btn.onclick = () => {
        activeModal = btn.dataset.tab;
        renderPanelModalTabs();
        refreshModalContent({ force: true });
      };
    });
  }
  tabs.querySelectorAll("[data-tab]").forEach(btn => {
    const active = btn.dataset.tab === activeModal;
    btn.classList.toggle("active", active);
    btn.setAttribute("aria-selected", active ? "true" : "false");
  });
}

function updatePanelModalChrome(meta) {
  const textarea = document.getElementById("modal-content");
  const panel = document.getElementById("modal-content-panel");
  const helpBtn = document.getElementById("modal-help");
  const copyBtn = document.getElementById("modal-copy");
  const refreshBtn = document.getElementById("modal-refresh");
  const isSetup = meta.type === "setup";
  const isHtml = meta.type === "html";
  const isJson = meta.type === "json";

  document.getElementById("modal-title").textContent = meta.title;
  textarea.hidden = !isJson;
  panel.hidden = !isHtml;
  document.querySelectorAll(".setup-pane").forEach((pane) => {
    const active = isSetup && pane.id === `setup-pane-${meta.pane}`;
    pane.classList.toggle("active", active);
    pane.hidden = !active;
  });
  if (helpBtn) {
    helpBtn.hidden = !isSetup;
    if (isSetup) {
      helpBtn.dataset.help = meta.help;
      helpBtn.setAttribute("aria-label", `Pomoc — ${meta.title}`);
    }
  }
  if (copyBtn) copyBtn.hidden = !isJson;
  if (refreshBtn) refreshBtn.hidden = !isHtml;
}

function modalHasActiveSelection() {
  const backdrop = document.getElementById("modal-backdrop");
  if (!backdrop?.classList.contains("open")) return false;
  const meta = panelModalViews[activeModal];
  if (meta?.type === "setup") return false;
  const textarea = document.getElementById("modal-content");
  if (textarea && !textarea.hidden && textarea.selectionEnd > textarea.selectionStart) {
    return true;
  }
  const panel = document.getElementById("modal-content-panel");
  const selection = window.getSelection?.();
  if (selection && !selection.isCollapsed && panel && !panel.hidden) {
    const node = selection.anchorNode;
    if (node && panel.contains(node)) return true;
  }
  return false;
}

function refreshModalContent({ force = false } = {}) {
  if (!force && modalHasActiveSelection()) return;
  const meta = panelModalViews[activeModal];
  if (!meta) return;
  updatePanelModalChrome(meta);
  if (meta.type === "json") {
    refreshJsonModalContent({ force });
  } else if (meta.type === "html") {
    refreshHtmlModalContent({ force });
  }
}

function refreshJsonModalContent({ force = false } = {}) {
  const meta = panelModalViews[activeModal];
  const textarea = document.getElementById("modal-content");
  const cacheKey = `${activeModal}:text`;
  const text = meta.get();
  if (!force && cacheKey === modalRenderedKey && text === modalRenderedContent) return;
  textarea.value = text;
  modalRenderedKey = cacheKey;
  modalRenderedContent = text;
}

function refreshHtmlModalContent({ force = false } = {}) {
  const panel = document.getElementById("modal-content-panel");
  const cacheKey = `${activeModal}:html`;
  const html = formatDiagnosticsHtml(diagnosticsSnapshot);
  if (!force && cacheKey === modalRenderedKey && html === modalRenderedContent) return;
  panel.tabIndex = -1;
  panel.innerHTML = html;
  modalRenderedKey = cacheKey;
  modalRenderedContent = html;
}

function isSelectAllShortcut(event) {
  if (!event.metaKey && !event.ctrlKey) return false;
  const key = event.key?.toLowerCase();
  return key === "a" || event.code === "KeyA";
}

function selectWithinElement(root) {
  if (!root) return false;
  if (root.tagName === "TEXTAREA" || (root.tagName === "INPUT" && root.type !== "checkbox")) {
    root.focus({ preventScroll: true });
    root.select();
    return true;
  }
  root.focus?.({ preventScroll: true });
  const selection = window.getSelection?.();
  if (!selection) return false;
  const range = document.createRange();
  range.selectNodeContents(root);
  selection.removeAllRanges();
  selection.addRange(range);
  return true;
}

function handleModalSelectAll(event) {
  if (!isSelectAllShortcut(event)) return false;
  const helpBackdrop = document.getElementById("help-modal-backdrop");
  const noticeBackdrop = document.getElementById("notice-modal-backdrop");
  const panelBackdrop = document.getElementById("modal-backdrop");
  const helpOpen = helpBackdrop?.classList.contains("open");
  const noticeOpen = noticeBackdrop?.classList.contains("open");
  const panelOpen = panelBackdrop?.classList.contains("open");
  if (!helpOpen && !noticeOpen && !panelOpen) return false;

  event.preventDefault();
  event.stopPropagation();
  event.stopImmediatePropagation();

  if (helpOpen) {
    selectWithinElement(document.getElementById("help-modal-content"));
    return true;
  }
  if (noticeOpen) {
    selectWithinElement(document.getElementById("notice-modal-content"));
    return true;
  }

  const panel = document.getElementById("modal-content-panel");
  const textarea = document.getElementById("modal-content");
  if (panel && !panel.hidden) {
    selectWithinElement(panel);
  } else {
    selectWithinElement(textarea);
  }
  return true;
}

function handleModalKeydown(event) {
  if (handleModalSelectAll(event)) return;
  handleDialogKeydown(event);
  if (event.key !== "Escape") return;
  const helpBackdrop = document.getElementById("help-modal-backdrop");
  const panelBackdrop = document.getElementById("modal-backdrop");
  if (helpBackdrop?.classList.contains("open")) {
    event.preventDefault();
    closeHelp();
  } else if (panelBackdrop?.classList.contains("open")) {
    event.preventDefault();
    closeModal();
  }
}

document.addEventListener("keydown", handleModalKeydown, true);
