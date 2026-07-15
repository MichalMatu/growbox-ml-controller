function friendlyError(message) {
  const map = {
    "serial port is not connected": "Brak połączenia — kliknij Połącz",
    "port must not be empty": "Wybierz port USB",
    "Failed to fetch": "Panel offline — uruchom: make panel",
  };
  return map[message] || message;
}
async function runAction(fn, btn) {
  try {
    return await fn();
  } catch (err) {
    if (btn) {
      btn.classList.add("state-error");
      setTimeout(() => btn.classList.remove("state-error"), 1600);
    }
    throw err;
  }
}

async function api(path, options = {}) {
  let res;
  try {
    res = await fetch(path, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
  } catch (err) {
    throw new Error(friendlyError(err.message || "Failed to fetch"));
  }
  const data = await res.json();
  if (!res.ok) throw new Error(friendlyError(data.error || res.statusText));
  return data;
}
