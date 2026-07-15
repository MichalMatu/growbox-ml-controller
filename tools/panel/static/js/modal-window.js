const MODAL_WINDOW_MARGIN = 12;
const MODAL_WINDOW_MIN_W = 300;
const MODAL_WINDOW_MIN_H = 200;
const MODAL_WINDOW_STORAGE_PREFIX = "growbox-modal-window:";
const MODAL_WINDOW_CASCADE_STEP = 28;
const MODAL_STACK_BASE_Z = 100;

let modalWindowDrag = null;
let modalWindowResize = null;
let modalStackSeq = MODAL_STACK_BASE_Z;

function openModalBackdrops() {
  return [...document.querySelectorAll(".modal-backdrop.open")];
}

function backdropStackZ(backdrop) {
  return Number(backdrop?.style.zIndex || backdrop?.dataset.stackOrder || MODAL_STACK_BASE_Z);
}

function raiseModalBackdrop(backdrop) {
  if (!backdrop?.classList.contains("open")) return;
  modalStackSeq += 1;
  backdrop.style.zIndex = String(modalStackSeq);
  backdrop.dataset.stackOrder = String(modalStackSeq);
  syncModalFocusRing();
}

function topmostOpenModalBackdrop() {
  const open = openModalBackdrops();
  if (!open.length) return null;
  return open.reduce((top, backdrop) => (
    backdropStackZ(backdrop) >= backdropStackZ(top) ? backdrop : top
  ));
}

function syncModalFocusRing() {
  document.querySelectorAll(".modal.modal--focused").forEach((modal) => {
    modal.classList.remove("modal--focused");
  });
  const top = topmostOpenModalBackdrop();
  top?.querySelector(".modal")?.classList.add("modal--focused");
}

function modalCascadeOffset(backdrop) {
  const open = openModalBackdrops();
  const index = open.indexOf(backdrop);
  return Math.max(0, index) * MODAL_WINDOW_CASCADE_STEP;
}

function closeTopmostModal() {
  const top = topmostOpenModalBackdrop();
  if (!top) return false;
  switch (top.id) {
    case "help-modal-backdrop":
      closeHelp();
      return true;
    case "modal-backdrop":
      closeModal();
      return true;
    case "notice-modal-backdrop":
      closeNotice();
      return true;
    case "confirm-modal-backdrop":
      finishConfirm(false);
      return true;
    default:
      return false;
  }
}

function modalWindowStorageKey(backdrop) {
  return MODAL_WINDOW_STORAGE_PREFIX + backdrop.id;
}

function readModalWindowGeometry(backdrop) {
  try {
    const raw = sessionStorage.getItem(modalWindowStorageKey(backdrop));
    if (!raw) return null;
    const geometry = JSON.parse(raw);
    if (!geometry || typeof geometry !== "object") return null;
    const { left, top, width, height } = geometry;
    if (![left, top, width, height].every(v => typeof v === "number" && Number.isFinite(v))) return null;
    return { left, top, width, height };
  } catch {
    return null;
  }
}

function writeModalWindowGeometry(backdrop, geometry) {
  try {
    sessionStorage.setItem(modalWindowStorageKey(backdrop), JSON.stringify(geometry));
  } catch {
    /* ignore quota */
  }
}

function clearModalWindowGeometry(backdrop) {
  try {
    sessionStorage.removeItem(modalWindowStorageKey(backdrop));
  } catch {
    /* ignore */
  }
}

function cssLengthPx(value) {
  const trimmed = String(value || "").trim();
  if (!trimmed) return 0;
  if (trimmed.endsWith("px")) return parseFloat(trimmed);
  const probe = document.createElement("div");
  probe.style.position = "absolute";
  probe.style.visibility = "hidden";
  probe.style.width = trimmed;
  document.body.appendChild(probe);
  const px = probe.getBoundingClientRect().width;
  probe.remove();
  return px;
}

function defaultModalWindowGeometry(modal, backdrop) {
  const styles = getComputedStyle(document.documentElement);
  const isWide = modal.classList.contains("modal--wide");
  const maxW = Math.max(MODAL_WINDOW_MIN_W, window.innerWidth - MODAL_WINDOW_MARGIN * 2);
  const maxH = Math.max(MODAL_WINDOW_MIN_H, window.innerHeight - MODAL_WINDOW_MARGIN * 2);
  const width = Math.min(
    cssLengthPx(isWide ? styles.getPropertyValue("--modal-w-wide") : styles.getPropertyValue("--modal-w")) || (isWide ? 928 : 720),
    maxW,
  );
  const bodyH = Math.min(
    cssLengthPx(isWide ? styles.getPropertyValue("--modal-body-min-h-wide") : styles.getPropertyValue("--modal-body-h")) || (isWide ? 420 : 320),
    maxH - 96,
  );
  const height = Math.min(bodyH + 96, maxH);
  const cascade = backdrop ? modalCascadeOffset(backdrop) : 0;
  return clampModalWindowGeometry({
    left: Math.round((window.innerWidth - width) / 2) + cascade,
    top: Math.round((window.innerHeight - height) / 2) + cascade,
    width: Math.round(width),
    height: Math.round(height),
  });
}

