"use strict";
// HiveLens Enterprise Telemetry UI. Buildless, dependency-free, local-only assets.

/* ── Helpers ─────────────────────────────────────────────────────────── */
const $ = (id) => document.getElementById(id);
const esc = (value) =>
  String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

const ICONS = {
  scan: '<path d="M8 3H5a2 2 0 0 0-2 2v3m13-5h3a2 2 0 0 1 2 2v3M3 16v3a2 2 0 0 0 2 2h3m8 0h3a2 2 0 0 0 2-2v-3M7 12h10"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  search: '<circle cx="11" cy="11" r="6.5"/><path d="m16 16 4.5 4.5"/>',
  hive: '<path d="m12 3 8 4.5v9L12 21l-8-4.5v-9Z"/><path d="M8 10h8M8 14h8"/>',
  check: '<path d="m5 12 4.5 4.5L19 7"/>',
  alert: '<path d="M12 4 2.5 20h19Z"/><path d="M12 10v4m0 3v.01"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.5 1.5m11 11L19 19M5 19l1.5-1.5m11-11L19 5"/>',
  moon: '<path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8Z"/>',
  upload: '<path d="M12 15V3M7 8l5-5 5 5M4 15v4a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-4"/>',
  download: '<path d="M12 3v12m-5-5 5 5 5-5M4 15v4a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-4"/>',
  close: '<path d="m6 6 12 12M6 18 18 6"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v6m0-10v.01"/>',
  arrow: '<path d="M5 12h14m-6-6 6 6-6 6"/>',
  external: '<path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/>',
  sort: '<path d="M8 4v16m0 0-3-3m3 3 3-3M16 20V4m0 0-3 3m3-3 3 3"/>',
  grid: '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
  activity: '<path d="M22 12h-4l-3 9L9 3l-3 9H2"/>',
  chart: '<path d="M4 20h16M7 16v-5M12 16V7M17 16v-8"/>',
  layers: '<path d="m12 2 10 5-10 5L2 7l10-5Z"/><path d="m2 12 10 5 10-5"/><path d="m2 17 10 5 10-5"/>',
  microscope: '<path d="M6 18h8M3 21h18M14 21a7 7 0 1 0 0-14h-1M9 14h2M9 12a2 2 0 0 1-2-2V6h6v4a2 2 0 0 1-2 2Z"/>',
};
const icon = (name) => `<svg class="icon" viewBox="0 0 24 24" aria-hidden="true">${ICONS[name] || ICONS.hive}</svg>`;
const hydrateIcons = (root = document) =>
  root.querySelectorAll("[data-icon]").forEach((el) => {
    el.innerHTML = icon(el.dataset.icon);
  });

const VIEWS = {
  overview: "Fleet Overview",
  inspect: "New Inspection",
  history: "Colony Records & Audit",
  benchmark: "Validation Benchmark",
  method: "System Architecture",
};
const STATUS = { good: "Normal", watch: "Watch", act: "Critical", unknown: "Uninspected" };
const statusOf = (s) => (Object.hasOwn(STATUS, s) ? s : "unknown");
const badge = (s) => `<span class="badge ${statusOf(s)}">${STATUS[statusOf(s)]}</span>`;

const num = (value, digits = 1) =>
  value == null || !Number.isFinite(Number(value))
    ? "—"
    : new Intl.NumberFormat("en", { maximumFractionDigits: digits }).format(value);
const dateLabel = (value, withYear = true) =>
  value
    ? new Date(`${value.slice(0, 10)}T12:00:00`).toLocaleDateString("en-GB", {
        day: "2-digit",
        month: "short",
        ...(withYear ? { year: "numeric" } : {}),
      })
    : "—";
const localDate = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};
const store = {
  get(key, fallback = null) {
    try {
      return JSON.parse(localStorage.getItem(`hivelens:${key}`)) ?? fallback;
    } catch {
      return fallback;
    }
  },
  set(key, value) {
    try {
      localStorage.setItem(`hivelens:${key}`, JSON.stringify(value));
    } catch {
      /* storage unavailable */
    }
  },
};
const jobSession = {
  get() {
    try {
      return JSON.parse(sessionStorage.getItem("hivelens:job"));
    } catch {
      return null;
    }
  },
  set(job) {
    try {
      job ? sessionStorage.setItem("hivelens:job", JSON.stringify(job)) : sessionStorage.removeItem("hivelens:job");
    } catch {
      /* ignore */
    }
  },
};

/* ── Corporate Theme Toggle (Default: Light Enterprise) ──────────────── */
function applyTheme(theme) {
  const t = theme === "dark" ? "dark" : "light";
  document.documentElement.setAttribute("data-theme", t);
  const btn = $("theme-toggle");
  if (btn) btn.innerHTML = `${icon(t === "dark" ? "sun" : "moon")}<span>${t === "dark" ? "Light" : "Dark"}</span>`;
  store.set("corp_theme", t);
}

/* ── State ───────────────────────────────────────────────────────────── */
let state = null;
let view = "overview";
let selectedHive = store.get("hive");
let statusFilter = "all";
let sortAscending = true;
let historyController = null;
let historyData = null;
let historyHive = null;
let selectedRecord = null;
let boardFile = null;
let frameFiles = [];
let previewUrls = [];
let previewGeneration = 0;
let activeJob = null;
let eventStream = null;
let startingJob = false;
let toastTimer;
const thumbnailCache = new WeakMap();

const hives = () => state?.apiary?.hives || [];
const isSynthetic = (h) => h.synthetic === true || /\(synthetic\)/i.test(h.name || "");
const displayName = (h) => (h.name || "").replace(/\s*\(synthetic\)/gi, "");
const hiveName = (id) => {
  const h = state?.hives.find((x) => x.id === id);
  return h ? displayName(h) : id;
};

function toast(message, error = false) {
  clearTimeout(toastTimer);
  const el = $("toast");
  el.textContent = message;
  el.classList.toggle("error", error);
  el.hidden = false;
  toastTimer = setTimeout(() => (el.hidden = true), error ? 8000 : 4000);
}

async function api(path, body, signal) {
  const controller = signal ? null : new AbortController();
  const timer = controller ? setTimeout(() => controller.abort(), path === "/api/commons" ? 180000 : 60000) : null;
  try {
    const response = await fetch(path, {
      signal: signal || controller.signal,
      ...(body === undefined
        ? {}
        : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }),
    });
    const data = await response.json();
    if (!response.ok || data.error) throw new Error(data.error || `Request failed (${response.status})`);
    return data;
  } finally {
    clearTimeout(timer);
  }
}

async function withButton(button, task) {
  if (button.disabled) return;
  button.disabled = true;
  try {
    await task();
  } catch (e) {
    toast(e.name === "AbortError" ? "The request timed out. Try again." : e.message, true);
  } finally {
    button.disabled = false;
  }
}

const emptyState = (title, text, action = "") =>
  `<div class="empty">${icon("hive")}<h3>${esc(title)}</h3><p>${esc(text)}</p>${action}</div>`;

/* ── Routing ─────────────────────────────────────────────────────────── */
function go(next) {
  if (location.hash === `#${next}`) route();
  else location.hash = next;
}

function route() {
  const next = location.hash.slice(1);
  if (next === "main") return;
  view = Object.hasOwn(VIEWS, next) ? next : "overview";
  for (const key of Object.keys(VIEWS)) {
    $(`view-${key}`).hidden = key !== view;
    const link = document.querySelector(`[data-nav="${key}"]`);
    link.classList.toggle("active", key === view);
    key === view ? link.setAttribute("aria-current", "page") : link.removeAttribute("aria-current");
  }
  $("topbar-title").textContent = VIEWS[view];
  document.title = `${VIEWS[view]} · HiveLens`;
  window.scrollTo({ top: 0, behavior: "instant" });
  renderView();
}

function renderView() {
  if (!state) return;
  if (view === "overview") renderOverview();
  if (view === "inspect") updateSummary();
  if (view === "history") loadHistory();
  if (view === "benchmark") renderBenchmark();
}

