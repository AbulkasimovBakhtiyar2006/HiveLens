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
      if (view === "overview") renderFarmConditions();
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

function farmWeatherCard(farm) {
  if (farm.lat == null) {
    return `<div class="wcard empty">
      <strong>${esc(farm.name)}</strong>
      <p>No location yet.</p>
      <button type="button" class="link-btn" data-edit-farm="${esc(farm.id)}">Add location</button>
    </div>`;
  }
  const entry = loadWeather(farm.id);
  const c = entry.data?.current;
  return `<button type="button" class="wcard" data-farm="${esc(farm.id)}">
    ${c ? weatherIcon(c, "md") : '<span class="wx wx-md placeholder"></span>'}
    <span class="wcard-body">
      <strong>${esc(farm.name)}</strong>
      ${
        c
          ? `<span class="wcard-temp">${num(c.temp_c, 0)}°C <span class="muted">${esc(c.text)}</span></span>
             <span class="wcard-meta">${windArrow(c.wind_dir_deg)}${num(c.wind_ms)} m/s, gusts ${num(c.gust_ms, 0)}</span>
             <span class="flight-tag ${c.flight.level}">Bee flight: ${FLIGHT[c.flight.level]}</span>`
          : `<span class="wcard-meta">${entry.error ? esc(entry.error) : "Loading…"}</span>`
      }
    </span>
  </button>`;
}

function renderFarmConditions() {
  const el = $("farm-conditions");
  if (!el || !state) return;
  if (selectedFarm === "all") {
    const real = farms().filter((f) => f.id);
    el.innerHTML = real.length
      ? `<section class="panel"><header class="panel-head"><div class="panel-title-group"><h2>Weather on the farms</h2><span class="sub-text">Select a farm for the hourly forecast.</span></div></header><div class="wcards">${real.map(farmWeatherCard).join("")}</div></section>`
      : "";
    return;
  }
  const farm = farmByKey(selectedFarm);
  el.innerHTML = farm?.id ? farmConditionsPanel(farm) : "";
}

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
