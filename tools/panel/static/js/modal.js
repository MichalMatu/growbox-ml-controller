var modalRenderedKey = "";
var modalRenderedContent = "";

const modalViews = {
  scenario: { tab: "Scenariusz", title: "Scenariusz (payload)", get: () => JSON.stringify(collectScenario(), null, 2) },
  decision: { tab: "Ostatnia", title: "Ostatnia decyzja", get: () => lastDecision ? JSON.stringify(lastDecision, null, 2) : "Brak decyzji." },
  history: { tab: "Historia", title: "Historia serial", get: () => formatHistory(lastState) },
  device: { tab: "Startup", title: "Startup / status", get: () => formatDevice(lastState) },
  diagnostics: { tab: "Zasoby", title: "Zasoby", html: true },
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
  refreshModalContent({ force: true });
  document.getElementById("modal-close")?.focus();
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
  if (!tabs.dataset.ready) {
    tabs.innerHTML = Object.entries(modalViews).map(([key, meta]) =>
      `<button type="button" data-tab="${key}">${meta.tab}</button>`
    ).join("");
    tabs.dataset.ready = "1";
    tabs.querySelectorAll("[data-tab]").forEach(btn => {
      btn.onclick = () => {
        activeModal = btn.dataset.tab;
        renderModalTabs();
        refreshModalContent({ force: true });
      };
    });
  }
  tabs.querySelectorAll("[data-tab]").forEach(btn => {
    btn.classList.toggle("active", btn.dataset.tab === activeModal);
  });
}

function modalHasActiveSelection() {
  const backdrop = document.getElementById("modal-backdrop");
  if (!backdrop?.classList.contains("open")) return false;
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
  const cacheKey = `${activeModal}:${isHtml ? "html" : "text"}`;
  if (isHtml) {
    const html = formatDiagnosticsHtml(diagnosticsSnapshot);
    if (!force && cacheKey === modalRenderedKey && html === modalRenderedContent) return;
    panel.tabIndex = -1;
    panel.innerHTML = html;
    modalRenderedKey = cacheKey;
    modalRenderedContent = html;
  } else {
    const text = meta.get();
    if (!force && cacheKey === modalRenderedKey && text === modalRenderedContent) return;
    textarea.value = text;
    modalRenderedKey = cacheKey;
    modalRenderedContent = text;
  }
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
  const jsonBackdrop = document.getElementById("modal-backdrop");
  const helpOpen = helpBackdrop?.classList.contains("open");
  const jsonOpen = jsonBackdrop?.classList.contains("open");
  if (!helpOpen && !jsonOpen) return false;

  event.preventDefault();
  event.stopPropagation();
  event.stopImmediatePropagation();

  if (helpOpen) {
    selectWithinElement(document.getElementById("help-modal-content"));
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
  if (event.key !== "Escape") return;
  const helpBackdrop = document.getElementById("help-modal-backdrop");
  const jsonBackdrop = document.getElementById("modal-backdrop");
  if (helpBackdrop?.classList.contains("open")) {
    event.preventDefault();
    closeHelp();
  } else if (jsonBackdrop?.classList.contains("open")) {
    event.preventDefault();
    closeModal();
  }
}

document.addEventListener("keydown", handleModalKeydown, true);