async function loadState() {
  try {
    state = await api("/api/state");
    $("load-error").hidden = true;
    const measuredHives = state.apiary?.hives?.filter((h) => !isSynthetic(h)) || [];
    if (!state.hives.some((h) => h.id === selectedHive)) {
      selectedHive = measuredHives[0]?.id || state.hives[0]?.id || null;
    }
    const conn = $("api-state");
    conn.innerHTML = `<i></i>${state.has_api_key ? "ONLINE" : "NO KEY"}`;
    conn.classList.toggle("offline", !state.has_api_key);
    conn.title = state.has_api_key
      ? `Meta Model API active: ${state.segment_model} + ${state.reasoning_model}`
      : "Set MODEL_API_KEY in .env to run an analysis.";
    $("version").textContent = state.version ? `v${state.version}` : "v0.1";
    $("models").textContent = `${state.segment_model} · ${state.reasoning_model}`;
    syncHiveSelects();
    populateSamples();
    renderView();
    updateRunButtons();
    return true;
  } catch (e) {
    $("load-error-text").textContent = `Could not load the workspace. ${e.message}`;
    $("load-error").hidden = false;
    $("api-state").innerHTML = "<i></i>OFFLINE";
    $("api-state").classList.add("offline");
    return false;
  }
}

function syncHiveSelects() {
  const byId = Object.fromEntries((state.apiary?.hives || []).map((h) => [h.id, h]));
  const sorted = [...state.hives].sort((a, b) => {
    const sa = isSynthetic(byId[a.id] || a);
    const sb = isSynthetic(byId[b.id] || b);
    if (sa !== sb) return sa ? 1 : -1;
    return a.name.localeCompare(b.name, undefined, { numeric: true });
  });
  const options = sorted.length
    ? sorted
        .map((h) => {
          const syn = isSynthetic(byId[h.id] || h);
          return `<option value="${esc(h.id)}">${esc(displayName(h))} [${syn ? "SYNTHETIC" : "MEASURED"}]</option>`;
        })
        .join("")
    : '<option value="">No colonies registered</option>';
  for (const id of ["inspection-hive", "history-hive"]) {
    $(id).innerHTML = options;
    $(id).value = selectedHive || "";
  }

  // Update Topbar Context Pill & Left Sidebar Colony List
  const activeObj = byId[selectedHive];
  $("topbar-colony-pill").textContent = activeObj
    ? `Colony: ${displayName(activeObj)} (${isSynthetic(activeObj) ? "Synthetic" : "Measured"})`
    : "No colony selected";

  const sideList = $("sidebar-hive-list");
  if (sideList) {
    sideList.innerHTML = sorted
      .map((h) => {
        const info = byId[h.id] || h;
        const s = statusOf(info.overall);
        const mpd = info.mites_per_day != null ? `${num(info.mites_per_day)}/d` : "—";
        return `<button type="button" class="side-hive-btn ${h.id === selectedHive ? "active" : ""}" data-hive="${esc(h.id)}" data-destination="history">
          <span class="side-hive-left"><i class="dot ${s}"></i><span class="side-hive-name">${esc(displayName(h))}</span></span>
          <span class="side-hive-meta">${esc(mpd)}</span>
        </button>`;
      })
      .join("");
  }
}

function selectHive(id, destination) {
  if (!state?.hives.some((h) => h.id === id)) return;
  if (id !== selectedHive) selectedRecord = null;
  selectedHive = id;
  store.set("hive", id);
  syncHiveSelects();
  updateSummary();
  if (destination) go(destination);
  else if (view === "history") loadHistory();
}

/* ── Fleet Overview & Spatial Matrix ─────────────────────────────────── */
function kpi(label, value, note, dot = "") {
  return `<div class="kpi"><div class="kpi-label">${dot ? `<i class="dot ${dot}"></i>` : ""}${esc(label)}</div><div class="kpi-value">${esc(value)}</div><div class="kpi-note">${esc(note)}</div></div>`;
}

function renderSpatialMap(all, links) {
  const mapEl = $("apiary-map-svg");
  const sideEl = $("apiary-drift-panel");
  if (!all.length) {
    $("apiary-map-card").hidden = true;
    return;
  }
  $("apiary-map-card").hidden = false;

  const xs = all.map((h) => h.x_m || 0);
  const ys = all.map((h) => h.y_m || 0);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs, minX + 5);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys, minY + 3);

  const W = 720;
  const H = 280;
  const padX = 72;
  const padY = 52;
  const sx = (x) => padX + ((x - minX) / Math.max(1, maxX - minX)) * (W - padX * 2);
  const sy = (y) => padY + ((y - minY) / Math.max(1, maxY - minY)) * (H - padY * 2);

  const byId = Object.fromEntries(all.map((h) => [h.id, h]));
  const colorMap = {
    good: "var(--good)",
    watch: "var(--watch)",
    act: "var(--act)",
    unknown: "var(--muted)",
  };

  let gridSvg = "";
  for (let gx = 0; gx <= Math.ceil(maxX); gx += 2.5) {
    const px = sx(gx);
    gridSvg += `<line x1="${px.toFixed(1)}" y1="16" x2="${px.toFixed(1)}" y2="${H - 22}" stroke="var(--border)" stroke-dasharray="2 3"/>`;
    gridSvg += `<text x="${px.toFixed(1)}" y="${H - 6}" text-anchor="middle" fill="var(--muted)" font-size="10" font-family="var(--mono)">${gx.toFixed(1)}m</text>`;
  }

  const vecSvg = (links || [])
    .map((l) => {
      const a = byId[l.from_id];
      const b = byId[l.to_id];
      if (!a || !b) return "";
      const x1 = sx(a.x_m);
      const y1 = sy(a.y_m);
      const x2 = sx(b.x_m);
      const y2 = sy(b.y_m);
      const mx = (x1 + x2) / 2;
      const my = (y1 + y2) / 2 - 8;
      const col = l.risk === "high" ? "var(--act)" : "var(--watch)";
      return `<g>
        <line x1="${x1.toFixed(1)}" y1="${y1.toFixed(1)}" x2="${x2.toFixed(1)}" y2="${y2.toFixed(1)}" stroke="${col}" stroke-width="1.75" class="drift-vec"/>
        <rect x="${(mx - 20).toFixed(1)}" y="${(my - 7).toFixed(1)}" width="40" height="14" rx="2" fill="var(--surface)" stroke="${col}" stroke-width="1"/>
        <text x="${mx.toFixed(1)}" y="${(my + 3).toFixed(1)}" text-anchor="middle" fill="${col}" font-size="9" font-family="var(--mono)" font-weight="600">${l.distance_m}m</text>
      </g>`;
    })
    .join("");

  const nodesSvg = all
    .map((h) => {
      const cx = sx(h.x_m);
      const cy = sy(h.y_m);
      const s = statusOf(h.overall);
      const col = colorMap[s];
      const measured = !isSynthetic(h);
      const shortName = displayName(h).split("·")[0].trim();
      const mpd = h.mites_per_day != null ? `${num(h.mites_per_day)}/d` : "—";
      return `<g class="map-node" data-hive="${esc(h.id)}" data-destination="history">
        <title>${esc(displayName(h))} (${measured ? "Measured" : "Synthetic"}) · ${mpd} mites/day</title>
        <rect x="${(cx - 32).toFixed(1)}" y="${(cy - 20).toFixed(1)}" width="64" height="40" rx="4" fill="var(--surface)" stroke="${col}" stroke-width="${measured ? 2.2 : 1.5}"/>
        <text x="${cx.toFixed(1)}" y="${(cy - 4).toFixed(1)}" text-anchor="middle" fill="var(--text)" font-size="10" font-weight="600">${esc(shortName)}</text>
        <text x="${cx.toFixed(1)}" y="${(cy + 10).toFixed(1)}" text-anchor="middle" fill="${col}" font-size="9.5" font-family="var(--mono)" font-weight="600">${esc(mpd)}</text>
      </g>`;
    })
    .join("");

  mapEl.innerHTML = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Spatial apiary coordinate matrix">${gridSvg}${vecSvg}${nodesSvg}</svg>`;

  let sideHtml = `<h4>Contagion Risk Links (${(links || []).length})</h4>`;
  if (links?.length) {
    sideHtml += links
      .map(
        (l) => `<button type="button" class="drift-item ${l.risk === "high" ? "high" : ""}" data-hive="${esc(l.to_id)}" data-destination="history" style="text-align:left">
          <div class="drift-item-top"><span>${esc(l.from_name.replace(/\s*\(synthetic\)/i, ""))} → ${esc(l.to_name.replace(/\s*\(synthetic\)/i, ""))}</span><span class="tag">${l.distance_m} m</span></div>
          <small>Exposure: ${esc(l.risk.toUpperCase())} · Source drop: ${num(byId[l.from_id]?.mites_per_day)}/d</small>
        </button>`,
      )
      .join("");
  } else {
    sideHtml += `<p class="hint">No active mite-drift contagion links within 4.0 m.</p>`;
  }
  sideEl.innerHTML = sideHtml;
}

