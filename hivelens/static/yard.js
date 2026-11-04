"use strict";
// Yard maps: one per farm, drawn to scale. In layout mode the beekeeper drags hives to where
// they really stand, arranges them in rows, sees the distances, and picks each hive's paint colour.
// Runs after app.js and uses its helpers ($, esc, api, num, state, farms, …).

const mapSelection = {}; // farm key → selected hive id
const yardEdit = {}; // farm key → { pos: { hiveId: {x, y} }, dirty, arrange }
const SNAP_M = 0.25;
const MEASURE_M = 6; // distances shown while editing
const DRIFT_M = 4; // same threshold the server uses for drift links
// Bees tell blue, yellow and white apart well and see red as dark, so red is left out.
const PAINTS = [
  ["White", "#f3f1ea"],
  ["Yellow", "#e9c46a"],
  ["Blue", "#6f9fd8"],
  ["Green", "#9cc49a"],
  ["Lilac", "#b39ddb"],
  ["Orange", "#e8a15c"],
  ["Grey", "#a7b0b6"],
];

const TONE = {
  good: ["var(--good)", "var(--good-soft)"],
  watch: ["var(--watch)", "var(--watch-soft)"],
  act: ["var(--act)", "var(--act-soft)"],
  unknown: ["var(--border-strong)", "var(--surface-2)"],
};

function inkFor(hex) {
  const n = parseInt(hex.slice(1), 16);
  const lum = (0.299 * ((n >> 16) & 255) + 0.587 * ((n >> 8) & 255) + 0.114 * (n & 255)) / 255;
  return lum > 0.62 ? "#1d2a20" : "#ffffff";
}
const snap = (v) => Math.round(v / SNAP_M) * SNAP_M;
const farmIdOfKey = (key) => (key === "unassigned" ? null : key);

function positionOf(key, h) {
  const edit = yardEdit[key];
  return edit?.pos[h.id] || { x: h.x_m || 0, y: h.y_m || 0 };
}

