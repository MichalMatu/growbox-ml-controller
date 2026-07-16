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

function formatUsageDetailParts(used, total) {
  return {
    bytes: `${formatBytes(used)} / ${formatBytes(total)}`,
    pct: formatUsagePct(used, total),
  };
}

function renderDiagMeterValue(used, total, { detail = "", compact = false } = {}) {
  const fullText = detail || formatUsageDetail(used, total);
  const titleAttr = ` title="${escapeHtml(fullText)}"`;
  if (compact && !detail) {
    const parts = formatUsageDetailParts(used, total);
    return `<span class="diag-meter-value diag-meter-value--split"${titleAttr}>
      <span class="diag-meter-bytes">${escapeHtml(parts.bytes)}</span>
      <span class="diag-meter-pct">${escapeHtml(parts.pct)}</span>
    </span>`;
  }
  return `<span class="diag-meter-value"${titleAttr}>${escapeHtml(fullText)}</span>`;
}

function renderDiagMeter(label, used, total, { tone = "accent", detail = "", showLabel = true, compact = false } = {}) {
  const pct = formatDiagPercent(used, total);
  const barPct = used > 0 && pct < 1 ? Math.max(pct, 0.8) : pct;
  const fillCls = ["diag-meter-fill", tone, used > 0 ? "has-use" : ""].filter(Boolean).join(" ");
  const headClass = showLabel ? "diag-meter-head" : "diag-meter-head diag-meter-head--solo";
  const labelMarkup = showLabel
    ? `<span class="diag-meter-label">${escapeHtml(label)}</span>`
    : "";
  return `<div class="diag-meter">
    <div class="${headClass}">
      ${labelMarkup}
      ${renderDiagMeterValue(used, total, { detail, compact })}
    </div>
    <div class="diag-meter-track" aria-hidden="true">
      <span class="${fillCls}" style="width:${barPct}%"></span>
    </div>
  </div>`;
}

function renderDiagTableRow(row) {
  if (row.meter) {
    const meter = renderDiagMeter(row.label, row.used, row.total, {
      tone: row.tone,
      detail: row.detail,
      showLabel: false,
      compact: !row.detail,
    });
    return `<tr><th scope="row">${escapeHtml(row.label)}</th><td class="num diag-meter-cell">${meter}</td></tr>`;
  }
  const rowCls = row.warn ? " class=\"invalid\"" : "";
  const value = row.mono
    ? `<strong>${escapeHtml(String(row.value ?? "—"))}</strong>`
    : escapeHtml(String(row.value ?? "—"));
  return `<tr${rowCls}><th scope="row">${escapeHtml(row.label)}</th><td class="num">${value}</td></tr>`;
}

function renderDiagTable(title, rows, { valueHead = "Wartość" } = {}) {
  const body = rows.map(renderDiagTableRow).join("");
  return `<div class="live-sensor-col">
    <div class="live-data-table-wrap">
      <table class="live-data-table diag-data-table" aria-label="${escapeHtml(title)}">
        <colgroup>
          <col class="sensor-col" />
          <col class="reading-col" />
        </colgroup>
        <thead>
          <tr>
            <th scope="col" class="sensor-col live-table-group-head">${escapeHtml(title)}</th>
            <th scope="col" class="num">${escapeHtml(valueHead)}</th>
          </tr>
        </thead>
        <tbody>${body}</tbody>
      </table>
    </div>
  </div>`;
}

function formatDiagnosticsHtml(snapshot) {
  if (!snapshot) {
    return `<p class="diag-note">Brak danych — połącz płytkę i kliknij <strong>Odśwież</strong>.</p>`;
  }
  if (typeof snapshot === "string") {
    return `<p class="diag-note diag-error">${escapeHtml(snapshot)}</p>`;
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
  const stackTotal = Number(task.main_stack_size_bytes) || 16384;
  const stackUsed = stackFree > 0 ? Math.max(0, stackTotal - stackFree) : 0;
  const connected = Boolean(snapshot.connected);
  const port = (snapshot.port || "—").replace("/dev/cu.", "");
  const mode = runtime.mode === "replay" ? "Replay" : runtime.mode === "closed_loop" ? "Loop" : "—";
  const runState = runtime.paused === false ? "działa" : "pauza";
  const serialLineBytes = Number(memory.serial_line_bytes) || 0;
  const serialInPsram = memory.serial_line_in_psram === true;

  const connection = renderDiagTable("Połączenie", [
    { label: "Status", value: connected ? "OK" : "brak", warn: !connected },
    { label: "Port", value: port, mono: true },
    { label: "Profil", value: boardProfile, mono: true },
    { label: "PSRAM", value: psramOn ? "włączony" : "wyłączony" },
    { label: "Tryb", value: mode },
    { label: "Stan", value: runState },
    { label: "Krok", value: runtime.step ?? "—", mono: true },
    { label: "Seed", value: runtime.seed ?? startup.seed ?? "—", mono: true },
  ]);

  const psramRows = psramOn
    ? [
        {
          label: "Zajęte",
          meter: true,
          used: usedPsram,
          total: totalPsram,
          tone: usedPsram / totalPsram > 0.85 ? "warn" : "ok",
          detail: formatUsageDetail(usedPsram, totalPsram),
        },
        { label: "Wolne", value: formatBytes(freePsram), mono: true },
        { label: "Max blok", value: formatBytes(heap.largest_free_psram), mono: true },
        { label: "Min. wolne", value: formatBytes(heap.min_free_psram), mono: true },
        {
          label: "Bufor serial",
          value: serialLineBytes ? `${formatBytes(serialLineBytes)} · ${serialInPsram ? "PSRAM" : "DRAM"}` : "—",
          mono: true,
        },
        { label: "caps alloc", value: memory.spiram_caps_alloc ? "tak" : "nie" },
        { label: "malloc→PSRAM", value: memory.spiram_malloc ? "tak" : "nie" },
      ]
    : [{ label: "PSRAM", value: "niedostępny" }];
  const psram = renderDiagTable("PSRAM", psramRows);

  const dramRows = [];
  if (totalInternal > 0) {
    dramRows.push({
      label: "Zajęte",
      meter: true,
      used: usedInternal,
      total: totalInternal,
      tone: usedInternal / totalInternal > 0.85 ? "warn" : "accent",
      detail: formatUsageDetail(usedInternal, totalInternal),
    });
  }
  dramRows.push(
    { label: "Wolne", value: formatBytes(freeInternal), mono: true },
    { label: "Min. wolne", value: formatBytes(minInternal), mono: true },
    { label: "Max blok", value: formatBytes(largestInternal), mono: true },
    {
      label: "Stos main",
      meter: true,
      used: stackUsed,
      total: stackTotal,
      tone: stackFree < 1024 ? "warn" : "accent",
      detail: `${formatBytes(stackFree)} wolne / ${formatBytes(stackTotal)}`,
    },
  );
  const dram = renderDiagTable("DRAM", dramRows);

  return `<div class="live-sensors-split diag-split" aria-label="Zasoby płytki">${connection}${psram}${dram}</div>`;
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