function renderOverview() {
  const all = hives();
  const count = (s) => all.filter((h) => h.overall === s).length;
  const measuredCount = all.filter((h) => !isSynthetic(h)).length;
  const driftRiskCount = state?.apiary?.summary?.at_drift_risk ?? 0;
  const inspections = all.reduce((n, h) => n + h.inspection_count, 0);

  $("overview-stats").innerHTML =
    kpi("Monitored Colonies", all.length, `${measuredCount} measured · ${all.length - measuredCount} synthetic`, "") +
    kpi("Normal Status", count("good"), "Within threshold (<3.0/d)", "good") +
    kpi("Watch Status", count("watch"), "Elevated drop (3.0–9.9/d)", "watch") +
    kpi("Critical Action", count("act"), "Above threshold (≥10.0/d)", "act") +
    kpi("Drift Exposure", driftRiskCount, `${inspections} total inspection records`, "watch");

  const urgent = all.filter((h) => h.overall === "act").sort((a, b) => Number(isSynthetic(a)) - Number(isSynthetic(b)));
  $("attention").hidden = !urgent.length;
  $("attention").innerHTML = urgent.length
    ? `<div class="attention-head">${icon("alert")}Critical Action Required (${urgent.length})</div>` +
      urgent
        .map(
          (h) =>
            `<button class="attention-row" type="button" data-hive="${esc(h.id)}" data-destination="history"><strong>${esc(displayName(h))}</strong><span>${esc(h.flags?.[0] || "Review latest inspection.")}</span>${icon("arrow")}</button>`,
        )
        .join("")
    : "";

  renderSpatialMap(all, state?.apiary?.drift_links || []);

  const filters = [
    ["all", "All", all.length],
    ["act", "Critical", count("act")],
    ["watch", "Watch", count("watch")],
    ["good", "Normal", count("good")],
    ["unknown", "Uninspected", count("unknown")],
  ];
  $("status-filter").innerHTML = filters
    .map(
      ([key, label, n]) =>
        `<button type="button" data-filter="${key}" aria-pressed="${statusFilter === key}">${label}<span class="n">${n}</span></button>`,
    )
    .join("");
  renderHiveGrid();
}

function renderHiveGrid() {
  const all = hives();
  const query = $("hive-search").value.toLocaleLowerCase().trim();
  const source = $("source-filter").value;
  const list = all
    .filter(
      (h) =>
        (!query || `${h.name} ${h.location}`.toLocaleLowerCase().includes(query)) &&
        (statusFilter === "all" || statusOf(h.overall) === statusFilter) &&
        (source === "all" || (source === "synthetic" ? isSynthetic(h) : !isSynthetic(h))),
    )
    .sort((a, b) => {
      const synA = isSynthetic(a);
      const synB = isSynthetic(b);
      if (synA !== synB) return synA ? 1 : -1;
      return a.name.localeCompare(b.name, undefined, { numeric: true }) * (sortAscending ? 1 : -1);
    });

  $("hive-grid").innerHTML = list.map(hiveRow).join("");
  $("hive-empty").hidden = list.length > 0;
  $("hive-empty").innerHTML = all.length
    ? `${icon("search")}<h3>No matching records</h3><p>Adjust your search query, status filter, or data source selector.</p>`
    : `${icon("hive")}<h3>No colonies registered</h3><p>Register a colony to begin recording inspections.</p><button class="btn primary sm" type="button" data-add-hive>${icon("plus")}Register Colony</button>`;
}

function hiveRow(h) {
  const s = statusOf(h.overall);
  const syn = isSynthetic(h);
  const change = h.mites_per_day_change;
  const delta =
    change != null && Math.abs(change) >= 0.05
      ? `<span class="delta ${change > 0 ? "up" : ""}">${change > 0 ? "+" : "−"}${num(Math.abs(change))}</span>`
      : '<span class="muted">—</span>';
  return `<tr class="${syn ? "" : "measured-row"}">
    <td class="strong"><a href="#history" data-hive="${esc(h.id)}" data-destination="history" style="text-decoration:none">${esc(displayName(h))}</a></td>
    <td class="muted">${esc(h.location || "—")}</td>
    <td>${syn ? '<span class="tag demo">Synthetic</span>' : '<span class="tag measured">Measured</span>'}</td>
    <td>${badge(s)}</td>
    <td class="num strong">${h.mites_per_day != null ? `${num(h.mites_per_day)} /d` : "—"}</td>
    <td class="num">${delta}</td>
    <td class="num">${h.honey_kg_hive_est != null ? `${num(h.honey_kg_hive_est)} kg` : "—"}</td>
    <td class="num">${h.brood_total_pct != null ? `${num(h.brood_total_pct)}%` : "—"}</td>
    <td class="num">${h.stores_weeks != null ? `${num(h.stores_weeks)} wk` : "—"}</td>
    <td class="muted">${h.latest_date ? `${esc(dateLabel(h.latest_date))} (${h.inspection_count})` : "None"}</td>
    <td class="num"><button type="button" class="btn sm" data-hive="${esc(h.id)}" data-destination="history">Open Dossier</button></td>
  </tr>`;
}

/* ── New Inspection ──────────────────────────────────────────────────── */
function populateSamples() {
  const previous = $("board-sample").value;
  const checked = new Set([...document.querySelectorAll(".frame-sample:checked")].map((el) => el.value));
  $("board-sample").innerHTML =
    '<option value="">— None selected —</option>' +
    state.samples.boards
      .map((b) => `<option value="${esc(b.name)}">${esc(b.name)}${b.experts == null ? "" : ` (${b.experts} expert mites)`}</option>`)
      .join("");
  if (state.samples.boards.some((b) => b.name === previous)) $("board-sample").value = previous;
  $("frame-samples").innerHTML = state.samples.frames.length
    ? state.samples.frames
        .map(
          (f) =>
            `<label class="sample-tile" title="${esc(f.name.replaceAll("_", " "))}"><input type="checkbox" class="frame-sample" value="${esc(f.name)}" ${checked.has(f.name) ? "checked" : ""} aria-label="${esc(f.name)}"><img src="/api/sample_preview/frame/${encodeURIComponent(f.name)}?max_side=240" alt="" loading="lazy" decoding="async"></label>`,
        )
        .join("")
    : '<p class="hint">No reference frames downloaded.</p>';
}

const draftFields = ["inspection-days", "inspection-frames", "inspection-note", "inspection-depth", "inspection-agent"];
function saveDraft() {
  const draft = {};
  for (const id of draftFields) draft[id] = $(id).type === "checkbox" ? $(id).checked : $(id).value;
  store.set("draft", draft);
}
function restoreDraft() {
  $("inspection-date").value = localDate();
  const draft = store.get("draft", {});
  for (const id of draftFields) {
    if (draft[id] === undefined) continue;
    if ($(id).type === "checkbox") $(id).checked = Boolean(draft[id]);
    else $(id).value = draft[id];
  }
}

const checkedFrameSamples = () => [...document.querySelectorAll(".frame-sample:checked")].map((el) => el.value);