/* ── Drawing ─────────────────────────────────────────────────────────── */
function yardSvg(key, members, links) {
  const editing = Boolean(yardEdit[key]);
  const pts = members.map((h) => positionOf(key, h));
  const margin = editing ? 2.5 : 0;
  let minX = Math.floor(Math.min(...pts.map((p) => p.x)) - margin);
  let maxX = Math.ceil(Math.max(...pts.map((p) => p.x)) + margin);
  let minY = Math.floor(Math.min(...pts.map((p) => p.y)) - margin);
  let maxY = Math.ceil(Math.max(...pts.map((p) => p.y)) + margin);
  if (maxX - minX < 4) maxX = minX + 4;
  if (maxY - minY < (editing ? 3 : 1)) maxY = minY + (editing ? 3 : 1);
  const spanX = maxX - minX;
  const spanY = maxY - minY;

  const W = 720;
  const pad = { l: 84, r: 48, t: 44, b: 64 };
  const scale = Math.min((W - pad.l - pad.r) / spanX, 90, ((editing ? 520 : 440) - pad.t - pad.b) / spanY);
  const H = Math.round(spanY * scale + pad.t + pad.b);
  const offX = pad.l + (W - pad.l - pad.r - spanX * scale) / 2;
  const sx = (x) => offX + (x - minX) * scale;
  const sy = (y) => pad.t + (y - minY) * scale;
  const tw = 64;
  const th = 46;

  const step = spanX > 40 ? 5 : spanX > 14 ? 2 : 1;
  let grid = "";
  for (let gx = minX; gx <= maxX; gx += step) {
    const px = sx(gx).toFixed(1);
    grid += `<line class="map-grid" x1="${px}" y1="${pad.t - 26}" x2="${px}" y2="${H - pad.b + 30}"/>`;
    grid += `<text class="map-axis" x="${px}" y="${H - 12}" text-anchor="middle">${gx} m</text>`;
  }
  for (let gy = minY; gy <= maxY; gy += step) {
    const py = sy(gy).toFixed(1);
    grid += `<line class="map-grid" x1="${(offX - tw / 2 - 8).toFixed(1)}" y1="${py}" x2="${(offX + spanX * scale + 34).toFixed(1)}" y2="${py}"/>`;
    grid += `<text class="map-axis" x="${(offX - tw / 2 - 14).toFixed(1)}" y="${(sy(gy) + 3.5).toFixed(1)}" text-anchor="end">${gy} m</text>`;
  }

  // Stop a line at the tile edge (tiles are rectangles, so the gap depends on the direction).
  const edgeGap = (ux, uy) =>
    Math.min(Math.abs(ux) > 1e-6 ? tw / 2 / Math.abs(ux) : Infinity, Math.abs(uy) > 1e-6 ? th / 2 / Math.abs(uy) : Infinity) + 6;
  const segment = (a, b) => {
    const pa = positionOf(key, a);
    const pb = positionOf(key, b);
    const x1 = sx(pa.x);
    const y1 = sy(pa.y);
    const x2 = sx(pb.x);
    const y2 = sy(pb.y);
    const len = Math.hypot(x2 - x1, y2 - y1) || 1;
    const ux = (x2 - x1) / len;
    const uy = (y2 - y1) / len;
    const g = edgeGap(ux, uy);
    return { x1: x1 + ux * g, y1: y1 + uy * g, x2: x2 - ux * g, y2: y2 - uy * g, mx: (x1 + x2) / 2, my: (y1 + y2) / 2, long: len > g * 2 };
  };

  let edges = "";
  if (editing) {
    // Measuring lines between every pair closer than MEASURE_M.
    for (let i = 0; i < members.length; i++) {
      for (let j = i + 1; j < members.length; j++) {
        const a = members[i];
        const b = members[j];
        const pa = positionOf(key, a);
        const pb = positionOf(key, b);
        const d = Math.hypot(pa.x - pb.x, pa.y - pb.y);
        if (d > MEASURE_M) continue;
        const risky = d <= DRIFT_M && (a.overall === "act" || b.overall === "act");
        const s = segment(a, b);
        if (!s.long) continue;
        edges += `<g class="map-measure${risky ? " risky" : ""}"><line x1="${s.x1.toFixed(1)}" y1="${s.y1.toFixed(1)}" x2="${s.x2.toFixed(1)}" y2="${s.y2.toFixed(1)}"/>
          <text x="${s.mx.toFixed(1)}" y="${(s.my - 5).toFixed(1)}" text-anchor="middle">${num(d)} m</text></g>`;
      }
    }
  } else {
    const byId = Object.fromEntries(members.map((h) => [h.id, h]));
    edges = links
      .map((l) => {
        const a = byId[l.from_id];
        const b = byId[l.to_id];
        if (!a || !b) return "";
        const s = segment(a, b);
        return s.long
          ? `<line class="map-link ${l.risk === "high" ? "high" : ""}" x1="${s.x1.toFixed(1)}" y1="${s.y1.toFixed(1)}" x2="${s.x2.toFixed(1)}" y2="${s.y2.toFixed(1)}"><title>${esc(shortName(a))} to ${esc(shortName(b))}: ${esc(l.distance_m)} m, ${esc(l.risk)} exposure</title></line>`
          : "";
      })
      .join("");
  }

  const nodes = members
    .map((h) => {
      const p = positionOf(key, h);
      const cx = sx(p.x);
      const cy = sy(p.y);
      const s = statusOf(h.overall);
      const [stroke, soft] = TONE[s];
      const fill = h.color || soft;
      const ink = h.color ? inkFor(h.color) : "var(--text)";
      const measured = !isSynthetic(h);
      const selected = mapSelection[key] === h.id;
      const value = h.mites_per_day != null ? num(h.mites_per_day) : "–";
      const label = `${displayName(h)}, ${STATUS[s]}, ${h.mites_per_day != null ? `${num(h.mites_per_day)} mites per day` : "no inspection"}${measured ? ", measured" : ""}`;
      return `<g class="map-node${measured ? " measured" : ""}${selected ? " selected" : ""}${editing ? " draggable" : ""}" data-map-hive="${esc(h.id)}" data-map-farm="${esc(key)}" tabindex="0" role="button" aria-pressed="${selected}" aria-label="${esc(label)}">
        <title>${esc(label)}${editing ? `. Position ${num(p.x, 2)} m, ${num(p.y, 2)} m` : ""}</title>
        ${measured || selected ? `<rect class="map-ring" x="${(cx - tw / 2 - 5).toFixed(1)}" y="${(cy - th / 2 - 5).toFixed(1)}" width="${tw + 10}" height="${th + 10}" rx="13"/>` : ""}
        <rect class="map-tile" x="${(cx - tw / 2).toFixed(1)}" y="${(cy - th / 2).toFixed(1)}" width="${tw}" height="${th}" rx="9" fill="${fill}" stroke="${stroke}"/>
        <text class="map-value" x="${cx.toFixed(1)}" y="${(cy + 1).toFixed(1)}" text-anchor="middle" style="fill:${ink}">${esc(value)}</text>
        <text class="map-unit" x="${cx.toFixed(1)}" y="${(cy + 14).toFixed(1)}" text-anchor="middle" style="fill:${ink}">mites/day</text>
        <text class="map-label" x="${cx.toFixed(1)}" y="${(cy + th / 2 + 17).toFixed(1)}" text-anchor="middle">${esc(shortName(h))}</text>
      </g>`;
    })
    .join("");

  return `<svg viewBox="0 0 ${W} ${H}" role="group" aria-label="Yard map, hive positions in metres"
    data-min-x="${minX}" data-min-y="${minY}" data-off-x="${offX.toFixed(2)}" data-pad-t="${pad.t}" data-scale="${scale.toFixed(4)}">${grid}${edges}${nodes}</svg>`;
}

