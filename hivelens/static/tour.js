"use strict";
// Short guided tours. "Explore a saved analysis" walks through a finished inspection;
// "Try your own photos" walks through the inspection form. Each step points at a real
// element on the page; steps whose element is missing (no claims yet, say) are skipped.
// Uses helpers from app.js (state, store).

const TOURS = {
  explore: [
    {
      sel: "#history-result .record-head",
      title: "One saved inspection",
      text: "This is a finished photo analysis: which hive, which day, and its status.",
    },
    {
      sel: "#history-result .figures .figure",
      title: "The photo, marked up",
      text: "Green: mites SAM 3.1 found. Blue: spots Muse Spark confirmed. Red cross: spots the size and shape checks rejected as debris. Select a photo to see it full size.",
    },
    {
      sel: "#history-result .metric-grid",
      title: "What was measured",
      text: "Numbers measured from the photo by plain code, not guessed by a model: mites per day, rejected debris, brood and honey.",
    },
    {
      sel: "#history-result .claims-box",
      title: "Every claim is checked",
      text: "Muse Spark states what it sees, and each claim is checked against the measurements. Only verified claims can reach the report.",
    },
    {
      sel: "#history-result .report-summary",
      title: "The report",
      text: "A short summary, the findings that passed the check, and what to do next.",
    },
    {
      sel: "#history-trends",
      title: "Change over time",
      text: "Every inspection is kept, so you can follow mites, honey, brood and stores from one visit to the next.",
    },
  ],
  own: [
    {
      sel: "#inspection-hive",
      title: "1. Choose the hive",
      text: "Pick the hive the photos come from. No hive yet? Use Add hive above.",
    },
    {
      sel: "#board-drop",
      title: "2. Add a sticky-board photo",
      text: "This counts the mites. Use a sharp, full-resolution photo of the whole board.",
    },
    {
      sel: "#board-sample",
      title: "No photo at hand?",
      text: "Pick a sample board from the public dataset to see a real result.",
    },
    {
      sel: "#frames-drop",
      title: "3. Frames, if you like",
      text: "Optional: frame photos give honey, brood and pollen.",
    },
    {
      sel: "#inspection-days",
      title: "4. Days on the board",
      text: "How long the board was under the hive, so the count becomes mites per day.",
    },
    {
      sel: "#run-inspection",
      title: "5. Run it",
      text: "It takes one to three minutes. Progress shows at the bottom right, and the result opens in Hive records.",
      extra: () => (state && !state.has_api_key ? " Running needs a MODEL_API_KEY in the .env file." : ""),
    },
  ],
};

let tour = null; // { name, steps, i }
let tourLayer = null;

function visible(el) {
  if (!el) return false;
  const r = el.getBoundingClientRect();
  return r.width > 0 && r.height > 0;
}

function tourSteps(name) {
  return TOURS[name].filter((s) => visible(document.querySelector(s.sel)));
}

function buildLayer() {
  if (tourLayer) return tourLayer;
  const spot = document.createElement("div");
  spot.className = "tour-spot";
  const card = document.createElement("div");
  card.className = "tour-card";
  card.setAttribute("role", "dialog");
  card.setAttribute("aria-live", "polite");
  card.setAttribute("aria-labelledby", "tour-title");
  card.innerHTML = `<p class="tour-count" id="tour-count"></p>
    <h3 id="tour-title"></h3>
    <p id="tour-text"></p>
    <div class="tour-actions">
      <button type="button" class="link-btn" data-tour-act="skip">Skip tour</button>
      <span>
        <button type="button" class="btn sm" data-tour-act="back">Back</button>
        <button type="button" class="btn sm primary" data-tour-act="next">Next</button>
      </span>
    </div>`;
  document.body.append(spot, card);
  tourLayer = { spot, card };
  return tourLayer;
}