function updateSummary() {
  if (!state) return;
  const sample = $("board-sample").value;
  const frames = frameFiles.length + checkedFrameSamples().length;
  const hive = state.hives.find((h) => h.id === selectedHive);
  const row = (label, value, cls = "") => `<li><span>${label}</span><b class="${cls}" title="${esc(value)}">${esc(value)}</b></li>`;
  $("inspect-summary").innerHTML =
    row("Target Colony", hive ? displayName(hive) : "Unselected", hive ? "" : "missing") +
    row("Inspection Date", dateLabel($("inspection-date").value)) +
    row("Sticky Board", boardFile ? boardFile.name : sample ? sample : "None", boardFile || sample ? "ok" : "missing") +
    row("Comb Frames", frames ? `${frames} image${frames === 1 ? "" : "s"}` : "None", frames ? "ok" : "missing") +
    row("Resolution Mode", $("inspection-depth").value === "thorough" ? "Multi-Pass (600/300px)" : "Single-Pass (600px)") +
    row("Claim Audit Gate", $("inspection-agent").checked ? "Enabled" : "Disabled");
  let hint = "";
  if (!state.has_api_key) hint = "Configure MODEL_API_KEY in .env to execute.";
  else if (!hive) hint = "Register a colony first.";
  else if (!boardFile && !sample && !frames) hint = "Provide at least one optical input.";
  else if (activeJob) hint = "Pipeline execution in progress.";
  else hint = "Ready for execution.";
  $("run-hint").textContent = hint;
}

function validateFiles(files) {
  for (const file of files) {
    if (!["image/jpeg", "image/png", "image/webp"].includes(file.type)) throw new Error(`${file.name}: choose a JPG, PNG or WebP image.`);
    if (file.size > 25 * 1024 * 1024) throw new Error(`${file.name}: the limit is 25 MB per photo.`);
    if (!file.size) throw new Error(`${file.name}: this file is empty.`);
  }
}

function setFiles(kind, files) {
  try {
    validateFiles(files);
    if (kind === "board" && files.length > 1) throw new Error("Choose one sticky-board photo at a time.");
    const frames = kind === "frames" ? [...frameFiles, ...files] : frameFiles;
    if (frames.length + checkedFrameSamples().length > 8) throw new Error("Choose up to 8 frame photos per inspection.");
    const board = kind === "board" ? files[0] : boardFile;
    if ([board, ...frames].filter(Boolean).reduce((sum, f) => sum + f.size, 0) > 60 * 1024 * 1024)
      throw new Error("Keep the total upload below 60 MB.");
    if (kind === "board") {
      boardFile = board;
      $("board-sample").value = "";
      $("board-sample-info").textContent = "";
    } else frameFiles = frames;
    renderPreviews();
  } catch (e) {
    toast(e.message, true);
  }
  $(`${kind}-file`).value = "";
}

function renderPreviews() {
  const generation = ++previewGeneration;
  previewUrls.forEach((url) => URL.revokeObjectURL(url));
  previewUrls = [];
  const preview = (src, name, kind, index, local = false) =>
    `<div class="preview"><button type="button" data-image="${esc(src)}" aria-label="View ${esc(name)}"><img ${local ? "data-local-preview" : `src="${esc(src)}"`} alt="" decoding="async"></button><button type="button" class="remove" data-remove="${kind}" data-index="${esc(index)}" aria-label="Remove ${esc(name)}">×</button><small title="${esc(name)}">${esc(name)}</small></div>`;
  const filePreview = (file, kind, index) => {
    const url = URL.createObjectURL(file);
    previewUrls.push(url);
    return preview(url, file.name, kind, index, true);
  };
  const sample = $("board-sample").value;
  $("board-preview").innerHTML = boardFile
    ? filePreview(boardFile, "board", 0)
    : sample
      ? preview(`/api/sample_preview/board/${encodeURIComponent(sample)}?max_side=600`, sample, "sample-board", 0)
      : "";
  $("frames-preview").innerHTML =
    frameFiles.map((f, i) => filePreview(f, "frames", i)).join("") +
    checkedFrameSamples()
      .map((name) => preview(`/api/sample_preview/frame/${encodeURIComponent(name)}?max_side=400`, name, "sample-frame", name))
      .join("");
  buildLocalPreviews([boardFile, ...frameFiles].filter(Boolean), generation);
  updateSummary();
}

async function buildLocalPreviews(files, generation) {
  const images = [...document.querySelectorAll("[data-local-preview]")];
  for (let i = 0; i < files.length; i++) {
    if (generation !== previewGeneration) return;
    const file = files[i];
    const image = images[i];
    if (!image) return;
    try {
      let thumbnail = thumbnailCache.get(file);
      if (!thumbnail) {
        const bitmap = await createImageBitmap(file, { resizeWidth: 320, resizeQuality: "medium" });
        try {
          const canvas = document.createElement("canvas");
          canvas.width = bitmap.width;
          canvas.height = bitmap.height;
          canvas.getContext("2d").drawImage(bitmap, 0, 0);
          thumbnail = await new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.8));
        } finally {
          bitmap.close();
        }
        if (!thumbnail) throw new Error("Preview unavailable");
        thumbnailCache.set(file, thumbnail);
      }
      if (generation !== previewGeneration) return;
      const url = URL.createObjectURL(thumbnail);
      previewUrls.push(url);
      image.src = url;
    } catch {
      if (generation === previewGeneration) image.src = image.closest("button").dataset.image;
    }
  }
}

function readBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(new Error(`Could not read ${file.name}`));
    reader.readAsDataURL(file);
  });
}

function updateRunButtons() {
  const disabled = Boolean(activeJob || startingJob || !state?.has_api_key);
  $("run-inspection").disabled = disabled;
  $("run-benchmark").disabled = disabled;
  updateSummary();
}

async function startInspection(event) {
  event.preventDefault();
  if (activeJob || startingJob) return;
  if (!$("inspection-form").reportValidity()) return;
  if (!selectedHive) return toast("Register a colony before starting an inspection.", true);
  const sample = $("board-sample").value;
  const frameSamples = checkedFrameSamples();
  if (!boardFile && !sample && !frameFiles.length && !frameSamples.length)
    return toast("Add at least one sticky-board or frame image.", true);
  if (frameFiles.length + frameSamples.length > 8) return toast("Choose up to 8 frame photos per inspection.", true);

  startingJob = true;
  updateRunButtons();
  const hiveId = selectedHive;
  const files = [...frameFiles];
  const board = boardFile;
  const payload = {
    hive_id: hiveId,
    date: $("inspection-date").value,
    days_on_board: Number($("inspection-days").value),
    frames_in_hive: Number($("inspection-frames").value),
    board_refine: $("inspection-depth").value === "thorough",
    note: $("inspection-note").value,
    use_agent: $("inspection-agent").checked,
    board_sample: sample || null,
    frame_samples: frameSamples,
  };
  try {
    toast("Submitting optical inputs…");
    payload.board_b64 = board ? await readBase64(board) : null;
    payload.frames_b64 = [];
    for (const file of files) payload.frames_b64.push(await readBase64(file));
    const result = await api("/api/inspect", payload);
    $("inspection-result").innerHTML = "";
    attachJob({ id: result.job_id, kind: "inspection", hiveId });
  } catch (e) {
    toast(e.message, true);
  } finally {
    startingJob = false;
    updateRunButtons();
  }
}

/* ── Live Jobs (SSE) ─────────────────────────────────────────────────── */
function logJob(text) {
  const feed = $("job-feed");
  const line = document.createElement("div");
  line.textContent = text;
  const nearBottom = feed.scrollHeight - feed.scrollTop - feed.clientHeight < 50;
  feed.append(line);
  while (feed.childElementCount > 200) feed.firstElementChild.remove();
  if (nearBottom) feed.scrollTop = feed.scrollHeight;
}

function setProgress(pct) {
  $("job-bar").style.width = `${pct}%`;
  $("job-progress").setAttribute("aria-valuenow", pct);
  $("job-pct").textContent = `${pct}%`;
}

function finishJob(message, failed = false) {
  eventStream?.close();
  eventStream = null;
  activeJob = null;
  jobSession.set(null);
  updateRunButtons();
  $("job-title").textContent = message;
  $("job-spinner").className = `spinner ${failed ? "failed" : "done"}`;
  $("job-dismiss").hidden = false;
  if (failed) {
    logJob(message);
    toast(message, true);
  }
}