function clampModalWindowGeometry(geometry) {
  const maxW = Math.max(MODAL_WINDOW_MIN_W, window.innerWidth - MODAL_WINDOW_MARGIN * 2);
  const maxH = Math.max(MODAL_WINDOW_MIN_H, window.innerHeight - MODAL_WINDOW_MARGIN * 2);
  const width = Math.max(MODAL_WINDOW_MIN_W, Math.min(geometry.width, maxW));
  const height = Math.max(MODAL_WINDOW_MIN_H, Math.min(geometry.height, maxH));
  const left = Math.max(
    MODAL_WINDOW_MARGIN,
    Math.min(geometry.left, window.innerWidth - width - MODAL_WINDOW_MARGIN),
  );
  const top = Math.max(
    MODAL_WINDOW_MARGIN,
    Math.min(geometry.top, window.innerHeight - height - MODAL_WINDOW_MARGIN),
  );
  return { left: Math.round(left), top: Math.round(top), width: Math.round(width), height: Math.round(height) };
}

function geometryFromModal(modal) {
  const rect = modal.getBoundingClientRect();
  return {
    left: Math.round(rect.left),
    top: Math.round(rect.top),
    width: Math.round(rect.width),
    height: Math.round(rect.height),
  };
}

function applyModalWindowGeometry(modal, geometry) {
  const clamped = clampModalWindowGeometry(geometry);
  modal.classList.add("modal--windowed");
  modal.style.left = `${clamped.left}px`;
  modal.style.top = `${clamped.top}px`;
  modal.style.width = `${clamped.width}px`;
  modal.style.height = `${clamped.height}px`;
  return clamped;
}

function resetModalWindowGeometry(backdrop) {
  const modal = backdrop.querySelector(".modal");
  if (!modal) return;
  clearModalWindowGeometry(backdrop);
  modal.classList.remove("modal--windowed", "modal--dragging", "modal--resizing");
  modal.style.left = "";
  modal.style.top = "";
  modal.style.width = "";
  modal.style.height = "";
  requestAnimationFrame(() => {
    if (!backdrop.classList.contains("open")) return;
    applyModalWindowGeometry(modal, defaultModalWindowGeometry(modal, backdrop));
    writeModalWindowGeometry(backdrop, geometryFromModal(modal));
  });
}

function prepareModalWindow(backdrop) {
  const modal = backdrop.querySelector(".modal");
  if (!modal) return;
  const stored = readModalWindowGeometry(backdrop);
  applyModalWindowGeometry(modal, stored || defaultModalWindowGeometry(modal, backdrop));
  if (!stored) writeModalWindowGeometry(backdrop, geometryFromModal(modal));
  raiseModalBackdrop(backdrop);
}

function modalWindowDragBlocked(target) {
  return Boolean(target.closest(
    "button, a, input, select, textarea, label, .modal-resize-handle",
  ));
}

function onModalWindowHeadPointerDown(event) {
  if (event.button !== 0) return;
  if (modalWindowDragBlocked(event.target)) return;
  const head = event.currentTarget;
  const modal = head.closest(".modal");
  const backdrop = modal?.parentElement;
  if (!backdrop?.classList.contains("modal-backdrop") || !backdrop.classList.contains("open")) return;
  raiseModalBackdrop(backdrop);
  const geometry = geometryFromModal(modal);
  modalWindowDrag = {
    modal,
    backdrop,
    startX: event.clientX,
    startY: event.clientY,
    origin: geometry,
  };
  modal.classList.add("modal--dragging");
  head.setPointerCapture?.(event.pointerId);
  event.preventDefault();
}

function onModalWindowResizePointerDown(event) {
  if (event.button !== 0) return;
  const handle = event.currentTarget;
  const modal = handle.closest(".modal");
  const backdrop = modal?.parentElement;
  if (!backdrop?.classList.contains("modal-backdrop") || !backdrop.classList.contains("open")) return;
  modalWindowResize = {
    modal,
    backdrop,
    startX: event.clientX,
    startY: event.clientY,
    origin: geometryFromModal(modal),
  };
  modal.classList.add("modal--resizing");
  handle.setPointerCapture?.(event.pointerId);
  event.preventDefault();
  event.stopPropagation();
}