function placeTour() {
  if (!tour) return;
  const step = tour.steps[tour.i];
  const el = document.querySelector(step.sel);
  const { spot, card } = tourLayer;
  if (!visible(el)) return endTour();
  const r = el.getBoundingClientRect();
  const pad = 6;
  Object.assign(spot.style, { top: `${r.top - pad}px`, left: `${r.left - pad}px`, width: `${r.width + pad * 2}px`, height: `${r.height + pad * 2}px` });
  const cw = card.offsetWidth;
  const ch = card.offsetHeight;
  const below = r.bottom + pad + 12;
  const above = r.top - pad - 12 - ch;
  // Below the element if it fits, else above; for an element taller than the screen, pin the card low.
  const top = below + ch < innerHeight - 8 ? below : above >= 8 ? above : innerHeight - ch - 16;
  const left = Math.min(Math.max(8, r.left), innerWidth - cw - 8);
  Object.assign(card.style, { top: `${top}px`, left: `${left}px` });
}

function showStep() {
  const step = tour.steps[tour.i];
  const { card } = tourLayer;
  card.querySelector("#tour-count").textContent = `${tour.i + 1} of ${tour.steps.length}`;
  card.querySelector("#tour-title").textContent = step.title;
  card.querySelector("#tour-text").textContent = step.text + (step.extra ? step.extra() : "");
  card.querySelector('[data-tour-act="back"]').hidden = tour.i === 0;
  card.querySelector('[data-tour-act="next"]').textContent = tour.i === tour.steps.length - 1 ? "Done" : "Next";
  const el = document.querySelector(step.sel);
  el.scrollIntoView({ block: "center", behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
  placeTour();
  setTimeout(placeTour, 350); // after the scroll settles
  card.querySelector('[data-tour-act="next"]').focus({ preventScroll: true });
}

function startTour(name) {
  const steps = tourSteps(name);
  if (!steps.length) return;
  buildLayer();
  tour = { name, steps, i: 0 };
  document.documentElement.classList.add("touring");
  showStep();
}

function endTour() {
  if (!tour) return;
  store.set(`tour-${tour.name}`, true);
  tour = null;
  document.documentElement.classList.remove("touring");
  tourLayer?.spot.remove();
  tourLayer?.card.remove();
  tourLayer = null;
}

// Start a tour once the page it needs has finished rendering (the record loads asynchronously).
function startTourWhenReady(name, timeoutMs = 8000) {
  const first = TOURS[name][0].sel;
  const until = performance.now() + timeoutMs;
  const tick = () => {
    if (visible(document.querySelector(first))) return setTimeout(() => startTour(name), 250);
    if (performance.now() < until) setTimeout(tick, 150);
  };
  tick();
}

document.addEventListener(
  "click",
  (event) => {
    const act = event.target.closest("[data-tour-act]");
    if (act && tour) {
      const a = act.dataset.tourAct;
      if (a === "skip") endTour();
      if (a === "back" && tour.i > 0) {
        tour.i -= 1;
        showStep();
      }
      if (a === "next") {
        if (tour.i < tour.steps.length - 1) {
          tour.i += 1;
          showStep();
        } else endTour();
      }
      return;
    }
    if (event.target.closest("#welcome-example:not(:disabled)")) startTourWhenReady("explore");
    else if (event.target.closest('.welcome-actions a[href="#inspect"]')) startTourWhenReady("own");
    const replay = event.target.closest("[data-tour]");
    if (replay) {
      endTour();
      startTourWhenReady(replay.dataset.tour, 2000);
    }
  },
  true,
);

document.addEventListener("keydown", (event) => {
  if (tour && event.key === "Escape") endTour();
});
addEventListener("resize", () => requestAnimationFrame(placeTour));
addEventListener("scroll", () => requestAnimationFrame(placeTour), { passive: true });
addEventListener("hashchange", () => setTimeout(() => tour && !visible(document.querySelector(tour.steps[tour.i].sel)) && endTour(), 200));
