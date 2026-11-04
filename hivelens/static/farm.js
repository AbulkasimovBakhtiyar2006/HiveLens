"use strict";
// Farm details, weather at each farm, and the resizable sidebar.
// Runs after app.js and uses its helpers ($, esc, api, num, store, state, farms, …).

/* ── Resizable sidebar ───────────────────────────────────────────────── */
const SIDE_MIN = 200;
const SIDE_MAX = 440;
const SIDE_DEFAULT = 236;

function setSideWidth(px, save = true) {
  const w = Math.round(Math.min(SIDE_MAX, Math.max(SIDE_MIN, px)));
  document.documentElement.style.setProperty("--side-w", `${w}px`);
  const handle = $("sidebar-resizer");
  if (handle) handle.setAttribute("aria-valuenow", String(w));
  if (save) store.set("side-w", w);
  return w;
}

(function initResizer() {
  const handle = $("sidebar-resizer");
  if (!handle) return;
  const saved = store.get("side-w", SIDE_DEFAULT);
  setSideWidth(Number(saved) || SIDE_DEFAULT, false);
  let dragging = false;
  handle.addEventListener("pointerdown", (event) => {
    dragging = true;
    handle.setPointerCapture(event.pointerId);
    document.documentElement.classList.add("resizing");
  });
  handle.addEventListener("pointermove", (event) => {
    if (dragging) setSideWidth(event.clientX, false);
  });
  const stop = (event) => {
    if (!dragging) return;
    dragging = false;
    handle.releasePointerCapture?.(event.pointerId);
    document.documentElement.classList.remove("resizing");
    setSideWidth(handle.getBoundingClientRect().left + handle.offsetWidth / 2);
  };
  handle.addEventListener("pointerup", stop);
  handle.addEventListener("pointercancel", stop);
  handle.addEventListener("dblclick", () => setSideWidth(SIDE_DEFAULT));
  handle.addEventListener("keydown", (event) => {
    const now = Number(handle.getAttribute("aria-valuenow")) || SIDE_DEFAULT;
    const step = event.shiftKey ? 48 : 16;
    const next = { ArrowLeft: now - step, ArrowRight: now + step, Home: SIDE_MIN, End: SIDE_MAX }[event.key];
    if (next === undefined) return;
    event.preventDefault();
    setSideWidth(next);
  });
})();

/* ── Bee breeds ──────────────────────────────────────────────────────── */
const BREEDS = {
  carnica: ["Carniolan", "A. m. carnica", "Gentle, winters well and builds up fast in spring. Swarms readily."],
  ligustica: ["Italian", "A. m. ligustica", "Gentle and productive with large colonies. Uses more stores over winter."],
  buckfast: ["Buckfast", "hybrid line", "Gentle, low swarming, good honey yields."],
  caucasica: ["Caucasian", "A. m. caucasica", "Gentle, long tongue, heavy propolis use, slower spring build-up."],
  mellifera: ["Central Russian (dark European)", "A. m. mellifera", "Very winter hardy and thrifty with stores. Can be defensive."],
  carpatica: ["Carpathian", "A. m. carpatica", "Gentle, winter hardy and low swarming."],
  local: ["Local or mixed", "", "Traits vary. Note what you see at inspections."],
};
// Rough guide to what beekeepers usually keep in a country; shown only while no breed is set.
const BREED_HINTS = {
  KZ: "Central Russian, Carpathian and Carniolan bees are common in Kazakhstan.",
  RU: "Central Russian and Carpathian bees are common in Russia.",
  KG: "Carpathian and Carniolan bees are common in Kyrgyzstan.",
  UZ: "Carpathian and Caucasian bees are common in Uzbekistan.",
  UA: "Carpathian and Ukrainian steppe bees are common in Ukraine.",
  SI: "The Carniolan bee is native to Slovenia.",
  AT: "Carniolan bees are the usual choice in Austria.",
  DE: "Carniolan and Buckfast bees are common in Germany.",
  IT: "The Italian bee is native to Italy.",
  GE: "The Caucasian grey mountain bee is native to Georgia.",
  GB: "Buckfast and dark European bees are common in the UK.",
  FR: "Dark European and Buckfast bees are common in France.",
  US: "Italian and Carniolan bees are common in the United States.",
};

