var confirmReturnFocus = null;
var confirmResolve = null;
var noticeReturnFocus = null;

function finishConfirm(ok) {
  const backdrop = document.getElementById("confirm-modal-backdrop");
  const resolve = confirmResolve;
  const returnTo = confirmReturnFocus;
  confirmResolve = null;
  confirmReturnFocus = null;
  restoreFocusFromDialog(backdrop, returnTo, "#btn-connect");
  backdrop.classList.remove("open");
  backdrop.setAttribute("inert", "");
  backdrop.setAttribute("aria-hidden", "true");
  updateModalLock();
  resolve?.(ok);
}

function openConfirm({ title, html, okLabel = "OK", cancelLabel = "Anuluj" }) {
  return new Promise((resolve) => {
    const backdrop = document.getElementById("confirm-modal-backdrop");
    if (!backdrop) {
      resolve(false);
      return;
    }
    confirmResolve = resolve;
    confirmReturnFocus = document.activeElement;
    document.getElementById("confirm-modal-title").textContent = title || "Potwierdź";
    document.getElementById("confirm-modal-content").innerHTML = html || "";
    const okBtn = document.getElementById("confirm-modal-ok");
    const cancelBtn = document.getElementById("confirm-modal-cancel");
    okBtn.textContent = okLabel;
    cancelBtn.textContent = cancelLabel;
    backdrop.classList.add("open");
    backdrop.removeAttribute("inert");
    backdrop.setAttribute("aria-hidden", "false");
    updateModalLock();
    cancelBtn.focus();
  });
}

function openNotice({ title, body, instructions, html }) {
  const backdrop = document.getElementById("notice-modal-backdrop");
  if (!backdrop) return;
  noticeReturnFocus = document.activeElement;
  document.getElementById("notice-modal-title").textContent = title || "Informacja";
  const content = document.getElementById("notice-modal-content");
  if (html) {
    content.innerHTML = html;
  } else {
    const parts = [];
    if (body) parts.push(`<p>${escapeHtml(body)}</p>`);
    if (instructions) parts.push(`<h4>Co zrobić?</h4>${instructions}`);
    content.innerHTML = parts.join("");
  }
  backdrop.classList.add("open");
  backdrop.removeAttribute("inert");
  backdrop.setAttribute("aria-hidden", "false");
  updateModalLock();
  document.getElementById("notice-modal-close")?.focus({ preventScroll: true });
}

function closeNotice() {
  const backdrop = document.getElementById("notice-modal-backdrop");
  const returnTo = noticeReturnFocus;
  noticeReturnFocus = null;
  restoreFocusFromDialog(backdrop, returnTo, "#btn-connect");
  backdrop.classList.remove("open");
  backdrop.setAttribute("inert", "");
  backdrop.setAttribute("aria-hidden", "true");
  updateModalLock();
}

function handleDialogKeydown(event) {
  const confirmBackdrop = document.getElementById("confirm-modal-backdrop");
  const noticeBackdrop = document.getElementById("notice-modal-backdrop");
  if (event.key !== "Escape") return;
  if (confirmBackdrop?.classList.contains("open")) {
    event.preventDefault();
    finishConfirm(false);
  } else if (noticeBackdrop?.classList.contains("open")) {
    event.preventDefault();
    closeNotice();
  }
}

function initPanelDialogs() {
  document.getElementById("confirm-modal-cancel")?.addEventListener("click", () => finishConfirm(false));
  document.getElementById("confirm-modal-ok")?.addEventListener("click", () => finishConfirm(true));
  document.getElementById("confirm-modal-backdrop")?.addEventListener("click", (event) => {
    if (event.target.id === "confirm-modal-backdrop") finishConfirm(false);
  });
  document.getElementById("notice-modal-close")?.addEventListener("click", closeNotice);
  document.getElementById("notice-modal-backdrop")?.addEventListener("click", (event) => {
    if (event.target.id === "notice-modal-backdrop") closeNotice();
  });
  document.getElementById("top-messages")?.addEventListener("click", (event) => {
    const btn = event.target.closest("[data-msg-idx]");
    if (!btn) return;
    const item = topBarMessageItems[Number(btn.dataset.msgIdx)];
    if (!item?.detail) return;
    openNotice(item.detail);
  });
}

initPanelDialogs();
