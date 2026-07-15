function setNested(obj, path, value) {
  const parts = path.split(".");
  let cur = obj;
  for (let i = 0; i < parts.length - 1; i++) {
    if (typeof cur[parts[i]] !== "object" || cur[parts[i]] === null) cur[parts[i]] = {};
    cur = cur[parts[i]];
  }
  cur[parts[parts.length - 1]] = value;
}

function getNested(obj, path) {
  return path.split(".").reduce((acc, key) => (acc && acc[key] !== undefined ? acc[key] : undefined), obj);
}

function restoreFocusFromDialog(backdrop, returnTo, fallbackSelector) {
  const fallbackEl = fallbackSelector ? document.querySelector(fallbackSelector) : null;
  const canFocus = (el) => {
    if (!el || !document.contains(el) || typeof el.focus !== "function") return false;
    if (el.disabled) return false;
    if (el.classList.contains("state-disabled")) return false;
    return true;
  };
  const focusEl = (el) => {
    if (!canFocus(el)) return false;
    el.focus({ preventScroll: true });
    return !backdrop.contains(document.activeElement);
  };
  if (!focusEl(returnTo)) focusEl(fallbackEl);
  const focused = document.activeElement;
  if (focused && backdrop.contains(focused)) {
    if (typeof focused.blur === "function") focused.blur();
    focusEl(fallbackEl);
  }
}