function breedBlock(farm) {
  const b = BREEDS[farm.breed];
  if (b) {
    return `<div class="cond-fact"><dt>Bee breed</dt><dd><strong>${esc(b[0])}</strong>${b[1] ? ` <span class="muted">${esc(b[1])}</span>` : ""}<p>${esc(b[2])}</p></dd></div>`;
  }
  const hint = BREED_HINTS[farm.country_code];
  return `<div class="cond-fact"><dt>Bee breed</dt><dd><span class="muted">Not set.</span>${hint ? `<p>${esc(hint)}</p>` : ""}</dd></div>`;
}

/* ── Farm form (add and edit) ────────────────────────────────────────── */
function openFarmDialog(farm = null) {
  $("farm-dialog-title").textContent = farm ? "Edit farm" : "Add farm";
  $("create-farm").textContent = farm ? "Save farm" : "Add farm";
  $("edit-farm-id").value = farm?.id || "";
  $("new-farm-name").value = farm?.name || "";
  $("new-farm-location").value = farm?.location || "";
  $("new-farm-maps").value = farm?.maps_url || "";
  $("new-farm-breed").value = farm?.breed || "";
  $("add-farm-dialog").showModal();
  $("new-farm-name").focus();
}

document.addEventListener(
  "click",
  (event) => {
    const add = event.target.closest("[data-add-farm]");
    const edit = event.target.closest("[data-edit-farm]");
    if (!add && !edit) return;
    event.stopImmediatePropagation();
    openFarmDialog(edit ? farmByKey(edit.dataset.editFarm) : null);
  },
  true,
);

$("add-farm-form").addEventListener("submit", (event) => {
  event.preventDefault();
  const name = $("new-farm-name").value.trim();
  if (!name) return $("new-farm-name").focus();
  const id = $("edit-farm-id").value;
  withButton($("create-farm"), async () => {
    const body = {
      name,
      location: $("new-farm-location").value.trim(),
      maps_url: $("new-farm-maps").value.trim(),
      breed: $("new-farm-breed").value,
    };
    const data = await api(id ? "/api/farm_update" : "/api/farms", id ? { ...body, farm_id: id } : body);
    $("add-farm-dialog").close();
    $("add-farm-form").reset();
    delete weatherCache[data.farm.id];
    selectedFarm = data.farm.id;
    store.set("farm", selectedFarm);
    await loadState();
    go("overview");
    toast(data.warning || `${data.farm.name} ${id ? "saved" : "added"}.`, Boolean(data.warning));
  });
});

/* ── Weather ─────────────────────────────────────────────────────────── */
const weatherCache = {};
const hourPick = {};
const WEATHER_TTL_MS = 10 * 60 * 1000;

function loadWeather(farmId) {
  const hit = weatherCache[farmId];
  if (hit && (hit.promise || Date.now() - hit.at < WEATHER_TTL_MS)) return hit;
  const entry = { at: Date.now(), data: hit?.data || null, error: null };
  entry.promise = api(`/api/weather/${encodeURIComponent(farmId)}`)
    .then((data) => {
      entry.data = data;
      entry.error = null;
    })
    .catch((e) => {
      entry.error = e.message;
    })
    .finally(() => {
      entry.promise = null;
      entry.at = Date.now();
      if (view === "overview") {
        renderFarmConditions();
        renderTopbar();
      }
    });
  weatherCache[farmId] = entry;
  return entry;
}

const COMPASS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"];
const compass = (deg) => (deg == null ? "" : COMPASS[Math.round(((deg % 360) + 360) % 360 / 45) % 8]);
const hourLabel = (iso) => (iso ? iso.slice(11, 16) : "");
const dayLabel = (iso, i) =>
  i === 0 ? "Today" : new Date(`${iso}T12:00:00`).toLocaleDateString(undefined, { weekday: "short", day: "numeric" });
const FLIGHT = { good: "Good", limited: "Limited", none: "No flight" };

function windArrow(deg) {
  // Meteorological direction is where the wind comes from; the arrow shows where it blows to.
  const to = ((deg ?? 0) + 180) % 360;
  return `<svg class="wind-arrow" viewBox="0 0 16 16" aria-hidden="true"><g transform="rotate(${to} 8 8)"><path d="M8 2.5v11M4.5 6 8 2.5 11.5 6"/></g></svg>`;
}