function attachJob(job) {
  eventStream?.close();
  activeJob = job;
  jobSession.set(job);
  updateRunButtons();
  $("job-panel").hidden = false;
  $("job-dismiss").hidden = true;
  $("job-result-link").hidden = true;
  $("job-spinner").className = "spinner";
  $("job-feed").textContent = "";
  setProgress(0);
  $("job-title").textContent = job.kind === "inspection" ? "Running inspection pipeline…" : "Evaluating benchmark set…";
  const stream = new EventSource(`/api/jobs/${encodeURIComponent(job.id)}/stream`);
  eventStream = stream;
  stream.onmessage = async (message) => {
    if (activeJob?.id !== job.id) return;
    let ev;
    try {
      ev = JSON.parse(message.data);
    } catch {
      return;
    }
    if (ev.type === "progress") {
      setProgress(Math.max(0, Math.min(100, Math.round((ev.frac || 0) * 100))));
      $("job-title").textContent = ev.msg || "Processing…";
    }
    if (ev.type === "log") logJob(ev.text);
    if (ev.type === "agent_event") {
      const a = ev.event || {};
      if (a.type === "claim") logJob(`[${a.verdict.toUpperCase()}] ${a.statement} (${a.reason})`);
      else if (a.type === "thought") logJob(a.text || "");
      else if (a.type === "tool_call") logJob(`call: ${a.name}()`);
    }
    if (ev.type === "error") finishJob(ev.error || "Analysis failed.", true);
    if (ev.type === "done") {
      finishJob(job.kind === "inspection" ? "Inspection saved" : "Evaluation complete");
      setProgress(100);
      const link = $("job-result-link");
      if (job.kind === "inspection") {
        renderRecord(job.hiveId, ev.result, "inspection-result");
        link.href = "#history";
        link.dataset.resultHive = job.hiveId;
        link.dataset.resultRecord = ev.result.id;
        if (view === "inspect") $("inspection-result").scrollIntoView({ behavior: "smooth", block: "start" });
      } else {
        link.href = "#benchmark";
        delete link.dataset.resultHive;
        delete link.dataset.resultRecord;
      }
      await loadState();
      link.hidden = false;
    }
  };
  stream.onerror = () => {
    if (activeJob?.id === job.id) $("job-title").textContent = "Reconnecting stream…";
  };
}

/* ── Colony Records & Audit Trail ────────────────────────────────────── */
async function loadHistory() {
  historyController?.abort();
  const hive = selectedHive;
  if (!hive) {
    $("history-trends").innerHTML = "";
    $("history-list").innerHTML = '<li class="tl-empty">No colonies registered.</li>';
    $("history-count").textContent = "";
    $("history-result").innerHTML = emptyState(
      "No colonies registered",
      "Register a colony, then run an inspection to initialize its record.",
      `<button class="btn primary sm" type="button" data-add-hive>${icon("plus")}Register Colony</button>`,
    );
    $("export-hive").hidden = true;
    return;
  }
  const controller = new AbortController();
  historyController = controller;
  if (historyHive !== hive) {
    $("history-list").innerHTML = '<li class="tl-empty">Loading…</li>';
    $("history-result").innerHTML = "";
    $("history-trends").innerHTML = "";
  }
  try {
    const data = await api(`/api/hive/${encodeURIComponent(hive)}`, undefined, controller.signal);
    if (hive !== selectedHive || controller.signal.aborted) return;
    historyData = data;
    historyHive = hive;
    $("export-hive").href = `/api/export/${encodeURIComponent(hive)}.zip`;
    $("export-hive").hidden = false;
    const link = $("job-result-link");
    if (link.dataset.resultHive === hive && data.inspections.some((r) => r.id === link.dataset.resultRecord)) {
      selectedRecord = link.dataset.resultRecord;
      delete link.dataset.resultRecord;
    }
    if (!data.inspections.some((r) => r.id === selectedRecord)) selectedRecord = data.inspections.at(-1)?.id || null;
    $("history-count").textContent = data.inspections.length || "0";
    if (!data.inspections.length) {
      $("history-trends").innerHTML = "";
      $("history-list").innerHTML = '<li class="tl-empty">No records.</li>';
      $("history-result").innerHTML = emptyState(
        "No inspection records",
        "Submit sticky-board or comb imagery to create the first baseline record.",
        `<button class="btn primary sm" type="button" data-go="inspect">${icon("scan")}New Inspection</button>`,
      );
      return;
    }
    renderTrends(data.metrics_rows || []);
    renderTimeline();
    renderSelectedRecord();
  } catch (e) {
    if (e.name !== "AbortError")
      $("history-result").innerHTML = emptyState(
        "Could not load colony history",
        e.message,
        '<button class="btn sm" type="button" data-retry-history>Retry</button>',
      );
  }
}

function renderTimeline() {
  $("history-list").innerHTML = [...historyData.inspections]
    .reverse()
    .map((rec) => {
      const s = statusOf(rec.status?.overall);
      const mpd = rec.metrics?.mites_per_day;
      const hasEv = Boolean(rec.files?.board_evidence);
      return `<li><button type="button" data-record="${esc(rec.id)}" aria-current="${rec.id === selectedRecord}">
        <i class="tl-dot ${s}"></i>
        <span class="tl-main">
          <strong>${esc(dateLabel(rec.date))}</strong>
          <small>${STATUS[s]}${mpd != null ? ` · ${num(mpd)}/d` : ""}${rec.synthetic ? " · SYNTH" : hasEv ? " · AUDIT" : ""}</small>
        </span>
      </button></li>`;
    })
    .join("");
}

function renderSelectedRecord() {
  if (historyHive !== selectedHive) return;
  const rec = historyData?.inspections.find((r) => r.id === selectedRecord);
  renderRecord(historyHive, rec, "history-result");
}

function sparkline(points, label) {
  const W = 240;
  const H = 48;
  const pad = 5;
  const values = points.map((p) => p.v);
  const max = Math.max(...values);
  const min = Math.min(0, ...values);
  const span = max - min || 1;
  const n = Math.max(1, points.length - 1);
  const xy = points.map((p, i) => [pad + (i / n) * (W - pad * 2), H - pad - ((p.v - min) / span) * (H - pad * 2)]);
  if (xy.length === 1) xy[0][0] = W / 2;
  const line = xy.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
  const area = xy.length > 1 ? `${line} L${xy.at(-1)[0].toFixed(1)},${H - pad} L${xy[0][0].toFixed(1)},${H - pad} Z` : "";
  return `<svg class="spark" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" role="img" aria-label="${esc(label)} trend">${area ? `<path class="area" d="${area}"/>` : ""}<path class="line" d="${line}"/>${xy
    .map(([x, y], i) => `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="2.5"><title>${esc(points[i].date)}: ${num(points[i].v)}</title></circle>`)
    .join("")}</svg>`;
}

function renderTrends(rows) {
  const specs = [
    ["Mite Drop Rate", "mites_per_day", "mites/d", true],
    ["Estimated Honey", "honey_kg_hive_est", "kg", false],
    ["Brood Coverage", "brood_total_pct", "%", false],
    ["Food Reserve", "stores_weeks", "weeks", false],
  ];
  $("history-trends").innerHTML = specs
    .map(([label, key, unit, higherIsWorse]) => {
      const points = rows.map((r) => ({ v: r[key], date: r.date })).filter((p) => p.v != null && Number.isFinite(p.v));
      const latest = points.at(-1)?.v;
      const prev = points.at(-2)?.v;
      let change = "";
      if (latest != null && prev != null && Math.abs(latest - prev) >= 0.05) {
        const up = latest > prev;
        const bad = up === higherIsWorse;
        change = `<span class="${bad ? "trend-up" : "trend-down"}" style="font-size:11.5px;font-weight:600;font-family:var(--mono)">${up ? "+" : "−"}${num(Math.abs(latest - prev))}</span>`;
      }
      return `<div class="panel trend"><div class="trend-top"><span>${label}</span>${change}</div><div class="trend-value">${num(latest)}${latest == null ? "" : `<small>${unit}</small>`}</div>${points.length ? sparkline(points, label) : '<p class="hint" style="height:48px;padding-top:14px">No data</p>'}<div class="trend-dates"><span>${esc(dateLabel(points[0]?.date, false))}</span><span>${esc(dateLabel(points.at(-1)?.date, false))}</span></div></div>`;
    })
    .join("");
}

