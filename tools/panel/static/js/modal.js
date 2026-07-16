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
    type: "html",
    panelClass: "diag-modal-body",
    getHtml: () => formatHistoryHtml(lastState),
  },
  device: {
    tab: "Status",
    title: "Startup / status",
    type: "json",
    get: () => formatDevice(lastState),
  },
  previous: {
    tab: "Poprzedni",
    title: "Poprzedni stan aktuatorów",
    type: "setup",
    help: "previous",
    pane: "previous",
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

const HISTORY_DIRECTION_META = {
  tx: { label: "Wysłano", className: "tx" },
  rx: { label: "Odebrano", className: "rx" },
  rx_invalid: { label: "Niepoprawny JSON", className: "invalid" },
};

function formatHistoryTimestamp(timestamp) {
  if (!Number.isFinite(timestamp)) return "";
  return new Date(timestamp * 1000).toLocaleString("pl-PL", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function formatHistoryPayload(payload) {
  if (payload === null || payload === undefined) return "";
  if (typeof payload === "string") return payload;
  try {
    return JSON.stringify(payload, null, 2);
  } catch (_) {
    return String(payload);
  }
}

function highlightJson(source) {
  const text = String(source ?? "");
  const tokenRe = /("(\\u[\dA-Fa-f]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)/g;
  let html = "";
  let last = 0;
  let match;
  while ((match = tokenRe.exec(text)) !== null) {
    html += escapeHtml(text.slice(last, match.index));
    const token = match[0];
    let cls = "json-num";
    if (/^"/.test(token)) cls = /:$/.test(token) ? "json-key" : "json-str";
    else if (/^(true|false|null)$/.test(token)) cls = "json-lit";
    html += `<span class="${cls}">${escapeHtml(token)}</span>`;
    last = tokenRe.lastIndex;
  }
  html += escapeHtml(text.slice(last));
  return html;
}

function renderHistoryEntry(entry, index) {
  const direction = entry?.direction || "rx";
  const meta = HISTORY_DIRECTION_META[direction] || {
    label: direction,
    className: "unknown",
  };
  const payloadText = formatHistoryPayload(entry?.payload);
  const body = direction === "rx_invalid"
    ? `<pre class="history-raw"><code>${escapeHtml(payloadText)}</code></pre>`
    : `<pre class="history-json"><code>${highlightJson(payloadText)}</code></pre>`;
  const time = formatHistoryTimestamp(entry?.timestamp);
  const timeMarkup = time
    ? `<time class="history-time" datetime="${new Date((entry.timestamp || 0) * 1000).toISOString()}">${escapeHtml(time)}</time>`
    : "";
  return `<article class="history-entry history-entry--${meta.className}">
    <header class="history-entry-head">
      <span class="history-index">#${index + 1}</span>
      <span class="history-dir">${escapeHtml(meta.label)}</span>
      ${timeMarkup}
    </header>
    ${body}
  </article>`;
}

function formatHistoryHtml(state) {
  const items = state?.history;
  if (!items?.length) {
    return '<p class="history-empty">Brak historii komunikacji z płytką.</p>';
  }
  const visible = items.slice(0, 20);
  const entries = visible.map((entry, index) => renderHistoryEntry(entry, index)).join("");
  return `<div class="history-panel">
    <p class="history-summary">Ostatnie <strong>${visible.length}</strong> wpisów (najnowsze u góry)</p>
    ${entries}
  </div>`;
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
  syncPanelModalActions();
  refreshModalContent({ force: true });
  document.getElementById("modal-close")?.focus({ preventScroll: true });
}

function closeModal() {
  const backdrop = document.getElementById("modal-backdrop");
  const returnTo = modalReturnFocus;
  modalReturnFocus = null;
  restoreFocusFromDialog(backdrop, returnTo, "#btn-panel-scenario");
  backdrop.classList.remove("open");
  backdrop.setAttribute("inert", "");
  backdrop.setAttribute("aria-hidden", "true");
  refreshModalStepBadge();
  updateModalLock();
  syncPanelModalActions();
}

function syncPanelModalActions() {
  const backdrop = document.getElementById("modal-backdrop");
  const open = backdrop?.classList.contains("open");
  document.querySelectorAll("[data-panel-modal]").forEach((btn) => {
    const active = open && btn.dataset.panelModal === activeModal;
    btn.classList.toggle("active", active);
    btn.setAttribute("aria-pressed", active ? "true" : "false");
  });
}

function refreshModalStepBadge() {
  const el = document.getElementById("modal-step-badge");
  const backdrop = document.getElementById("modal-backdrop");
  if (!el) return;
  const step = typeof previousStepForDisplay === "function" ? previousStepForDisplay() : null;
  const show = Boolean(
    step !== null
    && step !== undefined
    && backdrop?.classList.contains("open")
    && activeModal === "previous"
  );
  el.hidden = !show;
  if (show) el.textContent = `Krok ${step}`;
}

function updatePanelModalChrome(meta) {
  const textarea = document.getElementById("modal-content");
  const panel = document.getElementById("modal-content-panel");
  const isSetup = meta.type === "setup";
  const isHtml = meta.type === "html";
  const isJson = meta.type === "json";

  document.getElementById("modal-title").textContent = meta.title;
  refreshModalStepBadge();
  textarea.hidden = !isJson;
  panel.hidden = !isHtml;
  panel.className = meta.panelClass || "diag-modal-body";
  document.querySelectorAll(".setup-pane").forEach((pane) => {
    const active = isSetup && pane.id === `setup-pane-${meta.pane}`;
    pane.classList.toggle("active", active);
    pane.hidden = !active;
  });
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
  const meta = panelModalViews[activeModal];
  const panel = document.getElementById("modal-content-panel");
  const cacheKey = `${activeModal}:html`;
  const html = meta?.getHtml
    ? meta.getHtml()
    : formatDiagnosticsHtml(diagnosticsSnapshot);
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
  const top = topmostOpenModalBackdrop?.();
  if (!top) return false;

  event.preventDefault();
  event.stopPropagation();
  event.stopImmediatePropagation();

  switch (top.id) {
    case "help-modal-backdrop":
      selectWithinElement(document.getElementById("help-modal-content"));
      return true;
    case "notice-modal-backdrop":
      selectWithinElement(document.getElementById("notice-modal-content"));
      return true;
    case "confirm-modal-backdrop":
      selectWithinElement(document.getElementById("confirm-modal-content"));
      return true;
    case "modal-backdrop": {
      const panel = document.getElementById("modal-content-panel");
      const textarea = document.getElementById("modal-content");
      if (panel && !panel.hidden) {
        selectWithinElement(panel);
      } else {
        selectWithinElement(textarea);
      }
      return true;
    }
    default:
      return false;
  }
}

function handleModalKeydown(event) {
  if (handleModalSelectAll(event)) return;
  if (event.key !== "Escape") return;
  if (closeTopmostModal?.()) {
    event.preventDefault();
  }
}

document.addEventListener("keydown", handleModalKeydown, true);
