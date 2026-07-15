const MODAL_WINDOW_MARGIN = 12;
const MODAL_WINDOW_MIN_W = 300;
const MODAL_WINDOW_MIN_H = 200;
const MODAL_WINDOW_STORAGE_PREFIX = "growbox-modal-window:";

let modalWindowDrag = null;
let modalWindowResize = null;

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

function defaultModalWindowGeometry(modal) {
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
  return clampModalWindowGeometry({
    left: Math.round((window.innerWidth - width) / 2),
    top: Math.round((window.innerHeight - height) / 2),
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
    applyModalWindowGeometry(modal, defaultModalWindowGeometry(modal));
    writeModalWindowGeometry(backdrop, geometryFromModal(modal));
  });
}

function prepareModalWindow(backdrop) {
  const modal = backdrop.querySelector(".modal");
  if (!modal) return;
  const stored = readModalWindowGeometry(backdrop);
  applyModalWindowGeometry(modal, stored || defaultModalWindowGeometry(modal));
  if (!stored) writeModalWindowGeometry(backdrop, geometryFromModal(modal));
}

function modalWindowDragBlocked(target) {
  return Boolean(target.closest(
    "button, a, input, select, textarea, label, .modal-tabs, .modal-resize-handle",
  ));
}

function onModalWindowHeadPointerDown(event) {
  if (event.button !== 0) return;
  if (modalWindowDragBlocked(event.target)) return;
  const head = event.currentTarget;
  const modal = head.closest(".modal");
  const backdrop = modal?.parentElement;
  if (!backdrop?.classList.contains("modal-backdrop") || !backdrop.classList.contains("open")) return;
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

function initModalWindow(backdrop) {
  const modal = backdrop.querySelector(".modal");
  if (!modal) return;
  ensureModalResizeHandle(modal);
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
        modal?.classList.remove("modal--dragging", "modal--resizing");
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
