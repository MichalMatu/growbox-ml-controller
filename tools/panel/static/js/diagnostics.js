var diagnosticsSnapshot = null;

function formatBytes(value) {
  const n = Number(value);
  if (!Number.isFinite(n) || n < 0) return "—";
  if (n >= 1048576) return `${(n / 1048576).toFixed(2)} MB`;
  if (n >= 1024) return `${(n / 1024).toFixed(1)} kB`;
  return `${Math.round(n)} B`;
}

function formatUsagePct(used, total) {
  if (!Number.isFinite(used) || !Number.isFinite(total) || total <= 0) return "0%";
  const pct = (used / total) * 100;
  if (pct > 0 && pct < 1) return `${pct.toFixed(2)}%`;
  return `${Math.round(pct)}%`;
}

function formatDiagPercent(used, total) {
  if (!Number.isFinite(used) || !Number.isFinite(total) || total <= 0) return 0;
  return Math.min(100, Math.max(0, (used / total) * 100));
}

function formatUsageDetail(used, total) {
  return `${formatBytes(used)} / ${formatBytes(total)} · ${formatUsagePct(used, total)}`;
}

function renderDiagMeter(label, used, total, { tone = "accent", detail = "" } = {}) {
  const pct = formatDiagPercent(used, total);
  const barPct = used > 0 && pct < 1 ? Math.max(pct, 0.8) : pct;
  const fillCls = ["diag-meter-fill", tone, used > 0 ? "has-use" : ""].filter(Boolean).join(" ");
  return `<div class="diag-meter">
    <div class="diag-meter-head">
      <span class="diag-meter-label">${label}</span>
      <span class="diag-meter-value">${detail || formatUsageDetail(used, total)}</span>
    </div>
    <div class="diag-meter-track" aria-hidden="true">
      <span class="${fillCls}" style="width:${barPct}%"></span>
    </div>
  </div>`;
}

function renderDiagRow(label, value, { mono = false, warn = false } = {}) {
  const cls = ["diag-row", warn ? "warn" : "", mono ? "mono" : ""].filter(Boolean).join(" ");
  return `<div class="${cls}"><span class="diag-row-label">${label}</span><span class="diag-row-value">${value}</span></div>`;
}