/* ── Side panel ──────────────────────────────────────────────────────── */
function paintPicker(h) {
  const swatches = PAINTS.map(
    ([name, hex]) =>
      `<button type="button" class="swatch" style="--swatch:${hex}" data-paint="${hex}" data-paint-hive="${esc(h.id)}" aria-pressed="${(h.color || "").toLowerCase() === hex}" title="${name}" aria-label="Paint ${esc(shortName(h))} ${name.toLowerCase()}"></button>`,
  ).join("");
  return `<div class="paint">
    <div class="paint-head"><strong>Hive colour</strong>${h.color ? `<button type="button" class="link-btn" data-paint="" data-paint-hive="${esc(h.id)}">Use status colour</button>` : ""}</div>
    <div class="swatches">${swatches}
      <label class="swatch custom" title="Any colour"><span class="sr-only">Any colour for ${esc(shortName(h))}</span><input type="color" value="${esc(h.color || "#e9c46a")}" data-paint-hive="${esc(h.id)}" /></label>
    </div>
    <p class="hint">Bees tell blue, yellow and white apart best. Painting neighbours differently helps them find their own hive and reduces drift.</p>
  </div>`;
}

function hiveDetail(key, h) {
  if (!h) {
    return yardEdit[key]
      ? `<p class="map-hint">Drag hives to where they stand. Select one and use the arrow keys to move it ${SNAP_M} m, or 1 m with Shift. Lines show distances under ${MEASURE_M} m; red means a critical hive is within ${DRIFT_M} m.</p>`
      : '<p class="map-hint">Select a hive on the map to see its numbers and set its colour.</p>';
  }
  const s = statusOf(h.overall);
  const stat = (label, v, unit) => `<div><dt>${label}</dt><dd>${v != null ? `${num(v)}${unit ? `<small>${unit}</small>` : ""}` : "–"}</dd></div>`;
  const p = positionOf(key, h);
  return `<div class="map-detail">
    <div class="map-detail-head"><strong>${esc(displayName(h))}</strong>${badge(s)}</div>
    <p class="map-detail-meta">${isSynthetic(h) ? "Demo data" : "Measured"}${h.latest_date ? `, last inspected ${esc(dateLabel(h.latest_date))}` : ", not inspected yet"}. Stands at ${num(p.x, 2)} m, ${num(p.y, 2)} m${h.placed || yardEdit[key] ? "" : " (default spot)"}.</p>
    <dl class="map-stats">
      ${stat("Mites per day", h.mites_per_day, "")}
      ${stat("Honey", h.honey_kg_hive_est, "kg")}
      ${stat("Brood", h.brood_total_pct, "%")}
      ${stat("Stores", h.stores_weeks, "wk")}
    </dl>
    ${h.flags?.length ? `<p class="map-flag ${s}">${esc(h.flags[0])}</p>` : ""}
    ${paintPicker(h)}
    <div class="map-detail-actions">
      <button type="button" class="btn sm primary" data-hive="${esc(h.id)}" data-destination="history">Open records</button>
      <button type="button" class="btn sm" data-hive="${esc(h.id)}" data-destination="inspect">New inspection</button>
    </div>
  </div>`;
}

