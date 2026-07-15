var diagnosticsSnapshot = null;

function formatBytes(value) {
  const n = Number(value);
  if (!Number.isFinite(n) || n < 0) return "—";
  if (n >= 1048576) return `${(n / 1048576).toFixed(2)} MB`;
  if (n >= 1024) return `${(n / 1024).toFixed(1)} kB`;
  return `${Math.round(n)} B`;
}

function formatDiagPercent(used, total) {
  if (!Number.isFinite(used) || !Number.isFinite(total) || total <= 0) return 0;
  return Math.min(100, Math.max(0, Math.round((used / total) * 100)));
}

function renderDiagMeter(label, used, total, { tone = "accent", detail = "" } = {}) {
  const pct = formatDiagPercent(used, total);
  return `<div class="diag-meter">
    <div class="diag-meter-head">
      <span class="diag-meter-label">${label}</span>
      <span class="diag-meter-value">${detail || `${pct}%`}</span>
    </div>
    <div class="diag-meter-track" aria-hidden="true">
      <span class="diag-meter-fill ${tone}" style="width:${pct}%"></span>
    </div>
  </div>`;
}

function renderDiagRow(label, value, { mono = false, warn = false } = {}) {
  const cls = ["diag-row", warn ? "warn" : "", mono ? "mono" : ""].filter(Boolean).join(" ");
  return `<div class="${cls}"><span class="diag-row-label">${label}</span><span class="diag-row-value">${value}</span></div>`;
}

function formatDiagnosticsHtml(snapshot) {
  if (!snapshot) {
    return `<p class="diag-note">Brak danych — połącz płytkę i kliknij <strong>Odśwież</strong>.</p>`;
  }
  if (typeof snapshot === "string") {
    return `<p class="diag-note diag-error">${snapshot}</p>`;
  }

  const device = snapshot.device || {};
  const heap = device.heap || {};
  const task = device.task || {};
  const runtime = device.runtime || {};
  const startup = snapshot.startup || {};
  const boardProfile = device.board_profile || startup.board_profile || "—";
  const psramOn = Boolean(heap.psram_enabled ?? startup.psram_enabled);
  const totalPsram = Number(heap.total_psram) || 0;
  const freePsram = Number(heap.free_psram) || 0;
  const usedPsram = totalPsram > 0 ? Math.max(0, totalPsram - freePsram) : 0;
  const freeInternal = Number(heap.free_internal ?? startup.free_internal ?? startup.free_heap) || 0;
  const minInternal = Number(heap.min_free_internal) || 0;
  const largestInternal = Number(heap.largest_free_internal) || 0;
  const stackFree = Number(task.main_stack_free_bytes) || 0;
  const stackTotal = 8192;
  const stackUsed = stackFree > 0 ? Math.max(0, stackTotal - stackFree) : 0;
  const connected = Boolean(snapshot.connected);
  const port = snapshot.port || "—";
  const mode = runtime.mode === "replay" ? "Replay" : runtime.mode === "closed_loop" ? "Loop" : "—";
  const runState = runtime.paused === false ? "działa" : "pauza";

  const psramSection = psramOn
    ? `${renderDiagMeter("PSRAM — zajęte", usedPsram, totalPsram, {
        tone: usedPsram / totalPsram > 0.85 ? "warn" : "ok",
        detail: `${formatBytes(freePsram)} wolne / ${formatBytes(totalPsram)}`,
      })}
      ${renderDiagRow("Największy blok PSRAM", formatBytes(heap.largest_free_psram), { mono: true })}
      ${renderDiagRow("Minimum PSRAM od startu", formatBytes(heap.min_free_psram), { mono: true })}`
    : `<p class="diag-note">PSRAM wyłączone lub niedostępne w firmware.</p>`;

  return `<div class="diag-panel">
    <section class="diag-section">
      <h4>Połączenie</h4>
      ${renderDiagRow("Status", connected ? "Połączono" : "Brak połączenia", { warn: !connected })}
      ${renderDiagRow("Port", port, { mono: true })}
      ${renderDiagRow("Profil płytki", boardProfile, { mono: true })}
    </section>
    <section class="diag-section">
      <h4>Pamięć PSRAM</h4>
      ${renderDiagRow("PSRAM", psramOn ? "włączony" : "wyłączony")}
      ${psramSection}
    </section>
    <section class="diag-section">
      <h4>DRAM wewnętrzny</h4>
      ${renderDiagRow("Wolne teraz", formatBytes(freeInternal), { mono: true })}
      ${renderDiagRow("Minimum od startu", formatBytes(minInternal), { mono: true })}
      ${renderDiagRow("Największy wolny blok", formatBytes(largestInternal), { mono: true })}
    </section>
    <section class="diag-section">
      <h4>Stos zadania main</h4>
      ${renderDiagMeter("Zajęty stos", stackUsed, stackTotal, {
        tone: stackFree < 1024 ? "warn" : "accent",
        detail: `${formatBytes(stackFree)} wolne / ${formatBytes(stackTotal)}`,
      })}
    </section>
    <section class="diag-section">
      <h4>Runtime firmware</h4>
      ${renderDiagRow("Tryb", mode)}
      ${renderDiagRow("Stan", runState)}
      ${renderDiagRow("Krok", runtime.step ?? "—", { mono: true })}
      ${renderDiagRow("Seed", runtime.seed ?? startup.seed ?? "—", { mono: true })}
    </section>
    ${startup.free_heap !== undefined ? `<section class="diag-section">
      <h4>Przy starcie (startup)</h4>
      ${renderDiagRow("Wolna pamięć", formatBytes(startup.free_heap), { mono: true })}
      ${renderDiagRow("DRAM", formatBytes(startup.free_internal), { mono: true })}
      ${renderDiagRow("PSRAM", formatBytes(startup.free_psram), { mono: true })}
    </section>` : ""}
  </div>`;
}

function updateResourcesStrip() {
  const el = document.getElementById("resources-strip");
  if (!el) return;
  if (!lastState?.connected || !diagnosticsSnapshot?.device?.heap) {
    el.hidden = true;
    el.innerHTML = "";
    return;
  }
  const heap = diagnosticsSnapshot.device.heap;
  const psramOn = Boolean(heap.psram_enabled);
  const totalPsram = Number(heap.total_psram) || 0;
  const freePsram = Number(heap.free_psram) || 0;
  const freeInternal = Number(heap.free_internal) || 0;
  const parts = [
    `<span class="res-chip"><span class="res-label">DRAM</span> ${formatBytes(freeInternal)}</span>`,
  ];
  if (psramOn && totalPsram > 0) {
    const pct = formatDiagPercent(totalPsram - freePsram, totalPsram);
    parts.push(`<span class="res-chip psram"><span class="res-label">PSRAM</span> ${formatBytes(freePsram)} <span class="res-muted">(${pct}% użyte)</span></span>`);
  }
  el.hidden = false;
  el.innerHTML = parts.join("");
}

async function refreshDiagnosticsView(refreshDevice = true) {
  const query = refreshDevice && lastState?.connected ? "?refresh=1" : "";
  try {
    diagnosticsSnapshot = await api(`/api/diagnostics${query}`);
  } catch (err) {
    diagnosticsSnapshot = `Błąd: ${friendlyError(err.message)}`;
  }
  updateResourcesStrip();
  if (activeModal === "diagnostics") refreshModalContent();
}

async function openDiagnosticsModal() {
  await refreshDiagnosticsView(true);
  openModal("diagnostics");
}