/* Weather icons: Meteocons by Bas Milius (MIT), stored in /static/weather/. */
function weatherIconName(w) {
  const c = Number(w.code ?? 3);
  const d = w.is_day === false ? "night" : "day";
  if (c <= 1) return `clear-${d}`;
  if (c === 2) return `partly-cloudy-${d}`;
  if (c === 3) return `overcast-${d}`;
  if (c === 45 || c === 48) return `fog-${d}`;
  if ([56, 57, 66, 67].includes(c)) return "sleet";
  if (c >= 51 && c <= 55) return "drizzle";
  if (c >= 61 && c <= 65) return "rain";
  if (c >= 80 && c <= 82) return `partly-cloudy-${d}-rain`;
  if (c >= 71 && c <= 77) return "snow";
  if (c === 85 || c === 86) return `partly-cloudy-${d}-snow`;
  if (c === 95) return `thunderstorms-${d}-rain`;
  if (c === 96 || c === 99) return "hail";
  return "cloudy";
}

function weatherIcon(w, size = "md") {
  const windy = (w.wind_ms ?? 0) >= 6.5 || (w.gust_ms ?? 0) >= 12;
  const px = { lg: 168, md: 72, sm: 52 }[size] || 72;
  return `<span class="wx wx-${size}">
    <img src="/static/weather/${weatherIconName(w)}.svg" width="${px}" height="${px}" alt="${esc(w.text || "Weather")}" />
    ${windy && size !== "sm" ? `<img class="wx-wind" src="/static/weather/wind.svg" width="${Math.round(px * 0.5)}" height="${Math.round(px * 0.5)}" alt="Windy" title="Windy" />` : ""}
  </span>`;
}

const statIcon = (name) => `<img class="wx-stat" src="/static/weather/${name}.svg" width="28" height="28" alt="" />`;

function nowBlock(w, when) {
  const fl = w.flight || { level: "none", reason: "" };
  const rain = w.precip_prob != null ? `${w.precip_prob}% chance` : `${num(w.precip_mm ?? 0)} mm`;
  return `<div class="cond-when">${esc(when)}</div>
    <div class="cond-temp">${num(w.temp_c, 0)}<small>°C</small></div>
    <p class="cond-text">${esc(w.text)}${w.feels_c != null ? `, feels like ${num(w.feels_c, 0)} °C` : ""}</p>
    <dl class="cond-stats">
      <div><dt>${statIcon("windsock")}Wind</dt><dd>${windArrow(w.wind_dir_deg)}${num(w.wind_ms)} m/s <span class="muted">${esc(compass(w.wind_dir_deg))}</span></dd></div>
      <div><dt>${statIcon("wind")}Gusts</dt><dd>${num(w.gust_ms)} m/s</dd></div>
      <div><dt>${statIcon("raindrops")}Rain</dt><dd>${esc(rain)}</dd></div>
      ${w.humidity_pct != null ? `<div><dt>${statIcon("humidity")}Humidity</dt><dd>${num(w.humidity_pct, 0)}%</dd></div>` : ""}
    </dl>
    <p class="flight ${fl.level}"><strong>Bee flight: ${FLIGHT[fl.level]}</strong> ${esc(fl.reason)}</p>`;
}

function farmFacts(farm, data) {
  const coords = farm.lat != null ? `${num(farm.lat, 4)}, ${num(farm.lon, 4)}` : "";
  const elev = data?.elevation_m ?? farm.elevation_m;
  return `<dl class="cond-facts">
    <div class="cond-fact"><dt>Place</dt><dd>${esc(farm.place || farm.location || "Not set")}${coords ? `<p>${esc(coords)}${elev != null ? `, ${num(elev, 0)} m above sea level` : ""}</p>` : ""}</dd></div>
    ${hasLocation(farm) ? `<div class="cond-fact cond-location"><dt>Location map</dt><dd>${mapSlot(`farm:${farm.id}`, `Map of ${farm.name}`)}</dd></div>` : ""}
    ${breedBlock(farm)}
  </dl>`;
}