function arrangeForm(key, count) {
  const a = yardEdit[key].arrange;
  return `<form class="arrange" data-arrange="${esc(key)}">
    <strong>Arrange in rows</strong>
    <label>Rows <input name="rows" type="number" min="1" max="${count}" step="1" value="${a.rows}" /></label>
    <label>Between hives, m <input name="spacing" type="number" min="0.5" max="50" step="0.25" value="${a.spacing}" /></label>
    <label>Between rows, m <input name="gap" type="number" min="0.5" max="50" step="0.25" value="${a.gap}" /></label>
    <label>Pattern
      <select name="pattern"><option value="straight"${a.pattern === "straight" ? " selected" : ""}>Straight</option><option value="staggered"${a.pattern === "staggered" ? " selected" : ""}>Staggered</option></select>
    </label>
    <button type="submit" class="btn sm">Arrange</button>
  </form>`;
}

function farmMapPanel(key, members, links, showFarmName) {
  const farm = farmByKey(key);
  const editing = yardEdit[key];
  const title = showFarmName ? `${farm?.name || "Unassigned"}` : "Yard map";
  const sub = editing
    ? `Editing the layout of ${farm?.name || "these hives"}. Nothing is saved until you select Save layout.`
    : `${showFarmName && farm?.location ? `${farm.location}. ` : ""}${members.length} hive${members.length === 1 ? "" : "s"}, drawn to scale${members.some((h) => !h.placed) ? ". Hives you have not placed yet stand in a default grid" : ""}.`;
  const actions = !members.length
    ? ""
    : editing
      ? `<button type="button" class="btn sm" data-yard-reset="${esc(key)}">Default grid</button>
         <button type="button" class="btn sm" data-yard-cancel="${esc(key)}">Cancel</button>
         <button type="button" class="btn sm primary" data-yard-save="${esc(key)}"${editing.dirty ? "" : " disabled"}>Save layout</button>`
      : `<button type="button" class="btn sm" data-yard-edit="${esc(key)}">Edit layout</button>`;
  const head = `<header class="panel-head">
      <div class="panel-title-group"><h2>${esc(title)}</h2><span class="sub-text">${esc(sub)}</span></div>
      <div class="page-actions">${actions}</div>
    </header>
    <div class="map-legend map-legend-row">
      <span><i class="dot good"></i>Below 3</span><span><i class="dot watch"></i>3–10</span><span><i class="dot act"></i>10+ mites/day</span>
      ${editing ? '<span><i class="key-line measure"></i>Distance</span><span><i class="key-line high"></i>Within 4 m of a critical hive</span>' : '<span><i class="key-line high"></i>High exposure</span><span><i class="key-line"></i>Moderate</span>'}
      <span><i class="key-ring"></i>Measured</span>
    </div>`;
  if (!members.length) {
    return `<section class="panel farm-map">${head}${emptyState(
      "No hives on this farm yet",
      "Add a hive to place it on the yard map.",
      '<button class="btn primary sm" type="button" data-add-hive>Add hive</button>',
    )}</section>`;
  }
  if (mapSelection[key] && !members.some((h) => h.id === mapSelection[key])) delete mapSelection[key];
  const byId = Object.fromEntries(members.map((h) => [h.id, h]));
  const sorted = [...links].sort((a, b) => Number(b.risk === "high") - Number(a.risk === "high") || a.distance_m - b.distance_m);
  const pairs = sorted.length
    ? sorted
        .map(
          (l) => `<button type="button" class="drift-item ${l.risk === "high" ? "high" : ""}" data-map-hive="${esc(l.to_id)}" data-map-farm="${esc(key)}">
            <span class="drift-item-top"><span>${esc(shortName(byId[l.from_id] || { name: l.from_name }))} → ${esc(shortName(byId[l.to_id] || { name: l.to_name }))}</span><span class="drift-dist">${esc(l.distance_m)} m</span></span>
            <small>${l.risk === "high" ? "High" : "Moderate"} exposure, source ${num(byId[l.from_id]?.mites_per_day)} mites/day</small>
          </button>`,
        )
        .join("")
    : '<p class="hint">No hive is within 4 m of a critical hive.</p>';
  return `<section class="panel farm-map${editing ? " editing" : ""}" data-farm-map="${esc(key)}">
    ${head}
    ${editing ? arrangeForm(key, members.length) : ""}
    <div class="map-workspace">
      <div class="apiary-map-canvas">${yardSvg(key, members, links)}</div>
      <aside class="drift-sidebar">
        ${hiveDetail(key, byId[mapSelection[key]])}
        ${editing ? "" : `<h4>Exposed pairs <span class="count">${sorted.length}</span></h4><div class="drift-list">${pairs}</div>`}
      </aside>
    </div>
  </section>`;
}