function renderDiagSection(title, body) {
  return `<section class="diag-section"><h4>${title}</h4>${body}</section>`;
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
  const memory = device.memory || {};
  const task = device.task || {};
  const runtime = device.runtime || {};
  const startup = snapshot.startup || {};
  const boardProfile = device.board_profile || startup.board_profile || "—";
  const psramOn = Boolean(heap.psram_enabled ?? startup.psram_enabled);
  const totalPsram = Number(heap.total_psram) || 0;
  const freePsram = Number(heap.free_psram) || 0;
  const usedPsram = Number(heap.used_psram) || (totalPsram > 0 ? Math.max(0, totalPsram - freePsram) : 0);
  const totalInternal = Number(heap.total_internal) || 0;
  const freeInternal = Number(heap.free_internal ?? startup.free_internal ?? startup.free_heap) || 0;
  const usedInternal = Number(heap.used_internal) || (totalInternal > 0 ? Math.max(0, totalInternal - freeInternal) : 0);
  const minInternal = Number(heap.min_free_internal) || 0;
  const largestInternal = Number(heap.largest_free_internal) || 0;
  const stackFree = Number(task.main_stack_free_bytes) || 0;
  const stackTotal = 8192;
  const stackUsed = stackFree > 0 ? Math.max(0, stackTotal - stackFree) : 0;
  const connected = Boolean(snapshot.connected);
  const port = (snapshot.port || "—").replace("/dev/cu.", "");
  const mode = runtime.mode === "replay" ? "Replay" : runtime.mode === "closed_loop" ? "Loop" : "—";
  const runState = runtime.paused === false ? "działa" : "pauza";
  const serialLineBytes = Number(memory.serial_line_bytes) || 0;
  const serialInPsram = memory.serial_line_in_psram === true;

  const psramBody = psramOn
    ? `${renderDiagMeter("Zajęte", usedPsram, totalPsram, {
        tone: usedPsram / totalPsram > 0.85 ? "warn" : "ok",
        detail: formatUsageDetail(usedPsram, totalPsram),
      })}
      ${renderDiagRow("Wolne", formatBytes(freePsram), { mono: true })}
      ${renderDiagRow("Max blok", formatBytes(heap.largest_free_psram), { mono: true })}
      ${renderDiagRow("Min. wolne", formatBytes(heap.min_free_psram), { mono: true })}`
    : `<p class="diag-note">PSRAM niedostępny.</p>`;

  const dramBody = totalInternal > 0
    ? `${renderDiagMeter("Zajęte", usedInternal, totalInternal, {
        tone: usedInternal / totalInternal > 0.85 ? "warn" : "accent",
        detail: formatUsageDetail(usedInternal, totalInternal),
      })}
      ${renderDiagRow("Wolne", formatBytes(freeInternal), { mono: true })}
      ${renderDiagRow("Min. wolne", formatBytes(minInternal), { mono: true })}
      ${renderDiagRow("Max blok", formatBytes(largestInternal), { mono: true })}`
    : `${renderDiagRow("Wolne", formatBytes(freeInternal), { mono: true })}
      ${renderDiagRow("Min. wolne", formatBytes(minInternal), { mono: true })}
      ${renderDiagRow("Max blok", formatBytes(largestInternal), { mono: true })}`;

  const allocBody = psramOn
    ? `${renderDiagRow("Bufor serial", serialLineBytes ? `${formatBytes(serialLineBytes)} · ${serialInPsram ? "PSRAM" : "DRAM"}` : "—", { mono: true })}
      ${renderDiagRow("caps alloc", memory.spiram_caps_alloc ? "tak" : "nie")}
      ${renderDiagRow("malloc→PSRAM", memory.spiram_malloc ? "tak" : "nie")}`
    : `<p class="diag-note">Brak PSRAM w buildzie.</p>`;

  return `<div class="diag-panel">
    ${renderDiagSection("Połączenie", `
      <div class="diag-inline-grid">
        ${renderDiagRow("Status", connected ? "OK" : "brak", { warn: !connected })}
        ${renderDiagRow("Port", port, { mono: true })}
        ${renderDiagRow("Profil", boardProfile, { mono: true })}
        ${renderDiagRow("PSRAM", psramOn ? "włączony" : "wyłączony")}
      </div>
    `)}
    <div class="diag-columns">
      <div class="diag-col">
        ${renderDiagSection("PSRAM", psramBody)}
        ${renderDiagSection("Alokacje", allocBody)}
      </div>
      <div class="diag-col">
        ${renderDiagSection("DRAM", dramBody)}
        ${renderDiagSection("Stos main", renderDiagMeter("Zajęty", stackUsed, stackTotal, {
          tone: stackFree < 1024 ? "warn" : "accent",
          detail: `${formatBytes(stackFree)} wolne / ${formatBytes(stackTotal)}`,
        }))}
        ${renderDiagSection("Runtime", `
          ${renderDiagRow("Tryb", mode)}
          ${renderDiagRow("Stan", runState)}
          ${renderDiagRow("Krok", runtime.step ?? "—", { mono: true })}
          ${renderDiagRow("Seed", runtime.seed ?? startup.seed ?? "—", { mono: true })}
        `)}
      </div>
    </div>
  </div>`;
}

async function refreshDiagnosticsView(refreshDevice = true) {
  const query = refreshDevice && lastState?.connected ? "?refresh=1" : "";
  try {
    diagnosticsSnapshot = await api(`/api/diagnostics${query}`);
  } catch (err) {
    diagnosticsSnapshot = `Błąd: ${friendlyError(err.message)}`;
  }
  if (activeModal === "diagnostics") refreshModalContent({ force: refreshDevice });
}

async function openDiagnosticsModal() {
  await refreshDiagnosticsView(true);
  openModal("diagnostics");
}