function mapsHref(farm) {
  if (farm.maps_url && /^https?:\/\//i.test(farm.maps_url)) return farm.maps_url;
  if (farm.lat != null) return `https://www.google.com/maps/search/?api=1&query=${farm.lat},${farm.lon}`;
  return "";
}

function farmConditionsPanel(farm) {
  const href = mapsHref(farm);
  const actions = `${href ? `<a class="btn sm" href="${esc(href)}" target="_blank" rel="noopener">Open in Google Maps</a>` : ""}<button type="button" class="btn sm" data-edit-farm="${esc(farm.id)}">Edit farm</button>`;
  const head = (sub) => `<header class="panel-head">
      <div class="panel-title-group"><h2>Weather at the farm</h2><span class="sub-text">${esc(sub)}</span></div>
      <div class="page-actions">${actions}</div>
    </header>`;
  if (farm.lat == null) {
    return `<section class="panel conditions">${head(farm.location || "No location yet")}
      <div class="cond-empty">
        <p>Add a place name or paste a Google Maps link to see wind, rain and bee flight weather for this farm.</p>
        <button type="button" class="btn primary sm" data-edit-farm="${esc(farm.id)}">Add location</button>
      </div>
      <div class="cond-body no-weather">${farmFacts(farm, null)}</div>
    </section>`;
  }
  const entry = loadWeather(farm.id);
  const data = entry.data;
  if (!data) {
    return `<section class="panel conditions">${head(farm.place || farm.location)}
      <div class="cond-empty"><p>${entry.error ? esc(entry.error) : "Loading the forecast…"}</p>${entry.error ? `<button type="button" class="btn sm" data-weather-retry="${esc(farm.id)}">Try again</button>` : ""}</div>
      <div class="cond-body no-weather">${farmFacts(farm, null)}</div>
    </section>`;
  }
  const pick = hourPick[farm.id];
  const shown = pick != null && data.hourly[pick] ? data.hourly[pick] : data.current;
  const when = pick != null && data.hourly[pick] ? `Forecast for ${hourLabel(shown.time)}` : `Now, ${hourLabel(data.current.time)} local time`;
  const hours = data.hourly
    .map((h, i) => {
      const pct = Math.max(0, Math.min(100, h.precip_prob ?? 0));
      return `<button type="button" class="hour" data-weather-hour="${i}" data-weather-farm="${esc(farm.id)}" aria-pressed="${pick === i}">
        <span class="hour-time">${i === 0 ? "Now" : esc(hourLabel(h.time))}</span>
        <span class="hour-temp">${num(h.temp_c, 0)}°</span>
        <span class="hour-rain" title="Chance of rain ${pct}%"><i style="height:${pct}%"></i></span>
        <span class="hour-wind">${num(h.wind_ms, 0)} m/s</span>
        <i class="hour-flight ${h.flight.level}" title="Bee flight: ${FLIGHT[h.flight.level]}"></i>
      </button>`;
    })
    .join("");
  const days = data.daily
    .map(
      (d, i) => `<div class="day">
        ${weatherIcon({ ...d, is_day: true }, "sm")}
        <div><strong>${esc(dayLabel(d.date, i))}</strong><span>${esc(d.text)}</span></div>
        <div class="day-num"><b>${num(d.max_c, 0)}°</b> ${num(d.min_c, 0)}°</div>
        <div class="day-meta">${num(d.precip_mm)} mm, wind to ${num(d.gust_ms, 0)} m/s</div>
      </div>`,
    )
    .join("");
  return `<section class="panel conditions" data-conditions="${esc(farm.id)}">
    ${head(`${farm.place || farm.location}. Open-Meteo forecast, refreshed every 15 minutes.`)}
    <div class="cond-body">
      <div class="cond-scene">${weatherIcon(shown, "lg")}</div>
      <div class="cond-now">${nowBlock(shown, when)}${pick != null ? `<button type="button" class="link-btn" data-weather-hour="now" data-weather-farm="${esc(farm.id)}">Back to now</button>` : ""}</div>
      ${farmFacts(farm, data)}
    </div>
    <div class="cond-hours-head"><h3>Next 24 hours</h3><span class="sub-text">Select an hour to see it above. Bars show the chance of rain.</span></div>
    <div class="cond-hours" role="group" aria-label="Next 24 hours">${hours}</div>
    <div class="cond-days">${days}</div>
  </section>`;
}

// The map selection previews a farm; opening its workspace is an explicit second action.
let locationPick = null;
const hasLocation = (f) => f && Number.isFinite(f.lat) && Number.isFinite(f.lon) && Math.abs(f.lat) <= 90 && Math.abs(f.lon) <= 180;

function locationCard(farm, index) {
  const located = hasLocation(farm);
  const c = located ? loadWeather(farm.id).data?.current : null;
  return `<button type="button" class="location-card" ${located ? `data-location-pick="${esc(farm.id)}" aria-pressed="${locationPick === farm.id}"` : `data-edit-farm="${esc(farm.id)}"`}>
    <span class="location-number${located ? "" : " unplaced"}">${located ? String(index + 1).padStart(2, "0") : "–"}</span>
    <span class="location-card-copy"><strong>${esc(farm.name)}</strong><span>${esc(farm.location || farm.place || "Add a location")}</span>
      <span class="location-card-meta">${farm.hive_count || 0} ${farm.hive_count === 1 ? "hive" : "hives"}${c ? ` · ${num(c.temp_c, 0)}°C · ${esc(c.text)}` : located ? " · Weather pending" : " · Not on the map"}</span>
    </span><span class="location-card-arrow" aria-hidden="true">↗</span>
  </button>`;
}

function locationPreview() {
  const f = farms().find((f) => f.id === locationPick && hasLocation(f));
  if (!f) return '<span class="location-caption">Select a farm to explore its location and weather.</span>';
  return `<div class="location-preview-copy"><strong>${esc(f.name)}</strong><span>${num(f.lat, 4)}, ${num(f.lon, 4)} · ${f.hive_count || 0} hives</span></div>
    <div class="page-actions"><a class="btn sm" href="${esc(mapsHref(f))}" target="_blank" rel="noopener">Google Maps ↗</a><button type="button" class="btn sm primary" data-farm="${esc(f.id)}">Open farm</button></div>`;
}

function mapSlot(key, label, world = false) {
  return `<div class="map-slot ${world ? "world" : "farm"}" data-map-slot="${esc(key)}" aria-label="${esc(label)}">
    <div class="location-map-tools"><span class="map-provider">Map</span><div class="page-actions">
      <button type="button" class="map-tool" data-map-fit="${esc(key)}" aria-label="${world ? "Show all farms on map" : "Recenter farm map"}">${world ? "Show all" : "Recenter"}</button>
      <button type="button" class="map-tool" data-map-type="${esc(key)}" aria-pressed="false" hidden>Satellite</button>
    </div></div><div class="map-mount"><p class="map-offline" role="status">Loading map…</p></div>
  </div>`;
}

function renderFarmConditions() {
  const el = $("farm-conditions");
  if (!el || !state) return;
  const railScroll = el.querySelector(".location-rail")?.scrollTop || 0;
  const focusedFarm = el.contains(document.activeElement) ? document.activeElement?.dataset.locationPick : null;
  if (selectedFarm === "all") {
    const real = farms().filter((f) => f.id && !f.field_archive);
    const located = real.filter(hasLocation);
    if (!located.some((f) => f.id === locationPick)) locationPick = null;
    el.innerHTML = real.length ? `<section class="panel location-panel">
      <header class="panel-head"><div class="panel-title-group"><h2>Farm locations</h2><span class="sub-text">${located.length} on the map · ${real.length} farms</span></div><button type="button" class="btn sm" data-add-farm>Add farm</button></header>
      <div class="location-workspace">
        <div class="location-rail" aria-label="Farms on the map">${real.map((f) => locationCard(f, located.indexOf(f))).join("")}</div>
        ${located.length ? mapSlot("world", "Map of your farms", true) : '<div class="location-empty"><strong>Put your apiary on the map</strong><p>Add a place or coordinates to a farm to see it here.</p><button type="button" class="btn sm" data-edit-farm="'+esc(real[0].id)+'">Add location</button></div>'}
      </div><div class="location-preview" aria-live="polite">${locationPreview()}</div>
    </section>` : "";
  } else {
    const farm = farmByKey(selectedFarm);
    el.innerHTML = farm?.id && !farm.field_archive ? farmConditionsPanel(farm) : "";
  }
  const rail = el.querySelector(".location-rail");
  if (rail) rail.scrollTop = railScroll;
  if (focusedFarm) el.querySelector(`[data-location-pick="${CSS.escape(focusedFarm)}"]`)?.focus({ preventScroll: true });
  mountFarmMaps(el);
}

/* ── Location map providers ──────────────────────────────────────────── */
// One retained map per view. Weather refreshes move the canvas, not recreate the map.
// Google is optional; absence, network failure or rejected credentials fall back to OSM.
const farmMaps = {};
const TILE_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
const TILE_CREDIT = '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> contributors';
let googleMapsLoad;
let googleMapsUnavailable = false;
const reduceMapMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

function loadGoogleMaps() {
  const key = state?.maps?.browser_key;
  if (!key || googleMapsUnavailable) return Promise.resolve(null);
  if (googleMapsLoad) return googleMapsLoad;
  googleMapsLoad = new Promise((resolve) => {
    let settled = false;
    const finish = (value) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      resolve(value);
    };
    const fail = () => {
      googleMapsUnavailable = true;
      finish(null);
      // Authentication errors can arrive after the script loaded successfully.
      for (const [id, entry] of Object.entries(farmMaps)) {
        if (entry.provider !== "google") continue;
        entry.observer?.disconnect();
        entry.dispose();
        entry.el.remove();
        delete farmMaps[id];
      }
      if (view === "overview") mountFarmMaps($("farm-conditions"));
    };
    const timer = setTimeout(fail, 10000);
    window.gm_authFailure = fail;
    window.hiveLensMapsReady = async () => {
      try {
        await Promise.all([google.maps.importLibrary("maps"), google.maps.importLibrary("marker")]);
        finish(googleMapsUnavailable ? null : google.maps);
      } catch { fail(); }
    };
    const script = document.createElement("script");
    const query = new URLSearchParams({ key, v: "weekly", loading: "async", callback: "hiveLensMapsReady" });
    script.src = `https://maps.googleapis.com/maps/api/js?${query}`;
    script.async = true;
    script.onerror = fail;
    document.head.appendChild(script);
  });
  return googleMapsLoad;
}

