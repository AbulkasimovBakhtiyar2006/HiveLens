"use strict";
// HiveLens Enterprise Telemetry UI. Buildless, dependency-free, local-only assets.

/* ── Helpers ─────────────────────────────────────────────────────────── */
const workspaceMode = typeof location !== "undefined" && new URLSearchParams(location.search).get("mode") === "production" ? "production" : "demo";
const apiUrl = (path) => path.startsWith("/api/") && !path.startsWith("/api/workspaces/") ? path.replace("/api/", `/api/workspaces/${workspaceMode}/`) : path;
const workspaceStorageKey = (key) => `hivelens:${workspaceMode === "production" && !["palette", "corp_theme", "side-w"].includes(key) ? "production:" : ""}${key}`;
const $ = (id) => document.getElementById(id);
const esc = (value) =>
  String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

// Optical family: 24 × 24 grid, 1.75-unit strokes, rounded ends.
const ICONS = {
  compass: '<circle cx="12" cy="12" r="9"/><path d="m16 8-2.5 5.5L8 16l2.5-5.5Z"/>',
  records: '<path d="M8 3h9a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2ZM3 7h4m-4 5h4m-4 5h4m4-9h5m-5 4h5m-5 4h3"/>',
  book: '<path d="M12 5v15M3 4h5a4 4 0 0 1 4 2 4 4 0 0 1 4-2h5v15h-5a4 4 0 0 0-4 2 4 4 0 0 0-4-2H3Z"/>',
  wallet: '<path d="M20 8V6a2 2 0 0 0-2-2H6a3 3 0 0 0 0 6h14v10H6a3 3 0 0 1-3-3V7m17 6h-5v4h5"/>',
  settings: '<path d="M4 7h3m4 0h9M4 17h9m4 0h3"/><circle cx="9" cy="7" r="2"/><circle cx="15" cy="17" r="2"/>',
  scan: '<path d="M8 4H6a2 2 0 0 0-2 2v2m12-4h2a2 2 0 0 1 2 2v2M4 16v2a2 2 0 0 0 2 2h2m8 0h2a2 2 0 0 0 2-2v-2M8 12h8"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  search: '<circle cx="10.5" cy="10.5" r="6"/><path d="m15 15 4.5 4.5"/>',
  hive: '<path d="m12 3 8 4.5v9L12 21l-8-4.5v-9Z"/><path d="M8.5 9h7m-7 3h7m-7 3h7"/>',
  check: '<path d="m5 12 4.5 4.5L19 7"/>',
  alert: '<path d="M10.3 4.8a2 2 0 0 1 3.4 0l7.4 12.7a2 2 0 0 1-1.7 3H4.6a2 2 0 0 1-1.7-3Z"/><path d="M12 9v4m0 3.5v.1"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2.5v1.5m0 16v1.5M2.5 12H4m16 0h1.5M5.3 5.3l1.1 1.1m11.2 11.2 1.1 1.1m-13.4 0 1.1-1.1M17.6 6.4l1.1-1.1"/>',
  moon: '<path d="M20.5 13.1A8.5 8.5 0 0 1 10.9 3.5a8.5 8.5 0 1 0 9.6 9.6Z"/>',
  upload: '<path d="M12 15V4m-4 4 4-4 4 4M4 15v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3"/>',
  download: '<path d="M12 4v11m-4-4 4 4 4-4M4 15v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3"/>',
  close: '<path d="m6.5 6.5 11 11m-11 0 11-11"/>',
  info: '<circle cx="12" cy="12" r="8.5"/><path d="M12 11v5m0-8v.1"/>',
  arrow: '<path d="M5 12h14m-5-5 5 5-5 5"/>',
  external: '<path d="M14 4h6v6m0-6-9 9m7 1v4a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4"/>',
  sort: '<path d="M8 4v16m-3-3 3 3 3-3M16 20V4m-3 3 3-3 3 3"/>',
  grid: '<rect x="4" y="4" width="6" height="6" rx="1.5"/><rect x="14" y="4" width="6" height="6" rx="1.5"/><rect x="4" y="14" width="6" height="6" rx="1.5"/><rect x="14" y="14" width="6" height="6" rx="1.5"/>',
  activity: '<path d="M3 12h4l3-7 4 14 3-7h4"/>',
  chart: '<path d="M4 4v16h16M8 15v-4m5 4V7m5 8v-5"/>',
  layers: '<path d="m12 3 9 5-9 5-9-5Zm-9 10 9 5 9-5M3 18l9 5 9-5"/>',
  microscope: '<path d="M4 21h16M9 17h4m0 4a6 6 0 0 0 2-11M8 4h6v7a2 2 0 0 1-2 2h-2a2 2 0 0 1-2-2Zm2 9v2h2v-2M10 4V2h2v2"/>',
};
const icon = (name) => `<svg class="icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">${ICONS[name] || ICONS.hive}</svg>`;
const hydrateIcons = (root = document) =>
  root.querySelectorAll("[data-icon]").forEach((el) => {
    el.innerHTML = icon(el.dataset.icon);
  });

const VIEWS = {
  welcome: "Start here",
  overview: "Overview",
  inspect: "New inspection",
  history: "Hive records",
  benchmark: "Benchmark",
  method: "How it works",
  usage: "Usage and cost",
  settings: "Settings",
  research: "Field dataset",
  guide: "Mite guide",
};
const STATUS = { good: "Normal", watch: "Watch", act: "Critical", unknown: "No data" };
const statusOf = (s) => (Object.hasOwn(STATUS, s) ? s : "unknown");
const badge = (s) => `<span class="badge ${statusOf(s)}">${STATUS[statusOf(s)]}</span>`;

