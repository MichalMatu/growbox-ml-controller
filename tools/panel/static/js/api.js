const CONNECT_ERROR_CATALOG = [
  {
    match: (message) => message.includes("Wybrany port nie odpowiada"),
    short: "Zły port",
    title: "To nie jest płytka growbox",
    body: "Port otworzył się, ale urządzenie nie odpowiedziało protokołem growbox ML.",
    instructions: `<ul>
      <li>Wybierz port <code>usbmodem…</code> (Espressif / JTAG)</li>
      <li>Pomiń porty Bluetooth, słuchawek i <code>debug-console</code></li>
      <li>Odłącz inne urządzenia USB, jeśli lista jest myląca</li>
    </ul>`,
  },
  {
    match: (message) => message.includes("płytka nie odpowiedziała jak growbox"),
    short: "Brak odpowiedzi",
    title: "Płytka nie odpowiada",
    body: "Połączenie szeregowe działa, ale firmware nie zwrócił statusu growbox ML.",
    instructions: `<ul>
      <li>Sprawdź, czy wybrany port to ESP32-S3 (<code>usbmodem</code>)</li>
      <li>Naciśnij przycisk <strong>EN</strong> na płytce i spróbuj ponownie</li>
      <li>Upewnij się, że firmware growbox jest wgrany i działa</li>
    </ul>`,
  },
  {
    match: (message) => message.includes("nie zwróciła scenariusza"),
    short: "Brak scenariusza",
    title: "Brak scenariusza z płytki",
    body: "Połączenie jest aktywne, ale płytka nie zwróciła aktualnego scenariusza.",
    instructions: `<ul>
      <li>Kliknij <strong>Połącz</strong> ponownie po resecie płytki</li>
      <li>Sprawdź w logu serial, czy firmware obsługuje <code>get_scenario</code></li>
    </ul>`,
  },
  {
    match: (message) => message.includes("port must not be empty") || message.includes("Wybierz port"),
    short: "Wybierz port",
    title: "Brak portu",
    body: "Wybierz port USB z listy przed połączeniem.",
    instructions: `<ul><li>Kliknij <strong>↻</strong>, jeśli lista portów jest pusta</li></ul>`,
  },
  {
    match: (message) => message.includes("Failed to fetch") || message.includes("Panel offline"),
    short: "Panel offline",
    title: "Panel nie działa",
    body: "Przeglądarka nie może połączyć się z serwerem panelu.",
    instructions: `<ul><li>Uruchom panel: <code>make panel</code></li></ul>`,
  },
  {
    match: (message) => message.includes("serial port is not connected") || message.includes("Brak połączenia"),
    short: "Brak połączenia",
    title: "Nie połączono z płytką",
    body: "Ta operacja wymaga aktywnego połączenia szeregowego.",
    instructions: `<ul><li>Wybierz port ESP32 i kliknij <strong>Połącz</strong></li></ul>`,
  },
];

function resolveConnectError(message) {
  const text = String(message || "");
  for (const entry of CONNECT_ERROR_CATALOG) {
    if (entry.match(text)) {
      return {
        short: entry.short,
        title: entry.title,
        body: entry.body,
        instructions: entry.instructions,
      };
    }
  }
  const short = text.length > 36 ? `${text.slice(0, 33)}…` : text;
  return {
    short: short || "Błąd",
    title: "Błąd połączenia",
    body: text,
    instructions: "",
  };
}

function friendlyError(message) {
  return resolveConnectError(message).short;
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
    throw new Error(err.message || "Failed to fetch");
  }
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || res.statusText);
  return data;
}