function mapPinHtml(f, index) {
  return `<span class="location-pin${locationPick === f.id ? " selected" : ""}">${String(index + 1).padStart(2, "0")}</span>`;
}

function createLeafletMap(el, world) {
  const map = L.map(el, { scrollWheelZoom: false, worldCopyJump: true, zoomSnap: 0.5, zoomControl: false, minZoom: 1 });
  L.control.zoom({ position: "bottomright" }).addTo(map);
  L.control.scale({ position: "bottomleft", imperial: false }).addTo(map);
  const tiles = L.tileLayer(TILE_URL, { maxZoom: 19, attribution: TILE_CREDIT }).addTo(map);
  const pins = L.layerGroup().addTo(map);
  let shown = [];
  const draw = () => {
    pins.clearLayers();
    // Nearby farms share a marker at world scale, then separate as the map zooms in.
    const groups = [];
    shown.forEach((f, i) => {
      const point = map.latLngToLayerPoint([f.lat, f.lon]);
      const group = groups.find((g) => g.point.distanceTo(point) < 38);
      if (group) group.items.push({ f, i });
      else groups.push({ point, items: [{ f, i }] });
    });
    for (const { items } of groups) {
      const { f, i } = items[0];
      const cluster = items.length > 1;
      const marker = L.marker([f.lat, f.lon], {
        icon: L.divIcon({ className: "location-marker", html: cluster ? `<span class="location-pin cluster">${items.length}<small>farms</small></span>` : mapPinHtml(f, i), iconSize: [38, 44], iconAnchor: [19, 40] }),
        title: cluster ? `${items.length} farms. Zoom in to explore.` : f.name,
        keyboard: true,
      });
      marker.bindTooltip(items.map(({ f }) => esc(f.name)).join("<br>"), { direction: "top", offset: [0, -40], className: "location-tooltip" });
      marker.on("click", () => cluster
        ? map.fitBounds(items.map(({ f }) => [f.lat, f.lon]), { padding: [64, 64], maxZoom: 14, animate: !reduceMapMotion() })
        : world ? pickLocation(f.id) : selectFarm(farmKey(f.id)));
      marker.addTo(pins);
      marker.getElement()?.setAttribute("aria-label", cluster ? `${items.length} farms. Zoom in to explore.` : `Show ${f.name} on map`);
    }
  };
  map.on("zoomend", draw);
  let tileErrors = 0;
  tiles.on("tileerror", () => {
    if (++tileErrors < 3 || el.querySelector(".map-tile-error")) return;
    const notice = document.createElement("p");
    notice.className = "map-tile-error";
    notice.textContent = "Map tiles unavailable. Farm locations and Google Maps links still work.";
    el.appendChild(notice);
  });
  tiles.on("tileload", () => { tileErrors = 0; el.querySelector(".map-tile-error")?.remove(); });
  return {
    provider: "leaflet", el, map,
    resize: () => map.invalidateSize({ pan: false }),
    update: (farms) => { shown = farms; draw(); },
    fit: () => {
      if (!shown.length) return;
      if (!world || shown.length === 1) map.setView([shown[0].lat, shown[0].lon], world ? 7 : 12, { animate: false });
      else map.fitBounds(shown.map((f) => [f.lat, f.lon]), { padding: [56, 56], maxZoom: 12, animate: false });
    },
    focus: (f) => map.setView([f.lat, f.lon], 12, { animate: !reduceMapMotion() }),
    dispose: () => map.remove(),
  };
}