function renderFarmMaps() {
  const wrap = $("farm-maps");
  if (!wrap) return;
  const links = state?.apiary?.drift_links || [];
  const keys = selectedFarm === "all" ? farms().filter((f) => f.hive_count).map((f) => farmKey(f.id)) : [selectedFarm];
  wrap.innerHTML = keys
    .map((key) => {
      const members = hivesOfFarm(key);
      const ids = new Set(members.map((h) => h.id));
      return farmMapPanel(key, members, links.filter((l) => ids.has(l.from_id) && ids.has(l.to_id)), selectedFarm === "all");
    })
    .join("");
}

function refocus(key, id) {
  document.querySelector(`[data-farm-map="${CSS.escape(key)}"] .map-node[data-map-hive="${CSS.escape(id)}"]`)?.focus({ preventScroll: true });
}

function pickMapHive(key, id) {
  mapSelection[key] = mapSelection[key] === id && !yardEdit[key] ? undefined : id;
  renderFarmMaps();
  refocus(key, id);
}

/* ── Layout editing ──────────────────────────────────────────────────── */
function startEdit(key) {
  const members = hivesOfFarm(key);
  yardEdit[key] = {
    pos: Object.fromEntries(members.map((h) => [h.id, { x: h.x_m || 0, y: h.y_m || 0 }])),
    dirty: false,
    arrange: { rows: Math.max(1, Math.round(Math.sqrt(members.length))), spacing: 2.5, gap: 2.5, pattern: "straight" },
  };
  renderFarmMaps();
}

function arrange(key, rows, spacing, gap, pattern) {
  const members = hivesOfFarm(key).sort(byHiveName);
  const cols = Math.ceil(members.length / rows);
  members.forEach((h, i) => {
    const r = Math.floor(i / cols);
    const c = i % cols;
    yardEdit[key].pos[h.id] = { x: snap(c * spacing + (pattern === "staggered" && r % 2 ? spacing / 2 : 0)), y: snap(r * gap) };
  });
  Object.assign(yardEdit[key], { dirty: true, arrange: { rows, spacing, gap, pattern } });
  renderFarmMaps();
}

async function saveLayout(key, button) {
  const edit = yardEdit[key];
  const positions = Object.entries(edit.pos).map(([hive_id, p]) => ({ hive_id, x_m: p.x, y_m: p.y }));
  await withButton(button, async () => {
    await api("/api/hive_layout", { farm_id: farmIdOfKey(key), positions });
    delete yardEdit[key];
    await loadState();
    toast("Layout saved. Drift links now use the new distances.");
  });
}

async function resetLayout(key, button) {
  await withButton(button, async () => {
    await api("/api/hive_layout", { farm_id: farmIdOfKey(key), reset: true });
    delete yardEdit[key];
    await loadState();
    toast("Hives are back in the default grid.");
  });
}

// Dragging a hive tile: move it live, then snap and redraw on release.
let drag = null;

function svgPoint(svg, event) {
  const pt = svg.createSVGPoint();
  pt.x = event.clientX;
  pt.y = event.clientY;
  return pt.matrixTransform(svg.getScreenCTM().inverse());
}

document.addEventListener("pointerdown", (event) => {
  const node = event.target.closest(".map-node.draggable");
  if (!node || event.button !== 0) return;
  const svg = node.ownerSVGElement;
  const start = svgPoint(svg, event);
  drag = { node, svg, start, key: node.dataset.mapFarm, id: node.dataset.mapHive, moved: false, pointer: event.pointerId };
  node.setPointerCapture(event.pointerId);
  node.classList.add("dragging");
  event.preventDefault();
});