/* ── Inspection Record Dossier ───────────────────────────────────────── */
function downloadJson(record) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(record, null, 2)], { type: "application/json" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = `hivelens-${record.id || record.date}.json`;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function compositionBar(m) {
  const keys = [
    ["honey", "honey_pct"],
    ["brood", "brood_pct"],
    ["larvae", "larvae_pct"],
    ["pollen", "pollen_pct"],
    ["empty", "empty_pct"],
    ["bees", "bees_pct"],
  ].filter(([, k]) => m[k] != null && Number.isFinite(m[k]));
  if (!keys.length) return "";
  const total = keys.reduce((s, [, k]) => s + Math.max(0, m[k]), 0) || 1;
  const color = (c) => {
    const rgb = state?.class_colors?.[c];
    return rgb ? `rgb(${rgb.join(",")})` : "var(--muted)";
  };
  const label = (c) => state?.class_labels?.[c] || c;
  return `<div class="composition"><h4>Comb Area Composition (% of visible comb)</h4><div class="comp-bar">${keys
    .map(([c, k]) => `<i style="width:${((Math.max(0, m[k]) / total) * 100).toFixed(2)}%;background:${color(c)}" title="${esc(label(c))}: ${num(m[k])}%"></i>`)
    .join("")}</div><div class="comp-legend">${keys
    .map(([c, k]) => `<span><i style="background:${color(c)}"></i>${esc(label(c))} <b>${num(m[k])}%</b></span>`)
    .join("")}</div></div>`;
}

function renderRecord(hiveId, rec, target) {
  const el = $(target);
  if (!rec) {
    el.innerHTML = "";
    return;
  }
  const m = rec.metrics || {};
  const report = rec.report;
  const files = rec.files || {};
  const s = statusOf(rec.status?.overall);
  const fileUrl = (name, size = 1400) =>
    `/api/file/${encodeURIComponent(hiveId)}/${encodeURIComponent(rec.id)}/${encodeURIComponent(name)}?max_side=${size}`;

  const metricDefs = [
    ["Mites / Day", m.mites_per_day, "", m.mites_per_day_change],
    ["Mites Counted", m.mite_count, ""],
    ["Rejected Debris", m.rejected_detections, ""],
    ["Brood Area", m.brood_total_pct, "%"],
    ["Capped Honey", m.honey_pct, "%"],
    ["Hive Honey Est.", m.honey_kg_hive_est, "kg"],
    ["Food Reserve", m.stores_weeks, "wk"],
  ].filter(([, v]) => v != null);
  const metrics = metricDefs.length
    ? `<div class="metric-grid">${metricDefs
        .map(
          ([label, v, unit, ch]) =>
            `<div class="metric"><span>${label}</span><strong>${num(v)}${unit ? `<small>${unit}</small>` : ""}${ch != null && Math.abs(ch) >= 0.05 ? `<span class="delta ${ch > 0 ? "up" : ""}" style="margin-left:6px">${ch > 0 ? "+" : "−"}${num(Math.abs(ch))}</span>` : ""}</strong></div>`,
        )
        .join("")}</div>`
    : "";

  const flags = (rec.status?.flags || []).length
    ? `<div class="flags">${rec.status.flags.map((f) => `<div class="flag ${s === "act" ? "act" : ""}">${icon("alert")}<span>${esc(f)}</span></div>`).join("")}</div>`
    : "";

  const overlays = Object.keys(files)
    .filter((k) => k.endsWith("_overlay"))
    .sort((a, b) => Number(b.startsWith("board")) - Number(a.startsWith("board")))
    .map((key) => {
      const original = files[key.replace(/_overlay$/, "")];
      const board = key.startsWith("board");
      const src = fileUrl(files[key]);
      const title = board ? "Sticky Board Detection Overlay" : `${key.replace(/_overlay$/, "").replaceAll("_", " ")} Segmentation Overlay`;
      const caption = board
        ? "Green circle: SAM 3.1 detection · Blue circle: Muse Spark contact-sheet vote · Red cross: candidate rejected by morphological filter."
        : "Yellow: capped honey · Brown: capped brood · White: larvae · Orange: pollen · Blue: empty/nectar · Grey: bees (occlusion).";
      return `<figure class="figure"><div class="figure-head"><strong>${esc(title)}</strong>${original ? `<button class="link-btn" type="button" data-image="${esc(fileUrl(original, 2400))}">Raw Source Image ${icon("external")}</button>` : ""}</div><button type="button" data-image="${esc(fileUrl(files[key], 2400))}" aria-label="Enlarge ${esc(title)}"><img src="${esc(src)}" alt="${esc(title)}" loading="lazy" decoding="async"></button><figcaption>${caption}</figcaption></figure>`;
    })
    .join("");

  const evidenceKeys = Object.keys(files).filter((k) => k === "board_evidence" || k.startsWith("board_muse_sheet"));
  const evidence = evidenceKeys.length
    ? `<div class="evidence">
        <div class="evidence-head">
          <h4>Morphology Audit &amp; Contact-Sheet Evidence</h4>
          <span class="tag measured">${evidenceKeys.length} Plates</span>
        </div>
        <div class="evidence-grid">${evidenceKeys
          .map((k) => {
            const label =
              k === "board_evidence"
                ? "Morphology Audit: Counted & Rejected Candidates"
                : `Muse Spark 6×6 Contact Sheet #${k.split("_").at(-1)}`;
            return `<button type="button" data-image="${esc(fileUrl(files[k], 2400))}"><img src="${esc(fileUrl(files[k], 600))}" alt="" loading="lazy"><span>${esc(label)}</span></button>`;
          })
          .join("")}</div>
      </div>`
    : "";

  const urgency = { now: ["act", "Immediate"], this_week: ["watch", "This Week"], next_inspection: ["", "Next Inspection"] };
  const reportHtml = report
    ? `<div class="report-summary"><strong>Executive Summary:</strong> ${esc(report.summary)}</div>
      ${
        report.findings?.length
          ? `<div class="report-section"><h4>Verified Findings</h4>${report.findings
              .map((f) => `<div class="finding">${icon("check")}<div>${esc(f.text)}<br><small>Reference claims: ${esc((f.claim_ids || []).join(", "))}</small></div></div>`)
              .join("")}</div>`
          : ""
      }
      ${
        report.actions?.length
          ? `<div class="report-section"><h4>Recommended Operational Actions</h4>${report.actions
              .map((a) => {
                const [cls, text] = urgency[a.urgency] || ["", a.urgency || ""];
                return `<div class="action"><div class="action-top"><strong>${esc(a.action)}</strong>${text ? `<span class="badge ${cls} plain">${esc(text)}</span>` : ""}</div>${a.reason ? `<p>Rationale: ${esc(a.reason)}</p>` : ""}</div>`;
              })
              .join("")}</div>`
          : ""
      }
      ${report.caveats?.length ? `<div class="report-section"><h4>Caveats</h4>${report.caveats.map((c) => `<p class="caveat">${esc(c)}</p>`).join("")}</div>` : ""}
      ${
        report.discarded_findings?.length
          ? `<div class="report-section"><h4>Suppressed Findings (Unverified)</h4>${report.discarded_findings.map((f) => `<p class="caveat"><s>${esc(f.text)}</s></p>`).join("")}</div>`
          : ""
      }`
    : '<p class="report-summary">Measurements only. Agent report generation was disabled for this record.</p>';

  const claims = rec.claims || [];
  const rejectedCount = claims.filter((c) => c.verdict === "rejected").length;
  const verifiedCount = claims.filter((c) => c.verdict === "verified").length;
  const claimsHtml = claims.length
    ? `<div class="claims-box">
        <div class="claims-box-head">
          <h4>Epistemic Claim Verification Log (<code>check_claim</code>)</h4>
          <span class="tag">${verifiedCount} Verified · ${rejectedCount} Rejected</span>
        </div>
        <table class="claims">
          <thead><tr><th>Status</th><th>Hypothesis Statement</th><th>Measured Value</th></tr></thead>
          <tbody>${claims
            .map(
              (c) =>
                `<tr>
                  <td><span class="badge ${c.verdict === "verified" ? "good" : c.verdict === "rejected" ? "act" : ""}">${esc(c.verdict)}</span></td>
                  <td><code>${esc(c.id)}</code> ${esc(c.statement)}</td>
                  <td><code>${esc(c.metric)} = ${esc(num(c.actual, 2))}</code></td>
                </tr>`,
            )
            .join("")}</tbody>
        </table>
      </div>`
    : "";

  el.innerHTML = `<article class="panel record">
    <header class="record-head">
      <div>
        <h2>Inspection Record: ${esc(dateLabel(rec.date))} ${badge(s)} ${rec.synthetic ? '<span class="tag demo">Synthetic</span>' : '<span class="tag measured">Measured</span>'}</h2>
        <p>${esc(hiveName(hiveId))}${rec.models?.segmentation ? ` · Models: ${esc(rec.models.segmentation)} / ${esc(rec.models.reasoning)}` : ""}</p>
      </div>
      <button class="btn sm record-download" type="button">${icon("download")}Export JSON</button>
    </header>
    <div class="record-body">
      ${rec.synthetic ? '<div class="alert warn">' + icon("info") + "<p>Synthetic scenario record: metrics are simulated for fleet demonstration. Select <b>Hive #7</b> to inspect camera-measured sticky-board and comb records.</p></div>" : ""}
      ${flags}
      ${metrics}
      ${compositionBar(m)}
      ${rec.inputs?.note ? `<p class="note"><b>Inspector note:</b> ${esc(rec.inputs.note)}</p>` : ""}
      <div class="record-cols">
        <div class="figures">${evidence}${overlays || emptyState("No optical attachments", rec.synthetic ? "Synthetic records do not include camera imagery." : "No overlay attached.")}</div>
        <div class="report">${claimsHtml}${reportHtml}${rec.trace?.length ? '<details><summary>Execution Trace (' + rec.trace.length + ' tool events)</summary><pre class="trace-log"></pre></details>' : ""}</div>
      </div>
    </div>
  </article>`;
  el.querySelector(".record-download").addEventListener("click", () => downloadJson(rec));
  if (rec.trace?.length) el.querySelector(".trace-log").textContent = JSON.stringify(rec.trace, null, 2);
}

/* ── Benchmark & Comparative Optical Plates ──────────────────────────── */
function renderProofGallery() {
  const wrap = $("proof-gallery");
  const card = $("visual-proof-card");
  const imgs = state?.demo_assets?.images || [];
  if (!imgs.length) {
    card.hidden = true;
    return;
  }
  card.hidden = false;
  const items = [
    {
      file: "IMG_5582_naive_vs_hivelens.jpg",
      title: "Plate 1 — 49 MP Sticky Board: Baseline SAM 3.1 (0/21) vs. HiveLens (20/21)",
      desc: "Single-pass full-board SAM 3.1 misses 30 px mites due to input downscaling. HiveLens combines 600 px + 300 px tiling, Muse Spark voting, and ellipse filtering.",
    },
    {
      file: "IMG_5582_evidence.jpg",
      title: "Plate 2 — Morphological Audit Sheet: Counted vs. Rejected Detections",
      desc: "High-magnification crops of all 20 counted mites and 9 rejected candidates showing fitted ellipses, aspect ratios, Δ(R−G) redness, and solidity.",
    },
    {
      file: "IMG_5582_muse_sheet_1.jpg",
      title: "Plate 3 — Muse Spark 6×6 Contact Sheet with Morphological Vetoes",
      desc: "Unexplained dark candidates presented to Muse Spark. Blue borders denote confirmed mites; red crossed borders denote candidates vetoed by physical checks.",
    },
    {
      file: "A_slice_of_the_brood_nest_naive_vs_hivelens.jpg",
      title: "Plate 4 — Comb Frame: Text-Prompted SAM 3.1 vs. SAM Mask + Muse Grid",
      desc: "Prompting SAM 3.1 with cell textures returns whole-frame regions (86–99%). HiveLens uses SAM for comb/bee geometry and Muse Spark for tile classification.",
    },
  ].filter((x) => imgs.includes(x.file));

  wrap.innerHTML = items
    .map((item) => {
      const fullUrl = `/api/demo_asset/${encodeURIComponent(item.file)}?max_side=2400`;
      const thumbUrl = `/api/demo_asset/${encodeURIComponent(item.file)}?max_side=800`;
      return `<article class="proof-card">
        <button type="button" data-image="${esc(fullUrl)}" aria-label="Enlarge ${esc(item.title)}">
          <img src="${esc(thumbUrl)}" alt="${esc(item.title)}" loading="lazy" decoding="async" />
        </button>
        <div class="proof-meta">
          <strong>${esc(item.title)}</strong>
          <p>${esc(item.desc)}</p>
        </div>
      </article>`;
    })
    .join("");
}

function renderBenchmark() {
  renderProofGallery();
  const b = state.benchmark;
  const s = b?.summary;
  const rows = b?.images || [];
  $("benchmark-provenance").textContent = s
    ? `Validation Protocol: ${s.images} held-out sticky boards (Boards 9–20) · ${s.experts_total} expert-annotated mites (Divasón et al. 2023, Zenodo CC BY 4.0) · Boards 1–${s.skipped_first ?? 8} were reserved for threshold calibration and are excluded.`
    : "No saved evaluation found.";
  $("benchmark-stats").innerHTML =
    kpi("Box-Match F1", num(s?.sam_f1, 3), s?.cv_f1 != null ? `Baseline CV: ${num(s.cv_f1, 3)}` : "Held-out test set", "good") +
    kpi("Precision", num(s?.sam_precision, 3), "True positives / all predictions", "good") +
    kpi("Recall", num(s?.sam_recall, 3), "Detected / expert ground truth", "watch") +
    kpi("HiveLens MAE", `${num(s?.sam_mae, 2)}`, "Mites / board count error", "good") +
    kpi("Baseline CV MAE", `${num(s?.cv_mae, 1)}`, "Threshold baseline error", "act");
  $("benchmark-table").innerHTML = rows
    .map((r) => {
      const samOnly = Math.max(0, (r.sam || 0) - (r.muse_votes_kept || 0));
      return `<tr>
        <td><code>${esc(r.image)}</code></td>
        <td class="num">${num(r.experts)}</td>
        <td class="num strong">${num(r.sam)}</td>
        <td class="num">${num(samOnly)}</td>
        <td class="num">${num(r.muse_votes_kept)}</td>
        <td class="num">${num(r.sam_rejected)}</td>
        <td class="num muted">${num(r.classic_cv)}</td>
        <td class="num">${num(r.sam_precision, 3)}</td>
        <td class="num">${num(r.sam_recall, 3)}</td>
        <td class="num strong">${num(r.sam_f1, 3)}</td>
      </tr>`;
    })
    .join("");
  if (!rows.length) {
    $("benchmark-chart").innerHTML = emptyState("No benchmark records", "Run an evaluation to compare predictions against expert annotations.");
    return;
  }
  const W = Math.max(600, rows.length * 56);
  const H = 200;
  const top = 14;
  const base = 170;
  const left = 36;
  const max = Math.max(1, ...rows.flatMap((r) => [r.experts || 0, r.sam || 0]));
  const step = (W - left - 8) / rows.length;
  const bw = Math.min(14, step / 3);
  const y = (v) => base - (v / max) * (base - top);
  const grid = [0, 0.25, 0.5, 0.75, 1]
    .map((f) => `<path class="grid-line" d="M${left} ${y(max * f).toFixed(1)}H${W}"/><text class="axis" x="${left - 6}" y="${(y(max * f) + 3).toFixed(1)}" text-anchor="end">${num(max * f, 0)}</text>`)
    .join("");
  const bars = rows
    .map((r, i) => {
      const cx = left + step * i + step / 2;
      return `<g><title>${esc(r.image)}: Expert ${r.experts}, HiveLens ${r.sam} (F1 ${r.sam_f1})</title><rect class="bar-a" x="${(cx - bw - 1).toFixed(1)}" y="${y(r.experts || 0).toFixed(1)}" width="${bw}" height="${(base - y(r.experts || 0)).toFixed(1)}" rx="2"/><rect class="bar-b" x="${(cx + 1).toFixed(1)}" y="${y(r.sam || 0).toFixed(1)}" width="${bw}" height="${(base - y(r.sam || 0)).toFixed(1)}" rx="2"/><text class="axis" x="${cx.toFixed(1)}" y="${base + 16}" text-anchor="middle">${esc(String(r.image).replace("IMG_", ""))}</text></g>`;
    })
    .join("");
  $("benchmark-chart").innerHTML = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Expert and HiveLens mite counts per board">${grid}${bars}</svg>`;
}