function createGoogleMap(el, world, g) {
  const map = new g.Map(el, {
    mapId: state?.maps?.map_id || "DEMO_MAP_ID", center: { lat: 30, lng: 20 }, zoom: 2,
    disableDefaultUI: true, zoomControl: true, scaleControl: true, gestureHandling: "cooperative",
    clickableIcons: false, streetViewControl: false,
  });
  let shown = [];
  let pins = [];
  return {
    provider: "google", el, map,
    resize: () => g.event.trigger(map, "resize"),
    update: (farms) => {
      shown = farms;
      pins.forEach((p) => { g.event.clearInstanceListeners(p); p.map = null; });
      pins = shown.map((f, i) => {
        const content = document.createElement("div");
        content.innerHTML = mapPinHtml(f, i);
        const pin = new g.marker.AdvancedMarkerElement({ map, position: { lat: f.lat, lng: f.lon }, title: f.name, content });
        pin.addListener("click", () => world ? pickLocation(f.id) : selectFarm(farmKey(f.id)));
        return pin;
      });
    },
    fit: () => {
      if (!shown.length) return;
      if (!world || shown.length === 1) { map.setCenter({ lat: shown[0].lat, lng: shown[0].lon }); map.setZoom(world ? 7 : 12); }
      else {
        const bounds = new g.LatLngBounds();
        shown.forEach((f) => bounds.extend({ lat: f.lat, lng: f.lon }));
        map.fitBounds(bounds, 56);
      }
    },
    focus: (f) => { map.setCenter({ lat: f.lat, lng: f.lon }); map.setZoom(12); },
    setType: (satellite) => map.setMapTypeId(satellite ? "hybrid" : "roadmap"),
    dispose: () => { pins.forEach((p) => { g.event.clearInstanceListeners(p); p.map = null; }); g.event.clearInstanceListeners(map); },
  };
}