document.addEventListener("pointermove", (event) => {
  if (!drag || event.pointerId !== drag.pointer) return;
  const p = svgPoint(drag.svg, event);
  const dx = p.x - drag.start.x;
  const dy = p.y - drag.start.y;
  if (Math.hypot(dx, dy) > 2) drag.moved = true;
  drag.node.setAttribute("transform", `translate(${dx.toFixed(1)} ${dy.toFixed(1)})`);
  drag.dx = dx;
  drag.dy = dy;
});

function endDrag(event) {
  if (!drag || event.pointerId !== drag.pointer) return;
  const { key, id, svg, moved, dx = 0, dy = 0 } = drag;
  drag = null;
  mapSelection[key] = id;
  if (moved) {
    const scale = Number(svg.dataset.scale);
    const p = yardEdit[key].pos[id];
    yardEdit[key].pos[id] = { x: snap(p.x + dx / scale), y: snap(p.y + dy / scale) };
    yardEdit[key].dirty = true;
  }
  renderFarmMaps();
  refocus(key, id);
}
document.addEventListener("pointerup", endDrag);
document.addEventListener("pointercancel", endDrag);

/* ── Events ──────────────────────────────────────────────────────────── */
document.addEventListener("click", (event) => {
  const t = event.target;
  const nodeOrPair = t.closest("[data-map-hive]");
  if (nodeOrPair) {
    if (!nodeOrPair.classList.contains("draggable")) pickMapHive(nodeOrPair.dataset.mapFarm, nodeOrPair.dataset.mapHive);
    return;
  }
  const el = t.closest("[data-yard-edit],[data-yard-cancel],[data-yard-save],[data-yard-reset],[data-paint]");
  if (!el) return;
  if (el.dataset.yardEdit) startEdit(el.dataset.yardEdit);
  if (el.dataset.yardCancel) {
    delete yardEdit[el.dataset.yardCancel];
    renderFarmMaps();
  }
  if (el.dataset.yardSave) saveLayout(el.dataset.yardSave, el);
  if (el.dataset.yardReset) resetLayout(el.dataset.yardReset, el);
  if (el.dataset.paint !== undefined && el.tagName === "BUTTON") paintHive(el.dataset.paintHive, el.dataset.paint || null, el);
});

document.addEventListener("change", (event) => {
  const input = event.target.closest('input[type="color"][data-paint-hive]');
  if (input) paintHive(input.dataset.paintHive, input.value, null);
});

document.addEventListener("submit", (event) => {
  const form = event.target.closest("form[data-arrange]");
  if (!form) return;
  event.preventDefault();
  const f = new FormData(form);
  const rows = Math.max(1, Math.round(Number(f.get("rows")) || 1));
  const spacing = Math.max(0.5, Number(f.get("spacing")) || 2.5);
  const gap = Math.max(0.5, Number(f.get("gap")) || 2.5);
  arrange(form.dataset.arrange, rows, spacing, gap, f.get("pattern") === "staggered" ? "staggered" : "straight");
});

document.addEventListener("keydown", (event) => {
  const node = event.target.closest?.(".map-node");
  if (!node) return;
  const key = node.dataset.mapFarm;
  const id = node.dataset.mapHive;
  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    pickMapHive(key, id);
    return;
  }
  const move = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] }[event.key];
  if (!move || !yardEdit[key]) return;
  event.preventDefault();
  const stepM = event.shiftKey ? 1 : SNAP_M;
  const p = yardEdit[key].pos[id];
  yardEdit[key].pos[id] = { x: snap(p.x + move[0] * stepM), y: snap(p.y + move[1] * stepM) };
  yardEdit[key].dirty = true;
  mapSelection[key] = id;
  renderFarmMaps();
  refocus(key, id);
});

async function paintHive(hiveId, color, button) {
  const run = async () => {
    await api("/api/hive_style", { hive_id: hiveId, color });
    await loadState();
  };
  try {
    if (button) await withButton(button, run);
    else await run();
  } catch (e) {
    toast(e.message, true);
  }
}