/* ── Events ──────────────────────────────────────────────────────────── */
document.addEventListener("click", (event) => {
  const mapNode = event.target.closest(".map-node");
  if (mapNode && mapNode.dataset.hive) {
    selectHive(mapNode.dataset.hive, mapNode.dataset.destination || "history");
    return;
  }
  const target = event.target.closest("button,a");
  if (!target) return;
  if (target.id === "theme-toggle") {
    const cur = document.documentElement.getAttribute("data-theme") || "light";
    applyTheme(cur === "dark" ? "light" : "dark");
    return;
  }
  if (target.id === "hero-open-measured") {
    const measured = state?.apiary?.hives?.find((h) => !isSynthetic(h)) || state?.hives?.[0];
    if (measured) selectHive(measured.id, "history");
    else go("inspect");
    return;
  }
  if (target.dataset.go) go(target.dataset.go);
  if (target.hasAttribute("data-add-hive")) {
    $("add-hive-dialog").showModal();
    $("new-hive-name").focus();
  }
  if (target.dataset.close) $(target.dataset.close).close();
  if (target.dataset.hive) {
    event.preventDefault();
    selectHive(target.dataset.hive, target.dataset.destination);
  }
  if (target.dataset.filter) {
    statusFilter = target.dataset.filter;
    document.querySelectorAll("#status-filter button").forEach((b) => b.setAttribute("aria-pressed", b === target));
    renderHiveGrid();
  }
  if (target.dataset.record) {
    selectedRecord = target.dataset.record;
    document.querySelectorAll("#history-list button").forEach((b) => b.setAttribute("aria-current", b === target));
    renderSelectedRecord();
  }
  if (target.dataset.image) {
    $("full-image").src = target.dataset.image;
    $("image-dialog").showModal();
  }
  if (target.hasAttribute("data-retry-history")) loadHistory();
  if (target.id === "job-result-link" && target.dataset.resultHive) {
    event.preventDefault();
    selectHive(target.dataset.resultHive, "history");
  }
  if (target.dataset.remove) {
    const kind = target.dataset.remove;
    if (kind === "board") boardFile = null;
    if (kind === "frames") frameFiles.splice(Number(target.dataset.index), 1);
    if (kind === "sample-board") {
      $("board-sample").value = "";
      $("board-sample-info").textContent = "";
    }
    if (kind === "sample-frame")
      document.querySelectorAll(".frame-sample").forEach((el) => {
        if (el.value === target.dataset.index) el.checked = false;
      });
    renderPreviews();
  }
});

