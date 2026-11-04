"use strict";
// Usage and cost page, settings page, and the profile button in the sidebar.
// Runs after app.js and uses its helpers ($, esc, api, num, toast, withButton, state, view).

const ROLE_LABELS = { beekeeper: "Beekeeper", owner: "Apiary owner", inspector: "Bee inspector", researcher: "Researcher" };

/* ── Profile button ──────────────────────────────────────────────────── */
// The uploaded photo, or a plain yellow circle when there is none.
function paintAvatar(el, profile) {
  const v = profile?.photo_version;
  el.innerHTML = v ? `<img src="${apiUrl(`/api/profile_photo?v=${encodeURIComponent(v)}`)}" alt="" />` : el.id === "profile-avatar" ? icon("settings") : "";
  el.classList.toggle("settings-icon", !v && el.id === "profile-avatar");
}

function renderProfileChip() {
  const p = state?.profile || {};
  paintAvatar($("profile-avatar"), p);
  $("profile-name").textContent = "Settings";
  $("profile-sub").textContent = p.name || "Theme, profile & prices";
}

/* ── Money ───────────────────────────────────────────────────────────── */
function usd(value) {
  if (value == null || !Number.isFinite(value)) return "–";
  if (value === 0) return "$0.00";
  if (Math.abs(value) < 0.01) return `$${value.toFixed(4)}`;
  return `$${value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}
const count = (n) => (n ?? 0).toLocaleString();
const modelLabel = (m) => (m.kind === "segmentation" ? "SAM 3.1" : "Muse Spark");

/* ── Usage page ──────────────────────────────────────────────────────── */
let usageRequest = null;

function costChart(daily) {
  const max = Math.max(...daily.map((d) => d.cost), 0);
  if (!max) return '<p class="hint chart-empty">Estimated cost is $0.00 for the last 30 days.</p>';
  const W = 720;
  const H = 150;
  const base = 120;
  const step = W / daily.length;
  const bars = daily
    .map((d, i) => {
      const h = (d.cost / max) * (base - 12);
      const x = i * step + step * 0.18;
      const label = new Date(`${d.date}T12:00:00`).toLocaleDateString(undefined, { day: "numeric", month: "short" });
      return `<g><title>${esc(label)}: ${esc(usd(d.cost))}</title><rect class="cost-bar" x="${x.toFixed(1)}" y="${(base - h).toFixed(1)}" width="${(step * 0.64).toFixed(1)}" height="${Math.max(h, d.cost ? 1.5 : 0).toFixed(1)}" rx="2"/>${
        i % 5 === 0 || i === daily.length - 1 ? `<text class="axis" x="${(i * step + step / 2).toFixed(1)}" y="${base + 18}" text-anchor="middle">${esc(label)}</text>` : ""
      }</g>`;
    })
    .join("");
  return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Estimated cost per day, last 30 days"><path class="grid-line" d="M0 ${base}H${W}"/>${bars}</svg>`;
}