function onModalWindowPointerMove(event) {
  if (modalWindowDrag) {
    const dx = event.clientX - modalWindowDrag.startX;
    const dy = event.clientY - modalWindowDrag.startY;
    applyModalWindowGeometry(modalWindowDrag.modal, {
      left: modalWindowDrag.origin.left + dx,
      top: modalWindowDrag.origin.top + dy,
      width: modalWindowDrag.origin.width,
      height: modalWindowDrag.origin.height,
    });
    return;
  }
  if (modalWindowResize) {
    const dx = event.clientX - modalWindowResize.startX;
    const dy = event.clientY - modalWindowResize.startY;
    applyModalWindowGeometry(modalWindowResize.modal, {
      left: modalWindowResize.origin.left,
      top: modalWindowResize.origin.top,
      width: modalWindowResize.origin.width + dx,
      height: modalWindowResize.origin.height + dy,
    });
  }
}

function finishModalWindowPointer(modal, backdrop) {
  if (!modal || !backdrop) return;
  modal.classList.remove("modal--dragging", "modal--resizing");
  writeModalWindowGeometry(backdrop, geometryFromModal(modal));
}

function onModalWindowPointerUp(event) {
  if (modalWindowDrag) {
    finishModalWindowPointer(modalWindowDrag.modal, modalWindowDrag.backdrop);
    modalWindowDrag = null;
    return;
  }
  if (modalWindowResize) {
    finishModalWindowPointer(modalWindowResize.modal, modalWindowResize.backdrop);
    modalWindowResize = null;
  }
}

function onModalWindowHeadDoubleClick(event) {
  if (modalWindowDragBlocked(event.target)) return;
  const backdrop = event.currentTarget.closest(".modal-backdrop");
  if (!backdrop) return;
  resetModalWindowGeometry(backdrop);
}

function ensureModalResizeHandle(modal) {
  if (modal.querySelector(".modal-resize-handle")) return;
  const handle = document.createElement("div");
  handle.className = "modal-resize-handle";
  handle.setAttribute("aria-hidden", "true");
  handle.title = "Zmień rozmiar";
  handle.addEventListener("pointerdown", onModalWindowResizePointerDown);
  modal.appendChild(handle);
}

function onModalWindowSurfacePointerDown(event) {
  if (event.button !== 0) return;
  const modal = event.currentTarget;
  const backdrop = modal?.parentElement;
  if (!backdrop?.classList.contains("modal-backdrop") || !backdrop.classList.contains("open")) return;
  raiseModalBackdrop(backdrop);
}

function initModalWindow(backdrop) {
  const modal = backdrop.querySelector(".modal");
  if (!modal) return;
  ensureModalResizeHandle(modal);
  if (modal.dataset.modalWindowBound !== "1") {
    modal.dataset.modalWindowBound = "1";
    modal.addEventListener("pointerdown", onModalWindowSurfacePointerDown);
  }
  const head = modal.querySelector(".modal-head");
  if (!head || head.dataset.modalWindowBound === "1") return;
  head.dataset.modalWindowBound = "1";
  head.addEventListener("pointerdown", onModalWindowHeadPointerDown);
  head.addEventListener("dblclick", onModalWindowHeadDoubleClick);
}

function initModalWindows() {
  document.querySelectorAll(".modal-backdrop").forEach(initModalWindow);
  document.addEventListener("pointermove", onModalWindowPointerMove);
  document.addEventListener("pointerup", onModalWindowPointerUp);
  document.addEventListener("pointercancel", onModalWindowPointerUp);
  window.addEventListener("resize", () => {
    document.querySelectorAll(".modal-backdrop.open .modal.modal--windowed").forEach((modal) => {
      const backdrop = modal.parentElement;
      if (!backdrop) return;
      applyModalWindowGeometry(modal, clampModalWindowGeometry(geometryFromModal(modal)));
      writeModalWindowGeometry(backdrop, geometryFromModal(modal));
    });
  });

  const observer = new MutationObserver((records) => {
    records.forEach((record) => {
      const backdrop = record.target;
      if (!backdrop.classList?.contains("modal-backdrop")) return;
      if (backdrop.classList.contains("open")) {
        initModalWindow(backdrop);
        requestAnimationFrame(() => prepareModalWindow(backdrop));
      } else {
        const modal = backdrop.querySelector(".modal");
        modal?.classList.remove("modal--dragging", "modal--resizing", "modal--focused");
        syncModalFocusRing();
      }
    });
  });

  document.querySelectorAll(".modal-backdrop").forEach((backdrop) => {
    observer.observe(backdrop, { attributes: true, attributeFilter: ["class"] });
  });
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initModalWindows);
} else {
  initModalWindows();
}