async function mountFarmMap(slot) {
  if (!slot.isConnected) return;
  const key = slot.dataset.mapSlot;
  const world = key === "world";
  const shown = world ? farms().filter((f) => f.id && hasLocation(f)) : [farmByKey(key.slice(5))].filter(hasLocation);
  if (!shown.length) return;
  let entry = farmMaps[key];
  if (!entry) {
    const g = await loadGoogleMaps();
    if (!slot.isConnected) return;
    // Another weather refresh may have finished mounting while Google loaded.
    entry = farmMaps[key];
    if (!entry) {
      if (!g && typeof L === "undefined") {
        slot.querySelector(".map-mount").innerHTML = '<p class="map-offline">Map unavailable. Use the farm list or open its location in Google Maps.</p>';
        return;
      }
      const el = document.createElement("div");
      el.className = "farm-map-canvas";
      slot.querySelector(".map-mount").replaceChildren(el);
      try { entry = g ? createGoogleMap(el, world, g) : createLeafletMap(el, world); }
      catch {
        if (typeof L === "undefined") { el.textContent = "Map unavailable. Open the location in Google Maps."; return; }
        el.replaceChildren();
        entry = createLeafletMap(el, world);
      }
      farmMaps[key] = entry;
      entry.observer = new ResizeObserver(() => { if (entry.el.isConnected) entry.resize(); });
      entry.observer.observe(el);
    }
  }
  slot.querySelector(".map-mount").replaceChildren(entry.el);
  slot.querySelector(".map-provider").textContent = entry.provider === "google" ? "Google Maps" : "OpenStreetMap";
  const toggle = slot.querySelector("[data-map-type]");
  toggle.hidden = entry.provider !== "google";
  toggle.setAttribute("aria-pressed", String(Boolean(entry.satellite)));
  const geometry = JSON.stringify(shown.map((f) => [f.id, f.lat, f.lon]));
  const signature = JSON.stringify(shown.map((f) => [f.id, f.name])) + locationPick;
  requestAnimationFrame(() => {
    if (!entry.el.isConnected) return;
    entry.resize();
    if (entry.geometry !== geometry) {
      // Leaflet needs an initial center before projecting marker coordinates.
      if (entry.provider === "leaflet" && !entry.geometry) entry.map.setView([shown[0].lat, shown[0].lon], 2);
      entry.update(shown);
      entry.fit();
      if (world && locationPick) entry.focus(shown.find((f) => f.id === locationPick));
    } else if (entry.signature !== signature) entry.update(shown);
    entry.geometry = geometry;
    entry.signature = signature;
  });
}