function usageHtml(u) {
  const t = u.totals;
  const proj = u.projection;
  const budget = u.budget || 0;
  const month = t.month.cost;
  const kpis =
    kpi("This month (est.)", usd(month), `${count(t.month.calls)} model calls`) +
    kpi("Today (est.)", usd(t.today.cost), `${count(t.today.calls)} model calls`) +
    kpi("All time (est.)", usd(t.all.cost), u.tracking_since ? `Since ${new Date(u.tracking_since * 1000).toLocaleDateString()}` : "Nothing recorded yet") +
    kpi("Est. per inspection", usd(u.per_inspection), u.inspections_priced ? `Average of ${u.inspections_priced} inspection${u.inspections_priced === 1 ? "" : "s"}` : "Run an inspection to measure") +
    kpi("Monthly projection", usd(proj.monthly_cost), `${proj.hives} hives, ${num(proj.inspections_per_month, 0)} inspections each`);

  const budgetBar = budget
    ? `<section class="panel budget">
        <div class="budget-top"><strong>Monthly budget (estimated usage)</strong><span>${esc(usd(month))} of ${esc(usd(budget))}</span></div>
        <div class="budget-bar ${month > budget ? "over" : month > budget * 0.8 ? "near" : ""}"><i style="width:${Math.min(100, (month / budget) * 100).toFixed(1)}%"></i></div>
        <p class="hint">${month > budget ? "Estimated usage exceeds this month’s budget." : `${esc(usd(budget - month))} estimated budget remaining.`}</p>
      </section>`
    : "";

  const estimate =
    proj.monthly_cost != null
      ? `<p class="estimate">At <strong>${esc(usd(u.per_inspection))}</strong> per inspection, ${proj.hives} hives inspected ${num(proj.inspections_per_month, 0)} times a month cost about <strong>${esc(usd(proj.monthly_cost))}</strong> a month${budget ? `, against a budget of ${esc(usd(budget))}` : ""}.</p>`
      : `<p class="estimate">The estimate appears after the first inspection is recorded: it prices recorded model calls using the rates in Settings.</p>`;

  const models = u.by_model.length
    ? `<table class="table">
        <thead><tr><th>Model</th><th class="num">Calls</th><th class="num">Input tokens</th><th class="num">Cached</th><th class="num">Output tokens</th><th class="num">Est. cost</th></tr></thead>
        <tbody>${u.by_model
          .map(
            (m) => `<tr><td><strong>${esc(modelLabel(m))}</strong> <span class="muted">${esc(m.model)}</span></td><td class="num">${count(m.calls)}</td><td class="num">${count(m.input_tokens)}</td><td class="num">${count(m.cached_tokens)}</td><td class="num">${count(m.output_tokens)}</td><td class="num strong">${esc(usd(m.cost))}</td></tr>`,
          )
          .join("")}</tbody>
      </table>`
    : emptyState("No recorded calls yet", "Calls are recorded from now on, each time an inspection or benchmark reaches the Meta API.");

  const jobs = u.jobs.length
    ? `<table class="table">
        <thead><tr><th>When</th><th>Run</th><th class="num">SAM 3.1 calls</th><th class="num">Muse Spark calls</th><th class="num">Tokens</th><th class="num">Est. cost</th></tr></thead>
        <tbody>${u.jobs
          .map(
            (j) => `<tr><td class="muted">${esc(new Date(j.started * 1000).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }))}</td><td>${esc(j.label || (j.kind === "benchmark" ? "Benchmark" : "Inspection"))}</td><td class="num">${count(j.segmentation)}</td><td class="num">${count(j.reasoning)}</td><td class="num">${count(j.input_tokens + j.output_tokens)}</td><td class="num strong">${esc(usd(j.cost))}</td></tr>`,
          )
          .join("")}</tbody>
      </table>`
    : '<p class="hint panel-note">Each inspection and benchmark run will be listed here with its estimated cost.</p>';

  const p = u.prices;
  return `<div id="usage-stats" class="kpi-strip">${kpis}</div>
    ${budgetBar}
    <section class="panel">
      <header class="panel-head"><div class="panel-title-group"><h2>Running cost estimate</h2><span class="sub-text">Change hives per month and budget in Settings.</span></div></header>
      <div class="panel-body">${estimate}</div>
    </section>
    <section class="panel">
      <header class="panel-head"><div class="panel-title-group"><h2>Estimated cost per day</h2><span class="sub-text">Last 30 days</span></div></header>
      <div class="chart">${costChart(u.daily)}</div>
    </section>
    <section class="panel"><header class="panel-head"><h2>By model</h2></header><div class="table-wrap">${models}</div></section>
    <section class="panel"><header class="panel-head"><h2>Recent runs</h2></header><div class="table-wrap">${jobs}</div></section>
    <section class="panel">
      <header class="panel-head"><h2>Cached analysis</h2></header>
      <div class="panel-body prose">
        <p>${count(u.cache.sam)} SAM 3.1 answers and ${count(u.cache.muse)} Muse Spark answers are stored on this computer. Matching analysis requests can reuse these results. Report generation still makes new API calls. The stored SAM results represent an estimated request value${
          u.cache.sam_value ? ` of ${esc(usd(u.cache.sam_value))} at the configured SAM rate` : " of $0.00"
        }; this is not a measured saving.</p>
        <p class="hint">Configured estimate rates (SAM defaults to a placeholder): Muse Spark ${esc(usd(p.muse.input_per_m))} input, ${esc(usd(p.muse.cached_per_m))} cached input and ${esc(usd(p.muse.output_per_m))} output per million tokens. SAM 3.1 ${esc(usd(p.sam.per_request))} per request. Reasoning tokens are billed as output.</p>
      </div>
    </section>`;
}

function renderUsage() {
  const el = $("usage-body");
  if (usageRequest) return;
  usageRequest = api("/api/usage")
    .then((u) => {
      if (view === "usage") el.innerHTML = usageHtml(u);
    })
    .catch((e) => {
      el.innerHTML = `<div class="alert danger"><span>Could not load usage. ${esc(e.message)}</span></div>`;
    })
    .finally(() => {
      usageRequest = null;
    });
}