$("inspection-form").addEventListener("submit", startInspection);
$("inspection-form").addEventListener("input", (event) => {
  if (draftFields.includes(event.target.id)) saveDraft();
  updateSummary();
});
$("inspection-hive").addEventListener("change", (e) => selectHive(e.target.value));
$("history-hive").addEventListener("change", (e) => selectHive(e.target.value));
$("hive-search").addEventListener("input", renderHiveGrid);
$("source-filter").addEventListener("change", renderHiveGrid);
$("sort-hives").addEventListener("click", () => {
  sortAscending = !sortAscending;
  $("sort-hives").firstChild.textContent = sortAscending ? "Sort A–Z " : "Sort Z–A ";
  renderHiveGrid();
});
$("retry-load").addEventListener("click", loadState);
$("board-sample").addEventListener("change", () => {
  boardFile = null;
  const b = state.samples.boards.find((x) => x.name === $("board-sample").value);
  $("board-sample-info").textContent = b?.experts != null ? `Reference XML annotation: ${b.experts} expert-verified mites.` : "";
  renderPreviews();
});
$("frame-samples").addEventListener("change", (event) => {
  if (frameFiles.length + checkedFrameSamples().length > 8) {
    event.target.checked = false;
    toast("Choose up to 8 frame photos.", true);
  }
  renderPreviews();
});
for (const kind of ["board", "frames"]) {
  $(`${kind}-file`).addEventListener("change", (e) => setFiles(kind, [...e.target.files]));
  const zone = $(`${kind}-drop`);
  zone.addEventListener("dragover", (e) => {
    e.preventDefault();
    zone.classList.add("drag-over");
  });
  zone.addEventListener("dragleave", () => zone.classList.remove("drag-over"));
  zone.addEventListener("drop", (e) => {
    e.preventDefault();
    zone.classList.remove("drag-over");
    setFiles(kind, [...e.dataTransfer.files]);
  });
}
$("add-hive-form").addEventListener("submit", (event) => {
  event.preventDefault();
  const name = $("new-hive-name").value.trim();
  if (!name) return $("new-hive-name").focus();
  withButton($("create-hive"), async () => {
    const data = await api("/api/hives", { name, location: $("new-hive-location").value.trim() });
    selectedHive = data.hive.id;
    selectedRecord = null;
    store.set("hive", selectedHive);
    $("add-hive-dialog").close();
    $("add-hive-form").reset();
    await loadState();
    toast(`${data.hive.name} registered.`);
  });
});
$("seed-demo").addEventListener("click", () =>
  withButton($("seed-demo"), async () => {
    const result = await api("/api/seed_apiary", {});
    await loadState();
    toast(result.created ? `${result.created} synthetic colonies loaded.` : "Synthetic fleet is already loaded.");
  }),
);
$("fetch-frames").addEventListener("click", () =>
  withButton($("fetch-frames"), async () => {
    toast("Fetching reference frames…");
    const result = await api("/api/commons", {});
    await loadState();
    if (result.errors?.length) toast(result.errors.join(" · "), true);
    else toast("Reference frames ready.");
  }),
);
$("benchmark-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (activeJob || startingJob || !$("benchmark-form").reportValidity()) return;
  startingJob = true;
  updateRunButtons();
  try {
    const result = await api("/api/benchmark", { n_boards: Number($("benchmark-n").value), skip: 8, use_muse: true });
    attachJob({ id: result.job_id, kind: "benchmark" });
  } catch (e) {
    toast(e.message, true);
  } finally {
    startingJob = false;
    updateRunButtons();
  }
});
$("job-dismiss").addEventListener("click", () => ($("job-panel").hidden = true));
for (const dialog of document.querySelectorAll("dialog"))
  dialog.addEventListener("click", (event) => {
    if (event.target !== dialog) return;
    const r = dialog.getBoundingClientRect();
    if (event.clientX < r.left || event.clientX > r.right || event.clientY < r.top || event.clientY > r.bottom || dialog.id === "image-dialog")
      dialog.close();
  });
document.addEventListener("keydown", (event) => {
  if (
    event.key === "/" &&
    !event.ctrlKey &&
    !event.metaKey &&
    !event.altKey &&
    !["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement?.tagName) &&
    !document.querySelector("dialog[open]")
  ) {
    event.preventDefault();
    go("overview");
    $("hive-search").focus();
  }
});
window.addEventListener("hashchange", route);
window.addEventListener("pagehide", () => {
  previewGeneration++;
  eventStream?.close();
  previewUrls.forEach((url) => URL.revokeObjectURL(url));
});
window.addEventListener("pageshow", (event) => {
  if (event.persisted) {
    renderPreviews();
    if (activeJob) attachJob(activeJob);
  }
});

/* ── Boot ────────────────────────────────────────────────────────────── */
hydrateIcons();
applyTheme(store.get("corp_theme", "light"));
restoreDraft();
route();
loadState().then((ok) => {
  const job = jobSession.get();
  if (ok && job) attachJob(job);
});