// The overall status is the most severe measured dimension, not just varroa.
function statusReasons(levels = {}, metrics = {}) {
  const order = { act: 3, watch: 2, good: 1, unknown: 0 };
  return [
    ["varroa", "Mites", metrics.mites_per_day, "mites/day"],
    ["stores", "Stores", metrics.stores_weeks, "weeks remaining"],
    ["brood", "Brood", metrics.brood_total_pct, "% visible area"],
  ].map(([key, label, value, unit]) => ({
    level: statusOf(levels[key]),
    text: `${label}: ${value == null ? "not measured" : `${num(value)} ${unit}`}`,
  })).sort((a, b) => order[b.level] - order[a.level]);
}
function primaryReason(h) {
  return statusReasons(h.levels, h).filter((r) => r.level === h.overall && r.level !== "unknown")
    .map((r) => r.text).join(" · ") || (h.overall === "unknown" ? "No inspection data" : "Review latest inspection.");
}

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
      return JSON.parse(localStorage.getItem(workspaceStorageKey(key))) ?? fallback;
    } catch {
      return fallback;
    }
  },
  set(key, value) {
    try {
      localStorage.setItem(workspaceStorageKey(key), JSON.stringify(value));
    } catch {
      /* storage unavailable */
    }
  },
};
function applyWorkspaceMode() {
  const production = workspaceMode === "production";
  document.documentElement.dataset.workspace = workspaceMode;
  $("workspace-mode").value = workspaceMode;
  $("workspace-label").textContent = production ? "Production workspace" : "Demo workspace";
  $("workspace-description").textContent = production
    ? "Your farms and inspections. Stored separately from the demo."
    : "Sample analyses and simulated histories. Explore real study data in Field dataset.";
  if (production) {
    $("welcome-example").hidden = !welcomeExample;
    $("welcome-own").classList.add("primary");
    $("welcome-photo-step").textContent = "Photograph your sticky board for mite counts, or a frame for honey and brood. Keep the hive, date and board exposure time with the photos.";
    $("welcome-data-note").textContent = "Your workspace contains only the farms and records you add. The public field archive and benchmark remain available as separate references.";
  }
}
const jobSession = {
  get() {
    try {
      return JSON.parse(sessionStorage.getItem(workspaceStorageKey("job")));
    } catch {
      return null;
    }
  },
  set(job) {
    try {
      job ? sessionStorage.setItem(workspaceStorageKey("job"), JSON.stringify(job)) : sessionStorage.removeItem(workspaceStorageKey("job"));
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

function applyPalette(value, updateUrl = false) {
  const palette = value === "honey" ? "honey" : "forest";
  document.documentElement.dataset.palette = palette;
  store.set("palette", palette);
  document.querySelectorAll("[data-palette-choice]").forEach((button) => {
    button.setAttribute("aria-pressed", button.dataset.paletteChoice === palette);
  });
  const favicon = document.querySelector('link[rel="icon"]');
  if (favicon) favicon.href = "/static/mark.svg?v=5";
  if (updateUrl) {
    const url = new URL(location.href);
    url.searchParams.set("palette", palette);
    history.replaceState(null, "", url);
  }
}

/* ── State ───────────────────────────────────────────────────────────── */
let state = null;
let view = "overview";
let selectedHive = store.get("hive");
let selectedFarm = store.get("farm", "all");
let statusFilter = "all";
let sortAscending = true;
let historyController = null;
let historyData = null;
let historyHive = null;
let selectedRecord = null;
let boardFile = null;
let frameFiles = [];
const captureSources = new WeakMap();
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
    const response = await fetch(apiUrl(path), {
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
function entryView(requested, welcomed) {
  if (!welcomed && (!requested || requested === "overview")) return "welcome";
  return Object.hasOwn(VIEWS, requested) ? requested : "overview";
}

function go(next) {
  if (location.hash === `#${next}`) route();
  else location.hash = next;
}

function route() {
  const next = location.hash.slice(1);
  if (next === "main") return;
  if (view === "welcome" && next !== "welcome") {
    store.set("welcomed", true);
  }
  view = Object.hasOwn(VIEWS, next) ? next : "overview";
  document.documentElement.dataset.view = view;
  for (const key of Object.keys(VIEWS)) {
    $(`view-${key}`).hidden = key !== view;
    const link = document.querySelector(`[data-nav="${key}"]`);
    link.classList.toggle("active", key === view);
    key === view ? link.setAttribute("aria-current", "page") : link.removeAttribute("aria-current");
  }
  renderTopbar();
  document.title = `${VIEWS[view]} · HiveLens`;
  window.scrollTo({ top: 0, behavior: "instant" });
  renderView();
}

function renderView() {
  if (view === "research" && typeof renderResearch === "function") renderResearch();
  if (!state) return;
  if (typeof renderProfileChip === "function") renderProfileChip(); // account.js
  if (view === "welcome") renderWelcome();
  if (view === "usage" && typeof renderUsage === "function") renderUsage();
  if (view === "settings" && typeof renderSettings === "function") renderSettings();
  if (view === "overview") renderOverview();
  if (view === "inspect") updateSummary();
  if (view === "history") loadHistory();
  if (view === "benchmark") renderBenchmark();
}

let welcomeExample = null;
let welcomeLoading = false;
async function renderWelcome() {
  if (welcomeExample || welcomeLoading) return;
  const candidates = hives().filter((h) => !isSynthetic(h) && (h.inspection_count > 0 || h.sample_inspection_count > 0));
  welcomeLoading = true;
  try {
    for (const hive of candidates) {
      const data = await api(`/api/hive/${encodeURIComponent(hive.id)}`);
      const rec = [...data.inspections].reverse().find((r) => !r.synthetic && r.report && Object.keys(r.files || {}).some((key) => key.endsWith("_overlay")));
      if (!rec) continue;
      const files = rec.files;
      const overlay = files.board_overlay ? "board_overlay" : Object.keys(files).find((key) => key.endsWith("_overlay"));
      const original = files[overlay.replace(/_overlay$/, "")];
      const url = (name) => apiUrl(`/api/file/${encodeURIComponent(hive.id)}/${encodeURIComponent(rec.id)}/${encodeURIComponent(name)}?max_side=720`);
      const photo = (name, label) => `<div><img src="${esc(url(name))}" alt="${esc(label)}" decoding="async"><span>${esc(label)}</span></div>`;
      $("welcome-proof").innerHTML = (original ? photo(original, "Original photo") : "") + photo(files[overlay], "Measured evidence");
      $("welcome-proof-caption").textContent = rec.demo_capture ? "Public sample photographs · Saved model output, not a real colony history." : `${displayName(hive)} · ${dateLabel(rec.date)} · Saved photo analysis`;
      welcomeExample = { hiveId: hive.id, recordId: rec.id };
      $("welcome-example").disabled = false;
      $("welcome-example").hidden = false;
      $("welcome-example-hint").textContent = rec.demo_capture ? "A saved model run on public samples. No API key or upload needed." : "A saved inspection, ready to explore. No upload needed.";
      return;
    }
    $("welcome-example-hint").textContent = workspaceMode === "production" ? "Start by adding a hive and its photographs. Your first completed analysis will be saved here." : "No saved photo analysis yet. Try your own photos or explore the benchmark.";
    $("welcome-proof").innerHTML = '<p class="muted">The first completed photo analysis will appear here.</p>';
    $("welcome-proof-caption").textContent = "Original photographs and marked-up results stay together in your hive’s history.";
  } catch {
    $("welcome-example-hint").textContent = "Could not load the example. Reopen Start here to retry, or explore the workspace.";
  } finally {
    welcomeLoading = false;
  }
}

async function loadState() {
  try {
    state = await api("/api/state");
    applyWorkspaceMode();
    $("load-error").hidden = true;
    const measuredHives = state.apiary?.hives?.filter((h) => !isSynthetic(h)) || [];
    if (!state.hives.some((h) => h.id === selectedHive)) {
      selectedHive = measuredHives[0]?.id || state.hives[0]?.id || null;
    }
    const conn = $("api-state");
    conn.innerHTML = `<i></i>${state.has_api_key ? "Connected" : "No API key"}`;
    conn.classList.toggle("offline", !state.has_api_key);
    conn.title = state.has_api_key
      ? `Meta Model API active: ${state.segment_model} + ${state.reasoning_model}`
      : "Set MODEL_API_KEY in .env to run an analysis.";
    $("version").textContent = state.version ? `v${state.version}` : "v0.1";
    $("models").textContent = `${state.segment_model}, ${state.reasoning_model}`;
    syncHiveSelects();
    populateSamples();
    renderView();
    updateRunButtons();
    return true;
  } catch (e) {
    $("load-error-text").textContent = `Could not load the workspace. ${e.message}`;
    $("load-error").hidden = false;
    $("api-state").innerHTML = "<i></i>Offline";
    $("api-state").classList.add("offline");
    return false;
  }
}

function syncHiveSelects() {
  const byId = Object.fromEntries((state.apiary?.hives || []).map((h) => [h.id, h]));
  if (selectedFarm !== "all" && !farmByKey(selectedFarm)) selectedFarm = "all";
  const option = (h) => {
    const syn = isSynthetic(byId[h.id] || h);
    return `<option value="${esc(h.id)}">${esc(displayName(h))}${syn ? " (demo)" : ""}</option>`;
  };
  const groups = farms()
    .map((f) => {
      const members = state.hives.filter((h) => farmKey((byId[h.id] || h).farm_id ?? null) === farmKey(f.id)).sort(byHiveName);
      return members.length ? `<optgroup label="${esc(f.name)}">${members.map(option).join("")}</optgroup>` : "";
    })
    .join("");
  const options = groups || '<option value="">No hives yet</option>';
  for (const id of ["inspection-hive", "history-hive"]) {
    $(id).innerHTML = options;
    $(id).value = selectedHive || "";
  }

  renderFarmNav();
  renderTopbar();
}

function selectHive(id, destination) {
  if (!state?.hives.some((h) => h.id === id)) return;
  if (id !== selectedHive) selectedRecord = null;
  selectedHive = id;
  store.set("hive", id);
  const hive = hives().find((h) => h.id === id);
  if (hive && selectedFarm !== "all" && farmKey(hive.farm_id) !== selectedFarm) {
    selectedFarm = farmKey(hive.farm_id);
    store.set("farm", selectedFarm);
  }
  syncHiveSelects();
  updateSummary();
  if (destination) go(destination);
  else if (view === "history") loadHistory();
}

/* ── Fleet Overview & Spatial Matrix ─────────────────────────────────── */
function kpi(label, value, note, dot = "") {
  return `<div class="kpi"><div class="kpi-label">${dot ? `<i class="dot ${dot}"></i>` : ""}${esc(label)}</div><div class="kpi-value">${esc(value)}</div><div class="kpi-note">${esc(note)}</div></div>`;
}

/* ── Farms ───────────────────────────────────────────────────────────── */
// A farm key is the farm id, or "unassigned" for hives without a farm.
const farmKey = (id) => id ?? "unassigned";
const farms = () => state?.apiary?.farms || [];
const farmByKey = (key) => farms().find((f) => farmKey(f.id) === key);
const farmName = (id) => farmByKey(farmKey(id))?.name || "Unassigned";
const hivesOfFarm = (key) => hives().filter((h) => farmKey(h.farm_id) === key);
const hivesInView = () => (selectedFarm === "all" ? hives() : hivesOfFarm(selectedFarm));
const shortName = (h) => displayName(h).split("·")[0].trim();
const byHiveName = (a, b) =>
  Number(isSynthetic(a)) - Number(isSynthetic(b)) || a.name.localeCompare(b.name, undefined, { numeric: true });

function selectFarm(key) {
  selectedFarm = key === "all" || farmByKey(key) ? key : "all";
  store.set("farm", selectedFarm);
  renderFarmNav();
  go("overview");
}

function renderFarmNav() {
  const el = $("farm-list");
  if (!el || !state) return;
  const item = (key, label, count, status) =>
    `<button type="button" class="farm-btn" data-farm="${esc(key)}" aria-current="${selectedFarm === key}">
      <i class="dot ${status}"></i><span class="farm-name">${esc(label)}</span><span class="farm-count">${count}</span>
    </button>`;
  let html = item("all", "All farms", hives().length, "none");
  for (const f of farms()) {
    const key = farmKey(f.id);
    html += `<div class="farm-group">${item(key, f.name, f.hive_count, f.hive_count ? statusOf(f.overall) : "unknown")}`;
    if (selectedFarm === key) {
      const members = hivesOfFarm(key).sort(byHiveName);
      html += members.length
        ? `<ul class="farm-hives">${members
            .map(
              (h) => `<li><button type="button" class="farm-hive" data-hive="${esc(h.id)}" data-destination="history" aria-current="${h.id === selectedHive}">
                <i class="dot ${statusOf(h.overall)}"></i><span class="farm-name"${isSynthetic(h) ? ' title="Demo data"' : ""}>${esc(shortName(h))}</span><span class="farm-count">${h.mites_per_day != null ? num(h.mites_per_day) : "–"}</span>
              </button></li>`,
            )
            .join("")}</ul>`
        : '<p class="farm-empty">No hives yet.</p>';
    }
    html += "</div>";
  }
  el.innerHTML = html;
}

function fillFarmSelect(select, current) {
  const real = farms().filter((f) => f.id);
  select.innerHTML =
    real.map((f) => `<option value="${esc(f.id)}">${esc(f.name)}</option>`).join("") + '<option value="">No farm</option>';
  select.value = real.some((f) => f.id === current) ? current : real[0]?.id || "";
}

// The yard maps (view and layout editor) live in yard.js.

// Hive context for records and inspections. Overview already has its own title and summary.
function renderTopbar() {
  if (!$("topbar-crumbs")) return;
  const fact = (text, tone = "") =>
    `<span class="fact${tone ? ` ${tone}` : ""}">${text}</span>`;
  const hive = state ? hives().find((h) => h.id === selectedHive) : null;
  let crumbs = [];
  let facts = "";
  if (["history", "inspect"].includes(view) && hive) {
    crumbs = [farmName(hive.farm_id), shortName(hive)];
    const s = statusOf(hive.overall);
    if (isSynthetic(hive)) facts += fact("Demo data");
    if (hive.field_archive) facts += fact("Research archive · 2019–2020");
    const samplesOnly = !hive.inspection_count && hive.sample_inspection_count > 0;
    if (samplesOnly) facts += fact("Public photo samples");
    if (!samplesOnly && (!hive.field_archive || hive.inspection_count)) facts += fact(`Latest: ${STATUS[s]}`, s === "unknown" ? "" : s);
    if (hive.mites_per_day != null) facts += fact(`${num(hive.mites_per_day)} mites/day`);
    if (hive.stores_weeks != null) facts += fact(`${num(hive.stores_weeks)} weeks of stores`);
    if (!samplesOnly) facts += fact(hive.latest_date ? `Inspected ${esc(dateLabel(hive.latest_date))}` : hive.field_archive ? `Last observation ${esc(dateLabel(hive.field_archive.date_range[1]))}` : "Not inspected yet");
  }
  $("topbar-crumbs").innerHTML = crumbs
    .map((c, i) => (i === crumbs.length - 1 ? `<strong>${esc(c)}</strong>` : `<span>${esc(c)}</span><span class="crumb-sep" aria-hidden="true">/</span>`))
    .join("");
  $("topbar-facts").innerHTML = facts;
  $("topbar-crumbs").hidden = !crumbs.length;
  $("topbar").hidden = !crumbs.length && !facts;
}

function renderOverview() {
  $("view-overview").classList.toggle("one-farm", selectedFarm !== "all");
  $("page-add-farm").hidden = selectedFarm !== "all";
  $("page-add-hive").hidden = selectedFarm === "all";
  renderTopbar();
  const all = hivesInView();
  const count = (s) => all.filter((h) => h.overall === s).length;
  const measuredCount = all.filter((h) => !isSynthetic(h) && h.latest_date).length;
  const demoCount = all.filter(isSynthetic).length;
  const sourceNote = (level) => workspaceMode === "demo" ? `${all.filter((h) => h.overall === level && isSynthetic(h)).length} demo included` : "Your inspections";
  const exposed = all.filter((h) => h.drift_risk_from?.length && h.overall !== "act");
  const byId = new Map(hives().map((h) => [h.id, h]));
  const demoExposure = exposed.filter((h) => isSynthetic(h) || h.drift_risk_from.some((source) => isSynthetic(byId.get(source.id) || {}))).length;
  const farm = selectedFarm === "all" ? null : farmByKey(selectedFarm);
  const farmCount = farms().filter((f) => f.id).length;
  $("overview-title").textContent = farm ? farm.name : "All farms";
  $("overview-sub").textContent = farm
    ? `${farm.location ? `${farm.location}. ` : ""}Latest inspection of each hive on this farm.`
    : `${farmCount} farm${farmCount === 1 ? "" : "s"}, ${hives().length} hives. Latest inspection of each hive.`;

  $("overview-stats").innerHTML =
    kpi("Hives", all.length, `${measuredCount} measured, ${demoCount} demo, ${all.length - measuredCount - demoCount} uninspected`, "") +
    kpi("Normal", count("good"), `Measured checks normal · ${sourceNote("good")}`, "good") +
    kpi("Watch", count("watch"), `At least one check to watch · ${sourceNote("watch")}`, "watch") +
    kpi("Critical", count("act"), `At least one critical check · ${sourceNote("act")}`, "act") +
    kpi("Drift exposure", exposed.length, `${demoExposure} with demo data · Within 4 m of a high-mite hive`, "watch");


  const urgent = all.filter((h) => h.overall === "act").sort((a, b) => Number(isSynthetic(a)) - Number(isSynthetic(b)));
  $("attention").hidden = !urgent.length;
  $("attention").innerHTML = urgent.length
    ? `<div class="attention-head">${icon("alert")}${workspaceMode === "demo" ? "Example alerts" : "Requires action"} (${urgent.length})</div>` +
      urgent
        .map(
          (h) =>
            `<button class="attention-row" type="button" data-hive="${esc(h.id)}" data-destination="history"><strong>${esc(displayName(h))}${isSynthetic(h) ? ' <small class="tag demo">Demo</small>' : ""}</strong><span>${esc(primaryReason(h))}</span>${icon("arrow")}</button>`,
        )
        .join("")
    : "";

  if (typeof renderFarmMaps === "function") renderFarmMaps(); // yard.js
  if (typeof renderFarmConditions === "function") renderFarmConditions(); // farm.js

  const filters = [
    ["all", "All hives", all.length],
    ["act", "Critical", count("act")],
    ["watch", "Watch", count("watch")],
    ["good", "Normal", count("good")],
    ["unknown", "No data", count("unknown")],
  ];
  $("status-filter").innerHTML = filters
    .map(
      ([key, label, n]) =>
        `<button type="button" data-filter="${key}" aria-pressed="${statusFilter === key}">${label}<span class="n">${n}</span></button>`,
    )
    .join("");
  renderHiveGrid();
  if (typeof renderImportedApiaries === "function") renderImportedApiaries(all, farm);
}

function renderHiveGrid() {
  const all = hivesInView();
  const query = $("hive-search").value.toLocaleLowerCase().trim();
  const source = $("source-filter").value;
  const matching = all
    .filter(
      (h) =>
        (!query || `${h.name} ${h.location} ${farmName(h.farm_id)}`.toLocaleLowerCase().includes(query)) &&
        (source === "all" || (source === "synthetic" ? isSynthetic(h) : !isSynthetic(h))),
    );
  document.querySelectorAll("#status-filter button").forEach((button) => {
    const key = button.dataset.filter;
    button.querySelector(".n").textContent = key === "all" ? matching.length : matching.filter((h) => statusOf(h.overall) === key).length;
    button.setAttribute("aria-pressed", statusFilter === key);
  });
  const list = matching.filter((h) => statusFilter === "all" || statusOf(h.overall) === statusFilter)
    .sort((a, b) => {
      const synA = isSynthetic(a);
      const synB = isSynthetic(b);
      if (synA !== synB) return synA ? 1 : -1;
      return a.name.localeCompare(b.name, undefined, { numeric: true }) * (sortAscending ? 1 : -1);
    });

  $("hive-grid").innerHTML = list.map(hiveRow).join("");
  $("hive-table-wrap").hidden = !list.length;
  $("hive-result-count").textContent = `${list.length} of ${all.length} shown`;
  $("clear-hive-filters").hidden = !query && source === "all" && statusFilter === "all";
  $("hive-empty").hidden = list.length > 0;
  $("hive-empty").innerHTML = all.length
    ? `${icon("search")}<h3>No hives match</h3><p>Try another status or clear your filters.</p>`
    : `${icon("hive")}<h3>No hives yet</h3><p>Add a hive to start recording inspections.</p><button class="btn primary sm" type="button" data-add-hive>${icon("plus")}Add hive</button>`;
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
    <td class="muted col-farm">${esc(farmName(h.farm_id))}</td>
    <td>${syn ? '<span class="tag demo">Demo data</span>' : h.latest_date ? '<span class="tag measured">Measured</span>' : h.field_archive ? '<span class="tag">Research archive</span>' : '<span class="tag">No inspection</span>'}</td>
    <td>${badge(s)}${["act", "watch"].includes(s) ? `<small class="status-reason">${esc(primaryReason(h))}</small>` : ""}</td>
    <td class="num strong">${h.mites_per_day != null ? `${num(h.mites_per_day)} /d` : "—"}</td>
    <td class="num">${delta}</td>
    <td class="num">${h.honey_kg_hive_est != null ? `${num(h.honey_kg_hive_est)} kg` : "—"}</td>
    <td class="num">${h.brood_total_pct != null ? `${num(h.brood_total_pct)}%` : "—"}</td>
    <td class="num">${h.stores_weeks != null ? `${num(h.stores_weeks)} wk` : "—"}</td>
    <td class="muted">${h.latest_date ? `${esc(dateLabel(h.latest_date))} (${h.inspection_count})` : "None"}</td>
    <td class="num"><button type="button" class="btn sm" data-hive="${esc(h.id)}" data-destination="history">Open</button></td>
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
            `<label class="sample-tile" title="${esc(f.name.replaceAll("_", " "))}"><input type="checkbox" class="frame-sample" value="${esc(f.name)}" ${checked.has(f.name) ? "checked" : ""} aria-label="${esc(f.name)}"><img src="${apiUrl(`/api/sample_preview/frame/${encodeURIComponent(f.name)}?max_side=240`)}" alt="" loading="lazy" decoding="async"></label>`,
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

function inspectionReadiness() {
  if (!state) return "Loading inspection settings…";
  if (activeJob || startingJob) return "An analysis is running. Wait for it to finish.";
  if (!state.has_api_key) return "Add MODEL_API_KEY to .env to run inspections.";
  if (!state.hives.some((h) => h.id === selectedHive)) return "Choose a hive first.";
  if (!$('inspection-date').validity.valid) return "Choose a valid inspection date.";
  if (!$('inspection-days').validity.valid) return "Enter 0.5–30 days in steps of 0.5.";
  if (!$('inspection-frames').validity.valid) return "Enter a whole number of frames from 1 to 40.";
  const frames = frameFiles.length + checkedFrameSamples().length;
  if (frames > 8) return "Choose up to 8 frame photos.";
  if (!boardFile && !$('board-sample').value && !frames) return "Add a board photo or at least one frame.";
  return "";
}

function timingKey() {
  return JSON.stringify([Boolean(boardFile || $('board-sample').value), frameFiles.length + checkedFrameSamples().length,
    $('inspection-depth').value, $('inspection-agent').checked]);
}
function timingHint() {
  const samples = store.get("inspection-times", []).filter((r) => r.key === timingKey() && r.ms > 0);
  if (!samples.length) return "Duration unknown until the first comparable run.";
  const minutes = samples.map((r) => Math.max(1, Math.ceil(r.ms / 60000)));
  const low = Math.min(...minutes), high = Math.max(...minutes);
  return `Previous ${samples.length} similar run${samples.length === 1 ? "" : "s"}: ${low === high ? `about ${low}` : `${low}–${high}`} min. Browser-local history; photo detail, cache and API load can change this.`;
}

function updateSummary() {
  if (!state) return;
  const sample = $("board-sample").value;
  const frames = frameFiles.length + checkedFrameSamples().length;
  const hive = state.hives.find((h) => h.id === selectedHive);
  const row = (label, value, cls = "") => `<li><span>${label}</span><b class="${cls}" title="${esc(value)}">${esc(value)}</b></li>`;
  $("inspect-summary").innerHTML =
    row("Hive", hive ? `${displayName(hive)}${isSynthetic(hive) ? " (Demo)" : ""}` : "Not chosen", hive ? "" : "missing") +
    row("Date", dateLabel($("inspection-date").value)) +
    row("Sticky board", boardFile ? boardFile.name : sample ? sample : "None", boardFile || sample ? "ok" : "missing") +
    row("Frames", frames ? `${frames} image${frames === 1 ? "" : "s"}` : "None", frames ? "ok" : "missing") +
    row("Board reading", $("inspection-depth").value === "thorough" ? "Thorough" : "Fast") +
    row("Report", $("inspection-agent").checked ? "On" : "Off");
  const reason = inspectionReadiness();
  $("run-inspection").disabled = Boolean(reason);
  const hasDemoCapture = [boardFile, ...frameFiles].some((file) => file && captureSources.get(file)?.source === "demo");
  $("run-hint").textContent = reason || (hasDemoCapture ? "Demo analysis: saved in history, excluded from hive status and trends." : "Ready to run.");
  $("timing-hint").textContent = timingHint();
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
    return true;
  } catch (e) {
    toast(e.message, true);
    return false;
  } finally {
    $(`${kind}-file`).value = "";
  }
}

function renderPreviews() {
  const generation = ++previewGeneration;
  previewUrls.forEach((url) => URL.revokeObjectURL(url));
  previewUrls = [];
  const preview = (src, name, kind, index, local = false) =>
    `<div class="preview"><button type="button" data-image="${esc(src)}" aria-label="View ${esc(name)}"><img ${local ? "data-local-preview" : `src="${esc(src)}"`} alt="" decoding="async"></button><button type="button" class="remove" data-remove="${kind}" data-index="${esc(index)}" aria-label="Remove ${esc(name)}">${icon("close")}</button><small title="${esc(name)}">${esc(name)}</small></div>`;
  const filePreview = (file, kind, index) => {
    const url = URL.createObjectURL(file);
    previewUrls.push(url);
    return preview(url, file.name, kind, index, true);
  };
  const sample = $("board-sample").value;
  $("board-preview").innerHTML = boardFile
    ? filePreview(boardFile, "board", 0)
    : sample
      ? preview(apiUrl(`/api/sample_preview/board/${encodeURIComponent(sample)}?max_side=600`), sample, "sample-board", 0)
      : "";
  $("frames-preview").innerHTML =
    frameFiles.map((f, i) => filePreview(f, "frames", i)).join("") +
    checkedFrameSamples()
      .map((name) => preview(apiUrl(`/api/sample_preview/frame/${encodeURIComponent(name)}?max_side=400`), name, "sample-frame", name))
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
  $("run-benchmark").disabled = disabled;
  updateSummary();
}

async function startInspection(event) {
  event.preventDefault();
  if (activeJob || startingJob) return;
  if (!$("inspection-form").reportValidity()) return;
  const reason = inspectionReadiness();
  if (reason) return toast(reason, true);
  if (!selectedHive) return toast("Add a hive before you run an inspection.", true);
  const sample = $("board-sample").value;
  const frameSamples = checkedFrameSamples();
  if (!boardFile && !sample && !frameFiles.length && !frameSamples.length)
    return toast("Add a board photo or at least one frame.", true);
  if (frameFiles.length + frameSamples.length > 8) return toast("Choose up to 8 frame photos per inspection.", true);

  startingJob = true;
  updateRunButtons();
  const hiveId = selectedHive;
  const files = [...frameFiles];
  const board = boardFile;
  const timing = { startedAt: Date.now(), timingKey: timingKey() };
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
    capture_sources: Object.fromEntries([
      ["board", board], ...files.map((file, i) => [`frame_${i + 1}`, file]),
    ].filter(([, file]) => file && captureSources.has(file)).map(([key, file]) => [key, captureSources.get(file)])),
  };
  try {
    toast("Uploading photos…");
    payload.board_b64 = board ? await readBase64(board) : null;
    payload.frames_b64 = [];
    for (const file of files) payload.frames_b64.push(await readBase64(file));
    const result = await api("/api/inspect", payload);
    $("inspection-result").innerHTML = "";
    attachJob({ id: result.job_id, kind: "inspection", hiveId, ...timing });
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
  $("job-title").textContent = job.kind === "inspection" ? "Running inspection…" : "Running benchmark…";
  const stream = new EventSource(apiUrl(`/api/jobs/${encodeURIComponent(job.id)}/stream`));
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
      if (job.kind === "inspection" && job.startedAt && job.timingKey && job.timingReliable !== false) {
        const times = store.get("inspection-times", []);
        if (!times.some((r) => r.id === job.id)) {
          times.push({ id: job.id, key: job.timingKey, ms: Date.now() - job.startedAt });
          store.set("inspection-times", times.slice(-30));
        }
      }
      finishJob(job.kind === "inspection" ? "Inspection saved" : "Benchmark finished");
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
    job.timingReliable = false;
    if (activeJob?.id === job.id) $("job-title").textContent = "Reconnecting…";
  };
}

/* ── Colony Records & Audit Trail ────────────────────────────────────── */
async function loadHistory() {
  historyController?.abort();
  if ($("history-field-archive")) {
    $("history-field-archive").hidden = true;
    $("history-field-archive").innerHTML = "";
    $("history-photo-records").hidden = false;
    document.querySelector('[data-tour="explore"]').hidden = false;
  }
  const hive = selectedHive;
  $("history-description").textContent = hives().find(h => h.id === hive)?.field_archive
    ? "Published field observations with original dates and units. Any new photo inspections are kept separately below."
    : "Every inspection of a hive, with photos, evidence and the report.";
  if (!hive) {
    $("history-trends").innerHTML = "";
    $("history-list").innerHTML = '<li class="tl-empty">No colonies registered.</li>';
    $("history-count").textContent = "";
    $("history-result").innerHTML = emptyState(
      "No hives yet",
      "Add a hive, then run its first inspection.",
      `<button class="btn primary sm" type="button" data-add-hive>${icon("plus")}Add hive</button>`,
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
    $("export-hive").href = apiUrl(`/api/export/${encodeURIComponent(hive)}.zip`);
    $("export-hive").hidden = false;
    const link = $("job-result-link");
    if (link.dataset.resultHive === hive && data.inspections.some((r) => r.id === link.dataset.resultRecord)) {
      selectedRecord = link.dataset.resultRecord;
      delete link.dataset.resultRecord;
    }
    if (!data.inspections.some((r) => r.id === selectedRecord)) selectedRecord = data.inspections.at(-1)?.id || null;
    $("history-count").textContent = data.inspections.length || "0";
    if (typeof renderImportedHistory === "function") renderImportedHistory(data.field_history);
    if (data.field_history && !data.inspections.length) {
      $("history-trends").innerHTML = "";
      $("history-photo-records").hidden = true;
      document.querySelector('[data-tour="explore"]').hidden = true;
      return;
    }
    if (!data.inspections.length) {
      $("history-trends").innerHTML = "";
      $("history-list").innerHTML = '<li class="tl-empty">No records.</li>';
      $("history-result").innerHTML = emptyState(
        "No inspections yet",
        "Run an inspection with a board or frame photo to start this record.",
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
        "Could not load this hive",
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
          <small>${rec.demo_capture ? "Sample analysis" : STATUS[s]}${mpd != null ? ` · ${num(mpd)}/d` : ""}${rec.synthetic ? ", demo" : hasEv ? ", with evidence" : ""}</small>
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
  if (!rows.length) {
    $("history-trends").innerHTML = "";
    return;
  }
  const specs = [
    ["Mites per day", "mites_per_day", "", true],
    ["Honey", "honey_kg_hive_est", "kg", false],
    ["Brood", "brood_total_pct", "%", false],
    ["Stores", "stores_weeks", "weeks", false],
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
  return `<div class="composition"><h4>Comb, share of visible area</h4><div class="comp-bar">${keys
    .map(([c, k]) => `<i style="width:${((Math.max(0, m[k]) / total) * 100).toFixed(2)}%;background:${color(c)}" title="${esc(label(c))}: ${num(m[k])}%"></i>`)
    .join("")}</div><div class="comp-legend">${keys
    .map(([c, k]) => `<span><i style="background:${color(c)}"></i>${esc(label(c))} <b>${num(m[k])}%</b></span>`)
    .join("")}</div></div>`;
}

// Mite drift around this hive, from the yard map: who it is close to, and how far.
function driftNote(hiveId) {
  const links = state?.apiary?.drift_links || [];
  const byId = Object.fromEntries(hives().map((h) => [h.id, h]));
  const from = links.filter((l) => l.to_id === hiveId);
  const to = links.filter((l) => l.from_id === hiveId);
  if (!from.length && !to.length) return "";
  const nameOf = (id, fallback) => `${esc(shortName(byId[id] || { name: fallback }))}${isSynthetic(byId[id] || {}) ? " (Demo)" : ""}`;
  const list = (items) => (items.length > 1 ? `${items.slice(0, -1).join(", ")} and ${items.at(-1)}` : items[0]);
  const sentences = [];
  if (from.length) {
    sentences.push(`This hive stands ${list(from.map((l) => `${esc(l.distance_m)} m from ${nameOf(l.from_id, l.from_name)}, which drops ${num(byId[l.from_id]?.mites_per_day)} mites a day`))}.`);
  }
  if (to.length) {
    sentences.push(`Its mites can spread to ${list(to.map((l) => `${nameOf(l.to_id, l.to_name)} (${esc(l.distance_m)} m)`))}.`);
  }
  return `<div class="flag ${to.length ? "act" : ""}">${icon("alert")}<span><strong>Mite drift.</strong> ${sentences.join(" ")} <a href="#overview" data-go="overview">See the yard map</a></span></div>`;
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
  const captures = Object.entries(rec.inputs?.capture_sources || {});
  const demoCapture = Boolean(rec.demo_capture) || captures.some(([, source]) => source.source === "demo");
  const sourceCredits = (rec.provenance?.sources || []).map((source) => `<li>${esc(source.title)} · ${esc(source.author)} · ${esc(source.license)}</li>`).join("");
  const captureHtml = captures.length ? `<div class="capture-provenance"><h4>Captured photos</h4><ul>${captures.map(([photo, source]) => `<li><strong>${esc(photo.replaceAll("_", " "))}</strong> · ${source.source === "camera" ? "Camera" : source.source === "demo" ? "Demo video (recorded)" : "Uploaded video (recorded)"}<br>${esc(source.name)} · ${esc(source.captured_at)} · ${esc(source.width)} × ${esc(source.height)} px${source.video_seconds == null ? "" : ` · video ${esc(Number(source.video_seconds).toFixed(1))}s`}${source.source === "demo" ? ' · <a href="https://commons.wikimedia.org/wiki/File:Queen_honey_bee_laying_eggs.webm" target="_blank" rel="noopener">Source</a> · <a href="https://creativecommons.org/licenses/by-sa/3.0/" target="_blank" rel="noopener">CC BY-SA 3.0</a> (excerpt, captured still and analysis annotations)' : ""}</li>`).join("")}</ul></div>` : "";
  const s = statusOf(rec.status?.overall);
  const fileUrl = (name, size = 1400) =>
    apiUrl(`/api/file/${encodeURIComponent(hiveId)}/${encodeURIComponent(rec.id)}/${encodeURIComponent(name)}?max_side=${size}`);

  const metricDefs = [
    ["Mites per day", m.mites_per_day, "", m.mites_per_day_change],
    ["Mites counted", m.mite_count, ""],
    ["Rejected as debris", m.rejected_detections, ""],
    ["Brood", m.brood_total_pct, "%"],
    ["Capped honey", m.honey_pct, "%"],
    ["Honey in hive", m.honey_kg_hive_est, "kg"],
    ["Stores", m.stores_weeks, "wk"],
  ].filter(([, v]) => v != null);
  const metrics = metricDefs.length
    ? `<div class="metric-grid">${metricDefs
        .map(
          ([label, v, unit, ch]) =>
            `<div class="metric"><span>${label}</span><strong>${num(v)}${unit ? `<small>${unit}</small>` : ""}${!demoCapture && ch != null && Math.abs(ch) >= 0.05 ? `<span class="delta ${ch > 0 ? "up" : ""}" style="margin-left:6px">${ch > 0 ? "+" : "−"}${num(Math.abs(ch))}</span>` : ""}</strong></div>`,
        )
        .join("")}</div>`
    : "";

  const flags = `<div class="status-checks" aria-label="Status by measurement">${statusReasons(rec.status?.levels, m)
    .map((r) => `<div class="status-check">${badge(r.level)}<span>${esc(r.text)}</span></div>`).join("")}</div>`;

  const overlays = Object.keys(files)
    .filter((k) => k.endsWith("_overlay"))
    .sort((a, b) => Number(b.startsWith("board")) - Number(a.startsWith("board")))
    .map((key) => {
      const original = files[key.replace(/_overlay$/, "")];
      const board = key.startsWith("board");
      const src = fileUrl(files[key]);
      const title = board ? "Sticky board" : `${key.replace(/_overlay$/, "").replaceAll("_", " ")}`;
      const caption = board
        ? "Green: found by SAM 3.1. Blue: confirmed by Muse Spark. Red cross: rejected by the size and shape checks."
        : "Yellow: capped honey. Brown: capped brood. White: larvae. Orange: pollen. Blue: empty or nectar. Grey: bees covering the comb.";
      return `<figure class="figure"><div class="figure-head"><strong>${esc(title)}</strong>${original ? `<button class="link-btn" type="button" data-image="${esc(fileUrl(original, 2400))}">Original ${icon("external")}</button>` : ""}</div><button type="button" data-image="${esc(fileUrl(files[key], 2400))}" aria-label="Enlarge ${esc(title)}"><img src="${esc(src)}" alt="${esc(title)}" loading="lazy" decoding="async"></button><figcaption>${caption}</figcaption></figure>`;
    })
    .join("");

  const evidenceKeys = Object.keys(files).filter((k) => k === "board_evidence" || k.startsWith("board_muse_sheet"));
  const evidence = evidenceKeys.length
    ? `<div class="evidence">
        <div class="evidence-head">
          <h4>Evidence</h4>
          <span class="tag measured">${evidenceKeys.length} images</span>
        </div>
        <div class="evidence-grid">${evidenceKeys
          .map((k) => {
            const label =
              k === "board_evidence"
                ? "Counted and rejected spots"
                : `Muse Spark sheet ${k.split("_").at(-1)}`;
            return `<button type="button" data-image="${esc(fileUrl(files[k], 2400))}"><img src="${esc(fileUrl(files[k], 600))}" alt="" loading="lazy"><span>${esc(label)}</span></button>`;
          })
          .join("")}</div>
      </div>`
    : "";

  const urgency = { now: ["act", "Immediate"], this_week: ["watch", "This week"], next_inspection: ["", "Next inspection"] };
  const reportHtml = report
    ? `<div class="report-summary"><strong>Summary</strong>${esc(report.summary)}</div>
      ${
        report.actions?.length
          ? `<div class="report-section"><h4>What to do</h4>${report.actions
              .map((a) => {
                const [cls, text] = urgency[a.urgency] || ["", a.urgency || ""];
                return `<div class="action"><div class="action-top"><strong>${esc(a.action)}</strong>${text ? `<span class="badge ${cls} plain">${esc(text)}</span>` : ""}</div>${a.reason ? `<p>${esc(a.reason)}</p>` : ""}</div>`;
              })
              .join("")}</div>`
          : ""
      }
      ${
        report.findings?.length
          ? `<div class="report-section"><h4>Findings</h4>${report.findings
              .map((f) => `<div class="finding">${icon("check")}<div>${esc(f.text)}<br><small>Based on claims ${esc((f.claim_ids || []).join(", "))}</small></div></div>`)
              .join("")}</div>`
          : ""
      }
      ${report.caveats?.length ? `<div class="report-section"><h4>Caveats</h4>${report.caveats.map((c) => `<p class="caveat">${esc(c)}</p>`).join("")}</div>` : ""}
      ${
        report.discarded_findings?.length
          ? `<div class="report-section"><h4>Dropped, not backed by measurements</h4>${report.discarded_findings.map((f) => `<p class="caveat"><s>${esc(f.text)}</s></p>`).join("")}</div>`
          : ""
      }`
    : '<p class="report-summary">Measurements only. No report was written for this inspection.</p>';

  const claims = rec.claims || [];
  const rejectedCount = claims.filter((c) => c.verdict === "rejected").length;
  const verifiedCount = claims.filter((c) => c.verdict === "verified").length;
  const claimsHtml = claims.length
    ? `<details class="claims-box">
        <summary>Claims checked against measurements · ${verifiedCount} verified, ${rejectedCount} rejected</summary>
        <div class="table-wrap"><table class="claims">
          <thead><tr><th>Result</th><th>Claim</th><th>Measured</th></tr></thead>
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
        </table></div>
      </details>`
    : "";

  el.innerHTML = `<article class="panel record">
    <header class="record-head">
      <div>
        <h2>${esc(dateLabel(rec.date))} ${badge(s)} ${rec.synthetic ? '<span class="tag demo">Demo data</span>' : demoCapture ? '<span class="tag demo">Sample analysis</span>' : '<span class="tag measured">Measured</span>'}</h2>
        <p>${esc(hiveName(hiveId))}${rec.models?.segmentation && !rec.synthetic ? `, ${esc(rec.models.segmentation)} and ${esc(rec.models.reasoning)}` : ""}</p>
      </div>
      <button class="btn sm record-download" type="button">${icon("download")}Export JSON</button>
    </header>
    <div class="record-body">
      ${demoCapture ? `<div class="alert warn"><p>Analysis of sample media. Excluded from live hive status and trends. ${esc(rec.provenance?.note || "These photos do not establish the condition of this colony.")}</p></div>` : ""}
      ${sourceCredits ? `<details><summary>Photo sources and licenses</summary><ul>${sourceCredits}</ul><p>Source URLs and modification details are included in Export JSON and the hive ZIP.</p></details>` : ""}
      ${rec.synthetic ? '<div class="alert warn">' + icon("info") + "<p>Demo record. These numbers and recommendations are simulated. Do not use this record to make decisions about a real colony.</p></div>" : ""}
      <div class="report report-lead">${reportHtml}</div>
      ${flags}
      ${demoCapture ? "" : driftNote(hiveId)}
      ${metrics}
      ${compositionBar(m)}
      ${rec.inputs?.note ? `<p class="note"><b>Note:</b> ${esc(rec.inputs.note)}</p>` : ""}
      ${captureHtml}
      <div class="record-cols">
        <div class="figures">${evidence}${overlays || emptyState("No photos", rec.synthetic ? "Demo records have no photos." : "This inspection has no overlay.")}</div>
        <div class="report">${claimsHtml}${rec.status?.flags?.length ? `<details><summary>Rule notes (${rec.status.flags.length})</summary>${rec.status.flags.map((f) => `<p>${esc(f)}</p>`).join("")}</details>` : ""}${rec.trace?.length ? '<details><summary>Agent trace (' + rec.trace.length + ' tool calls)</summary><pre class="trace-log"></pre></details>' : ""}</div>
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
      title: "Sticky board: SAM 3.1 alone finds 0 of 21 mites, HiveLens finds 20",
      desc: "On the whole photo the 30 px mites are too small for SAM. HiveLens reads 600 px and 300 px tiles, asks Muse Spark about unclear spots and checks each shape.",
    },
    {
      file: "IMG_5582_evidence.jpg",
      title: "Every counted and rejected spot",
      desc: "Close-ups of the 20 counted mites and 9 rejected spots, with the size, colour and shape numbers behind each decision.",
    },
    {
      file: "IMG_5582_muse_sheet_1.jpg",
      title: "What Muse Spark was shown",
      desc: "Spots SAM was unsure about. Blue: Muse Spark said mite. Red cross: Muse said mite, the shape checks disagreed.",
    },
    {
      file: "A_slice_of_the_brood_nest_naive_vs_hivelens.jpg",
      title: "Frame: SAM 3.1 alone versus SAM with Muse Spark",
      desc: "Asked for capped brood, SAM marks almost the whole frame. HiveLens uses SAM for the comb and bees, and Muse Spark labels each tile.",
    },
  ].filter((x) => imgs.includes(x.file));

  wrap.innerHTML = items
    .map((item) => {
      const fullUrl = apiUrl(`/api/demo_asset/${encodeURIComponent(item.file)}?max_side=2400`);
      const thumbUrl = apiUrl(`/api/demo_asset/${encodeURIComponent(item.file)}?max_side=800`);
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
    ? `${s.images} evaluation boards with ${s.experts_total} expert annotations. Exploratory development included overlapping boards: this is not a fully untouched test set.`
    : "No saved benchmark yet.";
  $("benchmark-stats").innerHTML =
    kpi("F1", num(s?.sam_f1, 2), s?.cv_f1 != null ? `Classic method: ${num(s.cv_f1, 2)}` : "Test boards", "") +
    kpi("Precision", num(s?.sam_precision, 2), "Counted mites that are real", "") +
    kpi("Recall", num(s?.sam_recall, 2), "Real mites that were found", "") +
    kpi("Count error", `${num(s?.sam_mae, 1)}`, "Mites per board, HiveLens", "") +
    kpi("Classic method error", `${num(s?.cv_mae, 0)}`, "Mites per board, darkness threshold", "");
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
    $("benchmark-chart").innerHTML = emptyState("No benchmark yet", "Run the benchmark to compare HiveLens with the expert counts.");
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
  const target = event.target.closest("button,a");
  if (!target) return;
  if (target.hasAttribute("data-back-top")) {
    event.preventDefault();
    $("main").focus({ preventScroll: true });
    window.scrollTo({ top: 0, behavior: "instant" });
    return;
  }
  if (target.dataset.paletteChoice) {
    applyPalette(target.dataset.paletteChoice, true);
    return;
  }
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
  if (target.id === "welcome-example" && welcomeExample) {
    selectHive(welcomeExample.hiveId);
    selectedRecord = welcomeExample.recordId;
    go("history");
    return;
  }
  if (target.dataset.go) go(target.dataset.go);
  if (target.dataset.farm) selectFarm(target.dataset.farm);
  if (target.hasAttribute("data-add-hive")) {
    fillFarmSelect($("new-hive-farm"), selectedFarm);
    $("add-hive-dialog").showModal();
    $("new-hive-name").focus();
  }
  if (target.dataset.close) $(target.dataset.close).close();
  if (target.dataset.hive) {
    event.preventDefault();
    selectHive(target.dataset.hive, target.dataset.destination);
  }
  if (target.dataset.fact) {
    // Top bar facts jump to what they count: the hive table filtered by status, or the forecast.
    if (target.dataset.fact === "weather") {
      $("farm-conditions").scrollIntoView({ behavior: "smooth", block: "start" });
    } else {
      statusFilter = target.dataset.fact;
      renderOverview();
      $("hives-panel").scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }
  if (target.dataset.filter) {
    statusFilter = target.dataset.filter;
    document.querySelectorAll("#status-filter button").forEach((b) => b.setAttribute("aria-pressed", b === target));
    renderHiveGrid();
  }
  if (target.id === "clear-hive-filters") {
    $("hive-search").value = "";
    $("source-filter").value = "all";
    statusFilter = "all";
    renderHiveGrid();
    $("hive-search").focus();
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
    const data = await api("/api/hives", {
      name,
      location: $("new-hive-location").value.trim(),
      farm_id: $("new-hive-farm").value || null,
    });
    selectedHive = data.hive.id;
    selectedRecord = null;
    store.set("hive", selectedHive);
    $("add-hive-dialog").close();
    $("add-hive-form").reset();
    await loadState();
    toast(`${data.hive.name} added.`);
  });
});
// The farm form (add and edit) is handled in farm.js.
$("seed-demo").addEventListener("click", () =>
  withButton($("seed-demo"), async () => {
    const result = await api("/api/seed_apiary", {});
    await loadState();
    toast(result.created ? `${result.created} demo hives added.` : "The demo farms are already loaded.");
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
    if (activeJob) attachJob({ ...activeJob, timingReliable: false });
  }
});

/* ── Boot ────────────────────────────────────────────────────────────── */
hydrateIcons();
applyWorkspaceMode();
$("workspace-mode").addEventListener("change", (event) => {
  const url = new URL(location.href);
  url.searchParams.set("mode", event.target.value);
  location.assign(url.href);
});
applyTheme(store.get("corp_theme", "light"));
applyPalette(document.documentElement.dataset.palette);
restoreDraft();
const initialView = entryView(location.hash.slice(1), store.get("welcomed", false));
if (initialView === "welcome" && location.hash !== "#welcome") history.replaceState(null, "", "#welcome");
route();
loadState().then((ok) => {
  const job = jobSession.get();
  if (ok && job) attachJob({ ...job, timingReliable: false });
});