// Defer tiles and optional Google SDK until a location map approaches the viewport.
const mapVisibility = new IntersectionObserver((entries) => {
  for (const entry of entries) if (entry.isIntersecting) {
    mapVisibility.unobserve(entry.target);
    mountFarmMap(entry.target);
  }
}, { rootMargin: "240px" });

function mountFarmMaps(root) {
  if (!root) return;
  mapVisibility.disconnect();
  root.querySelectorAll("[data-map-slot]").forEach((slot) => {
    if (farmMaps[slot.dataset.mapSlot]) mountFarmMap(slot);
    else mapVisibility.observe(slot);
  });
}

function pickLocation(id) {
  const farm = farms().find((f) => f.id === id && hasLocation(f));
  if (!farm) return;
  locationPick = id;
  document.querySelectorAll("[data-location-pick]").forEach((el) => el.setAttribute("aria-pressed", String(el.dataset.locationPick === id)));
  const preview = document.querySelector(".location-preview");
  if (preview) preview.innerHTML = locationPreview();
  const entry = farmMaps.world;
  if (entry) { entry.focus(farm); entry.update(farms().filter((f) => f.id && hasLocation(f))); }
}

document.addEventListener("click", (event) => {
  const pick = event.target.closest("[data-location-pick]");
  if (pick) { pickLocation(pick.dataset.locationPick); return; }
  const fit = event.target.closest("[data-map-fit]");
  if (fit) {
    const entry = farmMaps[fit.dataset.mapFit];
    if (fit.dataset.mapFit === "world") {
      locationPick = null;
      document.querySelectorAll("[data-location-pick]").forEach((el) => el.setAttribute("aria-pressed", "false"));
      const preview = document.querySelector(".location-preview");
      if (preview) preview.innerHTML = locationPreview();
      entry?.update(farms().filter((f) => f.id && hasLocation(f)));
    }
    entry?.fit();
  }
  const type = event.target.closest("[data-map-type]");
  if (type) {
    const entry = farmMaps[type.dataset.mapType];
    if (!entry?.setType) return;
    entry.satellite = !entry.satellite;
    entry.setType(entry.satellite);
    type.setAttribute("aria-pressed", String(entry.satellite));
  }
});

document.addEventListener("click", (event) => {
  const hour = event.target.closest("[data-weather-hour]");
  if (hour) {
    const farmId = hour.dataset.weatherFarm;
    const i = hour.dataset.weatherHour === "now" ? null : Number(hour.dataset.weatherHour);
    hourPick[farmId] = i === 0 || hourPick[farmId] === i ? null : i;
    const strip = document.querySelector(".cond-hours");
    const scroll = strip?.scrollLeft || 0;
    renderFarmConditions();
    const again = document.querySelector(".cond-hours");
    if (again) again.scrollLeft = scroll;
    document.querySelector(`[data-weather-hour="${i ?? 0}"][data-weather-farm="${CSS.escape(farmId)}"]`)?.focus({ preventScroll: true });
    return;
  }
  const retry = event.target.closest("[data-weather-retry]");
  if (retry) {
    delete weatherCache[retry.dataset.weatherRetry];
    renderFarmConditions();
  }
});
