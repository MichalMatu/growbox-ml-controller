function escapeHtml(text) {
  return String(text ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function isIndexSegment(segment) {
  return /^\d+$/.test(segment);
}

function normalizeControlType(value) {
  if (value === "pwm" || value === 1 || value === 1.0) return "pwm";
  if (value === "binary" || value === 0 || value === 0.0) return "binary";
  if (typeof value === "string" && value.toLowerCase() === "pwm") return "pwm";
  return "binary";
}

function coerceContainer(parent, key, nextKey) {
  const existing = parent[key];
  if (isIndexSegment(nextKey)) {
    if (Array.isArray(existing)) return existing;
    if (existing && typeof existing === "object") {
      const arr = [];
      for (const [idx, entry] of Object.entries(existing)) {
        if (isIndexSegment(idx)) arr[Number(idx)] = entry;
      }
      parent[key] = arr;
      return arr;
    }
    parent[key] = [];
    return parent[key];
  }
  if (existing && typeof existing === "object" && !Array.isArray(existing)) return existing;
  parent[key] = {};
  return parent[key];
}

function setNested(obj, path, value) {
  const parts = path.split(".");
  let cur = obj;
  for (let i = 0; i < parts.length - 1; ) {
    const key = parts[i];
    if (isIndexSegment(key)) {
      const index = Number(key);
      const next = parts[i + 1];
      if (cur[index] === undefined || cur[index] === null) {
        cur[index] = isIndexSegment(next) ? [] : {};
      }
      cur = cur[index];
      i += 1;
      continue;
    }
    const next = parts[i + 1];
    if (cur[key] === undefined || cur[key] === null) {
      cur[key] = isIndexSegment(next) ? [] : {};
    } else if (isIndexSegment(next)) {
      cur[key] = coerceContainer({ [key]: cur[key] }, key, next);
    }
    if (isIndexSegment(next)) {
      const index = Number(next);
      if (cur[key][index] === undefined || cur[key][index] === null) {
        cur[key][index] = isIndexSegment(parts[i + 2]) ? [] : {};
      }
      cur = cur[key][index];
      i += 2;
      continue;
    }
    cur = cur[key];
    i += 1;
  }
  const leaf = parts[parts.length - 1];
  if (isIndexSegment(leaf)) cur[Number(leaf)] = value;
  else cur[leaf] = value;
}

function getNested(obj, path) {
  if (!obj || !path) return undefined;
  return path.split(".").reduce((acc, key) => {
    if (acc === undefined || acc === null) return undefined;
    if (Array.isArray(acc) && isIndexSegment(key)) return acc[Number(key)];
    return acc[key];
  }, obj);
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