/* ── Settings page ───────────────────────────────────────────────────── */
const SETTINGS_FIELDS = [
  ["set-name", ["profile", "name"]],
  ["set-email", ["profile", "email"]],
  ["set-org", ["profile", "organisation"]],
  ["set-role", ["profile", "role"]],
  ["price-muse-in", ["prices", "muse", "input_per_m"], true],
  ["price-muse-cached", ["prices", "muse", "cached_per_m"], true],
  ["price-muse-out", ["prices", "muse", "output_per_m"], true],
  ["price-sam-req", ["prices", "sam", "per_request"], true],
  ["price-sam-in", ["prices", "sam", "input_per_m"], true],
  ["price-sam-out", ["prices", "sam", "output_per_m"], true],
  ["plan-per-month", ["planning", "inspections_per_hive_month"], true],
  ["plan-budget", ["planning", "monthly_budget"], true],
];
let settingsDirty = false;

function fillSettings(data) {
  for (const [id, path] of SETTINGS_FIELDS) $(id).value = path.reduce((o, k) => o?.[k], data.settings) ?? "";
  paintAvatar($("settings-avatar"), data.settings.profile);
  $("photo-remove").hidden = !data.settings.profile.photo_version;
  const a = data.api;
  $("api-info").innerHTML = `
    <div><dt>API key</dt><dd>${a.has_api_key ? '<span class="badge good">Configured on server</span>' : '<span class="badge act">Missing</span> Configure MODEL_API_KEY on the server.'}</dd></div>
    <div><dt>Endpoint</dt><dd><code>${esc(a.base_url)}</code></dd></div>
    <div><dt>Segmentation</dt><dd><code>${esc(a.segment_model)}</code></dd></div>
    <div><dt>Reasoning</dt><dd><code>${esc(a.reasoning_model)}</code>, effort ${esc(a.reasoning_effort)}</dd></div>
    <div><dt>Usage log</dt><dd><code>${workspaceMode === "production" ? "data/workspaces/production/usage.jsonl" : "data/usage.jsonl"}</code></dd></div>`;
  settingsDirty = false;
  $("settings-hint").textContent = "";
}

function renderSettings() {
  document.querySelectorAll("#settings-form input, #settings-form select, #settings-form button").forEach((el) => {
    if (!el.closest(".appearance-settings")) el.disabled = state?.can_write === false;
  });
  if (settingsDirty) return; // keep what the user is typing
  api("/api/settings")
    .then(fillSettings)
    .catch((e) => toast(`Could not load settings. ${e.message}`, true));
}

$("settings-form").addEventListener("input", (event) => {
  if (event.target.id === "photo-file") return;
  settingsDirty = true;
  $("settings-hint").textContent = "Unsaved changes.";
});

$("settings-form").addEventListener("submit", (event) => {
  event.preventDefault();
  const body = {};
  for (const [id, path, numeric] of SETTINGS_FIELDS) {
    const raw = $(id).value.trim();
    const value = numeric ? (raw === "" ? 0 : Number(raw)) : raw;
    path.slice(0, -1).reduce((o, k) => (o[k] ??= {}), body)[path.at(-1)] = value;
  }
  withButton($("save-settings"), async () => {
    const data = await api("/api/settings", body);
    fillSettings(data);
    state.profile = data.settings.profile;
    renderProfileChip();
    toast("Settings saved.");
  });
});

/* ── Profile photo ───────────────────────────────────────────────────── */
async function shrinkToDataUrl(file, maxSide = 1024) {
  const bitmap = await createImageBitmap(file);
  const scale = Math.min(1, maxSide / Math.max(bitmap.width, bitmap.height));
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(bitmap.width * scale);
  canvas.height = Math.round(bitmap.height * scale);
  canvas.getContext("2d").drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  bitmap.close?.();
  return canvas.toDataURL("image/jpeg", 0.9);
}

function photoSaved(data) {
  state.profile = data.settings.profile;
  paintAvatar($("settings-avatar"), state.profile);
  $("photo-remove").hidden = !state.profile.photo_version;
  renderProfileChip();
}

$("photo-file").addEventListener("change", async (event) => {
  const file = event.target.files?.[0];
  event.target.value = "";
  if (!file) return;
  if (!/^image\/(jpeg|png|webp)$/.test(file.type)) return toast("Choose a JPEG, PNG or WebP photo.", true);
  try {
    photoSaved(await api("/api/profile_photo", { image: await shrinkToDataUrl(file) }));
    toast("Profile photo updated.");
  } catch (e) {
    toast(e.message || "Could not read that photo.", true);
  }
});

$("photo-remove").addEventListener("click", () =>
  withButton($("photo-remove"), async () => {
    photoSaved(await api("/api/profile_photo", { remove: true }));
    toast("Profile photo removed.");
  }),
);
